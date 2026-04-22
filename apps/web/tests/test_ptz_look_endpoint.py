"""Unit tests for POST /api/ptz/look.

Covers:
- xy normalization math (yaw_delta = x * 60°, pitch_delta = y * 40°)
- clamp to motor limits before the RPC
- 401 without a session cookie
- 422 on invalid body (out-of-range xy)
"""

from __future__ import annotations

import json

import pytest
from dirt_contracts.webapp_v1.models import PTZApplied
from httpx import ASGITransport, AsyncClient

from dirt_shared.services.ptz import (
    LOOK_PITCH_RANGE_DEG,
    LOOK_YAW_RANGE_DEG,
    PITCH_MAX,
    PITCH_MIN,
    YAW_MAX,
    PTZService,
)
from dirt_web.app import create_app
from dirt_web.deps import get_ptz


def _write_config(tmp_path):
    path = tmp_path / "camera.json"
    path.write_text(json.dumps({"presets": {}}))
    return path


class _FakeDaemon:
    """Records RPC calls; replies with deterministic state + move responses."""

    def __init__(
        self, *, cur_yaw: float, cur_pitch: float, cur_zoom: float = 1.0
    ) -> None:
        self.cur_yaw = cur_yaw
        self.cur_pitch = cur_pitch
        self.cur_zoom = cur_zoom
        self.calls: list[str] = []

    async def __call__(self, line: str) -> dict[str, str]:
        self.calls.append(line)
        if line == "get_state":
            return {
                "_status": "ok",
                "camera_connected": "true",
                "motor_yaw": str(self.cur_yaw),
                "motor_pitch": str(self.cur_pitch),
                "zoom": str(self.cur_zoom),
            }
        if line.startswith("move_motor"):
            _, pitch, yaw = line.split()
            self.cur_yaw = float(yaw)
            self.cur_pitch = float(pitch)
            return {
                "_status": "ok",
                "motor_pitch": pitch,
                "motor_yaw": yaw,
            }
        return {"_status": "error"}


@pytest.fixture
async def look_harness(app_engine, tmp_path):
    def _build(cur_yaw: float = 0.0, cur_pitch: float = 0.0):
        daemon = _FakeDaemon(cur_yaw=cur_yaw, cur_pitch=cur_pitch)
        ptz = PTZService(rpc=daemon, config_path=_write_config(tmp_path))
        app = create_app(engine=app_engine, run_mcp=False)
        app.dependency_overrides[get_ptz] = lambda: ptz
        return app, daemon

    return _build


@pytest.fixture
async def authed_client(app_engine, tmp_path):
    async def _build(cur_yaw: float = 0.0, cur_pitch: float = 0.0):
        daemon = _FakeDaemon(cur_yaw=cur_yaw, cur_pitch=cur_pitch)
        ptz = PTZService(rpc=daemon, config_path=_write_config(tmp_path))
        app = create_app(engine=app_engine, run_mcp=False)
        app.dependency_overrides[get_ptz] = lambda: ptz
        transport = ASGITransport(app=app)
        ac = AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        )
        login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "changeme"},
        )
        ac.cookies = login.cookies
        return ac, daemon

    return _build


async def test_look_applies_normalized_delta(authed_client):
    client, _daemon = await authed_client(cur_yaw=0.0, cur_pitch=0.0)
    try:
        # x=0.25 → +15° yaw; y=-0.25 → -10° pitch.
        response = await client.post("/api/ptz/look", json={"x": 0.25, "y": -0.25})
        assert response.status_code == 200
        model = PTZApplied.model_validate(response.json())
        assert model.ok is True
        assert model.preset is None
        assert model.yaw == pytest.approx(0.25 * LOOK_YAW_RANGE_DEG)
        assert model.pitch == pytest.approx(-0.25 * LOOK_PITCH_RANGE_DEG)
    finally:
        await client.aclose()


async def test_look_clamps_to_motor_limits(authed_client):
    # Already at the yaw edge; pushing +x further must clamp to YAW_MAX,
    # not overshoot.
    client, daemon = await authed_client(cur_yaw=YAW_MAX - 1, cur_pitch=0.0)
    try:
        response = await client.post("/api/ptz/look", json={"x": 0.5, "y": 0.5})
        assert response.status_code == 200
        model = PTZApplied.model_validate(response.json())
        assert model.yaw == pytest.approx(YAW_MAX)
        # +0.5 * 40° = +20° pitch from 0, within [PITCH_MIN, PITCH_MAX].
        assert PITCH_MIN <= model.pitch <= PITCH_MAX

        # Verify the clamp happened BEFORE the RPC — the move_motor
        # argument itself must be the clamped value, not the raw sum.
        move_calls = [c for c in daemon.calls if c.startswith("move_motor")]
        assert len(move_calls) == 1
        _, pitch_arg, yaw_arg = move_calls[0].split()
        assert float(yaw_arg) == pytest.approx(YAW_MAX)
        assert float(pitch_arg) == pytest.approx(20.0)
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "bad_body",
    [
        {"x": 0.8, "y": 0.0},  # x out of [-0.5, 0.5]
        {"x": 0.0, "y": -0.9},  # y out of range
        {"x": 0.1},  # missing y
        {"x": 0.1, "y": 0.1, "extra": True},  # additionalProperties: false
    ],
)
async def test_look_rejects_invalid_body(authed_client, bad_body):
    client, _ = await authed_client()
    try:
        response = await client.post("/api/ptz/look", json=bad_body)
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_look_requires_auth(look_harness):
    app, _ = look_harness()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.post("/api/ptz/look", json={"x": 0.0, "y": 0.0})
        assert response.status_code == 401
