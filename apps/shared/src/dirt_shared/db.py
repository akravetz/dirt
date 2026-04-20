"""Database helpers — engine factory + session helper + health-check ping.

Schema + migrations are owned by Atlas (see ADR-006, ``atlas.hcl``,
``migrations/``). This module hands out engines and sessions; it does
not own a module-level singleton (singleton-retirement, 2026-04-19).

Composition roots (``dirt_web.app.create_app``, ``dirt_hwd.app.create_app``,
``dirt_voice`` startup) call ``build_core_services`` from
``dirt_shared.app_wiring`` to construct an engine once per process.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Side-effect import: populates SQLModel.metadata with all table classes.
# Required by the Atlas external-schema loader and by any session-level
# code that resolves SQLModel references through the global metadata.
import dirt_shared.models  # noqa: F401


async def ping(engine: AsyncEngine) -> None:
    """Verify the DB is reachable. DDL is owned by Atlas — see migrations/."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
