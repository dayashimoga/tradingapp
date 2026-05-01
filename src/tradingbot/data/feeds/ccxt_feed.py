"""CCXT data feed — connects to crypto exchanges via CCXT library."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from tradingbot.data.base import DataFeed
from tradingbot.data.normalizer import DataNormalizer

if TYPE_CHECKING:
    from tradingbot.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class CCXTDataFeed(DataFeed):
    """
    Market data feed using CCXT for cryptocurrency exchanges.

    Supports REST polling for OHLCV data. WebSocket streaming
    can be added via ccxt.pro for lower latency.
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        symbols: list[str] | None = None,
        timeframe: str = "1m",
        api_key: str = "",
        secret: str = "",
        sandbox: bool = True,
        poll_interval: float = 60.0,
    ) -> None:
        self._exchange_id = exchange_id
        self._symbols = symbols or ["BTC/USDT"]
        self._timeframe = timeframe
        self._api_key = api_key
        self._secret = secret
        self._sandbox = sandbox
        self._poll_interval = poll_interval
        self._exchange: Any = None
        self._running = False
        self._event_bus: EventBus | None = None

    def _create_exchange(self) -> Any:
        """Create and configure CCXT async exchange instance."""
        import ccxt.async_support as ccxt_async

        exchange_class = getattr(ccxt_async, self._exchange_id)
        config: dict[str, Any] = {
            "enableRateLimit": True,
        }
        if self._api_key:
            config["apiKey"] = self._api_key
        if self._secret:
            config["secret"] = self._secret

        exchange = exchange_class(config)

        if self._sandbox:
            try:
                exchange.set_sandbox_mode(True)
                logger.info("Sandbox mode enabled for %s", self._exchange_id)
            except Exception:
                logger.warning("Sandbox mode not available for %s", self._exchange_id)

        return exchange

    async def start(self, event_bus: EventBus) -> None:
        """Start polling exchange for market data, orderbooks, and funding."""
        self._event_bus = event_bus
        self._exchange = self._create_exchange()
        self._running = True

        logger.info(
            "Starting async CCXT data feed: exchange=%s, symbols=%s, timeframe=%s",
            self._exchange_id,
            self._symbols,
            self._timeframe,
        )

        while self._running:
            try:
                for symbol in self._symbols:
                    # 1. Fetch OHLCV
                    ohlcv_data = await self._exchange.fetch_ohlcv(
                        symbol,
                        self._timeframe,
                        limit=1,
                    )
                    if ohlcv_data:
                        event = DataNormalizer.from_ohlcv_list(
                            symbol=symbol,
                            ohlcv=ohlcv_data[-1],
                            exchange=self._exchange_id,
                            timeframe=self._timeframe,
                        )
                        await event_bus.publish(event)
                        
                    # 2. Fetch Orderbook (Microstructure)
                    try:
                        ob = await self._exchange.fetch_order_book(symbol, limit=20)
                        if ob:
                            from tradingbot.core.events import OrderBookEvent
                            ob_event = OrderBookEvent(
                                symbol=symbol,
                                exchange=self._exchange_id,
                                bids=ob.get("bids", []),
                                asks=ob.get("asks", [])
                            )
                            await event_bus.publish(ob_event)
                    except Exception as e:
                        logger.debug("Failed to fetch orderbook for %s: %s", symbol, e)
                        
                    # 3. Fetch Funding Rate (Derivatives only)
                    if ":" in symbol or "PERP" in symbol.upper() or "SWAP" in symbol.upper():
                        try:
                            funding = await self._exchange.fetch_funding_rate(symbol)
                            if funding:
                                from tradingbot.core.events import FundingRateEvent
                                funding_event = FundingRateEvent(
                                    symbol=symbol,
                                    exchange=self._exchange_id,
                                    funding_rate=funding.get("fundingRate", 0.0),
                                    next_funding_timestamp=funding.get("nextFundingTimestamp")
                                )
                                await event_bus.publish(funding_event)
                        except Exception as e:
                            logger.debug("Failed to fetch funding for %s: %s", symbol, e)

                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("CCXT data feed error: %s", exc)
                await asyncio.sleep(5)  # Back off on error

    async def stop(self) -> None:
        """Stop the data feed."""
        self._running = False
        if self._exchange:
            with contextlib.suppress(Exception):
                await self._exchange.close()
        logger.info("CCXT data feed stopped")

    def is_connected(self) -> bool:
        """Check if exchange is connected."""
        return self._running and self._exchange is not None
