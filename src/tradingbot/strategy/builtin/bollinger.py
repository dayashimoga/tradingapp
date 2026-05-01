"""Bollinger Band Strategy — mean reversion based on Bollinger Band touches."""

from __future__ import annotations

import logging
import math
from collections import deque
from typing import Any

from tradingbot.core.events import MarketDataEvent, SignalEvent, SignalSide
from tradingbot.strategy.base import Strategy
from tradingbot.strategy.registry import register_strategy

logger = logging.getLogger(__name__)


@register_strategy("bollinger")
class BollingerBandStrategy(Strategy):
    """
    Bollinger Band Mean Reversion Strategy.

    Generates BUY when price touches/crosses the lower band,
    and SELL when price touches/crosses the upper band.
    """

    def __init__(self, name: str = "bollinger", **kwargs: Any) -> None:
        super().__init__(name=name, **kwargs)
        self._period = int(self._params.get("period", 20))
        self._num_std = float(self._params.get("num_std", 2.0))
        self._prices: deque[float] = deque(maxlen=self._period)

    @property
    def period(self) -> int:
        """Bollinger Band period."""
        return self._period

    @property
    def num_std(self) -> float:
        """Number of standard deviations for band width."""
        return self._num_std

    def _calculate_bands(self) -> tuple[float, float, float] | None:
        """
        Calculate Bollinger Bands.

        Returns (middle_band, upper_band, lower_band) or None if insufficient data.
        """
        if len(self._prices) < self._period:
            return None

        prices = list(self._prices)
        sma = sum(prices) / len(prices)
        variance = sum((p - sma) ** 2 for p in prices) / len(prices)
        std = math.sqrt(variance)

        upper = sma + (self._num_std * std)
        lower = sma - (self._num_std * std)

        return sma, upper, lower

    def calculate_signal(self, market_data: MarketDataEvent) -> SignalEvent | None:
        """
        Calculate Bollinger Band signal.

        BUY when price <= lower band, SELL when price >= upper band.
        """
        self._prices.append(market_data.close)
        bands = self._calculate_bands()

        if bands is None:
            self._is_warmed_up = False
            return None

        self._is_warmed_up = True
        middle, upper, lower = bands
        price = market_data.close
        signal = None

        # Price at or below lower band → BUY (mean reversion up)
        if price <= lower:
            band_width = upper - lower
            distance = lower - price
            strength = min(distance / band_width if band_width > 0 else 0.5, 1.0)

            signal = SignalEvent(
                source=self._name,
                symbol=market_data.symbol,
                side=SignalSide.BUY,
                strength=strength,
                strategy_name=self._name,
                reason=f"Price {price:.2f} at lower band {lower:.2f}",
                suggested_price=price,
                metadata={
                    "middle_band": middle,
                    "upper_band": upper,
                    "lower_band": lower,
                },
            )
            logger.info(
                "BUY signal: %s price=%.2f <= lower_band=%.2f",
                market_data.symbol,
                price,
                lower,
            )

        # Price at or above upper band → SELL (mean reversion down)
        elif price >= upper:
            band_width = upper - lower
            distance = price - upper
            strength = min(distance / band_width if band_width > 0 else 0.5, 1.0)

            signal = SignalEvent(
                source=self._name,
                symbol=market_data.symbol,
                side=SignalSide.SELL,
                strength=strength,
                strategy_name=self._name,
                reason=f"Price {price:.2f} at upper band {upper:.2f}",
                suggested_price=price,
                metadata={
                    "middle_band": middle,
                    "upper_band": upper,
                    "lower_band": lower,
                },
            )
            logger.info(
                "SELL signal: %s price=%.2f >= upper_band=%.2f",
                market_data.symbol,
                price,
                upper,
            )

        return signal

    def reset(self) -> None:
        """Reset strategy state."""
        self._prices.clear()
        self._is_warmed_up = False
