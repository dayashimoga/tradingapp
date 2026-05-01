"""Abstract base class for broker adapters."""

from __future__ import annotations

import abc
from typing import Any

from tradingbot.core.events import FillEvent, OrderEvent


class Broker(abc.ABC):
    """
    Abstract broker interface.

    All broker adapters must implement place_order and cancel_order.
    """

    @abc.abstractmethod
    async def place_order(self, order: OrderEvent) -> FillEvent:
        """
        Place an order with the broker.

        Args:
            order: The order to execute.

        Returns:
            FillEvent with execution details.

        Raises:
            BrokerError: If the order cannot be placed.
        """

    @abc.abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """
        Cancel an existing order.

        Args:
            broker_order_id: The broker's order ID.

        Returns:
            True if cancelled successfully.
        """

    @abc.abstractmethod
    async def get_account_info(self) -> dict[str, Any]:
        """Get account balance and status."""

    @abc.abstractmethod
    async def get_positions(self) -> dict[str, Any]:
        """Get current open positions."""


class BrokerError(Exception):
    """Exception raised by broker operations."""

    def __init__(self, message: str, broker: str = "", order_id: str = "") -> None:
        super().__init__(message)
        self.broker = broker
        self.order_id = order_id
