"""Shared composition-root helpers.

``dirt_hwd.app.create_app`` and the voice channel need the same plumbing:
build an ``AsyncEngine``, construct ``Settings``, and wire the DB-backed
services they share. That work lives here so the composition roots don't
drift apart.

Background loops are *not* built here — they're hwd-specific and depend
on hardware config. They get assembled in ``dirt_hwd.app.create_app``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from dirt_shared.config import Settings
from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.system_status import SystemStatusService


@dataclass(frozen=True)
class CoreServices:
    """Bundle of constructor-injected services shared across process roots."""

    engine: AsyncEngine
    settings: Settings
    clock: Callable[[], datetime]
    readings: ReadingsService
    grow: GrowStateService
    system_status: SystemStatusService


def build_core_services(
    *,
    engine: AsyncEngine | None = None,
    settings: Settings | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CoreServices:
    """Construct ``Settings`` + engine if not provided, then wire shared
    DB-backed services. Composition roots call this once at process start.

    ``clock`` is the single source of "what time is it now" for every
    service in the bundle. Production composition roots use the default
    (``datetime.now(UTC)``); tests pass a frozen clock so the whole
    service graph reads from one deterministic reference."""
    if settings is None:
        settings = Settings()
    if engine is None:
        assert settings.database_url is not None  # noqa: S101 (type narrow)
        engine = create_async_engine(settings.database_url)

    readings = ReadingsService(engine, clock=clock)
    grow = GrowStateService(engine, clock=clock)
    system_status = SystemStatusService(engine, clock=clock)

    return CoreServices(
        engine=engine,
        settings=settings,
        clock=clock,
        readings=readings,
        grow=grow,
        system_status=system_status,
    )
