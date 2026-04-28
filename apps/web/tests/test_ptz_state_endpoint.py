"""Unit tests for GET /api/ptz/state.

Thin wrapper over ``PTZService.get_state``. Tests inject a fake
``rpc`` callable and a tmp-path ``camera.json`` via
``app.dependency_overrides`` so neither the camera daemon socket
nor the user's home directory are touched.
"""

from __future__ import annotations

import json

import pytest
from dirt_contracts.webapp_v1.models import PTZState
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
            "description": "wide · full tent",
        },
        "plant_a": {
            "pitch": -38,
            "yaw": -55,
            "zoom": 1.5,
            "description": "Plant A close-up (yellow)",
        },
        "plant_b": {
            "pitch": -40,
            "yaw": -20,
            "zoom": 1.5,
            "description": "Plant B close-up (orange)",
        },
    }
}


def _write_camera_config(tmp_path):
    path = tmp_path / "camera.json"
    path.write_text(json.dumps(_CAMERA_CONFIG))
    return path


def _make_ptz(tmp_path, rpc_response):
    async def _rpc(_line: str):
        return rpc_response

    return PTZService(rpc=_rpc, config_path=_write_camera_config(tmp_path))


@pytest.fixture
async def client(tmp_path):
    app = create_app(run_mcp=False)
    ptz = _make_ptz(
        tmp_path,
        {
            "_status": "ok",
            "camera_connected": "true",
            "motor_yaw": "-55",
            "motor_pitch": "-38",
            "zoom": "1.5",
        },
    )
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
        yield ac


async def test_ptz_state_returns_contract_shape(client: AsyncClient):
    response = await client.get("/api/ptz/state")
    assert response.status_code == 200
    model = PTZState.model_validate(response.json())

    assert model.connected is True
    assert model.yaw == -55.0
    assert model.pitch == -38.0
    assert model.zoom == 1.5
    # Currently sitting at the plant_a preset within tolerance.
    assert model.preset == "plant_a"

    # Presets come from camera.json; the service fills label/description
    # and augments plant_* rows with sticker_color from the default map.
    by_id = {p.id: p for p in model.presets}
    assert set(by_id) == {"overview", "plant_a", "plant_b"}
    assert by_id["plant_a"].sticker_color == "yellow"
    assert by_id["plant_a"].yaw == -55.0
    assert by_id["plant_a"].pitch == -38.0
    assert by_id["plant_a"].zoom == 1.5
    assert by_id["overview"].sticker_color is None


async def test_ptz_state_disconnected_when_daemon_down(tmp_path):
    app = create_app(run_mcp=False)
    ptz = _make_ptz(tmp_path, {"_status": "error", "msg": "daemon_unreachable"})
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

        response = await ac.get("/api/ptz/state")
        assert response.status_code == 200
        model = PTZState.model_validate(response.json())
        assert model.connected is False
        assert model.preset is None
        # Presets still come back from the config file even if the
        # daemon is down — FE uses them to render the preset row
        # regardless of camera connectivity.
        assert {p.id for p in model.presets} == {"overview", "plant_a", "plant_b"}


async def test_ptz_state_preset_null_when_not_at_preset(tmp_path):
    app = create_app(run_mcp=False)
    ptz = _make_ptz(
        tmp_path,
        {
            "_status": "ok",
            "camera_connected": "true",
            "motor_yaw": "12.5",
            "motor_pitch": "-25",
            "zoom": "1.2",
        },
    )
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

        response = await ac.get("/api/ptz/state")
        model = PTZState.model_validate(response.json())
        assert model.preset is None


async def test_ptz_state_requires_auth():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/ptz/state")
        assert response.status_code == 401
