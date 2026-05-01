"""Paper broker — simulated order execution for testing and development."""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from typing import Any

from tradingbot.core.events import FillEvent, OrderEvent, SignalSide
from tradingbot.execution.brokers.base import Broker, BrokerError

logger = logging.getLogger(__name__)


class PaperBroker(Broker):
    """
    Simulated broker for paper trading.

    Provides realistic order fills with configurable slippage and latency.
    Maintains an in-memory portfolio for tracking positions and balances.
    """

    def __init__(
        self,
        initial_balance: float = 100000.0,
        slippage: float = 0.0005,
        latency_ms: int = 50,
        commission_rate: float = 0.001,
    ) -> None:
        self._balance = initial_balance
        self._initial_balance = initial_balance
        self._slippage = slippage
        self._latency_ms = latency_ms
        self._commission_rate = commission_rate
        self._positions: dict[str, float] = {}
        self._order_history: list[dict[str, Any]] = []

    @property
    def balance(self) -> float:
        """Current cash balance."""
        return self._balance

    @property
    def positions(self) -> dict[str, float]:
        """Current positions (symbol → quantity)."""
        return self._positions.copy()

    async def place_order(self, order: OrderEvent) -> FillEvent:
        """
        Simulate order execution with realistic slippage and latency.

        Args:
            order: The order to execute.

        Returns:
            FillEvent with simulated execution details.
        """
        # Simulate network latency
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000)

        # Calculate fill price with slippage
        base_price = order.price or 0
        if base_price <= 0:
            raise BrokerError(
                "Cannot fill order with zero price",
                broker="paper",
                order_id=order.event_id,
            )

        # Apply random slippage (adverse for the trader)
        slippage_factor = 1 + (random.uniform(0, self._slippage))
        if order.side == SignalSide.BUY:
            fill_price = base_price * slippage_factor  # Pay more
        else:
            fill_price = base_price * (2 - slippage_factor)  # Receive less

        # Calculate commission
        trade_value = fill_price * order.quantity
        commission = trade_value * self._commission_rate

        # Validate balance for buys
        if order.side == SignalSide.BUY:
            total_cost = trade_value + commission
            if total_cost > self._balance:
                raise BrokerError(
                    f"Insufficient balance: need {total_cost:.2f}, have {self._balance:.2f}",
                    broker="paper",
                    order_id=order.event_id,
                )

        # Update positions and balance
        broker_order_id = str(uuid.uuid4())

        if order.side == SignalSide.BUY:
            self._balance -= trade_value + commission
            current_qty = self._positions.get(order.symbol, 0)
            self._positions[order.symbol] = current_qty + order.quantity
        else:
            self._balance += trade_value - commission
            current_qty = self._positions.get(order.symbol, 0)
            new_qty = current_qty - order.quantity
            if new_qty <= 0:
                self._positions.pop(order.symbol, None)
            else:
                self._positions[order.symbol] = new_qty

        # Record order
        self._order_history.append({
            "broker_order_id": broker_order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "fill_price": fill_price,
            "commission": commission,
        })

        logger.info(
            "Paper trade executed: %s %s %.6f @ %.2f (commission: %.2f)",
            order.side.value,
            order.symbol,
            order.quantity,
            fill_price,
            commission,
        )

        return FillEvent(
            source="paper_broker",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
            order_id=order.event_id,
            broker_order_id=broker_order_id,
            strategy_name=order.strategy_name,
            reason=order.reason,
            metadata=order.metadata,
        )

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Paper broker orders fill instantly, so cancel always returns False."""
        logger.warning("Paper broker: cancel not applicable (orders fill instantly)")
        return False

    async def get_account_info(self) -> dict[str, Any]:
        """Get simulated account info."""
        return {
            "balance": self._balance,
            "initial_balance": self._initial_balance,
            "pnl": self._balance - self._initial_balance,
            "total_trades": len(self._order_history),
        }

    async def get_positions(self) -> dict[str, Any]:
        """Get current positions."""
        return self._positions.copy()
