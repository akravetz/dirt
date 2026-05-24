"""Climate demand, allocation, and dispatch service for the main tent."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from math import ceil
from typing import Protocol

from dirt_hwd.services.climate_actuators import (
    DEFAULT_DEHUMIDIFIER_DEVICE_ID,
    DEFAULT_THERMOFORGE_DEVICE_ID,
    ClimateActuators,
    ThermoForgeHeaterTarget,
)
from dirt_hwd.services.climate_policy import ClimatePolicy, Phase, phase_from_lights
from dirt_shared.observability import log_event
from dirt_shared.services.grow_state import GrowContext, Stage
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID

MAX_INTEGRAL_DT_S = 120.0
STREAM = "climate_controller"
DEFAULT_CANOPY_DEVICE_ID = "fan-controller"
DEFAULT_HUMIDIFIER_DEVICE_ID = "govee-h7142-main"

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ClimateTuning:
    humidifier_kp: float = 85.0
    humidifier_ki: float = 0.05
    drying_vpd_kp: float = 95.0
    drying_rh_kp: float = 3.0
    drying_ki: float = 0.05
    heater_kp: float = 22.0
    heater_ki: float = 0.04
    cooling_fan_kp: float = 10.0
    drying_fan_share: float = 0.5
    integrator_clamp_pct: float = 100.0
    heater_level_hysteresis_pct: float = 4.0
    heater_minimum_hold_s: float = 180.0
    vpd_recovery_enter_kpa: float = 0.85
    vpd_recovery_exit_kpa: float = 0.95
    vpd_recovery_enter_below_high_f: float = 0.5
    vpd_recovery_safety_margin_f: float = 0.5
    fan_drying_enter_kpa: float = 0.85
    fan_drying_exit_kpa: float = 0.95
    fan_slew_step_pct: int = 15
    fan_slew_safety_temp_margin_f: float = 0.5


@dataclass(frozen=True, slots=True)
class ClimateInput:
    now: datetime
    stage: Stage
    lights_on: bool
    temperature_f: float | None
    temperature_age_s: float | None
    rh_pct: float | None
    rh_age_s: float | None
    vpd_kpa: float | None
    vpd_age_s: float | None
    current_fan_pct: int
    current_humidifier_pct: float = 0.0
    current_dehumidifier_on: bool = False
    current_heater_level: int = 0


@dataclass(frozen=True, slots=True)
class ClimateState:
    humidifier_integral: float = 0.0
    drying_integral: float = 0.0
    heat_integral: float = 0.0
    last_tick_at: datetime | None = None
    phase: Phase | None = None
    dehumidifier_on: bool = False
    dehumidifier_last_changed_at: datetime | None = None
    heater_level: int = 0
    heater_last_changed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ClimateDecision:
    fan_duty_pct: int
    humidifier_pct: float
    dehumidifier_on: bool
    heater_level: int
    reasons: tuple[str, ...]
    constraints: tuple[str, ...]
    conflicts: tuple[str, ...]
    state: ClimateState


class _Reading(Protocol):
    value: float
    ts: datetime


class ClimateReadings(Protocol):
    async def get_latest_reading(
        self,
        metric: str,
        **kwargs: object,
    ) -> _Reading | None: ...


class ClimateGrow(Protocol):
    async def current_context(self, **kwargs: object) -> GrowContext: ...


EventLogger = Callable[..., None]
ClimateActuatorRuntimeFactory = Callable[[], "ClimateActuatorRuntime"]
AsyncCloser = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ClimateActuatorRuntime:
    actuators: ClimateActuators
    close: AsyncCloser | None = None


@dataclass(frozen=True, slots=True)
class _SensorSnapshot:
    temperature: _Reading | None
    rh: _Reading | None
    vpd: _Reading | None
    humidifier_level: _Reading | None
    dehumidifier_on: _Reading | None
    heater_level: _Reading | None


class ClimateControllerService:
    """Background loop that dispatches unified climate decisions to actuators."""

    def __init__(  # noqa: PLR0913 - composition root dependencies are explicit.
        self,
        *,
        readings: ClimateReadings,
        grow: ClimateGrow,
        actuators: ClimateActuators | None = None,
        actuator_runtime_factory: ClimateActuatorRuntimeFactory | None = None,
        policy: ClimatePolicy,
        tuning: ClimateTuning | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        poll_interval_s: float = 30.0,
        event_logger: EventLogger = log_event,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
        zone_id: str = "canopy",
        canopy_device_id: str = DEFAULT_CANOPY_DEVICE_ID,
        humidifier_device_id: str = DEFAULT_HUMIDIFIER_DEVICE_ID,
        dehumidifier_device_id: str = DEFAULT_DEHUMIDIFIER_DEVICE_ID,
        heater_device_id: str = DEFAULT_THERMOFORGE_DEVICE_ID,
        humidifier_levels: int = 9,
    ) -> None:
        if actuators is None and actuator_runtime_factory is None:
            raise ValueError("actuators or actuator_runtime_factory is required")
        self._readings = readings
        self._grow = grow
        self._actuators = actuators
        self._actuator_runtime_factory = actuator_runtime_factory
        self._policy = policy
        self._tuning = tuning or ClimateTuning()
        self._clock = clock
        self._poll_interval_s = poll_interval_s
        self._log_event = event_logger
        self._site_id = site_id
        self._tent_id = tent_id
        self._zone_id = zone_id
        self._canopy_device_id = canopy_device_id
        self._humidifier_device_id = humidifier_device_id
        self._dehumidifier_device_id = dehumidifier_device_id
        self._heater_device_id = heater_device_id
        self._humidifier_levels = humidifier_levels
        self._state = ClimateState()

    async def run(self, stop_event: asyncio.Event) -> None:
        runtime = (
            ClimateActuatorRuntime(self._actuators)
            if self._actuators is not None
            else self._actuator_runtime_factory()
        )
        assert runtime.actuators is not None  # noqa: S101 - constructor invariant.
        logger.info(
            "climate controller starting: site=%s tent=%s interval=%.1fs",
            self._site_id,
            self._tent_id,
            self._poll_interval_s,
        )
        try:
            while not stop_event.is_set():
                try:
                    await self._tick(runtime.actuators)
                except Exception as exc:
                    logger.exception("climate controller tick failed")
                    self._log_event(
                        STREAM,
                        "error",
                        **self._scope_fields(),
                        error_type=type(exc).__name__,
                        error=repr(exc),
                    )
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self._poll_interval_s,
                    )
        finally:
            if runtime.close is not None:
                await runtime.close()
            logger.info("climate controller stopped")

    async def _tick(self, actuators: ClimateActuators | None = None) -> ClimateDecision:
        active_actuators = actuators or self._actuators
        if active_actuators is None:
            raise RuntimeError("climate actuators are not initialized")

        now = self._clock()
        ctx = await self._grow.current_context(
            site_id=self._site_id,
            tent_id=self._tent_id,
        )
        snapshot, current_fan_pct = await asyncio.gather(
            self._read_sensor_snapshot(),
            active_actuators.fan.read_duty(),
        )
        inp = ClimateInput(
            now=now,
            stage=ctx.stage,
            lights_on=ctx.lights.on,
            temperature_f=_value(snapshot.temperature),
            temperature_age_s=_age_s(now, snapshot.temperature),
            rh_pct=_value(snapshot.rh),
            rh_age_s=_age_s(now, snapshot.rh),
            vpd_kpa=_value(snapshot.vpd),
            vpd_age_s=_age_s(now, snapshot.vpd),
            current_fan_pct=current_fan_pct,
            current_humidifier_pct=self._humidifier_pct(snapshot.humidifier_level),
            current_dehumidifier_on=_bool_reading(
                snapshot.dehumidifier_on,
                fallback=self._state.dehumidifier_on,
            ),
            current_heater_level=_int_reading(
                snapshot.heater_level,
                fallback=self._state.heater_level,
            ),
        )
        decision = decide_climate(self._policy, self._state, inp, self._tuning)
        self._log_tick(ctx, inp, decision)
        await self._dispatch(active_actuators, inp, decision)
        self._state = decision.state
        return decision

    async def _read_sensor_snapshot(self) -> _SensorSnapshot:
        (
            temperature,
            rh,
            vpd,
            humidifier_level,
            dehumidifier_on,
            heater_level,
        ) = await asyncio.gather(
            self._canopy_reading("temperature_f"),
            self._canopy_reading("humidity_pct"),
            self._canopy_reading("vpd_kpa"),
            self._readings.get_latest_reading(
                "humidifier_mist_level",
                site_id=self._site_id,
                tent_id=self._tent_id,
                zone_id=self._zone_id,
                device_id=self._humidifier_device_id,
                capability_id="humidifier_mist_level",
            ),
            self._readings.get_latest_reading(
                "dehumidifier_on",
                site_id=self._site_id,
                tent_id=self._tent_id,
                zone_id=self._zone_id,
                device_id=self._dehumidifier_device_id,
                capability_id="power",
            ),
            self._readings.get_latest_reading(
                "heater_heat_level",
                site_id=self._site_id,
                tent_id=self._tent_id,
                device_id=self._heater_device_id,
                capability_id="heat_level",
            ),
        )
        return _SensorSnapshot(
            temperature=temperature,
            rh=rh,
            vpd=vpd,
            humidifier_level=humidifier_level,
            dehumidifier_on=dehumidifier_on,
            heater_level=heater_level,
        )

    async def _canopy_reading(self, metric: str) -> _Reading | None:
        return await self._readings.get_latest_reading(
            metric,
            site_id=self._site_id,
            tent_id=self._tent_id,
            zone_id=self._zone_id,
            device_id=self._canopy_device_id,
            capability_id=metric,
        )

    async def _dispatch(
        self,
        actuators: ClimateActuators,
        inp: ClimateInput,
        decision: ClimateDecision,
    ) -> None:
        if decision.humidifier_pct > 0 and decision.dehumidifier_on:
            raise RuntimeError("refusing simultaneous humidifier/dehumidifier command")

        if decision.dehumidifier_on:
            await self._dispatch_humidifier(actuators, 0.0)
            await self._dispatch_dehumidifier(actuators, True)
        else:
            dehumidifier_off = await self._dispatch_dehumidifier(actuators, False)
            if dehumidifier_off:
                await self._dispatch_humidifier(actuators, decision.humidifier_pct)

        if decision.fan_duty_pct != inp.current_fan_pct:
            await self._dispatch_fan(actuators, decision.fan_duty_pct)

        target = (
            ThermoForgeHeaterTarget.off()
            if decision.heater_level == 0
            else ThermoForgeHeaterTarget.heat_level(decision.heater_level)
        )
        await self._dispatch_heater(actuators, target)

    async def _dispatch_fan(
        self,
        actuators: ClimateActuators,
        duty_pct: int,
    ) -> bool:
        try:
            await actuators.fan.set_duty(duty_pct)
        except Exception as exc:
            self._log_actuator_error("fan", exc, target_duty_pct=duty_pct)
            return False
        return True

    async def _dispatch_humidifier(
        self,
        actuators: ClimateActuators,
        intensity_pct: float,
    ) -> bool:
        try:
            await actuators.humidifier.set_intensity(intensity_pct)
        except Exception as exc:
            self._log_actuator_error(
                "humidifier",
                exc,
                target_intensity_pct=round(intensity_pct, 1),
            )
            return False
        return True

    async def _dispatch_dehumidifier(
        self,
        actuators: ClimateActuators,
        on: bool,
    ) -> bool:
        try:
            await actuators.dehumidifier.set_power(on)
        except Exception as exc:
            self._log_actuator_error("dehumidifier", exc, target_on=on)
            return False
        return True

    async def _dispatch_heater(
        self,
        actuators: ClimateActuators,
        target: ThermoForgeHeaterTarget,
    ) -> bool:
        try:
            await actuators.heater.set_target(target)
        except Exception as exc:
            self._log_actuator_error("heater", exc, target_level=target.level)
            return False
        return True

    def _log_actuator_error(
        self,
        actuator: str,
        exc: Exception,
        **fields: object,
    ) -> None:
        logger.warning(
            "climate actuator command failed: actuator=%s error=%r",
            actuator,
            exc,
        )
        self._log_event(
            STREAM,
            "actuator_error",
            **self._scope_fields(),
            actuator=actuator,
            error_type=type(exc).__name__,
            error=str(exc),
            **fields,
        )

    def _humidifier_pct(self, reading: _Reading | None) -> float:
        if reading is None:
            return 0.0
        return max(0.0, min(100.0, reading.value / self._humidifier_levels * 100.0))

    def _log_tick(
        self,
        ctx: GrowContext,
        inp: ClimateInput,
        decision: ClimateDecision,
    ) -> None:
        phase_policy = self._policy.for_stage_phase(
            ctx.stage,
            phase_from_lights(ctx.lights.on),
        )
        self._log_event(
            STREAM,
            "tick",
            **self._scope_fields(),
            stage=ctx.stage,
            lights_on=ctx.lights.on,
            minutes_until_off=round(ctx.lights.minutes_until_off, 1),
            minutes_until_on=round(ctx.lights.minutes_until_on, 1),
            temperature_f=inp.temperature_f,
            temperature_age_s=_rounded(inp.temperature_age_s),
            humidity_pct=inp.rh_pct,
            humidity_age_s=_rounded(inp.rh_age_s),
            vpd_kpa=inp.vpd_kpa,
            vpd_age_s=_rounded(inp.vpd_age_s),
            vpd_low_kpa=phase_policy.vpd_kpa.low,
            vpd_high_kpa=phase_policy.vpd_kpa.high,
            temperature_low_f=phase_policy.temperature_f.low,
            temperature_high_f=phase_policy.temperature_f.high,
            rh_max_pct=phase_policy.rh_max_pct,
            current_fan_pct=inp.current_fan_pct,
            target_fan_pct=decision.fan_duty_pct,
            current_humidifier_pct=round(inp.current_humidifier_pct, 1),
            target_humidifier_pct=round(decision.humidifier_pct, 1),
            current_dehumidifier_on=inp.current_dehumidifier_on,
            target_dehumidifier_on=decision.dehumidifier_on,
            current_heater_level=inp.current_heater_level,
            target_heater_level=decision.heater_level,
            reasons=list(decision.reasons),
            constraints=list(decision.constraints),
            conflicts=list(decision.conflicts),
        )

    def _scope_fields(self) -> dict[str, str]:
        return {
            "site_id": self._site_id,
            "tent_id": self._tent_id,
            "zone_id": self._zone_id,
            "device_id": self._canopy_device_id,
        }


@dataclass(frozen=True, slots=True)
class _SensorFreshness:
    temperature: bool
    rh: bool
    vpd: bool


@dataclass(frozen=True, slots=True)
class _Demand:
    humidifier_pct: float
    drying_pct: float
    heat_pct: float
    cooling_fan_pct: int
    humidifier_p_term: float
    drying_p_term: float
    heat_p_term: float
    rh_guard: bool
    vpd_too_low: bool
    vpd_too_high: bool
    hard_low_temp: bool
    vpd_recovery_heat: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PhaseState:
    state: ClimateState
    phase: Phase
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _DemandReasonFlags:
    rh_guard: bool
    vpd_too_high: bool
    vpd_too_low: bool
    hard_low_temp: bool
    temp_low: bool
    temp_high: bool
    vpd_recovery_heat: bool


@dataclass(frozen=True, slots=True)
class _Allocation:
    humidifier_pct: float
    dehumidifier_on: bool
    heater_level: int


@dataclass(frozen=True, slots=True)
class _UpdateContext:
    phase: Phase
    demand: _Demand
    allocation: _Allocation
    tuning: ClimateTuning


@dataclass(frozen=True, slots=True)
class _FanSlewContext:
    policy: ClimatePolicy
    inp: ClimateInput
    demand: _Demand
    target_high_f: float
    tuning: ClimateTuning


def decide_climate(
    policy: ClimatePolicy,
    state: ClimateState,
    inp: ClimateInput,
    tuning: ClimateTuning | None = None,
) -> ClimateDecision:
    """Return one pure climate-control decision and the updated controller state."""
    tuning = tuning or ClimateTuning()
    phase = phase_from_lights(inp.lights_on)
    phase_state = _reset_integrators_on_phase_change(state, inp, phase)
    state = phase_state.state
    fresh = _sensor_freshness(policy, inp)

    if not (fresh.rh and fresh.vpd):
        return _failsafe_decision(policy, inp, fresh, phase_state)

    if not fresh.temperature:
        next_state = replace(
            state,
            humidifier_integral=0.0,
            drying_integral=0.0,
            heat_integral=0.0,
            last_tick_at=inp.now,
            phase=phase,
            dehumidifier_on=False,
            heater_level=0,
        )
        return ClimateDecision(
            fan_duty_pct=policy.fan.floor_pct,
            humidifier_pct=0.0,
            dehumidifier_on=False,
            heater_level=0,
            reasons=(*phase_state.reasons, "failsafe_stale_temperature"),
            constraints=("sensor_failsafe",),
            conflicts=(),
            state=next_state,
        )

    demand = _compute_demand(policy, state, inp, tuning)
    dehumidifier_on, dehumidifier_reason = _allocate_dehumidifier(
        policy,
        state,
        inp,
        demand,
    )
    heater_level, heater_reason = _allocate_heater(policy, state, inp, demand, tuning)
    fan_pct, fan_reasons, conflicts = _allocate_fan(
        policy,
        inp,
        demand,
        heater_level=heater_level,
        tuning=tuning,
    )
    humidifier_pct, humidifier_reasons = _allocate_humidifier(
        demand,
        dehumidifier_on=dehumidifier_on,
    )

    allocation = _Allocation(
        humidifier_pct=humidifier_pct,
        dehumidifier_on=dehumidifier_on,
        heater_level=heater_level,
    )
    next_state = _updated_state(
        policy,
        state,
        inp,
        _UpdateContext(
            phase=phase,
            demand=demand,
            allocation=allocation,
            tuning=tuning,
        ),
    )
    return ClimateDecision(
        fan_duty_pct=fan_pct,
        humidifier_pct=humidifier_pct,
        dehumidifier_on=dehumidifier_on,
        heater_level=heater_level,
        reasons=(
            *phase_state.reasons,
            *demand.reasons,
            dehumidifier_reason,
            heater_reason,
            *fan_reasons,
            *humidifier_reasons,
        ),
        constraints=_constraints(demand),
        conflicts=conflicts,
        state=next_state,
    )


def _sensor_freshness(policy: ClimatePolicy, inp: ClimateInput) -> _SensorFreshness:
    return _SensorFreshness(
        temperature=_fresh(
            inp.temperature_f,
            inp.temperature_age_s,
            policy.stale.temperature_s,
        ),
        rh=_fresh(inp.rh_pct, inp.rh_age_s, policy.stale.humidity_s),
        vpd=_fresh(inp.vpd_kpa, inp.vpd_age_s, policy.stale.vpd_s),
    )


def _fresh(value: float | None, age_s: float | None, limit_s: float) -> bool:
    return value is not None and age_s is not None and age_s <= limit_s


def _reset_integrators_on_phase_change(
    state: ClimateState,
    inp: ClimateInput,
    phase: Phase,
) -> _PhaseState:
    if state.phase is None or state.phase == phase:
        return _PhaseState(state=state, phase=phase, reasons=())
    return _PhaseState(
        state=replace(
            state,
            humidifier_integral=0.0,
            drying_integral=0.0,
            heat_integral=0.0,
            phase=phase,
            heater_level=inp.current_heater_level,
        ),
        phase=phase,
        reasons=("phase_transition_bumpless",),
    )


def _failsafe_decision(
    policy: ClimatePolicy,
    inp: ClimateInput,
    fresh: _SensorFreshness,
    phase_state: _PhaseState,
) -> ClimateDecision:
    heater_level = 0
    reasons = [*phase_state.reasons, "failsafe_stale_rh_vpd"]
    if fresh.temperature and inp.temperature_f is not None:
        temp_error = policy.hard_min_temperature_f - inp.temperature_f
        if temp_error > 0:
            heater_level = max(1, min(10, ceil((45.0 + temp_error * 15.0) / 10.0)))
            reasons.append("hard_low_temperature_guard")
    next_state = replace(
        phase_state.state,
        humidifier_integral=0.0,
        drying_integral=0.0,
        heat_integral=heater_level * 10.0,
        last_tick_at=inp.now,
        phase=phase_state.phase,
        dehumidifier_on=False,
        heater_level=heater_level,
    )
    return ClimateDecision(
        fan_duty_pct=policy.fan.floor_pct,
        humidifier_pct=0.0,
        dehumidifier_on=False,
        heater_level=heater_level,
        reasons=tuple(reasons),
        constraints=("sensor_failsafe",),
        conflicts=(),
        state=next_state,
    )


def _compute_demand(
    policy: ClimatePolicy,
    state: ClimateState,
    inp: ClimateInput,
    tuning: ClimateTuning,
) -> _Demand:
    phase_policy = policy.for_stage_phase(inp.stage, phase_from_lights(inp.lights_on))
    assert inp.temperature_f is not None  # noqa: S101 - narrowed by caller.
    assert inp.rh_pct is not None  # noqa: S101 - narrowed by caller.
    assert inp.vpd_kpa is not None  # noqa: S101 - narrowed by caller.

    dt_s = _dt_s(state, inp.now)
    rh_guard = inp.rh_pct > phase_policy.rh_max_pct
    vpd_too_high = inp.vpd_kpa > phase_policy.vpd_kpa.high
    vpd_too_low = inp.vpd_kpa < phase_policy.vpd_kpa.low
    hard_low_temp = inp.temperature_f < policy.hard_min_temperature_f

    humidifier_error = max(0.0, inp.vpd_kpa - phase_policy.vpd_kpa.high)
    drying_vpd_error = max(0.0, phase_policy.vpd_kpa.low - inp.vpd_kpa)
    drying_rh_error = max(0.0, inp.rh_pct - phase_policy.rh_max_pct)
    heat_error = _heat_error(policy, inp, phase_policy.temperature_f.low)
    vpd_recovery_heat = _vpd_recovery_heat_requested(
        state,
        inp,
        phase_policy.temperature_f.high,
        tuning,
    )
    if vpd_recovery_heat and heat_error <= 0:
        heat_error = max(0.0, phase_policy.temperature_f.high - inp.temperature_f)

    humidifier_integral = _integral(
        state.humidifier_integral,
        humidifier_error,
        dt_s,
        tuning.humidifier_ki,
        tuning,
    )
    drying_integral = _integral(
        state.drying_integral,
        drying_vpd_error + drying_rh_error,
        dt_s,
        tuning.drying_ki,
        tuning,
    )
    heat_integral = _integral(
        state.heat_integral,
        heat_error,
        dt_s,
        tuning.heater_ki,
        tuning,
    )

    humidifier_p = tuning.humidifier_kp * humidifier_error
    drying_p = (
        tuning.drying_vpd_kp * drying_vpd_error + tuning.drying_rh_kp * drying_rh_error
    )
    heat_p = _heat_p_term(policy, inp, heat_error, hard_low_temp, tuning)

    reasons = _demand_reasons(
        _DemandReasonFlags(
            rh_guard=rh_guard,
            vpd_too_high=vpd_too_high,
            vpd_too_low=vpd_too_low,
            hard_low_temp=hard_low_temp,
            temp_low=inp.temperature_f < phase_policy.temperature_f.low,
            temp_high=inp.temperature_f > phase_policy.temperature_f.high,
            vpd_recovery_heat=vpd_recovery_heat,
        )
    )
    return _Demand(
        humidifier_pct=_pct(humidifier_p + humidifier_integral)
        if humidifier_error > 0
        else 0.0,
        drying_pct=_pct(drying_p + drying_integral)
        if drying_vpd_error > 0 or drying_rh_error > 0
        else 0.0,
        heat_pct=_pct(heat_p + heat_integral) if heat_error > 0 else 0.0,
        cooling_fan_pct=_cooling_fan_pct(
            policy,
            inp,
            phase_policy.temperature_f.high,
            tuning,
        ),
        humidifier_p_term=humidifier_p,
        drying_p_term=drying_p,
        heat_p_term=heat_p,
        rh_guard=rh_guard,
        vpd_too_high=vpd_too_high,
        vpd_too_low=vpd_too_low,
        hard_low_temp=hard_low_temp,
        vpd_recovery_heat=vpd_recovery_heat,
        reasons=reasons,
    )


def _heat_error(policy: ClimatePolicy, inp: ClimateInput, target_low_f: float) -> float:
    assert inp.temperature_f is not None  # noqa: S101 - narrowed by caller.
    if inp.temperature_f < policy.hard_min_temperature_f:
        return policy.hard_min_temperature_f - inp.temperature_f
    return max(0.0, target_low_f - inp.temperature_f)


def _vpd_recovery_heat_requested(
    state: ClimateState,
    inp: ClimateInput,
    target_high_f: float,
    tuning: ClimateTuning,
) -> bool:
    assert inp.temperature_f is not None  # noqa: S101 - narrowed by caller.
    assert inp.vpd_kpa is not None  # noqa: S101 - narrowed by caller.
    if inp.temperature_f >= target_high_f + tuning.vpd_recovery_safety_margin_f:
        return False
    current = _current_heater_level(state, inp)
    if current > 0 and inp.vpd_kpa < tuning.vpd_recovery_exit_kpa:
        return True
    enter_below = target_high_f - tuning.vpd_recovery_enter_below_high_f
    return (
        inp.vpd_kpa < tuning.vpd_recovery_enter_kpa and inp.temperature_f < enter_below
    )


def _heat_p_term(
    policy: ClimatePolicy,
    inp: ClimateInput,
    heat_error: float,
    hard_low_temp: bool,
    tuning: ClimateTuning,
) -> float:
    if heat_error <= 0:
        return 0.0
    if hard_low_temp:
        return max(55.0, 45.0 + heat_error * 15.0)
    return tuning.heater_kp * heat_error


def _cooling_fan_pct(
    policy: ClimatePolicy,
    inp: ClimateInput,
    target_high_f: float,
    tuning: ClimateTuning,
) -> int:
    assert inp.temperature_f is not None  # noqa: S101 - narrowed by caller.
    if inp.temperature_f <= target_high_f:
        return 0
    max_elevated = policy.fan.max_pct - policy.fan.floor_pct
    return round(
        min(
            max_elevated,
            (inp.temperature_f - target_high_f) * tuning.cooling_fan_kp,
        )
    )


def _demand_reasons(flags: _DemandReasonFlags) -> tuple[str, ...]:
    reasons: list[str] = []
    if flags.rh_guard:
        reasons.append("hard_rh_guard")
    if flags.hard_low_temp:
        reasons.append("hard_low_temperature_guard")
    elif flags.temp_low:
        reasons.append("temperature_trim_heat")
    if flags.vpd_recovery_heat:
        reasons.append("vpd_recovery_heat")
    if flags.vpd_too_high:
        reasons.append("vpd_split_humidify")
    if flags.vpd_too_low:
        reasons.append("vpd_split_dry")
    if flags.temp_high:
        reasons.append("temperature_trim_cool")
    return tuple(reasons or ("hold_in_band",))


def _allocate_dehumidifier(
    policy: ClimatePolicy,
    state: ClimateState,
    inp: ClimateInput,
    demand: _Demand,
) -> tuple[bool, str]:
    current_on = _current_dehumidifier_on(state, inp)
    requested_on = _dehumidifier_requested(policy, inp, demand, current_on)
    if requested_on == current_on:
        return current_on, "dehumidifier_on" if current_on else "dehumidifier_off"

    changed_at = state.dehumidifier_last_changed_at
    elapsed_s = None if changed_at is None else (inp.now - changed_at).total_seconds()
    if (
        requested_on
        and elapsed_s is not None
        and elapsed_s < policy.dehumidifier.minimum_off_s
    ):
        return False, "dehumidifier_min_off_hold"
    if (
        not requested_on
        and elapsed_s is not None
        and elapsed_s < policy.dehumidifier.minimum_on_s
    ):
        return True, "dehumidifier_min_on_hold"
    reason = "dehumidifier_turn_on" if requested_on else "dehumidifier_turn_off"
    return requested_on, reason


def _current_dehumidifier_on(state: ClimateState, inp: ClimateInput) -> bool:
    if state.dehumidifier_last_changed_at is None:
        return inp.current_dehumidifier_on
    return state.dehumidifier_on


def _dehumidifier_requested(
    policy: ClimatePolicy,
    inp: ClimateInput,
    demand: _Demand,
    current_on: bool,
) -> bool:
    phase_policy = policy.for_stage_phase(inp.stage, phase_from_lights(inp.lights_on))
    assert inp.rh_pct is not None  # noqa: S101 - narrowed by caller.
    assert inp.vpd_kpa is not None  # noqa: S101 - narrowed by caller.
    if current_on:
        rh_recovered = (
            inp.rh_pct < phase_policy.rh_max_pct - policy.dehumidifier.rh_deadband_pct
        )
        vpd_recovered = (
            inp.vpd_kpa
            > phase_policy.vpd_kpa.low + policy.dehumidifier.vpd_deadband_kpa
        )
        return not (rh_recovered and vpd_recovered)
    return (
        demand.rh_guard
        or inp.vpd_kpa < phase_policy.vpd_kpa.low - policy.dehumidifier.vpd_deadband_kpa
    )


def _allocate_heater(
    policy: ClimatePolicy,
    state: ClimateState,
    inp: ClimateInput,
    demand: _Demand,
    tuning: ClimateTuning,
) -> tuple[int, str]:
    phase_policy = policy.for_stage_phase(inp.stage, phase_from_lights(inp.lights_on))
    assert inp.temperature_f is not None  # noqa: S101 - narrowed by caller.
    safety_high_f = (
        phase_policy.temperature_f.high + tuning.vpd_recovery_safety_margin_f
        if demand.vpd_recovery_heat
        else phase_policy.temperature_f.high
    )
    current = _current_heater_level(state, inp)
    if inp.temperature_f >= safety_high_f:
        return 0, "heater_safety_off"
    if demand.vpd_recovery_heat and demand.heat_pct <= 0 and current > 0:
        return current, "heater_vpd_recovery_maintenance"
    if demand.heat_pct <= 0:
        return 0, "heater_safety_off"

    requested = _heat_level(demand.heat_pct)
    if (
        demand.vpd_recovery_heat
        and inp.temperature_f >= phase_policy.temperature_f.high
        and requested > current
    ):
        return current, "heater_vpd_recovery_maintenance"
    if demand.hard_low_temp and requested > current:
        return requested, "heater_hard_low_step_up"
    if current == 0:
        return requested, "heater_level_request"
    if abs(requested * 10.0 - current * 10.0) < tuning.heater_level_hysteresis_pct:
        return current, "heater_level_hysteresis_hold"
    if _within_heater_hold(state, inp, tuning):
        return current, "heater_min_hold"
    return requested, "heater_level_request"


def _current_heater_level(state: ClimateState, inp: ClimateInput) -> int:
    if state.heater_last_changed_at is None:
        return inp.current_heater_level
    return state.heater_level


def _heat_level(heat_pct: float) -> int:
    if heat_pct <= 0:
        return 0
    return max(1, min(10, ceil(heat_pct / 10.0)))


def _within_heater_hold(
    state: ClimateState,
    inp: ClimateInput,
    tuning: ClimateTuning,
) -> bool:
    if state.heater_last_changed_at is None:
        return False
    elapsed_s = (inp.now - state.heater_last_changed_at).total_seconds()
    return elapsed_s < tuning.heater_minimum_hold_s


def _allocate_fan(
    policy: ClimatePolicy,
    inp: ClimateInput,
    demand: _Demand,
    *,
    heater_level: int,
    tuning: ClimateTuning,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    phase_policy = policy.for_stage_phase(inp.stage, phase_from_lights(inp.lights_on))
    max_elevated = policy.fan.max_pct - policy.fan.floor_pct
    drying_fan_pct = round(
        min(max_elevated, demand.drying_pct * tuning.drying_fan_share)
    )
    cooling_fan_pct = demand.cooling_fan_pct
    reasons: list[str] = []
    conflicts: list[str] = []

    drying_fan_pct, hysteresis_reasons = _drying_fan_pct_after_hysteresis(
        policy,
        inp,
        demand,
        drying_fan_pct,
        tuning,
    )
    reasons.extend(hysteresis_reasons)

    if heater_level > 0 and cooling_fan_pct > 0:
        cooling_fan_pct = 0
        conflicts.append("heater_elevated_fan_cooling_suppressed")
    if (
        heater_level > 0
        and inp.current_fan_pct > policy.fan.floor_pct
        and not (demand.rh_guard or demand.vpd_too_low)
    ):
        conflicts.append("heater_elevated_fan_cooling_suppressed")
    if demand.vpd_recovery_heat and not demand.rh_guard:
        drying_fan_pct = 0
    if heater_level > 0 and drying_fan_pct > 0:
        if demand.rh_guard or demand.vpd_too_low:
            reasons.append("heater_with_elevated_fan_drying_allowed")
        else:
            drying_fan_pct = 0
            conflicts.append("heater_elevated_fan_non_safety_suppressed")

    if _near_low_temperature(policy, inp) and not demand.rh_guard:
        drying_fan_pct = 0
    elevated = max(cooling_fan_pct, drying_fan_pct)
    if elevated > 0:
        fan_reason = (
            "fan_elevated_for_drying"
            if drying_fan_pct >= cooling_fan_pct
            else "fan_elevated_for_cooling"
        )
        reasons.append(fan_reason)
    else:
        reasons.append("fan_floor")
    requested = policy.fan.floor_pct + elevated
    fan_pct = _slew_fan_target(
        _FanSlewContext(
            policy=policy,
            inp=inp,
            demand=demand,
            target_high_f=phase_policy.temperature_f.high,
            tuning=tuning,
        ),
        target_pct=requested,
    )
    if fan_pct != requested:
        reasons.append("fan_slew_limited")
    return fan_pct, tuple(reasons), tuple(conflicts)


def _drying_fan_pct_after_hysteresis(
    policy: ClimatePolicy,
    inp: ClimateInput,
    demand: _Demand,
    requested_pct: int,
    tuning: ClimateTuning,
) -> tuple[int, tuple[str, ...]]:
    if demand.rh_guard:
        return requested_pct, ()
    if demand.vpd_recovery_heat or inp.vpd_kpa is None:
        return 0, ()

    current_elevated = max(0, inp.current_fan_pct - policy.fan.floor_pct)
    if current_elevated > 0 and inp.vpd_kpa < tuning.fan_drying_exit_kpa:
        return max(requested_pct, current_elevated), ("fan_drying_hysteresis_hold",)
    if inp.vpd_kpa < tuning.fan_drying_enter_kpa:
        return requested_pct, ()
    return 0, ()


def _slew_fan_target(ctx: _FanSlewContext, *, target_pct: int) -> int:
    if _fan_slew_bypassed(ctx, target_pct=target_pct):
        return target_pct

    current = max(
        ctx.policy.fan.floor_pct,
        min(ctx.policy.fan.max_pct, ctx.inp.current_fan_pct),
    )
    delta = target_pct - current
    if abs(delta) <= ctx.tuning.fan_slew_step_pct:
        return target_pct
    step = ctx.tuning.fan_slew_step_pct if delta > 0 else -ctx.tuning.fan_slew_step_pct
    return current + step


def _fan_slew_bypassed(ctx: _FanSlewContext, *, target_pct: int) -> bool:
    if ctx.demand.rh_guard or ctx.demand.hard_low_temp:
        return True
    if ctx.inp.temperature_f is not None and (
        ctx.inp.temperature_f
        >= ctx.target_high_f + ctx.tuning.fan_slew_safety_temp_margin_f
    ):
        return True
    return target_pct == ctx.inp.current_fan_pct


def _near_low_temperature(policy: ClimatePolicy, inp: ClimateInput) -> bool:
    if inp.temperature_f is None:
        return True
    return inp.temperature_f <= policy.hard_min_temperature_f


def _allocate_humidifier(
    demand: _Demand,
    *,
    dehumidifier_on: bool,
) -> tuple[float, tuple[str, ...]]:
    if demand.rh_guard:
        return 0.0, ("humidifier_forced_off_high_rh",)
    if dehumidifier_on:
        return 0.0, ("humidifier_forced_off_dehumidifier_on",)
    if demand.drying_pct > 0:
        return 0.0, ("humidifier_forced_off_drying",)
    if demand.humidifier_pct <= 0:
        return 0.0, ("humidifier_off",)
    return demand.humidifier_pct, ("humidifier_request",)


def _updated_state(
    policy: ClimatePolicy,
    state: ClimateState,
    inp: ClimateInput,
    ctx: _UpdateContext,
) -> ClimateState:
    allocation = ctx.allocation
    demand = ctx.demand
    tuning = ctx.tuning
    dehumidifier_changed = allocation.dehumidifier_on != _current_dehumidifier_on(
        state,
        inp,
    )
    heater_changed = allocation.heater_level != _current_heater_level(state, inp)
    humidifier_integral = _track_integral(
        demand.humidifier_p_term,
        allocation.humidifier_pct,
        tuning,
    )
    dehumidifier_last_changed_at = (
        inp.now if dehumidifier_changed else state.dehumidifier_last_changed_at
    )
    heater_last_changed_at = inp.now if heater_changed else state.heater_last_changed_at
    return replace(
        state,
        humidifier_integral=humidifier_integral,
        drying_integral=_track_integral(
            demand.drying_p_term,
            _delivered_drying_pct(policy, demand, allocation.dehumidifier_on, tuning),
            tuning,
        ),
        heat_integral=_track_integral(
            demand.heat_p_term,
            allocation.heater_level * 10.0,
            tuning,
        ),
        last_tick_at=inp.now,
        phase=ctx.phase,
        dehumidifier_on=allocation.dehumidifier_on,
        dehumidifier_last_changed_at=dehumidifier_last_changed_at,
        heater_level=allocation.heater_level,
        heater_last_changed_at=heater_last_changed_at,
    )


def _delivered_drying_pct(
    policy: ClimatePolicy,
    demand: _Demand,
    dehumidifier_on: bool,
    tuning: ClimateTuning,
) -> float:
    fan_delivery = min(
        policy.fan.max_pct - policy.fan.floor_pct,
        demand.drying_pct * tuning.drying_fan_share,
    )
    dehumidifier_delivery = 60.0 if dehumidifier_on else 0.0
    return min(100.0, fan_delivery + dehumidifier_delivery)


def _constraints(demand: _Demand) -> tuple[str, ...]:
    constraints: list[str] = []
    if demand.hard_low_temp:
        constraints.append("hard_low_temperature")
    if demand.rh_guard:
        constraints.append("hard_rh")
    return tuple(constraints)


def _dt_s(state: ClimateState, now: datetime) -> float:
    if state.last_tick_at is None:
        return 0.0
    return max(0.0, min((now - state.last_tick_at).total_seconds(), MAX_INTEGRAL_DT_S))


def _integral(
    previous: float,
    error: float,
    dt_s: float,
    ki: float,
    tuning: ClimateTuning,
) -> float:
    if error <= 0:
        return 0.0
    return _clamp(
        previous + ki * error * dt_s,
        -tuning.integrator_clamp_pct,
        tuning.integrator_clamp_pct,
    )


def _track_integral(
    p_term: float,
    delivered_pct: float,
    tuning: ClimateTuning,
) -> float:
    return _clamp(
        delivered_pct - p_term,
        -tuning.integrator_clamp_pct,
        tuning.integrator_clamp_pct,
    )


def _pct(value: float) -> float:
    return _clamp(value, 0.0, 100.0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _value(reading: _Reading | None) -> float | None:
    return None if reading is None else reading.value


def _age_s(now: datetime, reading: _Reading | None) -> float | None:
    if reading is None:
        return None
    return max(0.0, (now - reading.ts).total_seconds())


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _bool_reading(reading: _Reading | None, *, fallback: bool) -> bool:
    if reading is None:
        return fallback
    return reading.value >= 0.5


def _int_reading(reading: _Reading | None, *, fallback: int) -> int:
    if reading is None:
        return fallback
    return max(0, min(10, round(reading.value)))
