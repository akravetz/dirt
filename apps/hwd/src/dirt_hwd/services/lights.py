"""Lights control via Kasa smart plug.

Binary schedule drive: the plug is forced to match the grow's configured
wall-clock window (the current scoped ``growrun`` lights fields, interpreted
in ``growrun.timezone``). Every tick we reconcile plug state
to the schedule's boolean — no hysteresis, no sensor feedback, no margin.
On a cold start the first tick reconciles whatever the plug was left in
(e.g. a pre-existing analog timer position) to the schedule.

Replaces the unreliable analog push-pin 24-hour timer.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from kasa import Credentials, Device, Discover

from dirt_shared.config import LightsConfig
from dirt_shared.observability import log_event
from dirt_shared.services.grow_state import GrowStateService

logger = logging.getLogger(__name__)

STREAM = "lights"


async def _safe_disconnect(plug: Device | None) -> None:
    if plug is None:
        return
    with contextlib.suppress(Exception):
        await plug.disconnect()


class LightsLoopService:
    """Schedule-driven lights plug reconciler. Constructor-inject everything.

    Constructor takes:
      - ``config``: LightsConfig (kasa creds + plug host + poll interval)
      - ``grow``: GrowStateService for the lights schedule + timezone

    Run via ``await loop_svc.run(stop_event)`` from the lifespan.
    """

    def __init__(
        self,
        config: LightsConfig,
        *,
        grow: GrowStateService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._config = config
        self._grow = grow
        self._clock = clock

    async def run(self, stop_event: asyncio.Event) -> None:
        cfg = self._config
        if not cfg.kasa_username or not cfg.kasa_password:
            logger.warning(
                "KASA_USERNAME/KASA_PASSWORD unset — lights loop disabled",
            )
            return

        creds = Credentials(cfg.kasa_username, cfg.kasa_password)
        host = cfg.kasa_lights_host
        interval = cfg.poll_interval

        logger.info(
            "lights loop starting: host=%s interval=%ds",
            host,
            interval,
        )

        plug: Device | None = None

        while not stop_event.is_set():
            try:
                if plug is None:
                    plug = await Discover.discover_single(host, credentials=creds)
                    if plug is None:
                        raise RuntimeError(
                            f"kasa discover_single({host}) returned None",
                        )

                await plug.update()
                is_on = bool(plug.is_on)

                lights = await self._grow.lights_state()
                target = lights.on

                if target != is_on:
                    if target:
                        await plug.turn_on()
                    else:
                        await plug.turn_off()
                    log_event(
                        STREAM,
                        "state_change",
                        new_state="on" if target else "off",
                        reason="scheduled_on" if target else "scheduled_off",
                        minutes_until_off=round(lights.minutes_until_off, 1),
                        minutes_until_on=round(lights.minutes_until_on, 1),
                    )
                    logger.info(
                        "lights → %s (minutes_until_off=%.1f minutes_until_on=%.1f)",
                        "on" if target else "off",
                        lights.minutes_until_off,
                        lights.minutes_until_on,
                    )

            except Exception as exc:
                logger.exception(
                    "lights loop error — dropping plug connection",
                )
                await _safe_disconnect(plug)
                plug = None
                log_event(
                    STREAM,
                    "error",
                    error_type=type(exc).__name__,
                    error=repr(exc),
                )

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=interval)

        await _safe_disconnect(plug)
        logger.info("lights loop stopped")
