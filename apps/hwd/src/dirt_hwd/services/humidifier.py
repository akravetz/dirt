"""Humidifier control via Kasa EP10 smart plug.

Bang-bang hysteresis on tent VPD against the stage-dynamic upper band from
`dirt.services.grow_state.current_targets()`, with lights-schedule feedforward:

  A. Pre-lights-off prep window — force OFF in the last N minutes of lights-on
     so the humidifier isn't dosing mist into air that's about to cool and
     crash VPD (see 2026-04-19 decision).
  B. Lights-off band offset — during dark, the whole band shifts down by
     `vpd_lights_off_offset_kpa`. The humidifier can't raise night VPD anyway
     (single-direction actuator); the offset lets the loop rest instead of
     chasing a setpoint it can't hit.

The humidifier is a single-direction actuator (adds moisture → drops VPD),
so we target the band's upper edge: kick on when VPD rises above it, kick
off once it falls back below by `vpd_deadband_kpa`.

The only safety is stale-sensor failsafe OFF. The Raydrop has its own
low-water cutoff, so continuous-on from a stuck-high VPD reading is
self-limiting. Relay cycle count is bounded by the deadband alone.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from kasa import Credentials, Device, Discover
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import settings
from dirt_shared.db import engine
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.observability import log_event
from dirt_shared.services.grow_state import current_stage, current_targets, lights_state
from dirt_shared.services.readings import get_latest_reading

logger = logging.getLogger(__name__)

STREAM = "humidifier"


async def _record(on: bool) -> None:
    async with AsyncSession(engine) as session:
        session.add(
            SensorReading(
                location="tent",
                metric="humidifier_on",
                value=1.0 if on else 0.0,
                source="kasa",
            )
        )
        await session.commit()


async def _safe_disconnect(plug: Device | None) -> None:
    if plug is None:
        return
    with contextlib.suppress(Exception):
        await plug.disconnect()


async def humidifier_loop(stop_event: asyncio.Event) -> None:
    """Close the loop: tent VPD → Kasa plug → Raydrop humidifier.

    Polls every `humidifier_poll_interval` seconds. Each tick fetches the
    current stage's VPD band fresh so a veg→flower flip takes effect without
    a restart. Records the plug's state as a `humidifier_on` reading (0/1)
    every poll so it graphs alongside `vpd_kpa`. State transitions are also
    emitted to the `humidifier` operational log stream with the triggering
    reason, stage, and upper-band edge.
    """
    if not settings.kasa_username or not settings.kasa_password:
        logger.warning("KASA_USERNAME/KASA_PASSWORD unset — humidifier loop disabled")
        return

    creds = Credentials(settings.kasa_username, settings.kasa_password)
    host = settings.kasa_humidifier_host
    deadband = settings.vpd_deadband_kpa
    interval = settings.humidifier_poll_interval
    stale_s = settings.humidifier_failsafe_stale_seconds
    night_offset = settings.vpd_lights_off_offset_kpa
    prep_minutes = settings.lights_off_prep_minutes

    logger.info(
        "humidifier loop starting: host=%s deadband=%.2fkPa interval=%ds "
        "night_offset=%+.2fkPa prep_window=%dmin",
        host, deadband, interval, night_offset, prep_minutes,
    )

    plug: Device | None = None

    while not stop_event.is_set():
        try:
            if plug is None:
                # discover_single is the only path that accepts credentials
                # directly; Device.connect(host=...) has no credentials kwarg
                # on this python-kasa branch. One UDP probe per reconnect is
                # cheap at our 30s cadence.
                plug = await Discover.discover_single(host, credentials=creds)
                if plug is None:
                    raise RuntimeError(f"kasa discover_single({host}) returned None")

            await plug.update()
            is_on = bool(plug.is_on)

            # Stage-dynamic band + lights-off offset (B). During lights-off
            # the whole band drops by `night_offset` (negative value) because
            # the humidifier can't raise night VPD — chasing it just causes
            # overshoot. Deadband width is preserved.
            stage = await current_stage()
            lights = await lights_state()
            offset = 0.0 if lights.on else night_offset
            vpd_lo_day, vpd_hi_day = (await current_targets())["vpd_kpa"]
            vpd_lo = vpd_lo_day + offset
            vpd_hi = vpd_hi_day + offset
            turn_on_above = vpd_hi
            turn_off_below = vpd_hi - deadband

            # Pre-lights-off prep window (A). Last N minutes of lights-on:
            # force OFF regardless of VPD so we don't dose mist into air
            # that's about to cool and crash VPD into damping-off territory.
            in_prep_window = lights.on and lights.minutes_until_off < prep_minutes

            reading = await get_latest_reading("vpd_kpa")
            now = datetime.now(UTC)
            vpd: float | None = reading.value if reading else None
            # SQLite drops tzinfo; treat stored timestamps as UTC.
            age = None
            if reading is not None:
                ts = reading.timestamp
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                age = (now - ts).total_seconds()

            new_state = is_on
            reason: str | None = None

            if vpd is None or age is None or age > stale_s:
                if is_on:
                    new_state = False
                    reason = "failsafe_stale_sensor"
            elif in_prep_window:
                if is_on:
                    new_state = False
                    reason = "lights_off_prep"
                # else: already off, stay off — don't start during prep window
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
                    band_offset_kpa=offset,
                )
                logger.info(
                    "humidifier → %s (reason=%s vpd=%s stage=%s band=[%.2f,%.2f] "
                    "lights_on=%s until_off=%.1fmin)",
                    "on" if new_state else "off",
                    reason, vpd, stage, vpd_lo, vpd_hi,
                    lights.on, lights.minutes_until_off,
                )

            await _record(is_on)

        except Exception:
            logger.exception("humidifier loop error — dropping plug connection")
            await _safe_disconnect(plug)
            plug = None
            log_event(STREAM, "error")

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=interval)

    await _safe_disconnect(plug)
    logger.info("humidifier loop stopped")
