"""Unit tests for the event bus."""

from __future__ import annotations

import pytest

from tradingbot.core.event_bus import EventBus
from tradingbot.core.events import (
    AlertEvent,
    EventType,
    HeartbeatEvent,
    MarketDataEvent,
    SignalEvent,
    SignalSide,
)


class TestEventBus:
    """Tests for EventBus pub/sub functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, event_bus):
        """Test basic subscribe and publish."""
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe(EventType.MARKET_DATA, handler)
        event = MarketDataEvent(source="test", symbol="BTC/USDT", close=100.0)
        await event_bus.publish(event)

        assert len(received) == 1
        assert received[0].symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, event_bus):
        """Test multiple handlers for same event type."""
        results = []

        async def handler_a(event):
            results.append("a")

        async def handler_b(event):
            results.append("b")

        event_bus.subscribe(EventType.MARKET_DATA, handler_a)
        event_bus.subscribe(EventType.MARKET_DATA, handler_b)

        await event_bus.publish(MarketDataEvent(source="test"))
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_priority_ordering(self, event_bus):
        """Test that handlers are called in priority order."""
        order = []

        async def low_priority(event):
            order.append("low")

        async def high_priority(event):
            order.append("high")

        event_bus.subscribe(EventType.MARKET_DATA, low_priority, priority=200)
        event_bus.subscribe(EventType.MARKET_DATA, high_priority, priority=10)

        await event_bus.publish(MarketDataEvent(source="test"))
        assert order == ["high", "low"]

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus):
        """Test handler removal."""
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe(EventType.MARKET_DATA, handler)
        result = event_bus.unsubscribe(EventType.MARKET_DATA, handler)
        assert result is True

        await event_bus.publish(MarketDataEvent(source="test"))
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self, event_bus):
        """Test unsubscribing a handler that doesn't exist."""

        async def handler(event):
            pass

        result = event_bus.unsubscribe(EventType.MARKET_DATA, handler)
        assert result is False

    @pytest.mark.asyncio
    async def test_event_history(self, event_bus):
        """Test event history tracking."""
        await event_bus.publish(MarketDataEvent(source="test"))
        await event_bus.publish(MarketDataEvent(source="test2"))

        assert len(event_bus.history) == 2
        assert event_bus.event_count == 2

    @pytest.mark.asyncio
    async def test_history_max_size(self):
        """Test that history respects max size."""
        bus = EventBus(max_history=2)
        for i in range(5):
            await bus.publish(MarketDataEvent(source=f"test{i}"))

        assert len(bus.history) == 2
        assert bus.event_count == 5

    @pytest.mark.asyncio
    async def test_dead_letter_queue(self, event_bus):
        """Test that failed handlers go to dead letter queue."""

        async def failing_handler(event):
            raise ValueError("Handler error")

        event_bus.subscribe(EventType.MARKET_DATA, failing_handler)
        await event_bus.publish(MarketDataEvent(source="test"))

        assert len(event_bus.dead_letter_queue) == 1
        event, exc = event_bus.dead_letter_queue[0]
        assert isinstance(exc, ValueError)

    @pytest.mark.asyncio
    async def test_failed_handler_doesnt_block_others(self, event_bus):
        """Test that a failed handler doesn't prevent other handlers."""
        results = []

        async def failing_handler(event):
            raise ValueError("fail")

        async def working_handler(event):
            results.append("ok")

        event_bus.subscribe(EventType.MARKET_DATA, failing_handler, priority=10)
        event_bus.subscribe(EventType.MARKET_DATA, working_handler, priority=20)

        await event_bus.publish(MarketDataEvent(source="test"))
        assert results == ["ok"]

    @pytest.mark.asyncio
    async def test_no_handlers(self, event_bus):
        """Test publishing with no handlers doesn't error."""
        await event_bus.publish(MarketDataEvent(source="test"))
        assert event_bus.event_count == 1

    @pytest.mark.asyncio
    async def test_publish_many(self, event_bus):
        """Test publishing multiple events."""
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe(EventType.MARKET_DATA, handler)

        events = [MarketDataEvent(source=f"t{i}") for i in range(3)]
        await event_bus.publish_many(events)
        assert len(received) == 3

    def test_start_stop(self, event_bus):
        """Test start/stop lifecycle."""
        assert not event_bus.is_running
        event_bus.start()
        assert event_bus.is_running
        event_bus.stop()
        assert not event_bus.is_running

    def test_clear(self, event_bus):
        """Test clearing all state."""

        async def handler(event):
            pass

        event_bus.subscribe(EventType.MARKET_DATA, handler)
        event_bus.clear()
        assert event_bus.get_subscriber_count() == 0
        assert event_bus.event_count == 0

    def test_subscriber_count(self, event_bus):
        """Test subscriber counting."""

        async def handler(event):
            pass

        event_bus.subscribe(EventType.MARKET_DATA, handler)
        event_bus.subscribe(EventType.SIGNAL, handler)

        assert event_bus.get_subscriber_count() == 2
        assert event_bus.get_subscriber_count(EventType.MARKET_DATA) == 1
        assert event_bus.get_subscriber_count(EventType.FILL) == 0

    @pytest.mark.asyncio
    async def test_different_event_types_isolated(self, event_bus):
        """Test that different event types don't cross-fire."""
        market_received = []
        signal_received = []

        async def market_handler(event):
            market_received.append(event)

        async def signal_handler(event):
            signal_received.append(event)

        event_bus.subscribe(EventType.MARKET_DATA, market_handler)
        event_bus.subscribe(EventType.SIGNAL, signal_handler)

        await event_bus.publish(MarketDataEvent(source="test"))
        assert len(market_received) == 1
        assert len(signal_received) == 0
