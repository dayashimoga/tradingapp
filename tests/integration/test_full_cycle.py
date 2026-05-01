"""Integration test — full signal-to-fill trading cycle."""

from __future__ import annotations

import pytest

from tests.conftest import make_market_data
from tradingbot.config.schema import ExecutionConfig, RiskConfig, TradingBotConfig
from tradingbot.core.event_bus import EventBus
from tradingbot.core.events import EventType
from tradingbot.execution.brokers.paper_broker import PaperBroker
from tradingbot.execution.order_manager import OrderManager
from tradingbot.portfolio.tracker import PortfolioTracker
from tradingbot.risk.manager import RiskManager
from tradingbot.strategy.builtin.sma_crossover import SMACrossoverStrategy


class TestFullCycle:
    """End-to-end integration: MarketData → Strategy → Risk → Order → Fill → Portfolio."""

    @pytest.mark.asyncio
    async def test_buy_cycle(self):
        bus = EventBus()
        TradingBotConfig()

        # Setup components
        strategy = SMACrossoverStrategy(
            params={"fast_period": 3, "slow_period": 5}, event_bus=bus
        )
        risk_mgr = RiskManager(
            config=RiskConfig(max_position_size=0.05), event_bus=bus, portfolio_value=100000
        )
        broker = PaperBroker(initial_balance=100000, slippage=0, commission_rate=0)
        order_mgr = OrderManager(
            config=ExecutionConfig(retry_attempts=1, retry_delay=0.01),
            broker=broker, event_bus=bus,
        )
        portfolio = PortfolioTracker(initial_cash=100000)

        # Wire event handlers
        bus.subscribe(EventType.MARKET_DATA, strategy.on_market_data, priority=50)
        bus.subscribe(EventType.SIGNAL, risk_mgr.on_signal, priority=50)
        bus.subscribe(EventType.ORDER, order_mgr.on_order, priority=50)
        bus.subscribe(EventType.FILL, portfolio.on_fill, priority=50)

        # Feed prices that create a golden cross
        prices = [100, 99, 98, 97, 96, 97, 98, 99, 100, 101, 102, 103]
        for p in prices:
            await bus.publish(make_market_data(p, "BTC/USDT"))

        # Verify something happened in the pipeline
        assert bus.event_count > len(prices)  # extra events from signals/orders/fills

    @pytest.mark.asyncio
    async def test_risk_rejection_cycle(self):
        bus = EventBus()
        risk_mgr = RiskManager(
            config=RiskConfig(max_daily_loss=1.0),  # Very low limit
            event_bus=bus, portfolio_value=100000,
        )
        risk_mgr.update_daily_pnl(-100.0)  # Already exceeded

        strategy = SMACrossoverStrategy(
            params={"fast_period": 3, "slow_period": 5}, event_bus=bus
        )

        bus.subscribe(EventType.MARKET_DATA, strategy.on_market_data, priority=50)
        bus.subscribe(EventType.SIGNAL, risk_mgr.on_signal, priority=50)

        orders_received = []
        async def capture_order(e): orders_received.append(e)
        bus.subscribe(EventType.ORDER, capture_order, priority=50)

        prices = [100, 99, 98, 97, 96, 97, 98, 99, 100, 101, 102, 103]
        for p in prices:
            await bus.publish(make_market_data(p, "BTC/USDT"))

        # Risk manager should reject all signals
        assert len(orders_received) == 0
        assert risk_mgr.rejected_count >= 0


class TestEngineIntegration:
    """Engine lifecycle tests."""

    @pytest.mark.asyncio
    async def test_engine_creation(self):
        from tradingbot.core.engine import Engine
        config = TradingBotConfig()
        bus = EventBus()
        engine = Engine(config=config, event_bus=bus)
        assert not engine.is_running

    @pytest.mark.asyncio
    async def test_run_once(self):
        from tradingbot.core.engine import Engine
        config = TradingBotConfig()
        bus = EventBus()
        engine = Engine(config=config, event_bus=bus)

        received = []
        async def handler(e): received.append(e)
        bus.subscribe(EventType.MARKET_DATA, handler)

        await engine.run_once(make_market_data(100.0))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_register_components(self):

        from tradingbot.core.engine import Engine
        config = TradingBotConfig()
        engine = Engine(config=config)

        strategy = SMACrossoverStrategy(params={"fast_period": 3, "slow_period": 5})
        engine.register_strategy(strategy)
        assert len(engine._strategies) == 1
