"""Risk limits — configurable trading limits and thresholds."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class TradingLimits:
    """Configurable trading limits that can be checked programmatically."""

    max_daily_loss: float = 500.0
    max_daily_trades: int = 100
    max_position_value: float = 50000.0
    max_total_exposure: float = 0.30
    max_drawdown_pct: float = 0.10
    max_consecutive_losses: int = 5

    # Tracking state
    _daily_loss: float = field(default=0.0, repr=False)
    _daily_trades: int = field(default=0, repr=False)
    _consecutive_losses: int = field(default=0, repr=False)
    _peak_value: float = field(default=0.0, repr=False)
    _reset_date: str = field(default="", repr=False)

    def _check_reset(self) -> None:
        """Reset daily counters if it's a new day."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if today != self._reset_date:
            self._daily_loss = 0.0
            self._daily_trades = 0
            self._reset_date = today

    def record_trade(self, pnl: float) -> None:
        """Record a completed trade's P&L."""
        self._check_reset()
        self._daily_trades += 1

        if pnl < 0:
            self._daily_loss += abs(pnl)
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def update_peak(self, portfolio_value: float) -> None:
        """Update peak portfolio value for drawdown tracking."""
        if portfolio_value > self._peak_value:
            self._peak_value = portfolio_value

    def check_daily_loss(self) -> bool:
        """Returns True if daily loss limit is exceeded."""
        self._check_reset()
        return self._daily_loss >= self.max_daily_loss

    def check_daily_trades(self) -> bool:
        """Returns True if daily trade limit is exceeded."""
        self._check_reset()
        return self._daily_trades >= self.max_daily_trades

    def check_consecutive_losses(self) -> bool:
        """Returns True if consecutive loss limit is exceeded."""
        return self._consecutive_losses >= self.max_consecutive_losses

    def check_drawdown(self, current_value: float) -> bool:
        """Returns True if max drawdown is exceeded."""
        if self._peak_value <= 0:
            return False
        drawdown = (self._peak_value - current_value) / self._peak_value
        return drawdown >= self.max_drawdown_pct

    def check_all(self, current_value: float = 0) -> list[str]:
        """
        Check all limits and return list of violated ones.

        Returns empty list if all limits are within bounds.
        """
        violations = []

        if self.check_daily_loss():
            violations.append(f"Daily loss limit exceeded: ${self._daily_loss:.2f}")

        if self.check_daily_trades():
            violations.append(f"Daily trade limit exceeded: {self._daily_trades}")

        if self.check_consecutive_losses():
            violations.append(
                f"Consecutive losses exceeded: {self._consecutive_losses}"
            )

        if current_value > 0 and self.check_drawdown(current_value):
            violations.append(
                f"Max drawdown exceeded for value ${current_value:.2f}"
            )

        return violations
