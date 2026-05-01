"""Macro Economic and News Data Feed using yfinance."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import yfinance as yf

from tradingbot.data.base import DataFeed

if TYPE_CHECKING:
    from tradingbot.core.event_bus import EventBus
    from tradingbot.core.events import MarketDataEvent

logger = logging.getLogger(__name__)


class MacroFeed(DataFeed):
    """
    Fetches macroeconomic data and news headlines using yfinance.
    """

    def __init__(self, symbols: list[str] | None = None, poll_interval: float = 3600.0) -> None:
        # Default to SPY, DXY (Dollar Index), and Gold as macro proxies
        self._symbols = symbols or ["SPY", "DX-Y.NYB", "GC=F"]
        self._poll_interval = poll_interval
        self._running = False
        self._event_bus: EventBus | None = None

    async def start(self, event_bus: EventBus) -> None:
        """Start polling macro data."""
        self._event_bus = event_bus
        self._running = True

        logger.info("Starting Macro feed for symbols: %s", self._symbols)

        while self._running:
            try:
                # We offload blocking yfinance calls to thread
                await asyncio.to_thread(self._fetch_macro_data)
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Macro data feed error: %s", exc)
                await asyncio.sleep(60)

    def _fetch_macro_data(self) -> None:
        """Fetch macro data synchronously (run in thread pool)."""
        # In a real implementation we would parse the yfinance Ticker data
        # and emit custom MacroEvent or SentimentEvent.
        # This is just a stub for now.
        for symbol in self._symbols:
            try:
                ticker = yf.Ticker(symbol)
                # Just ping it to ensure we have connection
                info = ticker.fast_info
                logger.debug("Fetched macro proxy %s: %s", symbol, info.get("lastPrice"))
            except Exception as e:
                logger.warning("Failed to fetch macro data for %s: %s", symbol, e)

    async def stop(self) -> None:
        self._running = False
        logger.info("Macro feed stopped.")

    def is_connected(self) -> bool:
        return self._running
