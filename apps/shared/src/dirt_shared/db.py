"""Database connection + session factory.

Schema + migrations are owned by Atlas (see ADR-006, ``atlas.hcl``,
``migrations/``). This module only opens a connection pool and hands out
sessions. ``init_db`` is a connection health check; app boot no longer
runs DDL.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import settings

# Side-effect import: populates SQLModel.metadata with all table classes.
# Required by the Atlas external-schema loader and by any session-level
# code that resolves SQLModel references through the global metadata.
import dirt_shared.models  # noqa: F401

engine = create_async_engine(settings.database_url)


async def get_session():
    async with AsyncSession(engine) as session:
        yield session


async def init_db() -> None:
    """Verify the DB is reachable. DDL is owned by Atlas — see migrations/."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
