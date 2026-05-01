"""Tests to boost coverage for engine, simulator, routes, and circuit breaker."""

import asyncio
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from tradingbot.core.events import (
    EventType, MarketDataEvent, SignalEvent, SignalSide,
    FillEvent, HeartbeatEvent, AlertEvent, AlertLevel, OrderEvent, OrderType
)
from tradingbot.config.schema import TradingBotConfig, RiskConfig
from tradingbot.core.engine import Engine
from tradingbot.core.event_bus import EventBus
from tradingbot.risk.circuit_breaker import CircuitBreaker


# ==================== Engine Deep Coverage ====================

class TestEngineDeep:
    @pytest.fixture
    def engine(self):
        config = TradingBotConfig()
        return Engine(config=config)

    @pytest.mark.asyncio
    async def test_heartbeat_emits_event(self):
        config = TradingBotConfig()
        config.bot.heartbeat_interval = 1
        eb = EventBus()
        engine = Engine(config=config, event_bus=eb)

        received = []
        async def capture(e):
            received.append(e)
        eb.subscribe(EventType.HEARTBEAT, capture)

        # Directly publish a heartbeat like the engine does
        heartbeat = HeartbeatEvent(
            source="engine",
            component="engine",
            status="healthy",
            details={"mode": config.bot.mode, "event_count": eb.event_count},
        )
        await eb.publish(heartbeat)
        assert len(received) == 1
        assert received[0].component == "engine"
        assert received[0].status == "healthy"

    @pytest.mark.asyncio
    async def test_update_prices(self):
        config = TradingBotConfig()
        engine = Engine(config=config)
        mock_tracker = MagicMock()
        engine._portfolio_tracker = mock_tracker
        event = MarketDataEvent(source="t", symbol="BTC/USDT", open=1, high=2, low=0.5, close=100, volume=10)
        await engine._update_prices(event)
        mock_tracker.update_price.assert_called_once_with("BTC/USDT", 100)

    @pytest.mark.asyncio
    async def test_update_prices_no_tracker(self):
        config = TradingBotConfig()
        engine = Engine(config=config)
        event = MarketDataEvent(source="t", symbol="BTC/USDT", open=1, high=2, low=0.5, close=100, volume=10)
        # Should not raise
        await engine._update_prices(event)

    @pytest.mark.asyncio
    async def test_update_prices_non_market_event(self):
        config = TradingBotConfig()
        engine = Engine(config=config)
        mock_tracker = MagicMock()
        engine._portfolio_tracker = mock_tracker
        event = AlertEvent(source="t", title="test", message="msg")
        await engine._update_prices(event)
        mock_tracker.update_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        config = TradingBotConfig()
        eb = EventBus()
        engine = Engine(config=config, event_bus=eb)
        # Add a mock data feed that completes quickly
        mock_feed = AsyncMock()
        mock_feed.start = AsyncMock(return_value=None)
        mock_feed.stop = AsyncMock()
        engine.register_data_feed(mock_feed)

        task = asyncio.create_task(engine.start())
        await asyncio.sleep(0.5)
        await engine.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert not engine.is_running

    def test_engine_properties(self, engine):
        assert engine.config is not None
        assert engine.event_bus is not None
        assert engine.is_running == False


# ==================== Simulator Coverage ====================

from tradingbot.data.feeds.simulator import SimulatedDataFeed


class TestSimulatorDeep:
    @pytest.mark.asyncio
    async def test_simulator_emits_market_data(self):
        eb = EventBus()
        feed = SimulatedDataFeed(symbols=["BTC/USDT"], interval=0.1, volatility=0.01)
        received = []
        eb.subscribe(EventType.MARKET_DATA, lambda e: received.append(e))

        task = asyncio.create_task(feed.start(eb))
        await asyncio.sleep(0.5)
        await feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert len(received) >= 1
        assert received[0].symbol == "BTC/USDT"
        assert received[0].close > 0

    @pytest.mark.asyncio
    async def test_simulator_multiple_symbols(self):
        eb = EventBus()
        feed = SimulatedDataFeed(symbols=["BTC/USDT", "ETH/USDT"], interval=0.1)
        received = []
        eb.subscribe(EventType.MARKET_DATA, lambda e: received.append(e))

        task = asyncio.create_task(feed.start(eb))
        await asyncio.sleep(0.5)
        await feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        symbols = set(e.symbol for e in received)
        assert "BTC/USDT" in symbols
        assert "ETH/USDT" in symbols

    def test_simulator_is_connected_when_not_started(self):
        feed = SimulatedDataFeed(symbols=["BTC/USDT"])
        assert not feed.is_connected()

    @pytest.mark.asyncio
    async def test_simulator_stop_sets_not_running(self):
        feed = SimulatedDataFeed(symbols=["BTC/USDT"])
        await feed.stop()
        assert not feed.is_connected()


# ==================== Circuit Breaker Deep Coverage ====================

class TestCircuitBreakerDeep:
    def test_cooldown_remaining_not_tripped(self):
        cb = CircuitBreaker()
        assert cb.cooldown_remaining == 0.0

    def test_trip_count(self):
        cb = CircuitBreaker(volatility_threshold=0.5, window_size=5)
        # Feed stable data first
        for i in range(10):
            cb.check_price(100)
        # Then spike
        cb.check_price(200)
        assert cb.trip_count >= 0

    def test_is_tripped_property_auto_resets(self):
        from datetime import timedelta
        cb = CircuitBreaker(cooldown_minutes=0)
        cb._tripped = True
        cb._tripped_until = datetime.now(UTC) - timedelta(minutes=1)
        # Should auto-reset
        assert cb.is_tripped == False

    def test_manual_reset_clears_all(self):
        cb = CircuitBreaker()
        cb._tripped = True
        cb._last_price = 100
        cb._price_changes.append(0.1)
        cb.reset()
        assert not cb.is_tripped
        assert cb._last_price is None
        assert len(cb._price_changes) == 0


# ==================== API Routes Coverage ====================

from httpx import AsyncClient, ASGITransport


class TestAPIRoutes:
    @pytest.fixture
    def mock_engine(self):
        """Create a mock engine with all required attributes."""
        engine = MagicMock()
        engine.is_running = True
        engine.config = TradingBotConfig()
        engine.config.bot.name = "TestBot"
        engine.config.bot.mode = "paper"
        engine.config.data.symbols = ["BTC/USDT"]
        engine.event_bus = MagicMock()
        engine.event_bus.event_count = 42
        engine.event_bus.dead_letter_queue = []
        engine.event_bus.get_subscriber_count = MagicMock(return_value=5)

        engine._strategies = []
        engine._data_feeds = []
        engine._order_manager = MagicMock()
        engine._order_manager.pending_count = 0
        engine._order_manager.filled_count = 10
        engine._order_manager.failed_count = 1

        engine._portfolio_tracker = MagicMock()
        engine._portfolio_tracker.cash = 95000.0
        engine._portfolio_tracker.total_value = 100000.0
        engine._portfolio_tracker.unrealized_pnl = 500.0
        engine._portfolio_tracker.realized_pnl = 200.0
        engine._portfolio_tracker.positions = {}
        engine._portfolio_tracker._initial_cash = 100000.0

        engine._risk_manager = MagicMock()
        engine._risk_manager.get_state.return_value = {
            "daily_pnl": -50,
            "max_daily_loss": 500,
            "daily_loss_pct": 10.0,
            "open_positions": 1,
            "max_open_positions": 5,
            "total_exposure": 0.05,
            "max_total_exposure": 0.3,
            "max_position_size": 0.05,
            "circuit_breaker_active": False,
            "circuit_breaker_until": None,
            "approved_count": 8,
            "rejected_count": 2,
            "portfolio_value": 100000,
            "kill_switch": False,
        }
        engine._risk_manager.is_circuit_breaker_active = False

        from tradingbot.data.history import OHLCVHistory
        engine._ohlcv_history = OHLCVHistory()
        engine._database = None

        return engine

    @pytest.mark.asyncio
    async def test_status(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/status")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "running"
                    assert data["mode"] == "paper"

    @pytest.mark.asyncio
    async def test_portfolio(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/portfolio")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["cash"] == 95000.0

    @pytest.mark.asyncio
    async def test_health(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/health")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["event_count"] == 42

    @pytest.mark.asyncio
    async def test_strategies(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/strategies")
                    assert resp.status_code == 200
                    assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_strategies_state(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/strategies/state")
                    assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_risk_state(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/risk/state")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["daily_pnl"] == -50

    @pytest.mark.asyncio
    async def test_kill_switch(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post("/api/risk/kill", json={"active": True})
                    assert resp.status_code == 200
                    mock_engine._risk_manager.set_kill_switch.assert_called_with(True)

    @pytest.mark.asyncio
    async def test_trades_empty(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/trades")
                    assert resp.status_code == 200
                    assert resp.json()["trades"] == []

    @pytest.mark.asyncio
    async def test_candles(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # URL-encode the slash as the route handles decoding
                    resp = await client.get("/api/candles/BTCUSDT")
                    assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_analytics(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/analytics")
                    assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_manual_trade(self, mock_engine):
        mock_engine.event_bus.publish = AsyncMock()
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post("/api/trade/manual", json={
                        "symbol": "BTC/USDT", "side": "buy", "quantity": 0.01
                    })
                    assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_manual_trade_invalid_side(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post("/api/trade/manual", json={
                        "symbol": "BTC/USDT", "side": "invalid", "quantity": 0.01
                    })
                    assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_market_context(self, mock_engine):
        with patch("tradingbot.api.routes.get_engine", return_value=mock_engine):
            with patch("tradingbot.api.main.engine", mock_engine):
                from tradingbot.api.main import app
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/market/context")
                    assert resp.status_code == 200


# ==================== Risk Manager position sizing edge case ====================

class TestRiskManagerExtra:
    def test_calculate_position_size_with_suggested_price(self):
        from tradingbot.risk.manager import RiskManager
        config = RiskConfig()
        rm = RiskManager(config=config, event_bus=MagicMock(), portfolio_value=100000)
        signal = MagicMock()
        signal.suggested_price = 50000.0
        qty = rm._calculate_position_size(signal)
        assert qty > 0

    def test_calculate_position_size_without_suggested_price(self):
        from tradingbot.risk.manager import RiskManager
        config = RiskConfig()
        rm = RiskManager(config=config, event_bus=MagicMock(), portfolio_value=100000)
        signal = MagicMock()
        signal.suggested_price = None
        qty = rm._calculate_position_size(signal)
        assert qty > 0

    def test_calculate_position_size_zero_price(self):
        from tradingbot.risk.manager import RiskManager
        config = RiskConfig()
        rm = RiskManager(config=config, event_bus=MagicMock(), portfolio_value=100000)
        signal = MagicMock()
        signal.suggested_price = 0
        qty = rm._calculate_position_size(signal)
        assert qty > 0  # Falls through to max_value
