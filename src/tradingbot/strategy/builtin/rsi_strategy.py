"""RSI Strategy — buys on oversold conditions, sells on overbought."""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

from tradingbot.core.events import MarketDataEvent, SignalEvent, SignalSide
from tradingbot.strategy.base import Strategy
from tradingbot.strategy.registry import register_strategy

logger = logging.getLogger(__name__)


@register_strategy("rsi")
class RSIStrategy(Strategy):
    """
    Relative Strength Index (RSI) Strategy.

    Generates BUY signal when RSI drops below oversold threshold,
    and SELL signal when RSI rises above overbought threshold.
    """

    def __init__(self, name: str = "rsi", **kwargs: Any) -> None:
        super().__init__(name=name, **kwargs)
        self._period = int(self._params.get("period", 14))
        self._overbought = float(self._params.get("overbought", 70.0))
        self._oversold = float(self._params.get("oversold", 30.0))
        self._prices: deque[float] = deque(maxlen=self._period + 1)
        self._prev_rsi: float | None = None

    @property
    def period(self) -> int:
        """RSI calculation period."""
        return self._period

    @property
    def overbought(self) -> float:
        """Overbought threshold."""
        return self._overbought

    @property
    def oversold(self) -> float:
        """Oversold threshold."""
        return self._oversold

    def _calculate_rsi(self) -> float | None:
        """
        Calculate RSI using the standard Wilder's smoothing method.

        Returns RSI value (0-100) or None if not enough data.
        """
        if len(self._prices) < self._period + 1:
            return None

        prices = list(self._prices)
        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def calculate_signal(self, market_data: MarketDataEvent) -> SignalEvent | None:
        """
        Calculate RSI signal.

        Returns BUY when RSI crosses into oversold, SELL when overbought.
        """
        self._prices.append(market_data.close)
        rsi = self._calculate_rsi()

        if rsi is None:
            self._is_warmed_up = False
            return None

        self._is_warmed_up = True
        signal = None

        # Oversold → BUY
        if rsi < self._oversold and (self._prev_rsi is None or self._prev_rsi >= self._oversold):
            signal = SignalEvent(
                source=self._name,
                symbol=market_data.symbol,
                side=SignalSide.BUY,
                strength=min((self._oversold - rsi) / self._oversold, 1.0),
                strategy_name=self._name,
                reason=f"RSI oversold: {rsi:.1f} < {self._oversold}",
                suggested_price=market_data.close,
                metadata={"rsi": rsi},
            )
            logger.info("BUY signal: %s RSI=%.1f (oversold)", market_data.symbol, rsi)

        # Overbought → SELL
        elif rsi > self._overbought and (
            self._prev_rsi is None or self._prev_rsi <= self._overbought
        ):
            signal = SignalEvent(
                source=self._name,
                symbol=market_data.symbol,
                side=SignalSide.SELL,
                strength=min((rsi - self._overbought) / (100 - self._overbought), 1.0),
                strategy_name=self._name,
                reason=f"RSI overbought: {rsi:.1f} > {self._overbought}",
                suggested_price=market_data.close,
                metadata={"rsi": rsi},
            )
            logger.info("SELL signal: %s RSI=%.1f (overbought)", market_data.symbol, rsi)

        self._prev_rsi = rsi
        return signal

    def get_state(self) -> dict[str, any]:
        """Get current RSI state for dashboard."""
        rsi = self._calculate_rsi()
        zone = "warming_up"
        if rsi is not None:
            if rsi < self._oversold:
                zone = "oversold"
            elif rsi > self._overbought:
                zone = "overbought"
            else:
                zone = "neutral"
        return {
            **super().get_state(),
            "type": "Mean Reversion",
            "rsi": round(rsi, 1) if rsi is not None else None,
            "zone": zone,
            "overbought": self._overbought,
            "oversold": self._oversold,
            "period": self._period,
            "data_points": len(self._prices),
        }

    def reset(self) -> None:
        """Reset strategy state."""
        self._prices.clear()
        self._prev_rsi = None
        self._is_warmed_up = False
