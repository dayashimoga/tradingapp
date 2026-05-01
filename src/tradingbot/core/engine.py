"""Main engine orchestrator — wires all modules together and manages lifecycle."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from typing import TYPE_CHECKING

from tradingbot.core.event_bus import EventBus
from tradingbot.core.events import (
    AlertEvent,
    AlertLevel,
    Event,
    EventType,
    HeartbeatEvent,
    MarketDataEvent,
)
from tradingbot.data.history import OHLCVHistory

if TYPE_CHECKING:
    from tradingbot.config.schema import TradingBotConfig
    from tradingbot.data.base import DataFeed
    from tradingbot.execution.order_manager import OrderManager
    from tradingbot.portfolio.tracker import PortfolioTracker
    from tradingbot.risk.manager import RiskManager
    from tradingbot.strategy.base import Strategy

logger = logging.getLogger(__name__)


class Engine:
    """
    Main trading engine orchestrator.

    Manages the lifecycle of all components:
    init → warmup → run → shutdown

    Coordinates event flow:
    MarketData → Strategy → RiskManager → OrderManager → Portfolio
    """

    def __init__(
        self,
        config: TradingBotConfig,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config
        self.event_bus = event_bus or EventBus()
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Components (set via register methods)
        self._data_feeds: list[DataFeed] = []
        self._strategies: list[Strategy] = []
        self._risk_manager: RiskManager | None = None
        self._order_manager: OrderManager | None = None
        self._portfolio_tracker: PortfolioTracker | None = None

        # OHLCV history buffer for chart data
        self._ohlcv_history = OHLCVHistory()

        # Heartbeat
        self._heartbeat_task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        """Whether the engine is currently running."""
        return self._running

    def register_data_feed(self, feed: DataFeed) -> None:
        """Register a market data feed."""
        self._data_feeds.append(feed)
        logger.info("Registered data feed: %s", feed.__class__.__name__)

    def register_strategy(self, strategy: Strategy) -> None:
        """Register a trading strategy."""
        self._strategies.append(strategy)
        logger.info("Registered strategy: %s", strategy.name)

    def register_risk_manager(self, risk_manager: RiskManager) -> None:
        """Register the risk manager."""
        self._risk_manager = risk_manager
        logger.info("Registered risk manager")

    def register_order_manager(self, order_manager: OrderManager) -> None:
        """Register the order manager."""
        self._order_manager = order_manager
        logger.info("Registered order manager")

    def register_portfolio_tracker(self, portfolio_tracker: PortfolioTracker) -> None:
        """Register the portfolio tracker."""
        self._portfolio_tracker = portfolio_tracker
        logger.info("Registered portfolio tracker")

    async def _update_prices(self, event: Event) -> None:
        """Update portfolio tracker with latest prices."""
        if isinstance(event, MarketDataEvent) and self._portfolio_tracker:
            self._portfolio_tracker.update_price(event.symbol, event.close)

    async def _setup_event_handlers(self) -> None:
        """Wire up event subscriptions between components."""
        # OHLCV history listens to market data (highest priority)
        self.event_bus.subscribe(
            EventType.MARKET_DATA,
            self._ohlcv_history.on_market_data,
            priority=10,
        )

        # Price updates to portfolio tracker
        self.event_bus.subscribe(
            EventType.MARKET_DATA,
            self._update_prices,
            priority=20,
        )

        # Strategies listen to market data
        for strategy in self._strategies:
            self.event_bus.subscribe(
                EventType.MARKET_DATA,
                strategy.on_market_data,
                priority=50,
            )

        # Risk manager validates signals
        if self._risk_manager:
            self.event_bus.subscribe(
                EventType.SIGNAL,
                self._risk_manager.on_signal,
                priority=50,
            )

        # Order manager executes approved orders
        if self._order_manager:
            self.event_bus.subscribe(
                EventType.ORDER,
                self._order_manager.on_order,
                priority=50,
            )

        # Portfolio tracker processes fills
        if self._portfolio_tracker:
            self.event_bus.subscribe(
                EventType.FILL,
                self._portfolio_tracker.on_fill,
                priority=50,
            )

    def _setup_signal_handlers(self) -> None:
        """Register OS signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:  # noqa: SIM105
                loop.add_signal_handler(sig, self._handle_shutdown_signal, sig)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler for all signals
                pass

    def _handle_shutdown_signal(self, sig: signal.Signals) -> None:
        """Handle OS shutdown signal."""
        logger.info("Received signal %s, initiating graceful shutdown...", sig.name)
        self._shutdown_event.set()

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat to monitor system health."""
        interval = self.config.bot.heartbeat_interval
        while self._running:
            try:
                event = HeartbeatEvent(
                    source="engine",
                    component="engine",
                    status="healthy",
                    details={
                        "mode": self.config.bot.mode,
                        "event_count": self.event_bus.event_count,
                        "dead_letters": len(self.event_bus.dead_letter_queue),
                        "strategies": len(self._strategies),
                        "data_feeds": len(self._data_feeds),
                    },
                )
                await self.event_bus.publish(event)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error("Heartbeat error: %s", exc)
                await asyncio.sleep(interval)

    async def start(self) -> None:
        """
        Start the trading engine.

        Lifecycle:
        1. Setup event handlers
        2. Initialize components
        3. Start data feeds
        4. Run main loop
        5. Graceful shutdown
        """
        logger.info("Starting %s in %s mode...", self.config.bot.name, self.config.bot.mode)

        try:
            # Setup
            self._running = True
            self.event_bus.start()
            await self._setup_event_handlers()
            self._setup_signal_handlers()

            # Publish startup alert
            await self.event_bus.publish(
                AlertEvent(
                    source="engine",
                    level=AlertLevel.INFO,
                    title="Bot Started",
                    message=f"{self.config.bot.name} started in {self.config.bot.mode} mode",
                )
            )

            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Start data feeds
            feed_tasks = []
            for feed in self._data_feeds:
                task = asyncio.create_task(feed.start(self.event_bus))
                feed_tasks.append(task)

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as exc:
            logger.error("Engine error: %s", exc, exc_info=True)
            await self.event_bus.publish(
                AlertEvent(
                    source="engine",
                    level=AlertLevel.CRITICAL,
                    title="Engine Error",
                    message=str(exc),
                )
            )
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Gracefully shutdown all components."""
        if not self._running:
            return

        logger.info("Shutting down trading engine...")
        self._running = False

        # Cancel heartbeat
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task

        # Stop data feeds
        for feed in self._data_feeds:
            try:
                await feed.stop()
            except Exception as exc:
                logger.error("Error stopping data feed: %s", exc)

        # Publish shutdown alert
        try:  # noqa: SIM105
            await self.event_bus.publish(
                AlertEvent(
                    source="engine",
                    level=AlertLevel.INFO,
                    title="Bot Stopped",
                    message=f"{self.config.bot.name} shut down gracefully",
                )
            )
        except Exception:
            pass
        
        self.event_bus.stop()
        logger.info("Trading engine stopped")

    async def run_once(self, market_data: MarketDataEvent) -> None:
        """
        Process a single market data event through the full pipeline.

        Useful for testing and backtesting.
        """
        await self.event_bus.publish(market_data)
