"""Order manager — manages order lifecycle with retry and error handling."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tradingbot.core.events import (
    AlertEvent,
    AlertLevel,
    ErrorEvent,
    Event,
    OrderEvent,
)
from tradingbot.execution.brokers.base import Broker, BrokerError
from tradingbot.execution.retry import RetryExhaustedError, retry_async

if TYPE_CHECKING:
    from tradingbot.config.schema import ExecutionConfig
    from tradingbot.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manages the order lifecycle.

    Receives OrderEvents, executes them through the broker with retry logic,
    and publishes FillEvents or error notifications.
    """

    def __init__(
        self,
        config: ExecutionConfig,
        broker: Broker,
        event_bus: EventBus,
    ) -> None:
        self._config = config
        self._broker = broker
        self._event_bus = event_bus
        self._pending_orders: dict[str, OrderEvent] = {}
        self._filled_count = 0
        self._failed_count = 0

    @property
    def filled_count(self) -> int:
        """Number of successfully filled orders."""
        return self._filled_count

    @property
    def failed_count(self) -> int:
        """Number of failed orders."""
        return self._failed_count

    @property
    def pending_count(self) -> int:
        """Number of orders currently pending."""
        return len(self._pending_orders)

    async def on_order(self, event: Event) -> None:
        """
        Handle an incoming order event.

        Executes the order with retry logic and publishes the result.
        """
        if not isinstance(event, OrderEvent):
            return

        self._pending_orders[event.event_id] = event

        try:
            fill = await retry_async(
                self._broker.place_order,
                event,
                max_attempts=self._config.retry_attempts,
                base_delay=self._config.retry_delay,
                retryable_exceptions=(BrokerError, ConnectionError, TimeoutError),
            )

            self._filled_count += 1
            self._pending_orders.pop(event.event_id, None)

            logger.info(
                "Order filled: %s %s %.6f @ %.2f",
                fill.side.value,
                fill.symbol,
                fill.quantity,
                fill.fill_price,
            )

            # Publish fill event
            await self._event_bus.publish(fill)

        except RetryExhaustedError as exc:
            self._failed_count += 1
            self._pending_orders.pop(event.event_id, None)

            logger.error("Order FAILED after retries: %s %s", event.symbol, exc)

            # Publish error event
            await self._event_bus.publish(
                ErrorEvent(
                    source="order_manager",
                    error_type="order_failed",
                    message=f"Order failed for {event.symbol}: {exc}",
                    component="execution",
                )
            )

            # Publish alert
            await self._event_bus.publish(
                AlertEvent(
                    source="order_manager",
                    level=AlertLevel.CRITICAL,
                    title="Order Failed",
                    message=f"{event.side.value} {event.symbol} qty={event.quantity}: {exc}",
                )
            )
