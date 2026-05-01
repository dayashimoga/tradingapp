"""Unit tests for trading strategies."""

from __future__ import annotations
import pytest
from tests.conftest import make_market_data
from tradingbot.core.events import SignalSide
from tradingbot.strategy.builtin.sma_crossover import SMACrossoverStrategy
from tradingbot.strategy.builtin.rsi_strategy import RSIStrategy
from tradingbot.strategy.builtin.bollinger import BollingerBandStrategy
from tradingbot.strategy.registry import register_strategy, get_strategy, list_strategies, clear_registry


class TestSMACrossover:
    def _make(self, fast=3, slow=5):
        return SMACrossoverStrategy(params={"fast_period": fast, "slow_period": slow})

    def test_warmup(self):
        s = self._make()
        for i in range(4):
            s.calculate_signal(make_market_data(100.0))
        assert not s.is_warmed_up

    def test_golden_cross(self):
        s = self._make(fast=3, slow=5)
        # Feed declining then rising prices to create crossover
        prices = [100, 99, 98, 97, 96, 97, 98, 99, 100, 101, 102, 103]
        signals = [s.calculate_signal(make_market_data(p)) for p in prices]
        buy_signals = [sig for sig in signals if sig and sig.side == SignalSide.BUY]
        assert len(buy_signals) >= 1

    def test_death_cross(self):
        s = self._make(fast=3, slow=5)
        prices = [96, 97, 98, 99, 100, 99, 98, 97, 96, 95, 94, 93]
        signals = [s.calculate_signal(make_market_data(p)) for p in prices]
        sell_signals = [sig for sig in signals if sig and sig.side == SignalSide.SELL]
        assert len(sell_signals) >= 1

    def test_no_signal_flat(self):
        s = self._make(fast=3, slow=5)
        for _ in range(20):
            sig = s.calculate_signal(make_market_data(100.0))
        # Flat prices = no crossover after warmup baseline
        # After warmup there should be no cross signals
        assert sig is None

    def test_reset(self):
        s = self._make()
        s.calculate_signal(make_market_data(100.0))
        s.reset()
        assert not s.is_warmed_up

    def test_properties(self):
        s = self._make(fast=5, slow=20)
        assert s.fast_period == 5
        assert s.slow_period == 20


class TestRSI:
    def _make(self, period=5, ob=70, os_=30):
        return RSIStrategy(params={"period": period, "overbought": ob, "oversold": os_})

    def test_warmup(self):
        s = self._make(period=5)
        for i in range(4):
            s.calculate_signal(make_market_data(100.0))
        assert not s.is_warmed_up

    def test_oversold_buy(self):
        s = self._make(period=5)
        # Declining prices → low RSI → BUY
        prices = [100, 99, 98, 97, 96, 95, 94]
        signals = [s.calculate_signal(make_market_data(p)) for p in prices]
        buy_sigs = [sig for sig in signals if sig and sig.side == SignalSide.BUY]
        assert len(buy_sigs) >= 1

    def test_overbought_sell(self):
        s = self._make(period=5)
        prices = [94, 95, 96, 97, 98, 99, 100]
        signals = [s.calculate_signal(make_market_data(p)) for p in prices]
        sell_sigs = [sig for sig in signals if sig and sig.side == SignalSide.SELL]
        assert len(sell_sigs) >= 1

    def test_reset(self):
        s = self._make()
        s.calculate_signal(make_market_data(100.0))
        s.reset()
        assert not s.is_warmed_up

    def test_properties(self):
        s = self._make(period=10, ob=80, os_=20)
        assert s.period == 10
        assert s.overbought == 80
        assert s.oversold == 20


class TestBollinger:
    def _make(self, period=5, std=2.0):
        return BollingerBandStrategy(params={"period": period, "num_std": std})

    def test_warmup(self):
        s = self._make(period=5)
        for i in range(3):
            s.calculate_signal(make_market_data(100.0))
        assert not s.is_warmed_up

    def test_lower_band_buy(self):
        s = self._make(period=5, std=1.0)
        # Normal prices, then a sharp drop
        prices = [100, 100, 100, 100, 100, 90]
        signals = [s.calculate_signal(make_market_data(p)) for p in prices]
        buy_sigs = [sig for sig in signals if sig and sig.side == SignalSide.BUY]
        assert len(buy_sigs) >= 1

    def test_upper_band_sell(self):
        s = self._make(period=5, std=1.0)
        prices = [100, 100, 100, 100, 100, 110]
        signals = [s.calculate_signal(make_market_data(p)) for p in prices]
        sell_sigs = [sig for sig in signals if sig and sig.side == SignalSide.SELL]
        assert len(sell_sigs) >= 1

    def test_no_signal_within_bands(self):
        s = self._make(period=5, std=2.0)
        # Use slightly varying prices that stay within bands
        prices = [100, 101, 99, 100.5, 99.5, 100, 100.2, 99.8, 100.1, 99.9]
        sig = None
        for p in prices:
            sig = s.calculate_signal(make_market_data(p))
        assert sig is None

    def test_reset(self):
        s = self._make()
        s.calculate_signal(make_market_data(100.0))
        s.reset()
        assert not s.is_warmed_up

    def test_properties(self):
        s = self._make(period=20, std=2.5)
        assert s.period == 20
        assert s.num_std == 2.5


class TestRegistry:
    def setup_method(self):
        clear_registry()
        # Re-import to re-register built-in strategies
        import importlib
        import tradingbot.strategy.builtin.sma_crossover
        import tradingbot.strategy.builtin.rsi_strategy
        import tradingbot.strategy.builtin.bollinger
        importlib.reload(tradingbot.strategy.builtin.sma_crossover)
        importlib.reload(tradingbot.strategy.builtin.rsi_strategy)
        importlib.reload(tradingbot.strategy.builtin.bollinger)

    def test_list_strategies(self):
        names = list_strategies()
        assert "sma_crossover" in names
        assert "rsi" in names
        assert "bollinger" in names

    def test_get_strategy(self):
        s = get_strategy("sma_crossover", params={"fast_period": 5})
        assert s.name == "sma_crossover"

    def test_unknown_strategy(self):
        with pytest.raises(KeyError):
            get_strategy("nonexistent")
