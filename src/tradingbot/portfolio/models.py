"""Portfolio data models — Position, Trade, and Portfolio value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Position:
    """Represents an open position in a single asset."""

    symbol: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def market_value(self) -> float:
        """Current market value of the position."""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """Total cost basis of the position."""
        return self.quantity * self.avg_entry_price

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L."""
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as a percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100

    @property
    def is_long(self) -> bool:
        """Whether this is a long position."""
        return self.quantity > 0


@dataclass
class Trade:
    """Represents a completed trade."""

    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    commission: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    order_id: str = ""
    broker_order_id: str = ""

    @property
    def net_value(self) -> float:
        """Net value of the trade after commission."""
        gross = self.quantity * self.price
        if self.side == "buy":
            return -(gross + self.commission)
        return gross - self.commission


@dataclass
class PortfolioSnapshot:
    """Point-in-time snapshot of portfolio state."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    cash: float = 0.0
    total_value: float = 0.0
    positions_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    num_positions: int = 0
    num_trades: int = 0
