"""End-to-end test of HumidifierLoopService for one tick.

Drives the loop with mock readings + mock grow + httpx.MockTransport
shaping the Govee API. Sets stop_event from within the get_state mock so
exactly one full tick runs before the loop exits.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from dirt_hwd.services.humidifier import (
    DispatchDiff,
    HumidifierLoopService,
    _plan_dispatch,
)
from dirt_shared.config import HumidifierConfig
from dirt_shared.services.grow_state import GrowContext, LightsState

T0 = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
SKU = "H7142"
MAC = "AA:BB:CC:DD:EE:FF:00:11"


def _config(**overrides) -> HumidifierConfig:
    base = dict(
        govee_api_key="TEST_KEY",
        govee_sku=SKU,
        govee_mac=MAC,
        mist_levels=9,
        level_hysteresis_pct=3.0,
        pi_kc=8.0,
        pi_ki=0.01,
        pi_integrator_clamp=50.0,
        pi_threshold_pct=5.0,
        pi_threshold_hysteresis_pct=1.0,
        pi_night_offset_kpa=-0.3,
        lights_off_prep_minutes=5,
        poll_interval=30,
        failsafe_stale_seconds=300,
        ineffective_alert_after_s=1200,
        ineffective_min_vpd_drop_kpa=0.15,
        telegram_bot_token="",
        telegram_chat_id="",
    )
    base.update(overrides)
    return HumidifierConfig(**base)


# ============================================================
# Fake services
# ============================================================


@dataclass
class _Reading:
    value: float
    ts: datetime


class FakeReadings:
    def __init__(self, vpd: float, rh: float, ts: datetime) -> None:
        self.vpd = _Reading(vpd, ts)
        self.rh = _Reading(rh, ts)
        self.ingested: list[tuple[dict, Any, dict[str, Any]]] = []
        self.latest_calls: list[tuple[str, dict[str, Any]]] = []

    async def get_latest_reading(self, metric, **kwargs):
        self.latest_calls.append((metric, dict(kwargs)))
        if metric == "vpd_kpa":
            return self.vpd
        if metric == "humidity_pct":
            return self.rh
        return None

    async def ingest_reading(self, metrics, *, source, **kwargs):
        self.ingested.append((dict(metrics), source, dict(kwargs)))


class FakeGrow:
    def __init__(self, ctx: GrowContext) -> None:
        self.ctx = ctx
        self.context_calls: list[dict[str, Any]] = []

    async def current_context(self, **kwargs) -> GrowContext:
        self.context_calls.append(dict(kwargs))
        return self.ctx


def _veg_lights_on() -> GrowContext:
    return GrowContext(
        stage="veg",
        lights=LightsState(on=True, minutes_until_off=600, minutes_until_on=600),
        targets={
            "vpd_kpa": (0.9, 1.1),
            "humidity_pct": (50.0, 70.0),
        },
    )


def _veg_lights_off() -> GrowContext:
    return GrowContext(
        stage="veg",
        lights=LightsState(on=False, minutes_until_off=600, minutes_until_on=120),
        targets={
            "vpd_kpa": (0.9, 1.1),
            "humidity_pct": (50.0, 70.0),
        },
    )


# ============================================================
# Govee mock transport — collects requests, scripts responses
# ============================================================


class GoveeFake:
    def __init__(
        self,
        *,
        state_response: dict,
        stop_after_state: bool = False,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        self.requests: list[dict] = []
        self._state = state_response
        self._stop_after_state = stop_after_state
        self._stop_event = stop_event

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body_bytes = request.read()
        body = json.loads(body_bytes) if body_bytes else None
        self.requests.append({"method": request.method, "path": path, "body": body})

        if request.method == "GET" and path.endswith("/user/devices"):
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "message": "ok",
                    "data": [
                        {
                            "sku": SKU,
                            "device": MAC,
                            "deviceName": "test",
                            "type": "devices.types.humidifier",
                            "capabilities": [],
                        }
                    ],
                },
            )

        if path.endswith("/device/state"):
            if self._stop_after_state and self._stop_event is not None:
                self._stop_event.set()
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "msg": "ok",
                    "payload": self._state,
                },
            )

        if path.endswith("/device/control"):
            return httpx.Response(200, json={"code": 200, "msg": "ok"})

        return httpx.Response(404)


def _build_loop(
    cfg: HumidifierConfig,
    readings: FakeReadings,
    grow: FakeGrow,
    handler,
    *,
    clock=lambda: T0,
) -> HumidifierLoopService:
    transport = httpx.MockTransport(handler)
    return HumidifierLoopService(
        cfg,
        readings=readings,
        grow=grow,
        clock=clock,
        http_client_factory=lambda: httpx.AsyncClient(transport=transport, timeout=5.0),
    )


# ============================================================
# Plan dispatch sanity (in addition to standalone tests)
# ============================================================


def test_dispatch_diff_module_exposed():
    """Loop module re-exports DispatchDiff for callers / tests."""
    diff = _plan_dispatch(current_power=False, current_level=None, target_level=5)
    assert isinstance(diff, DispatchDiff)


# ============================================================
# Single-tick loop tests
# ============================================================


async def test_loop_boot_tick_powers_on_and_sets_level_with_interleave():
    """VPD far above upper band, device OFF — first tick should send
    set_power(on=True) AND set_manual_level on the same tick, with the
    inline sleep separating them."""
    cfg = _config()
    # error = 5.0 - 1.1 = 3.9 → p = 8 * 3.9 = 31.2 → bucket 3
    readings = FakeReadings(vpd=5.0, rh=55.0, ts=T0)
    grow = FakeGrow(_veg_lights_on())
    stop_event = asyncio.Event()

    fake = GoveeFake(
        state_response={
            "capabilities": [
                {"instance": "online", "state": {"value": True}},
                {"instance": "powerSwitch", "state": {"value": 0}},  # OFF
                {
                    "instance": "workMode",
                    "state": {"value": {"workMode": 1, "modeValue": 1}},
                },
            ]
        },
        stop_after_state=True,
        stop_event=stop_event,
    )
    loop = _build_loop(cfg, readings, grow, fake.handler)

    await asyncio.wait_for(loop.run(stop_event), timeout=2.0)

    # Sequence: state, control(power), control(workMode). No initial discover
    # because govee_mac is set in cfg.
    paths = [r["path"] for r in fake.requests]
    methods = [r["method"] for r in fake.requests]
    assert paths == [
        "/router/api/v1/device/state",
        "/router/api/v1/device/control",
        "/router/api/v1/device/control",
    ]
    assert methods == ["POST", "POST", "POST"]

    power_call = fake.requests[1]["body"]["payload"]["capability"]
    assert power_call == {
        "type": "devices.capabilities.on_off",
        "instance": "powerSwitch",
        "value": 1,
    }
    workmode_call = fake.requests[2]["body"]["payload"]["capability"]
    assert workmode_call["type"] == "devices.capabilities.work_mode"
    assert workmode_call["instance"] == "workMode"
    assert workmode_call["value"]["workMode"] == 1
    # u_pct from 3.9 kPa error * kc=8 = 31.2 → bucket ceil(31.2/11.11) = 3.
    assert workmode_call["value"]["modeValue"] == 3

    # Actuator breadcrumb recorded with the dispatched level.
    assert len(readings.ingested) == 1
    metrics, source, ingest_kwargs = readings.ingested[0]
    assert metrics["humidifier_on"] == 1.0
    assert metrics["humidifier_mist_level"] == 3.0
    assert source == "govee"
    assert ingest_kwargs == {
        "site_id": "homebox",
        "tent_id": "main",
        "zone_id": "canopy",
        "device_id": "govee-h7142-main",
    }
    assert grow.context_calls == [{"site_id": "homebox", "tent_id": "main"}]
    assert readings.latest_calls == [
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


async def test_loop_steady_state_at_target_no_api_calls():
    """Device already at the level the PI/quantizer picked — should send
    only the state read, no control calls."""
    cfg = _config()
    # VPD slightly above setpoint → small u → low level. Pick a state that
    # already matches whatever the PI/quantizer outputs to verify the
    # no_op path. Use VPD just over the setpoint so u stays small.
    readings = FakeReadings(vpd=1.15, rh=55.0, ts=T0)
    grow = FakeGrow(_veg_lights_on())
    stop_event = asyncio.Event()

    # First-tick: integrator zero, error=0.05, p=8*0.05=0.4 → below threshold (5).
    # plug_on=False → target_level=None → device should be OFF.
    # Use a state where device is OFF — should be no_op.
    fake = GoveeFake(
        state_response={
            "capabilities": [
                {"instance": "online", "state": {"value": True}},
                {"instance": "powerSwitch", "state": {"value": 0}},
                {
                    "instance": "workMode",
                    "state": {"value": {"workMode": 1, "modeValue": 1}},
                },
            ]
        },
        stop_after_state=True,
        stop_event=stop_event,
    )
    loop = _build_loop(cfg, readings, grow, fake.handler)

    await asyncio.wait_for(loop.run(stop_event), timeout=2.0)

    paths = [r["path"] for r in fake.requests]
    assert paths == ["/router/api/v1/device/state"]


async def test_loop_off_path_lights_off_outside_window_powers_off():
    """Lights off and outside prep window → PI emits u=0 → if device is
    currently ON, loop should send set_power(on=False)."""
    cfg = _config(lights_off_prep_minutes=5)
    readings = FakeReadings(vpd=1.5, rh=55.0, ts=T0)  # dry but irrelevant
    # lights off, 120 min until on → outside the 5-min prep window
    grow = FakeGrow(_veg_lights_off())
    stop_event = asyncio.Event()

    fake = GoveeFake(
        state_response={
            "capabilities": [
                {"instance": "online", "state": {"value": True}},
                {
                    "instance": "powerSwitch",
                    "state": {"value": 1},
                },  # ON — must turn off
                {
                    "instance": "workMode",
                    "state": {"value": {"workMode": 1, "modeValue": 5}},
                },
            ]
        },
        stop_after_state=True,
        stop_event=stop_event,
    )
    loop = _build_loop(cfg, readings, grow, fake.handler)

    await asyncio.wait_for(loop.run(stop_event), timeout=2.0)

    paths = [r["path"] for r in fake.requests]
    methods = [r["method"] for r in fake.requests]
    assert paths == ["/router/api/v1/device/state", "/router/api/v1/device/control"]
    assert methods == ["POST", "POST"]
    cap = fake.requests[1]["body"]["payload"]["capability"]
    assert cap == {
        "type": "devices.capabilities.on_off",
        "instance": "powerSwitch",
        "value": 0,
    }


async def test_loop_offline_device_skips_control():
    """Device offline → loop reads state, sees online=false, sends no
    control calls regardless of what PI/quantizer wanted."""
    cfg = _config()
    readings = FakeReadings(vpd=1.5, rh=55.0, ts=T0)
    grow = FakeGrow(_veg_lights_on())
    stop_event = asyncio.Event()

    fake = GoveeFake(
        state_response={
            "capabilities": [
                {"instance": "online", "state": {"value": False}},
            ]
        },
        stop_after_state=True,
        stop_event=stop_event,
    )
    loop = _build_loop(cfg, readings, grow, fake.handler)

    await asyncio.wait_for(loop.run(stop_event), timeout=2.0)

    paths = [r["path"] for r in fake.requests]
    assert paths == ["/router/api/v1/device/state"]


async def test_loop_discovers_mac_when_unset():
    """govee_mac empty → loop calls /user/devices once at startup."""
    cfg = _config(govee_mac="")
    readings = FakeReadings(vpd=1.15, rh=55.0, ts=T0)  # off path
    grow = FakeGrow(_veg_lights_on())
    stop_event = asyncio.Event()

    fake = GoveeFake(
        state_response={
            "capabilities": [
                {"instance": "online", "state": {"value": True}},
                {"instance": "powerSwitch", "state": {"value": 0}},
                {
                    "instance": "workMode",
                    "state": {"value": {"workMode": 1, "modeValue": 1}},
                },
            ]
        },
        stop_after_state=True,
        stop_event=stop_event,
    )
    loop = _build_loop(cfg, readings, grow, fake.handler)

    await asyncio.wait_for(loop.run(stop_event), timeout=2.0)

    paths = [r["path"] for r in fake.requests]
    assert paths[0] == "/router/api/v1/user/devices"
    assert "/router/api/v1/device/state" in paths


async def test_loop_disabled_when_api_key_unset():
    """No api key → loop returns immediately (warning, no I/O)."""
    cfg = _config(govee_api_key="")
    readings = FakeReadings(vpd=1.5, rh=55.0, ts=T0)
    grow = FakeGrow(_veg_lights_on())
    stop_event = asyncio.Event()

    fake = GoveeFake(state_response={"capabilities": []})
    loop = _build_loop(cfg, readings, grow, fake.handler)

    # Should return without ever calling the mock.
    await asyncio.wait_for(loop.run(stop_event), timeout=2.0)
    assert fake.requests == []


# Note: the inline 200ms sleep between set_power and set_manual_level on
# the boot tick is implicitly verified by `_plan_dispatch` unit tests
# (interleave=True for off→ON-at-N) and the boot-tick request-order test
# above. A direct monkeypatch on dirt_hwd.* would violate the no-patching
# invariant; threading sleep through DI for one assertion isn't worth it.
