"""Alpaca data feed — connects to Alpaca Markets for US equities."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tradingbot.core.event_bus import EventBus
from tradingbot.data.base import DataFeed
from tradingbot.data.normalizer import DataNormalizer

logger = logging.getLogger(__name__)


class AlpacaDataFeed(DataFeed):
    """
    Market data feed using Alpaca Markets API for US stocks/ETFs.

    Uses REST polling for bar data. Can be extended for WebSocket streaming.
    """

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        symbols: list[str] | None = None,
        timeframe: str = "1m",
        paper: bool = True,
        poll_interval: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._symbols = symbols or ["AAPL"]
        self._timeframe = timeframe
        self._paper = paper
        self._poll_interval = poll_interval
        self._client: Any = None
        self._running = False

    def _create_client(self) -> Any:
        """Create Alpaca API client."""
        from alpaca.data.historical import StockHistoricalDataClient

        client = StockHistoricalDataClient(
            api_key=self._api_key or None,
            secret_key=self._secret_key or None,
        )
        return client

    async def start(self, event_bus: EventBus) -> None:
        """Start polling Alpaca for market data."""
        self._client = self._create_client()
        self._running = True

        logger.info(
            "Starting Alpaca data feed: symbols=%s, paper=%s",
            self._symbols,
            self._paper,
        )

        while self._running:
            try:
                from alpaca.data.requests import StockLatestBarRequest

                request = StockLatestBarRequest(symbol_or_symbols=self._symbols)
                bars = self._client.get_stock_latest_bar(request)

                for symbol, bar in bars.items():
                    bar_dict = {
                        "o": bar.open,
                        "h": bar.high,
                        "l": bar.low,
                        "c": bar.close,
                        "v": bar.volume,
                    }
                    event = DataNormalizer.from_alpaca_bar(
                        symbol=symbol,
                        bar=bar_dict,
                    )
                    await event_bus.publish(event)

                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Alpaca data feed error: %s", exc)
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the data feed."""
        self._running = False
        logger.info("Alpaca data feed stopped")

    def is_connected(self) -> bool:
        """Check if Alpaca client is connected."""
        return self._running and self._client is not None
