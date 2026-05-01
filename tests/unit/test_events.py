"""Unit tests for core events."""

from __future__ import annotations

import pytest

from tradingbot.core.events import (
    AlertEvent,
    AlertLevel,
    ErrorEvent,
    EventType,
    FillEvent,
    HeartbeatEvent,
    MarketDataEvent,
    OrderEvent,
    OrderStatus,
    OrderType,
    PortfolioEvent,
    SignalEvent,
    SignalSide,
)


class TestEvents:
    """Tests for event dataclasses."""

    def test_market_data_event_creation(self):
        """Test MarketDataEvent creation with defaults."""
        event = MarketDataEvent(symbol="BTC/USDT", close=50000.0)
        assert event.event_type == EventType.MARKET_DATA
        assert event.symbol == "BTC/USDT"
        assert event.close == 50000.0
        assert event.event_id  # UUID generated
        assert event.timestamp  # Timestamp generated

    def test_market_data_event_immutable(self):
        """Test that events are immutable (frozen dataclass)."""
        event = MarketDataEvent(symbol="BTC/USDT")
        with pytest.raises(AttributeError):
            event.symbol = "ETH/USDT"  # type: ignore[misc]

    def test_signal_event(self):
        """Test SignalEvent creation."""
        event = SignalEvent(
            symbol="BTC/USDT",
            side=SignalSide.BUY,
            strength=0.9,
            strategy_name="test",
            reason="test reason",
        )
        assert event.event_type == EventType.SIGNAL
        assert event.side == SignalSide.BUY
        assert event.strength == 0.9

    def test_order_event(self):
        """Test OrderEvent creation."""
        event = OrderEvent(
            symbol="BTC/USDT",
            side=SignalSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=1.5,
            price=50000.0,
        )
        assert event.event_type == EventType.ORDER
        assert event.order_type == OrderType.LIMIT
        assert event.quantity == 1.5
        assert event.status == OrderStatus.PENDING

    def test_fill_event(self):
        """Test FillEvent creation."""
        event = FillEvent(
            symbol="BTC/USDT",
            side=SignalSide.BUY,
            quantity=0.5,
            fill_price=49999.0,
            commission=25.0,
        )
        assert event.event_type == EventType.FILL
        assert event.fill_price == 49999.0
        assert event.commission == 25.0

    def test_portfolio_event(self):
        """Test PortfolioEvent creation."""
        event = PortfolioEvent(
            total_value=100000.0,
            cash=50000.0,
            unrealized_pnl=500.0,
        )
        assert event.event_type == EventType.PORTFOLIO
        assert event.total_value == 100000.0

    def test_alert_event(self):
        """Test AlertEvent creation."""
        event = AlertEvent(
            level=AlertLevel.CRITICAL,
            title="Test Alert",
            message="Something happened",
        )
        assert event.event_type == EventType.ALERT
        assert event.level == AlertLevel.CRITICAL

    def test_error_event(self):
        """Test ErrorEvent creation."""
        event = ErrorEvent(
            error_type="api_error",
            message="Connection failed",
            component="data_feed",
        )
        assert event.event_type == EventType.ERROR
        assert event.error_type == "api_error"

    def test_heartbeat_event(self):
        """Test HeartbeatEvent creation."""
        event = HeartbeatEvent(
            component="engine",
            status="healthy",
        )
        assert event.event_type == EventType.HEARTBEAT
        assert event.status == "healthy"

    def test_event_unique_ids(self):
        """Test that each event gets a unique ID."""
        e1 = MarketDataEvent()
        e2 = MarketDataEvent()
        assert e1.event_id != e2.event_id

    def test_signal_side_values(self):
        """Test SignalSide enum values."""
        assert SignalSide.BUY.value == "buy"
        assert SignalSide.SELL.value == "sell"
        assert SignalSide.HOLD.value == "hold"

    def test_order_type_values(self):
        """Test OrderType enum values."""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.STOP.value == "stop"

    def test_order_status_values(self):
        """Test OrderStatus enum values."""
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.CANCELLED.value == "cancelled"

    def test_event_metadata_dict(self):
        """Test that metadata fields default to empty dicts."""
        event = MarketDataEvent()
        assert event.raw_data == {}

        signal = SignalEvent()
        assert signal.metadata == {}


