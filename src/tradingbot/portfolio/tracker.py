"""Portfolio tracker — real-time position and P&L tracking."""

from __future__ import annotations

import logging

from tradingbot.core.events import Event, FillEvent, SignalSide
from tradingbot.portfolio.models import PortfolioSnapshot, Position, Trade

logger = logging.getLogger(__name__)


class PortfolioTracker:
    """
    Real-time portfolio tracker.

    Maintains positions, calculates P&L, and records trade history.
    Processes FillEvents from the order manager.
    """

    def __init__(self, initial_cash: float = 100000.0, trade_repo=None) -> None:
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._trades: list[Trade] = []
        self._realized_pnl = 0.0
        self._trade_repo = trade_repo

    @property
    def cash(self) -> float:
        """Current cash balance."""
        return self._cash

    @property
    def positions(self) -> dict[str, Position]:
        """Current positions (symbol → Position)."""
        return self._positions.copy()

    @property
    def trades(self) -> list[Trade]:
        """Trade history."""
        return list(self._trades)

    @property
    def total_value(self) -> float:
        """Total portfolio value (cash + positions)."""
        positions_value = sum(p.market_value for p in self._positions.values())
        return self._cash + positions_value

    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized P&L across all positions."""
        return sum(p.unrealized_pnl for p in self._positions.values())

    @property
    def realized_pnl(self) -> float:
        """Total realized P&L from closed trades."""
        return self._realized_pnl

    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)."""
        return self._realized_pnl + self.unrealized_pnl

    def get_snapshot(self) -> PortfolioSnapshot:
        """Get a point-in-time snapshot of the portfolio."""
        positions_value = sum(p.market_value for p in self._positions.values())
        return PortfolioSnapshot(
            cash=self._cash,
            total_value=self.total_value,
            positions_value=positions_value,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self._realized_pnl,
            num_positions=len(self._positions),
            num_trades=len(self._trades),
        )

    async def on_fill(self, event: Event) -> None:
        """
        Process a fill event and update portfolio state.

        For BUY fills: opens or adds to a position, decreases cash.
        For SELL fills: reduces or closes a position, increases cash.
        """
        if not isinstance(event, FillEvent):
            return

        trade = Trade(
            symbol=event.symbol,
            side=event.side.value,
            quantity=event.quantity,
            price=event.fill_price,
            commission=event.commission,
            order_id=event.order_id,
            broker_order_id=event.broker_order_id,
            strategy_name=event.strategy_name,
            reason=event.reason,
            metadata=event.metadata,
        )
        self._trades.append(trade)

        if event.side == SignalSide.BUY:
            self._process_buy(event)
        elif event.side == SignalSide.SELL:
            self._process_sell(event, trade)

        logger.info(
            "Portfolio updated: cash=%.2f, positions=%d, total_value=%.2f",
            self._cash,
            len(self._positions),
            self.total_value,
        )

        if self._trade_repo:
            import json
            await self._trade_repo.save_trade(
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                price=trade.price,
                commission=trade.commission,
                order_id=trade.order_id,
                broker_order_id=trade.broker_order_id,
                strategy_name=trade.strategy_name,
                reason=trade.reason,
                pnl=trade.realized_pnl,
                metadata_json=json.dumps(trade.metadata) if trade.metadata else "{}",
            )

    def _process_buy(self, fill: FillEvent) -> None:
        """Process a buy fill."""
        cost = fill.fill_price * fill.quantity + fill.commission
        self._cash -= cost

        if fill.symbol in self._positions:
            # Average into existing position
            pos = self._positions[fill.symbol]
            total_qty = pos.quantity + fill.quantity
            total_cost = pos.cost_basis + (fill.fill_price * fill.quantity)
            pos.avg_entry_price = total_cost / total_qty if total_qty > 0 else 0
            pos.quantity = total_qty
            pos.current_price = fill.fill_price
        else:
            # Open new position
            self._positions[fill.symbol] = Position(
                symbol=fill.symbol,
                quantity=fill.quantity,
                avg_entry_price=fill.fill_price,
                current_price=fill.fill_price,
            )

    def _process_sell(self, fill: FillEvent, trade: Trade) -> None:
        """Process a sell fill."""
        proceeds = fill.fill_price * fill.quantity - fill.commission
        self._cash += proceeds

        if fill.symbol in self._positions:
            pos = self._positions[fill.symbol]
            # Calculate realized P&L for the sold portion
            pnl = (fill.fill_price - pos.avg_entry_price) * fill.quantity - fill.commission
            self._realized_pnl += pnl
            trade.realized_pnl = pnl

            pos.quantity -= fill.quantity
            pos.current_price = fill.fill_price

            # Remove position if fully closed
            if pos.quantity <= 0:
                del self._positions[fill.symbol]
        else:
            # Short selling (record negative position)
            self._positions[fill.symbol] = Position(
                symbol=fill.symbol,
                quantity=-fill.quantity,
                avg_entry_price=fill.fill_price,
                current_price=fill.fill_price,
            )

    def update_price(self, symbol: str, price: float) -> None:
        """Update the current price for a position."""
        if symbol in self._positions:
            self._positions[symbol].current_price = price
