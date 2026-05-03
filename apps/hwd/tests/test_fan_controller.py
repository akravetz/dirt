from __future__ import annotations

from datetime import UTC, datetime, timedelta

from dirt_hwd.services.fan_controller import (
    FanTrimInput,
    FanTrimState,
    decide_fan_trim,
)
from dirt_shared.config import FanTrimConfig
from dirt_shared.services.grow_state import LightsState

T0 = datetime(2026, 5, 3, 20, 0, tzinfo=UTC)


def _cfg(**overrides) -> FanTrimConfig:
    base = dict(
        base_url="http://fan-controller.local",
        min_pct=15,
        max_pct=60,
        step_pct=5,
        step_interval_s=300,
        poll_interval=60,
        sensor_stale_s=300,
        drydown_minutes=60,
        drydown_pct=45,
        drydown_rh_buffer_pct=2.0,
        recover_rh_buffer_pct=2.0,
        recover_vpd_margin_kpa=0.05,
        recover_hold_s=900,
    )
    base.update(overrides)
    return FanTrimConfig(**base)


def _input(**overrides) -> FanTrimInput:
    base = dict(
        now=T0,
        current_pct=35,
        vpd=1.1,
        vpd_age_s=30.0,
        rh=55.0,
        rh_age_s=30.0,
        vpd_band=(1.0, 1.3),
        rh_band=(40.0, 60.0),
        lights=LightsState(
            on=True,
            minutes_until_off=180.0,
            minutes_until_on=540.0,
        ),
    )
    base.update(overrides)
    return FanTrimInput(**base)


def test_pre_lights_off_drydown_jumps_to_floor():
    decision = decide_fan_trim(
        _cfg(),
        FanTrimState(),
        _input(
            current_pct=15,
            rh=59.0,
            lights=LightsState(on=True, minutes_until_off=45.0, minutes_until_on=675.0),
        ),
    )

    assert decision.target_pct == 45
    assert decision.reason == "pre_lights_off_drydown"
    assert decision.new_state.last_change_ts == T0


def test_high_rh_steps_up_after_drydown_floor_is_met():
    decision = decide_fan_trim(
        _cfg(),
        FanTrimState(last_change_ts=T0 - timedelta(minutes=6)),
        _input(
            current_pct=45,
            rh=70.0,
            lights=LightsState(on=True, minutes_until_off=45.0, minutes_until_on=675.0),
        ),
    )

    assert decision.target_pct == 50
    assert decision.reason == "humid_trim_up_high_rh"


def test_low_vpd_step_up_is_rate_limited():
    decision = decide_fan_trim(
        _cfg(),
        FanTrimState(last_change_ts=T0 - timedelta(minutes=2)),
        _input(current_pct=35, vpd=0.8, rh=55.0),
    )

    assert decision.target_pct == 35
    assert decision.reason == "hold_rate_limited"


def test_recovery_hold_then_steps_down_toward_min():
    recovering = decide_fan_trim(
        _cfg(),
        FanTrimState(),
        _input(current_pct=45, vpd=1.1, rh=55.0),
    )

    assert recovering.target_pct == 45
    assert recovering.reason == "hold_recovering"

    decision = decide_fan_trim(
        _cfg(),
        FanTrimState(
            last_change_ts=T0 - timedelta(minutes=20),
            recover_since=T0 - timedelta(minutes=16),
        ),
        _input(current_pct=45, vpd=1.1, rh=55.0),
    )

    assert decision.target_pct == 40
    assert decision.reason == "trim_down_recovered"


def test_stale_sensor_holds_fan():
    decision = decide_fan_trim(
        _cfg(),
        FanTrimState(),
        _input(vpd=0.7, vpd_age_s=600.0, rh=75.0),
    )

    assert decision.target_pct == 35
    assert decision.reason == "hold_stale_sensor"


def test_enforces_configured_min_and_max():
    low = decide_fan_trim(_cfg(), FanTrimState(), _input(current_pct=5))
    high = decide_fan_trim(_cfg(), FanTrimState(), _input(current_pct=90))

    assert low.target_pct == 15
    assert high.target_pct == 60
    assert low.reason == "enforce_bounds"
    assert high.reason == "enforce_bounds"
