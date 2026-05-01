"""AsyncIO event bus — the central nervous system of the trading engine."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from tradingbot.core.events import Event, EventType

logger = logging.getLogger(__name__)

# Type alias for event handler callbacks
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Asynchronous publish/subscribe event bus.

    Components subscribe to specific event types and receive
    events asynchronously when published. Supports:
    - Type-safe subscriptions
    - Handler priority ordering
    - Dead-letter queue for failed events
    - Event history for debugging
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._subscribers: dict[EventType, list[tuple[int, EventHandler]]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history = max_history
        self._dead_letter: list[tuple[Event, Exception]] = []
        self._running = False
        self._event_count = 0

    @property
    def event_count(self) -> int:
        """Total number of events processed."""
        return self._event_count

    @property
    def history(self) -> list[Event]:
        """Recent event history (read-only copy)."""
        return list(self._history)

    @property
    def dead_letter_queue(self) -> list[tuple[Event, Exception]]:
        """Events that failed processing."""
        return list(self._dead_letter)

    @property
    def is_running(self) -> bool:
        """Whether the event bus is active."""
        return self._running

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
        priority: int = 100,
    ) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: The type of event to listen for.
            handler: Async callback to invoke when event is published.
            priority: Lower values = higher priority (processed first).
        """
        self._subscribers[event_type].append((priority, handler))
        # Sort by priority (lower = first)
        self._subscribers[event_type].sort(key=lambda x: x[0])
        logger.debug(
            "Subscribed %s to %s (priority=%d)",
            handler.__qualname__,
            event_type.value,
            priority,
        )

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> bool:
        """
        Remove a handler from an event type.

        Returns:
            True if handler was found and removed, False otherwise.
        """
        handlers = self._subscribers.get(event_type, [])
        for i, (_, h) in enumerate(handlers):
            if h is handler:
                handlers.pop(i)
                logger.debug("Unsubscribed %s from %s", handler.__qualname__, event_type.value)
                return True
        return False

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Events are delivered sequentially to handlers in priority order.
        Failed handlers are logged and the event is added to the dead letter queue,
        but processing continues for remaining handlers.
        """
        self._event_count += 1

        # Record in history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        handlers = self._subscribers.get(event.event_type, [])
        if not handlers:
            logger.debug("No handlers for event type: %s", event.event_type.value)
            return

        for _, handler in handlers:
            try:
                await handler(event)
            except Exception as exc:
                logger.error(
                    "Handler %s failed for event %s: %s",
                    handler.__qualname__,
                    event.event_id,
                    exc,
                    exc_info=True,
                )
                self._dead_letter.append((event, exc))

    async def publish_many(self, events: list[Event]) -> None:
        """Publish multiple events sequentially."""
        for event in events:
            await self.publish(event)

    def start(self) -> None:
        """Mark the event bus as running."""
        self._running = True
        logger.info("Event bus started")

    def stop(self) -> None:
        """Mark the event bus as stopped."""
        self._running = False
        logger.info("Event bus stopped")

    def clear(self) -> None:
        """Clear all subscribers, history, and dead letter queue."""
        self._subscribers.clear()
        self._history.clear()
        self._dead_letter.clear()
        self._event_count = 0

    def get_subscriber_count(self, event_type: EventType | None = None) -> int:
        """Get the number of subscribers, optionally filtered by event type."""
        if event_type is not None:
            return len(self._subscribers.get(event_type, []))
        return sum(len(handlers) for handlers in self._subscribers.values())
