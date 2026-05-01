"""Simulated market data feed — generates realistic price movements for dashboard demos."""

from __future__ import annotations

import asyncio
import logging
import math
import random
from typing import TYPE_CHECKING

from tradingbot.core.events import MarketDataEvent
from tradingbot.data.base import DataFeed

if TYPE_CHECKING:
    from tradingbot.core.event_bus import EventBus

logger = logging.getLogger(__name__)

# Realistic starting prices for common assets
DEFAULT_PRICES = {
    "BTC/USDT": 64250.0,
    "ETH/USDT": 3180.0,
    "AAPL": 189.50,
    "MSFT": 415.20,
    "TSLA": 178.80,
    "GOOGL": 170.60,
}


class SimulatedDataFeed(DataFeed):
    """
    Generates realistic simulated market data using geometric Brownian motion.

    Produces OHLCV bars at a configurable interval. The price follows
    a random walk with drift and mean-reversion to avoid extreme divergence.
    """

    def __init__(
        self,
        symbols: list[str],
        interval: float = 3.0,
        volatility: float = 0.002,
    ) -> None:
        self._symbols = symbols
        self._interval = interval
        self._volatility = volatility
        self._running = False
        self._prices: dict[str, float] = {}
        self._base_prices: dict[str, float] = {}
        self._tick_count = 0

        # Initialize prices
        for sym in symbols:
            price = DEFAULT_PRICES.get(sym, 100.0 + random.uniform(-20, 80))
            self._prices[sym] = price
            self._base_prices[sym] = price

    async def start(self, event_bus: EventBus) -> None:
        """Start generating simulated market data."""
        self._running = True
        logger.info(
            "SimulatedDataFeed started: %s symbols, %.1fs interval",
            len(self._symbols), self._interval,
        )

        while self._running:
            self._tick_count += 1

            for symbol in self._symbols:
                price = self._prices[symbol]
                base = self._base_prices[symbol]

                # Geometric Brownian motion with mean reversion
                drift = -0.0001 * (price - base) / base  # pull toward base
                shock = random.gauss(0, self._volatility)

                # Add slight sinusoidal trend for visual interest
                trend = 0.0003 * math.sin(self._tick_count / 40)

                change = drift + shock + trend
                new_price = price * (1 + change)

                # Generate OHLCV candle
                high = new_price * (1 + abs(random.gauss(0, self._volatility * 0.5)))
                low = new_price * (1 - abs(random.gauss(0, self._volatility * 0.5)))
                open_price = price  # open = previous close
                volume = random.uniform(100, 50000)

                self._prices[symbol] = new_price

                event = MarketDataEvent(
                    source="simulator",
                    symbol=symbol,
                    open=round(open_price, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(new_price, 2),
                    volume=round(volume, 2),
                    timeframe="simulated",
                    exchange="simulator",
                )

                await event_bus.publish(event)

            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        """Stop the simulated feed."""
        self._running = False
        logger.info("SimulatedDataFeed stopped")

    def is_connected(self) -> bool:
        """Simulator is always connected."""
        return self._running
