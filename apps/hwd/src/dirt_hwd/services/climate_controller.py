"""Climate demand, allocation, and dispatch service for the main tent."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
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
HEATER_SAFETY_MAX_F = 80.0

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
    cooling_fan_ki: float = 0.05
    drying_fan_share: float = 0.5
    integrator_clamp_pct: float = 100.0
    heater_level_hysteresis_pct: float = 5.0
    heater_minimum_dwell_s: float = 300.0
    fan_drying_enter_kpa: float = 0.85
    fan_drying_exit_kpa: float = 0.95
    fan_drying_rh_enter_below_max_pct: float = 1.5
    fan_drying_rh_exit_below_max_pct: float = 4.0
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
    cooling_fan_integral: float = 0.0
    last_tick_at: datetime | None = None
    phase: Phase | None = None
    dehumidifier_on: bool = False
    dehumidifier_last_changed_at: datetime | None = None
    heater_level: int = 0
    heater_last_changed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class VpdControlDiagnostics:
    band_low_kpa: float
    band_high_kpa: float
    selected_setpoint_kpa: float
    selected_edge: str
    control_vpd_kpa: float | None
    error_kpa: float | None


@dataclass(frozen=True, slots=True)
class ClimateDemandDiagnostics:
    raw_humidifier_pct: float
    raw_drying_pct: float
    raw_heat_pct: float
    raw_cooling_fan_pct: float
    clipped_humidifier_pct: float
    clipped_drying_pct: float
    clipped_heat_pct: float
    clipped_cooling_fan_pct: float
    delivered_humidifier_pct: float
    delivered_drying_pct: float
    delivered_heat_pct: float
    delivered_cooling_fan_pct: float
    anti_windup_reasons: tuple[str, ...]
    dehumidifier_allocation_reason: str | None = None
    dehumidifier_limit_reason: str | None = None
    heater_allocation_reason: str | None = None
    heater_limit_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ClimateDecision:
    fan_duty_pct: int
    humidifier_pct: float
    dehumidifier_on: bool
    heater_level: int
    active_mode: str
    vpd: VpdControlDiagnostics
    demand: ClimateDemandDiagnostics
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
            active_mode=decision.active_mode,
            vpd_band_low_kpa=decision.vpd.band_low_kpa,
            vpd_band_high_kpa=decision.vpd.band_high_kpa,
            vpd_selected_setpoint_kpa=decision.vpd.selected_setpoint_kpa,
            vpd_selected_edge=decision.vpd.selected_edge,
            control_vpd_kpa=decision.vpd.control_vpd_kpa,
            vpd_error_kpa=_rounded(decision.vpd.error_kpa),
            raw_humidifier_demand_pct=round(decision.demand.raw_humidifier_pct, 1),
            raw_drying_demand_pct=round(decision.demand.raw_drying_pct, 1),
            raw_heat_demand_pct=round(decision.demand.raw_heat_pct, 1),
            raw_cooling_fan_demand_pct=round(
                decision.demand.raw_cooling_fan_pct,
                1,
            ),
            clipped_humidifier_demand_pct=round(
                decision.demand.clipped_humidifier_pct,
                1,
            ),
            clipped_drying_demand_pct=round(
                decision.demand.clipped_drying_pct,
                1,
            ),
            clipped_heat_demand_pct=round(decision.demand.clipped_heat_pct, 1),
            clipped_cooling_fan_demand_pct=round(
                decision.demand.clipped_cooling_fan_pct,
                1,
            ),
            delivered_humidifier_pct=round(
                decision.demand.delivered_humidifier_pct,
                1,
            ),
            delivered_drying_pct=round(decision.demand.delivered_drying_pct, 1),
            delivered_heat_pct=round(decision.demand.delivered_heat_pct, 1),
            delivered_cooling_fan_pct=round(
                decision.demand.delivered_cooling_fan_pct,
                1,
            ),
            anti_windup_reasons=list(decision.demand.anti_windup_reasons),
            dehumidifier_allocation_reason=decision.demand.dehumidifier_allocation_reason,
            dehumidifier_limit_reason=decision.demand.dehumidifier_limit_reason,
            heater_allocation_reason=decision.demand.heater_allocation_reason,
            heater_limit_reason=decision.demand.heater_limit_reason,
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
    raw_humidifier_pct: float
    raw_drying_pct: float
    raw_heat_pct: float
    raw_cooling_fan_pct: float
    humidifier_pct: float
    drying_pct: float
    heat_pct: float
    cooling_fan_pct: int
    humidifier_p_term: float
    drying_p_term: float
    heat_p_term: float
    cooling_fan_p_term: float
    rh_guard: bool
    vpd_too_low: bool
    vpd_too_high: bool
    hard_low_temp: bool
    heater_safety_cap: bool
    dehumidifier_owns_vpd: bool
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
    dehumidifier_owns_vpd: bool
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
    fan_pct: int
    fan_reasons: tuple[str, ...]
    tuning: ClimateTuning


@dataclass(frozen=True, slots=True)
class _FanSlewContext:
    policy: ClimatePolicy
    inp: ClimateInput
    demand: _Demand
    target_high_f: float
    tuning: ClimateTuning


@dataclass(frozen=True, slots=True)
class _DemandDiagnosticContext:
    policy: ClimatePolicy
    demand: _Demand
    allocation: _Allocation
    fan_pct: int
    fan_reasons: tuple[str, ...]
    dehumidifier_reason: str
    heater_reason: str


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
        return _failsafe_decision(policy, inp, fresh, phase_state, tuning)

    if not fresh.temperature:
        current_heater_level = _current_heater_level(state, inp)
        next_state = replace(
            state,
            humidifier_integral=0.0,
            drying_integral=0.0,
            heat_integral=0.0,
            cooling_fan_integral=0.0,
            last_tick_at=inp.now,
            phase=phase,
            dehumidifier_on=False,
            heater_level=0,
            heater_last_changed_at=inp.now
            if current_heater_level != 0
            else state.heater_last_changed_at,
        )
        return ClimateDecision(
            fan_duty_pct=policy.fan.floor_pct,
            humidifier_pct=0.0,
            dehumidifier_on=False,
            heater_level=0,
            active_mode="sensor_failsafe",
            vpd=_vpd_diagnostics(policy, inp),
            demand=_failsafe_demand_diagnostics(),
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
    heater_level, heater_reason = _allocate_heater(
        state,
        inp,
        demand,
        tuning=tuning,
    )
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
            fan_pct=fan_pct,
            fan_reasons=fan_reasons,
            tuning=tuning,
        ),
    )
    return ClimateDecision(
        fan_duty_pct=fan_pct,
        humidifier_pct=humidifier_pct,
        dehumidifier_on=dehumidifier_on,
        heater_level=heater_level,
        active_mode=_active_mode(demand, allocation),
        vpd=_vpd_diagnostics(policy, inp),
        demand=_demand_diagnostics(
            _DemandDiagnosticContext(
                policy=policy,
                demand=demand,
                allocation=allocation,
                fan_pct=fan_pct,
                fan_reasons=fan_reasons,
                dehumidifier_reason=dehumidifier_reason,
                heater_reason=heater_reason,
            )
        ),
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


def _vpd_diagnostics(
    policy: ClimatePolicy,
    inp: ClimateInput,
) -> VpdControlDiagnostics:
    phase_policy = policy.for_stage_phase(inp.stage, phase_from_lights(inp.lights_on))
    low = phase_policy.vpd_kpa.low
    high = phase_policy.vpd_kpa.high
    if inp.vpd_kpa is None:
        return VpdControlDiagnostics(
            band_low_kpa=low,
            band_high_kpa=high,
            selected_setpoint_kpa=(low + high) / 2.0,
            selected_edge="unavailable",
            control_vpd_kpa=None,
            error_kpa=None,
        )
    if inp.vpd_kpa > high:
        return VpdControlDiagnostics(
            band_low_kpa=low,
            band_high_kpa=high,
            selected_setpoint_kpa=high,
            selected_edge="upper_edge",
            control_vpd_kpa=inp.vpd_kpa,
            error_kpa=inp.vpd_kpa - high,
        )
    if inp.vpd_kpa < low:
        return VpdControlDiagnostics(
            band_low_kpa=low,
            band_high_kpa=high,
            selected_setpoint_kpa=low,
            selected_edge="lower_edge",
            control_vpd_kpa=inp.vpd_kpa,
            error_kpa=inp.vpd_kpa - low,
        )
    return VpdControlDiagnostics(
        band_low_kpa=low,
        band_high_kpa=high,
        selected_setpoint_kpa=(low + high) / 2.0,
        selected_edge="inside_band",
        control_vpd_kpa=inp.vpd_kpa,
        error_kpa=0.0,
    )


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
            cooling_fan_integral=0.0,
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
    tuning: ClimateTuning,
) -> ClimateDecision:
    heater_level = 0
    reasons = [*phase_state.reasons, "failsafe_stale_rh_vpd"]
    if fresh.temperature and inp.temperature_f is not None:
        temp_error = policy.hard_min_temperature_f - inp.temperature_f
        if temp_error > 0:
            heater_level = _quantized_heat_level(
                45.0 + temp_error * 15.0,
                current_level=0,
                tuning=tuning,
            )
            reasons.append("hard_low_temperature_guard")
    current_heater_level = _current_heater_level(phase_state.state, inp)
    next_state = replace(
        phase_state.state,
        humidifier_integral=0.0,
        drying_integral=0.0,
        heat_integral=heater_level * 10.0,
        cooling_fan_integral=0.0,
        last_tick_at=inp.now,
        phase=phase_state.phase,
        dehumidifier_on=False,
        heater_level=heater_level,
        heater_last_changed_at=inp.now
        if heater_level != current_heater_level
        else phase_state.state.heater_last_changed_at,
    )
    return ClimateDecision(
        fan_duty_pct=policy.fan.floor_pct,
        humidifier_pct=0.0,
        dehumidifier_on=False,
        heater_level=heater_level,
        active_mode="sensor_failsafe",
        vpd=_vpd_diagnostics(policy, inp),
        demand=_failsafe_demand_diagnostics(delivered_heat_pct=heater_level * 10.0),
        reasons=tuple(reasons),
        constraints=("sensor_failsafe",),
        conflicts=(),
        state=next_state,
    )


def _failsafe_demand_diagnostics(
    *,
    delivered_heat_pct: float = 0.0,
) -> ClimateDemandDiagnostics:
    return ClimateDemandDiagnostics(
        raw_humidifier_pct=0.0,
        raw_drying_pct=0.0,
        raw_heat_pct=delivered_heat_pct,
        raw_cooling_fan_pct=0.0,
        clipped_humidifier_pct=0.0,
        clipped_drying_pct=0.0,
        clipped_heat_pct=delivered_heat_pct,
        clipped_cooling_fan_pct=0.0,
        delivered_humidifier_pct=0.0,
        delivered_drying_pct=0.0,
        delivered_heat_pct=delivered_heat_pct,
        delivered_cooling_fan_pct=0.0,
        anti_windup_reasons=("sensor_failsafe_reset",),
        heater_allocation_reason="sensor_failsafe_heat"
        if delivered_heat_pct > 0
        else "sensor_failsafe_off",
        heater_limit_reason="sensor_failsafe",
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
    vpd_deadband_kpa = policy.dehumidifier.vpd_deadband_kpa
    vpd_too_high = inp.vpd_kpa > phase_policy.vpd_kpa.high + vpd_deadband_kpa
    vpd_too_low = inp.vpd_kpa < phase_policy.vpd_kpa.low - vpd_deadband_kpa
    hard_low_temp = inp.temperature_f < policy.hard_min_temperature_f
    heater_safety_cap = inp.temperature_f >= HEATER_SAFETY_MAX_F
    dehumidifier_owns_vpd = rh_guard or (
        vpd_too_low and _rh_high_for_dehumidifier(policy, inp)
    )

    humidifier_error = (
        max(0.0, inp.vpd_kpa - phase_policy.vpd_kpa.high) if vpd_too_high else 0.0
    )
    drying_vpd_error = (
        max(0.0, phase_policy.vpd_kpa.low - inp.vpd_kpa) if vpd_too_low else 0.0
    )
    drying_rh_error = max(0.0, inp.rh_pct - phase_policy.rh_max_pct)
    vpd_recovery_heat = _vpd_recovery_heat_requested(
        policy,
        state,
        inp,
        vpd_too_low=vpd_too_low,
    )
    raw_heat_error = _raw_heat_error(
        policy,
        inp,
        drying_vpd_error=drying_vpd_error,
        hard_low_temp=hard_low_temp,
        vpd_too_low=vpd_too_low,
    )
    heat_allowed = (hard_low_temp or vpd_recovery_heat) and not heater_safety_cap

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
        raw_heat_error,
        dt_s,
        tuning.heater_ki,
        tuning,
    )
    cooling_fan_error = max(0.0, inp.temperature_f - phase_policy.temperature_f.high)
    cooling_fan_integral = _integral(
        state.cooling_fan_integral,
        cooling_fan_error,
        dt_s,
        tuning.cooling_fan_ki,
        tuning,
    )

    humidifier_p = tuning.humidifier_kp * humidifier_error
    drying_p = (
        tuning.drying_vpd_kp * drying_vpd_error + tuning.drying_rh_kp * drying_rh_error
    )
    heat_p = _heat_p_term(raw_heat_error, hard_low_temp, tuning)
    cooling_fan_p = tuning.cooling_fan_kp * cooling_fan_error
    if state.last_tick_at is None:
        if humidifier_error > 0 and inp.current_humidifier_pct > 0:
            humidifier_integral = _track_integral(
                humidifier_p,
                inp.current_humidifier_pct,
                tuning,
            )
        observed_drying_pct = _observed_drying_pct(policy, inp)
        if (drying_vpd_error > 0 or drying_rh_error > 0) and observed_drying_pct > 0:
            drying_integral = _track_integral(drying_p, observed_drying_pct, tuning)
        observed_heat_pct = inp.current_heater_level * 10.0
        if raw_heat_error > 0 and observed_heat_pct > 0:
            heat_integral = _track_integral(heat_p, observed_heat_pct, tuning)
        observed_fan_elevated_pct = max(0.0, inp.current_fan_pct - policy.fan.floor_pct)
        if cooling_fan_error > 0 and observed_fan_elevated_pct > 0:
            cooling_fan_integral = _track_integral(
                cooling_fan_p,
                observed_fan_elevated_pct,
                tuning,
            )
    raw_humidifier_pct = humidifier_p + humidifier_integral
    raw_drying_pct = drying_p + drying_integral
    raw_heat_pct = heat_p + heat_integral
    raw_cooling_fan_pct = cooling_fan_p + cooling_fan_integral
    clipped_cooling_fan_pct = min(
        policy.fan.max_pct - policy.fan.floor_pct,
        raw_cooling_fan_pct,
    )

    reasons = _demand_reasons(
        _DemandReasonFlags(
            rh_guard=rh_guard,
            vpd_too_high=vpd_too_high,
            vpd_too_low=vpd_too_low,
            dehumidifier_owns_vpd=dehumidifier_owns_vpd,
            hard_low_temp=hard_low_temp,
            temp_low=False,
            temp_high=inp.temperature_f > phase_policy.temperature_f.high,
            vpd_recovery_heat=vpd_recovery_heat,
        )
    )
    return _Demand(
        raw_humidifier_pct=raw_humidifier_pct,
        raw_drying_pct=raw_drying_pct,
        raw_heat_pct=raw_heat_pct,
        raw_cooling_fan_pct=raw_cooling_fan_pct,
        humidifier_pct=_pct(raw_humidifier_pct) if humidifier_error > 0 else 0.0,
        drying_pct=_pct(raw_drying_pct)
        if drying_vpd_error > 0 or drying_rh_error > 0
        else 0.0,
        heat_pct=_pct(raw_heat_pct) if heat_allowed and raw_heat_error > 0 else 0.0,
        cooling_fan_pct=round(_pct(clipped_cooling_fan_pct))
        if cooling_fan_error > 0
        else 0,
        humidifier_p_term=humidifier_p,
        drying_p_term=drying_p,
        heat_p_term=heat_p,
        cooling_fan_p_term=cooling_fan_p,
        rh_guard=rh_guard,
        vpd_too_high=vpd_too_high,
        vpd_too_low=vpd_too_low,
        hard_low_temp=hard_low_temp,
        heater_safety_cap=heater_safety_cap,
        dehumidifier_owns_vpd=dehumidifier_owns_vpd,
        vpd_recovery_heat=vpd_recovery_heat,
        reasons=reasons,
    )


def _raw_heat_error(
    policy: ClimatePolicy,
    inp: ClimateInput,
    *,
    drying_vpd_error: float,
    hard_low_temp: bool,
    vpd_too_low: bool,
) -> float:
    assert inp.temperature_f is not None  # noqa: S101 - narrowed by caller.
    if hard_low_temp:
        return policy.hard_min_temperature_f - inp.temperature_f
    if vpd_too_low:
        return drying_vpd_error
    return 0.0


def _observed_drying_pct(policy: ClimatePolicy, inp: ClimateInput) -> float:
    fan_delivery = max(0.0, inp.current_fan_pct - policy.fan.floor_pct)
    dehumidifier_delivery = 60.0 if inp.current_dehumidifier_on else 0.0
    return min(100.0, fan_delivery + dehumidifier_delivery)


def _vpd_recovery_heat_requested(
    policy: ClimatePolicy,
    state: ClimateState,
    inp: ClimateInput,
    *,
    vpd_too_low: bool,
) -> bool:
    assert inp.temperature_f is not None  # noqa: S101 - narrowed by caller.
    assert inp.vpd_kpa is not None  # noqa: S101 - narrowed by caller.
    if inp.temperature_f >= HEATER_SAFETY_MAX_F:
        return False
    phase_policy = policy.for_stage_phase(inp.stage, phase_from_lights(inp.lights_on))
    vpd_release_kpa = phase_policy.vpd_kpa.low + policy.dehumidifier.vpd_deadband_kpa
    current = _current_heater_level(state, inp)
    if current > 0 and inp.vpd_kpa < vpd_release_kpa:
        return True
    return vpd_too_low


def _rh_high_for_dehumidifier(policy: ClimatePolicy, inp: ClimateInput) -> bool:
    phase_policy = policy.for_stage_phase(inp.stage, phase_from_lights(inp.lights_on))
    assert inp.rh_pct is not None  # noqa: S101 - narrowed by caller.
    threshold = phase_policy.rh_max_pct - policy.dehumidifier.rh_deadband_pct
    return inp.rh_pct >= threshold


def _heat_p_term(
    heat_error: float,
    hard_low_temp: bool,
    tuning: ClimateTuning,
) -> float:
    if heat_error <= 0:
        return 0.0
    if hard_low_temp:
        return max(55.0, 45.0 + heat_error * 15.0)
    return tuning.heater_kp * heat_error


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
    if flags.dehumidifier_owns_vpd:
        reasons.append("dehumidifier_owns_vpd_recovery")
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
    requested_on = demand.dehumidifier_owns_vpd
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


def _allocate_heater(
    state: ClimateState,
    inp: ClimateInput,
    demand: _Demand,
    *,
    tuning: ClimateTuning,
) -> tuple[int, str]:
    assert inp.temperature_f is not None  # noqa: S101 - narrowed by caller.
    current = _current_heater_level(state, inp)
    if inp.temperature_f >= HEATER_SAFETY_MAX_F:
        return 0, "heater_safety_off"
    if demand.vpd_recovery_heat and demand.heat_pct <= 0 and 0 < current <= 5:
        return current, "heater_vpd_recovery_maintenance"

    requested = _quantized_heat_level(
        demand.heat_pct,
        current_level=current,
        tuning=tuning,
    )
    if demand.heat_pct <= 0 and current > 0:
        requested = 0
    if requested == current:
        if demand.vpd_recovery_heat and current > 0:
            return current, "heater_vpd_recovery_maintenance"
        return current, "heater_level_hysteresis_hold"
    if _within_heater_dwell(state, inp, tuning):
        return current, "heater_min_dwell"

    rate_limited = _rate_limited_heater_level(current, requested)
    if rate_limited != requested:
        reason = (
            "heater_decay_step_down"
            if rate_limited < current
            else "heater_rate_limited_step"
        )
        return rate_limited, reason
    if rate_limited < current and demand.heat_pct <= 0:
        return rate_limited, "heater_decay_step_down"
    if rate_limited == 0:
        return 0, "heater_off"
    return rate_limited, "heater_level_request"


def _current_heater_level(state: ClimateState, inp: ClimateInput) -> int:
    if state.heater_last_changed_at is None:
        return inp.current_heater_level
    return state.heater_level


def _quantized_heat_level(
    heat_pct: float,
    *,
    current_level: int,
    tuning: ClimateTuning,
) -> int:
    if heat_pct <= 0:
        return 0
    level = max(1, min(10, int((heat_pct + 5.0) // 10.0)))
    if current_level <= 0 or level == current_level:
        return level

    current_pct = current_level * 10.0
    if level > current_level:
        threshold_pct = current_pct + tuning.heater_level_hysteresis_pct
        return level if heat_pct >= threshold_pct else current_level

    threshold_pct = current_pct - tuning.heater_level_hysteresis_pct
    return level if heat_pct <= threshold_pct else current_level


def _rate_limited_heater_level(current: int, requested: int) -> int:
    if requested > current:
        return current + 1
    if requested < current:
        return current - 1
    return current


def _within_heater_dwell(
    state: ClimateState,
    inp: ClimateInput,
    tuning: ClimateTuning,
) -> bool:
    if state.heater_last_changed_at is None:
        return False
    elapsed_s = (inp.now - state.heater_last_changed_at).total_seconds()
    return elapsed_s < tuning.heater_minimum_dwell_s


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
    rh_drying_fan_active = any(
        reason in {"fan_drying_rh_enter", "fan_drying_rh_hysteresis_hold"}
        for reason in hysteresis_reasons
    )

    if heater_level > 0 and cooling_fan_pct > 0:
        cooling_fan_pct = 0
        conflicts.append("heater_elevated_fan_cooling_suppressed")
    if (
        heater_level > 0
        and inp.current_fan_pct > policy.fan.floor_pct
        and not (demand.rh_guard or demand.vpd_too_low)
    ):
        conflicts.append("heater_elevated_fan_cooling_suppressed")
    if demand.vpd_recovery_heat and not demand.rh_guard and not rh_drying_fan_active:
        drying_fan_pct = 0
    if heater_level > 0 and drying_fan_pct > 0:
        if demand.rh_guard or demand.vpd_too_low or rh_drying_fan_active:
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
    phase_policy = policy.for_stage_phase(inp.stage, phase_from_lights(inp.lights_on))
    current_elevated = max(0, inp.current_fan_pct - policy.fan.floor_pct)
    if inp.rh_pct is not None:
        rh_enter_pct = (
            phase_policy.rh_max_pct - tuning.fan_drying_rh_enter_below_max_pct
        )
        rh_exit_pct = phase_policy.rh_max_pct - tuning.fan_drying_rh_exit_below_max_pct
        if current_elevated > 0 and inp.rh_pct >= rh_exit_pct:
            return max(requested_pct, current_elevated), (
                "fan_drying_rh_hysteresis_hold",
            )
        if inp.rh_pct > rh_enter_pct:
            return requested_pct, ("fan_drying_rh_enter",)

    if demand.rh_guard:
        return requested_pct, ()
    if demand.vpd_recovery_heat or inp.vpd_kpa is None:
        return 0, ()

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


def _active_mode(demand: _Demand, allocation: _Allocation) -> str:
    if demand.hard_low_temp:
        return "hard_temperature_guard"
    if demand.rh_guard:
        return "hard_rh_guard"
    if allocation.humidifier_pct > 0 or demand.vpd_too_high:
        return "vpd_humidify"
    if demand.dehumidifier_owns_vpd and allocation.dehumidifier_on:
        return "vpd_dehumidify"
    if demand.vpd_recovery_heat or (demand.vpd_too_low and allocation.heater_level > 0):
        return "vpd_heat_assist"
    if demand.vpd_too_low or allocation.dehumidifier_on or demand.drying_pct > 0:
        return "vpd_dehumidify"
    if demand.cooling_fan_pct > 0:
        return "hard_temperature_guard"
    return "vpd_hold"


def _demand_diagnostics(ctx: _DemandDiagnosticContext) -> ClimateDemandDiagnostics:
    delivered_drying_pct = _delivered_drying_diagnostic_pct(
        ctx.policy,
        allocation=ctx.allocation,
        fan_pct=ctx.fan_pct,
        fan_reasons=ctx.fan_reasons,
    )
    delivered_cooling_fan_pct = _delivered_cooling_fan_pct(
        ctx.policy,
        fan_pct=ctx.fan_pct,
        fan_reasons=ctx.fan_reasons,
    )
    return ClimateDemandDiagnostics(
        raw_humidifier_pct=ctx.demand.raw_humidifier_pct,
        raw_drying_pct=ctx.demand.raw_drying_pct,
        raw_heat_pct=ctx.demand.raw_heat_pct,
        raw_cooling_fan_pct=ctx.demand.raw_cooling_fan_pct,
        clipped_humidifier_pct=min(
            ctx.demand.humidifier_pct,
            ctx.allocation.humidifier_pct,
        ),
        clipped_drying_pct=min(ctx.demand.drying_pct, delivered_drying_pct),
        clipped_heat_pct=min(
            ctx.demand.heat_pct,
            ctx.allocation.heater_level * 10.0,
        ),
        clipped_cooling_fan_pct=min(
            float(ctx.demand.cooling_fan_pct),
            delivered_cooling_fan_pct,
        ),
        delivered_humidifier_pct=ctx.allocation.humidifier_pct,
        delivered_drying_pct=delivered_drying_pct,
        delivered_heat_pct=ctx.allocation.heater_level * 10.0,
        delivered_cooling_fan_pct=delivered_cooling_fan_pct,
        anti_windup_reasons=(
            _tracking_reason(
                "humidifier",
                requested_pct=ctx.demand.humidifier_pct,
                delivered_pct=ctx.allocation.humidifier_pct,
            ),
            _tracking_reason(
                "drying",
                requested_pct=ctx.demand.drying_pct,
                delivered_pct=delivered_drying_pct,
            ),
            _tracking_reason(
                "heat",
                requested_pct=_pct(ctx.demand.raw_heat_pct),
                delivered_pct=ctx.allocation.heater_level * 10.0,
            ),
            _tracking_reason(
                "cooling_fan",
                requested_pct=ctx.demand.cooling_fan_pct,
                delivered_pct=delivered_cooling_fan_pct,
            ),
        ),
        dehumidifier_allocation_reason=ctx.dehumidifier_reason,
        dehumidifier_limit_reason=_dehumidifier_limit_reason(ctx.dehumidifier_reason),
        heater_allocation_reason=ctx.heater_reason,
        heater_limit_reason=_heater_limit_reason(ctx.demand, ctx.heater_reason),
    )


def _delivered_drying_diagnostic_pct(
    policy: ClimatePolicy,
    *,
    allocation: _Allocation,
    fan_pct: int,
    fan_reasons: tuple[str, ...],
) -> float:
    fan_delivery = (
        max(0.0, fan_pct - policy.fan.floor_pct)
        if "fan_elevated_for_drying" in fan_reasons
        else 0.0
    )
    dehumidifier_delivery = 60.0 if allocation.dehumidifier_on else 0.0
    return min(100.0, fan_delivery + dehumidifier_delivery)


def _delivered_cooling_fan_pct(
    policy: ClimatePolicy,
    *,
    fan_pct: int,
    fan_reasons: tuple[str, ...],
) -> float:
    if "fan_elevated_for_cooling" not in fan_reasons:
        return 0.0
    return max(0.0, fan_pct - policy.fan.floor_pct)


def _tracking_reason(
    actuator: str,
    *,
    requested_pct: float,
    delivered_pct: float,
) -> str:
    if requested_pct <= 0 and delivered_pct <= 0:
        return f"{actuator}_tracking_idle"
    if delivered_pct + 0.01 < requested_pct:
        return f"{actuator}_tracking_clipped_delivery"
    return f"{actuator}_tracking_delivered_output"


def _dehumidifier_limit_reason(reason: str) -> str | None:
    if reason in {"dehumidifier_min_off_hold", "dehumidifier_min_on_hold"}:
        return reason
    return None


def _heater_limit_reason(demand: _Demand, reason: str) -> str | None:
    if _pct(demand.raw_heat_pct) > 0 and demand.heat_pct <= 0:
        if demand.heater_safety_cap:
            return "heater_safety_off"
        return "heater_clipped_inactive_mode"
    if reason in {
        "heater_level_hysteresis_hold",
        "heater_min_dwell",
        "heater_rate_limited_step",
        "heater_decay_step_down",
        "heater_safety_off",
        "heater_vpd_recovery_maintenance",
    }:
        return reason
    return None


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
    delivered_drying_pct = _delivered_drying_diagnostic_pct(
        policy,
        allocation=allocation,
        fan_pct=ctx.fan_pct,
        fan_reasons=ctx.fan_reasons,
    )
    delivered_cooling_fan_pct = _delivered_cooling_fan_pct(
        policy,
        fan_pct=ctx.fan_pct,
        fan_reasons=ctx.fan_reasons,
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
            delivered_drying_pct,
            tuning,
        ),
        heat_integral=_track_integral(
            demand.heat_p_term,
            allocation.heater_level * 10.0,
            tuning,
        ),
        cooling_fan_integral=_track_integral(
            demand.cooling_fan_p_term,
            delivered_cooling_fan_pct,
            tuning,
        ),
        last_tick_at=inp.now,
        phase=ctx.phase,
        dehumidifier_on=allocation.dehumidifier_on,
        dehumidifier_last_changed_at=dehumidifier_last_changed_at,
        heater_level=allocation.heater_level,
        heater_last_changed_at=heater_last_changed_at,
    )


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
