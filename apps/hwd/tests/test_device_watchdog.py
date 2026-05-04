"""Tests for the device watchdog Telegram alerter."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs

import httpx
import pytest

from dirt_hwd.services.device_watchdog import (
    DeviceWatchdogConfig,
    DeviceWatchdogService,
    _diff,
    _format_age,
)
from dirt_shared.services.system_status import (
    DeviceKind,
    DeviceStatus,
    DeviceStatus_t,
)


class _FakeStatus:
    def __init__(self, devices: list[DeviceStatus]) -> None:
        self._devices = devices

    async def get_device_statuses(self) -> list[DeviceStatus]:
        return list(self._devices)


def _device(
    name: str,
    status: DeviceStatus_t,
    last_seen: datetime | None = datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    kind: DeviceKind = "moisture_node",
    device_id: str | None = None,
) -> DeviceStatus:
    return DeviceStatus(
        name=name,
        kind=kind,
        status=status,
        last_seen=last_seen,
        device_id=device_id,
    )


def _capture_transport(
    sink: list[dict[str, str]],
) -> httpx.MockTransport:
    """Telegram sendMessage stub. Decodes the form body so assertions can
    compare human-readable strings instead of URL-encoded ones."""

    def handler(request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        sink.append(form)
        return httpx.Response(200, json={"ok": True, "result": {}})

    return httpx.MockTransport(handler)


async def _run_one_tick(svc: DeviceWatchdogService) -> None:
    # A short wall-clock sleep lets the httpx POST in the loop complete
    # before we signal stop; an immediate stop would interrupt the send
    # mid-flight and drop the alert the test asserts on.
    stop = asyncio.Event()
    task = asyncio.create_task(svc.run(stop))
    await asyncio.sleep(0.2)
    stop.set()
    await asyncio.wait_for(task, timeout=2.0)


def _make_service(
    status: _FakeStatus,
    state_path: Path,
    transport: httpx.MockTransport,
) -> DeviceWatchdogService:
    cfg = DeviceWatchdogConfig(
        poll_interval=1,
        state_path=state_path,
        telegram_bot_token="test-token",
        telegram_chat_id="chat-1",
    )
    return DeviceWatchdogService(
        cfg,
        system_status=cast("object", status),  # type: ignore[arg-type]
        http_client_factory=lambda: httpx.AsyncClient(transport=transport),
    )


@pytest.mark.asyncio
async def test_cold_start_seeds_silently(tmp_path: Path) -> None:
    calls: list[dict[str, str]] = []
    status = _FakeStatus([_device("plant_a", "offline"), _device("plant_b", "ok")])
    svc = _make_service(status, tmp_path / "state.json", _capture_transport(calls))

    await _run_one_tick(svc)

    assert calls == []
    state = json.loads((tmp_path / "state.json").read_text())
    assert state == {"plant_a": "offline", "plant_b": "ok"}


@pytest.mark.asyncio
async def test_state_keys_use_stable_device_id(tmp_path: Path) -> None:
    calls: list[dict[str, str]] = []
    status = _FakeStatus(
        [_device("ESP32-C3 · plant_a", "ok", device_id="plant-a-node")]
    )
    svc = _make_service(status, tmp_path / "state.json", _capture_transport(calls))

    await _run_one_tick(svc)

    assert calls == []
    state = json.loads((tmp_path / "state.json").read_text())
    assert state == {"plant-a-node": "ok"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("seeded", "new_status", "expected_substring"),
    [
        ("ok", "offline", "offline"),
        ("offline", "ok", "back online"),
    ],
)
async def test_boundary_crossing_fires_alert(
    tmp_path: Path,
    seeded: DeviceStatus_t,
    new_status: DeviceStatus_t,
    expected_substring: str,
) -> None:
    state_path = tmp_path / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"plant_a": seeded}))

    calls: list[dict[str, str]] = []
    svc = _make_service(
        _FakeStatus([_device("plant_a", new_status)]),
        state_path,
        _capture_transport(calls),
    )

    await _run_one_tick(svc)

    assert len(calls) == 1
    assert calls[0]["chat_id"] == "chat-1"
    assert "plant_a" in calls[0]["text"]
    assert expected_substring in calls[0]["text"]


@pytest.mark.asyncio
async def test_warn_flap_does_not_fire(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"plant_a": "ok"}))

    calls: list[dict[str, str]] = []
    svc = _make_service(
        _FakeStatus([_device("plant_a", "warn")]),
        state_path,
        _capture_transport(calls),
    )

    await _run_one_tick(svc)

    assert calls == []


@pytest.mark.asyncio
async def test_stable_state_does_not_rewrite_file(tmp_path: Path) -> None:
    """Efficiency guard: no change → no disk write."""
    state_path = tmp_path / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"plant_a": "ok"}))
    mtime_before = state_path.stat().st_mtime_ns

    calls: list[dict[str, str]] = []
    svc = _make_service(
        _FakeStatus([_device("plant_a", "ok")]),
        state_path,
        _capture_transport(calls),
    )

    await _run_one_tick(svc)

    assert state_path.stat().st_mtime_ns == mtime_before


def test_diff_skips_devices_without_last_seen() -> None:
    assert (
        _diff({"reservoir": "offline"}, [_device("reservoir", "offline", None)]) == []
    )


def test_diff_ignores_unchanged_status() -> None:
    assert (
        _diff(
            {"plant_a": "ok", "plant_b": "offline"},
            [_device("plant_a", "ok"), _device("plant_b", "offline")],
        )
        == []
    )


def test_diff_ignores_new_device_first_sighting() -> None:
    # Adding a new node to the fleet should not fire an alert.
    assert _diff({}, [_device("plant_a", "offline")]) == []


def test_diff_detects_ok_to_offline() -> None:
    transitions = _diff({"plant_a": "ok"}, [_device("plant_a", "offline")])
    assert len(transitions) == 1
    assert transitions[0].old == "ok"
    assert transitions[0].new == "offline"


def test_format_age_bucketing() -> None:
    now = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
    assert _format_age(now, None) == "never"
    assert _format_age(now, datetime(2026, 4, 22, 11, 59, 30, tzinfo=UTC)) == "30s ago"
    assert _format_age(now, datetime(2026, 4, 22, 11, 55, 0, tzinfo=UTC)) == "5m ago"
    assert _format_age(now, datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)) == "2h ago"
    assert _format_age(now, datetime(2026, 4, 22, 9, 30, 0, tzinfo=UTC)) == "2h 30m ago"
