"""FastAPI application for the trading bot dashboard."""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from tradingbot.config.loader import load_config
from tradingbot.core.engine import Engine
from tradingbot.core.events import EventType

logger = logging.getLogger(__name__)

# Global instances
engine: Engine | None = None
connected_clients: list[WebSocket] = []
_engine_task: asyncio.Task | None = None


def _serialize_for_json(obj: any) -> any:
    """Helper to serialize objects for JSON broadcasting."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_for_json(i) for i in obj]
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    if hasattr(obj, "value"):  # For Enums
        return obj.value
    # Fallback: try str conversion
    return str(obj)


async def broadcast_event(event_type: EventType, data: dict):
    """Broadcast an event to all connected WebSocket clients."""
    if not connected_clients:
        return

    disconnected = []
    message = {"type": event_type.value, "data": _serialize_for_json(data)}

    for client in connected_clients:
        try:
            await client.send_json(message)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        if client in connected_clients:
            connected_clients.remove(client)


async def _event_listener(event):
    """Listener attached to the event bus to forward events to websockets."""
    if hasattr(event, "__dict__"):
        data = {k: v for k, v in event.__dict__.items() if not k.startswith("_")}
        await broadcast_event(event.event_type, data)


def _build_engine(config):
    """Build and wire the full trading engine with all components."""
    from tradingbot.core.event_bus import EventBus
    from tradingbot.data.feeds.simulator import SimulatedDataFeed
    from tradingbot.execution.order_manager import OrderManager
    from tradingbot.portfolio.tracker import PortfolioTracker
    from tradingbot.risk.manager import RiskManager
    from tradingbot.strategy.registry import get_strategy

    # Import builtins to register strategies
    import tradingbot.strategy.builtin.bollinger  # noqa: F401
    import tradingbot.strategy.builtin.rsi_strategy  # noqa: F401
    import tradingbot.strategy.builtin.sma_crossover  # noqa: F401

    event_bus = EventBus()
    eng = Engine(config=config, event_bus=event_bus)

    # 1. Data feed — simulated so the dashboard always has live data
    feed = SimulatedDataFeed(
        symbols=config.data.symbols,
        interval=3.0,
        volatility=0.002,
    )
    eng.register_data_feed(feed)

    # 2. Strategy
    strategy = get_strategy(
        config.strategy.name,
        params=config.strategy.params if config.strategy.params else {},
        event_bus=event_bus,
    )
    eng.register_strategy(strategy)

    # Initialize Database here for the tracker
    # Actually, building the engine is synchronous, but db.initialize is async.
    # We will set the trade_repo externally in lifespan after DB is initialized.
    
    # 3. Portfolio tracker
    initial_capital = config.execution.paper_trading.initial_balance
    portfolio_tracker = PortfolioTracker(initial_cash=initial_capital)
    eng.register_portfolio_tracker(portfolio_tracker)

    # 4. Risk manager
    risk_manager = RiskManager(
        config=config.risk,
        event_bus=event_bus,
        portfolio_value=initial_capital,
    )
    eng.register_risk_manager(risk_manager)

    # 5. Order manager with the actual paper broker
    from tradingbot.execution.brokers.paper_broker import PaperBroker
    paper_broker = PaperBroker(initial_balance=initial_capital)
    order_manager = OrderManager(
        config=config.execution,
        broker=paper_broker,
        event_bus=event_bus,
    )
    eng.register_order_manager(order_manager)

    return eng



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan manager to start and stop the trading bot engine."""
    global engine, _engine_task
    logger.info("Starting API and Bot Engine...")

    config = load_config()
    engine = _build_engine(config)

    # Initialize Database
    from tradingbot.persistence.database import Database
    from tradingbot.persistence.repository import TradeRepository
    
    import os
    db_dir = "/app/data" if os.path.isdir("/app/data") else "./data"
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "tradingbot.db")
    db = Database(url=f"sqlite+aiosqlite:///{db_path}", echo=False)
    await db.initialize()
    engine._database = db
    trade_repo = TradeRepository(db)
    
    if engine._portfolio_tracker:
        engine._portfolio_tracker._trade_repo = trade_repo

    # Subscribe to ALL event types for WebSocket broadcasting
    engine.event_bus.subscribe(EventType.PORTFOLIO, _event_listener)
    engine.event_bus.subscribe(EventType.SIGNAL, _event_listener)
    engine.event_bus.subscribe(EventType.FILL, _event_listener)
    engine.event_bus.subscribe(EventType.ALERT, _event_listener)
    engine.event_bus.subscribe(EventType.ORDER, _event_listener)
    engine.event_bus.subscribe(EventType.HEARTBEAT, _event_listener)
    engine.event_bus.subscribe(EventType.MARKET_DATA, _event_listener)

    # Start the engine in the background (data feeds, strategies, heartbeats)
    _engine_task = asyncio.create_task(engine.start())
    logger.info("Bot Engine Started — streaming simulated market data")

    yield

    logger.info("Stopping Bot Engine...")
    if engine:
        engine._shutdown_event.set()
        if hasattr(engine, "_database"):
            await engine._database.close()
    if _engine_task:
        _engine_task.cancel()
        try:
            await _engine_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Trading Bot Dashboard API",
    description="API for managing and monitoring the autonomous trading bot",
    version="2.0.0",
    lifespan=lifespan,
)

# Allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _handle_ws(websocket: WebSocket):
    """Shared WebSocket handler for both /ws and /ws/ routes."""
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # We don't expect much from the client, just keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await _handle_ws(websocket)


@app.websocket("/ws/")
async def websocket_endpoint_slash(websocket: WebSocket):
    await _handle_ws(websocket)


from tradingbot.api.routes import router

app.include_router(router, prefix="/api")
