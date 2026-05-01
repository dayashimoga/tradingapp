"""SMA Crossover Strategy — buys when fast SMA crosses above slow SMA, sells on cross below."""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

from tradingbot.core.events import MarketDataEvent, SignalEvent, SignalSide
from tradingbot.strategy.base import Strategy
from tradingbot.strategy.registry import register_strategy

logger = logging.getLogger(__name__)


@register_strategy("sma_crossover")
class SMACrossoverStrategy(Strategy):
    """
    Simple Moving Average Crossover Strategy.

    Generates BUY signal when the fast SMA crosses above the slow SMA,
    and SELL signal when fast SMA crosses below slow SMA.
    """

    def __init__(self, name: str = "sma_crossover", **kwargs: Any) -> None:
        super().__init__(name=name, **kwargs)
        self._fast_period = int(self._params.get("fast_period", 10))
        self._slow_period = int(self._params.get("slow_period", 30))
        self._prices: deque[float] = deque(maxlen=self._slow_period)
        self._prev_fast_above: bool | None = None

    @property
    def fast_period(self) -> int:
        """Fast SMA period."""
        return self._fast_period

    @property
    def slow_period(self) -> int:
        """Slow SMA period."""
        return self._slow_period

    def _calculate_sma(self, period: int) -> float | None:
        """Calculate SMA for the given period."""
        if len(self._prices) < period:
            return None
        prices = list(self._prices)[-period:]
        return sum(prices) / period

    def calculate_signal(self, market_data: MarketDataEvent) -> SignalEvent | None:
        """
        Calculate SMA crossover signal.

        Returns BUY on golden cross, SELL on death cross, None otherwise.
        """
        self._prices.append(market_data.close)

        fast_sma = self._calculate_sma(self._fast_period)
        slow_sma = self._calculate_sma(self._slow_period)

        if fast_sma is None or slow_sma is None:
            self._is_warmed_up = False
            return None

        self._is_warmed_up = True
        fast_above = fast_sma > slow_sma

        # First data point after warm-up — set baseline, no signal
        if self._prev_fast_above is None:
            self._prev_fast_above = fast_above
            return None

        signal = None

        # Golden cross: fast SMA crosses above slow SMA → BUY
        if fast_above and not self._prev_fast_above:
            signal = SignalEvent(
                source=self._name,
                symbol=market_data.symbol,
                side=SignalSide.BUY,
                strength=min(abs(fast_sma - slow_sma) / slow_sma * 100, 1.0),
                strategy_name=self._name,
                reason=f"Golden cross: fast_sma={fast_sma:.2f} > slow_sma={slow_sma:.2f}",
                suggested_price=market_data.close,
                metadata={"fast_sma": fast_sma, "slow_sma": slow_sma},
            )
            logger.info(
                "BUY signal: %s fast_sma=%.2f > slow_sma=%.2f",
                market_data.symbol,
                fast_sma,
                slow_sma,
            )

        # Death cross: fast SMA crosses below slow SMA → SELL
        elif not fast_above and self._prev_fast_above:
            signal = SignalEvent(
                source=self._name,
                symbol=market_data.symbol,
                side=SignalSide.SELL,
                strength=min(abs(fast_sma - slow_sma) / slow_sma * 100, 1.0),
                strategy_name=self._name,
                reason=f"Death cross: fast_sma={fast_sma:.2f} < slow_sma={slow_sma:.2f}",
                suggested_price=market_data.close,
                metadata={"fast_sma": fast_sma, "slow_sma": slow_sma},
            )
            logger.info(
                "SELL signal: %s fast_sma=%.2f < slow_sma=%.2f",
                market_data.symbol,
                fast_sma,
                slow_sma,
            )

        self._prev_fast_above = fast_above
        return signal

    def get_state(self) -> dict[str, any]:
        """Get current SMA crossover state for dashboard."""
        fast_sma = self._calculate_sma(self._fast_period)
        slow_sma = self._calculate_sma(self._slow_period)
        crossover = "warming_up"
        if fast_sma is not None and slow_sma is not None:
            crossover = "golden" if fast_sma > slow_sma else "death"
        return {
            **super().get_state(),
            "type": "Trend Following",
            "fast_sma": round(fast_sma, 2) if fast_sma else None,
            "slow_sma": round(slow_sma, 2) if slow_sma else None,
            "fast_period": self._fast_period,
            "slow_period": self._slow_period,
            "crossover": crossover,
            "data_points": len(self._prices),
        }

    def reset(self) -> None:
        """Reset strategy state."""
        self._prices.clear()
        self._prev_fast_above = None
        self._is_warmed_up = False
