from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

import dirt_control
from dirt_control.bootstrap import GatewayCredentialSeed, ensure_gateway_credential
from dirt_control.db import create_sessionmaker
from dirt_control.models import (
    CloudAsset,
    CloudAuditEvent,
    CloudCommand,
    CloudLatestMetric,
    CloudSite,
    CloudTent,
    GatewayCredential,
)
from dirt_control.settings import CloudSettings
from dirt_control.storage import S3ObjectStore

FIXED_NOW = datetime(2026, 5, 5, 3, 45, tzinfo=UTC)


def test_cloud_settings_accept_railway_database_url_alias() -> None:
    settings = CloudSettings(
        DATABASE_URL="postgresql+asyncpg://user:pass@db.example/dirt",
        DIRT_CLOUD_ADMIN_USERNAME="admin",
        DIRT_CLOUD_ADMIN_PASSWORD_HASH="hash",
        DIRT_CLOUD_SESSION_SECRET="test-session-secret-at-least-16",
    )

    assert settings.database_url == "postgresql+asyncpg://user:pass@db.example/dirt"


def test_cloud_settings_accept_comma_separated_allowed_origins(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db.example/dirt")
    monkeypatch.setenv("DIRT_CLOUD_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DIRT_CLOUD_ADMIN_PASSWORD_HASH", "hash")
    monkeypatch.setenv("DIRT_CLOUD_SESSION_SECRET", "test-session-secret-at-least-16")
    monkeypatch.setenv(
        "DIRT_CLOUD_ALLOWED_ORIGINS",
        "https://sirius-forge.com, https://preview.sirius-forge.com",
    )

    settings = CloudSettings()

    assert settings.allowed_origins == [
        "https://sirius-forge.com",
        "https://preview.sirius-forge.com",
    ]


def test_s3_object_store_generates_private_presigned_urls(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeS3Client:
        def generate_presigned_url(self, operation, *, Params, ExpiresIn, HttpMethod):
            calls.append(
                {
                    "operation": operation,
                    "params": Params,
                    "expires_in": ExpiresIn,
                    "method": HttpMethod,
                }
            )
            return f"https://bucket.test/{operation}"

    monkeypatch.setattr(
        "dirt_control.storage.boto3.client",
        lambda *args, **kwargs: FakeS3Client(),
    )
    settings = CloudSettings(
        DATABASE_URL="postgresql+asyncpg://user:pass@db.example/dirt",
        DIRT_CLOUD_ADMIN_USERNAME="admin",
        DIRT_CLOUD_ADMIN_PASSWORD_HASH="hash",
        DIRT_CLOUD_SESSION_SECRET="test-session-secret-at-least-16",
        DIRT_CLOUD_BUCKET_NAME="dirt-assets",
        DIRT_CLOUD_S3_ENDPOINT="https://s3.example",
        DIRT_CLOUD_S3_REGION="iad",
        DIRT_CLOUD_S3_ACCESS_KEY_ID="access-key",
        DIRT_CLOUD_S3_SECRET_ACCESS_KEY="secret-key",
    )

    store = S3ObjectStore(settings=settings)

    assert (
        store.presign_put(
            object_key="homebox/main/snapshot.jpg",
            content_type="image/jpeg",
            expires_in_s=900,
        )
        == "https://bucket.test/put_object"
    )
    assert (
        store.presign_get(object_key="homebox/main/snapshot.jpg", expires_in_s=300)
        == "https://bucket.test/get_object"
    )
    assert calls == [
        {
            "operation": "put_object",
            "params": {
                "Bucket": "dirt-assets",
                "Key": "homebox/main/snapshot.jpg",
                "ContentType": "image/jpeg",
            },
            "expires_in": 900,
            "method": "PUT",
        },
        {
            "operation": "get_object",
            "params": {
                "Bucket": "dirt-assets",
                "Key": "homebox/main/snapshot.jpg",
            },
            "expires_in": 300,
            "method": "GET",
        },
    ]


async def test_gateway_credential_bootstrap_upserts(
    cloud_engine: AsyncEngine,
) -> None:
    await ensure_gateway_credential(
        database_url=str(cloud_engine.url),
        seed=GatewayCredentialSeed(
            credential_id="homebox-gateway",
            gateway_id="homebox-gateway",
            token_sha256="a" * 64,
            allowed_site_id="homebox",
        ),
        now=FIXED_NOW,
        engine=cloud_engine,
    )
    await ensure_gateway_credential(
        database_url=str(cloud_engine.url),
        seed=GatewayCredentialSeed(
            credential_id="homebox-gateway",
            gateway_id="homebox-gateway",
            token_sha256="b" * 64,
            allowed_site_id="homebox",
        ),
        now=FIXED_NOW,
        engine=cloud_engine,
    )

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        credential = await session.get(GatewayCredential, "homebox-gateway")

    assert credential is not None
    assert credential.token_sha256 == "b" * 64
    assert credential.gateway_id == "homebox-gateway"
    assert credential.allowed_site_id == "homebox"
    assert credential.is_active is True


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


async def test_gateway_heartbeat_updates_credential_last_used(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    response = await client.post(
        "/api/gateway/v1/heartbeat",
        json={"site_id": "homebox", "gateway_id": "gateway-main"},
        headers=gateway_headers,
    )
    assert response.status_code == 200

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        credential = await session.get(GatewayCredential, "gateway-main")

    assert credential is not None
    assert credential.last_used_at == FIXED_NOW


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
    listed_queued = await authed_client.get("/api/commands?status=queued")
    assert listed_queued.status_code == 200
    assert [command["command_id"] for command in listed_queued.json()] == [
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
        {"site_id": "other-site"},
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
        "gateway_backlog_depth": 0,
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


async def test_health_exposes_gateway_backlog_and_failure_counts(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    heartbeat = await client.post(
        "/api/gateway/v1/heartbeat",
        headers=gateway_headers,
        json={"site_id": "homebox", "gateway_id": "gateway-main", "backlog_depth": 3},
    )
    assert heartbeat.status_code == 200
    failure = await client.post(
        "/api/gateway/v1/assets/upload-failure",
        headers=gateway_headers,
        json={
            "site_id": "homebox",
            "tent_id": "main",
            "asset_id": "asset-1",
            "object_key": "homebox/main/asset-1.jpg",
            "stage": "upload_or_complete",
            "error": "storage rejected upload",
        },
    )
    assert failure.status_code == 200

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        command = CloudCommand(
            command_id="failed-command",
            idempotency_key="failed-key",
            site_id="homebox",
            tent_id="main",
            device_id="obsbot-main",
            capability_id="ptz_move",
            command_type="ptz_zoom",
            payload={"delta": 0.1},
            requested_by="admin",
            status="failed",
            queued_at=FIXED_NOW,
            expires_at=FIXED_NOW + timedelta(seconds=60),
            finished_at=FIXED_NOW,
            error="ptz failed",
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
        session.add(command)
        await session.commit()

    health = await client.get("/api/health")

    assert health.status_code == 200
    assert health.json()["gateway_backlog_depth"] == 3
    assert health.json()["gateway_heartbeat_age_s"] == 0
    assert health.json()["asset_failures_24h"] == 1
    assert health.json()["command_failures_24h"] == 1
    assert health.json()["asset_retention_days"] == 30


async def test_audit_rows_cover_auth_command_claim_result_and_rotation(
    authed_client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    created = await authed_client.post(
        "/api/commands",
        json={
            "idempotency_key": "audit-click",
            "tent_id": "main",
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
            "command_type": "ptz_preset",
            "payload": {"preset": "overview"},
        },
    )
    assert created.status_code == 201
    command_id = created.json()["command_id"]
    claim = await authed_client.post(
        "/api/gateway/v1/commands/claim",
        headers=gateway_headers,
        json={"site_id": "homebox", "limit": 1},
    )
    assert claim.status_code == 200
    result = await authed_client.post(
        f"/api/gateway/v1/commands/{command_id}/result",
        headers=gateway_headers,
        json={"site_id": "homebox", "status": "failed", "error": "ptz rejected"},
    )
    assert result.status_code == 200
    rotated = await authed_client.post(
        "/api/admin/gateway-credentials/gateway-main/rotate",
        json={"token_sha256": "b" * 64},
    )
    assert rotated.status_code == 200

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        events = (
            (
                await session.execute(
                    select(CloudAuditEvent.event_type).order_by(
                        CloudAuditEvent.created_at
                    )
                )
            )
            .scalars()
            .all()
        )
        credential = await session.get(GatewayCredential, "gateway-main")
    assert "auth_login_succeeded" in events
    assert "command_created" in events
    assert "command_claimed" in events
    assert "command_result_reported" in events
    assert "gateway_credential_rotated" in events
    assert credential is not None
    assert credential.token_sha256 == "b" * 64


async def test_command_creation_can_be_disabled_by_config(
    cloud_engine: AsyncEngine,
    settings,
) -> None:
    from dirt_control.app import create_app

    disabled = settings.model_copy(update={"command_creation_enabled": False})
    app = create_app(settings=disabled, engine=cloud_engine, clock=lambda: FIXED_NOW)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        login = await client.post(
            "/api/auth/login", json={"username": "admin", "password": "test-password"}
        )
        assert login.status_code == 200
        client.cookies = login.cookies
        response = await client.post(
            "/api/commands",
            json={
                "idempotency_key": "disabled-click",
                "tent_id": "main",
                "device_id": "obsbot-main",
                "capability_id": "ptz_move",
                "command_type": "ptz_preset",
                "payload": {"preset": "overview"},
            },
        )
    await transport.aclose()
    assert response.status_code == 503


async def test_asset_retention_prunes_assets_older_than_30_days(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(
            CloudSite(
                site_id="homebox",
                name="Homebox",
                timezone="UTC",
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        session.add(
            CloudAsset(
                asset_id="old-asset",
                site_id="homebox",
                tent_id="main",
                object_key="homebox/main/old.jpg",
                content_type="image/jpeg",
                byte_size=10,
                captured_at=FIXED_NOW - timedelta(days=31),
                uploaded_at=FIXED_NOW - timedelta(days=31),
            )
        )
        session.add(
            CloudAsset(
                asset_id="fresh-asset",
                site_id="homebox",
                tent_id="main",
                object_key="homebox/main/fresh.jpg",
                content_type="image/jpeg",
                byte_size=10,
                captured_at=FIXED_NOW - timedelta(days=29),
                uploaded_at=FIXED_NOW - timedelta(days=29),
            )
        )
        await session.commit()

    response = await authed_client.post("/api/admin/assets/prune-expired")

    assert response.status_code == 200
    assert response.json()["matched"] == 1
    async with sessionmaker() as session:
        remaining = (
            (
                await session.execute(
                    select(CloudAsset.asset_id).order_by(CloudAsset.asset_id)
                )
            )
            .scalars()
            .all()
        )
        audit_count = await session.scalar(
            select(func.count())
            .select_from(CloudAuditEvent)
            .where(CloudAuditEvent.event_type == "asset_retention_pruned")
        )
    assert remaining == ["fresh-asset"]
    assert audit_count == 1


async def test_gateway_claim_expires_stale_commands_and_reclaims_own_claim(
    authed_client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    stale = await authed_client.post(
        "/api/commands",
        json={
            "idempotency_key": "stale-click",
            "tent_id": "main",
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
            "command_type": "ptz_preset",
            "payload": {"preset_id": "overview"},
        },
    )
    fresh = await authed_client.post(
        "/api/commands",
        json={
            "idempotency_key": "fresh-click",
            "tent_id": "main",
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
            "command_type": "ptz_zoom",
            "payload": {"zoom": 1.2},
        },
    )
    assert stale.status_code == 201
    assert fresh.status_code == 201
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        stale_row = await session.get(CloudCommand, stale.json()["command_id"])
        assert stale_row is not None
        stale_row.expires_at = FIXED_NOW - timedelta(seconds=1)
        await session.commit()

    second_claim = await authed_client.post(
        "/api/gateway/v1/commands/claim",
        headers=gateway_headers,
        json={"site_id": "homebox", "limit": 5},
    )
    assert second_claim.status_code == 200
    assert [cmd["command_id"] for cmd in second_claim.json()["commands"]] == [
        fresh.json()["command_id"]
    ]
    expired = await authed_client.get(f"/api/commands/{stale.json()['command_id']}")
    assert expired.json()["status"] == "expired"

    reclaim = await authed_client.post(
        "/api/gateway/v1/commands/claim",
        headers=gateway_headers,
        json={"site_id": "homebox", "limit": 5},
    )
    assert reclaim.status_code == 200
    assert [cmd["command_id"] for cmd in reclaim.json()["commands"]] == [
        fresh.json()["command_id"]
    ]


async def test_gateway_result_does_not_regress_terminal_command(
    authed_client: AsyncClient,
    gateway_headers: dict[str, str],
) -> None:
    created = await authed_client.post(
        "/api/commands",
        json={
            "idempotency_key": "terminal-click",
            "tent_id": "main",
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
            "command_type": "ptz_zoom",
            "payload": {"zoom": 1.4},
        },
    )
    command_id = created.json()["command_id"]

    succeeded = await authed_client.post(
        f"/api/gateway/v1/commands/{command_id}/result",
        headers=gateway_headers,
        json={
            "site_id": "homebox",
            "status": "succeeded",
            "result": {"ok": True},
        },
    )
    late_running = await authed_client.post(
        f"/api/gateway/v1/commands/{command_id}/result",
        headers=gateway_headers,
        json={"site_id": "homebox", "status": "running"},
    )

    assert succeeded.status_code == 200
    assert late_running.status_code == 200
    assert late_running.json()["status"] == "succeeded"
