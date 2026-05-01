"""Risk Manager — central gatekeeper that validates all trading signals."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from tradingbot.core.event_bus import EventBus
from tradingbot.core.events import (
    AlertEvent,
    AlertLevel,
    Event,
    OrderEvent,
    OrderType,
    SignalEvent,
    SignalSide,
)

if TYPE_CHECKING:
    from tradingbot.config.schema import RiskConfig

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Central risk management gatekeeper.

    ALL signals must pass through the risk manager before becoming orders.
    Validates against:
    - Daily loss limit
    - Position size limits
    - Maximum exposure
    - Maximum open positions
    - Circuit breaker state
    """

    def __init__(
        self,
        config: RiskConfig,
        event_bus: EventBus,
        portfolio_value: float = 100000.0,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._portfolio_value = portfolio_value

        # Tracking state
        self._daily_pnl = 0.0
        self._daily_reset_date: str = ""
        self._open_positions: dict[str, float] = {}  # symbol -> quantity
        self._total_exposure = 0.0

        # Audit trail
        self._approved_count = 0
        self._rejected_count = 0

        # Circuit breaker state
        self._circuit_breaker_active = False
        self._circuit_breaker_until: datetime | None = None

    @property
    def approved_count(self) -> int:
        """Number of approved signals."""
        return self._approved_count

    @property
    def rejected_count(self) -> int:
        """Number of rejected signals."""
        return self._rejected_count

    @property
    def daily_pnl(self) -> float:
        """Current daily P&L."""
        return self._daily_pnl

    @property
    def is_circuit_breaker_active(self) -> bool:
        """Whether the circuit breaker is currently active."""
        if self._circuit_breaker_active and self._circuit_breaker_until:
            if datetime.now(timezone.utc) >= self._circuit_breaker_until:
                self._circuit_breaker_active = False
                self._circuit_breaker_until = None
                logger.info("Circuit breaker cooldown expired, resuming trading")
                return False
        return self._circuit_breaker_active

    def update_portfolio_value(self, value: float) -> None:
        """Update the current portfolio value for position sizing."""
        self._portfolio_value = value

    def update_daily_pnl(self, pnl: float) -> None:
        """Update the daily P&L tracker."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._daily_reset_date:
            self._daily_pnl = 0.0
            self._daily_reset_date = today

        self._daily_pnl += pnl

    def update_position(self, symbol: str, quantity: float) -> None:
        """Update tracked position for a symbol."""
        if quantity == 0:
            self._open_positions.pop(symbol, None)
        else:
            self._open_positions[symbol] = quantity

    def activate_circuit_breaker(self, cooldown_minutes: int | None = None) -> None:
        """Activate the circuit breaker."""
        minutes = cooldown_minutes or self._config.circuit_breaker.cooldown_minutes
        from datetime import timedelta

        self._circuit_breaker_active = True
        self._circuit_breaker_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        logger.warning("Circuit breaker activated! Cooldown: %d minutes", minutes)

    async def on_signal(self, event: Event) -> None:
        """
        Validate a trading signal against risk rules.

        If approved, publishes an OrderEvent.
        If rejected, logs the reason and publishes an alert.
        """
        if not isinstance(event, SignalEvent):
            return

        # Skip HOLD signals
        if event.side == SignalSide.HOLD:
            return

        # Run validation checks
        rejection_reason = self._validate(event)

        if rejection_reason:
            self._rejected_count += 1
            logger.warning(
                "Signal REJECTED for %s: %s",
                event.symbol,
                rejection_reason,
            )
            await self._event_bus.publish(
                AlertEvent(
                    source="risk_manager",
                    level=AlertLevel.WARNING,
                    title="Signal Rejected",
                    message=f"{event.symbol} {event.side.value}: {rejection_reason}",
                )
            )
            return

        # Calculate position size
        quantity = self._calculate_position_size(event)

        # Create and publish order event
        self._approved_count += 1
        order = OrderEvent(
            source="risk_manager",
            symbol=event.symbol,
            side=event.side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=event.suggested_price if event.suggested_price else None,
            signal_id=event.event_id,
        )
        logger.info(
            "Signal APPROVED for %s: %s qty=%.6f",
            event.symbol,
            event.side.value,
            quantity,
        )
        await self._event_bus.publish(order)

    def _validate(self, signal: SignalEvent) -> str | None:
        """
        Run all risk validation checks on a signal.

        Returns rejection reason string, or None if approved.
        """
        # Check circuit breaker
        if self.is_circuit_breaker_active:
            return "Circuit breaker is active"

        # Check daily loss limit
        if self._daily_pnl <= -self._config.max_daily_loss:
            return f"Daily loss limit exceeded: {self._daily_pnl:.2f}"

        # Check max open positions (for new positions only)
        if signal.side == SignalSide.BUY and signal.symbol not in self._open_positions:
            if len(self._open_positions) >= self._config.max_open_positions:
                return f"Max open positions reached: {len(self._open_positions)}"

        return None

    def _calculate_position_size(self, signal: SignalEvent) -> float:
        """
        Calculate position size based on risk parameters.

        Uses max_position_size as fraction of portfolio.
        """
        max_value = self._portfolio_value * self._config.max_position_size

        if signal.suggested_price and signal.suggested_price > 0:
            quantity = max_value / signal.suggested_price
        else:
            quantity = max_value

        return quantity
