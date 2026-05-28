from __future__ import annotations

import pytest

from dirt_hwd.services.climate_policy import (
    THERMOFORGE_SUPPORTED_LEVELS,
    Band,
    ClimatePolicy,
    ClimatePolicyDefaults,
    FanPolicy,
    HeaterPolicy,
    default_climate_policy,
    phase_from_lights,
)


def test_selects_stage_and_phase_policy() -> None:
    policy = default_climate_policy()

    selected = policy.for_stage_phase("flower_early", "lights_on")

    assert selected.phase == "lights_on"
    assert selected.vpd_kpa.as_tuple() == (1.1, 1.3)
    assert selected.temperature_f.as_tuple() == (76.0, 78.0)
    assert selected.rh_max_pct == 65.0


def test_lights_state_selects_phase_name() -> None:
    assert phase_from_lights(True) == "lights_on"
    assert phase_from_lights(False) == "lights_off"


def test_lights_off_stage_policy_is_distinct_from_lights_on() -> None:
    policy = default_climate_policy()

    lights_off = policy.for_stage_phase("flower_early", "lights_off")

    assert lights_off.vpd_kpa.as_tuple() == (0.9, 1.1)
    assert lights_off.temperature_f.as_tuple() == (70.0, 72.0)
    assert lights_off.rh_max_pct == 75.0


def test_late_flower_lights_off_policy_stays_drier() -> None:
    policy = default_climate_policy()

    lights_off = policy.for_stage_phase("flower_late", "lights_off")

    assert lights_off.vpd_kpa.as_tuple() == (1.1, 1.3)
    assert lights_off.temperature_f.as_tuple() == (70.0, 72.0)
    assert lights_off.rh_max_pct == 60.0


def test_hard_minimum_temperature_is_explicit_and_configurable() -> None:
    default_policy = default_climate_policy()
    custom_policy = default_climate_policy(
        ClimatePolicyDefaults(hard_min_temperature_f=71.5)
    )

    assert default_policy.hard_min_temperature_f == 70.0
    assert custom_policy.hard_min_temperature_f == 71.5


def test_rh_max_values_are_explicit_by_stage_and_phase() -> None:
    policy = default_climate_policy()

    assert policy.for_stage_phase("veg", "lights_on").rh_max_pct == 70.0
    assert policy.for_stage_phase("veg", "lights_off").rh_max_pct == 75.0
    assert policy.for_stage_phase("flower_early", "lights_on").rh_max_pct == 65.0
    assert policy.for_stage_phase("flower_early", "lights_off").rh_max_pct == 75.0
    assert policy.for_stage_phase("flower_late", "lights_on").rh_max_pct == 55.0
    assert policy.for_stage_phase("flower_late", "lights_off").rh_max_pct == 60.0


def test_fan_limits_are_explicit_and_configurable() -> None:
    default_policy = default_climate_policy()
    custom_policy = default_climate_policy(
        ClimatePolicyDefaults(fan_floor_pct=15, fan_max_pct=70)
    )

    assert default_policy.fan.floor_pct == 20
    assert default_policy.fan.max_pct == 80
    assert custom_policy.fan.floor_pct == 15
    assert custom_policy.fan.max_pct == 70


def test_supported_heater_levels_are_thermoforge_off_plus_one_through_ten() -> None:
    policy = default_climate_policy()

    assert tuple(range(11)) == THERMOFORGE_SUPPORTED_LEVELS
    assert policy.heater.supported_levels == (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)


def test_stale_sensor_limits_default_to_existing_five_minute_guard() -> None:
    policy = default_climate_policy()

    assert policy.stale.temperature_s == 300.0
    assert policy.stale.humidity_s == 300.0
    assert policy.stale.vpd_s == 300.0
    assert policy.stale.fan_s == 300.0
    assert policy.stale.actuator_s == 300.0


def test_dehumidifier_cycle_policy_has_deadbands_and_minimum_durations() -> None:
    policy = default_climate_policy()

    assert policy.dehumidifier.vpd_deadband_kpa == 0.05
    assert policy.dehumidifier.rh_deadband_pct == 2.0
    assert policy.dehumidifier.minimum_on_s == 300.0
    assert policy.dehumidifier.minimum_off_s == 300.0


def test_policy_values_validate_basic_invariants() -> None:
    policy = default_climate_policy()

    with pytest.raises(ValueError, match="band low"):
        Band(2.0, 1.0)

    with pytest.raises(ValueError, match="every grow stage exactly once"):
        ClimatePolicy(
            stage_policies=(*policy.stage_policies, policy.stage_policies[0]),
            hard_min_temperature_f=policy.hard_min_temperature_f,
            fan=policy.fan,
            heater=policy.heater,
            stale=policy.stale,
            dehumidifier=policy.dehumidifier,
        )

    with pytest.raises(ValueError, match="fan policy"):
        FanPolicy(floor_pct=85, max_pct=80)

    with pytest.raises(ValueError, match="ThermoForge"):
        HeaterPolicy(supported_levels=(0, 1, 2))
