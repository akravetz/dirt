"""Humidifier control via Kasa EP10 smart plug.

Bang-bang hysteresis on tent VPD against the stage-dynamic upper band from
`dirt.services.grow_state.current_targets()`. The humidifier is a single-
direction actuator (adds moisture → drops VPD), so we target the band's
upper edge: kick on when VPD rises above it, kick off once it falls back
below by `vpd_deadband_kpa`. Night-time behavior is free — cooler air drops
VPD naturally, which turns the loop off without a schedule.

Safety posture: failsafe OFF on any ambiguity (stale sensor, unreachable
plug, max-on timeout). Stuck-off is safer than stuck-on — mold / damping-off
is worse than a brief dry spell.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from kasa import Credentials, Device, Discover
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.config import settings
from dirt.db import engine
from dirt.models.sensor_reading import SensorReading
from dirt.observability import log_event
from dirt.services.grow_state import current_stage, current_targets
from dirt.services.readings import get_latest_reading

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
    min_off = settings.humidifier_min_off_seconds
    max_on = settings.humidifier_max_on_seconds
    stale_s = settings.humidifier_failsafe_stale_seconds

    logger.info(
        "humidifier loop starting: host=%s deadband=%.2fkPa interval=%ds",
        host, deadband, interval,
    )

    plug: Device | None = None
    last_switch: float = 0.0  # monotonic seconds
    # If the plug is already on at startup, we can't know how long it's been
    # running. Seed turned_on_at to "now" so max_on_timeout resets fresh on
    # each process start rather than instantly tripping.
    turned_on_at: float | None = None

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
            if turned_on_at is None:
                turned_on_at = asyncio.get_event_loop().time() if is_on else 0.0

            # Stage-dynamic upper band; the humidifier targets the dry edge.
            stage = await current_stage()
            vpd_lo, vpd_hi = (await current_targets())["vpd_kpa"]
            turn_on_above = vpd_hi
            turn_off_below = vpd_hi - deadband

            reading = await get_latest_reading("vpd_kpa")
            now_mono = asyncio.get_event_loop().time()
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
            elif is_on and (now_mono - turned_on_at) > max_on:
                new_state = False
                reason = "max_on_timeout"
            elif (
                vpd > turn_on_above
                and not is_on
                and (now_mono - last_switch) >= min_off
            ):
                new_state = True
                reason = "vpd_above_upper_band"
            elif vpd < turn_off_below and is_on:
                new_state = False
                reason = "vpd_below_upper_band"

            if new_state != is_on:
                if new_state:
                    await plug.turn_on()
                    turned_on_at = now_mono
                else:
                    await plug.turn_off()
                last_switch = now_mono
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
                )
                logger.info(
                    "humidifier → %s (reason=%s vpd=%s age=%s stage=%s band=[%s,%s])",
                    "on" if new_state else "off",
                    reason, vpd, age, stage, vpd_lo, vpd_hi,
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
