"""Humidifier control via Govee H7142 (Wi-Fi-native, cloud API).

Per-tick state machine:
  1. Read VPD, RH, lights, stage targets from grow services + readings.
  2. PI controller emits continuous u_pct ∈ [0, 100] + plug_on gate.
  3. Quantizer maps u_pct → discrete Manual-mode level (1..9) with hysteresis.
  4. Read live device state from Govee.
  5. Diff (current device, target) → minimal API calls to converge.
  6. Track lackWaterEvent (tank empty) and ineffective-actuator watchdog.

The PI controller and quantizer are pure functions (separate modules); this
service is the I/O boundary. Cutover from Kasa+Raydrop bang-bang on
2026-04-27 — see wiki/decisions/2026-04-27-h7142-deployed.md.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import httpx

from dirt_hwd.services.environment_allocator import (
    HumidifierAllocationConfig,
    HumidifierAllocationInput,
    HumidifierAllocationOutput,
    allocate_humidifier_output,
)
from dirt_hwd.services.humidifier_dispatch import (
    DispatchConfig,
    DispatchOutput,
    DispatchState,
    quantize,
)
from dirt_hwd.services.humidifier_pi import (
    PIConfig,
    PIInput,
    PIOutput,
    PIState,
    track_delivered_output,
)
from dirt_hwd.services.humidifier_pi import (
    compute as pi_compute,
)
from dirt_shared.config import FanTrimConfig, HumidifierConfig
from dirt_shared.models.enums import SensorSource
from dirt_shared.observability import log_event
from dirt_shared.services.govee import (
    GoveeClient,
    GoveeError,
    GoveeRateLimitError,
)
from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID
from dirt_shared.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

STREAM = "humidifier"
SHADOW_STREAM = "humidifier_shadow"

# Inline pause between set_power(on) and set_manual_level(N) when the device
# is currently OFF and we want it ON at a non-default level on the same tick.
# 200ms is generous for the Govee cloud round-trip path; the second call
# would arrive ahead of the device's first command settling otherwise and
# the H7142 is observed to drop the closer-spaced second command.
_BOOT_TICK_INTERLEAVE_S = 0.2


# ============================================================
# Lack-water tracker (rising-edge-deduped)
# ============================================================


@dataclass(frozen=True)
class LackWaterState:
    """Tracks whether ``lackWaterEvent`` is currently active."""

    active: bool = False
    started_at: datetime | None = None


def update_lack_water(
    state: LackWaterState,
    *,
    lack_water: bool,
    now: datetime,
) -> tuple[LackWaterState, str | None]:
    """Advance the empty-tank tracker one tick. Returns (new_state, edge)
    where ``edge ∈ {None, "rising", "falling"}``."""
    if lack_water and not state.active:
        return LackWaterState(active=True, started_at=now), "rising"
    if not lack_water and state.active:
        return LackWaterState(active=False, started_at=None), "falling"
    return state, None


# ============================================================
# Ineffective-actuator watchdog
# ============================================================
# Replaces the Raydrop-specific "stuck red LED" watchdog. The H7142's empty-
# tank case is covered separately by lackWaterEvent, so this catches the
# residual failure modes: atomization plate fouling, firmware glitch, mist
# reaching the room not the canopy, etc. Triggers when we've been commanding
# a non-zero level for ``alert_after_s`` and VPD hasn't dropped by
# ``min_vpd_drop_kpa`` from the streak start.


@dataclass(frozen=True)
class IneffectiveState:
    start_ts: datetime | None = None
    start_vpd: float | None = None
    alert_sent: bool = False


def update_ineffective_state(  # noqa: PLR0913
    state: IneffectiveState,
    *,
    commanded_level: int | None,  # None == OFF, int == level 1..N
    vpd: float | None,
    now: datetime,
    alert_after_s: float,
    min_vpd_drop_kpa: float,
) -> tuple[IneffectiveState, bool]:
    """Advance the watchdog one tick; return (new_state, should_fire_alert).

    Streak semantics:
      - OFF→commanded transition starts a new streak (capture VPD).
      - commanded→OFF transition clears the streak.
      - Held commanded with no VPD drop ≥ min_vpd_drop_kpa after
        alert_after_s elapsed: fire alert exactly once per streak.
      - Stale / missing VPD during the streak: skip the check.

    Note: a level *change* (e.g. 3 → 5) does NOT reset the streak. The
    failure mode is "we've been asking for mist for X minutes and nothing
    is happening" — it doesn't matter which level we asked for.
    """
    is_commanded = commanded_level is not None and commanded_level >= 1
    if is_commanded and state.start_ts is None:
        return IneffectiveState(start_ts=now, start_vpd=vpd), False
    if not is_commanded and state.start_ts is not None:
        return IneffectiveState(), False
    if (
        is_commanded
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


# ============================================================
# Dispatch boundary — diff (current, target) → API calls
# ============================================================


@dataclass(frozen=True)
class DispatchDiff:
    """Decision for a single tick: what to send to the device, and why."""

    set_power_on: bool | None  # None = no power change
    set_level: int | None  # None = no level change
    interleave: bool  # send both with inline sleep between
    no_op: bool


def _plan_dispatch(
    *,
    current_power: bool | None,
    current_level: int | None,
    target_level: int | None,
) -> DispatchDiff:
    """Compute the minimal set of control calls to converge.

    Source of truth for ``current_*`` is the live device state, NOT our
    last-commanded value — divergence (user toggled via app, dropped
    command) self-heals on the next tick.
    """
    target_off = target_level is None
    current_off = current_power is False or (current_power is None)

    if target_off and current_off:
        return DispatchDiff(
            set_power_on=None, set_level=None, interleave=False, no_op=True
        )

    if target_off and not current_off:
        return DispatchDiff(
            set_power_on=False, set_level=None, interleave=False, no_op=False
        )

    # target is a level (not OFF) below.

    if current_off:
        # Boot-tick path: power on AND set the level on the same tick.
        # Skip the level call only if the device's last commanded level
        # already matches the target (workMode is preserved across power
        # cycles on the H7142, verified 2026-04-27).
        need_level = current_level != target_level
        return DispatchDiff(
            set_power_on=True,
            set_level=target_level if need_level else None,
            interleave=need_level,
            no_op=False,
        )

    # Already on; level may or may not need a change.
    if current_level == target_level:
        return DispatchDiff(
            set_power_on=None, set_level=None, interleave=False, no_op=True
        )
    return DispatchDiff(
        set_power_on=None, set_level=target_level, interleave=False, no_op=False
    )


# ============================================================
# Main loop service
# ============================================================


class HumidifierLoopService:
    """VPD-targeting humidifier control loop, H7142 actuator.

    Constructor-inject readings + grow + clock + http/govee factories."""

    def __init__(  # noqa: PLR0913 — composition root params; no useful sub-grouping.
        self,
        config: HumidifierConfig,
        *,
        readings: ReadingsService,
        grow: GrowStateService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
        govee_client_factory: Callable[[str, httpx.AsyncClient], GoveeClient]
        | None = None,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
        canopy_device_id: str = "fan-controller",
        humidifier_device_id: str = "govee-h7142-main",
        fan_trim_config: FanTrimConfig | None = None,
    ) -> None:
        self._config = config
        self._readings = readings
        self._grow = grow
        self._clock = clock
        self._site_id = site_id
        self._tent_id = tent_id
        self._zone_id = "canopy"
        self._canopy_device_id = canopy_device_id
        self._humidifier_device_id = humidifier_device_id
        self._allocator_config = (
            HumidifierAllocationConfig(
                fan_floor_pct=fan_trim_config.min_pct,
                fan_max_pct=fan_trim_config.max_pct,
                fan_high_vpd_margin_kpa=fan_trim_config.high_vpd_margin_kpa,
                fan_sensor_stale_s=fan_trim_config.sensor_stale_s,
                rh_reenable_buffer_pct=fan_trim_config.recover_rh_buffer_pct,
            )
            if fan_trim_config is not None
            else None
        )
        self._http_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=15.0)
        )
        self._govee_factory = govee_client_factory or (
            lambda key, http: GoveeClient(api_key=key, http=http)
        )

    async def _record_actuator(self, target_level: int | None) -> None:
        """Record the commanded actuator state as a sensor reading."""
        await self._readings.ingest_reading(
            {
                "humidifier_on": 0.0 if target_level is None else 1.0,
                "humidifier_mist_level": 0.0
                if target_level is None
                else float(target_level),
            },
            source=SensorSource.GOVEE,
            site_id=self._site_id,
            tent_id=self._tent_id,
            zone_id=self._zone_id,
            device_id=self._humidifier_device_id,
        )

    def _scope_fields(self, *, capability_id: str | None = None) -> dict[str, str]:
        fields = {
            "site_id": self._site_id,
            "tent_id": self._tent_id,
            "zone_id": self._zone_id,
            "device_id": self._humidifier_device_id,
        }
        if capability_id is not None:
            fields["capability_id"] = capability_id
        return fields

    async def _resolve_mac(self, govee: GoveeClient) -> str | None:
        """Either return the configured MAC, or discover by SKU."""
        if self._config.govee_mac:
            return self._config.govee_mac
        try:
            devices = await govee.discover()
        except GoveeError:
            logger.exception("govee discover failed; cannot start humidifier loop")
            return None
        for d in devices:
            if d.sku == self._config.govee_sku:
                logger.info(
                    "govee discovered %s mac=%s name=%r", d.sku, d.device, d.name
                )
                return d.device
        logger.error(
            "govee discover: no device with sku=%s on the account",
            self._config.govee_sku,
        )
        return None

    async def run(self, stop_event: asyncio.Event) -> None:  # noqa: PLR0915 — single-responsibility loop; splitting fragments control flow.
        cfg = self._config
        if not cfg.govee_api_key:
            logger.warning("GOVEE_API_KEY unset — humidifier loop disabled")
            return

        pi_cfg = PIConfig(
            kc=cfg.pi_kc,
            ki=cfg.pi_ki,
            integrator_clamp=cfg.pi_integrator_clamp,
            intensity_threshold=cfg.pi_threshold_pct,
            threshold_hysteresis=cfg.pi_threshold_hysteresis_pct,
            night_offset_kpa=cfg.pi_night_offset_kpa,
            failsafe_stale_s=cfg.failsafe_stale_seconds,
            lights_off_prep_minutes=cfg.lights_off_prep_minutes,
        )
        disp_cfg = DispatchConfig(
            levels=cfg.mist_levels,
            level_hysteresis_pct=cfg.level_hysteresis_pct,
        )

        logger.info(
            "humidifier loop starting: sku=%s mac=%s levels=%d hyst=%.1f%% "
            "interval=%ds lights_margin=%dmin pi_kc=%.2f pi_ki=%.4f",
            cfg.govee_sku,
            cfg.govee_mac or "<discover>",
            cfg.mist_levels,
            cfg.level_hysteresis_pct,
            cfg.poll_interval,
            cfg.lights_off_prep_minutes,
            cfg.pi_kc,
            cfg.pi_ki,
        )

        pi_state = PIState()
        disp_state = DispatchState()
        lack_state = LackWaterState()
        ineffective_state = IneffectiveState()
        prev_online = True

        async with self._http_factory() as http:
            govee = self._govee_factory(cfg.govee_api_key, http)
            telegram: TelegramClient | None = None
            if cfg.telegram_bot_token and cfg.telegram_chat_id:
                telegram = TelegramClient(token=cfg.telegram_bot_token, http=http)
            else:
                logger.info("telegram creds unset — humidifier alerts log-only")

            mac = await self._resolve_mac(govee)
            if mac is None:
                logger.warning("humidifier loop exiting: cannot resolve device MAC")
                return

            while not stop_event.is_set():
                try:
                    now = self._clock()

                    ctx = await self._grow.current_context(
                        site_id=self._site_id,
                        tent_id=self._tent_id,
                    )
                    stage = ctx.stage
                    lights = ctx.lights
                    vpd_lo, vpd_hi = ctx.targets["vpd_kpa"]
                    rh_band = ctx.targets["humidity_pct"]

                    reading_tasks = [
                        self._readings.get_latest_reading(
                            "vpd_kpa",
                            site_id=self._site_id,
                            tent_id=self._tent_id,
                            zone_id=self._zone_id,
                            device_id=self._canopy_device_id,
                            capability_id="vpd_kpa",
                        ),
                        self._readings.get_latest_reading(
                            "humidity_pct",
                            site_id=self._site_id,
                            tent_id=self._tent_id,
                            zone_id=self._zone_id,
                            device_id=self._canopy_device_id,
                            capability_id="humidity_pct",
                        ),
                    ]
                    if self._allocator_config is not None:
                        reading_tasks.append(
                            self._readings.get_latest_reading(
                                "fan_duty_pct",
                                site_id=self._site_id,
                                tent_id=self._tent_id,
                                zone_id=self._zone_id,
                                device_id=self._canopy_device_id,
                                capability_id="fan_duty_pct",
                            )
                        )
                    readings = await asyncio.gather(*reading_tasks)
                    vpd_reading = readings[0]
                    rh_reading = readings[1]
                    fan_reading = readings[2] if len(readings) > 2 else None
                    vpd = vpd_reading.value if vpd_reading else None
                    rh = rh_reading.value if rh_reading else None
                    vpd_age = (
                        (now - vpd_reading.ts).total_seconds()
                        if vpd_reading is not None
                        else None
                    )
                    fan_pct = fan_reading.value if fan_reading else None
                    fan_age = (
                        (now - fan_reading.ts).total_seconds()
                        if fan_reading is not None
                        else None
                    )

                    # ---- PI -------------------------------------------------
                    pi_inp = PIInput(
                        now=now,
                        vpd=vpd,
                        vpd_ts=vpd_reading.ts if vpd_reading else None,
                        rh=rh,
                        stage_vpd_band=(vpd_lo, vpd_hi),
                        stage_humidity_band=rh_band,
                        lights_on=lights.on,
                        minutes_until_off=lights.minutes_until_off,
                        minutes_until_on=lights.minutes_until_on,
                    )
                    pi_out = pi_compute(pi_cfg, pi_state, pi_inp)

                    # ---- Cross-actuator allocation -------------------------
                    alloc_out = self._allocate_humidifier_output(
                        pi_out,
                        now=now,
                        vpd=vpd,
                        rh=rh,
                        fan_pct=fan_pct,
                        fan_age=fan_age,
                        vpd_band=(vpd_lo, vpd_hi),
                        rh_band=rh_band,
                    )
                    if alloc_out.reason == "fan_relief_first":
                        pi_state = track_delivered_output(
                            pi_cfg,
                            pi_out,
                            delivered_u=alloc_out.u_pct,
                            delivered_plug_on=alloc_out.plug_on,
                        )
                    else:
                        pi_state = pi_out.new_state

                    # ---- Dispatch quantizer ---------------------------------
                    disp_out = quantize(
                        disp_cfg,
                        disp_state,
                        alloc_out.u_pct,
                        alloc_out.plug_on,
                    )

                    # ---- Read live device state -----------------------------
                    snap = await govee.get_state(cfg.govee_sku, mac)

                    # Track online/offline transitions (always, even when we
                    # skip dispatch).
                    if snap.online != prev_online:
                        log_event(
                            STREAM,
                            "device_online" if snap.online else "device_offline",
                            **self._scope_fields(),
                            online=snap.online,
                            power=snap.power_on,
                            mode_value=snap.mode_value,
                        )
                        prev_online = snap.online

                    # ---- Lack-water (always tracked) ------------------------
                    lack_state, edge = update_lack_water(
                        lack_state, lack_water=snap.lack_water, now=now
                    )
                    if edge == "rising":
                        await self._handle_lack_water_rising(
                            now, vpd, stage, disp_out.target_level, telegram
                        )
                    elif edge == "falling" and lack_state.started_at is None:
                        log_event(
                            STREAM,
                            "lack_water_cleared",
                            **self._scope_fields(capability_id="mist_level"),
                            stage=stage,
                            commanded_level=disp_out.target_level,
                        )

                    # ---- Decide + dispatch ----------------------------------
                    if not snap.online:
                        # Don't actuate while the device is unreachable from
                        # Govee cloud. PI/quantizer ran for diagnosability;
                        # disp_state is NOT advanced so we don't lie about
                        # what the device is doing.
                        log_event(
                            STREAM,
                            "skip_offline",
                            **self._scope_fields(capability_id="mist_level"),
                            target_level=disp_out.target_level,
                            u_pct=round(alloc_out.u_pct, 2),
                            stage=stage,
                            reason=pi_out.reason.value,
                            allocation_reason=alloc_out.reason,
                            requested_u_pct=round(pi_out.u, 2),
                            fan_pct=fan_pct,
                            fan_age_s=round(fan_age, 2)
                            if fan_age is not None
                            else None,
                        )
                        await self._log_shadow(
                            pi_out,
                            pi_state,
                            alloc_out,
                            disp_out,
                            vpd,
                            vpd_age,
                            rh,
                            stage,
                            vpd_lo,
                            vpd_hi,
                            rh_band,
                            lights,
                            pi_cfg,
                        )
                        await asyncio.sleep(0)  # yield
                    else:
                        diff = _plan_dispatch(
                            current_power=snap.power_on,
                            current_level=snap.mode_value,
                            target_level=disp_out.target_level,
                        )

                        if not diff.no_op:
                            await self._dispatch(govee, mac, diff)

                        prev_level = disp_state.last_level
                        disp_state = disp_out.new_state

                        await self._log_dispatch_change(
                            diff,
                            target_level=disp_out.target_level,
                            prev_level=prev_level,
                            pi_out=pi_out,
                            alloc_out=alloc_out,
                            disp_out=disp_out,
                            stage=stage,
                            vpd=vpd,
                            vpd_age=vpd_age,
                            rh=rh,
                            fan_pct=fan_pct,
                            fan_age=fan_age,
                            vpd_band=(vpd_lo, vpd_hi),
                            rh_band=rh_band,
                            lights_on=lights.on,
                            minutes_until_off=lights.minutes_until_off,
                            minutes_until_on=lights.minutes_until_on,
                        )

                        # Heartbeat for SystemStatusService — flips
                        # the device entry to "offline" if absent for
                        # ~5 min. Write every tick, not just on level
                        # transitions.
                        await self._record_actuator(disp_out.target_level)

                        await self._log_shadow(
                            pi_out,
                            pi_state,
                            alloc_out,
                            disp_out,
                            vpd,
                            vpd_age,
                            rh,
                            stage,
                            vpd_lo,
                            vpd_hi,
                            rh_band,
                            lights,
                            pi_cfg,
                        )

                    # ---- Ineffective watchdog -------------------------------
                    ineffective_state, fire = update_ineffective_state(
                        ineffective_state,
                        commanded_level=disp_out.target_level,
                        vpd=vpd,
                        now=now,
                        alert_after_s=cfg.ineffective_alert_after_s,
                        min_vpd_drop_kpa=cfg.ineffective_min_vpd_drop_kpa,
                    )
                    if fire:
                        await self._alert_ineffective(
                            ineffective_state,
                            vpd,
                            now,
                            stage,
                            (vpd_lo, vpd_hi),
                            disp_out.target_level,
                            telegram,
                        )

                except GoveeRateLimitError as exc:
                    # Quiet log — next tick retries naturally.
                    logger.info("govee rate limit (code=%s): %s", exc.code, exc.message)
                    log_event(
                        STREAM,
                        "rate_limited",
                        **self._scope_fields(),
                        error=exc.message,
                    )
                except Exception as exc:
                    logger.exception("humidifier loop error")
                    log_event(
                        STREAM,
                        "error",
                        **self._scope_fields(),
                        error_type=type(exc).__name__,
                        error=repr(exc),
                    )

                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=cfg.poll_interval)

        logger.info("humidifier loop stopped")

    # ------------------------------------------------------------------
    # Dispatch + observability helpers
    # ------------------------------------------------------------------

    def _allocate_humidifier_output(  # noqa: PLR0913
        self,
        pi_out: PIOutput,
        *,
        now: datetime,
        vpd: float | None,
        rh: float | None,
        fan_pct: float | None,
        fan_age: float | None,
        vpd_band: tuple[float, float],
        rh_band: tuple[float, float],
    ) -> HumidifierAllocationOutput:
        if self._allocator_config is None:
            return HumidifierAllocationOutput(
                u_pct=pi_out.u,
                plug_on=pi_out.plug_on,
                reason="allocator_disabled",
                fan_pct=fan_pct,
                fan_age_s=fan_age,
            )
        return allocate_humidifier_output(
            self._allocator_config,
            HumidifierAllocationInput(
                now=now,
                requested_u_pct=pi_out.u,
                requested_plug_on=pi_out.plug_on,
                vpd=vpd,
                rh=rh,
                fan_pct=fan_pct,
                fan_age_s=fan_age,
                vpd_band=vpd_band,
                rh_band=rh_band,
            ),
        )

    async def _dispatch(self, govee: GoveeClient, mac: str, diff: DispatchDiff) -> None:
        """Issue the API calls implied by ``diff``. Errors propagate."""
        sku = self._config.govee_sku
        if diff.set_power_on is not None:
            await govee.set_power(sku, mac, on=diff.set_power_on)
        if diff.interleave and diff.set_level is not None:
            # Same-tick boot path: pause briefly so the H7142 doesn't drop
            # the closer-spaced second command.
            await asyncio.sleep(_BOOT_TICK_INTERLEAVE_S)
        if diff.set_level is not None:
            await govee.set_manual_level(sku, mac, diff.set_level)

    async def _log_dispatch_change(  # noqa: PLR0913
        self,
        diff: DispatchDiff,
        *,
        target_level: int | None,
        prev_level: int | None,
        pi_out: PIOutput,
        alloc_out: HumidifierAllocationOutput,
        disp_out: DispatchOutput,
        stage: str,
        vpd: float | None,
        vpd_age: float | None,
        rh: float | None,
        fan_pct: float | None,
        fan_age: float | None,
        vpd_band: tuple[float, float],
        rh_band: tuple[float, float],
        lights_on: bool,
        minutes_until_off: float,
        minutes_until_on: float,
    ) -> int | None:
        """Emit state_change / level_change. Returns new prev_level."""
        if diff.no_op:
            return prev_level

        # Power transition (or first-tick set).
        if diff.set_power_on is not None or (prev_level is None) != (
            target_level is None
        ):
            log_event(
                STREAM,
                "state_change",
                **self._scope_fields(capability_id="power"),
                power=1 if target_level is not None else 0,
                level=target_level,
                u_pct=round(alloc_out.u_pct, 2),
                requested_u_pct=round(pi_out.u, 2),
                reason=pi_out.reason.value,
                allocation_reason=alloc_out.reason,
                vpd=vpd,
                vpd_age_s=round(vpd_age, 2) if vpd_age is not None else None,
                rh=rh,
                fan_pct=fan_pct,
                fan_age_s=round(fan_age, 2) if fan_age is not None else None,
                stage=stage,
                upper_band_kpa=vpd_band[1],
                lower_band_kpa=vpd_band[0],
                lights_on=lights_on,
                minutes_until_off=round(minutes_until_off, 1),
                minutes_until_on=round(minutes_until_on, 1),
                bucket_width_pct=round(disp_out.bucket_width, 2),
            )
        elif target_level != prev_level and target_level is not None:
            log_event(
                STREAM,
                "level_change",
                **self._scope_fields(capability_id="mist_level"),
                from_level=prev_level,
                to_level=target_level,
                u_pct=round(alloc_out.u_pct, 2),
                requested_u_pct=round(pi_out.u, 2),
                allocation_reason=alloc_out.reason,
                vpd=vpd,
                stage=stage,
                upper_band_kpa=vpd_band[1],
                lights_on=lights_on,
                bucket_width_pct=round(disp_out.bucket_width, 2),
            )
        return target_level

    async def _log_shadow(  # noqa: PLR0913
        self,
        pi_out: PIOutput,
        pi_state: PIState,
        alloc_out: HumidifierAllocationOutput,
        disp_out: DispatchOutput,
        vpd: float | None,
        vpd_age: float | None,
        rh: float | None,
        stage: str,
        vpd_lo: float,
        vpd_hi: float,
        rh_band: tuple[float, float],
        lights,
        pi_cfg: PIConfig,
    ) -> None:
        log_event(
            SHADOW_STREAM,
            "tick",
            **self._scope_fields(capability_id="mist_level"),
            u_pct=round(alloc_out.u_pct, 2),
            requested_u_pct=round(pi_out.u, 2),
            plug_on_shadow=alloc_out.plug_on,
            requested_plug_on=pi_out.plug_on,
            allocation_reason=alloc_out.reason,
            target_level=disp_out.target_level,
            setpoint_kpa=round(pi_out.setpoint_vpd, 3),
            error_kpa=round(pi_out.error, 4),
            p_term=round(pi_out.p_term, 3),
            i_term=round(pi_out.i_term, 3),
            integrator=round(pi_state.integral, 3),
            reason=pi_out.reason.value,
            vpd=vpd,
            vpd_age_s=round(vpd_age, 2) if vpd_age is not None else None,
            rh=rh,
            fan_pct=alloc_out.fan_pct,
            fan_age_s=round(alloc_out.fan_age_s, 2)
            if alloc_out.fan_age_s is not None
            else None,
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
            naive_level=disp_out.naive_level,
            held_by_hysteresis=disp_out.held_by_hysteresis,
            bucket_width_pct=round(disp_out.bucket_width, 2),
            level_hysteresis_pct=round(self._config.level_hysteresis_pct, 2),
        )

    # ------------------------------------------------------------------
    # Alert paths
    # ------------------------------------------------------------------

    async def _handle_lack_water_rising(
        self,
        now: datetime,
        vpd: float | None,
        stage: str,
        commanded_level: int | None,
        telegram: TelegramClient | None,
    ) -> None:
        log_event(
            STREAM,
            "lack_water",
            **self._scope_fields(capability_id="mist_level"),
            stage=stage,
            commanded_level=commanded_level,
            vpd=vpd,
            ts=now.isoformat(),
        )
        logger.warning("humidifier: lackWaterEvent active — tank empty")
        if telegram is None:
            return
        text = (
            "⚠ <b>Humidifier tank empty</b>\n"
            f"H7142 reports lackWaterEvent. Stage={stage}, VPD={vpd}.\n"
            "Refill the tank to resume mist."
        )
        try:
            await telegram.send_message(self._config.telegram_chat_id, text)
        except TelegramError:
            logger.exception("telegram send failed for lack-water alert")

    async def _alert_ineffective(  # noqa: PLR0913
        self,
        state: IneffectiveState,
        vpd: float | None,
        now: datetime,
        stage: str,
        vpd_band: tuple[float, float],
        commanded_level: int | None,
        telegram: TelegramClient | None,
    ) -> None:
        start_ts = state.start_ts
        start_vpd = state.start_vpd
        if start_ts is None or start_vpd is None or vpd is None:
            return
        pinned_min = (now - start_ts).total_seconds() / 60
        vpd_drop = start_vpd - vpd
        log_event(
            STREAM,
            "suspected_ineffective",
            **self._scope_fields(capability_id="mist_level"),
            pinned_minutes=round(pinned_min, 1),
            vpd_at_start=round(start_vpd, 3),
            vpd_now=round(vpd, 3),
            vpd_drop=round(vpd_drop, 3),
            stage=stage,
            upper_band_kpa=vpd_band[1],
            lower_band_kpa=vpd_band[0],
            commanded_level=commanded_level,
        )
        logger.warning(
            "humidifier suspected ineffective: commanded level=%s for %.0fm, "
            "VPD %.2f → %.2f kPa (drop %+.2f, threshold %.2f)",
            commanded_level,
            pinned_min,
            start_vpd,
            vpd,
            vpd_drop,
            self._config.ineffective_min_vpd_drop_kpa,
        )
        if telegram is None:
            return
        text = (
            "⚠ <b>Humidifier ineffective</b>\n"
            f"Commanded level {commanded_level} for {pinned_min:.0f}m; "
            f"VPD {start_vpd:.2f} → {vpd:.2f} kPa (drop {vpd_drop:+.2f}).\n"
            "Check H7142 atomization plate, tank level, mist visibility."
        )
        try:
            await telegram.send_message(self._config.telegram_chat_id, text)
        except TelegramError:
            logger.exception("telegram send failed for ineffective alert")
