"""Shared composition-root helpers.

Both ``dirt_web.app.create_app`` and ``dirt_hwd.app.create_app`` (and the
voice channel's startup) need the same plumbing: build an ``AsyncEngine``,
construct a ``Settings``, and wire all of the DB-backed service classes.
That work lives here so the per-app factories don't drift apart.

Background loops are *not* built here — they're hwd-specific and depend
on hardware config that the web app shouldn't touch. They get assembled
in ``dirt_hwd.app.create_app``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from dirt_shared.config import Settings
from dirt_shared.services.commands import CommandService
from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.plant_detail import PlantDetailService
from dirt_shared.services.plants import PlantsService
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.scope_catalog import ScopeCatalogService
from dirt_shared.services.snapshots import SnapshotsService
from dirt_shared.services.system_status import SystemStatusService


@dataclass(frozen=True)
class CoreServices:
    """Bundle of constructor-injected services shared across both web + hwd."""

    engine: AsyncEngine
    settings: Settings
    clock: Callable[[], datetime]
    snapshots: SnapshotsService
    readings: ReadingsService
    grow: GrowStateService
    plant_detail: PlantDetailService
    plants: PlantsService
    system_status: SystemStatusService
    commands: CommandService
    scope_catalog: ScopeCatalogService


def build_core_services(
    *,
    engine: AsyncEngine | None = None,
    settings: Settings | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CoreServices:
    """Construct ``Settings`` + engine if not provided, then wire every
    DB-backed service. Composition roots call this once at app start and
    pass the result onto ``app.state`` (or hold it directly, for non-FastAPI
    consumers like ``dirt_voice``).

    ``clock`` is the single source of "what time is it now" for every
    service in the bundle. Production composition roots use the default
    (``datetime.now(UTC)``); tests pass a frozen clock so the whole
    service graph reads from one deterministic reference."""
    if settings is None:
        settings = Settings()
    if engine is None:
        assert settings.database_url is not None  # noqa: S101 (type narrow)
        engine = create_async_engine(settings.database_url)

    snapshots = SnapshotsService(engine)
    readings = ReadingsService(engine, clock=clock)
    grow = GrowStateService(engine, clock=clock)
    plant_detail = PlantDetailService()
    plants = PlantsService(engine, plant_detail=plant_detail, clock=clock)
    system_status = SystemStatusService(engine, clock=clock)
    commands = CommandService(engine, clock=clock)
    scope_catalog = ScopeCatalogService(engine)

    return CoreServices(
        engine=engine,
        settings=settings,
        clock=clock,
        snapshots=snapshots,
        readings=readings,
        grow=grow,
        plant_detail=plant_detail,
        plants=plants,
        system_status=system_status,
        commands=commands,
        scope_catalog=scope_catalog,
    )
