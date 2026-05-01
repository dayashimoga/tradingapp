"""Alpaca broker adapter — executes orders on Alpaca Markets."""

from __future__ import annotations

import logging
from typing import Any

from tradingbot.core.events import FillEvent, OrderEvent, OrderType, SignalSide
from tradingbot.execution.brokers.base import Broker, BrokerError

logger = logging.getLogger(__name__)


class AlpacaBroker(Broker):
    """
    Broker adapter for Alpaca Markets (US Stocks/ETFs).

    Supports market and limit orders via the Alpaca Python SDK.
    """

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        paper: bool = True,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._paper = paper
        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create Alpaca trading client."""
        if self._client is None:
            from alpaca.trading.client import TradingClient

            self._client = TradingClient(
                api_key=self._api_key,
                secret_key=self._secret_key,
                paper=self._paper,
            )
        return self._client

    async def place_order(self, order: OrderEvent) -> FillEvent:
        """Place an order via Alpaca."""
        client = self._get_client()

        try:
            from alpaca.trading.enums import OrderSide, TimeInForce
            from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

            side = OrderSide.BUY if order.side == SignalSide.BUY else OrderSide.SELL

            if order.order_type == OrderType.MARKET:
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
            elif order.order_type == OrderType.LIMIT:
                if order.price is None:
                    raise BrokerError("Limit order requires a price", broker="alpaca")
                request = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=order.price,
                )
            else:
                raise BrokerError(
                    f"Unsupported order type: {order.order_type}",
                    broker="alpaca",
                )

            result = client.submit_order(request)

            fill_price = float(result.filled_avg_price or order.price or 0)
            filled_qty = float(result.filled_qty or order.quantity)

            logger.info(
                "Alpaca order submitted: %s %s %.2f @ %.2f",
                side.value,
                order.symbol,
                filled_qty,
                fill_price,
            )

            return FillEvent(
                source="alpaca_broker",
                symbol=order.symbol,
                side=order.side,
                quantity=filled_qty,
                fill_price=fill_price,
                commission=0.0,  # Alpaca is commission-free for stocks
                order_id=order.event_id,
                broker_order_id=str(result.id),
            )

        except BrokerError:
            raise
        except Exception as exc:
            raise BrokerError(
                f"Alpaca order failed: {exc}",
                broker="alpaca",
                order_id=order.event_id,
            ) from exc

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order via Alpaca."""
        client = self._get_client()
        try:
            client.cancel_order_by_id(broker_order_id)
            return True
        except Exception as exc:
            logger.error("Failed to cancel order %s: %s", broker_order_id, exc)
            return False

    async def get_account_info(self) -> dict[str, Any]:
        """Get Alpaca account info."""
        client = self._get_client()
        try:
            account = client.get_account()
            return {
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "status": account.status,
            }
        except Exception as exc:
            raise BrokerError(f"Failed to fetch account: {exc}", broker="alpaca") from exc

    async def get_positions(self) -> dict[str, Any]:
        """Get open positions from Alpaca."""
        client = self._get_client()
        try:
            positions = client.get_all_positions()
            return {
                p.symbol: {
                    "qty": float(p.qty),
                    "avg_entry_price": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "unrealized_pl": float(p.unrealized_pl),
                }
                for p in positions
            }
        except Exception as exc:
            logger.error("Failed to fetch positions: %s", exc)
            return {}
