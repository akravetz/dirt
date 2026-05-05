from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

import dirt_control
from dirt_control.db import create_sessionmaker
from dirt_control.models import CloudAsset, CloudCommand, CloudLatestMetric, CloudTent

FIXED_NOW = datetime(2026, 5, 5, 3, 45, tzinfo=UTC)


async def test_browser_state_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/sites")
    assert response.status_code == 401


async def test_gateway_auth_rejects_missing_invalid_and_overscoped_credentials(
    client: AsyncClient,
    gateway_headers: dict[str, str],
) -> None:
    heartbeat = {"site_id": "homebox", "gateway_id": "gateway-main"}

    assert (
        await client.post("/api/gateway/v1/heartbeat", json=heartbeat)
    ).status_code == 401
    assert (
        await client.post(
            "/api/gateway/v1/heartbeat",
            json=heartbeat,
            headers={"authorization": "Bearer wrong"},
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/gateway/v1/heartbeat",
            json={"site_id": "other-site", "gateway_id": "gateway-main"},
            headers=gateway_headers,
        )
    ).status_code == 403


async def test_catalog_upsert_is_idempotent(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    catalog = {
        "site": {"site_id": "homebox", "name": "Home Box"},
        "tents": [{"tent_id": "main", "name": "Main"}],
        "zones": [{"tent_id": "main", "zone_id": "canopy", "name": "Canopy"}],
        "devices": [
            {
                "tent_id": "main",
                "zone_id": "canopy",
                "device_id": "env-main",
                "name": "Env Main",
            }
        ],
        "capabilities": [
            {
                "tent_id": "main",
                "device_id": "env-main",
                "capability_id": "env-main-temp",
                "metric_name": "temperature_f",
                "unit": "f",
            }
        ],
    }

    first = await client.put(
        "/api/gateway/v1/catalog", json=catalog, headers=gateway_headers
    )
    second = await client.put(
        "/api/gateway/v1/catalog", json=catalog, headers=gateway_headers
    )

    assert first.status_code == 200
    assert second.status_code == 200
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(CloudTent))
    assert count == 1


async def test_latest_metric_upsert_is_idempotent(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    payload = {
        "site_id": "homebox",
        "metrics": [
            {
                "site_id": "homebox",
                "tent_id": "main",
                "capability_id": "env-main-temp",
                "metric": "temperature_f",
                "value": 75.0,
                "unit": "f",
                "source_updated_at": "2026-05-05T03:44:00Z",
            }
        ],
    }
    assert (
        await client.put(
            "/api/gateway/v1/metrics/latest",
            json=payload,
            headers=gateway_headers,
        )
    ).status_code == 200
    payload["metrics"][0]["value"] = 76.0
    assert (
        await client.put(
            "/api/gateway/v1/metrics/latest",
            json=payload,
            headers=gateway_headers,
        )
    ).status_code == 200

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        rows = (await session.execute(select(CloudLatestMetric))).scalars().all()
    assert len(rows) == 1
    assert rows[0].value == 76.0


async def test_duplicate_command_idempotency_returns_same_intent_without_hardware(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    body = {
        "idempotency_key": "same-click",
        "tent_id": "main",
        "device_id": "obsbot-main",
        "capability_id": "ptz_move",
        "command_type": "ptz_preset",
        "payload": {"preset": "overview"},
    }

    first = await authed_client.post("/api/commands", json=body)
    second = await authed_client.post("/api/commands", json=body)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["command_id"] == second.json()["command_id"]
    assert first.json()["status"] == "queued"
    assert datetime.fromisoformat(first.json()["expires_at"]) == FIXED_NOW + timedelta(
        seconds=60
    )
    listed = await authed_client.get("/api/commands")
    assert listed.status_code == 200
    assert [command["command_id"] for command in listed.json()] == [
        first.json()["command_id"]
    ]
    fetched = await authed_client.get(f"/api/commands/{first.json()['command_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["command_id"] == first.json()["command_id"]
    assert _forbidden_hardware_imports() == set()

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(CloudCommand))
    assert count == 1


def _forbidden_hardware_imports() -> set[str]:
    forbidden = {"dirt_hwd", "dirt_shared.services.ptz"}
    package_root = Path(dirt_control.__file__).parent
    found: set[str] = set()
    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _matches_forbidden_import(alias.name, forbidden):
                        found.add(alias.name)
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and _matches_forbidden_import(node.module, forbidden)
            ):
                found.add(node.module)
    return found


def _matches_forbidden_import(module: str, forbidden: set[str]) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden
    )


async def test_command_creation_rejects_non_ptz_remote_control(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    valid_body = {
        "idempotency_key": "unsafe-click",
        "tent_id": "main",
        "device_id": "obsbot-main",
        "capability_id": "ptz_move",
        "command_type": "ptz_preset",
        "payload": {"preset": "overview"},
    }

    unsafe_cases = [
        {"command_type": "fan_set_duty"},
        {"command_type": "lights_set"},
        {"command_type": "humidifier_set"},
        {"device_id": "fan-main"},
        {"capability_id": "fan_duty"},
    ]
    for patch in unsafe_cases:
        body = valid_body | patch
        response = await authed_client.post("/api/commands", json=body)
        assert response.status_code == 422

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(CloudCommand))
    assert count == 0


async def test_asset_flow_is_direct_upload_handshake_and_signed_url_requires_auth(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    sign = await client.post(
        "/api/gateway/v1/assets/sign-upload",
        headers=gateway_headers,
        json={
            "site_id": "homebox",
            "tent_id": "main",
            "asset_id": "asset-1",
            "object_key": "homebox/main/asset-1.jpg",
            "content_type": "image/jpeg",
            "byte_size": 25_000_000,
            "sha256": "a" * 64,
        },
    )
    assert sign.status_code == 200
    assert sign.json()["method"] == "PUT"
    assert sign.json()["upload_url"].startswith("https://assets.test/")

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        before_count = await session.scalar(
            select(func.count()).select_from(CloudAsset)
        )
    assert before_count == 0

    complete = await client.post(
        "/api/gateway/v1/assets/complete",
        headers=gateway_headers,
        json={
            "site_id": "homebox",
            "tent_id": "main",
            "asset_id": "asset-1",
            "object_key": "homebox/main/asset-1.jpg",
            "content_type": "image/jpeg",
            "byte_size": 25_000_000,
            "sha256": "a" * 64,
            "captured_at": "2026-05-05T03:40:00Z",
        },
    )
    assert complete.status_code == 200

    unauth = await client.get("/api/assets/asset-1/signed-url")
    assert unauth.status_code == 401

    login = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password"},
    )
    assert login.status_code == 200
    client.cookies = login.cookies

    authed = await client.get("/api/assets/asset-1/signed-url")
    assert authed.status_code == 200
    assert authed.json()["signed_url"].startswith("https://assets.test/")


async def test_sync_status_exposes_gateway_age_and_command_backlog(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.get("/api/sync/status")
    assert response.status_code == 200
    assert response.json() == {
        "site_id": "homebox",
        "gateway_last_seen_at": None,
        "last_catalog_sync_at": None,
        "command_backlog_depth": 0,
        "status": "offline",
    }

    command = await authed_client.post(
        "/api/commands",
        json={
            "idempotency_key": "backlog-click",
            "tent_id": "main",
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
            "command_type": "ptz_preset",
            "payload": {"preset": "overview"},
        },
    )
    assert command.status_code == 201

    response = await authed_client.get("/api/sync/status")
    assert response.status_code == 200
    assert response.json()["command_backlog_depth"] == 1
    assert response.json()["status"] == "offline"
