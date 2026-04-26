"""Humidifier control via Kasa EP10 smart plug.

Bang-bang hysteresis on tent VPD against the stage-dynamic upper band from
``GrowStateService.current_targets()``, with lights-schedule feedforward.

The humidifier is a single-direction actuator (adds moisture → drops VPD),
so we target the band's upper edge: kick on when VPD rises above it, kick
off once it falls back below by ``vpd_deadband_kpa``.

A secondary stuck-actuator watchdog fires a Telegram alert when the plug
has been continuously ON for ``stuck_alert_after_s`` without VPD dropping
by ``stuck_min_vpd_drop_kpa`` — the signature of a Raydrop low-water
float-sensor latch (red LED, electrically on, no mist), first observed
2026-04-23. See wiki/hardware/humidifier-control.md "Red LED =
low-water sensor latch".
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import httpx
from kasa import Credentials, Device, Discover

from dirt_hwd.services.humidifier_pi import (
    PIConfig,
    PIInput,
    PIState,
)
from dirt_hwd.services.humidifier_pi import (
    compute as pi_compute,
)
from dirt_shared.config import HumidifierConfig
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.observability import log_event
from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

STREAM = "humidifier"
SHADOW_STREAM = "humidifier_shadow"

# Conservative starting gains (Phase 4 prep — shadow only, not actuating).
# Sourced from FOPDT-fit findings (2026-04-25) at the *low end* of the
# bracket; refined under shadow-mode + graduated-step test in Phase 2/3
# acceptance, not by edits to this constant during the prep phase.
# See: docs/epics/continuous-humidifier/fopdt-fit-findings.md
_SHADOW_PI_KC = 8.0
_SHADOW_PI_KI = 0.01
_SHADOW_PI_INTEGRATOR_CLAMP = 50.0
_SHADOW_PI_THRESHOLD = 5.0
_SHADOW_PI_THRESHOLD_HYSTERESIS = 1.0
_SHADOW_PI_NIGHT_OFFSET_KPA = -0.3


async def _safe_disconnect(plug: Device | None) -> None:
    if plug is None:
        return
    with contextlib.suppress(Exception):
        await plug.disconnect()


# ============================================================
# Stuck-actuator watchdog (pure state machine, unit-testable)
# ============================================================


@dataclass(frozen=True)
class StuckState:
    """Tracker for the humidifier's current continuous-ON streak."""

    start_ts: datetime | None = None
    start_vpd: float | None = None
    alert_sent: bool = False


def update_stuck_state(  # noqa: PLR0913 — parameters are the full tick context; collapsing into a config object would add boilerplate without hiding anything meaningful.
    state: StuckState,
    *,
    is_on: bool,
    vpd: float | None,
    now: datetime,
    alert_after_s: float,
    min_vpd_drop_kpa: float,
) -> tuple[StuckState, bool]:
    """Advance the watchdog one tick; return (new_state, should_fire_alert).

    Contract:
      - Off→on transition: start a new streak (capture VPD at transition).
      - On→off transition: clear the streak.
      - Held on with no VPD drop >= min_vpd_drop_kpa after alert_after_s
        elapsed: fire alert exactly once per streak (suppress dupes until
        the next off→on).
      - Stale / missing VPD during the streak: skip the stuck check — the
        main loop's failsafe handles the no-sensor case separately.
    """
    if is_on and state.start_ts is None:
        return StuckState(start_ts=now, start_vpd=vpd), False
    if not is_on and state.start_ts is not None:
        return StuckState(), False
    if (
        is_on
        and state.start_ts is not None
        and state.start_vpd is not None
        and vpd is not None
        and not state.alert_sent
    ):
        elapsed_s = (now - state.start_ts).total_seconds()
        drop = state.start_vpd - vpd
        if elapsed_s >= alert_after_s and drop < min_vpd_drop_kpa:
            return replace(state, alert_sent=True), True
    return state, False


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
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._config = config
        self._readings = readings
        self._grow = grow
        self._clock = clock
        self._http_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=10.0)
        )

    async def _record(self, on: bool) -> None:
        await self._readings.ingest_reading(
            SensorLocation.TENT,
            {"humidifier_on": 1.0 if on else 0.0},
            source=SensorSource.KASA,
        )

    async def run(self, stop_event: asyncio.Event) -> None:  # noqa: PLR0915 — single-responsibility state-machine loop; splitting it would fragment the control flow across private methods without reducing total complexity.
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
            "lights_margin=%dmin stuck_after=%ds min_vpd_drop=%.2fkPa",
            host,
            deadband,
            interval,
            margin_minutes,
            cfg.stuck_alert_after_s,
            cfg.stuck_min_vpd_drop_kpa,
        )

        plug: Device | None = None
        stuck_state = StuckState()
        pi_state = PIState()
        pi_cfg = PIConfig(
            kc=_SHADOW_PI_KC,
            ki=_SHADOW_PI_KI,
            integrator_clamp=_SHADOW_PI_INTEGRATOR_CLAMP,
            intensity_threshold=_SHADOW_PI_THRESHOLD,
            threshold_hysteresis=_SHADOW_PI_THRESHOLD_HYSTERESIS,
            night_offset_kpa=_SHADOW_PI_NIGHT_OFFSET_KPA,
            failsafe_stale_s=cfg.failsafe_stale_seconds,
            lights_off_prep_minutes=cfg.lights_off_prep_minutes,
        )

        async with self._http_factory() as http:
            telegram: TelegramClient | None = None
            if cfg.telegram_bot_token and cfg.telegram_chat_id:
                telegram = TelegramClient(
                    token=cfg.telegram_bot_token,
                    http=http,
                )
            else:
                logger.info(
                    "telegram creds unset — stuck-humidifier alerts disabled "
                    "(log-only)",
                )

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

                    ctx = await self._grow.current_context()
                    stage = ctx.stage
                    lights = ctx.lights
                    vpd_lo, vpd_hi = ctx.targets["vpd_kpa"]
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
                        lights.on and lights.minutes_until_off >= margin_minutes
                    ) or (not lights.on and lights.minutes_until_on <= margin_minutes)

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
                            reason,
                            vpd,
                            stage,
                            vpd_lo,
                            vpd_hi,
                            lights.on,
                            allowed,
                        )

                    # Shadow-mode PI controller. Computes what the continuous
                    # intensity would be each tick and logs to a separate
                    # stream — no actuator action. Safe to fail under any
                    # input edge (None RH, missing sensor, etc.) since the
                    # controller is total-functional. See
                    # docs/epics/continuous-humidifier/phase4-test-plan.md.
                    rh_reading = await self._readings.get_latest_reading("humidity_pct")
                    rh = rh_reading.value if rh_reading else None
                    rh_band = ctx.targets["humidity_pct"]
                    pi_inp = PIInput(
                        now=now,
                        vpd=vpd,
                        vpd_ts=reading.ts if reading else None,
                        rh=rh,
                        stage_vpd_band=(vpd_lo, vpd_hi),
                        stage_humidity_band=rh_band,
                        lights_on=lights.on,
                        minutes_until_off=lights.minutes_until_off,
                        minutes_until_on=lights.minutes_until_on,
                    )
                    pi_out = pi_compute(pi_cfg, pi_state, pi_inp)
                    pi_state = pi_out.new_state
                    log_event(
                        SHADOW_STREAM,
                        "tick",
                        u_pct=round(pi_out.u, 2),
                        plug_on_shadow=pi_out.plug_on,
                        plug_on_actual=is_on,
                        setpoint_kpa=round(pi_out.setpoint_vpd, 3),
                        error_kpa=round(pi_out.error, 4),
                        p_term=round(pi_out.p_term, 3),
                        i_term=round(pi_out.i_term, 3),
                        integrator=round(pi_state.integral, 3),
                        reason=pi_out.reason.value,
                        vpd=vpd,
                        vpd_age_s=round(age, 2) if age is not None else None,
                        rh=rh,
                        stage=stage,
                        upper_band_kpa=vpd_hi,
                        lower_band_kpa=vpd_lo,
                        rh_ceiling_pct=rh_band[1],
                        lights_on=lights.on,
                        minutes_until_off=round(lights.minutes_until_off, 1),
                        minutes_until_on=round(lights.minutes_until_on, 1),
                        kc=pi_cfg.kc,
                        ki=pi_cfg.ki,
                        threshold_pct=pi_cfg.intensity_threshold,
                    )

                    stuck_state, fire_alert = update_stuck_state(
                        stuck_state,
                        is_on=is_on,
                        vpd=vpd,
                        now=now,
                        alert_after_s=cfg.stuck_alert_after_s,
                        min_vpd_drop_kpa=cfg.stuck_min_vpd_drop_kpa,
                    )
                    if fire_alert:
                        await self._alert_stuck(
                            stuck_state, vpd, now, stage, vpd_hi, vpd_lo, telegram
                        )

                    await self._record(is_on)

                except Exception as exc:
                    logger.exception(
                        "humidifier loop error — dropping plug connection",
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
        logger.info("humidifier loop stopped")

    async def _alert_stuck(  # noqa: PLR0913 — the call site has all this context already; passing it in is cheaper than re-deriving inside the method.
        self,
        stuck_state: StuckState,
        vpd: float | None,
        now: datetime,
        stage: str,
        vpd_hi: float,
        vpd_lo: float,
        telegram: TelegramClient | None,
    ) -> None:
        # `update_stuck_state` only fires when start_ts, start_vpd, and vpd are
        # all set — guard here to narrow types for static analysis.
        start_ts = stuck_state.start_ts
        start_vpd = stuck_state.start_vpd
        if start_ts is None or start_vpd is None or vpd is None:
            return
        pinned_min = (now - start_ts).total_seconds() / 60
        vpd_drop = start_vpd - vpd
        log_event(
            STREAM,
            "suspected_stuck",
            pinned_minutes=round(pinned_min, 1),
            vpd_at_start=round(start_vpd, 3),
            vpd_now=round(vpd, 3),
            vpd_drop=round(vpd_drop, 3),
            stage=stage,
            upper_band_kpa=vpd_hi,
            lower_band_kpa=vpd_lo,
        )
        logger.warning(
            "humidifier suspected stuck: pinned ON %.0fm, "
            "VPD %.2f → %.2f kPa (drop %+.2f, threshold %.2f)",
            pinned_min,
            start_vpd,
            vpd,
            vpd_drop,
            self._config.stuck_min_vpd_drop_kpa,
        )
        if telegram is None:
            return
        text = (
            f"⚠ <b>Humidifier suspected stuck</b>\n"
            f"Plug ON for {pinned_min:.0f}m; "
            f"VPD {start_vpd:.2f} → {vpd:.2f} kPa "
            f"(drop {vpd_drop:+.2f}).\n"
            f"Check Raydrop: red LED, water level, visible mist."
        )
        try:
            await telegram.send_message(self._config.telegram_chat_id, text)
        except TelegramError:
            logger.exception("telegram send failed for stuck alert")
