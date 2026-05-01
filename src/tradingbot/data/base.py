"""Abstract base class for market data feeds."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tradingbot.core.event_bus import EventBus


class DataFeed(abc.ABC):
    """
    Abstract base class for market data feeds.

    All data feeds must implement start() and stop() methods.
    Data is published to the event bus as MarketDataEvent instances.
    """

    @abc.abstractmethod
    async def start(self, event_bus: EventBus) -> None:
        """
        Start streaming market data and publishing to the event bus.

        Args:
            event_bus: The event bus to publish MarketDataEvent instances to.
        """

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop the data feed and clean up resources."""

    @abc.abstractmethod
    def is_connected(self) -> bool:
        """Check if the feed is currently connected and receiving data."""
