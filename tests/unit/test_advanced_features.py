"""Comprehensive tests for analytics, history, strategy state, risk state, and API routes."""

import asyncio
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

# ==================== Analytics Tests ====================

from tradingbot.analytics.performance import PerformanceCalculator, PerformanceMetrics


class TestPerformanceCalculator:
    def test_total_return_positive(self):
        assert PerformanceCalculator.calculate_total_return(110000, 100000) == 10.0

    def test_total_return_negative(self):
        assert PerformanceCalculator.calculate_total_return(90000, 100000) == -10.0

    def test_total_return_zero_capital(self):
        assert PerformanceCalculator.calculate_total_return(100, 0) == 0.0

    def test_sharpe_ratio_basic(self):
        returns = [0.01, 0.02, -0.005, 0.015, 0.01, -0.01, 0.02, 0.005]
        result = PerformanceCalculator.calculate_sharpe_ratio(returns)
        assert isinstance(result, float)
        assert result > 0  # Positive returns should give positive Sharpe

    def test_sharpe_ratio_insufficient_data(self):
        assert PerformanceCalculator.calculate_sharpe_ratio([0.01]) == 0.0
        assert PerformanceCalculator.calculate_sharpe_ratio([]) == 0.0

    def test_sharpe_ratio_zero_std(self):
        assert PerformanceCalculator.calculate_sharpe_ratio([0.01, 0.01, 0.01]) == 0.0

    def test_sortino_ratio_basic(self):
        returns = [0.01, 0.02, -0.005, 0.015, -0.01]
        result = PerformanceCalculator.calculate_sortino_ratio(returns)
        assert isinstance(result, float)

    def test_sortino_ratio_no_downside(self):
        returns = [0.01, 0.02, 0.03]
        result = PerformanceCalculator.calculate_sortino_ratio(returns)
        assert result == float("inf")

    def test_sortino_ratio_insufficient_data(self):
        assert PerformanceCalculator.calculate_sortino_ratio([]) == 0.0

    def test_max_drawdown_basic(self):
        equity = [100, 110, 105, 115, 100, 120]
        result = PerformanceCalculator.calculate_max_drawdown(equity)
        # Max drawdown: 115 -> 100 = 13.04%
        expected = (115 - 100) / 115 * 100
        assert abs(result - expected) < 0.01

    def test_max_drawdown_no_drawdown(self):
        equity = [100, 110, 120, 130]
        assert PerformanceCalculator.calculate_max_drawdown(equity) == 0.0

    def test_max_drawdown_insufficient(self):
        assert PerformanceCalculator.calculate_max_drawdown([100]) == 0.0

    def test_drawdown_series(self):
        equity = [100, 110, 105]
        series = PerformanceCalculator.calculate_drawdown_series(equity)
        assert len(series) == 3
        assert series[0] == 0.0
        assert series[1] == 0.0  # New peak
        assert series[2] < 0  # Drawdown from 110

    def test_compute_from_trades(self):
        trades = [
            {"side": "sell", "pnl": 100, "price": 50000, "quantity": 1},
            {"side": "sell", "pnl": -50, "price": 49000, "quantity": 1},
            {"side": "buy", "pnl": 0, "price": 48000, "quantity": 1},
        ]
        snapshots = [{"total_value": 100000}, {"total_value": 100050}]
        metrics = PerformanceCalculator.compute_from_trades(
            trades=trades, portfolio_snapshots=snapshots,
            initial_capital=100000, current_value=100050,
        )
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.gross_profit == 100
        assert metrics.gross_loss == 50
        assert metrics.win_rate == 0.5
        assert metrics.profit_factor == 2.0
        assert metrics.total_return_pct == pytest.approx(0.05)

    def test_compute_from_empty_trades(self):
        metrics = PerformanceCalculator.compute_from_trades([], [], 100000, 100000)
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0


# ==================== OHLCV History Tests ====================

from tradingbot.data.history import OHLCVHistory, Candle
from tradingbot.core.events import MarketDataEvent


class TestOHLCVHistory:
    @pytest.fixture
    def history(self):
        return OHLCVHistory(max_candles=10)

    @pytest.mark.asyncio
    async def test_on_market_data(self, history):
        event = MarketDataEvent(
            source="test", symbol="BTC/USDT",
            open=100, high=110, low=95, close=105, volume=1000,
        )
        await history.on_market_data(event)
        candles = history.get_candles("BTC/USDT")
        assert len(candles) == 1
        assert candles[0].close == 105

    @pytest.mark.asyncio
    async def test_multiple_symbols(self, history):
        for sym in ["BTC/USDT", "ETH/USDT"]:
            event = MarketDataEvent(source="test", symbol=sym, open=1, high=2, low=0.5, close=1.5, volume=100)
            await history.on_market_data(event)
        assert len(history.get_all_symbols()) == 2

    @pytest.mark.asyncio
    async def test_max_candles(self, history):
        for i in range(15):
            event = MarketDataEvent(source="test", symbol="BTC/USDT", open=i, high=i+1, low=i-1, close=i+0.5, volume=100)
            await history.on_market_data(event)
        assert len(history.get_candles("BTC/USDT")) == 10

    @pytest.mark.asyncio
    async def test_latest_prices(self, history):
        event = MarketDataEvent(source="test", symbol="BTC/USDT", open=100, high=110, low=95, close=105, volume=1000)
        await history.on_market_data(event)
        assert history.latest_prices["BTC/USDT"] == 105

    def test_get_candles_empty(self, history):
        assert history.get_candles("NONEXISTENT") == []

    def test_get_candles_dict(self, history):
        result = history.get_candles_dict("BTC/USDT")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ignores_non_market_data(self, history):
        from tradingbot.core.events import AlertEvent
        event = AlertEvent(source="test", title="test", message="test")
        await history.on_market_data(event)
        assert len(history.get_all_symbols()) == 0

    def test_clear(self, history):
        history._latest_prices["BTC"] = 100
        history.clear()
        assert len(history.latest_prices) == 0

    def test_candle_to_dict(self):
        c = Candle(time=123, open=1, high=2, low=0.5, close=1.5, volume=100)
        d = c.to_dict()
        assert d["time"] == 123
        assert d["close"] == 1.5


# ==================== Strategy State Tests ====================

from tradingbot.strategy.builtin.sma_crossover import SMACrossoverStrategy
from tradingbot.strategy.builtin.rsi_strategy import RSIStrategy
from tradingbot.strategy.builtin.bollinger import BollingerBandStrategy


class TestStrategyState:
    def test_sma_state_warming_up(self):
        s = SMACrossoverStrategy(name="sma", params={"fast_period": 3, "slow_period": 5})
        state = s.get_state()
        assert state["name"] == "sma"
        assert state["warmed_up"] == False
        assert state["crossover"] == "warming_up"
        assert state["type"] == "Trend Following"

    def test_sma_state_after_warmup(self):
        s = SMACrossoverStrategy(name="sma", params={"fast_period": 3, "slow_period": 5})
        prices = [10, 11, 12, 13, 14]
        for p in prices:
            s.calculate_signal(MarketDataEvent(source="t", symbol="X", close=p, open=p, high=p, low=p))
        state = s.get_state()
        assert state["fast_sma"] is not None
        assert state["slow_sma"] is not None
        assert state["crossover"] in ("golden", "death")
        assert state["data_points"] == 5

    def test_rsi_state_warming_up(self):
        s = RSIStrategy(name="rsi", params={"period": 5})
        state = s.get_state()
        assert state["name"] == "rsi"
        assert state["rsi"] is None
        assert state["zone"] == "warming_up"
        assert state["type"] == "Mean Reversion"

    def test_rsi_state_after_warmup(self):
        s = RSIStrategy(name="rsi", params={"period": 5})
        prices = [50, 51, 52, 51, 50, 49]
        for p in prices:
            s.calculate_signal(MarketDataEvent(source="t", symbol="X", close=p, open=p, high=p, low=p))
        state = s.get_state()
        assert state["rsi"] is not None
        assert state["zone"] in ("oversold", "overbought", "neutral")

    def test_bollinger_state_warming_up(self):
        s = BollingerBandStrategy(name="bb", params={"period": 5})
        state = s.get_state()
        assert state["position"] == "warming_up"
        assert state["type"] == "Mean Reversion"

    def test_bollinger_state_after_warmup(self):
        s = BollingerBandStrategy(name="bb", params={"period": 5})
        prices = [100, 101, 102, 101, 100]
        for p in prices:
            s.calculate_signal(MarketDataEvent(source="t", symbol="X", close=p, open=p, high=p, low=p))
        state = s.get_state()
        assert state["upper_band"] is not None
        assert state["lower_band"] is not None
        assert state["position"] in ("within", "above_upper", "below_lower")
        assert state["data_points"] == 5


# ==================== Risk Manager State Tests ====================

from tradingbot.risk.manager import RiskManager
from tradingbot.config.schema import RiskConfig


class TestRiskManagerState:
    @pytest.fixture
    def rm(self):
        config = RiskConfig()
        event_bus = MagicMock()
        return RiskManager(config=config, event_bus=event_bus)

    def test_get_state(self, rm):
        state = rm.get_state()
        assert "daily_pnl" in state
        assert "max_daily_loss" in state
        assert "circuit_breaker_active" in state
        assert "kill_switch" in state
        assert state["approved_count"] == 0
        assert state["rejected_count"] == 0

    def test_kill_switch_on(self, rm):
        rm.set_kill_switch(True)
        state = rm.get_state()
        assert state["circuit_breaker_active"] == True
        assert state["kill_switch"] == True

    def test_kill_switch_off(self, rm):
        rm.set_kill_switch(True)
        rm.set_kill_switch(False)
        state = rm.get_state()
        assert state["circuit_breaker_active"] == False
        assert state["kill_switch"] == False


# ==================== Engine OHLCV Integration Tests ====================

from tradingbot.core.engine import Engine
from tradingbot.config.schema import TradingBotConfig


class TestEngineOHLCV:
    def test_engine_has_ohlcv_history(self):
        config = TradingBotConfig()
        engine = Engine(config=config)
        assert engine._ohlcv_history is not None

    @pytest.mark.asyncio
    async def test_engine_registers_ohlcv_listener(self):
        config = TradingBotConfig()
        engine = Engine(config=config)
        # Manually call setup to register handlers
        await engine._setup_event_handlers()
        # Check that market_data has subscribers (ohlcv + price updater)
        from tradingbot.core.events import EventType
        count = engine.event_bus.get_subscriber_count(EventType.MARKET_DATA)
        assert count >= 2  # ohlcv_history + _update_prices


# ==================== API Serialization Tests ====================

class TestEventSerialization:
    def test_serialize_datetime(self):
        from tradingbot.api.main import _serialize_for_json
        dt = datetime(2026, 1, 1, 12, 0, 0)
        result = _serialize_for_json(dt)
        assert "2026-01-01" in result

    def test_serialize_enum(self):
        from tradingbot.api.main import _serialize_for_json
        from tradingbot.core.events import EventType
        result = _serialize_for_json(EventType.MARKET_DATA)
        assert result == "market_data"

    def test_serialize_dict(self):
        from tradingbot.api.main import _serialize_for_json
        result = _serialize_for_json({"key": "value", "num": 42})
        assert result == {"key": "value", "num": 42}

    def test_serialize_nested(self):
        from tradingbot.api.main import _serialize_for_json
        from tradingbot.core.events import EventType
        data = {"type": EventType.SIGNAL, "values": [1, 2, 3]}
        result = _serialize_for_json(data)
        assert result["type"] == "signal"
        assert result["values"] == [1, 2, 3]

    def test_serialize_none(self):
        from tradingbot.api.main import _serialize_for_json
        assert _serialize_for_json(None) is None

    def test_serialize_primitives(self):
        from tradingbot.api.main import _serialize_for_json
        assert _serialize_for_json(42) == 42
        assert _serialize_for_json(3.14) == 3.14
        assert _serialize_for_json("hello") == "hello"
        assert _serialize_for_json(True) == True


# ==================== Performance Metrics Edge Cases ====================

class TestPerformanceEdgeCases:
    def test_profit_factor_no_losses(self):
        trades = [{"side": "sell", "pnl": 100}, {"side": "sell", "pnl": 50}]
        metrics = PerformanceCalculator.compute_from_trades(trades, [], 100000, 100150)
        assert metrics.profit_factor == float("inf")

    def test_best_worst_trade(self):
        trades = [
            {"side": "sell", "pnl": 200},
            {"side": "sell", "pnl": -100},
            {"side": "sell", "pnl": 50},
        ]
        metrics = PerformanceCalculator.compute_from_trades(trades, [], 100000, 100150)
        assert metrics.best_trade == 200
        assert metrics.worst_trade == -100

    def test_only_buy_trades(self):
        trades = [{"side": "buy", "pnl": 0}, {"side": "buy", "pnl": 0}]
        metrics = PerformanceCalculator.compute_from_trades(trades, [], 100000, 100000)
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
