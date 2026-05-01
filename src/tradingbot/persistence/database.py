"""Database setup — async SQLAlchemy engine and session management."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tradingbot.persistence.models import Base

logger = logging.getLogger(__name__)


class Database:
    """
    Async database connection manager.

    Uses SQLAlchemy async engine with aiosqlite for SQLite.
    """

    def __init__(self, url: str = "sqlite+aiosqlite:///./tradingbot.db", echo: bool = False):
        self._url = url
        self._echo = echo
        self._engine = create_async_engine(url, echo=echo)
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def initialize(self) -> None:
        """Create all tables if they don't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized: %s", self._url)

    async def get_session(self) -> AsyncSession:
        """Get a new async database session."""
        return self._session_factory()

    async def close(self) -> None:
        """Close the database engine."""
        await self._engine.dispose()
        logger.info("Database connection closed")
