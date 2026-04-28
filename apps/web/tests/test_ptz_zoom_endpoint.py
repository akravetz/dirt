"""Unit tests for POST /api/ptz/zoom.

Covers:
- XOR validation — exactly one of ``zoom`` / ``delta`` required
- absolute path → ``set_zoom <value>``
- relative path → ``get_state`` + ``set_zoom (cur + delta)``
- 401 without a session cookie
"""

from __future__ import annotations

import json

import pytest
from dirt_contracts.webapp_v1.models import PTZZoomResponse
from httpx import ASGITransport, AsyncClient

from dirt_shared.services.ptz import ZOOM_MAX, PTZService
from dirt_web.app import create_app
from dirt_web.deps import get_ptz


def _write_config(tmp_path):
    path = tmp_path / "camera.json"
    path.write_text(json.dumps({"presets": {}}))
    return path


class _FakeDaemon:
    def __init__(self, cur_zoom: float = 1.0) -> None:
        self.cur_zoom = cur_zoom
        self.calls: list[str] = []

    async def __call__(self, line: str) -> dict[str, str]:
        self.calls.append(line)
        if line == "get_state":
            return {
                "_status": "ok",
                "camera_connected": "true",
                "motor_yaw": "0",
                "motor_pitch": "0",
                "zoom": str(self.cur_zoom),
            }
        if line.startswith("set_zoom"):
            _, value = line.split()
            self.cur_zoom = float(value)
            return {"_status": "ok", "zoom": value}
        return {"_status": "error"}


@pytest.fixture
async def authed_client(tmp_path):
    async def _build(cur_zoom: float = 1.0):
        daemon = _FakeDaemon(cur_zoom=cur_zoom)
        ptz = PTZService(rpc=daemon, config_path=_write_config(tmp_path))
        app = create_app(run_mcp=False)
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


async def test_zoom_absolute(authed_client):
    client, daemon = await authed_client(cur_zoom=1.0)
    try:
        response = await client.post("/api/ptz/zoom", json={"zoom": 1.8})
        assert response.status_code == 200
        model = PTZZoomResponse.model_validate(response.json())
        assert model.ok is True
        assert model.zoom == pytest.approx(1.8)

        # Absolute path issues set_zoom directly — no preceding get_state
        # read for the current value.
        assert daemon.calls == ["set_zoom 1.80"]
    finally:
        await client.aclose()


async def test_zoom_relative_reads_current_then_sets(authed_client):
    client, daemon = await authed_client(cur_zoom=1.3)
    try:
        response = await client.post("/api/ptz/zoom", json={"delta": 0.2})
        assert response.status_code == 200
        model = PTZZoomResponse.model_validate(response.json())
        assert model.zoom == pytest.approx(1.5)

        assert daemon.calls == ["get_state", "set_zoom 1.50"]
    finally:
        await client.aclose()


async def test_zoom_relative_clamps_to_max(authed_client):
    client, _daemon = await authed_client(cur_zoom=1.9)
    try:
        response = await client.post("/api/ptz/zoom", json={"delta": 1.0})
        assert response.status_code == 200
        model = PTZZoomResponse.model_validate(response.json())
        assert model.zoom == pytest.approx(ZOOM_MAX)
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "body",
    [
        {},  # neither
        {"zoom": 1.5, "delta": 0.2},  # both
    ],
)
async def test_zoom_xor_violation_returns_400(authed_client, body):
    client, daemon = await authed_client()
    try:
        response = await client.post("/api/ptz/zoom", json=body)
        assert response.status_code == 400
        # No daemon RPC fires when XOR validation fails.
        assert daemon.calls == []
    finally:
        await client.aclose()


async def test_zoom_requires_auth(tmp_path):
    daemon = _FakeDaemon()
    ptz = PTZService(rpc=daemon, config_path=_write_config(tmp_path))
    app = create_app(run_mcp=False)
    app.dependency_overrides[get_ptz] = lambda: ptz
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.post("/api/ptz/zoom", json={"zoom": 1.5})
        assert response.status_code == 401
