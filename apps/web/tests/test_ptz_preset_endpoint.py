"""Unit tests for POST /api/ptz/preset/{id}."""

from __future__ import annotations

import json

import pytest
from dirt_contracts.webapp_v1.models import PTZApplied
from httpx import ASGITransport, AsyncClient

from dirt_shared.services.ptz import PTZService
from dirt_web.app import create_app
from dirt_web.deps import get_ptz

_CAMERA_CONFIG = {
    "presets": {
        "overview": {
            "pitch": -10,
            "yaw": 0,
            "zoom": 1.0,
            "description": "wide",
        },
        "plant_a": {
            "pitch": -38,
            "yaw": -55,
            "zoom": 1.5,
            "description": "Plant A",
        },
    }
}


class _RecordingRpc:
    """Fake daemon RPC that records every call and replies with deterministic ok responses."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, line: str) -> dict[str, str]:
        self.calls.append(line)
        if line.startswith("move_motor"):
            _, pitch, yaw = line.split()
            return {
                "_status": "ok",
                "motor_pitch": pitch,
                "motor_yaw": yaw,
            }
        if line.startswith("set_zoom"):
            _, zoom = line.split()
            return {"_status": "ok", "zoom": zoom}
        return {"_status": "error"}


def _write_config(tmp_path):
    path = tmp_path / "camera.json"
    path.write_text(json.dumps(_CAMERA_CONFIG))
    return path


@pytest.fixture
async def ptz_harness(tmp_path):
    rpc = _RecordingRpc()
    ptz = PTZService(rpc=rpc, config_path=_write_config(tmp_path))
    app = create_app(run_mcp=False)
    app.dependency_overrides[get_ptz] = lambda: ptz
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "changeme"},
        )
        ac.cookies = login.cookies
        yield ac, rpc


async def test_preset_happy_path(ptz_harness):
    client, rpc = ptz_harness
    response = await client.post("/api/ptz/preset/plant_a")
    assert response.status_code == 200
    model = PTZApplied.model_validate(response.json())

    assert model.ok is True
    assert model.preset == "plant_a"
    assert model.yaw == -55.0
    assert model.pitch == -38.0
    assert model.zoom == 1.5

    # Service issues move_motor + set_zoom (order may vary due to
    # asyncio.gather; assert set membership, not order).
    assert {"move_motor -38.00 -55.00", "set_zoom 1.50"} <= set(rpc.calls)


async def test_preset_404_on_unknown(ptz_harness):
    client, rpc = ptz_harness
    response = await client.post("/api/ptz/preset/nonexistent")
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "nonexistent" in detail
    # No daemon RPCs fired for an unknown preset — validation happens
    # before the socket round-trip.
    assert rpc.calls == []


async def test_preset_requires_auth(tmp_path):
    rpc = _RecordingRpc()
    ptz = PTZService(rpc=rpc, config_path=_write_config(tmp_path))
    app = create_app(run_mcp=False)
    app.dependency_overrides[get_ptz] = lambda: ptz
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.post("/api/ptz/preset/plant_a")
        assert response.status_code == 401
