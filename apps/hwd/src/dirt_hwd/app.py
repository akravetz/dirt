"""dirt-hwd composition root.

Owns the ESP32 ingest endpoint and four background services that touch
hardware exclusively (capture, archive, humidifier loop, serial reader).
``create_app`` wires them into the lifespan; tests construct an app with
``background_services=[]`` to skip the hardware loops entirely.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from dirt_hwd.api.ingest import router as ingest_router
from dirt_hwd.services.archive import ArchiveService
from dirt_hwd.services.humidifier import HumidifierLoopService
from dirt_hwd.services.serial_reader import SerialReaderService
from dirt_shared.app_wiring import build_core_services
from dirt_shared.config import Settings
from dirt_shared.db import ping
from dirt_shared.services.capture import CaptureService


class BackgroundService(Protocol):
    """Anything wired into the lifespan as a long-running task.

    Each service exposes ``async def run(stop_event)`` and is shut down
    via ``stop_event.set()`` in the lifespan's finally block.
    """

    async def run(self, stop_event: asyncio.Event) -> None: ...


def _default_background_services(
    *,
    engine: AsyncEngine,
    settings: Settings,
    core,
) -> list[BackgroundService]:
    """Build the four production background services from settings."""
    return [
        CaptureService(engine, settings.capture(), clock=core.clock),
        ArchiveService(settings.archive(), clock=core.clock),
        HumidifierLoopService(
            settings.humidifier(),
            readings=core.readings,
            grow=core.grow,
            clock=core.clock,
        ),
        SerialReaderService(
            settings.serial(),
            readings=core.readings,
        ),
    ]


def create_app(
    *,
    engine: AsyncEngine | None = None,
    settings: Settings | None = None,
    background_services: list[BackgroundService] | None = None,
) -> FastAPI:
    """Compose the dirt-hwd FastAPI app.

    Args:
        engine: AsyncEngine for DB-backed services. Defaults to the engine
            built from Settings (production path).
        settings: Settings instance. Defaults to ``Settings()``.
        background_services: Override which background services run.
            Pass ``[]`` to disable all loops (the test path).
            Pass ``None`` to wire the production default four.
    """
    core = build_core_services(engine=engine, settings=settings)
    engine = core.engine
    settings = core.settings

    services = (
        background_services
        if background_services is not None
        else _default_background_services(
            engine=engine, settings=settings, core=core,
        )
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await ping(engine)
        stop_event = asyncio.Event()
        tasks = [
            asyncio.create_task(svc.run(stop_event)) for svc in services
        ]
        try:
            yield
        finally:
            stop_event.set()
            for t in tasks:
                await t

    app = FastAPI(title="Dirt HWD", lifespan=lifespan)
    app.state.engine = engine
    app.state.settings = settings
    app.state.readings = core.readings
    app.state.grow = core.grow
    app.state.snapshots = core.snapshots
    app.state.plant_detail = core.plant_detail
    app.state.plants = core.plants
    app.state.humidifier_state = core.humidifier_state
    app.state.system_status = core.system_status
    app.state.background_services = services

    app.include_router(ingest_router)
    return app


# Module-level instance for `uvicorn dirt_hwd.app:app` (existing systemd unit).
app = create_app()
