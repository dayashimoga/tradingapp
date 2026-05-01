"""Market data normalizer — converts raw exchange data to standardized format."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from tradingbot.core.events import MarketDataEvent

logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    Normalizes raw market data from different sources into
    a consistent MarketDataEvent format.
    """

    @staticmethod
    def from_ohlcv_list(
        symbol: str,
        ohlcv: list[float | int],
        exchange: str = "",
        timeframe: str = "1m",
    ) -> MarketDataEvent:
        """
        Normalize a CCXT-style OHLCV list: [timestamp, open, high, low, close, volume].

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT").
            ohlcv: List of [timestamp_ms, open, high, low, close, volume].
            exchange: Exchange name.
            timeframe: Candle timeframe.

        Returns:
            Normalized MarketDataEvent.
        """
        if len(ohlcv) < 6:
            raise ValueError(f"OHLCV list must have at least 6 elements, got {len(ohlcv)}")

        timestamp_ms = ohlcv[0]
        ts = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        return MarketDataEvent(
            timestamp=ts,
            source=exchange,
            symbol=symbol,
            open=float(ohlcv[1]),
            high=float(ohlcv[2]),
            low=float(ohlcv[3]),
            close=float(ohlcv[4]),
            volume=float(ohlcv[5]),
            timeframe=timeframe,
            exchange=exchange,
        )

    @staticmethod
    def from_ticker(
        symbol: str,
        ticker: dict[str, Any],
        exchange: str = "",
    ) -> MarketDataEvent:
        """
        Normalize a CCXT-style ticker dictionary.

        Args:
            symbol: Trading pair symbol.
            ticker: Ticker dictionary with keys like 'last', 'high', 'low', etc.
            exchange: Exchange name.

        Returns:
            Normalized MarketDataEvent.
        """
        last_price = float(ticker.get("last", 0) or 0)

        return MarketDataEvent(
            source=exchange,
            symbol=symbol,
            open=float(ticker.get("open", last_price) or last_price),
            high=float(ticker.get("high", last_price) or last_price),
            low=float(ticker.get("low", last_price) or last_price),
            close=last_price,
            volume=float(ticker.get("baseVolume", 0) or 0),
            timeframe="tick",
            exchange=exchange,
            raw_data=ticker,
        )

    @staticmethod
    def from_alpaca_bar(
        symbol: str,
        bar: dict[str, Any],
    ) -> MarketDataEvent:
        """
        Normalize an Alpaca bar dictionary.

        Args:
            symbol: Trading symbol.
            bar: Alpaca bar with keys 'o', 'h', 'l', 'c', 'v', 't'.

        Returns:
            Normalized MarketDataEvent.
        """
        return MarketDataEvent(
            source="alpaca",
            symbol=symbol,
            open=float(bar.get("o", 0)),
            high=float(bar.get("h", 0)),
            low=float(bar.get("l", 0)),
            close=float(bar.get("c", 0)),
            volume=float(bar.get("v", 0)),
            timeframe="1m",
            exchange="alpaca",
            raw_data=bar,
        )
