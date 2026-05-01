"""Circuit breaker — halts trading during extreme volatility."""

from __future__ import annotations

import logging
import math
from collections import deque
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Volatility-based circuit breaker.

    Monitors price changes and triggers when volatility exceeds
    a configurable threshold (measured in standard deviations).
    """

    def __init__(
        self,
        volatility_threshold: float = 3.0,
        cooldown_minutes: int = 30,
        window_size: int = 50,
    ) -> None:
        self._threshold = volatility_threshold
        self._cooldown_minutes = cooldown_minutes
        self._window_size = window_size
        self._price_changes: deque[float] = deque(maxlen=window_size)
        self._last_price: float | None = None
        self._tripped = False
        self._tripped_until: datetime | None = None
        self._trip_count = 0

    @property
    def is_tripped(self) -> bool:
        """Whether the circuit breaker is currently tripped."""
        if self._tripped and self._tripped_until:
            if datetime.now(timezone.utc) >= self._tripped_until:
                self._tripped = False
                self._tripped_until = None
                logger.info("Circuit breaker reset after cooldown")
                return False
        return self._tripped

    @property
    def trip_count(self) -> int:
        """Number of times the circuit breaker has been tripped."""
        return self._trip_count

    @property
    def cooldown_remaining(self) -> float:
        """Remaining cooldown time in seconds, or 0 if not tripped."""
        if not self._tripped or not self._tripped_until:
            return 0.0
        remaining = (self._tripped_until - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, remaining)

    def check_price(self, price: float) -> bool:
        """
        Check a new price and determine if circuit breaker should trip.

        Args:
            price: Current market price.

        Returns:
            True if the circuit breaker is tripped (trading should halt).
        """
        if self.is_tripped:
            return True

        if self._last_price is not None and self._last_price > 0:
            pct_change = (price - self._last_price) / self._last_price
            self._price_changes.append(pct_change)

        self._last_price = price

        # Need enough data to calculate volatility
        if len(self._price_changes) < 3:
            return False

        # Calculate current volatility (standard deviation of % changes)
        changes = list(self._price_changes)
        mean = sum(changes) / len(changes)
        variance = sum((c - mean) ** 2 for c in changes) / len(changes)
        std = math.sqrt(variance) if variance > 0 else 0

        # Check if latest change exceeds threshold * std
        if std > 0 and len(changes) > 0:
            latest_z_score = abs(changes[-1] - mean) / std
            if latest_z_score >= self._threshold:
                self._trip(latest_z_score)
                return True

        return False

    def _trip(self, z_score: float) -> None:
        """Trip the circuit breaker."""
        self._tripped = True
        self._tripped_until = datetime.now(timezone.utc) + timedelta(
            minutes=self._cooldown_minutes
        )
        self._trip_count += 1
        logger.warning(
            "Circuit breaker TRIPPED! z-score=%.2f (threshold=%.2f). "
            "Cooldown: %d minutes. Trip #%d",
            z_score,
            self._threshold,
            self._cooldown_minutes,
            self._trip_count,
        )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._tripped = False
        self._tripped_until = None
        self._price_changes.clear()
        self._last_price = None
        logger.info("Circuit breaker manually reset")
