from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine

import dirt_control
from dirt_control.bootstrap import GatewayCredentialSeed, ensure_gateway_credential
from dirt_control.db import create_sessionmaker
from dirt_control.models import (
    CloudAsset,
    CloudAuditEvent,
    CloudCapability,
    CloudCommand,
    CloudDevice,
    CloudLatestMetric,
    CloudMetricPresentation,
    CloudMetricRollup,
    CloudPlant,
    CloudSchedule,
    CloudSite,
    CloudTent,
    CloudWikiPage,
    GatewayCredential,
)
from dirt_control.settings import CloudSettings
from dirt_control.storage import S3ObjectStore, create_asset_store

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


def test_asset_store_defaults_to_s3_and_requires_credentials() -> None:
    settings = CloudSettings(
        DATABASE_URL="postgresql+asyncpg://user:pass@db.example/dirt",
        DIRT_CLOUD_ADMIN_USERNAME="admin",
        DIRT_CLOUD_ADMIN_PASSWORD_HASH="hash",
        DIRT_CLOUD_SESSION_SECRET="test-session-secret-at-least-16",
    )

    assert settings.asset_store == "s3"
    with pytest.raises(
        ValueError, match="DIRT_CLOUD_ASSET_STORE=s3 requires S3 settings"
    ):
        create_asset_store(settings=settings, clock=lambda: FIXED_NOW)


def _rollup(
    suffix: str,
    *,
    bucket: str,
    start: datetime,
    avg: float,
    min_value: float | None = None,
    max_value: float | None = None,
    device_id: str = "env-main",
    metric: str = "temperature_f",
    capability_id: str = "env-main-temp",
    unit: str = "f",
) -> CloudMetricRollup:
    return CloudMetricRollup(
        rollup_key=(
            f"homebox:main:{device_id}:{capability_id}:{metric}:{bucket}:{suffix}"
        ),
        site_id="homebox",
        tent_id="main",
        device_id=device_id,
        capability_id=capability_id,
        metric=metric,
        bucket=bucket,
        bucket_start_at=start,
        bucket_end_at=start + timedelta(minutes=5),
        min_value=avg - 0.5 if min_value is None else min_value,
        avg_value=avg,
        max_value=avg + 0.5 if max_value is None else max_value,
        sample_count=1,
        unit=unit,
        received_at=FIXED_NOW,
    )


def _plant(
    plant_id: str,
    *,
    display_order: int,
    grow_run_id: str = "main-2026-03-15",
    moisture_device_id: str | None = "plant-a-node",
    moisture_capability_id: str | None = "soil_moisture_raw",
    is_active: bool = True,
    synced_at: datetime = FIXED_NOW,
) -> CloudPlant:
    return CloudPlant(
        plant_key=f"homebox:main:{grow_run_id}:{plant_id}",
        site_id="homebox",
        tent_id="main",
        grow_run_id=grow_run_id,
        plant_id=plant_id,
        name=f"Plant {plant_id.upper()}",
        display_order=display_order,
        sticker_color="yellow" if plant_id == "a" else None,
        status="primary" if is_active else "retired",
        purple=plant_id == "a",
        moisture_target_low=55.0,
        moisture_target_high=70.0,
        moisture_device_id=moisture_device_id,
        moisture_capability_id=moisture_capability_id,
        wiki_path=f"wiki/grows/{grow_run_id}/plants/plant-{plant_id}.md",
        is_active=is_active,
        synced_at=synced_at,
        created_at=FIXED_NOW,
        updated_at=synced_at,
    )


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
                "last_seen_at": None,
            },
            {
                "tent_id": "main",
                "zone_id": "canopy",
                "device_id": "env-backup",
                "name": "Env Backup",
                "last_seen_at": None,
            },
        ],
        "capabilities": [
            {
                "tent_id": "main",
                "device_id": "env-main",
                "capability_id": "env-main-temp",
                "metric_name": "temperature_f",
                "unit": "f",
            },
            {
                "tent_id": "main",
                "device_id": "env-backup",
                "capability_id": "env-main-temp",
                "metric_name": "temperature_f",
                "unit": "f",
            },
        ],
        "schedules": [
            {
                "site_id": "homebox",
                "tent_id": "main",
                "zone_id": "canopy",
                "device_id": "env-main",
                "capability_id": "env-main-temp",
                "schedule_id": "main-lights-photoperiod",
                "kind": "lights",
                "starts_local": "09:00:00",
                "ends_local": "21:00:00",
                "timezone": "America/Denver",
                "is_enabled": True,
            }
        ],
        "plants": [
            {
                "tent_id": "main",
                "grow_run_id": "main-2026-03-15",
                "plant_id": "a",
                "name": "Plant A",
                "display_order": 1,
                "sticker_color": "yellow",
                "status": "primary",
                "purple": True,
                "moisture_target_low": 55.0,
                "moisture_target_high": 70.0,
                "moisture_device_id": "env-main",
                "moisture_capability_id": "env-main-temp",
                "wiki_path": "wiki/grows/main-2026-03-15/plants/plant-a.md",
                "is_active": True,
            },
            {
                "tent_id": "main",
                "grow_run_id": "main-2026-03-15",
                "plant_id": "b",
                "name": "Plant B",
                "display_order": 2,
                "sticker_color": None,
                "status": "retired",
                "purple": False,
                "moisture_target_low": 50.0,
                "moisture_target_high": 65.0,
                "moisture_device_id": None,
                "moisture_capability_id": None,
                "wiki_path": None,
                "is_active": False,
            },
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
    assert first.json()["plants"] == 2
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(CloudTent))
        capability_count = await session.scalar(
            select(func.count()).select_from(CloudCapability)
        )
        schedule_count = await session.scalar(
            select(func.count()).select_from(CloudSchedule)
        )
        plant_count = await session.scalar(select(func.count()).select_from(CloudPlant))
        plant_a = await session.get(
            CloudPlant,
            "homebox:main:main-2026-03-15:a",
        )
    assert count == 1
    assert capability_count == 2
    assert schedule_count == 1
    assert plant_count == 2
    assert plant_a is not None
    assert plant_a.moisture_device_id == "env-main"
    assert plant_a.wiki_path == "wiki/grows/main-2026-03-15/plants/plant-a.md"


async def test_gateway_wiki_projection_upserts_deletes_and_checks_scope(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    first_payload = {
        "site_id": "homebox",
        "generated_at": FIXED_NOW.isoformat(),
        "pages": [
            {
                "path": "wiki/grows/main-2026-03-15/plants/plant-a.md",
                "title": "Plant A",
                "frontmatter": {"title": "Plant A"},
                "body_markdown": "# Plant A\n",
                "sha256": "a" * 64,
                "source_updated_at": FIXED_NOW.isoformat(),
            },
            {
                "path": "wiki/grows/main-2026-03-15/plants/plant-b.md",
                "title": "Plant B",
                "frontmatter": {"title": "Plant B"},
                "body_markdown": "# Plant B\n",
                "sha256": "b" * 64,
                "source_updated_at": FIXED_NOW.isoformat(),
            },
        ],
        "excluded_paths": ["wiki/AGENTS.md"],
        "content_hash": "c" * 64,
    }
    second_payload = {
        **first_payload,
        "pages": [
            {
                **first_payload["pages"][0],
                "title": "Plant A Updated",
                "body_markdown": "# Plant A\n\nUpdated.\n",
                "sha256": "d" * 64,
            }
        ],
        "content_hash": "e" * 64,
    }

    first = await client.put(
        "/api/gateway/v1/wiki", json=first_payload, headers=gateway_headers
    )
    second = await client.put(
        "/api/gateway/v1/wiki", json=second_payload, headers=gateway_headers
    )
    forbidden = await client.put(
        "/api/gateway/v1/wiki",
        json={**first_payload, "site_id": "other-site"},
        headers=gateway_headers,
    )

    assert first.status_code == 200
    assert first.json()["upserted"] == 2
    assert first.json()["deleted"] == 0
    assert second.status_code == 200
    assert second.json()["upserted"] == 1
    assert second.json()["deleted"] == 1
    assert forbidden.status_code == 403
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        rows = (await session.execute(select(CloudWikiPage))).scalars().all()
    assert len(rows) == 1
    assert rows[0].path == "wiki/grows/main-2026-03-15/plants/plant-a.md"
    assert rows[0].title == "Plant A Updated"
    assert rows[0].body_markdown == "# Plant A\n\nUpdated.\n"


async def test_gateway_camera_capture_policy_matches_camera_to_lights_by_tent(
    client: AsyncClient,
    gateway_headers: dict[str, str],
) -> None:
    catalog = {
        "site": {"site_id": "homebox", "name": "Home Box"},
        "tents": [{"tent_id": "breeding", "name": "Breeding"}],
        "zones": [
            {"tent_id": "breeding", "zone_id": "canopy", "name": "Canopy"},
            {"tent_id": "breeding", "zone_id": "lights", "name": "Lights"},
        ],
        "devices": [
            {
                "tent_id": "breeding",
                "zone_id": "canopy",
                "device_id": "obsbot-breeding",
                "name": "Breeding Camera",
                "kind": "camera",
                "last_seen_at": FIXED_NOW.isoformat(),
            }
        ],
        "schedules": [
            {
                "site_id": "homebox",
                "tent_id": "breeding",
                "zone_id": "lights",
                "schedule_id": "breeding-lights-photoperiod",
                "kind": "lights",
                "starts_local": "06:00:00",
                "ends_local": "18:00:00",
                "timezone": "America/Denver",
                "is_enabled": True,
            }
        ],
    }
    synced = await client.put(
        "/api/gateway/v1/catalog", json=catalog, headers=gateway_headers
    )

    response = await client.get(
        "/api/gateway/v1/cameras/obsbot-breeding/capture-policy",
        headers=gateway_headers,
    )

    assert synced.status_code == 200
    assert response.status_code == 200
    assert response.json() == {
        "site_id": "homebox",
        "tent_id": "breeding",
        "camera_device_id": "obsbot-breeding",
        "enabled": True,
        "require_lights_on": True,
        "lights_on_local": "06:00:00",
        "lights_off_local": "18:00:00",
        "timezone": "America/Denver",
        "source_schedule_id": "breeding-lights-photoperiod",
        "reason": None,
    }


async def test_gateway_camera_capture_policy_fails_open_when_missing_rows(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    missing_camera = await client.get(
        "/api/gateway/v1/cameras/obsbot-missing/capture-policy",
        headers=gateway_headers,
    )
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(
            CloudSite(
                site_id="homebox",
                name="Home Box",
                timezone="America/Denver",
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        session.add(
            CloudDevice(
                device_key="homebox:breeding:obsbot-breeding",
                site_id="homebox",
                tent_id="breeding",
                zone_id="canopy",
                device_id="obsbot-breeding",
                name="Breeding Camera",
                kind="camera",
                controller="obsbot",
                is_active=True,
                synced_at=FIXED_NOW,
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        session.add(
            CloudDevice(
                device_key="homebox:breeding:obsbot-disabled",
                site_id="homebox",
                tent_id="breeding",
                zone_id="canopy",
                device_id="obsbot-disabled",
                name="Disabled Breeding Camera",
                kind="camera",
                controller="obsbot",
                is_active=False,
                synced_at=FIXED_NOW,
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        await session.commit()

    missing_schedule = await client.get(
        "/api/gateway/v1/cameras/obsbot-breeding/capture-policy",
        headers=gateway_headers,
    )
    disabled = await client.get(
        "/api/gateway/v1/cameras/obsbot-disabled/capture-policy",
        headers=gateway_headers,
    )

    assert missing_camera.status_code == 200
    assert missing_camera.json()["enabled"] is True
    assert missing_camera.json()["require_lights_on"] is False
    assert missing_camera.json()["reason"] == "camera_not_found"
    assert missing_schedule.status_code == 200
    assert missing_schedule.json()["enabled"] is True
    assert missing_schedule.json()["require_lights_on"] is False
    assert missing_schedule.json()["reason"] == "lights_schedule_not_found"
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["reason"] == "camera_disabled"


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
                "device_id": "env-main",
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
    assert rows[0].device_id == "env-main"


async def test_latest_metric_upsert_keeps_device_scoped_streams_separate(
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
                "device_id": "plant-a-node",
                "capability_id": "soil_moisture_raw",
                "metric": "soil_moisture_raw",
                "value": 1800.0,
                "unit": "raw",
                "source_updated_at": "2026-05-05T03:44:00Z",
            },
            {
                "site_id": "homebox",
                "tent_id": "main",
                "device_id": "plant-b-node",
                "capability_id": "soil_moisture_raw",
                "metric": "soil_moisture_raw",
                "value": 2200.0,
                "unit": "raw",
                "source_updated_at": "2026-05-05T03:44:00Z",
            },
        ],
    }

    response = await client.put(
        "/api/gateway/v1/metrics/latest",
        json=payload,
        headers=gateway_headers,
    )

    assert response.status_code == 200
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        result = await session.execute(
            select(CloudLatestMetric).order_by(CloudLatestMetric.device_id)
        )
        rows = result.scalars().all()
    assert [row.device_id for row in rows] == ["plant-a-node", "plant-b-node"]
    assert [row.value for row in rows] == [1800.0, 2200.0]


async def test_rollup_upsert_keeps_device_scoped_streams_separate(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    payload = {
        "site_id": "homebox",
        "rollups": [
            {
                "site_id": "homebox",
                "tent_id": "main",
                "device_id": "plant-a-node",
                "capability_id": "soil_moisture_raw",
                "metric": "soil_moisture_raw",
                "bucket": "1h",
                "bucket_start_at": "2026-05-05T03:00:00Z",
                "bucket_end_at": "2026-05-05T04:00:00Z",
                "avg_value": 1800.0,
                "sample_count": 12,
                "unit": "raw",
            },
            {
                "site_id": "homebox",
                "tent_id": "main",
                "device_id": "plant-b-node",
                "capability_id": "soil_moisture_raw",
                "metric": "soil_moisture_raw",
                "bucket": "1h",
                "bucket_start_at": "2026-05-05T03:00:00Z",
                "bucket_end_at": "2026-05-05T04:00:00Z",
                "avg_value": 2200.0,
                "sample_count": 12,
                "unit": "raw",
            },
        ],
    }

    response = await client.post(
        "/api/gateway/v1/metrics/rollups",
        json=payload,
        headers=gateway_headers,
    )

    assert response.status_code == 200
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        result = await session.execute(
            select(CloudMetricRollup).order_by(CloudMetricRollup.device_id)
        )
        rows = result.scalars().all()
    assert [row.device_id for row in rows] == ["plant-a-node", "plant-b-node"]
    assert [row.avg_value for row in rows] == [1800.0, 2200.0]


async def test_current_metrics_expose_canonical_metric_names(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                CloudLatestMetric(
                    metric_key=("homebox:main:fan-controller:fan_pct:fan_pct"),
                    site_id="homebox",
                    tent_id="main",
                    zone_id="canopy",
                    device_id="fan-controller",
                    capability_id="fan_pct",
                    metric="fan_pct",
                    value=42.0,
                    unit="%",
                    source_updated_at=FIXED_NOW - timedelta(seconds=30),
                    received_at=FIXED_NOW,
                    stale_after_s=120,
                ),
                CloudLatestMetric(
                    metric_key=(
                        "homebox:main:govee-h7142-main:"
                        "humidifier_intensity_pct:humidifier_intensity_pct"
                    ),
                    site_id="homebox",
                    tent_id="main",
                    zone_id="canopy",
                    device_id="govee-h7142-main",
                    capability_id="humidifier_intensity_pct",
                    metric="humidifier_intensity_pct",
                    value=50.0,
                    unit="%",
                    source_updated_at=FIXED_NOW - timedelta(seconds=30),
                    received_at=FIXED_NOW,
                    stale_after_s=120,
                ),
                CloudLatestMetric(
                    metric_key=(
                        "homebox:main:ac-infinity-thermoforge-main:"
                        "heat_level:heater_intensity_pct"
                    ),
                    site_id="homebox",
                    tent_id="main",
                    zone_id="heat",
                    device_id="ac-infinity-thermoforge-main",
                    capability_id="heat_level",
                    metric="heater_intensity_pct",
                    value=70.0,
                    unit="%",
                    source_updated_at=FIXED_NOW - timedelta(seconds=30),
                    received_at=FIXED_NOW,
                    stale_after_s=120,
                ),
                CloudLatestMetric(
                    metric_key=(
                        "homebox:main:kasa-dehumidifier-main:power:dehumidifier_on"
                    ),
                    site_id="homebox",
                    tent_id="main",
                    zone_id="canopy",
                    device_id="kasa-dehumidifier-main",
                    capability_id="power",
                    metric="dehumidifier_on",
                    value=1.0,
                    unit="bool",
                    source_updated_at=FIXED_NOW - timedelta(seconds=30),
                    received_at=FIXED_NOW,
                    stale_after_s=120,
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get("/api/tents/main/metrics/current")

    assert response.status_code == 200
    by_metric = {metric["metric"]: metric for metric in response.json()}
    assert by_metric["fan_pct"]["value"] == 42.0
    assert by_metric["fan_pct"]["unit"] == "%"
    assert by_metric["humidifier_intensity_pct"]["value"] == 50.0
    assert by_metric["humidifier_intensity_pct"]["unit"] == "%"
    assert by_metric["heater_intensity_pct"]["value"] == 70.0
    assert by_metric["heater_intensity_pct"]["unit"] == "%"
    assert by_metric["dehumidifier_on"]["value"] == 1.0
    assert by_metric["dehumidifier_on"]["unit"] == "bool"


async def test_metric_presentation_exposes_ordered_backend_registry(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        await session.execute(delete(CloudMetricPresentation))
        session.add_all(
            [
                CloudMetricPresentation(
                    metric="fan_pct",
                    display_name="Fan Speed",
                    unit="%",
                    accent="neutral",
                    value_precision=0,
                    y_min=0.0,
                    y_max=100.0,
                    current_enabled=True,
                    history_enabled=True,
                    dashboard_group="temperature_loop",
                    dashboard_group_label="Temperature Loop",
                    dashboard_group_order=10,
                    display_order=30,
                ),
                CloudMetricPresentation(
                    metric="heater_intensity_pct",
                    display_name="Heat Output",
                    unit="%",
                    accent="temp",
                    value_precision=0,
                    y_min=0.0,
                    y_max=100.0,
                    current_enabled=True,
                    history_enabled=True,
                    dashboard_group="temperature_loop",
                    dashboard_group_label="Temperature Loop",
                    dashboard_group_order=10,
                    display_order=10,
                ),
                CloudMetricPresentation(
                    metric="humidity_pct",
                    display_name="Canopy Humidity",
                    unit="%",
                    accent="humidity",
                    value_precision=1,
                    y_min=20.0,
                    y_max=90.0,
                    current_enabled=True,
                    history_enabled=True,
                    dashboard_group="humidity_loop",
                    dashboard_group_label="Humidity Loop",
                    dashboard_group_order=20,
                    display_order=20,
                ),
                CloudMetricPresentation(
                    metric="dehumidifier_on",
                    display_name="Dehumidifier Runtime",
                    unit="%",
                    accent="humidity",
                    value_precision=0,
                    y_min=0.0,
                    y_max=100.0,
                    current_enabled=False,
                    history_enabled=True,
                    dashboard_group="humidity_loop",
                    dashboard_group_label="Humidity Loop",
                    dashboard_group_order=20,
                    display_order=25,
                ),
                CloudMetricPresentation(
                    metric="vpd_kpa",
                    display_name="VPD",
                    unit="kPa",
                    accent="vpd",
                    value_precision=2,
                    y_min=0.1,
                    y_max=1.9,
                    current_enabled=True,
                    history_enabled=True,
                    dashboard_group="plant_water",
                    dashboard_group_label="Plant / Water",
                    dashboard_group_order=30,
                    display_order=40,
                ),
                CloudMetricPresentation(
                    metric="soil_moisture_raw",
                    display_name="Raw Moisture",
                    unit="raw",
                    accent="neutral",
                    value_precision=0,
                    y_min=None,
                    y_max=None,
                    current_enabled=False,
                    history_enabled=False,
                    dashboard_group=None,
                    dashboard_group_label=None,
                    dashboard_group_order=None,
                    display_order=50,
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get("/api/tents/main/metrics/presentation")

    assert response.status_code == 200
    body = response.json()
    assert [metric["metric"] for metric in body["current_metrics"]] == [
        "heater_intensity_pct",
        "humidity_pct",
        "fan_pct",
        "vpd_kpa",
    ]
    assert body["current_metrics"][0] == {
        "metric": "heater_intensity_pct",
        "display_name": "Heat Output",
        "unit": "%",
        "accent": "temp",
        "value_precision": 0,
        "y_min": 0.0,
        "y_max": 100.0,
        "display_order": 10,
    }
    assert [group["group"] for group in body["history_groups"]] == [
        "temperature_loop",
        "humidity_loop",
        "plant_water",
    ]
    assert body["history_groups"][0]["label"] == "Temperature Loop"
    assert body["history_groups"][0]["display_order"] == 10
    assert [metric["metric"] for metric in body["history_groups"][0]["metrics"]] == [
        "heater_intensity_pct",
        "fan_pct",
    ]
    assert [metric["metric"] for metric in body["history_groups"][1]["metrics"]] == [
        "humidity_pct",
        "dehumidifier_on",
    ]
    assert body["history_groups"][1]["metrics"][1] == {
        "metric": "dehumidifier_on",
        "display_name": "Dehumidifier Runtime",
        "unit": "%",
        "accent": "humidity",
        "value_precision": 0,
        "y_min": 0.0,
        "y_max": 100.0,
        "display_order": 25,
    }
    assert body["history_groups"][2]["metrics"][0] == {
        "metric": "vpd_kpa",
        "display_name": "VPD",
        "unit": "kPa",
        "accent": "vpd",
        "value_precision": 2,
        "y_min": 0.1,
        "y_max": 1.9,
        "display_order": 40,
    }
    assert body["supported_ranges"] == [
        {"range": "1h", "bucket": "5m"},
        {"range": "24h", "bucket": "1h"},
        {"range": "7d", "bucket": "4h"},
        {"range": "30d", "bucket": "4h"},
        {"range": "90d", "bucket": "1d"},
    ]


async def test_current_metrics_keep_device_scoped_streams_separate(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                CloudLatestMetric(
                    metric_key=(
                        "homebox:main:plant-a-node:soil_moisture_raw:soil_moisture_raw"
                    ),
                    site_id="homebox",
                    tent_id="main",
                    zone_id="canopy",
                    device_id="plant-a-node",
                    capability_id="soil_moisture_raw",
                    metric="soil_moisture_raw",
                    value=1800.0,
                    unit="raw",
                    source_updated_at=FIXED_NOW - timedelta(seconds=30),
                    received_at=FIXED_NOW,
                    stale_after_s=120,
                ),
                CloudLatestMetric(
                    metric_key=(
                        "homebox:main:plant-b-node:soil_moisture_raw:soil_moisture_raw"
                    ),
                    site_id="homebox",
                    tent_id="main",
                    zone_id="canopy",
                    device_id="plant-b-node",
                    capability_id="soil_moisture_raw",
                    metric="soil_moisture_raw",
                    value=2200.0,
                    unit="raw",
                    source_updated_at=FIXED_NOW - timedelta(seconds=30),
                    received_at=FIXED_NOW,
                    stale_after_s=120,
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get("/api/tents/main/metrics/current")

    assert response.status_code == 200
    rows = response.json()
    assert [row["device_id"] for row in rows] == ["plant-a-node", "plant-b-node"]
    assert [row["value"] for row in rows] == [1800.0, 2200.0]


async def test_metric_history_filters_bucket_and_window_by_range(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    rows = [
        _rollup("old-5m", bucket="5m", start=FIXED_NOW - timedelta(hours=2), avg=1.0),
        _rollup(
            "fresh-5m", bucket="5m", start=FIXED_NOW - timedelta(minutes=30), avg=2.0
        ),
        _rollup("fresh-1h", bucket="1h", start=FIXED_NOW - timedelta(hours=2), avg=3.0),
        _rollup("old-1h", bucket="1h", start=FIXED_NOW - timedelta(days=2), avg=4.0),
        _rollup("fresh-4h", bucket="4h", start=FIXED_NOW - timedelta(days=2), avg=5.0),
        _rollup("old-4h", bucket="4h", start=FIXED_NOW - timedelta(days=8), avg=6.0),
        _rollup(
            "fresh-30d-4h",
            bucket="4h",
            start=FIXED_NOW - timedelta(days=20),
            avg=7.0,
        ),
        _rollup(
            "fresh-90d-1d",
            bucket="1d",
            start=FIXED_NOW - timedelta(days=60),
            avg=8.0,
        ),
        _rollup(
            "old-90d-1d",
            bucket="1d",
            start=FIXED_NOW - timedelta(days=100),
            avg=9.0,
        ),
    ]
    async with sessionmaker() as session:
        session.add_all(rows)
        await session.commit()

    one_hour = await authed_client.get(
        "/api/tents/main/metrics/history?range=1h&metric=temperature_f"
    )
    one_day = await authed_client.get(
        "/api/tents/main/metrics/history?range=24h&metric=temperature_f"
    )
    seven_days = await authed_client.get(
        "/api/tents/main/metrics/history?range=7d&metric=temperature_f"
    )
    thirty_days = await authed_client.get(
        "/api/tents/main/metrics/history?range=30d&metric=temperature_f"
    )
    ninety_days = await authed_client.get(
        "/api/tents/main/metrics/history?range=90d&metric=temperature_f"
    )
    invalid = await authed_client.get(
        "/api/tents/main/metrics/history?range=180d&metric=temperature_f"
    )

    assert one_hour.status_code == 200
    assert one_day.status_code == 200
    assert seven_days.status_code == 200
    assert thirty_days.status_code == 200
    assert ninety_days.status_code == 200
    assert invalid.status_code == 400
    assert [point["bucket"] for point in one_hour.json()["points"]] == ["5m"]
    assert [point["avg"] for point in one_hour.json()["points"]] == [2.0]
    assert [point["bucket"] for point in one_day.json()["points"]] == ["1h"]
    assert [point["avg"] for point in one_day.json()["points"]] == [3.0]
    assert [point["bucket"] for point in seven_days.json()["points"]] == ["4h"]
    assert [point["avg"] for point in seven_days.json()["points"]] == [5.0]
    assert [point["bucket"] for point in thirty_days.json()["points"]] == [
        "4h",
        "4h",
        "4h",
    ]
    assert [point["avg"] for point in thirty_days.json()["points"]] == [7.0, 6.0, 5.0]
    assert [point["bucket"] for point in ninety_days.json()["points"]] == ["1d"]
    assert [point["avg"] for point in ninety_days.json()["points"]] == [8.0]


async def test_metric_history_can_filter_exact_device_stream(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    rows = [
        _rollup(
            "plant-a",
            bucket="1h",
            start=FIXED_NOW - timedelta(hours=2),
            avg=1800.0,
            device_id="plant-a-node",
            metric="soil_moisture_raw",
            capability_id="soil_moisture_raw",
            unit="raw",
        ),
        _rollup(
            "plant-b",
            bucket="1h",
            start=FIXED_NOW - timedelta(hours=2),
            avg=2200.0,
            device_id="plant-b-node",
            metric="soil_moisture_raw",
            capability_id="soil_moisture_raw",
            unit="raw",
        ),
    ]
    async with sessionmaker() as session:
        session.add_all(rows)
        await session.commit()

    response = await authed_client.get(
        "/api/tents/main/metrics/history"
        "?range=24h&metric=soil_moisture_raw"
        "&device_id=plant-a-node&capability_id=soil_moisture_raw"
    )
    invalid = await authed_client.get(
        "/api/tents/main/metrics/history"
        "?range=24h&metric=soil_moisture_raw&device_id=plant-a-node"
    )

    assert response.status_code == 200
    assert [point["avg"] for point in response.json()["points"]] == [1800.0]
    assert invalid.status_code == 400


async def test_browser_plants_require_auth(client: AsyncClient) -> None:
    response = await client.get("/api/tents/main/plants")

    assert response.status_code == 401


async def test_browser_plant_list_orders_and_marks_moisture_streams(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _plant(
                    "b",
                    display_order=2,
                    moisture_device_id=None,
                    moisture_capability_id=None,
                    is_active=False,
                ),
                _plant("a", display_order=1),
            ]
        )
        session.add(
            CloudLatestMetric(
                metric_key="homebox:main:plant-a-node:soil_moisture_raw:soil_moisture_pct",
                site_id="homebox",
                tent_id="main",
                zone_id=None,
                device_id="plant-a-node",
                capability_id="soil_moisture_raw",
                metric="soil_moisture_pct",
                value=57.0,
                unit="%",
                source_updated_at=FIXED_NOW - timedelta(seconds=30),
                received_at=FIXED_NOW,
                stale_after_s=120,
            )
        )
        await session.commit()

    response = await authed_client.get("/api/tents/main/plants")

    assert response.status_code == 200
    rows = response.json()
    assert [row["plant_id"] for row in rows] == ["a", "b"]
    assert rows[0]["has_moisture_stream"] is True
    assert rows[0]["moisture_device_id"] == "plant-a-node"
    assert rows[0]["latest_moisture"]["metric"] == "soil_moisture_pct"
    assert rows[0]["latest_moisture"]["value"] == 57.0
    assert rows[0]["wiki_path"] == "wiki/grows/main-2026-03-15/plants/plant-a.md"
    assert rows[1]["has_moisture_stream"] is False
    assert rows[1]["latest_moisture"] is None


async def test_browser_plant_detail_returns_metadata_latest_and_freshness(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(_plant("a", display_order=1))
        session.add(
            CloudLatestMetric(
                metric_key="homebox:main:plant-a-node:soil_moisture_raw:soil_moisture_pct",
                site_id="homebox",
                tent_id="main",
                zone_id=None,
                device_id="plant-a-node",
                capability_id="soil_moisture_raw",
                metric="soil_moisture_pct",
                value=58.5,
                unit="%",
                source_updated_at=FIXED_NOW - timedelta(seconds=45),
                received_at=FIXED_NOW,
                stale_after_s=120,
            )
        )
        session.add(
            CloudWikiPage(
                wiki_key="homebox:wiki/grows/main-2026-03-15/plants/plant-a.md",
                site_id="homebox",
                path="wiki/grows/main-2026-03-15/plants/plant-a.md",
                title="Plant A Wiki",
                frontmatter={"title": "Plant A Wiki", "type": "plant"},
                body_markdown="# Plant A Wiki\n\nProjected body.\n",
                sha256="f" * 64,
                source_updated_at=FIXED_NOW - timedelta(hours=1),
                synced_at=FIXED_NOW,
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        await session.commit()

    response = await authed_client.get("/api/tents/main/plants/a")

    assert response.status_code == 200
    body = response.json()
    assert body["plant_id"] == "a"
    assert body["name"] == "Plant A"
    assert body["moisture_device_id"] == "plant-a-node"
    assert body["moisture_capability_id"] == "soil_moisture_raw"
    assert body["target_bounds"] == {"low": 55.0, "high": 70.0}
    assert body["latest_moisture"]["metric"] == "soil_moisture_pct"
    assert body["latest_moisture"]["value"] == 58.5
    assert body["freshness"] == {"source_age_s": 45, "is_current": True}
    assert body["wiki_path"] == "wiki/grows/main-2026-03-15/plants/plant-a.md"
    assert body["wiki_content"] == {
        "path": "wiki/grows/main-2026-03-15/plants/plant-a.md",
        "title": "Plant A Wiki",
        "frontmatter": {"title": "Plant A Wiki", "type": "plant"},
        "body_markdown": "# Plant A Wiki\n\nProjected body.\n",
        "sha256": "f" * 64,
        "source_updated_at": "2026-05-05T02:45:00Z",
    }


async def test_browser_plants_use_latest_synced_row_per_public_plant_id(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _plant(
                    "a",
                    display_order=9,
                    grow_run_id="main-2025-01-01",
                    moisture_device_id="old-plant-a-node",
                    synced_at=FIXED_NOW - timedelta(days=30),
                    is_active=False,
                ),
                _plant(
                    "a",
                    display_order=1,
                    grow_run_id="main-2026-03-15",
                    moisture_device_id="new-plant-a-node",
                    synced_at=FIXED_NOW,
                ),
            ]
        )
        session.add(
            CloudLatestMetric(
                metric_key="homebox:main:new-plant-a-node:soil_moisture_raw:soil_moisture_pct",
                site_id="homebox",
                tent_id="main",
                zone_id=None,
                device_id="new-plant-a-node",
                capability_id="soil_moisture_raw",
                metric="soil_moisture_pct",
                value=61.0,
                unit="%",
                source_updated_at=FIXED_NOW - timedelta(seconds=30),
                received_at=FIXED_NOW,
                stale_after_s=120,
            )
        )
        await session.commit()

    listed = await authed_client.get("/api/tents/main/plants")
    detail = await authed_client.get("/api/tents/main/plants/a")

    assert listed.status_code == 200
    listed_rows = listed.json()
    assert len(listed_rows) == 1
    assert listed_rows[0]["plant_id"] == "a"
    assert listed_rows[0]["grow_run_id"] == "main-2026-03-15"
    assert listed_rows[0]["moisture_device_id"] == "new-plant-a-node"
    assert detail.status_code == 200
    assert detail.json()["grow_run_id"] == "main-2026-03-15"
    assert detail.json()["moisture_device_id"] == "new-plant-a-node"
    assert detail.json()["latest_moisture"]["value"] == 61.0
    assert detail.json()["wiki_content"] is None


async def test_browser_plant_detail_and_history_404_without_moisture_stream(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(
            _plant(
                "b",
                display_order=2,
                moisture_device_id=None,
                moisture_capability_id=None,
                is_active=False,
            )
        )
        await session.commit()

    missing = await authed_client.get("/api/tents/main/plants/missing")
    no_stream_detail = await authed_client.get("/api/tents/main/plants/b")
    no_stream_history = await authed_client.get(
        "/api/tents/main/plants/b/moisture/history?range=24h"
    )

    assert missing.status_code == 404
    assert no_stream_detail.status_code == 404
    assert no_stream_history.status_code == 404


async def test_browser_plant_moisture_history_filters_exact_stream_and_range(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(_plant("a", display_order=1))
        session.add_all(
            [
                _rollup(
                    "plant-a-fresh",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=52.0,
                    device_id="plant-a-node",
                    metric="soil_moisture_pct",
                    capability_id="soil_moisture_raw",
                    unit="%",
                ),
                _rollup(
                    "plant-a-old",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(days=2),
                    avg=51.0,
                    device_id="plant-a-node",
                    metric="soil_moisture_pct",
                    capability_id="soil_moisture_raw",
                    unit="%",
                ),
                _rollup(
                    "plant-b-fresh",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=47.0,
                    device_id="plant-b-node",
                    metric="soil_moisture_pct",
                    capability_id="soil_moisture_raw",
                    unit="%",
                ),
                _rollup(
                    "plant-a-wrong-metric",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=1800.0,
                    device_id="plant-a-node",
                    metric="soil_moisture_raw",
                    capability_id="soil_moisture_raw",
                    unit="raw",
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get(
        "/api/tents/main/plants/a/moisture/history?range=24h"
    )
    invalid = await authed_client.get(
        "/api/tents/main/plants/a/moisture/history?range=180d"
    )

    assert response.status_code == 200
    assert response.json()["metric"] == "soil_moisture_pct"
    assert response.json()["range"] == "24h"
    assert [point["avg"] for point in response.json()["points"]] == [52.0]
    assert invalid.status_code == 400


async def test_browser_plant_moisture_comparison_history_returns_all_tent_streams(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _plant("b", display_order=2, moisture_device_id="plant-b-node"),
                _plant("a", display_order=1),
                _plant(
                    "c",
                    display_order=3,
                    moisture_device_id=None,
                    moisture_capability_id=None,
                ),
            ]
        )
        session.add_all(
            [
                CloudLatestMetric(
                    metric_key=(
                        "homebox:main:plant-a-node:soil_moisture_raw:soil_moisture_pct"
                    ),
                    site_id="homebox",
                    tent_id="main",
                    zone_id=None,
                    device_id="plant-a-node",
                    capability_id="soil_moisture_raw",
                    metric="soil_moisture_pct",
                    value=52.0,
                    unit="%",
                    source_updated_at=FIXED_NOW - timedelta(seconds=30),
                    received_at=FIXED_NOW,
                    stale_after_s=120,
                ),
                CloudLatestMetric(
                    metric_key=(
                        "homebox:main:plant-b-node:soil_moisture_raw:soil_moisture_pct"
                    ),
                    site_id="homebox",
                    tent_id="main",
                    zone_id=None,
                    device_id="plant-b-node",
                    capability_id="soil_moisture_raw",
                    metric="soil_moisture_pct",
                    value=64.0,
                    unit="%",
                    source_updated_at=FIXED_NOW - timedelta(seconds=45),
                    received_at=FIXED_NOW,
                    stale_after_s=120,
                ),
            ]
        )
        session.add_all(
            [
                _rollup(
                    "plant-a-fresh",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=52.0,
                    device_id="plant-a-node",
                    metric="soil_moisture_pct",
                    capability_id="soil_moisture_raw",
                    unit="%",
                ),
                _rollup(
                    "plant-b-fresh",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=64.0,
                    device_id="plant-b-node",
                    metric="soil_moisture_pct",
                    capability_id="soil_moisture_raw",
                    unit="%",
                ),
                _rollup(
                    "plant-a-wrong-metric",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=1800.0,
                    device_id="plant-a-node",
                    metric="soil_moisture_raw",
                    capability_id="soil_moisture_raw",
                    unit="raw",
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get(
        "/api/tents/main/plants/moisture/history?range=24h"
    )
    invalid = await authed_client.get(
        "/api/tents/main/plants/moisture/history?range=180d"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "soil_moisture_pct"
    assert body["range"] == "24h"
    assert [plant["plant_id"] for plant in body["plants"]] == ["a", "b"]
    assert [plant["latest_moisture"]["value"] for plant in body["plants"]] == [
        52.0,
        64.0,
    ]
    assert [plant["points"][0]["avg"] for plant in body["plants"]] == [52.0, 64.0]
    assert invalid.status_code == 400


async def test_browser_plant_history_uses_latest_synced_row_per_public_plant_id(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _plant(
                    "a",
                    display_order=9,
                    grow_run_id="main-2025-01-01",
                    moisture_device_id="old-plant-a-node",
                    synced_at=FIXED_NOW - timedelta(days=30),
                    is_active=False,
                ),
                _plant(
                    "a",
                    display_order=1,
                    grow_run_id="main-2026-03-15",
                    moisture_device_id="new-plant-a-node",
                    synced_at=FIXED_NOW,
                ),
            ]
        )
        session.add_all(
            [
                _rollup(
                    "old-grow",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=40.0,
                    device_id="old-plant-a-node",
                    metric="soil_moisture_pct",
                    capability_id="soil_moisture_raw",
                    unit="%",
                ),
                _rollup(
                    "new-grow",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=65.0,
                    device_id="new-plant-a-node",
                    metric="soil_moisture_pct",
                    capability_id="soil_moisture_raw",
                    unit="%",
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get(
        "/api/tents/main/plants/a/moisture/history?range=24h"
    )

    assert response.status_code == 200
    assert [point["avg"] for point in response.json()["points"]] == [65.0]


async def test_metric_history_uses_canonical_metrics_and_runtime_percentage(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _rollup(
                    "fan",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=44.0,
                    metric="fan_pct",
                    capability_id="fan_pct",
                    unit="%",
                ),
                _rollup(
                    "humidifier",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=50.0,
                    min_value=44.44,
                    max_value=55.56,
                    metric="humidifier_intensity_pct",
                    capability_id="humidifier_intensity_pct",
                    unit="%",
                ),
                _rollup(
                    "heater",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=70.0,
                    metric="heater_intensity_pct",
                    capability_id="heat_level",
                    unit="%",
                ),
                _rollup(
                    "dehumidifier",
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    min_value=0.0,
                    avg=0.65,
                    max_value=1.0,
                    metric="dehumidifier_on",
                    capability_id="power",
                    unit="bool",
                ),
            ]
        )
        await session.commit()

    fan = await authed_client.get(
        "/api/tents/main/metrics/history?range=24h&metric=fan_pct"
    )
    humidifier = await authed_client.get(
        "/api/tents/main/metrics/history?range=24h&metric=humidifier_intensity_pct"
    )
    heater = await authed_client.get(
        "/api/tents/main/metrics/history?range=24h&metric=heater_intensity_pct"
    )
    dehumidifier = await authed_client.get(
        "/api/tents/main/metrics/history?range=24h&metric=dehumidifier_on"
    )

    assert fan.status_code == 200
    assert fan.json()["metric"] == "fan_pct"
    assert fan.json()["points"][0]["avg"] == 44.0
    assert fan.json()["points"][0]["unit"] == "%"
    assert humidifier.status_code == 200
    assert humidifier.json()["metric"] == "humidifier_intensity_pct"
    assert humidifier.json()["points"][0]["min"] == 44.44
    assert humidifier.json()["points"][0]["avg"] == 50.0
    assert humidifier.json()["points"][0]["max"] == 55.56
    assert humidifier.json()["points"][0]["unit"] == "%"
    assert heater.status_code == 200
    assert heater.json()["metric"] == "heater_intensity_pct"
    assert heater.json()["points"][0]["avg"] == 70.0
    assert heater.json()["points"][0]["unit"] == "%"
    assert dehumidifier.status_code == 200
    assert dehumidifier.json()["metric"] == "dehumidifier_on"
    assert dehumidifier.json()["points"][0]["min"] == 0.0
    assert dehumidifier.json()["points"][0]["avg"] == 65.0
    assert dehumidifier.json()["points"][0]["max"] == 100.0
    assert dehumidifier.json()["points"][0]["unit"] == "%"


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
        "payload": {"preset_id": "overview"},
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
        "payload": {"preset_id": "overview"},
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


async def test_asset_complete_replaces_existing_asset_for_same_object_key(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    first = await client.post(
        "/api/gateway/v1/assets/complete",
        headers=gateway_headers,
        json={
            "site_id": "homebox",
            "tent_id": "main",
            "asset_id": "asset-old",
            "object_key": "homebox/main/snapshots/plant-a.jpg",
            "content_type": "image/jpeg",
            "byte_size": 10,
            "sha256": "a" * 64,
            "captured_at": "2026-05-05T03:40:00Z",
        },
    )
    second = await client.post(
        "/api/gateway/v1/assets/complete",
        headers=gateway_headers,
        json={
            "site_id": "homebox",
            "tent_id": "main",
            "asset_id": "asset-new",
            "object_key": "homebox/main/snapshots/plant-a.jpg",
            "content_type": "image/jpeg",
            "byte_size": 20,
            "sha256": "b" * 64,
            "captured_at": "2026-05-05T03:45:00Z",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["asset_id"] == "asset-new"
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        assets = (
            (
                await session.execute(
                    select(CloudAsset).where(
                        CloudAsset.object_key == "homebox/main/snapshots/plant-a.jpg"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(assets) == 1
    assert assets[0].asset_id == "asset-new"
    assert assets[0].byte_size == 20


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
            "payload": {"preset_id": "overview"},
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


async def test_health_audits_current_metrics_without_device_liveness(
    client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(
            CloudSite(
                site_id="homebox",
                name="Homebox",
                timezone="America/Denver",
                gateway_last_seen_at=None,
                gateway_backlog_depth=0,
                last_catalog_sync_at=FIXED_NOW,
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        session.add(
            CloudDevice(
                device_key="homebox:main:env-main",
                site_id="homebox",
                tent_id="main",
                zone_id="canopy",
                device_id="env-main",
                name="Env Main",
                kind="sensor",
                is_active=True,
                last_seen_at=None,
                synced_at=FIXED_NOW,
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        session.add(
            CloudLatestMetric(
                metric_key="homebox:main:env-main:env-main-temp:temperature_f",
                site_id="homebox",
                tent_id="main",
                zone_id="canopy",
                device_id="env-main",
                capability_id="env-main-temp",
                metric="temperature_f",
                value=74.5,
                unit="f",
                source_updated_at=FIXED_NOW - timedelta(seconds=30),
                received_at=FIXED_NOW,
                stale_after_s=120,
            )
        )
        await session.commit()

    health = await client.get("/api/health")

    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert health.json()["status"] == "offline"
    async with sessionmaker() as session:
        event = (
            await session.execute(
                select(CloudAuditEvent).where(
                    CloudAuditEvent.event_type
                    == "data_consistency_missing_device_liveness"
                )
            )
        ).scalar_one()
    assert event.actor_type == "system"
    assert event.site_id == "homebox"
    assert event.subject_type == "cloud_device"
    assert event.subject_id == "homebox:main:env-main"
    assert event.event_metadata == {
        "tent_id": "main",
        "device_id": "env-main",
        "metrics": ["temperature_f"],
        "capability_ids": ["env-main-temp"],
    }


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
            "payload": {"preset_id": "overview"},
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
                "payload": {"preset_id": "overview"},
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
