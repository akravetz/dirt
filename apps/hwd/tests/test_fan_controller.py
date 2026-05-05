from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from dirt_hwd.services.fan_controller import (
    FanTrimInput,
    FanTrimLoopService,
    FanTrimState,
    decide_fan_trim,
)
from dirt_shared.config import FanTrimConfig
from dirt_shared.services.grow_state import GrowContext, LightsState

T0 = datetime(2026, 5, 3, 20, 0, tzinfo=UTC)


def _cfg(**overrides) -> FanTrimConfig:
    base = dict(
        base_url="http://fan-controller.local",
        min_pct=15,
        max_pct=70,
        step_pct=5,
        step_interval_s=300,
        high_vpd_step_pct=10,
        high_vpd_step_interval_s=180,
        high_vpd_margin_kpa=0.05,
        poll_interval=60,
        sensor_stale_s=300,
        drydown_minutes=60,
        drydown_pct=45,
        drydown_rh_buffer_pct=2.0,
        recover_rh_buffer_pct=2.0,
        recover_vpd_margin_kpa=0.05,
        recover_hold_s=300,
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
            last_change_ts=T0 - timedelta(minutes=6),
            recover_since=T0 - timedelta(minutes=6),
        ),
        _input(current_pct=45, vpd=1.1, rh=55.0),
    )

    assert decision.target_pct == 40
    assert decision.reason == "trim_down_recovered"


def test_high_vpd_steps_down_faster_than_normal_recovery():
    decision = decide_fan_trim(
        _cfg(),
        FanTrimState(last_change_ts=T0 - timedelta(minutes=4)),
        _input(current_pct=70, vpd=1.38, rh=55.0),
    )

    assert decision.target_pct == 60
    assert decision.reason == "trim_down_high_vpd"


def test_high_vpd_step_down_is_rate_limited_separately():
    decision = decide_fan_trim(
        _cfg(),
        FanTrimState(last_change_ts=T0 - timedelta(minutes=2)),
        _input(current_pct=70, vpd=1.38, rh=55.0),
    )

    assert decision.target_pct == 70
    assert decision.reason == "hold_rate_limited"


def test_high_vpd_does_not_override_high_rh_step_up():
    decision = decide_fan_trim(
        _cfg(),
        FanTrimState(last_change_ts=T0 - timedelta(minutes=6)),
        _input(current_pct=60, vpd=1.38, rh=61.0),
    )

    assert decision.target_pct == 65
    assert decision.reason == "humid_trim_up_high_rh"


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
    assert high.target_pct == 70
    assert low.reason == "enforce_bounds"
    assert high.reason == "enforce_bounds"


class _Reading:
    def __init__(self, value: float, ts: datetime) -> None:
        self.value = value
        self.ts = ts


class _FakeReadings:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get_latest_reading(self, metric: str, **kwargs):
        self.calls.append((metric, dict(kwargs)))
        if metric == "vpd_kpa":
            return _Reading(1.1, T0)
        if metric == "humidity_pct":
            return _Reading(55.0, T0)
        return None


class _FakeGrow:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def current_context(self, **kwargs) -> GrowContext:
        self.calls.append(dict(kwargs))
        return GrowContext(
            stage="flower_early",
            lights=LightsState(
                on=True,
                minutes_until_off=180.0,
                minutes_until_on=540.0,
            ),
            targets={
                "vpd_kpa": (1.0, 1.3),
                "humidity_pct": (40.0, 60.0),
            },
        )


async def test_fan_loop_reads_main_canopy_scope() -> None:
    readings = _FakeReadings()
    grow = _FakeGrow()
    stop_event = asyncio.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/fan":
            stop_event.set()
            return httpx.Response(
                200,
                json={"set_duty_pct": 35, "reported_duty_pct": 35},
            )
        pytest.fail(f"unexpected fan request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    service = FanTrimLoopService(
        _cfg(poll_interval=30),
        readings=readings,
        grow=grow,
        clock=lambda: T0,
        http_factory=lambda: httpx.AsyncClient(transport=transport),
    )

    await asyncio.wait_for(service.run(stop_event), timeout=2.0)

    assert grow.calls == [{"site_id": "homebox", "tent_id": "main"}]
    assert readings.calls == [
        (
            "vpd_kpa",
            {
                "site_id": "homebox",
                "tent_id": "main",
                "zone_id": "canopy",
                "device_id": "fan-controller",
                "capability_id": "vpd_kpa",
            },
        ),
        (
            "humidity_pct",
            {
                "site_id": "homebox",
                "tent_id": "main",
                "zone_id": "canopy",
                "device_id": "fan-controller",
                "capability_id": "humidity_pct",
            },
        ),
    ]
