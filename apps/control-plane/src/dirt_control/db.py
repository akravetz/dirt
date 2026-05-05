from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from dirt_control.settings import CloudSettings, normalize_async_database_url


def create_engine(settings: CloudSettings) -> AsyncEngine:
    return create_async_engine(normalize_async_database_url(settings.database_url))


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def ping(engine: AsyncEngine) -> None:
    """Verify connectivity only. Atlas owns all cloud DDL."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def session_scope(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session
