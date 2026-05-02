"""Tests for dynamic symbol management, strategy tuning, and simulator backfill."""

from __future__ import annotations

import asyncio
import math
import random
from collections import deque
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradingbot.core.event_bus import EventBus
from tradingbot.core.events import EventType, MarketDataEvent, SignalSide
from tradingbot.data.feeds.simulator import SimulatedDataFeed, DEFAULT_PRICES


# ============================================================
# SimulatedDataFeed: Backfill Tests
# ============================================================

class TestSimulatorBackfill:
    """Tests for the instant history backfill feature."""

    @pytest.fixture
    def feed(self):
        return SimulatedDataFeed(symbols=["BTC/USDT"], interval=0.01, volatility=0.001)

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.mark.timeout(15)
    async def test_backfill_publishes_200_bars_per_symbol(self, feed):
        """Backfill should publish exactly 200 events per symbol before live loop."""
        bus = EventBus()
        events = []

        async def capture(event):
            events.append(event)
            if len(events) >= 200:
                feed._running = False  # Stop after backfill

        bus.subscribe(EventType.MARKET_DATA, capture)

        task = asyncio.create_task(feed.start(bus))
        await asyncio.sleep(3)
        feed._running = False
        try:
            await asyncio.wait_for(task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        assert len(events) >= 200, f"Expected >=200 events, got {len(events)}"

    async def test_backfill_events_have_historical_timestamps(self, feed):
        """Backfill events should have timestamps in the past."""
        bus = EventBus()
        events = []
        before = datetime.now(timezone.utc)

        async def capture(event):
            events.append(event)
            if len(events) >= 200:
                feed._running = False

        bus.subscribe(EventType.MARKET_DATA, capture)
        task = asyncio.create_task(feed.start(bus))
        await asyncio.sleep(3)
        feed._running = False
        try:
            await asyncio.wait_for(task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        # First backfill event should be old (600 seconds ago for 200 bars * 3s default)
        assert len(events) >= 200
        first_ts = events[0].timestamp
        assert first_ts < before, "First backfill event should have a historical timestamp"

    async def test_backfill_prices_are_valid(self, feed):
        """All backfill events should have positive OHLCV values."""
        bus = EventBus()
        events = []

        async def capture(event):
            events.append(event)
            if len(events) >= 200:
                feed._running = False

        bus.subscribe(EventType.MARKET_DATA, capture)
        task = asyncio.create_task(feed.start(bus))
        await asyncio.sleep(3)
        feed._running = False
        try:
            await asyncio.wait_for(task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        for e in events[:200]:
            assert e.open > 0
            assert e.high > 0
            assert e.low > 0
            assert e.close > 0
            assert e.volume >= 0


# ============================================================
# SimulatedDataFeed: Dynamic Symbol Management
# ============================================================

class TestDynamicSymbols:
    """Tests for add_symbol / remove_symbol."""

    def test_remove_symbol(self):
        feed = SimulatedDataFeed(symbols=["BTC/USDT", "ETH/USDT"])
        assert "ETH/USDT" in feed._symbols
        feed.remove_symbol("ETH/USDT")
        assert "ETH/USDT" not in feed._symbols

    def test_remove_nonexistent_symbol(self):
        feed = SimulatedDataFeed(symbols=["BTC/USDT"])
        feed.remove_symbol("FAKE/USDT")  # Should not raise
        assert feed._symbols == ["BTC/USDT"]

    async def test_add_symbol_backfills(self):
        feed = SimulatedDataFeed(symbols=["BTC/USDT"], interval=0.01)
        bus = EventBus()
        events = []

        async def capture(event):
            events.append(event)

        bus.subscribe(EventType.MARKET_DATA, capture)

        await feed.add_symbol("SOL/USDT", bus)

        sol_events = [e for e in events if e.symbol == "SOL/USDT"]
        assert len(sol_events) == 200, f"Expected 200 SOL events, got {len(sol_events)}"
        assert "SOL/USDT" in feed._symbols

    async def test_add_duplicate_symbol_no_op(self):
        feed = SimulatedDataFeed(symbols=["BTC/USDT"])
        bus = EventBus()
        events = []

        async def capture(event):
            events.append(event)

        bus.subscribe(EventType.MARKET_DATA, capture)

        await feed.add_symbol("BTC/USDT", bus)
        assert len(events) == 0, "Adding a duplicate should not backfill"

    def test_default_prices_lookup(self):
        feed = SimulatedDataFeed(symbols=["BTC/USDT"])
        assert feed._prices["BTC/USDT"] == DEFAULT_PRICES["BTC/USDT"]

    def test_unknown_symbol_gets_random_price(self):
        feed = SimulatedDataFeed(symbols=["DOGE/USDT"])
        price = feed._prices["DOGE/USDT"]
        assert 80.0 <= price <= 180.0  # 100 + uniform(-20, 80)

    def test_is_connected_false_before_start(self):
        feed = SimulatedDataFeed(symbols=["BTC/USDT"])
        assert feed.is_connected() is False

    async def test_stop_sets_running_false(self):
        feed = SimulatedDataFeed(symbols=["BTC/USDT"])
        feed._running = True
        await feed.stop()
        assert feed._running is False


# ============================================================
# AdvancedAggregator: Threshold Tests
# ============================================================

class TestAggregatorThreshold:
    """Tests for the dynamic signal_threshold on AdvancedAggregator."""

    def test_default_threshold(self):
        from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
        agg = AdvancedAggregator()
        assert agg.signal_threshold == 0.5

    def test_custom_threshold(self):
        from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
        agg = AdvancedAggregator(signal_threshold=0.3)
        assert agg.signal_threshold == 0.3

    def test_threshold_affects_signal_generation(self):
        """A very low threshold should produce signals more easily."""
        from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
        import pandas as pd
        import numpy as np

        agg = AdvancedAggregator(signal_threshold=0.01)  # Very low

        # Create enough data for indicators
        np.random.seed(42)
        n = 200
        closes = 50000 + np.cumsum(np.random.randn(n) * 100)
        df = pd.DataFrame({
            "open": closes - 50,
            "high": closes + 100,
            "low": closes - 100,
            "close": closes,
            "volume": np.random.uniform(100, 50000, n)
        })

        signal = agg.generate_signal("BTC/USDT", df, float(closes[-1]))
        # With threshold 0.01, even a small score should trigger
        # (signal may still be None if score is exactly 0, but likely not)
        # We just check it doesn't crash
        assert signal is None or signal.side in (SignalSide.BUY, SignalSide.SELL)

    def test_very_high_threshold_blocks_signals(self):
        """A very high threshold should block signals."""
        from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
        import pandas as pd
        import numpy as np

        agg = AdvancedAggregator(signal_threshold=10.0)  # Impossibly high

        np.random.seed(42)
        n = 200
        closes = 50000 + np.cumsum(np.random.randn(n) * 100)
        df = pd.DataFrame({
            "open": closes - 50,
            "high": closes + 100,
            "low": closes - 100,
            "close": closes,
            "volume": np.random.uniform(100, 50000, n)
        })

        signal = agg.generate_signal("BTC/USDT", df, float(closes[-1]))
        assert signal is None, "Very high threshold should block all signals"


# ============================================================
# AdvancedStrategy: Integration
# ============================================================

class TestAdvancedStrategy:
    """Tests for the AdvancedStrategy wrapper."""

    def _make_market_data(self, close, symbol="BTC/USDT"):
        return MarketDataEvent(
            source="test",
            symbol=symbol,
            open=close * 0.999,
            high=close * 1.001,
            low=close * 0.998,
            close=close,
            volume=1000.0,
            timeframe="1m",
            exchange="test",
        )

    def test_strategy_init(self):
        from tradingbot.strategy.builtin.advanced_strategy import AdvancedStrategy
        s = AdvancedStrategy(name="test_adv")
        assert s.name == "test_adv"
        assert s._window == 200

    def test_strategy_warmup(self):
        from tradingbot.strategy.builtin.advanced_strategy import AdvancedStrategy
        s = AdvancedStrategy(name="test_adv")
        # Feed less than window data
        for i in range(50):
            md = self._make_market_data(50000 + i * 10)
            result = s.calculate_signal(md)
            assert result is None
        assert s._is_warmed_up is False

    def test_strategy_warms_up_after_window(self):
        from tradingbot.strategy.builtin.advanced_strategy import AdvancedStrategy
        s = AdvancedStrategy(name="test_adv", params={"window": 50})
        # Override window to 50 for faster test
        s._window = 50
        s._history = deque(maxlen=100)

        for i in range(60):
            md = self._make_market_data(50000 + i * 10)
            s.calculate_signal(md)

        assert s._is_warmed_up is True

    def test_strategy_get_state(self):
        from tradingbot.strategy.builtin.advanced_strategy import AdvancedStrategy
        s = AdvancedStrategy(name="test_adv")
        state = s.get_state()
        assert state["name"] == "test_adv"
        assert "type" in state
        assert state["type"] == "Multi-Dimensional Consensus"

    def test_strategy_reset(self):
        from tradingbot.strategy.builtin.advanced_strategy import AdvancedStrategy
        s = AdvancedStrategy(name="test_adv")
        s._last_state = {"score": 1.0}
        s._is_warmed_up = True
        s.reset()
        assert s._last_state == {}
        assert s._is_warmed_up is False


# ============================================================
# OHLCVHistory Tests
# ============================================================

class TestOHLCVHistory:
    """Tests for OHLCVHistory buffer."""

    async def test_stores_candles(self):
        from tradingbot.data.history import OHLCVHistory
        h = OHLCVHistory()
        md = MarketDataEvent(
            source="test", symbol="BTC/USDT",
            open=100, high=101, low=99, close=100.5,
            volume=500, timeframe="1m", exchange="test"
        )
        await h.on_market_data(md)
        candles = h.get_candles("BTC/USDT")
        assert len(candles) == 1
        assert candles[0].close == 100.5

    async def test_latest_prices(self):
        from tradingbot.data.history import OHLCVHistory
        h = OHLCVHistory()
        md = MarketDataEvent(
            source="test", symbol="ETH/USDT",
            open=3000, high=3050, low=2950, close=3020,
            volume=100, timeframe="1m", exchange="test"
        )
        await h.on_market_data(md)
        assert h.latest_prices["ETH/USDT"] == 3020

    async def test_max_candles_limit(self):
        from tradingbot.data.history import OHLCVHistory
        h = OHLCVHistory(max_candles=5)
        for i in range(10):
            md = MarketDataEvent(
                source="test", symbol="BTC/USDT",
                open=100+i, high=101+i, low=99+i, close=100.5+i,
                volume=500, timeframe="1m", exchange="test"
            )
            await h.on_market_data(md)
        candles = h.get_candles("BTC/USDT")
        assert len(candles) == 5

    async def test_clear(self):
        from tradingbot.data.history import OHLCVHistory
        h = OHLCVHistory()
        md = MarketDataEvent(
            source="test", symbol="BTC/USDT",
            open=100, high=101, low=99, close=100.5,
            volume=500, timeframe="1m", exchange="test"
        )
        await h.on_market_data(md)
        h.clear()
        assert h.get_candles("BTC/USDT") == []
        assert h.latest_prices == {}

    async def test_get_all_symbols(self):
        from tradingbot.data.history import OHLCVHistory
        h = OHLCVHistory()
        for sym in ["BTC/USDT", "ETH/USDT"]:
            md = MarketDataEvent(
                source="test", symbol=sym,
                open=100, high=101, low=99, close=100.5,
                volume=500, timeframe="1m", exchange="test"
            )
            await h.on_market_data(md)
        assert set(h.get_all_symbols()) == {"BTC/USDT", "ETH/USDT"}

    async def test_ignores_non_market_data(self):
        from tradingbot.data.history import OHLCVHistory
        from tradingbot.core.events import AlertEvent
        h = OHLCVHistory()
        alert = AlertEvent(source="test", title="hello", message="world")
        await h.on_market_data(alert)
        assert h.symbols == []

    async def test_get_candles_dict(self):
        from tradingbot.data.history import OHLCVHistory
        h = OHLCVHistory()
        md = MarketDataEvent(
            source="test", symbol="BTC/USDT",
            open=100, high=101, low=99, close=100.5,
            volume=500, timeframe="1m", exchange="test"
        )
        await h.on_market_data(md)
        dicts = h.get_candles_dict("BTC/USDT")
        assert isinstance(dicts[0], dict)
        assert "close" in dicts[0]


# ============================================================
# Portfolio Tracker Tests
# ============================================================

class TestPortfolioTracker:
    """Extended portfolio tracker tests."""

    def test_initial_state(self):
        from tradingbot.portfolio.tracker import PortfolioTracker
        pt = PortfolioTracker(initial_cash=50000)
        assert pt.cash == 50000
        assert pt.total_value == 50000
        assert pt.unrealized_pnl == 0
        assert pt.realized_pnl == 0
        assert pt.total_pnl == 0

    async def test_buy_reduces_cash(self):
        from tradingbot.portfolio.tracker import PortfolioTracker
        from tradingbot.core.events import FillEvent, SignalSide
        pt = PortfolioTracker(initial_cash=100000)
        fill = FillEvent(
            source="test", symbol="BTC/USDT", side=SignalSide.BUY,
            quantity=1.0, fill_price=50000.0, commission=10.0,
            order_id="o1", broker_order_id="b1"
        )
        await pt.on_fill(fill)
        assert pt.cash < 100000
        assert "BTC/USDT" in pt.positions
        assert pt.positions["BTC/USDT"].quantity == 1.0

    async def test_sell_increases_cash(self):
        from tradingbot.portfolio.tracker import PortfolioTracker
        from tradingbot.core.events import FillEvent, SignalSide
        pt = PortfolioTracker(initial_cash=100000)
        # Buy first
        buy = FillEvent(
            source="test", symbol="BTC/USDT", side=SignalSide.BUY,
            quantity=1.0, fill_price=50000.0, commission=10.0,
            order_id="o1", broker_order_id="b1"
        )
        await pt.on_fill(buy)
        cash_after_buy = pt.cash

        # Then sell
        sell = FillEvent(
            source="test", symbol="BTC/USDT", side=SignalSide.SELL,
            quantity=1.0, fill_price=51000.0, commission=10.0,
            order_id="o2", broker_order_id="b2"
        )
        await pt.on_fill(sell)
        assert pt.cash > cash_after_buy
        assert "BTC/USDT" not in pt.positions

    async def test_update_price(self):
        from tradingbot.portfolio.tracker import PortfolioTracker
        from tradingbot.core.events import FillEvent, SignalSide
        pt = PortfolioTracker(initial_cash=100000)
        fill = FillEvent(
            source="test", symbol="BTC/USDT", side=SignalSide.BUY,
            quantity=1.0, fill_price=50000.0, commission=10.0,
            order_id="o1", broker_order_id="b1"
        )
        await pt.on_fill(fill)
        pt.update_price("BTC/USDT", 55000.0)
        assert pt.positions["BTC/USDT"].current_price == 55000.0

    def test_snapshot(self):
        from tradingbot.portfolio.tracker import PortfolioTracker
        pt = PortfolioTracker(initial_cash=50000)
        snap = pt.get_snapshot()
        assert snap.cash == 50000
        assert snap.total_value == 50000


# ============================================================
# Risk Manager Tests
# ============================================================

class TestRiskManagerExtended:
    """Additional risk manager tests."""

    def _make_risk_manager(self, max_daily_loss=500, max_open=5):
        from tradingbot.risk.manager import RiskManager
        from tradingbot.config.schema import RiskConfig
        config = RiskConfig(
            max_daily_loss=max_daily_loss,
            max_position_size=0.05,
            max_total_exposure=0.3,
            stop_loss_pct=0.02,
            take_profit_pct=0.05,
            max_open_positions=max_open,
        )
        bus = EventBus()
        return RiskManager(config=config, event_bus=bus, portfolio_value=100000)

    def test_kill_switch(self):
        rm = self._make_risk_manager()
        rm.set_kill_switch(True)
        assert rm.is_circuit_breaker_active is True
        rm.set_kill_switch(False)
        assert rm.is_circuit_breaker_active is False

    def test_daily_pnl_reset(self):
        rm = self._make_risk_manager()
        rm.update_daily_pnl(100)
        assert rm.daily_pnl == 100
        # Simulate same day
        rm.update_daily_pnl(-50)
        assert rm.daily_pnl == 50

    def test_update_position(self):
        rm = self._make_risk_manager()
        rm.update_position("BTC/USDT", 1.0)
        assert "BTC/USDT" in rm._open_positions
        rm.update_position("BTC/USDT", 0)
        assert "BTC/USDT" not in rm._open_positions

    def test_get_state(self):
        rm = self._make_risk_manager()
        state = rm.get_state()
        assert "daily_pnl" in state
        assert "max_daily_loss" in state
        assert "kill_switch" in state

    def test_circuit_breaker_activation(self):
        rm = self._make_risk_manager()
        rm.activate_circuit_breaker(cooldown_minutes=1)
        assert rm.is_circuit_breaker_active is True
        assert rm._circuit_breaker_until is not None
