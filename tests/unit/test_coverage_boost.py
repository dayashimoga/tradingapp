"""Additional tests to boost coverage above 90%."""

import pytest
from tradingbot.portfolio.tracker import PortfolioTracker
from tradingbot.portfolio.models import PortfolioSnapshot
from tradingbot.core.events import FillEvent, SignalSide
from tradingbot.risk.manager import RiskManager
from tradingbot.risk.circuit_breaker import CircuitBreaker
from tradingbot.risk.limits import TradingLimits


class TestPortfolioSnapshotAndTotalPnl:
    """Tests for portfolio snapshot and total_pnl property."""

    @pytest.mark.asyncio
    async def test_total_pnl(self):
        """Test total_pnl combines realized + unrealized."""
        tracker = PortfolioTracker(initial_cash=10000.0)
        # Buy
        await tracker.on_fill(FillEvent(
            source="test", symbol="X", side=SignalSide.BUY,
            quantity=10.0, fill_price=100.0, commission=0.0,
        ))
        # Sell at profit
        await tracker.on_fill(FillEvent(
            source="test", symbol="X", side=SignalSide.SELL,
            quantity=5.0, fill_price=120.0, commission=0.0,
        ))
        # Now we have realized PNL + unrealized PNL from remaining 5 shares
        assert tracker.realized_pnl == 100.0  # (120 - 100) * 5
        assert tracker.total_pnl == tracker.realized_pnl + tracker.unrealized_pnl

    @pytest.mark.asyncio
    async def test_get_snapshot(self):
        """Test get_snapshot returns a valid PortfolioSnapshot."""
        tracker = PortfolioTracker(initial_cash=5000.0)
        await tracker.on_fill(FillEvent(
            source="test", symbol="Z", side=SignalSide.BUY,
            quantity=2.0, fill_price=100.0, commission=1.0,
        ))
        snap = tracker.get_snapshot()
        assert isinstance(snap, PortfolioSnapshot)
        assert snap.cash == 5000.0 - 201.0
        assert snap.num_positions == 1
        assert snap.num_trades == 1


class TestCircuitBreakerExtended:
    """Cover circuit breaker reset and cooldown paths."""

    def test_circuit_breaker_reset(self):
        breaker = CircuitBreaker(volatility_threshold=0.1, cooldown_minutes=5, window_size=3)
        # Feed data using the correct API
        for i in range(5):
            breaker.check_price(100.0 + i * 0.01)
        breaker.reset()
        assert breaker.is_tripped is False

    def test_circuit_breaker_needs_data(self):
        breaker = CircuitBreaker(volatility_threshold=0.1, cooldown_minutes=5, window_size=10)
        # Not enough data yet
        result = breaker.check_price(100.0)
        assert result is False
        assert breaker.is_tripped is False


class TestTradingLimitsExtended:
    """Cover TradingLimits edge cases."""

    def test_daily_trades_limit(self):
        limits = TradingLimits(
            max_daily_loss=500.0,
            max_daily_trades=3,
            max_consecutive_losses=5,
            max_drawdown_pct=10.0,
        )
        for _ in range(3):
            limits.record_trade(pnl=10.0)
        violations = limits.check_all()
        assert any("Daily trade" in v for v in violations)

    def test_drawdown_check(self):
        limits = TradingLimits(
            max_daily_loss=500.0,
            max_daily_trades=100,
            max_consecutive_losses=10,
            max_drawdown_pct=0.05,  # 5% as a fraction
        )
        limits.update_peak(10000.0)
        # check_all takes current_value as a parameter
        violations = limits.check_all(current_value=9000.0)
        assert any("drawdown" in v.lower() for v in violations)

    def test_consecutive_losses(self):
        limits = TradingLimits(
            max_daily_loss=10000.0,
            max_daily_trades=100,
            max_consecutive_losses=2,
            max_drawdown_pct=50.0,
        )
        limits.record_trade(pnl=-10.0)
        limits.record_trade(pnl=-10.0)
        violations = limits.check_all()
        assert any("Consecutive" in v for v in violations)


class TestRiskManagerDailyPnl:
    """Cover daily PNL tracking."""

    def test_update_daily_pnl(self):
        from tradingbot.config.schema import RiskConfig
        config = RiskConfig()
        rm = RiskManager(config=config, event_bus=None, portfolio_value=10000.0)
        rm.update_daily_pnl(50.0)
        assert rm.daily_pnl == 50.0
        rm.update_daily_pnl(-20.0)
        assert rm.daily_pnl == 30.0

    def test_circuit_breaker_activation(self):
        from tradingbot.config.schema import RiskConfig
        config = RiskConfig()
        rm = RiskManager(config=config, event_bus=None, portfolio_value=10000.0)
        rm.activate_circuit_breaker(cooldown_minutes=1)
        assert rm.is_circuit_breaker_active is True

    def test_position_tracking(self):
        from tradingbot.config.schema import RiskConfig
        config = RiskConfig()
        rm = RiskManager(config=config, event_bus=None, portfolio_value=10000.0)
        rm.update_position("BTC", 5.0)
        assert rm._open_positions["BTC"] == 5.0
        rm.update_position("BTC", 0.0)
        assert "BTC" not in rm._open_positions
