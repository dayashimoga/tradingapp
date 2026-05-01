"""Advanced Risk Management Layer."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tradingbot.core.events import SignalEvent

logger = logging.getLogger(__name__)


@dataclass
class RiskProfile:
    """Defines global risk limits."""
    max_portfolio_risk_pct: float = 0.05
    max_position_risk_pct: float = 0.02
    max_drawdown_pct: float = 0.10
    max_daily_loss: float = 1000.0


class RiskManager:
    """
    Evaluates signals against risk constraints and dynamically sizes positions.
    """

    def __init__(self, profile: RiskProfile | None = None) -> None:
        self.profile = profile or RiskProfile()
        self.daily_pnl = 0.0
        self.open_positions_count = 0
        self.max_open_positions = 5
        self.circuit_breaker_active = False

    def update_pnl(self, daily_pnl: float) -> None:
        """Update daily P&L and check circuit breakers."""
        self.daily_pnl = daily_pnl
        if self.daily_pnl <= -self.profile.max_daily_loss:
            if not self.circuit_breaker_active:
                logger.critical("CIRCUIT BREAKER TRIGGERED: Daily loss limit exceeded.")
                self.circuit_breaker_active = True
        elif self.circuit_breaker_active and self.daily_pnl > -self.profile.max_daily_loss:
            logger.info("CIRCUIT BREAKER LIFTED: Daily P&L recovered above limit.")
            self.circuit_breaker_active = False

    def evaluate_signal(self, signal: "SignalEvent", portfolio_value: float) -> bool:
        """
        Evaluate if a signal is safe to execute based on risk parameters.
        Returns True if approved, False if rejected.
        """
        if self.circuit_breaker_active:
            logger.warning("Signal rejected: Circuit breaker active.")
            return False

        if self.open_positions_count >= self.max_open_positions:
            logger.warning("Signal rejected: Maximum open positions reached.")
            return False

        # If AI model assigned a very high risk score
        if signal.risk_score and signal.risk_score > 80.0:
            logger.warning("Signal rejected: AI Risk Score too high (%.1f).", signal.risk_score)
            return False

        # Confidence check
        if signal.confidence and signal.confidence < 50.0:
            logger.warning("Signal rejected: Confidence too low (%.1f).", signal.confidence)
            return False

        return True

    def calculate_position_size(
        self,
        signal: "SignalEvent",
        portfolio_value: float,
        current_price: float
    ) -> float:
        """
        Calculate dynamic position size based on volatility (Kelly Criterion lite).
        """
        if not self.evaluate_signal(signal, portfolio_value):
            return 0.0

        # Base risk is max position risk
        risk_amount = portfolio_value * self.profile.max_position_risk_pct
        
        # Scale down risk based on AI risk score
        risk_multiplier = 1.0
        if signal.risk_score:
            # If risk is 0, multiplier is 1. If risk is 80, multiplier is 0.2
            risk_multiplier = max(0.1, 1.0 - (signal.risk_score / 100.0))
            
        adjusted_risk_amount = risk_amount * risk_multiplier

        # Use stop loss to determine size if available
        if signal.stop_loss and signal.stop_loss > 0 and signal.suggested_price:
            stop_dist = abs(signal.suggested_price - signal.stop_loss)
            if stop_dist > 0:
                # Risk Amount = Position Size * Stop Distance
                position_size = adjusted_risk_amount / stop_dist
                return position_size

        # Fallback: simple % of portfolio based on confidence
        confidence_scaler = (signal.confidence or 50.0) / 100.0
        position_value = portfolio_value * self.profile.max_position_risk_pct * confidence_scaler
        
        return position_value / current_price if current_price > 0 else 0.0
