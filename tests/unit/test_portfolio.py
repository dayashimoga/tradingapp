"""Unit tests for Portfolio Tracker."""

import pytest
from tradingbot.core.events import FillEvent, SignalSide
from tradingbot.portfolio.tracker import PortfolioTracker

@pytest.mark.asyncio
async def test_portfolio_tracker_pnl_calculation():
    """Test that PortfolioTracker correctly calculates realized PNL and assigns it to Trade."""
    tracker = PortfolioTracker(initial_cash=10000.0)
    
    # 1. Buy 2 BTC at $50,000
    buy_fill = FillEvent(
        source="broker",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        quantity=2.0,
        fill_price=50000.0,
        commission=10.0,
        strategy_name="TestStrat",
        reason="Test buy",
    )
    await tracker.on_fill(buy_fill)
    
    assert "BTC/USDT" in tracker.positions
    assert tracker.positions["BTC/USDT"].quantity == 2.0
    assert tracker.positions["BTC/USDT"].avg_entry_price == 50000.0
    
    # 2. Sell 1 BTC at $60,000
    sell_fill = FillEvent(
        source="broker",
        symbol="BTC/USDT",
        side=SignalSide.SELL,
        quantity=1.0,
        fill_price=60000.0,
        commission=10.0,
        strategy_name="TestStrat",
        reason="Test sell",
    )
    await tracker.on_fill(sell_fill)
    
    # Verify PNL is calculated correctly: (60000 - 50000) * 1 - 10 = 9990.0
    assert tracker.realized_pnl == 9990.0
    
    # Check that the trade has the PNL and reasoning attached
    trades = tracker.trades
    assert len(trades) == 2
    assert trades[1].side == "sell"
    assert trades[1].realized_pnl == 9990.0
    assert trades[1].reason == "Test sell"
    assert trades[1].strategy_name == "TestStrat"

@pytest.mark.asyncio
async def test_portfolio_sell_no_position():
    """Test selling when the position doesn't exist."""
    tracker = PortfolioTracker(initial_cash=10000.0)
    
    sell_fill = FillEvent(
        source="broker",
        symbol="ETH/USDT",
        side=SignalSide.SELL,
        quantity=1.0,
        fill_price=3000.0,
        commission=5.0,
    )
    await tracker.on_fill(sell_fill)
    
    # Should just add to cash but not fail
    assert tracker.cash == 10000.0 + (3000.0 * 1.0) - 5.0

@pytest.mark.asyncio
async def test_portfolio_properties():
    """Test properties and unrealized pnl."""
    tracker = PortfolioTracker(initial_cash=10000.0)
    
    # Add position
    await tracker.on_fill(FillEvent(
        source="broker",
        symbol="ADA/USDT",
        side=SignalSide.BUY,
        quantity=100.0,
        fill_price=1.0,
        commission=1.0,
    ))
    
    # Update current price
    tracker.positions["ADA/USDT"].current_price = 1.5
    
    assert tracker.unrealized_pnl == 50.0 # (1.5 - 1.0) * 100
    assert tracker.total_value == (10000.0 - 101.0) + 150.0
