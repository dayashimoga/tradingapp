"""Shared test fixtures for the entire test suite."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tradingbot.config.schema import (
    ExecutionConfig,
    RiskConfig,
    TradingBotConfig,
)
from tradingbot.core.event_bus import EventBus
from tradingbot.core.events import (
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    OrderType,
    SignalEvent,
    SignalSide,
)


@pytest.fixture
def event_bus():
    """Fresh event bus for each test."""
    return EventBus()


@pytest.fixture
def sample_config():
    """Default test configuration."""
    return TradingBotConfig()


@pytest.fixture
def risk_config():
    """Default risk configuration."""
    return RiskConfig(
        max_daily_loss=500.0,
        max_position_size=0.05,
        max_total_exposure=0.30,
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        max_open_positions=5,
    )


@pytest.fixture
def execution_config():
    """Default execution configuration."""
    return ExecutionConfig(
        retry_attempts=3,
        retry_delay=0.01,  # Fast retries for testing
        order_timeout=5,
    )


@pytest.fixture
def sample_market_data():
    """Sample market data event."""
    return MarketDataEvent(
        source="test",
        symbol="BTC/USDT",
        open=50000.0,
        high=50500.0,
        low=49500.0,
        close=50200.0,
        volume=1000.0,
        timeframe="1m",
        exchange="binance",
    )


@pytest.fixture
def sample_signal():
    """Sample buy signal event."""
    return SignalEvent(
        source="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        strength=0.8,
        strategy_name="test_strategy",
        reason="Test signal",
        suggested_price=50200.0,
    )


@pytest.fixture
def sample_sell_signal():
    """Sample sell signal event."""
    return SignalEvent(
        source="test_strategy",
        symbol="BTC/USDT",
        side=SignalSide.SELL,
        strength=0.7,
        strategy_name="test_strategy",
        reason="Test sell signal",
        suggested_price=51000.0,
    )


@pytest.fixture
def sample_order():
    """Sample order event."""
    return OrderEvent(
        source="risk_manager",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1,
        price=50200.0,
    )


@pytest.fixture
def sample_fill():
    """Sample fill event."""
    return FillEvent(
        source="paper_broker",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        quantity=0.1,
        fill_price=50210.0,
        commission=5.02,
        order_id="test-order-1",
        broker_order_id="broker-123",
    )


def make_market_data(close: float, symbol: str = "BTC/USDT") -> MarketDataEvent:
    """Helper to create market data with a specific close price."""
    return MarketDataEvent(
        source="test",
        symbol=symbol,
        open=close * 0.999,
        high=close * 1.001,
        low=close * 0.998,
        close=close,
        volume=100.0,
        timeframe="1m",
        exchange="test",
    )
