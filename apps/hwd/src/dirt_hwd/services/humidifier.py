"""Humidifier control via Kasa EP10 smart plug.

Bang-bang hysteresis on tent VPD against the stage-dynamic upper band from
``GrowStateService.current_targets()``, with lights-schedule feedforward.

The humidifier is a single-direction actuator (adds moisture → drops VPD),
so we target the band's upper edge: kick on when VPD rises above it, kick
off once it falls back below by ``vpd_deadband_kpa``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from kasa import Credentials, Device, Discover

from dirt_shared.config import HumidifierConfig
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.observability import log_event
from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.readings import ReadingsService

logger = logging.getLogger(__name__)

STREAM = "humidifier"


async def _safe_disconnect(plug: Device | None) -> None:
    if plug is None:
        return
    with contextlib.suppress(Exception):
        await plug.disconnect()


class HumidifierLoopService:
    """VPD-targeting humidifier control loop. Constructor-inject everything.

    Constructor takes:
      - ``config``: HumidifierConfig (kasa creds + VPD bands + intervals)
      - ``readings``: ReadingsService for VPD reads + state recording
      - ``grow``: GrowStateService for stage-dynamic band + lights schedule

    Run via ``await loop_svc.run(stop_event)`` from the lifespan.
    """

    def __init__(
        self,
        config: HumidifierConfig,
        *,
        readings: ReadingsService,
        grow: GrowStateService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._config = config
        self._readings = readings
        self._grow = grow
        self._clock = clock

    async def _record(self, on: bool) -> None:
        await self._readings.ingest_reading(
            SensorLocation.TENT,
            {"humidifier_on": 1.0 if on else 0.0},
            source=SensorSource.KASA,
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        cfg = self._config
        if not cfg.kasa_username or not cfg.kasa_password:
            logger.warning(
                "KASA_USERNAME/KASA_PASSWORD unset — humidifier loop disabled",
            )
            return

        creds = Credentials(cfg.kasa_username, cfg.kasa_password)
        host = cfg.kasa_humidifier_host
        deadband = cfg.vpd_deadband_kpa
        interval = cfg.poll_interval
        stale_s = cfg.failsafe_stale_seconds
        margin_minutes = cfg.lights_off_prep_minutes

        logger.info(
            "humidifier loop starting: host=%s deadband=%.2fkPa interval=%ds "
            "lights_margin=%dmin",
            host, deadband, interval, margin_minutes,
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

                stage = await self._grow.current_stage()
                lights = await self._grow.lights_state()
                vpd_lo, vpd_hi = (
                    await self._grow.current_targets()
                )["vpd_kpa"]
                turn_on_above = vpd_hi
                turn_off_below = vpd_hi - deadband

                # Humidifier-allowed window: from `lights_on - margin` through
                # `lights_off - margin`. Outside this window we force OFF —
                # design call (2026-04-19): the humidifier shouldn't run during
                # the dark period, since cool air drives natural condensation
                # and adding mist creates damping-off risk. Forces off across
                # the prep ramp-down before lights-off and stays off until
                # the ramp-up before lights-on.
                allowed = (
                    (lights.on and lights.minutes_until_off >= margin_minutes)
                    or (
                        not lights.on
                        and lights.minutes_until_on <= margin_minutes
                    )
                )

                reading = await self._readings.get_latest_reading("vpd_kpa")
                now = self._clock()
                vpd: float | None = reading.value if reading else None
                age = (
                    (now - reading.ts).total_seconds()
                    if reading is not None
                    else None
                )

                new_state = is_on
                reason: str | None = None

                if vpd is None or age is None or age > stale_s:
                    if is_on:
                        new_state = False
                        reason = "failsafe_stale_sensor"
                elif not allowed:
                    if is_on:
                        new_state = False
                        reason = "outside_lights_window"
                elif vpd > turn_on_above and not is_on:
                    new_state = True
                    reason = "vpd_above_upper_band"
                elif vpd < turn_off_below and is_on:
                    new_state = False
                    reason = "vpd_below_upper_band"

                if new_state != is_on:
                    if new_state:
                        await plug.turn_on()
                    else:
                        await plug.turn_off()
                    is_on = new_state
                    log_event(
                        STREAM,
                        "state_change",
                        new_state="on" if new_state else "off",
                        reason=reason,
                        vpd=vpd,
                        vpd_age_s=age,
                        stage=stage,
                        upper_band_kpa=vpd_hi,
                        lower_band_kpa=vpd_lo,
                        lights_on=lights.on,
                        minutes_until_off=round(lights.minutes_until_off, 1),
                        minutes_until_on=round(lights.minutes_until_on, 1),
                        allowed=allowed,
                    )
                    logger.info(
                        "humidifier → %s (reason=%s vpd=%s stage=%s "
                        "band=[%.2f,%.2f] lights_on=%s allowed=%s)",
                        "on" if new_state else "off",
                        reason, vpd, stage, vpd_lo, vpd_hi,
                        lights.on, allowed,
                    )

                await self._record(is_on)

            except Exception:
                logger.exception(
                    "humidifier loop error — dropping plug connection",
                )
                await _safe_disconnect(plug)
                plug = None
                log_event(STREAM, "error")

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=interval)

        await _safe_disconnect(plug)
        logger.info("humidifier loop stopped")
