"""FastAPI application for the trading bot dashboard."""

import asyncio
import logging
from contextlib import asynccontextmanager
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

def _serialize_for_json(obj: any) -> any:
    """Helper to serialize objects for JSON broadcasting."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_for_json(i) for i in obj]
    if hasattr(obj, "value"):  # For Enums
        return obj.value
    return obj

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
        await broadcast_event(event.type, data)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan manager to start and stop the trading bot engine."""
    global engine
    logger.info("Starting API and Bot Engine...")
    
    config = load_config()
    engine = Engine(config=config)
    await engine._setup_event_handlers()
    
    # Subscribe to events we want to broadcast to the UI
    engine.event_bus.subscribe(EventType.PORTFOLIO, _event_listener)
    engine.event_bus.subscribe(EventType.SIGNAL, _event_listener)
    engine.event_bus.subscribe(EventType.FILL, _event_listener)
    engine.event_bus.subscribe(EventType.ALERT, _event_listener)
    
    engine.event_bus.start()
    
    logger.info("Bot Engine Started")
    
    yield
    
    logger.info("Stopping Bot Engine...")
    if engine:
        await engine.stop()

app = FastAPI(
    title="Trading Bot Dashboard API",
    description="API for managing and monitoring the autonomous trading bot",
    version="1.0.0",
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # We don't expect much from the client, just keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

from tradingbot.api.routes import router
app.include_router(router, prefix="/api")
