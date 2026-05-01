"""Database models — SQLAlchemy ORM models for persistent storage."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class TradeRecord(Base):
    """Persisted trade record."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    order_id = Column(String(100), index=True)
    broker_order_id = Column(String(100))
    strategy_name = Column(String(100))
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, default="")


class PositionRecord(Base):
    """Persisted position record."""

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False, unique=True, index=True)
    quantity = Column(Float, nullable=False)
    avg_entry_price = Column(Float, nullable=False)
    current_price = Column(Float, default=0.0)
    opened_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PortfolioHistory(Base):
    """Historical portfolio snapshots for charting."""

    __tablename__ = "portfolio_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    cash = Column(Float, nullable=False)
    total_value = Column(Float, nullable=False)
    positions_value = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    num_positions = Column(Integer, default=0)


class AlertRecord(Base):
    """Persisted alert/notification record."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    level = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, default="")
    channel = Column(String(50), default="")
    delivered = Column(Integer, default=0)  # 0=pending, 1=delivered
