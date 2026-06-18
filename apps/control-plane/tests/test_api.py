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
    CloudPlantLine,
    CloudPlantLocation,
    CloudPlantMetricStream,
    CloudSchedule,
    CloudSeedLot,
    CloudSite,
    CloudTent,
    CloudWikiPage,
    CloudZone,
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
    is_active: bool = True,
    synced_at: datetime = FIXED_NOW,
) -> CloudPlant:
    _ = display_order
    source_plant_id = _source_plant_id(plant_id)
    return CloudPlant(
        site_id="homebox",
        source_plant_id=source_plant_id,
        line_source_id=1,
        sex_key="unknown",
        source_seed_lot_id=1,
        clone_source_plant_id=None,
        key=_plant_key(plant_id),
        name=f"Plant {plant_id.upper()}",
        germinated_at=FIXED_NOW - timedelta(days=51),
        culled_at=None if is_active else FIXED_NOW - timedelta(days=1),
        culled_reason=None if is_active else "test fixture",
        is_active=is_active,
        synced_at=synced_at,
        created_at=FIXED_NOW,
        updated_at=synced_at,
    )


def _plant_line() -> CloudPlantLine:
    return CloudPlantLine(
        site_id="homebox",
        source_line_id=1,
        project_code="SBBS",
        generation_label="R1",
        strain="Sirius Black x BS01",
        cultivar="R1",
        description=None,
        source_name="Unknown vendor",
        synced_at=FIXED_NOW,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _seed_lot(
    source_seed_lot_id: int = 1,
    *,
    line_source_id: int = 1,
    sex_type_key: str = "feminized",
    is_purchased: bool = True,
    seed_count: int | None = 12,
) -> CloudSeedLot:
    return CloudSeedLot(
        site_id="homebox",
        source_seed_lot_id=source_seed_lot_id,
        line_source_id=line_source_id,
        sex_type_key=sex_type_key,
        is_purchased=is_purchased,
        vendor_name="Unknown vendor" if is_purchased else None,
        acquired_at=FIXED_NOW - timedelta(days=60) if is_purchased else None,
        produced_by_cross_event_source_id=None if is_purchased else 42,
        seed_count=seed_count,
        notes=None,
        synced_at=FIXED_NOW,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _plant_location(
    plant_id: str,
    *,
    grid_position: str,
    synced_at: datetime = FIXED_NOW,
) -> CloudPlantLocation:
    return CloudPlantLocation(
        site_id="homebox",
        source_location_id=_source_plant_id(plant_id),
        source_plant_id=_source_plant_id(plant_id),
        tent_id="main",
        grid_position=grid_position,
        start_at=FIXED_NOW - timedelta(days=51),
        end_at=None,
        synced_at=synced_at,
        created_at=FIXED_NOW,
        updated_at=synced_at,
    )


def _plant_stream(
    plant_id: str,
    *,
    device_id: str = "plant-a-node",
    capability_id: str = "soil_moisture_pct",
    metric: str = "soil_moisture_pct",
    display_order: int = 1,
    is_active: bool = True,
) -> CloudPlantMetricStream:
    return CloudPlantMetricStream(
        site_id="homebox",
        source_plant_id=_source_plant_id(plant_id),
        device_id=device_id,
        capability_id=capability_id,
        metric=metric,
        display_order=display_order,
        is_active=is_active,
        synced_at=FIXED_NOW,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _plant_key(plant_id: str) -> str:
    return f"SBBS-R1-00{_source_plant_id(plant_id)}"


def _source_plant_id(plant_id: str) -> int:
    return ord(plant_id) - ord("a") + 1


def _tent(tent_id: str, name: str) -> CloudTent:
    return CloudTent(
        site_id="homebox",
        tent_id=tent_id,
        name=name,
        is_active=True,
        synced_at=FIXED_NOW,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _latest_metric(
    *,
    device_id: str,
    capability_id: str,
    metric: str,
    value: float,
    unit: str,
    source_updated_at: datetime = FIXED_NOW - timedelta(minutes=1),
    received_at: datetime = FIXED_NOW,
    stale_after_s: int = 300,
) -> CloudLatestMetric:
    return CloudLatestMetric(
        site_id="homebox",
        tent_id="main",
        zone_id="ignored-for-plant-detail",
        device_id=device_id,
        capability_id=capability_id,
        metric=metric,
        value=value,
        unit=unit,
        source_updated_at=source_updated_at,
        received_at=received_at,
        stale_after_s=stale_after_s,
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
        credential = (
            await session.execute(
                select(GatewayCredential).where(
                    GatewayCredential.credential_id == "homebox-gateway"
                )
            )
        ).scalar_one_or_none()

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
        credential = (
            await session.execute(
                select(GatewayCredential).where(
                    GatewayCredential.credential_id == "gateway-main"
                )
            )
        ).scalar_one_or_none()

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
        "plant_lines": [
            {
                "source_line_id": 1,
                "project_code": "SBBS",
                "generation_label": "R1",
                "strain": "Sirius Black x BS01",
                "cultivar": "SBBS R1",
                "description": None,
                "source_name": "Unknown vendor",
            }
        ],
        "seed_lots": [
            {
                "source_seed_lot_id": 1,
                "line_source_id": 1,
                "sex_type_key": "feminized",
                "is_purchased": True,
                "vendor_name": "Unknown vendor",
                "acquired_at": None,
                "produced_by_cross_event_source_id": None,
                "seed_count": None,
                "notes": None,
            }
        ],
        "plants": [
            {
                "source_plant_id": 1,
                "line_source_id": 1,
                "sex_key": "female",
                "source_seed_lot_id": 1,
                "clone_source_plant_id": None,
                "key": "SBBS-R1-001",
                "name": "Plant A",
                "germinated_at": "2026-03-15T12:00:00Z",
                "rooted_at": None,
                "veg_started_at": None,
                "flower_started_at": None,
                "culled_at": None,
                "culled_reason": None,
                "harvested_at": None,
                "selected_for_breeding_at": None,
                "selected_for_breeding_reason": None,
                "is_active": True,
            },
            {
                "source_plant_id": 2,
                "line_source_id": 1,
                "sex_key": "male",
                "source_seed_lot_id": 1,
                "clone_source_plant_id": None,
                "key": "SBBS-R1-002",
                "name": "Plant B",
                "germinated_at": "2026-03-15T12:00:00Z",
                "rooted_at": None,
                "veg_started_at": None,
                "flower_started_at": None,
                "culled_at": "2026-05-01T12:00:00Z",
                "culled_reason": "test fixture",
                "harvested_at": None,
                "selected_for_breeding_at": None,
                "selected_for_breeding_reason": None,
                "is_active": False,
            },
        ],
        "plant_locations": [
            {
                "source_location_id": 1,
                "source_plant_id": 1,
                "tent_id": "main",
                "grid_position": "A1",
                "start_at": "2026-03-15T12:00:00Z",
                "end_at": None,
            },
            {
                "source_location_id": 2,
                "source_plant_id": 2,
                "tent_id": "main",
                "grid_position": "B1",
                "start_at": "2026-03-15T12:00:00Z",
                "end_at": None,
            },
        ],
        "plant_metric_streams": [
            {
                "source_plant_id": 1,
                "device_id": "env-main",
                "capability_id": "env-main-temp",
                "metric": "temperature_f",
                "display_order": 1,
                "is_active": True,
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
    assert first.json()["plant_lines"] == 1
    assert first.json()["seed_lots"] == 1
    assert first.json()["plants"] == 2
    assert first.json()["plant_locations"] == 2
    assert first.json()["plant_metric_streams"] == 1
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        tent_count = await session.scalar(select(func.count()).select_from(CloudTent))
        zone_count = await session.scalar(select(func.count()).select_from(CloudZone))
        device_count = await session.scalar(
            select(func.count()).select_from(CloudDevice)
        )
        capability_count = await session.scalar(
            select(func.count()).select_from(CloudCapability)
        )
        schedule_count = await session.scalar(
            select(func.count()).select_from(CloudSchedule)
        )
        line_count = await session.scalar(
            select(func.count()).select_from(CloudPlantLine)
        )
        seed_lot_count = await session.scalar(
            select(func.count()).select_from(CloudSeedLot)
        )
        plant_count = await session.scalar(select(func.count()).select_from(CloudPlant))
        location_count = await session.scalar(
            select(func.count()).select_from(CloudPlantLocation)
        )
        stream_count = await session.scalar(
            select(func.count()).select_from(CloudPlantMetricStream)
        )
        plant_a = (
            await session.execute(
                select(CloudPlant).where(
                    CloudPlant.site_id == "homebox",
                    CloudPlant.source_plant_id == 1,
                )
            )
        ).scalar_one_or_none()
        seed_lot = (
            await session.execute(
                select(CloudSeedLot).where(
                    CloudSeedLot.site_id == "homebox",
                    CloudSeedLot.source_seed_lot_id == 1,
                )
            )
        ).scalar_one_or_none()
        plant_a_location = (
            await session.execute(
                select(CloudPlantLocation).where(
                    CloudPlantLocation.site_id == "homebox",
                    CloudPlantLocation.source_plant_id == 1,
                    CloudPlantLocation.tent_id == "main",
                    CloudPlantLocation.grid_position == "A1",
                )
            )
        ).scalar_one_or_none()
        plant_a_stream = (
            await session.execute(
                select(CloudPlantMetricStream).where(
                    CloudPlantMetricStream.site_id == "homebox",
                    CloudPlantMetricStream.source_plant_id == 1,
                    CloudPlantMetricStream.device_id == "env-main",
                    CloudPlantMetricStream.capability_id == "env-main-temp",
                    CloudPlantMetricStream.metric == "temperature_f",
                )
            )
        ).scalar_one_or_none()
    assert tent_count == 1
    assert zone_count == 1
    assert device_count == 2
    assert capability_count == 2
    assert schedule_count == 1
    assert line_count == 1
    assert seed_lot_count == 1
    assert plant_count == 2
    assert location_count == 2
    assert stream_count == 1
    assert plant_a is not None
    assert plant_a.key == "SBBS-R1-001"
    assert plant_a.line_source_id == 1
    assert plant_a.sex_key == "female"
    assert seed_lot is not None
    assert seed_lot.sex_type_key == "feminized"
    assert plant_a_location is not None
    assert plant_a_stream is not None
    assert plant_a_stream.display_order == 1
    assert plant_a_stream.is_active is True


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


async def test_rollup_upsert_is_idempotent(
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
                "device_id": "env-main",
                "capability_id": "env-main-temp",
                "metric": "temperature_f",
                "bucket": "1h",
                "bucket_start_at": "2026-05-05T03:00:00Z",
                "bucket_end_at": "2026-05-05T04:00:00Z",
                "min_value": 70.0,
                "avg_value": 75.0,
                "max_value": 80.0,
                "sample_count": 12,
                "unit": "f",
            }
        ],
    }
    assert (
        await client.post(
            "/api/gateway/v1/metrics/rollups",
            json=payload,
            headers=gateway_headers,
        )
    ).status_code == 200
    payload["rollups"][0]["avg_value"] = 76.0
    payload["rollups"][0]["sample_count"] = 13
    assert (
        await client.post(
            "/api/gateway/v1/metrics/rollups",
            json=payload,
            headers=gateway_headers,
        )
    ).status_code == 200

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        rows = (await session.execute(select(CloudMetricRollup))).scalars().all()
    assert len(rows) == 1
    assert rows[0].avg_value == 76.0
    assert rows[0].sample_count == 13
    assert rows[0].device_id == "env-main"


async def test_current_metrics_expose_canonical_metric_names(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                CloudLatestMetric(
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
                    metric="dehumidifier_runtime_pct",
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
        "dehumidifier_runtime_pct",
    ]
    assert body["history_groups"][1]["metrics"][1] == {
        "metric": "dehumidifier_runtime_pct",
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
        _rollup(bucket="5m", start=FIXED_NOW - timedelta(hours=2), avg=1.0),
        _rollup(
            bucket="5m",
            start=FIXED_NOW - timedelta(minutes=30),
            avg=2.0,
        ),
        _rollup(bucket="1h", start=FIXED_NOW - timedelta(hours=2), avg=3.0),
        _rollup(bucket="1h", start=FIXED_NOW - timedelta(days=2), avg=4.0),
        _rollup(bucket="4h", start=FIXED_NOW - timedelta(days=2), avg=5.0),
        _rollup(bucket="4h", start=FIXED_NOW - timedelta(days=8), avg=6.0),
        _rollup(
            bucket="4h",
            start=FIXED_NOW - timedelta(days=20),
            avg=7.0,
        ),
        _rollup(
            bucket="1d",
            start=FIXED_NOW - timedelta(days=60),
            avg=8.0,
        ),
        _rollup(
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
            bucket="1h",
            start=FIXED_NOW - timedelta(hours=2),
            avg=1800.0,
            device_id="plant-a-node",
            metric="soil_moisture_raw",
            capability_id="soil_moisture_raw",
            unit="raw",
        ),
        _rollup(
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


async def test_breeding_logbook_routes_require_auth(client: AsyncClient) -> None:
    response = await client.get("/api/breeding-logbook/bootstrap")

    assert response.status_code == 401


async def test_breeding_logbook_bootstrap_returns_lookups_and_locations(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _tent("main", "Main flower"),
                _tent("breeding", "Breeding tent"),
            ]
        )
        await session.commit()

    response = await authed_client.get("/api/breeding-logbook/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["today"] == "2026-05-05"
    assert [row["key"] for row in body["plant_sexes"]] == [
        "unknown",
        "male",
        "female",
        "herm",
        "reversed",
    ]
    assert [row["key"] for row in body["seed_lot_sex_types"]] == [
        "unknown",
        "feminized",
        "regular",
    ]
    assert body["locations"] == [
        {
            "key": "breeding",
            "display_name": "Breeding tent",
            "stage_key": "breeding",
            "tent_id": "breeding",
            "grid_position": None,
        },
        {
            "key": "main",
            "display_name": "Main flower",
            "stage_key": "flower",
            "tent_id": "main",
            "grid_position": None,
        },
    ]


async def test_breeding_logbook_plant_list_is_site_wide_and_screen_shaped(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _plant_line(),
                _seed_lot(),
                _plant("b", display_order=2, is_active=False),
                _plant("a", display_order=1),
                _plant_location("b", grid_position="B1"),
                _plant_location("a", grid_position="A1"),
            ]
        )
        session.add(_plant_stream("a"))
        await session.commit()

    response = await authed_client.get(
        "/api/breeding-logbook/plants?include_culled=false&group_by=stage"
    )
    with_culled = await authed_client.get(
        "/api/breeding-logbook/plants?include_culled=true&group_by=stage"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["group_by"] == "stage"
    assert body["active_count"] == 1
    assert body["culled_count"] == 0
    assert [row["key"] for row in body["plants"]] == ["SBBS-R1-001"]
    assert body["plants"][0] == {
        "id": "1",
        "key": "SBBS-R1-001",
        "name": "Plant A",
        "generation": "R1",
        "parents_label": "Sirius Black x BS01 x R1",
        "sex_key": "unknown",
        "stage_key": "germinating",
        "stage_day": 51,
        "germinated_on": "2026-03-15",
        "veg_started_on": None,
        "flower_started_on": None,
        "culled_on": None,
        "location_key": "main",
        "location_label": "main / A1",
        "seed_lot_label": "SBBS R1 #1",
        "last_note": "",
        "telemetry_summary": "1 plant stream",
    }
    assert with_culled.status_code == 200
    assert with_culled.json()["culled_count"] == 1
    assert [row["key"] for row in with_culled.json()["plants"]] == [
        "SBBS-R1-001",
        "SBBS-R1-002",
    ]


async def test_breeding_logbook_seed_lots_include_lots_without_current_plants(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(_plant_line())
        session.add_all(
            [
                _seed_lot(),
                _seed_lot(
                    2,
                    sex_type_key="regular",
                    is_purchased=False,
                    seed_count=None,
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get("/api/breeding-logbook/seed-lots")

    assert response.status_code == 200
    assert response.json()["seed_lots"] == [
        {
            "id": "1",
            "label": "SBBS R1 #1",
            "prefix": "SBBS",
            "generation": "R1",
            "source": "purchased",
            "source_label": "Unknown vendor",
            "parents_label": "Sirius Black x BS01 x R1",
            "sex_type_key": "feminized",
            "seed_count": 12,
        },
        {
            "id": "2",
            "label": "SBBS R1 #2",
            "prefix": "SBBS",
            "generation": "R1",
            "source": "cross",
            "source_label": "in-house cross",
            "parents_label": "Sirius Black x BS01 x R1",
            "sex_type_key": "regular",
            "seed_count": None,
        },
    ]


async def test_breeding_logbook_plant_detail_and_history_reuse_cloud_projection(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _plant_line(),
                _seed_lot(),
                _plant("a", display_order=1),
                _plant_location("a", grid_position="A1"),
                _plant_stream(
                    "a",
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                ),
                _latest_metric(
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    value=21.0,
                    unit="degC",
                ),
                _rollup(
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    min_value=20.0,
                    avg=21.0,
                    max_value=22.0,
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    unit="degC",
                ),
            ]
        )
        await session.commit()

    detail = await authed_client.get("/api/breeding-logbook/plants/SBBS-R1-001")
    history = await authed_client.get(
        "/api/breeding-logbook/plants/SBBS-R1-001/metrics/history?range=24h"
    )
    missing = await authed_client.get("/api/breeding-logbook/plants/missing")

    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["plant"]["key"] == "SBBS-R1-001"
    assert detail_body["lineage"] == {
        "parents": "Sirius Black x BS01 x R1",
        "offspring": "No offspring projected",
    }
    assert detail_body["metrics"] == [
        {"label": "Substrate Temp", "value": "69.8°F", "tone": "ok"}
    ]
    assert detail_body["events"] == []
    assert detail_body["wiki_content"] is None
    assert history.status_code == 200
    assert history.json()["streams"][0]["metric"] == "substrate_temp_c"
    assert history.json()["streams"][0]["points"][0]["avg"] == 69.8
    assert missing.status_code == 404


async def test_browser_plant_list_orders_and_counts_telemetry_streams(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _plant_line(),
                _plant("b", display_order=2, is_active=False),
                _plant("a", display_order=1),
                _plant_location("b", grid_position="B1"),
                _plant_location("a", grid_position="A1"),
            ]
        )
        session.add(_plant_stream("a"))
        await session.commit()

    response = await authed_client.get("/api/tents/main/plants")

    assert response.status_code == 200
    rows = response.json()
    assert [row["key"] for row in rows] == ["SBBS-R1-001", "SBBS-R1-002"]
    assert [row["grid_position"] for row in rows] == ["A1", "B1"]
    assert rows[0]["id"] == 1
    assert rows[0]["sex_key"] == "unknown"
    assert rows[0]["line"] == {
        "id": 1,
        "project_code": "SBBS",
        "generation_label": "R1",
        "strain": "Sirius Black x BS01",
        "cultivar": "R1",
        "source_name": "Unknown vendor",
    }
    assert rows[0]["telemetry_stream_count"] == 1
    assert rows[1]["telemetry_stream_count"] == 0
    assert "grow_run_id" not in rows[0]
    assert "moisture_target_low" not in rows[0]
    assert "moisture_target_high" not in rows[0]


async def test_browser_plant_detail_returns_metadata_wiki_and_telemetry_count(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(_plant_line())
        session.add(_plant("a", display_order=1))
        session.add(_plant_location("a", grid_position="A1"))
        session.add(_plant_stream("a"))
        await session.commit()

    response = await authed_client.get("/api/tents/main/plants/SBBS-R1-001")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["key"] == "SBBS-R1-001"
    assert body["sex_key"] == "unknown"
    assert body["grid_position"] == "A1"
    assert body["current_location"] == {
        "id": 1,
        "tent_id": "main",
        "grid_position": "A1",
        "start_at": (FIXED_NOW - timedelta(days=51)).isoformat().replace("+00:00", "Z"),
        "end_at": None,
    }
    assert body["line"] == {
        "id": 1,
        "project_code": "SBBS",
        "generation_label": "R1",
        "strain": "Sirius Black x BS01",
        "cultivar": "R1",
        "source_name": "Unknown vendor",
    }
    assert body["name"] == "Plant A"
    assert body["telemetry_stream_count"] == 1
    assert body["telemetry"] == [
        {
            "metric": "soil_moisture_pct",
            "display_name": "Soil Moisture",
            "display_unit": "%",
            "source_unit": "%",
            "value_precision": 0,
            "accent": "moisture",
            "y_min": 0.0,
            "y_max": 100.0,
            "display_order": 1,
            "history_enabled": True,
            "device_id": "plant-a-node",
            "capability_id": "soil_moisture_pct",
            "latest_reading": None,
        }
    ]
    assert body["notes"] == []
    assert body["events"] == []
    assert body["wiki_content"] is None
    assert "grow_run_id" not in body
    assert "target_bounds" not in body


async def test_browser_plants_use_current_location_and_source_plant_stream_identity(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _plant("a", display_order=1, synced_at=FIXED_NOW),
                _plant_location("a", grid_position="A1", synced_at=FIXED_NOW),
            ]
        )
        session.add(
            _plant_stream(
                "a",
                device_id="new-plant-a-node",
            )
        )
        await session.commit()

    listed = await authed_client.get("/api/tents/main/plants")
    detail = await authed_client.get("/api/tents/main/plants/SBBS-R1-001")

    assert listed.status_code == 200
    listed_rows = listed.json()
    assert len(listed_rows) == 1
    assert listed_rows[0]["id"] == 1
    assert listed_rows[0]["key"] == "SBBS-R1-001"
    assert listed_rows[0]["sex_key"] == "unknown"
    assert listed_rows[0]["telemetry_stream_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["id"] == 1
    assert detail.json()["telemetry_stream_count"] == 1
    assert detail.json()["wiki_content"] is None


async def test_browser_plant_detail_returns_plants_without_telemetry(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(_plant("b", display_order=2, is_active=False))
        session.add(_plant_location("b", grid_position="B1"))
        await session.commit()

    missing = await authed_client.get("/api/tents/main/plants/missing")
    detail = await authed_client.get("/api/tents/main/plants/SBBS-R1-002")

    assert missing.status_code == 404
    assert detail.status_code == 200
    assert detail.json()["telemetry_stream_count"] == 0
    assert detail.json()["telemetry"] == []


async def test_browser_plant_detail_exposes_mapped_latest_with_display_conversions(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(_plant("a", display_order=1))
        session.add(_plant_location("a", grid_position="A1"))
        session.add_all(
            [
                _plant_stream(
                    "a",
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    display_order=1,
                ),
                _plant_stream(
                    "a",
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-ec",
                    metric="substrate_ec_us_cm",
                    display_order=2,
                ),
                _plant_stream(
                    "a",
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-ph",
                    metric="substrate_ph",
                    display_order=3,
                ),
                _plant_stream(
                    "a",
                    device_id="plant-a-substrate-node",
                    capability_id="disabled-moisture",
                    metric="soil_moisture_pct",
                    display_order=4,
                    is_active=False,
                ),
            ]
        )
        session.add_all(
            [
                _latest_metric(
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    value=21.0,
                    unit="degC",
                    stale_after_s=600,
                ),
                _latest_metric(
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-ec",
                    metric="substrate_ec_us_cm",
                    value=1234.0,
                    unit="us/cm",
                ),
                _latest_metric(
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-ph",
                    metric="substrate_ph",
                    value=6.4,
                    unit="pH",
                ),
                _latest_metric(
                    device_id="other-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    value=1.0,
                    unit="degC",
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get("/api/tents/main/plants/SBBS-R1-001")

    assert response.status_code == 200
    telemetry = {stream["metric"]: stream for stream in response.json()["telemetry"]}
    assert list(telemetry) == ["substrate_temp_c", "substrate_ec_us_cm", "substrate_ph"]
    assert telemetry["substrate_temp_c"]["display_name"] == "Substrate Temp"
    assert telemetry["substrate_temp_c"]["display_unit"] == "°F"
    assert telemetry["substrate_temp_c"]["source_unit"] == "degC"
    assert telemetry["substrate_temp_c"]["latest_reading"] == {
        "value": 69.8,
        "source_value": 21.0,
        "source_unit": "degC",
        "display_unit": "°F",
        "device_id": "plant-a-substrate-node",
        "capability_id": "substrate-temp",
        "source_updated_at": "2026-05-05T03:44:00Z",
        "received_at": "2026-05-05T03:45:00Z",
        "stale_after_s": 600,
    }
    assert telemetry["substrate_ec_us_cm"]["display_unit"] == "mS/cm"
    assert telemetry["substrate_ec_us_cm"]["source_unit"] == "us/cm"
    assert telemetry["substrate_ec_us_cm"]["latest_reading"]["value"] == 1.234
    assert telemetry["substrate_ec_us_cm"]["latest_reading"]["source_value"] == 1234.0
    assert telemetry["substrate_ph"]["latest_reading"]["value"] == 6.4


async def test_browser_plant_metric_history_uses_mapped_streams_and_conversions(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _plant("a", display_order=1),
                _plant("b", display_order=2),
                _plant("c", display_order=3),
                _plant_location("a", grid_position="A1"),
                _plant_location("b", grid_position="B1"),
                _plant_location("c", grid_position="C1"),
            ]
        )
        session.add_all(
            [
                _plant_stream(
                    "a",
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    display_order=1,
                ),
                _plant_stream(
                    "a",
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-ec",
                    metric="substrate_ec_us_cm",
                    display_order=2,
                ),
                _plant_stream(
                    "a",
                    device_id="plant-a-raw-node",
                    capability_id="soil_moisture_raw",
                    metric="soil_moisture_raw",
                    display_order=3,
                ),
                _plant_stream(
                    "b",
                    device_id="plant-b-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    display_order=1,
                ),
            ]
        )
        session.add_all(
            [
                _rollup(
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    min_value=20.0,
                    avg=21.0,
                    max_value=22.0,
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    unit="degC",
                ),
                _rollup(
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=3),
                    min_value=1100.0,
                    avg=1200.0,
                    max_value=1300.0,
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-ec",
                    metric="substrate_ec_us_cm",
                    unit="us/cm",
                ),
                _rollup(
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=1.0,
                    device_id="plant-b-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    unit="degC",
                ),
                _rollup(
                    bucket="4h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=99.0,
                    device_id="plant-a-substrate-node",
                    capability_id="substrate-temp",
                    metric="substrate_temp_c",
                    unit="degC",
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get(
        "/api/tents/main/plants/SBBS-R1-001/metrics/history?range=24h"
    )
    empty = await authed_client.get(
        "/api/tents/main/plants/SBBS-R1-003/metrics/history?range=24h"
    )
    invalid = await authed_client.get(
        "/api/tents/main/plants/SBBS-R1-001/metrics/history?range=180d"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["range"] == "24h"
    assert body["bucket"] == "1h"
    streams = {stream["metric"]: stream for stream in body["streams"]}
    assert list(streams) == ["substrate_temp_c", "substrate_ec_us_cm"]
    assert streams["substrate_temp_c"]["points"] == [
        {
            "bucket": "1h",
            "bucket_start_at": "2026-05-05T01:45:00Z",
            "bucket_end_at": "2026-05-05T01:50:00Z",
            "min": 68.0,
            "avg": 69.8,
            "max": 71.6,
            "source_min": 20.0,
            "source_avg": 21.0,
            "source_max": 22.0,
            "sample_count": 1,
            "source_unit": "degC",
            "display_unit": "°F",
        }
    ]
    assert streams["substrate_ec_us_cm"]["points"][0]["min"] == 1.1
    assert streams["substrate_ec_us_cm"]["points"][0]["avg"] == 1.2
    assert streams["substrate_ec_us_cm"]["points"][0]["max"] == 1.3
    assert streams["substrate_ec_us_cm"]["points"][0]["source_avg"] == 1200.0
    assert streams["substrate_ec_us_cm"]["points"][0]["display_unit"] == "mS/cm"
    assert empty.status_code == 200
    assert empty.json()["streams"] == []
    assert invalid.status_code == 400


async def test_browser_plant_moisture_history_routes_are_removed(
    authed_client: AsyncClient,
) -> None:
    detail_history = await authed_client.get(
        "/api/tents/main/plants/SBBS-R1-001/moisture/history?range=24h"
    )
    comparison_history = await authed_client.get(
        "/api/tents/main/plants/moisture/history?range=24h"
    )

    assert detail_history.status_code == 404
    assert comparison_history.status_code == 404


async def test_metric_history_uses_canonical_metrics_and_dehumidifier_runtime(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _rollup(
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=44.0,
                    metric="fan_pct",
                    capability_id="fan_pct",
                    unit="%",
                ),
                _rollup(
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
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    avg=70.0,
                    metric="heater_intensity_pct",
                    capability_id="heat_level",
                    unit="%",
                ),
                _rollup(
                    bucket="1h",
                    start=FIXED_NOW - timedelta(hours=2),
                    min_value=0.0,
                    avg=65.0,
                    max_value=100.0,
                    metric="dehumidifier_runtime_pct",
                    capability_id="power",
                    unit="%",
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
        "/api/tents/main/metrics/history?range=24h&metric=dehumidifier_runtime_pct"
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
    assert dehumidifier.json()["metric"] == "dehumidifier_runtime_pct"
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
    assert event.subject_id == "site=homebox;tent=main;device=env-main"
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
        credential = (
            await session.execute(
                select(GatewayCredential).where(
                    GatewayCredential.credential_id == "gateway-main"
                )
            )
        ).scalar_one_or_none()
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
        stale_row = (
            await session.execute(
                select(CloudCommand).where(
                    CloudCommand.command_id == stale.json()["command_id"]
                )
            )
        ).scalar_one_or_none()
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
