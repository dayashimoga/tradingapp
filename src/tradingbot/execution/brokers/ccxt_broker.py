"""CCXT broker adapter — executes orders on crypto exchanges."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from tradingbot.core.events import FillEvent, OrderEvent, OrderType, SignalSide
from tradingbot.execution.brokers.base import Broker, BrokerError

logger = logging.getLogger(__name__)


class CCXTBroker(Broker):
    """
    Broker adapter for cryptocurrency exchanges via CCXT.

    Supports market and limit orders on any CCXT-supported exchange.
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: str = "",
        secret: str = "",
        sandbox: bool = True,
    ) -> None:
        self._exchange_id = exchange_id
        self._api_key = api_key
        self._secret = secret
        self._sandbox = sandbox
        self._exchange: Any = None

    def _get_exchange(self) -> Any:
        """Get or create CCXT exchange instance."""
        if self._exchange is None:
            import ccxt.async_support as ccxt

            exchange_class = getattr(ccxt, self._exchange_id)
            config: dict[str, Any] = {"enableRateLimit": True}
            if self._api_key:
                config["apiKey"] = self._api_key
            if self._secret:
                config["secret"] = self._secret

            self._exchange = exchange_class(config)

            if self._sandbox:
                try:
                    self._exchange.set_sandbox_mode(True)
                except Exception:
                    logger.warning("Sandbox not available for %s", self._exchange_id)

        return self._exchange

    async def place_order(self, order: OrderEvent) -> FillEvent:
        """Place an order via CCXT."""
        exchange = self._get_exchange()
        side = "buy" if order.side == SignalSide.BUY else "sell"

        try:
            if order.order_type == OrderType.MARKET:
                result = await exchange.create_market_order(
                    order.symbol,
                    side,
                    order.quantity,
                )
            elif order.order_type == OrderType.LIMIT:
                if order.price is None:
                    raise BrokerError("Limit order requires a price", broker="ccxt")
                result = await exchange.create_limit_order(
                    order.symbol,
                    side,
                    order.quantity,
                    order.price,
                )
            else:
                raise BrokerError(
                    f"Unsupported order type: {order.order_type}",
                    broker="ccxt",
                )

            fill_price = float(result.get("average", result.get("price", 0)) or 0)
            filled_qty = float(result.get("filled", order.quantity) or order.quantity)
            fee = result.get("fee", {})
            commission = float(fee.get("cost", 0) if fee else 0)

            logger.info(
                "CCXT order filled: %s %s %.6f @ %.2f",
                side,
                order.symbol,
                filled_qty,
                fill_price,
            )

            return FillEvent(
                source="ccxt_broker",
                symbol=order.symbol,
                side=order.side,
                quantity=filled_qty,
                fill_price=fill_price,
                commission=commission,
                order_id=order.event_id,
                broker_order_id=str(result.get("id", uuid.uuid4())),
            )

        except Exception as exc:
            raise BrokerError(
                f"CCXT order failed: {exc}",
                broker="ccxt",
                order_id=order.event_id,
            ) from exc

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order via CCXT."""
        exchange = self._get_exchange()
        try:
            # We don't have symbol here easily, some exchanges require it.
            # Assuming exchange doesn't strictly need it if only broker_order_id is passed,
            # or it might fail for exchanges like Binance that require symbol for cancellation.
            await exchange.cancel_order(broker_order_id)
            return True
        except Exception as exc:
            logger.error("Failed to cancel order %s: %s", broker_order_id, exc)
            return False

    async def get_account_info(self) -> dict[str, Any]:
        """Get account balance from exchange."""
        exchange = self._get_exchange()
        try:
            balance = await exchange.fetch_balance()
            return {
                "total": balance.get("total", {}),
                "free": balance.get("free", {}),
                "used": balance.get("used", {}),
            }
        except Exception as exc:
            raise BrokerError(f"Failed to fetch account info: {exc}", broker="ccxt") from exc

    async def get_positions(self) -> dict[str, Any]:
        """Get open positions (for exchanges that support it)."""
        exchange = self._get_exchange()
        try:
            if hasattr(exchange, "fetch_positions"):
                positions = await exchange.fetch_positions()
                return {p["symbol"]: p for p in positions}
            return {}
        except Exception as exc:
            logger.error("Failed to fetch positions: %s", exc)
            return {}

    async def close(self) -> None:
        if self._exchange:
            import contextlib
            with contextlib.suppress(Exception):
                await self._exchange.close()
