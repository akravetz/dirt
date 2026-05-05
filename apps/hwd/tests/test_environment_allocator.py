from __future__ import annotations

from datetime import UTC, datetime

from dirt_hwd.services.environment_allocator import (
    HumidifierAllocationConfig,
    HumidifierAllocationInput,
    allocate_humidifier_output,
)

T0 = datetime(2026, 5, 4, 18, 0, tzinfo=UTC)


def _cfg(**overrides) -> HumidifierAllocationConfig:
    base = dict(
        fan_floor_pct=15,
        fan_max_pct=70,
        fan_high_vpd_margin_kpa=0.05,
        fan_sensor_stale_s=300,
        rh_reenable_buffer_pct=2.0,
    )
    base.update(overrides)
    return HumidifierAllocationConfig(**base)


def _input(**overrides) -> HumidifierAllocationInput:
    base = dict(
        now=T0,
        requested_u_pct=15.0,
        requested_plug_on=True,
        vpd=1.31,
        rh=58.8,
        fan_pct=70.0,
        fan_age_s=30.0,
        vpd_band=(1.0, 1.3),
        rh_band=(40.0, 60.0),
    )
    base.update(overrides)
    return HumidifierAllocationInput(**base)


def test_blocks_humidifier_when_fan_is_saturated() -> None:
    out = allocate_humidifier_output(_cfg(), _input(fan_pct=70.0, rh=52.0, vpd=1.7))

    assert out.u_pct == 0.0
    assert out.plug_on is False
    assert out.reason == "fan_relief_first"


def test_blocks_near_rh_ceiling_while_fan_is_elevated() -> None:
    out = allocate_humidifier_output(_cfg(), _input(fan_pct=35.0, rh=58.5, vpd=1.6))

    assert out.u_pct == 0.0
    assert out.reason == "fan_relief_first"


def test_blocks_marginal_high_vpd_so_fan_can_step_down_first() -> None:
    out = allocate_humidifier_output(_cfg(), _input(fan_pct=45.0, rh=52.0, vpd=1.33))

    assert out.u_pct == 0.0
    assert out.reason == "fan_relief_first"


def test_allows_mist_when_fan_at_floor_and_rh_has_headroom() -> None:
    out = allocate_humidifier_output(_cfg(), _input(fan_pct=15.0, rh=52.0, vpd=1.7))

    assert out.u_pct == 15.0
    assert out.plug_on is True
    assert out.reason == "pi_request"


def test_allows_mist_on_stale_fan_reading() -> None:
    out = allocate_humidifier_output(
        _cfg(),
        _input(fan_pct=70.0, fan_age_s=600.0, rh=52.0, vpd=1.7),
    )

    assert out.u_pct == 15.0
    assert out.plug_on is True
    assert out.reason == "fan_unknown_passthrough"


def test_preserves_pi_off_request() -> None:
    out = allocate_humidifier_output(
        _cfg(),
        _input(requested_u_pct=0.0, requested_plug_on=False),
    )

    assert out.u_pct == 0.0
    assert out.plug_on is False
    assert out.reason == "pi_off"
