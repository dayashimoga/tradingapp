"""Unit tests for risk manager, circuit breaker, position sizer, and limits."""

from __future__ import annotations

import pytest

from tradingbot.config.schema import RiskConfig
from tradingbot.core.event_bus import EventBus
from tradingbot.core.events import EventType, SignalEvent, SignalSide
from tradingbot.risk.circuit_breaker import CircuitBreaker
from tradingbot.risk.limits import TradingLimits
from tradingbot.risk.manager import RiskManager
from tradingbot.risk.position_sizer import PositionSizer


class TestRiskManager:
    def _make(self, **kwargs):
        config = RiskConfig(**kwargs)
        bus = EventBus()
        return RiskManager(config=config, event_bus=bus, portfolio_value=100000.0), bus

    @pytest.mark.asyncio
    async def test_approve_valid_signal(self):
        rm, bus = self._make()
        orders = []
        async def capture(e): orders.append(e)
        bus.subscribe(EventType.ORDER, capture)

        signal = SignalEvent(symbol="BTC/USDT", side=SignalSide.BUY, strength=0.8,
                           strategy_name="test", suggested_price=50000.0)
        await rm.on_signal(signal)
        assert rm.approved_count == 1
        assert len(orders) == 1

    @pytest.mark.asyncio
    async def test_reject_hold_signal(self):
        rm, _bus = self._make()
        signal = SignalEvent(symbol="BTC/USDT", side=SignalSide.HOLD)
        await rm.on_signal(signal)
        assert rm.approved_count == 0
        assert rm.rejected_count == 0

    @pytest.mark.asyncio
    async def test_reject_daily_loss_exceeded(self):
        rm, _bus = self._make(max_daily_loss=100.0)
        rm.update_daily_pnl(-150.0)
        signal = SignalEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                           suggested_price=100.0)
        await rm.on_signal(signal)
        assert rm.rejected_count == 1

    @pytest.mark.asyncio
    async def test_reject_max_positions(self):
        rm, _bus = self._make(max_open_positions=1)
        rm.update_position("ETH/USDT", 1.0)
        signal = SignalEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                           suggested_price=100.0)
        await rm.on_signal(signal)
        assert rm.rejected_count == 1

    @pytest.mark.asyncio
    async def test_reject_circuit_breaker(self):
        rm, _bus = self._make()
        rm.activate_circuit_breaker(cooldown_minutes=60)
        signal = SignalEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                           suggested_price=100.0)
        await rm.on_signal(signal)
        assert rm.rejected_count == 1

    def test_position_size_calculation(self):
        rm, _ = self._make(max_position_size=0.05)
        signal = SignalEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                           suggested_price=50000.0)
        qty = rm._calculate_position_size(signal)
        assert qty == pytest.approx(0.1, rel=0.01)  # 5000/50000

    def test_update_portfolio_value(self):
        rm, _ = self._make()
        rm.update_portfolio_value(200000.0)
        assert rm._portfolio_value == 200000.0

    @pytest.mark.asyncio
    async def test_skip_non_signal(self):
        rm, _ = self._make()
        from tradingbot.core.events import MarketDataEvent
        await rm.on_signal(MarketDataEvent())
        assert rm.approved_count == 0


class TestCircuitBreaker:
    def test_not_tripped_initially(self):
        cb = CircuitBreaker()
        assert not cb.is_tripped
        assert cb.trip_count == 0

    def test_needs_data(self):
        cb = CircuitBreaker()
        assert not cb.check_price(100.0)
        assert not cb.check_price(101.0)

    def test_trips_on_spike(self):
        cb = CircuitBreaker(volatility_threshold=2.0, window_size=10)
        # Build normal data
        for p in [100, 100.1, 99.9, 100.2, 99.8, 100.1, 99.9, 100]:
            cb.check_price(p)
        # Spike
        result = cb.check_price(120.0)
        assert result is True
        assert cb.is_tripped
        assert cb.trip_count == 1

    def test_cooldown(self):
        cb = CircuitBreaker(cooldown_minutes=0)  # instant cooldown
        for p in [100, 100.1, 99.9, 100.2, 99.8, 100.1, 99.9, 100]:
            cb.check_price(p)
        cb.check_price(120.0)
        # After 0-minute cooldown, should reset
        assert not cb.is_tripped or cb.cooldown_remaining == 0

    def test_reset(self):
        cb = CircuitBreaker()
        cb._tripped = True
        cb.reset()
        assert not cb.is_tripped


class TestPositionSizer:
    def test_fixed_fraction(self):
        qty = PositionSizer.fixed_fraction(100000, 0.05, 50000)
        assert qty == pytest.approx(0.1)

    def test_fixed_fraction_zero_price(self):
        assert PositionSizer.fixed_fraction(100000, 0.05, 0) == 0.0

    def test_fixed_fraction_invalid_fraction(self):
        assert PositionSizer.fixed_fraction(100000, -0.1, 100) == 0.0
        assert PositionSizer.fixed_fraction(100000, 1.5, 100) == 0.0

    def test_kelly_criterion(self):
        qty = PositionSizer.kelly_criterion(0.6, 100, 80, 100000, 1000)
        assert qty > 0

    def test_kelly_zero_loss(self):
        assert PositionSizer.kelly_criterion(0.6, 100, 0, 100000, 1000) == 0.0

    def test_kelly_invalid_win_rate(self):
        assert PositionSizer.kelly_criterion(0, 100, 80, 100000, 1000) == 0.0
        assert PositionSizer.kelly_criterion(1.0, 100, 80, 100000, 1000) == 0.0

    def test_fixed_amount(self):
        assert PositionSizer.fixed_amount(5000, 100) == 50.0
        assert PositionSizer.fixed_amount(0, 100) == 0.0

    def test_risk_based(self):
        qty = PositionSizer.risk_based(100000, 0.01, 100, 95)
        assert qty == pytest.approx(200.0)

    def test_risk_based_zero(self):
        assert PositionSizer.risk_based(100000, 0.01, 100, 100) == 0.0


class TestTradingLimits:
    def test_daily_loss(self):
        tl = TradingLimits(max_daily_loss=100)
        tl.record_trade(-50)
        assert not tl.check_daily_loss()
        tl.record_trade(-60)
        assert tl.check_daily_loss()

    def test_daily_trades(self):
        tl = TradingLimits(max_daily_trades=2)
        tl.record_trade(10)
        tl.record_trade(10)
        assert tl.check_daily_trades()

    def test_consecutive_losses(self):
        tl = TradingLimits(max_consecutive_losses=3)
        tl.record_trade(-10)
        tl.record_trade(-10)
        assert not tl.check_consecutive_losses()
        tl.record_trade(-10)
        assert tl.check_consecutive_losses()

    def test_consecutive_reset_on_win(self):
        tl = TradingLimits(max_consecutive_losses=3)
        tl.record_trade(-10)
        tl.record_trade(-10)
        tl.record_trade(10)
        assert not tl.check_consecutive_losses()

    def test_drawdown(self):
        tl = TradingLimits(max_drawdown_pct=0.10)
        tl.update_peak(100000)
        assert not tl.check_drawdown(95000)
        assert tl.check_drawdown(89000)

    def test_check_all(self):
        tl = TradingLimits(max_daily_loss=10)
        tl.record_trade(-20)
        v = tl.check_all()
        assert len(v) >= 1
