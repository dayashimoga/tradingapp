"""Position sizing algorithms."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PositionSizer:
    """
    Position sizing calculator.

    Supports multiple sizing methods:
    - Fixed fraction of portfolio
    - Kelly criterion
    - Fixed dollar amount
    """

    @staticmethod
    def fixed_fraction(
        portfolio_value: float,
        fraction: float,
        price: float,
    ) -> float:
        """
        Calculate position size as a fixed fraction of portfolio.

        Args:
            portfolio_value: Total portfolio value.
            fraction: Fraction of portfolio to allocate (0.0 - 1.0).
            price: Current asset price.

        Returns:
            Quantity of asset to trade.
        """
        if price <= 0:
            return 0.0
        if fraction <= 0 or fraction > 1:
            return 0.0

        allocation = portfolio_value * fraction
        quantity = allocation / price
        return quantity

    @staticmethod
    def kelly_criterion(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        portfolio_value: float,
        price: float,
        max_fraction: float = 0.25,
    ) -> float:
        """
        Calculate position size using the Kelly Criterion.

        Kelly % = W - [(1-W) / R]
        where W = win probability, R = win/loss ratio

        Args:
            win_rate: Historical win probability (0.0 - 1.0).
            avg_win: Average winning trade amount.
            avg_loss: Average losing trade amount (positive number).
            portfolio_value: Total portfolio value.
            price: Current asset price.
            max_fraction: Maximum fraction cap (Kelly is often aggressive).

        Returns:
            Quantity of asset to trade.
        """
        if avg_loss <= 0 or price <= 0:
            return 0.0
        if win_rate <= 0 or win_rate >= 1:
            return 0.0

        win_loss_ratio = avg_win / avg_loss
        kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)

        # Kelly can be negative (don't trade) or very large (cap it)
        kelly_pct = max(0.0, min(kelly_pct, max_fraction))

        allocation = portfolio_value * kelly_pct
        quantity = allocation / price
        return quantity

    @staticmethod
    def fixed_amount(
        amount: float,
        price: float,
    ) -> float:
        """
        Calculate position size for a fixed dollar amount.

        Args:
            amount: Dollar amount to invest.
            price: Current asset price.

        Returns:
            Quantity of asset to trade.
        """
        if price <= 0 or amount <= 0:
            return 0.0
        return amount / price

    @staticmethod
    def risk_based(
        portfolio_value: float,
        risk_per_trade: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:
        """
        Calculate position size based on risk per trade and stop loss distance.

        Args:
            portfolio_value: Total portfolio value.
            risk_per_trade: Fraction of portfolio to risk (e.g., 0.01 = 1%).
            entry_price: Expected entry price.
            stop_loss_price: Stop loss price.

        Returns:
            Quantity of asset to trade.
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0

        risk_amount = portfolio_value * risk_per_trade
        risk_per_unit = abs(entry_price - stop_loss_price)

        if risk_per_unit <= 0:
            return 0.0

        quantity = risk_amount / risk_per_unit
        return quantity
