"""Unit tests for order manager, retry, paper broker, and portfolio tracker."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tradingbot.config.schema import ExecutionConfig
from tradingbot.core.event_bus import EventBus
from tradingbot.core.events import EventType, FillEvent, OrderEvent, OrderType, SignalSide
from tradingbot.execution.brokers.base import BrokerError
from tradingbot.execution.brokers.paper_broker import PaperBroker
from tradingbot.execution.order_manager import OrderManager
from tradingbot.execution.retry import RetryExhaustedError, retry_async
from tradingbot.portfolio.models import PortfolioSnapshot, Position, Trade
from tradingbot.portfolio.tracker import PortfolioTracker


class TestRetry:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        func = AsyncMock(return_value="ok")
        result = await retry_async(func, max_attempts=3, base_delay=0.01)
        assert result == "ok"
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        func = AsyncMock(side_effect=[ValueError("fail"), ValueError("fail"), "ok"])
        result = await retry_async(func, max_attempts=3, base_delay=0.01)
        assert result == "ok"
        assert func.call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted(self):
        func = AsyncMock(side_effect=ValueError("fail"))
        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry_async(func, max_attempts=2, base_delay=0.01)
        assert exc_info.value.attempts == 2

    @pytest.mark.asyncio
    async def test_non_retryable(self):
        func = AsyncMock(side_effect=TypeError("not retryable"))
        with pytest.raises(TypeError):
            await retry_async(func, max_attempts=3, base_delay=0.01,
                            retryable_exceptions=(ValueError,))


class TestPaperBroker:
    @pytest.mark.asyncio
    async def test_buy_order(self):
        broker = PaperBroker(initial_balance=100000, slippage=0, commission_rate=0)
        order = OrderEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                          order_type=OrderType.MARKET, quantity=1.0, price=50000.0)
        fill = await broker.place_order(order)
        assert fill.symbol == "BTC/USDT"
        assert fill.quantity == 1.0
        assert broker.balance < 100000
        assert "BTC/USDT" in broker.positions

    @pytest.mark.asyncio
    async def test_sell_order(self):
        broker = PaperBroker(initial_balance=100000, slippage=0, commission_rate=0)
        buy = OrderEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                        order_type=OrderType.MARKET, quantity=1.0, price=100.0)
        await broker.place_order(buy)
        sell = OrderEvent(symbol="BTC/USDT", side=SignalSide.SELL,
                         order_type=OrderType.MARKET, quantity=1.0, price=110.0)
        fill = await broker.place_order(sell)
        assert fill.side == SignalSide.SELL
        assert "BTC/USDT" not in broker.positions

    @pytest.mark.asyncio
    async def test_insufficient_balance(self):
        broker = PaperBroker(initial_balance=100, slippage=0)
        order = OrderEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                          order_type=OrderType.MARKET, quantity=1.0, price=50000.0)
        with pytest.raises(BrokerError, match="Insufficient"):
            await broker.place_order(order)

    @pytest.mark.asyncio
    async def test_zero_price_rejected(self):
        broker = PaperBroker()
        order = OrderEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                          order_type=OrderType.MARKET, quantity=1.0, price=0)
        with pytest.raises(BrokerError):
            await broker.place_order(order)

    @pytest.mark.asyncio
    async def test_account_info(self):
        broker = PaperBroker(initial_balance=50000)
        info = await broker.get_account_info()
        assert info["balance"] == 50000
        assert info["initial_balance"] == 50000

    @pytest.mark.asyncio
    async def test_cancel_returns_false(self):
        broker = PaperBroker()
        assert await broker.cancel_order("any") is False

    @pytest.mark.asyncio
    async def test_get_positions(self):
        broker = PaperBroker(initial_balance=100000, slippage=0, commission_rate=0)
        order = OrderEvent(symbol="ETH/USDT", side=SignalSide.BUY,
                          order_type=OrderType.MARKET, quantity=5.0, price=3000.0)
        await broker.place_order(order)
        pos = await broker.get_positions()
        assert "ETH/USDT" in pos


class TestOrderManager:
    @pytest.mark.asyncio
    async def test_successful_order(self):
        bus = EventBus()
        broker = PaperBroker(initial_balance=100000, slippage=0, commission_rate=0)
        config = ExecutionConfig(retry_attempts=1, retry_delay=0.01)
        om = OrderManager(config=config, broker=broker, event_bus=bus)

        fills = []
        async def capture(e): fills.append(e)
        bus.subscribe(EventType.FILL, capture)

        order = OrderEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                          order_type=OrderType.MARKET, quantity=0.1, price=50000.0)
        await om.on_order(order)
        assert om.filled_count == 1
        assert len(fills) == 1

    @pytest.mark.asyncio
    async def test_failed_order(self):
        bus = EventBus()
        mock_broker = AsyncMock()
        mock_broker.place_order = AsyncMock(side_effect=BrokerError("fail"))
        config = ExecutionConfig(retry_attempts=1, retry_delay=0.01)
        om = OrderManager(config=config, broker=mock_broker, event_bus=bus)

        order = OrderEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                          order_type=OrderType.MARKET, quantity=0.1, price=50000.0)
        await om.on_order(order)
        assert om.failed_count == 1

    @pytest.mark.asyncio
    async def test_skip_non_order(self):
        bus = EventBus()
        broker = PaperBroker()
        config = ExecutionConfig(retry_attempts=1, retry_delay=0.01)
        om = OrderManager(config=config, broker=broker, event_bus=bus)
        from tradingbot.core.events import MarketDataEvent
        await om.on_order(MarketDataEvent())
        assert om.filled_count == 0


class TestPortfolioTracker:
    @pytest.mark.asyncio
    async def test_buy_creates_position(self, sample_fill):
        pt = PortfolioTracker(initial_cash=100000)
        await pt.on_fill(sample_fill)
        assert "BTC/USDT" in pt.positions
        assert pt.cash < 100000
        assert len(pt.trades) == 1

    @pytest.mark.asyncio
    async def test_sell_closes_position(self):
        pt = PortfolioTracker(initial_cash=100000)
        buy = FillEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                       quantity=1.0, fill_price=100.0, commission=0)
        await pt.on_fill(buy)
        sell = FillEvent(symbol="BTC/USDT", side=SignalSide.SELL,
                        quantity=1.0, fill_price=110.0, commission=0)
        await pt.on_fill(sell)
        assert "BTC/USDT" not in pt.positions
        assert pt.realized_pnl == pytest.approx(10.0)

    @pytest.mark.asyncio
    async def test_total_value(self, sample_fill):
        pt = PortfolioTracker(initial_cash=100000)
        await pt.on_fill(sample_fill)
        assert pt.total_value > 0

    def test_snapshot(self):
        pt = PortfolioTracker(initial_cash=50000)
        snap = pt.get_snapshot()
        assert isinstance(snap, PortfolioSnapshot)
        assert snap.cash == 50000

    def test_update_price(self):
        pt = PortfolioTracker()
        from tradingbot.portfolio.models import Position
        pt._positions["BTC/USDT"] = Position(symbol="BTC/USDT", quantity=1, avg_entry_price=100, current_price=100)
        pt.update_price("BTC/USDT", 150)
        assert pt._positions["BTC/USDT"].current_price == 150

    @pytest.mark.asyncio
    async def test_skip_non_fill(self):
        pt = PortfolioTracker()
        from tradingbot.core.events import MarketDataEvent
        await pt.on_fill(MarketDataEvent())
        assert len(pt.trades) == 0

    @pytest.mark.asyncio
    async def test_average_into_position(self):
        pt = PortfolioTracker(initial_cash=100000)
        f1 = FillEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                      quantity=1.0, fill_price=100.0, commission=0)
        f2 = FillEvent(symbol="BTC/USDT", side=SignalSide.BUY,
                      quantity=1.0, fill_price=200.0, commission=0)
        await pt.on_fill(f1)
        await pt.on_fill(f2)
        pos = pt.positions["BTC/USDT"]
        assert pos.quantity == 2.0
        assert pos.avg_entry_price == pytest.approx(150.0)


class TestPositionModel:
    def test_market_value(self):
        p = Position(symbol="X", quantity=10, avg_entry_price=100, current_price=110)
        assert p.market_value == 1100

    def test_unrealized_pnl(self):
        p = Position(symbol="X", quantity=10, avg_entry_price=100, current_price=110)
        assert p.unrealized_pnl == 100

    def test_pnl_pct(self):
        p = Position(symbol="X", quantity=10, avg_entry_price=100, current_price=110)
        assert p.unrealized_pnl_pct == pytest.approx(10.0)

    def test_is_long(self):
        assert Position(symbol="X", quantity=1).is_long
        assert not Position(symbol="X", quantity=-1).is_long

    def test_zero_cost_basis_pct(self):
        p = Position(symbol="X", quantity=0, avg_entry_price=0)
        assert p.unrealized_pnl_pct == 0.0


class TestTradeModel:
    def test_buy_net_value(self):
        t = Trade(symbol="X", side="buy", quantity=10, price=100, commission=5)
        assert t.net_value == -1005

    def test_sell_net_value(self):
        t = Trade(symbol="X", side="sell", quantity=10, price=100, commission=5)
        assert t.net_value == 995
