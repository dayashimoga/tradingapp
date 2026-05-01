"""Repository — data access layer for persistent storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from tradingbot.persistence.database import Database
from tradingbot.persistence.models import AlertRecord, PortfolioHistory, TradeRecord

logger = logging.getLogger(__name__)


class TradeRepository:
    """Data access layer for trade records."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def save_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        order_id: str = "",
        broker_order_id: str = "",
        strategy_name: str = "",
    ) -> int:
        """Save a trade record and return its ID."""
        async with await self._db.get_session() as session:
            record = TradeRecord(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                commission=commission,
                order_id=order_id,
                broker_order_id=broker_order_id,
                strategy_name=strategy_name,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record.id  # type: ignore[return-value]

    async def get_trades(self, symbol: str | None = None, limit: int = 100) -> list[TradeRecord]:
        """Retrieve trade records, optionally filtered by symbol."""
        async with await self._db.get_session() as session:
            query = select(TradeRecord).order_by(TradeRecord.timestamp.desc()).limit(limit)
            if symbol:
                query = query.where(TradeRecord.symbol == symbol)
            result = await session.execute(query)
            return list(result.scalars().all())


class PortfolioHistoryRepository:
    """Data access layer for portfolio history snapshots."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def save_snapshot(
        self,
        cash: float,
        total_value: float,
        positions_value: float = 0.0,
        unrealized_pnl: float = 0.0,
        realized_pnl: float = 0.0,
        num_positions: int = 0,
    ) -> int:
        """Save a portfolio snapshot and return its ID."""
        async with await self._db.get_session() as session:
            record = PortfolioHistory(
                cash=cash,
                total_value=total_value,
                positions_value=positions_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                num_positions=num_positions,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record.id  # type: ignore[return-value]

    async def get_history(self, limit: int = 1000) -> list[PortfolioHistory]:
        """Retrieve portfolio history snapshots."""
        async with await self._db.get_session() as session:
            query = (
                select(PortfolioHistory)
                .order_by(PortfolioHistory.timestamp.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            return list(result.scalars().all())
