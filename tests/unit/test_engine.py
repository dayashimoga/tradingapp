"""Unit tests for the core engine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.conftest import make_market_data
from tradingbot.config.schema import TradingBotConfig
from tradingbot.core.engine import Engine
from tradingbot.core.event_bus import EventBus
from tradingbot.core.events import EventType


class TestEngine:
    def test_creation(self):
        config = TradingBotConfig()
        engine = Engine(config=config)
        assert not engine.is_running
        assert engine.event_bus is not None

    def test_custom_event_bus(self):
        bus = EventBus()
        engine = Engine(config=TradingBotConfig(), event_bus=bus)
        assert engine.event_bus is bus

    def test_register_strategy(self):
        from tradingbot.strategy.builtin.sma_crossover import SMACrossoverStrategy
        engine = Engine(config=TradingBotConfig())
        s = SMACrossoverStrategy(params={"fast_period": 3, "slow_period": 5})
        engine.register_strategy(s)
        assert len(engine._strategies) == 1

    def test_register_risk_manager(self):
        from tradingbot.config.schema import RiskConfig
        from tradingbot.risk.manager import RiskManager
        engine = Engine(config=TradingBotConfig())
        rm = RiskManager(config=RiskConfig(), event_bus=engine.event_bus)
        engine.register_risk_manager(rm)
        assert engine._risk_manager is rm

    def test_register_order_manager(self):
        from tradingbot.config.schema import ExecutionConfig
        from tradingbot.execution.brokers.paper_broker import PaperBroker
        from tradingbot.execution.order_manager import OrderManager
        engine = Engine(config=TradingBotConfig())
        om = OrderManager(
            config=ExecutionConfig(), broker=PaperBroker(), event_bus=engine.event_bus
        )
        engine.register_order_manager(om)
        assert engine._order_manager is om

    def test_register_portfolio_tracker(self):
        from tradingbot.portfolio.tracker import PortfolioTracker
        engine = Engine(config=TradingBotConfig())
        pt = PortfolioTracker()
        engine.register_portfolio_tracker(pt)
        assert engine._portfolio_tracker is pt

    def test_register_data_feed(self):
        engine = Engine(config=TradingBotConfig())
        mock_feed = MagicMock()
        engine.register_data_feed(mock_feed)
        assert len(engine._data_feeds) == 1

    @pytest.mark.asyncio
    async def test_run_once(self):
        bus = EventBus()
        engine = Engine(config=TradingBotConfig(), event_bus=bus)
        received = []
        async def handler(e): received.append(e)
        bus.subscribe(EventType.MARKET_DATA, handler)
        await engine.run_once(make_market_data(100.0))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_setup_event_handlers(self):
        from tradingbot.config.schema import RiskConfig
        from tradingbot.risk.manager import RiskManager
        from tradingbot.strategy.builtin.sma_crossover import SMACrossoverStrategy
        engine = Engine(config=TradingBotConfig())
        s = SMACrossoverStrategy(params={"fast_period": 3, "slow_period": 5})
        engine.register_strategy(s)
        rm = RiskManager(config=RiskConfig(), event_bus=engine.event_bus)
        engine.register_risk_manager(rm)
        await engine._setup_event_handlers()
        assert engine.event_bus.get_subscriber_count(EventType.MARKET_DATA) >= 1
        assert engine.event_bus.get_subscriber_count(EventType.SIGNAL) >= 1

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        engine = Engine(config=TradingBotConfig())
        await engine.stop()  # Should not raise
        assert not engine.is_running

    @pytest.mark.asyncio
    async def test_stop_when_running(self):
        engine = Engine(config=TradingBotConfig())
        engine._running = True
        engine.event_bus.start()
        await engine.stop()
        assert not engine.is_running
        assert not engine.event_bus.is_running
