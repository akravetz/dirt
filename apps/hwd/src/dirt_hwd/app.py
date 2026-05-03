"""dirt-hwd composition root.

Owns the ESP32 ingest endpoint and the background services that touch
hardware exclusively (capture, archive, humidifier loop, device watchdog).
``create_app`` wires them into the lifespan; tests construct an app with
``background_services=[]`` to skip the hardware loops entirely.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from dirt_hwd.api.ingest import router as ingest_router
from dirt_hwd.services.archive import ArchiveService
from dirt_hwd.services.device_watchdog import (
    DeviceWatchdogConfig,
    DeviceWatchdogService,
)
from dirt_hwd.services.fan_controller import FanTrimLoopService
from dirt_hwd.services.humidifier import HumidifierLoopService
from dirt_hwd.services.lights import LightsLoopService
from dirt_hwd.services.metric_freshness import (
    MetricFreshnessConfig,
    MetricFreshnessService,
)
from dirt_hwd.services.sensor_quality import SensorQualityConfig, SensorQualityService
from dirt_hwd.supervise import supervise
from dirt_shared.app_wiring import build_core_services
from dirt_shared.config import Settings
from dirt_shared.db import ping
from dirt_shared.services.capture import CaptureService

logger = logging.getLogger(__name__)


class BackgroundService(Protocol):
    """Anything wired into the lifespan as a long-running task.

    Each service exposes ``async def run(stop_event)`` and is shut down
    via ``stop_event.set()`` in the lifespan's finally block.
    """

    async def run(self, stop_event: asyncio.Event) -> None: ...


async def _crash_watchdog(
    tasks: list[asyncio.Task[None]],
    stop_event: asyncio.Event,
) -> None:
    """Turn a supervised-task budget exhaustion into a graceful process exit.

    When a ``supervise``-wrapped task re-raises (budget blown), asyncio
    stores the exception on the task without disturbing the other tasks.
    The process keeps running degraded. This watchdog bridges that gap:
    it waits for the first crash, logs it, sets ``stop_event`` to unwind
    siblings, then raises SIGTERM so uvicorn shuts the app down cleanly
    and systemd's ``Restart=on-failure`` (bounded by ``StartLimitBurst``)
    can relaunch from a fresh process state.
    """
    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    for t in done:
        exc = t.exception()
        if exc is None:
            continue
        logger.error(
            "supervised task %s exhausted its budget — triggering shutdown",
            t.get_name(),
            exc_info=exc,
        )
        stop_event.set()
        signal.raise_signal(signal.SIGTERM)
        return


def _default_background_services(
    *,
    engine: AsyncEngine,
    settings: Settings,
    core,
) -> list[BackgroundService]:
    """Build the production background services from settings."""
    return [
        CaptureService(engine, settings.capture(), clock=core.clock),
        ArchiveService(settings.archive(), clock=core.clock),
        HumidifierLoopService(
            settings.humidifier(),
            readings=core.readings,
            grow=core.grow,
            clock=core.clock,
        ),
        LightsLoopService(
            settings.lights(),
            grow=core.grow,
            clock=core.clock,
        ),
        FanTrimLoopService(
            settings.fan_trim(),
            readings=core.readings,
            grow=core.grow,
            clock=core.clock,
        ),
        DeviceWatchdogService(
            DeviceWatchdogConfig(
                poll_interval=settings.device_watchdog_poll_interval,
                state_path=settings.data_dir
                / "logs"
                / "device_watchdog"
                / "state.json",
                telegram_bot_token=settings.telegram_bot_token,
                telegram_chat_id=settings.telegram_allowed_user_id,
            ),
            system_status=core.system_status,
            clock=core.clock,
        ),
        MetricFreshnessService(
            MetricFreshnessConfig(
                poll_interval=settings.metric_freshness_poll_interval,
                stale_after_s=settings.metric_freshness_stale_after_s,
                state_path=settings.data_dir
                / "logs"
                / "metric_freshness"
                / "state.json",
                telegram_bot_token=settings.telegram_bot_token,
                telegram_chat_id=settings.telegram_allowed_user_id,
            ),
            readings=core.readings,
            clock=core.clock,
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
            engine=engine,
            settings=settings,
            core=core,
        )
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await ping(engine)
        stop_event = asyncio.Event()
        tasks = [
            asyncio.create_task(
                supervise(type(svc).__name__, svc.run, stop_event),
                name=type(svc).__name__,
            )
            for svc in services
        ]
        # Tests pass background_services=[]; asyncio.wait([]) would raise.
        watchdog = (
            asyncio.create_task(
                _crash_watchdog(tasks, stop_event),
                name="crash_watchdog",
            )
            if tasks
            else None
        )
        try:
            yield
        finally:
            stop_event.set()
            if watchdog is not None:
                watchdog.cancel()
            await asyncio.gather(
                *([watchdog] if watchdog is not None else []),
                *tasks,
                return_exceptions=True,
            )

    app = FastAPI(title="Dirt HWD", lifespan=lifespan)
    app.state.engine = engine
    app.state.settings = settings
    app.state.readings = core.readings
    app.state.grow = core.grow
    app.state.snapshots = core.snapshots
    app.state.plant_detail = core.plant_detail
    app.state.plants = core.plants
    app.state.system_status = core.system_status
    app.state.sensor_quality = SensorQualityService(
        SensorQualityConfig(
            state_path=settings.data_dir / "logs" / "sensor_quality" / "state.json",
            telegram_bot_token=settings.telegram_bot_token,
            telegram_chat_id=settings.telegram_allowed_user_id,
        )
    )
    app.state.background_services = services

    app.include_router(ingest_router)
    return app


# Module-level instance for `uvicorn dirt_hwd.app:app` (existing systemd unit).
app = create_app()
