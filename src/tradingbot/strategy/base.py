"""Abstract base class for trading strategies."""

from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING, Any

from tradingbot.core.events import Event, MarketDataEvent, SignalEvent

if TYPE_CHECKING:
    from tradingbot.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class Strategy(abc.ABC):
    """
    Abstract base class for trading strategies.

    Strategies receive market data events, maintain internal state,
    and emit signal events when trading conditions are met.
    """

    def __init__(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._name = name
        self._params = params or {}
        self._event_bus = event_bus
        self._is_warmed_up = False

    @property
    def name(self) -> str:
        """Strategy name."""
        return self._name

    @property
    def params(self) -> dict[str, Any]:
        """Strategy parameters."""
        return self._params.copy()

    @property
    def is_warmed_up(self) -> bool:
        """Whether the strategy has enough data to generate signals."""
        return self._is_warmed_up

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus for publishing signals."""
        self._event_bus = event_bus

    async def on_market_data(self, event: Event) -> None:
        """
        Handle incoming market data event.

        This is the entry point called by the event bus.
        It delegates to the concrete calculate_signal method.
        """
        if not isinstance(event, MarketDataEvent):
            return

        signal = self.calculate_signal(event)
        if signal is not None and self._event_bus is not None:
            await self._event_bus.publish(signal)

    @abc.abstractmethod
    def calculate_signal(self, market_data: MarketDataEvent) -> SignalEvent | None:
        """
        Calculate a trading signal based on market data.

        Args:
            market_data: The latest market data event.

        Returns:
            A SignalEvent if conditions are met, or None for no action.
        """

    @abc.abstractmethod
    def reset(self) -> None:
        """Reset strategy state (e.g., for backtesting new period)."""
