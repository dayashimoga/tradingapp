"""Multi-Timeframe Aggregator — Buffers and resamples tick/1m data to higher timeframes."""

import asyncio
import logging
from collections import defaultdict
import pandas as pd
from datetime import datetime, timezone

from tradingbot.core.events import EventType, MarketDataEvent

logger = logging.getLogger(__name__)

class TimeframeAggregator:
    """
    Listens to MarketDataEvents, buffers them, and builds OHLCV DataFrames 
    for multiple timeframes (e.g., 1m, 5m, 15m, 1h).
    """
    
    TIMEFRAMES = ["1min", "5min", "15min", "1h", "4h", "1D"]

    def __init__(self, max_candles: int = 1000):
        self._max_candles = max_candles
        # {symbol: list of dicts with 'time', 'open', 'high', 'low', 'close', 'volume'}
        self._raw_data: dict[str, list[dict]] = defaultdict(list)
        # {symbol: {timeframe: pd.DataFrame}}
        self._resampled_data: dict[str, dict[str, pd.DataFrame]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def on_market_data(self, event: MarketDataEvent) -> None:
        """Handle incoming market data and buffer it."""
        if not isinstance(event, MarketDataEvent):
            return

        async with self._lock:
            # Ensure timestamp is tz-aware for pandas resampling
            dt = event.timestamp
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            self._raw_data[event.symbol].append({
                "time": dt,
                "open": event.open,
                "high": event.high,
                "low": event.low,
                "close": event.close,
                "volume": event.volume
            })
            
            # Prune if too large (keep a large enough buffer for the highest timeframe, e.g. 1d needs 1440 * 1m candles for just 1 day. Let's keep 10000)
            if len(self._raw_data[event.symbol]) > 10000:
                self._raw_data[event.symbol] = self._raw_data[event.symbol][-10000:]

    async def _resample(self, symbol: str) -> None:
        """Resample the raw buffered data into pandas DataFrames for all timeframes."""
        async with self._lock:
            data = self._raw_data.get(symbol)
            if not data or len(data) < 2:
                return

            df = pd.DataFrame(data)
            df.set_index("time", inplace=True)
            
            for tf in self.TIMEFRAMES:
                try:
                    # Resample rules: O=first, H=max, L=min, C=last, V=sum
                    resampled = df.resample(tf).agg({
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum'
                    }).dropna()
                    
                    # Store up to max_candles
                    if len(resampled) > self._max_candles:
                        resampled = resampled.iloc[-self._max_candles:]
                        
                    self._resampled_data[symbol][tf] = resampled
                except Exception as e:
                    logger.error("Failed to resample %s to %s: %s", symbol, tf, e)

    async def get_dataframe(self, symbol: str, timeframe: str = "5min") -> pd.DataFrame:
        """Get the latest DataFrame for a specific symbol and timeframe."""
        await self._resample(symbol)
        async with self._lock:
            return self._resampled_data[symbol].get(timeframe, pd.DataFrame())

    async def get_multi_timeframe_state(self, symbol: str) -> dict[str, str]:
        """
        Check trend alignment across timeframes.
        Returns a dict mapping timeframe to 'BULLISH'/'BEARISH'/'NEUTRAL'.
        """
        await self._resample(symbol)
        state = {}
        async with self._lock:
            for tf in self.TIMEFRAMES:
                df = self._resampled_data[symbol].get(tf)
                if df is not None and len(df) >= 20:
                    # Simple heuristic: Close > 20-period SMA
                    sma = df['close'].rolling(20).mean().iloc[-1]
                    close = df['close'].iloc[-1]
                    state[tf] = "BULLISH" if close > sma else "BEARISH"
                else:
                    state[tf] = "NEUTRAL"
        return state
