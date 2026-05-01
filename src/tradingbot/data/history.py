"""OHLCV history buffer — stores candle data for chart rendering and analysis."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Any

from tradingbot.core.events import Event, MarketDataEvent

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """Single OHLCV candle."""

    time: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)


class OHLCVHistory:
    """
    Ring buffer for OHLCV history per symbol.

    Listens to MarketDataEvent and stores candles for REST API
    and chart rendering. Used to populate TradingView charts on
    initial page load.
    """

    def __init__(self, max_candles: int = 500) -> None:
        self._max_candles = max_candles
        self._history: dict[str, deque[Candle]] = defaultdict(
            lambda: deque(maxlen=max_candles)
        )
        self._latest_prices: dict[str, float] = {}

    @property
    def symbols(self) -> list[str]:
        """Get all symbols with history."""
        return list(self._history.keys())

    @property
    def latest_prices(self) -> dict[str, float]:
        """Get latest price per symbol."""
        return dict(self._latest_prices)

    async def on_market_data(self, event: Event) -> None:
        """Handle MarketDataEvent — store candle in history."""
        if not isinstance(event, MarketDataEvent):
            return

        candle = Candle(
            time=int(event.timestamp.timestamp()),
            open=event.open,
            high=event.high,
            low=event.low,
            close=event.close,
            volume=event.volume,
        )
        self._history[event.symbol].append(candle)
        self._latest_prices[event.symbol] = event.close

    def get_candles(self, symbol: str, limit: int = 200) -> list[Candle]:
        """Get recent candles for a symbol."""
        candles = list(self._history.get(symbol, []))
        return candles[-limit:]

    def get_candles_dict(self, symbol: str, limit: int = 200) -> list[dict[str, Any]]:
        """Get recent candles as dicts for JSON serialization."""
        return [c.to_dict() for c in self.get_candles(symbol, limit)]

    def get_all_symbols(self) -> list[str]:
        """Get all symbols with stored data."""
        return list(self._history.keys())

    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()
        self._latest_prices.clear()
