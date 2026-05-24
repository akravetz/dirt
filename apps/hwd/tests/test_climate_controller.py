from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from dirt_hwd.services.climate_actuators import (
    ClimateActuators,
    ThermoForgeHeaterTarget,
)
from dirt_hwd.services.climate_controller import (
    ClimateControllerService,
    ClimateInput,
    ClimateState,
    decide_climate,
)
from dirt_hwd.services.climate_policy import default_climate_policy
from dirt_hwd.services.thermoforge_protocol import ThermoForgeStatus
from dirt_shared.services.grow_state import GrowContext, LightsState

T0 = datetime(2026, 5, 22, 18, 0, tzinfo=UTC)
POLICY = default_climate_policy()


def _input(**overrides) -> ClimateInput:
    base = dict(
        now=T0,
        stage="flower_early",
        lights_on=True,
        temperature_f=77.0,
        temperature_age_s=30.0,
        rh_pct=55.0,
        rh_age_s=30.0,
        vpd_kpa=1.2,
        vpd_age_s=30.0,
        current_fan_pct=20,
        current_humidifier_pct=0.0,
        current_dehumidifier_on=False,
        current_heater_level=0,
    )
    base.update(overrides)
    return ClimateInput(**base)


def _decide(state: ClimateState | None = None, **overrides):
    return decide_climate(POLICY, state or ClimateState(), _input(**overrides))


class _FakeReading:
    def __init__(self, value: float, ts: datetime = T0 - timedelta(seconds=30)) -> None:
        self.value = value
        self.ts = ts


class _FakeReadings:
    def __init__(self, values: dict[str, float]) -> None:
        self.values = values
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def get_latest_reading(self, metric: str, **kwargs: object):
        self.calls.append((metric, dict(kwargs)))
        value = self.values.get(metric)
        return None if value is None else _FakeReading(value)


class _FakeGrow:
    async def current_context(self, **kwargs: object) -> GrowContext:
        return GrowContext(
            stage="flower_early",
            lights=LightsState(
                on=True, minutes_until_off=180.0, minutes_until_on=540.0
            ),
            targets={
                "temperature_f": (76.0, 78.0),
                "humidity_pct": (40.0, 65.0),
                "vpd_kpa": (1.1, 1.3),
            },
        )


class _FakeFan:
    def __init__(self, duty: int = 20) -> None:
        self.duty = duty
        self.set_calls: list[int] = []

    async def read_duty(self) -> int:
        return self.duty

    async def set_duty(self, duty_pct: int) -> int:
        self.set_calls.append(duty_pct)
        self.duty = duty_pct
        return duty_pct


class _FakeHumidifier:
    def __init__(self) -> None:
        self.intensities: list[float] = []

    async def set_intensity(self, intensity_pct: float) -> object:
        self.intensities.append(intensity_pct)
        return object()


class _FakeDehumidifier:
    def __init__(self) -> None:
        self.powers: list[bool] = []

    async def set_power(self, on: bool) -> bool:
        self.powers.append(on)
        return on


class _FakeHeater:
    def __init__(self) -> None:
        self.levels: list[int] = []

    async def set_target(self, target: ThermoForgeHeaterTarget) -> ThermoForgeStatus:
        self.levels.append(target.level)
        return ThermoForgeStatus(running=target.running, level=target.level)


class _FailingHeater:
    async def set_target(self, target: ThermoForgeHeaterTarget) -> ThermoForgeStatus:
        raise RuntimeError(f"heater unavailable for level {target.level}")


def _service(
    values: dict[str, float],
    *,
    fan: _FakeFan | None = None,
    humidifier: _FakeHumidifier | None = None,
    dehumidifier: _FakeDehumidifier | None = None,
    heater: _FakeHeater | None = None,
    events: list[tuple[str, str, dict[str, Any]]] | None = None,
) -> tuple[
    ClimateControllerService,
    _FakeReadings,
    _FakeFan,
    _FakeHumidifier,
    _FakeDehumidifier,
    _FakeHeater,
    list[tuple[str, str, dict[str, Any]]],
]:
    event_log = events if events is not None else []
    fake_fan = fan or _FakeFan()
    fake_humidifier = humidifier or _FakeHumidifier()
    fake_dehumidifier = dehumidifier or _FakeDehumidifier()
    fake_heater = heater or _FakeHeater()
    fake_readings = _FakeReadings(values)

    def capture_event(stream: str, event: str, **fields: Any) -> None:
        event_log.append((stream, event, fields))

    service = ClimateControllerService(
        readings=fake_readings,
        grow=_FakeGrow(),
        actuators=ClimateActuators(
            fan=fake_fan,
            humidifier=fake_humidifier,
            dehumidifier=fake_dehumidifier,
            heater=fake_heater,
        ),
        policy=POLICY,
        clock=lambda: T0,
        event_logger=capture_event,
    )
    return (
        service,
        fake_readings,
        fake_fan,
        fake_humidifier,
        fake_dehumidifier,
        fake_heater,
        event_log,
    )


def test_high_vpd_humidifies_without_drying_or_fan_relief() -> None:
    decision = _decide(vpd_kpa=1.55, rh_pct=52.0, temperature_f=77.0)

    assert decision.humidifier_pct > 0
    assert decision.dehumidifier_on is False
    assert decision.fan_duty_pct == POLICY.fan.floor_pct
    assert decision.heater_level == 0
    assert "vpd_split_humidify" in decision.reasons


def test_low_vpd_requests_dehumidifier_and_may_raise_fan() -> None:
    decision = _decide(vpd_kpa=0.82, rh_pct=58.0, temperature_f=78.0)

    assert decision.humidifier_pct == 0.0
    assert decision.dehumidifier_on is True
    assert decision.fan_duty_pct > POLICY.fan.floor_pct
    assert "vpd_split_dry" in decision.reasons


def test_rh_above_max_forces_humidifier_off_and_drying() -> None:
    decision = _decide(vpd_kpa=1.5, rh_pct=68.0, temperature_f=77.0)

    assert decision.humidifier_pct == 0.0
    assert decision.dehumidifier_on is True
    assert decision.fan_duty_pct > POLICY.fan.floor_pct
    assert "hard_rh" in decision.constraints
    assert "humidifier_forced_off_high_rh" in decision.reasons


def test_temperature_below_hard_floor_heats_and_keeps_fan_at_floor() -> None:
    decision = _decide(temperature_f=68.5, vpd_kpa=1.2, rh_pct=55.0)

    assert decision.heater_level > 0
    assert decision.fan_duty_pct == POLICY.fan.floor_pct
    assert decision.dehumidifier_on is False
    assert "hard_low_temperature_guard" in decision.reasons


def test_low_temperature_with_low_vpd_prefers_dehumidifier_over_fan_purge() -> None:
    decision = _decide(
        lights_on=False,
        temperature_f=68.5,
        vpd_kpa=0.82,
        rh_pct=70.0,
    )

    assert decision.heater_level > 0
    assert decision.dehumidifier_on is True
    assert decision.fan_duty_pct == POLICY.fan.floor_pct
    assert "vpd_split_dry" in decision.reasons


def test_low_vpd_near_floor_uses_heat_recovery_without_fan_purge() -> None:
    decision = _decide(
        lights_on=False,
        temperature_f=70.2,
        vpd_kpa=0.82,
        rh_pct=67.0,
    )

    assert decision.heater_level > 0
    assert decision.dehumidifier_on is True
    assert decision.fan_duty_pct == POLICY.fan.floor_pct
    assert "vpd_recovery_heat" in decision.reasons
    assert "fan_floor" in decision.reasons
    assert "hard_low_temperature" not in decision.constraints


def test_vpd_recovery_heat_continues_until_vpd_exit_or_temperature_cap() -> None:
    state = ClimateState(
        last_tick_at=T0 - timedelta(seconds=120),
        phase="lights_off",
        heater_level=5,
        heater_last_changed_at=T0 - timedelta(seconds=240),
    )

    decision = _decide(
        state,
        lights_on=False,
        temperature_f=71.7,
        vpd_kpa=0.93,
        rh_pct=64.0,
    )

    assert decision.heater_level > 0
    assert decision.fan_duty_pct == POLICY.fan.floor_pct
    assert "vpd_recovery_heat" in decision.reasons


def test_vpd_recovery_heat_exits_at_vpd_exit_threshold() -> None:
    state = ClimateState(
        last_tick_at=T0 - timedelta(seconds=120),
        phase="lights_off",
        heater_level=5,
        heater_last_changed_at=T0 - timedelta(seconds=240),
    )

    decision = _decide(
        state,
        lights_on=False,
        temperature_f=71.7,
        vpd_kpa=0.96,
        rh_pct=62.0,
    )

    assert decision.heater_level == 0
    assert "vpd_recovery_heat" not in decision.reasons


def test_vpd_recovery_heat_maintains_at_phase_high_until_safety_cap() -> None:
    state = ClimateState(
        last_tick_at=T0 - timedelta(seconds=120),
        phase="lights_off",
        heater_level=5,
        heater_last_changed_at=T0 - timedelta(seconds=240),
    )

    decision = _decide(
        state,
        lights_on=False,
        temperature_f=72.0,
        vpd_kpa=0.82,
        rh_pct=66.0,
    )

    assert decision.heater_level == 5
    assert "heater_vpd_recovery_maintenance" in decision.reasons


def test_vpd_recovery_heat_exits_at_temperature_safety_cap() -> None:
    state = ClimateState(
        last_tick_at=T0 - timedelta(seconds=120),
        phase="lights_off",
        heater_level=5,
        heater_last_changed_at=T0 - timedelta(seconds=240),
    )

    decision = _decide(
        state,
        lights_on=False,
        temperature_f=72.5,
        vpd_kpa=0.82,
        rh_pct=66.0,
    )

    assert decision.heater_level == 0
    assert decision.fan_duty_pct > POLICY.fan.floor_pct


def test_vpd_recovery_uses_lights_on_temperature_high() -> None:
    state = ClimateState(
        last_tick_at=T0 - timedelta(seconds=120),
        phase="lights_on",
        heater_level=5,
        heater_last_changed_at=T0 - timedelta(seconds=240),
    )

    decision = _decide(
        state,
        lights_on=True,
        temperature_f=78.0,
        vpd_kpa=0.82,
        rh_pct=58.0,
    )

    assert decision.heater_level == 5
    assert "vpd_recovery_heat" in decision.reasons
    assert "heater_vpd_recovery_maintenance" in decision.reasons


def test_vpd_recovery_lights_on_exits_at_temperature_safety_cap() -> None:
    state = ClimateState(
        last_tick_at=T0 - timedelta(seconds=120),
        phase="lights_on",
        heater_level=5,
        heater_last_changed_at=T0 - timedelta(seconds=240),
    )

    decision = _decide(
        state,
        lights_on=True,
        temperature_f=78.5,
        vpd_kpa=0.82,
        rh_pct=58.0,
    )

    assert decision.heater_level == 0
    assert "heater_safety_off" in decision.reasons


def test_drying_fan_waits_for_enter_threshold_from_floor() -> None:
    decision = _decide(
        lights_on=False,
        temperature_f=71.4,
        vpd_kpa=0.895,
        rh_pct=66.0,
        current_fan_pct=POLICY.fan.floor_pct,
    )

    assert decision.fan_duty_pct == POLICY.fan.floor_pct
    assert "vpd_split_dry" in decision.reasons
    assert "fan_elevated_for_drying" not in decision.reasons


def test_drying_fan_holds_until_exit_threshold_once_elevated() -> None:
    decision = _decide(
        lights_on=False,
        temperature_f=71.4,
        vpd_kpa=0.902,
        rh_pct=66.0,
        current_fan_pct=60,
    )

    assert decision.fan_duty_pct == 60
    assert "fan_drying_hysteresis_hold" in decision.reasons
    assert "fan_elevated_for_drying" in decision.reasons


def test_drying_fan_slew_limits_non_safety_step_up() -> None:
    decision = _decide(
        lights_on=False,
        temperature_f=72.0,
        vpd_kpa=0.5,
        rh_pct=74.0,
        current_fan_pct=POLICY.fan.floor_pct,
    )

    assert decision.fan_duty_pct == POLICY.fan.floor_pct + 15
    assert "fan_slew_limited" in decision.reasons


def test_hard_rh_guard_bypasses_fan_slew_limit() -> None:
    decision = _decide(
        lights_on=False,
        temperature_f=71.5,
        vpd_kpa=0.82,
        rh_pct=90.0,
        current_fan_pct=POLICY.fan.floor_pct,
    )

    assert decision.fan_duty_pct > POLICY.fan.floor_pct + 15
    assert "hard_rh" in decision.constraints
    assert "fan_slew_limited" not in decision.reasons


def test_heater_with_fan_floor_is_not_a_conflict() -> None:
    decision = _decide(temperature_f=71.0, vpd_kpa=1.2, rh_pct=55.0)

    assert decision.heater_level > 0
    assert decision.fan_duty_pct == POLICY.fan.floor_pct
    assert decision.conflicts == ()


def test_heater_suppresses_existing_elevated_fan_cooling() -> None:
    decision = _decide(
        temperature_f=71.0,
        vpd_kpa=1.2,
        rh_pct=55.0,
        current_fan_pct=60,
    )

    assert decision.heater_level > 0
    assert decision.fan_duty_pct == 45
    assert "heater_elevated_fan_cooling_suppressed" in decision.conflicts
    assert "fan_slew_limited" in decision.reasons


def test_heater_with_elevated_drying_fan_is_explicitly_allowed_for_safety() -> None:
    decision = _decide(temperature_f=69.0, vpd_kpa=0.82, rh_pct=78.0)

    assert decision.heater_level > 0
    assert decision.fan_duty_pct > POLICY.fan.floor_pct
    assert "heater_with_elevated_fan_drying_allowed" in decision.reasons
    assert "hard_rh" in decision.constraints


def test_missing_vpd_or_rh_fails_safe_but_allows_low_temp_heat() -> None:
    decision = _decide(temperature_f=68.0, vpd_kpa=None, vpd_age_s=None, rh_pct=55.0)

    assert decision.humidifier_pct == 0.0
    assert decision.dehumidifier_on is False
    assert decision.fan_duty_pct == POLICY.fan.floor_pct
    assert decision.heater_level > 0
    assert "sensor_failsafe" in decision.constraints


def test_dehumidifier_minimum_off_time_blocks_rapid_restart() -> None:
    state = ClimateState(
        drying_integral=80.0,
        last_tick_at=T0 - timedelta(seconds=30),
        phase="lights_on",
        dehumidifier_on=False,
        dehumidifier_last_changed_at=T0 - timedelta(seconds=60),
    )

    decision = _decide(state, vpd_kpa=0.82, rh_pct=58.0, temperature_f=76.0)

    assert decision.dehumidifier_on is False
    assert "dehumidifier_min_off_hold" in decision.reasons
    assert decision.state.drying_integral < state.drying_integral


def test_dehumidifier_minimum_on_time_blocks_rapid_stop() -> None:
    state = ClimateState(
        last_tick_at=T0 - timedelta(seconds=30),
        phase="lights_on",
        dehumidifier_on=True,
        dehumidifier_last_changed_at=T0 - timedelta(seconds=60),
    )

    decision = _decide(state, vpd_kpa=1.25, rh_pct=50.0, temperature_f=77.0)

    assert decision.dehumidifier_on is True
    assert decision.humidifier_pct == 0.0
    assert "dehumidifier_min_on_hold" in decision.reasons


def test_phase_transition_is_bumpless() -> None:
    state = ClimateState(
        humidifier_integral=100.0,
        drying_integral=100.0,
        heat_integral=100.0,
        last_tick_at=T0 - timedelta(seconds=30),
        phase="lights_on",
        heater_level=8,
    )

    decision = _decide(
        state,
        now=T0 + timedelta(hours=3),
        lights_on=False,
        temperature_f=71.0,
        rh_pct=65.0,
        vpd_kpa=1.0,
    )

    assert decision.humidifier_pct == 0.0
    assert decision.dehumidifier_on is False
    assert decision.fan_duty_pct == POLICY.fan.floor_pct
    assert decision.heater_level == 0
    assert "phase_transition_bumpless" in decision.reasons


def test_clipping_feedback_prevents_humidifier_windup() -> None:
    state = ClimateState(
        humidifier_integral=90.0,
        last_tick_at=T0 - timedelta(seconds=30),
        phase="lights_on",
    )

    decision = _decide(state, vpd_kpa=1.7, rh_pct=70.0, temperature_f=77.0)

    assert decision.humidifier_pct == 0.0
    assert decision.state.humidifier_integral < 0.0


@pytest.mark.parametrize("missing_field", ["vpd", "rh"])
def test_missing_or_stale_vpd_rh_disables_humidity_actuators(
    missing_field: str,
) -> None:
    overrides = {"vpd_age_s": 600.0} if missing_field == "vpd" else {"rh_age_s": 600.0}

    decision = _decide(**overrides)

    assert decision.humidifier_pct == 0.0
    assert decision.dehumidifier_on is False
    assert decision.fan_duty_pct == POLICY.fan.floor_pct


async def test_service_tick_dispatches_humidify_decision_and_logs_reason_codes() -> (
    None
):
    service, readings, fan, humidifier, dehumidifier, heater, events = _service(
        {
            "temperature_f": 77.0,
            "humidity_pct": 52.0,
            "vpd_kpa": 1.55,
            "humidifier_mist_level": 0.0,
            "dehumidifier_on": 0.0,
            "heater_heat_level": 0.0,
        }
    )

    decision = await service._tick()

    assert decision.humidifier_pct > 0
    assert humidifier.intensities == [decision.humidifier_pct]
    assert dehumidifier.powers == [False]
    assert fan.set_calls == []
    assert heater.levels == [0]
    assert (
        "humidifier_mist_level",
        {
            "site_id": "homebox",
            "tent_id": "main",
            "zone_id": "canopy",
            "device_id": "govee-h7142-main",
            "capability_id": "humidifier_mist_level",
        },
    ) in readings.calls
    assert len(events) == 1
    stream, event, fields = events[0]
    assert stream == "climate_controller"
    assert event == "tick"
    assert fields["target_humidifier_pct"] == round(decision.humidifier_pct, 1)
    assert fields["target_dehumidifier_on"] is False
    assert "vpd_split_humidify" in fields["reasons"]


async def test_service_tick_turns_humidifier_off_before_dehumidifying() -> None:
    service, _readings, fan, humidifier, dehumidifier, heater, events = _service(
        {
            "temperature_f": 78.0,
            "humidity_pct": 58.0,
            "vpd_kpa": 0.82,
            "humidifier_mist_level": 4.0,
            "dehumidifier_on": 0.0,
            "heater_heat_level": 0.0,
        }
    )

    decision = await service._tick()

    assert decision.humidifier_pct == 0.0
    assert decision.dehumidifier_on is True
    assert humidifier.intensities == [0.0]
    assert dehumidifier.powers == [True]
    assert fan.set_calls == [decision.fan_duty_pct]
    assert heater.levels == [0]
    assert events[0][2]["target_humidifier_pct"] == 0.0
    assert events[0][2]["target_dehumidifier_on"] is True
    assert "vpd_split_dry" in events[0][2]["reasons"]


async def test_service_tick_logs_heater_failure_without_blocking_drying() -> None:
    service, _readings, fan, humidifier, dehumidifier, _heater, events = _service(
        {
            "temperature_f": 68.5,
            "humidity_pct": 78.0,
            "vpd_kpa": 0.82,
            "humidifier_mist_level": 4.0,
            "dehumidifier_on": 0.0,
            "heater_heat_level": 0.0,
        },
        heater=_FailingHeater(),  # type: ignore[arg-type]
    )

    decision = await service._tick()

    assert decision.heater_level > 0
    assert humidifier.intensities == [0.0]
    assert dehumidifier.powers == [True]
    assert fan.set_calls == [decision.fan_duty_pct]
    assert [event for _stream, event, _fields in events] == ["tick", "actuator_error"]
    assert events[1][2]["actuator"] == "heater"
    assert events[1][2]["target_level"] == decision.heater_level
