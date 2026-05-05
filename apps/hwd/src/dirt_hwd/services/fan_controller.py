"""Supervisory fan trim for humidity/VPD control.

This is deliberately not part of the humidifier PI controller. The humidifier
loop owns the "too dry" side by adding moisture; this loop owns the
"too humid / VPD too low" side by trimming exhaust fan duty. Pre-lights-off
dry-down is feedforward: lights-off is scheduled, so the controller starts
drying the tent before the temperature crash makes VPD tank.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

import httpx

from dirt_shared.config import FanTrimConfig
from dirt_shared.observability import log_event
from dirt_shared.services.fan_node import FanNodeClient, FanNodeError
from dirt_shared.services.grow_state import GrowStateService, LightsState
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID

logger = logging.getLogger(__name__)

STREAM = "fan_controller"


@dataclass(frozen=True)
class FanTrimState:
    last_change_ts: datetime | None = None
    recover_since: datetime | None = None


@dataclass(frozen=True)
class FanTrimInput:
    now: datetime
    current_pct: int
    vpd: float | None
    vpd_age_s: float | None
    rh: float | None
    rh_age_s: float | None
    vpd_band: tuple[float, float]
    rh_band: tuple[float, float]
    lights: LightsState


@dataclass(frozen=True)
class FanTrimDecision:
    target_pct: int
    reason: str
    new_state: FanTrimState


def _clamp_pct(value: int, cfg: FanTrimConfig) -> int:
    return max(cfg.min_pct, min(cfg.max_pct, value))


def _sensor_unavailable(
    value: float | None, age_s: float | None, cfg: FanTrimConfig
) -> bool:
    return value is None or age_s is None or age_s > cfg.sensor_stale_s


def _can_step_after(
    state: FanTrimState,
    now: datetime,
    interval_s: int,
) -> bool:
    if state.last_change_ts is None:
        return True
    return (now - state.last_change_ts).total_seconds() >= interval_s


def _can_step(state: FanTrimState, now: datetime, cfg: FanTrimConfig) -> bool:
    return _can_step_after(state, now, cfg.step_interval_s)


def _changed(state: FanTrimState, now: datetime) -> FanTrimState:
    return FanTrimState(last_change_ts=now, recover_since=None)


def decide_fan_trim(
    cfg: FanTrimConfig,
    state: FanTrimState,
    inp: FanTrimInput,
) -> FanTrimDecision:
    """Return the next fan duty target for one tick.

    Rules, in priority order:
      1. Enforce configured min/max.
      2. Hold on missing/stale VPD or RH.
      3. Feedforward dry-down before lights-off: jump to the drydown floor.
      4. If RH is over ceiling or VPD is below floor, step fan up.
      5. If VPD is high and RH is not high, back off exhaust quickly.
      6. If recovered for long enough, step down toward the minimum.
    """
    current = inp.current_pct
    clamped = _clamp_pct(current, cfg)
    if clamped != current:
        return FanTrimDecision(
            target_pct=clamped,
            reason="enforce_bounds",
            new_state=_changed(state, inp.now),
        )

    if _sensor_unavailable(inp.vpd, inp.vpd_age_s, cfg) or _sensor_unavailable(
        inp.rh,
        inp.rh_age_s,
        cfg,
    ):
        return FanTrimDecision(
            target_pct=current,
            reason="hold_stale_sensor",
            new_state=replace(state, recover_since=None),
        )
    assert inp.vpd is not None  # noqa: S101 - narrowed by stale guard
    assert inp.rh is not None  # noqa: S101 - narrowed by stale guard

    vpd_lo, vpd_hi = inp.vpd_band
    _rh_lo, rh_hi = inp.rh_band

    drydown_threshold = rh_hi - cfg.drydown_rh_buffer_pct
    drydown_active = (
        inp.lights.on
        and inp.lights.minutes_until_off <= cfg.drydown_minutes
        and inp.rh > drydown_threshold
    )
    if drydown_active and current < cfg.drydown_pct:
        return FanTrimDecision(
            target_pct=_clamp_pct(cfg.drydown_pct, cfg),
            reason="pre_lights_off_drydown",
            new_state=_changed(state, inp.now),
        )

    too_humid = inp.rh > rh_hi
    vpd_too_low = inp.vpd < vpd_lo
    if too_humid or vpd_too_low:
        if not _can_step(state, inp.now, cfg):
            return FanTrimDecision(
                target_pct=current,
                reason="hold_rate_limited",
                new_state=replace(state, recover_since=None),
            )
        reason = "humid_trim_up_high_rh" if too_humid else "humid_trim_up_low_vpd"
        return FanTrimDecision(
            target_pct=_clamp_pct(current + cfg.step_pct, cfg),
            reason=reason,
            new_state=_changed(state, inp.now),
        )

    vpd_too_high = inp.vpd > vpd_hi + cfg.high_vpd_margin_kpa
    if vpd_too_high and inp.rh < rh_hi and current > cfg.min_pct:
        if not _can_step_after(state, inp.now, cfg.high_vpd_step_interval_s):
            return FanTrimDecision(
                target_pct=current,
                reason="hold_rate_limited",
                new_state=replace(state, recover_since=None),
            )
        return FanTrimDecision(
            target_pct=_clamp_pct(current - cfg.high_vpd_step_pct, cfg),
            reason="trim_down_high_vpd",
            new_state=_changed(state, inp.now),
        )

    recovered = (
        inp.rh < rh_hi - cfg.recover_rh_buffer_pct
        and inp.vpd > vpd_lo + cfg.recover_vpd_margin_kpa
    )
    if not recovered:
        return FanTrimDecision(
            target_pct=current,
            reason="hold_in_band",
            new_state=replace(state, recover_since=None),
        )

    recover_since = state.recover_since or inp.now
    if (inp.now - recover_since).total_seconds() < cfg.recover_hold_s:
        return FanTrimDecision(
            target_pct=current,
            reason="hold_recovering",
            new_state=replace(state, recover_since=recover_since),
        )
    if current <= cfg.min_pct:
        return FanTrimDecision(
            target_pct=current,
            reason="hold_at_min",
            new_state=replace(state, recover_since=recover_since),
        )
    if not _can_step(state, inp.now, cfg):
        return FanTrimDecision(
            target_pct=current,
            reason="hold_rate_limited",
            new_state=replace(state, recover_since=recover_since),
        )
    return FanTrimDecision(
        target_pct=_clamp_pct(current - cfg.step_pct, cfg),
        reason="trim_down_recovered",
        new_state=_changed(state, inp.now),
    )


class _HttpFactory(Protocol):
    def __call__(self) -> httpx.AsyncClient: ...


class FanTrimLoopService:
    """Background loop that turns fan-trim decisions into ESP32 API calls."""

    def __init__(  # noqa: PLR0913 - composition root params plus explicit hardware scope.
        self,
        config: FanTrimConfig,
        *,
        readings: ReadingsService,
        grow: GrowStateService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        http_factory: _HttpFactory = httpx.AsyncClient,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
        device_id: str = "fan-controller",
    ) -> None:
        self._config = config
        self._readings = readings
        self._grow = grow
        self._clock = clock
        self._http_factory = http_factory
        self._site_id = site_id
        self._tent_id = tent_id
        self._zone_id = "canopy"
        self._device_id = device_id

    def _scope_fields(self, *, capability_id: str | None = None) -> dict[str, str]:
        fields = {
            "site_id": self._site_id,
            "tent_id": self._tent_id,
            "zone_id": self._zone_id,
            "device_id": self._device_id,
        }
        if capability_id is not None:
            fields["capability_id"] = capability_id
        return fields

    async def run(self, stop_event: asyncio.Event) -> None:
        cfg = self._config
        logger.info(
            "fan trim loop starting: base_url=%s min=%d max=%d step=%d "
            "drydown=%d%%/%dmin interval=%ds",
            cfg.base_url,
            cfg.min_pct,
            cfg.max_pct,
            cfg.step_pct,
            cfg.drydown_pct,
            cfg.drydown_minutes,
            cfg.poll_interval,
        )

        state = FanTrimState()

        async with self._http_factory() as http:
            fan = FanNodeClient(http, base_url=cfg.base_url)
            while not stop_event.is_set():
                try:
                    now = self._clock()
                    ctx = await self._grow.current_context(
                        site_id=self._site_id,
                        tent_id=self._tent_id,
                    )

                    vpd_reading, rh_reading = await asyncio.gather(
                        self._readings.get_latest_reading(
                            "vpd_kpa",
                            site_id=self._site_id,
                            tent_id=self._tent_id,
                            zone_id=self._zone_id,
                            device_id=self._device_id,
                            capability_id="vpd_kpa",
                        ),
                        self._readings.get_latest_reading(
                            "humidity_pct",
                            site_id=self._site_id,
                            tent_id=self._tent_id,
                            zone_id=self._zone_id,
                            device_id=self._device_id,
                            capability_id="humidity_pct",
                        ),
                    )
                    fan_state = await fan.get_state()
                    current = int(fan_state["set_duty_pct"])

                    vpd_age = (
                        (now - vpd_reading.ts).total_seconds()
                        if vpd_reading is not None
                        else None
                    )
                    rh_age = (
                        (now - rh_reading.ts).total_seconds()
                        if rh_reading is not None
                        else None
                    )
                    decision = decide_fan_trim(
                        cfg,
                        state,
                        FanTrimInput(
                            now=now,
                            current_pct=current,
                            vpd=vpd_reading.value if vpd_reading else None,
                            vpd_age_s=vpd_age,
                            rh=rh_reading.value if rh_reading else None,
                            rh_age_s=rh_age,
                            vpd_band=ctx.targets["vpd_kpa"],
                            rh_band=ctx.targets["humidity_pct"],
                            lights=ctx.lights,
                        ),
                    )

                    if decision.target_pct != current:
                        ack = await fan.set_duty(decision.target_pct)
                        log_event(
                            STREAM,
                            "state_change",
                            **self._scope_fields(capability_id="fan_duty_pct"),
                            old_pct=current,
                            new_pct=ack,
                            target_pct=decision.target_pct,
                            reason=decision.reason,
                            stage=ctx.stage,
                            vpd=vpd_reading.value if vpd_reading else None,
                            rh=rh_reading.value if rh_reading else None,
                            lower_band_kpa=ctx.targets["vpd_kpa"][0],
                            upper_band_kpa=ctx.targets["vpd_kpa"][1],
                            rh_ceiling_pct=ctx.targets["humidity_pct"][1],
                            lights_on=ctx.lights.on,
                            minutes_until_off=round(ctx.lights.minutes_until_off, 1),
                            minutes_until_on=round(ctx.lights.minutes_until_on, 1),
                        )
                    state = decision.new_state

                    log_event(
                        STREAM,
                        "tick",
                        **self._scope_fields(capability_id="fan_duty_pct"),
                        current_pct=current,
                        target_pct=decision.target_pct,
                        reason=decision.reason,
                        stage=ctx.stage,
                        vpd=vpd_reading.value if vpd_reading else None,
                        vpd_age_s=round(vpd_age, 2) if vpd_age is not None else None,
                        rh=rh_reading.value if rh_reading else None,
                        rh_age_s=round(rh_age, 2) if rh_age is not None else None,
                        lower_band_kpa=ctx.targets["vpd_kpa"][0],
                        upper_band_kpa=ctx.targets["vpd_kpa"][1],
                        rh_ceiling_pct=ctx.targets["humidity_pct"][1],
                        lights_on=ctx.lights.on,
                        minutes_until_off=round(ctx.lights.minutes_until_off, 1),
                        minutes_until_on=round(ctx.lights.minutes_until_on, 1),
                    )

                except FanNodeError as exc:
                    logger.warning("fan trim node error: %s", exc)
                    log_event(
                        STREAM,
                        "error",
                        **self._scope_fields(),
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                except Exception as exc:
                    logger.exception("fan trim loop error")
                    log_event(
                        STREAM,
                        "error",
                        **self._scope_fields(),
                        error_type=type(exc).__name__,
                        error=repr(exc),
                    )

                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=cfg.poll_interval)

        logger.info("fan trim loop stopped")
