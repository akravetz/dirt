from __future__ import annotations

import ast
from datetime import UTC, datetime, time, timedelta
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
    CloudCrossEvent,
    CloudDevice,
    CloudLatestMetric,
    CloudMetricPresentation,
    CloudMetricRollup,
    CloudPlant,
    CloudPlantEvent,
    CloudPlantLine,
    CloudPlantLocation,
    CloudPlantMetricStream,
    CloudPlantNote,
    CloudPlantSexTest,
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
        source_tent_id=1,
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
    source_seed_lot_id: int | None = 1,
    line_source_id: int = 1,
    synced_at: datetime = FIXED_NOW,
) -> CloudPlant:
    _ = display_order
    source_plant_id = _source_plant_id(plant_id)
    return CloudPlant(
        site_id="homebox",
        source_plant_id=source_plant_id,
        line_source_id=line_source_id,
        sex_key="unknown",
        source_seed_lot_id=source_seed_lot_id,
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
    produced_by_cross_event_source_id: int | None = None,
    vendor_name: str | None = None,
    acquired_at: datetime | None = None,
    notes: str | None = None,
) -> CloudSeedLot:
    return CloudSeedLot(
        site_id="homebox",
        source_seed_lot_id=source_seed_lot_id,
        line_source_id=line_source_id,
        sex_type_key=sex_type_key,
        is_purchased=is_purchased,
        vendor_name=(
            (vendor_name if vendor_name is not None else "Unknown vendor")
            if is_purchased
            else None
        ),
        acquired_at=(
            (acquired_at if acquired_at is not None else FIXED_NOW - timedelta(days=60))
            if is_purchased
            else None
        ),
        produced_by_cross_event_source_id=(
            None if is_purchased else produced_by_cross_event_source_id or 42
        ),
        seed_count=seed_count,
        notes=notes,
        synced_at=FIXED_NOW,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _plant_location(
    plant_id: str,
    *,
    grid_position: str | None,
    end_at: datetime | None = None,
    tent_id: str = "main",
    synced_at: datetime = FIXED_NOW,
) -> CloudPlantLocation:
    return CloudPlantLocation(
        site_id="homebox",
        source_location_id=_source_plant_id(plant_id),
        source_plant_id=_source_plant_id(plant_id),
        source_tent_id=_source_tent_id(tent_id),
        grid_position=grid_position,
        start_at=FIXED_NOW - timedelta(days=51),
        end_at=end_at,
        synced_at=synced_at,
        created_at=FIXED_NOW,
        updated_at=synced_at,
    )


def _cross_event(
    source_cross_event_id: int,
    *,
    seed_parent: str,
    pollen_parent: str,
    pollen_parent_is_reversed: bool | None = None,
) -> CloudCrossEvent:
    return CloudCrossEvent(
        site_id="homebox",
        source_cross_event_id=source_cross_event_id,
        resulting_line_source_id=1,
        seed_parent_source_plant_id=_source_plant_id(seed_parent),
        pollen_parent_source_plant_id=_source_plant_id(pollen_parent),
        pollinated_at=FIXED_NOW - timedelta(days=10),
        pollen_parent_is_reversed=pollen_parent_is_reversed,
        notes=None,
        synced_at=FIXED_NOW,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _plant_note(
    source_note_id: int,
    *,
    plant_id: str,
    body: str,
    observed_at: datetime,
) -> CloudPlantNote:
    return CloudPlantNote(
        site_id="homebox",
        source_note_id=source_note_id,
        source_plant_id=_source_plant_id(plant_id),
        observed_at=observed_at,
        body=body,
        created_by="test",
        synced_at=FIXED_NOW,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _plant_event(
    source_event_id: int,
    *,
    plant_id: str,
    occurred_at: datetime,
    is_seed_production: bool = False,
    is_clone_taken: bool = False,
    is_sex_observation: bool = False,
    is_transplant: bool = False,
    is_selection_for_breeding: bool = False,
    reason: str | None = None,
    notes: str | None = None,
) -> CloudPlantEvent:
    return CloudPlantEvent(
        site_id="homebox",
        source_event_id=source_event_id,
        source_plant_id=_source_plant_id(plant_id),
        is_pollen_collection=False,
        is_seed_production=is_seed_production,
        is_clone_taken=is_clone_taken,
        is_sex_observation=is_sex_observation,
        is_reversal=False,
        is_transplant=is_transplant,
        is_selection_for_breeding=is_selection_for_breeding,
        occurred_at=occurred_at,
        reason=reason,
        notes=notes,
        metadata_json={},
        synced_at=FIXED_NOW,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
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


def _plant_sex_test(
    source_sex_test_id: int,
    *,
    plant_id: str,
    vendor_test_code: str,
    sample_collected_at: datetime = FIXED_NOW - timedelta(days=1),
    result_received_at: datetime | None = None,
    result_sex_key: str | None = None,
    is_inconclusive: bool = False,
    notes: str | None = None,
) -> CloudPlantSexTest:
    return CloudPlantSexTest(
        site_id="homebox",
        source_sex_test_id=source_sex_test_id,
        source_plant_id=_source_plant_id(plant_id),
        vendor_name="Farmer Freeman",
        assay_name="EZ-XY",
        vendor_test_code=vendor_test_code,
        sample_collected_at=sample_collected_at,
        sample_sent_at=None,
        result_received_at=result_received_at,
        result_sex_key=result_sex_key,
        is_inconclusive=is_inconclusive,
        notes=notes,
        synced_at=FIXED_NOW,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _plant_key(plant_id: str) -> str:
    return f"SBBS-R1-00{_source_plant_id(plant_id)}"


def _source_plant_id(plant_id: str) -> int:
    return ord(plant_id) - ord("a") + 1


def _source_tent_id(tent_id: str) -> int:
    return {"main": 1, "breeding": 2, "clones": 3}[tent_id]


def _tent(tent_id: str, name: str) -> CloudTent:
    return CloudTent(
        site_id="homebox",
        source_tent_id=_source_tent_id(tent_id),
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
        source_tent_id=1,
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
        clock=lambda: FIXED_NOW,
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
        clock=lambda: FIXED_NOW,
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


async def test_browser_tents_ignore_legacy_rows_without_source_tent_id(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(
            CloudTent(
                site_id="homebox",
                source_tent_id=None,
                name="Legacy Main Tent",
                is_active=True,
                synced_at=FIXED_NOW,
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        session.add(
            CloudTent(
                site_id="homebox",
                source_site_id=1,
                source_tent_id=1,
                name="Main Tent",
                role="flower",
                is_active=True,
                synced_at=FIXED_NOW,
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        await session.commit()

    response = await authed_client.get("/api/tents")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["source_tent_id"] == 1
    assert rows[0]["name"] == "Main Tent"


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
        "site_id": "homebox",
        "site": {"source_site_id": 1, "name": "Home Box"},
        "tents": [
            {
                "source_tent_id": 1,
                "name": "Main",
                "role": "flower",
            }
        ],
        "zones": [
            {
                "source_tent_id": 1,
                "source_zone_id": 10,
                "name": "Canopy",
            }
        ],
        "devices": [
            {
                "source_tent_id": 1,
                "source_zone_id": 10,
                "device_id": "env-main",
                "name": "Env Main",
                "last_seen_at": None,
            },
            {
                "source_tent_id": 1,
                "source_zone_id": 10,
                "device_id": "env-backup",
                "name": "Env Backup",
                "last_seen_at": None,
            },
        ],
        "capabilities": [
            {
                "source_tent_id": 1,
                "device_id": "env-main",
                "capability_id": "env-main-temp",
                "metric_name": "temperature_f",
                "unit": "f",
            },
            {
                "source_tent_id": 1,
                "device_id": "env-backup",
                "capability_id": "env-main-temp",
                "metric_name": "temperature_f",
                "unit": "f",
            },
        ],
        "schedules": [
            {
                "source_site_id": 1,
                "source_tent_id": 1,
                "source_zone_id": 10,
                "source_schedule_id": 100,
                "device_id": "env-main",
                "capability_id": "env-main-temp",
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
                "taken_at": None,
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
                "taken_at": None,
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
        "sex_tests": [
            {
                "source_sex_test_id": 1000,
                "source_plant_id": 1,
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "vendor_test_code": "FF-001",
                "sample_collected_at": "2026-07-01T12:00:00Z",
                "sample_sent_at": None,
                "result_received_at": None,
                "result_sex_key": None,
                "is_inconclusive": False,
                "notes": None,
            }
        ],
        "plant_locations": [
            {
                "source_location_id": 1,
                "source_plant_id": 1,
                "source_tent_id": 1,
                "grid_position": "A1",
                "start_at": "2026-03-15T12:00:00Z",
                "end_at": None,
            },
            {
                "source_location_id": 2,
                "source_plant_id": 2,
                "source_tent_id": 1,
                "grid_position": None,
                "start_at": "2026-03-15T12:00:00Z",
                "end_at": None,
            },
        ],
        "cross_events": [
            {
                "source_cross_event_id": 10,
                "resulting_line_source_id": 1,
                "seed_parent_source_plant_id": 1,
                "pollen_parent_source_plant_id": 2,
                "pollinated_at": "2026-04-20T12:00:00Z",
                "pollen_parent_is_reversed": None,
                "notes": None,
            }
        ],
        "plant_notes": [
            {
                "source_note_id": 20,
                "source_plant_id": 1,
                "observed_at": "2026-04-21T12:00:00Z",
                "body": "Branching improved.",
                "created_by": None,
            }
        ],
        "plant_events": [
            {
                "source_event_id": 30,
                "source_plant_id": 1,
                "is_pollen_collection": False,
                "is_seed_production": False,
                "is_clone_taken": False,
                "is_sex_observation": True,
                "is_reversal": False,
                "is_transplant": False,
                "is_selection_for_breeding": False,
                "occurred_at": "2026-04-22T12:00:00Z",
                "reason": None,
                "notes": None,
                "metadata": {"sex_key": "female"},
            }
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
    assert first.json()["sex_tests"] == 1
    assert first.json()["plant_locations"] == 2
    assert first.json()["cross_events"] == 1
    assert first.json()["plant_notes"] == 1
    assert first.json()["plant_events"] == 1
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
        sex_test_count = await session.scalar(
            select(func.count()).select_from(CloudPlantSexTest)
        )
        location_count = await session.scalar(
            select(func.count()).select_from(CloudPlantLocation)
        )
        cross_event_count = await session.scalar(
            select(func.count()).select_from(CloudCrossEvent)
        )
        note_count = await session.scalar(
            select(func.count()).select_from(CloudPlantNote)
        )
        event_count = await session.scalar(
            select(func.count()).select_from(CloudPlantEvent)
        )
        stream_count = await session.scalar(
            select(func.count()).select_from(CloudPlantMetricStream)
        )
        tent = (
            await session.execute(
                select(CloudTent).where(
                    CloudTent.site_id == "homebox",
                    CloudTent.source_tent_id == 1,
                )
            )
        ).scalar_one_or_none()
        zone = (
            await session.execute(
                select(CloudZone).where(
                    CloudZone.site_id == "homebox",
                    CloudZone.source_zone_id == 10,
                )
            )
        ).scalar_one_or_none()
        schedule = (
            await session.execute(
                select(CloudSchedule).where(
                    CloudSchedule.site_id == "homebox",
                    CloudSchedule.source_schedule_id == 100,
                )
            )
        ).scalar_one_or_none()
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
        sex_test = (
            await session.execute(
                select(CloudPlantSexTest).where(
                    CloudPlantSexTest.site_id == "homebox",
                    CloudPlantSexTest.source_sex_test_id == 1000,
                )
            )
        ).scalar_one_or_none()
        plant_a_location = (
            await session.execute(
                select(CloudPlantLocation).where(
                    CloudPlantLocation.site_id == "homebox",
                    CloudPlantLocation.source_plant_id == 1,
                    CloudPlantLocation.source_tent_id == 1,
                    CloudPlantLocation.grid_position == "A1",
                )
            )
        ).scalar_one_or_none()
        plant_b_location = (
            await session.execute(
                select(CloudPlantLocation).where(
                    CloudPlantLocation.site_id == "homebox",
                    CloudPlantLocation.source_plant_id == 2,
                    CloudPlantLocation.source_tent_id == 1,
                    CloudPlantLocation.grid_position.is_(None),
                )
            )
        ).scalar_one_or_none()
        cross_event = (
            await session.execute(
                select(CloudCrossEvent).where(
                    CloudCrossEvent.site_id == "homebox",
                    CloudCrossEvent.source_cross_event_id == 10,
                )
            )
        ).scalar_one_or_none()
        note = (
            await session.execute(
                select(CloudPlantNote).where(
                    CloudPlantNote.site_id == "homebox",
                    CloudPlantNote.source_note_id == 20,
                )
            )
        ).scalar_one_or_none()
        event = (
            await session.execute(
                select(CloudPlantEvent).where(
                    CloudPlantEvent.site_id == "homebox",
                    CloudPlantEvent.source_event_id == 30,
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
    assert sex_test_count == 1
    assert location_count == 2
    assert cross_event_count == 1
    assert note_count == 1
    assert event_count == 1
    assert stream_count == 1
    assert tent is not None
    assert tent.source_tent_id == 1
    assert tent.role == "flower"
    assert zone is not None
    assert zone.source_tent_id == 1
    assert zone.source_zone_id == 10
    assert schedule is not None
    assert schedule.source_tent_id == 1
    assert schedule.source_zone_id == 10
    assert schedule.source_schedule_id == 100
    assert plant_a is not None
    assert plant_a.key == "SBBS-R1-001"
    assert plant_a.line_source_id == 1
    assert plant_a.sex_key == "female"
    assert seed_lot is not None
    assert seed_lot.sex_type_key == "feminized"
    assert sex_test is not None
    assert sex_test.source_plant_id == 1
    assert sex_test.vendor_name == "Farmer Freeman"
    assert sex_test.assay_name == "EZ-XY"
    assert sex_test.vendor_test_code == "FF-001"
    assert sex_test.result_received_at is None
    assert sex_test.result_sex_key is None
    assert sex_test.is_inconclusive is False
    assert sex_test.notes is None
    assert plant_a_location is not None
    assert plant_b_location is not None
    assert plant_b_location.grid_position is None
    assert cross_event is not None
    assert cross_event.pollen_parent_is_reversed is None
    assert cross_event.notes is None
    assert note is not None
    assert note.body == "Branching improved."
    assert note.created_by is None
    assert event is not None
    assert event.is_sex_observation is True
    assert event.reason is None
    assert event.notes is None
    assert event.metadata_json == {"sex_key": "female"}
    assert plant_a_stream is not None
    assert plant_a_stream.display_order == 1
    assert plant_a_stream.is_active is True


async def test_catalog_snapshot_deactivates_omitted_plant_metric_streams(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    catalog = {
        "site_id": "homebox",
        "site": {"source_site_id": 1, "name": "Home Box"},
        "sex_tests": [],
        "plant_metric_streams": [
            {
                "source_plant_id": 42,
                "device_id": "substrate-node",
                "capability_id": "soil_moisture_pct",
                "metric": "soil_moisture_pct",
                "display_order": 1,
                "is_active": True,
            }
        ],
    }
    first = await client.put(
        "/api/gateway/v1/catalog",
        json=catalog,
        headers=gateway_headers,
    )
    catalog["plant_metric_streams"] = []
    second = await client.put(
        "/api/gateway/v1/catalog",
        json=catalog,
        headers=gateway_headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    async with create_sessionmaker(cloud_engine)() as session:
        stream = (
            await session.execute(
                select(CloudPlantMetricStream).where(
                    CloudPlantMetricStream.site_id == "homebox",
                    CloudPlantMetricStream.source_plant_id == 42,
                    CloudPlantMetricStream.device_id == "substrate-node",
                    CloudPlantMetricStream.capability_id == "soil_moisture_pct",
                    CloudPlantMetricStream.metric == "soil_moisture_pct",
                )
            )
        ).scalar_one()
    assert stream.is_active is False


async def test_catalog_upsert_persists_source_scope_ids(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    response = await client.put(
        "/api/gateway/v1/catalog",
        headers=gateway_headers,
        json={
            "site_id": "homebox",
            "site": {"source_site_id": 1, "name": "Home Box"},
            "tents": [
                {"source_tent_id": 1, "name": "Main", "role": "flower"},
            ],
            "zones": [
                {
                    "source_tent_id": 1,
                    "source_zone_id": 10,
                    "name": "Canopy",
                }
            ],
            "schedules": [
                {
                    "source_site_id": 1,
                    "source_tent_id": 1,
                    "source_zone_id": 10,
                    "source_schedule_id": 100,
                    "kind": "lights",
                    "starts_local": "09:00:00",
                    "ends_local": "21:00:00",
                    "timezone": "America/Denver",
                    "is_enabled": True,
                }
            ],
            "sex_tests": [],
        },
    )

    assert response.status_code == 200
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        tent = (
            await session.execute(
                select(CloudTent).where(CloudTent.source_tent_id == 1)
            )
        ).scalar_one()
        zone = (
            await session.execute(
                select(CloudZone).where(CloudZone.source_zone_id == 10)
            )
        ).scalar_one()
        schedule = (
            await session.execute(
                select(CloudSchedule).where(CloudSchedule.source_schedule_id == 100)
            )
        ).scalar_one()

    assert tent.source_tent_id == 1
    assert zone.source_tent_id == 1
    assert zone.source_zone_id == 10
    assert schedule.source_tent_id == 1
    assert schedule.source_zone_id == 10
    assert schedule.source_schedule_id == 100


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
        "site_id": "homebox",
        "site": {"source_site_id": 1, "name": "Home Box"},
        "tents": [
            {
                "source_tent_id": 2,
                "name": "Breeding",
                "role": "breeding",
            }
        ],
        "zones": [
            {
                "source_tent_id": 2,
                "source_zone_id": 20,
                "name": "Canopy",
            },
            {
                "source_tent_id": 2,
                "source_zone_id": 21,
                "name": "Lights",
            },
        ],
        "devices": [
            {
                "source_tent_id": 2,
                "source_zone_id": 20,
                "device_id": "obsbot-breeding",
                "name": "Breeding Camera",
                "kind": "camera",
                "last_seen_at": FIXED_NOW.isoformat(),
            }
        ],
        "schedules": [
            {
                "source_site_id": 1,
                "source_tent_id": 2,
                "source_zone_id": 21,
                "source_schedule_id": 200,
                "kind": "lights",
                "starts_local": "06:00:00",
                "ends_local": "18:00:00",
                "timezone": "America/Denver",
                "is_enabled": True,
            }
        ],
        "sex_tests": [],
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
        "source_site_id": 1,
        "source_tent_id": 2,
        "tent_name": "Breeding",
        "camera_device_id": "obsbot-breeding",
        "enabled": True,
        "require_lights_on": True,
        "lights_on_local": "06:00:00",
        "lights_off_local": "18:00:00",
        "timezone": "America/Denver",
        "source_schedule_id": 200,
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
                source_tent_id=2,
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
                source_tent_id=2,
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
    assert "tent_id" not in missing_camera.json()
    assert missing_camera.json()["enabled"] is True
    assert missing_camera.json()["require_lights_on"] is False
    assert missing_camera.json()["reason"] == "camera_not_found"
    assert missing_schedule.status_code == 200
    assert "tent_id" not in missing_schedule.json()
    assert missing_schedule.json()["enabled"] is True
    assert missing_schedule.json()["require_lights_on"] is False
    assert missing_schedule.json()["reason"] == "lights_schedule_not_found"
    assert disabled.status_code == 200
    assert "tent_id" not in disabled.json()
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
                "source_site_id": 1,
                "source_tent_id": 1,
                "source_zone_id": None,
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
                "source_site_id": 1,
                "source_tent_id": 1,
                "source_zone_id": None,
                "device_id": "plant-a-node",
                "capability_id": "soil_moisture_raw",
                "metric": "soil_moisture_raw",
                "value": 1800.0,
                "unit": "raw",
                "source_updated_at": "2026-05-05T03:44:00Z",
            },
            {
                "site_id": "homebox",
                "source_site_id": 1,
                "source_tent_id": 1,
                "source_zone_id": None,
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
                "source_site_id": 1,
                "source_tent_id": 1,
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
                "source_site_id": 1,
                "source_tent_id": 1,
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
                "source_site_id": 1,
                "source_tent_id": 1,
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
                    source_tent_id=1,
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
                    source_tent_id=1,
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
                    source_tent_id=1,
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
                    source_tent_id=1,
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

    response = await authed_client.get("/api/tents/1/metrics/current")

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

    response = await authed_client.get("/api/tents/1/metrics/presentation")

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
                    source_tent_id=1,
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
                    source_tent_id=1,
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

    response = await authed_client.get("/api/tents/1/metrics/current")

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
        "/api/tents/1/metrics/history?range=1h&metric=temperature_f"
    )
    one_day = await authed_client.get(
        "/api/tents/1/metrics/history?range=24h&metric=temperature_f"
    )
    seven_days = await authed_client.get(
        "/api/tents/1/metrics/history?range=7d&metric=temperature_f"
    )
    thirty_days = await authed_client.get(
        "/api/tents/1/metrics/history?range=30d&metric=temperature_f"
    )
    ninety_days = await authed_client.get(
        "/api/tents/1/metrics/history?range=90d&metric=temperature_f"
    )
    invalid = await authed_client.get(
        "/api/tents/1/metrics/history?range=180d&metric=temperature_f"
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


async def test_browser_tent_routes_scope_schedules_and_latest_assets_by_path_tent(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _tent("main", "Main Tent"),
                _tent("breeding", "Breeding Tent"),
                CloudSchedule(
                    site_id="homebox",
                    source_tent_id=1,
                    source_zone_id=8,
                    source_schedule_id=1,
                    device_id="kasa-lights-main",
                    capability_id="power",
                    kind="lights",
                    starts_local=time(9, 0),
                    ends_local=time(21, 0),
                    timezone="America/Denver",
                    is_enabled=True,
                    synced_at=FIXED_NOW,
                    created_at=FIXED_NOW,
                    updated_at=FIXED_NOW,
                ),
                CloudSchedule(
                    site_id="homebox",
                    source_tent_id=2,
                    source_zone_id=11,
                    source_schedule_id=2,
                    device_id="kasa-lights-breeding",
                    capability_id="power",
                    kind="lights",
                    starts_local=time(6, 0),
                    ends_local=time(18, 0),
                    timezone="America/Denver",
                    is_enabled=True,
                    synced_at=FIXED_NOW,
                    created_at=FIXED_NOW,
                    updated_at=FIXED_NOW,
                ),
                CloudAsset(
                    asset_id="main-latest",
                    site_id="homebox",
                    source_tent_id=1,
                    object_key="homebox/main/snapshots/latest.jpg",
                    content_type="image/jpeg",
                    byte_size=10,
                    captured_at=FIXED_NOW,
                    uploaded_at=FIXED_NOW,
                ),
                CloudAsset(
                    asset_id="breeding-latest",
                    site_id="homebox",
                    source_tent_id=2,
                    object_key="homebox/breeding/snapshots/latest.jpg",
                    content_type="image/jpeg",
                    byte_size=11,
                    captured_at=FIXED_NOW + timedelta(minutes=1),
                    uploaded_at=FIXED_NOW + timedelta(minutes=1),
                ),
            ]
        )
        await session.commit()

    schedules = await authed_client.get("/api/tents/1/lights/schedules")
    assets = await authed_client.get("/api/tents/2/assets/latest")

    assert schedules.status_code == 200
    schedule_body = schedules.json()
    assert schedule_body["site_id"] == "homebox"
    assert schedule_body["source_tent_id"] == 1
    assert schedule_body["tent_name"] == "Main Tent"
    assert len(schedule_body["schedules"]) == 1
    schedule = schedule_body["schedules"][0]
    assert schedule["site_id"] == "homebox"
    assert schedule["source_tent_id"] == 1
    assert schedule["tent_name"] == "Main Tent"
    assert schedule["source_zone_id"] == 8
    assert schedule["device_id"] == "kasa-lights-main"
    assert schedule["capability_id"] == "power"
    assert schedule["source_schedule_id"] == 1
    assert schedule["kind"] == "lights"
    assert schedule["enabled"] is True
    assert schedule["timezone"] == "America/Denver"
    assert schedule["starts_local"] == "09:00:00"
    assert schedule["ends_local"] == "21:00:00"
    assert schedule["duration_hours"] == 12.0
    assert {"is_on", "minutes_until_off", "minutes_until_on"} <= set(schedule)

    assert assets.status_code == 200
    asset_body = assets.json()
    assert [asset["asset_id"] for asset in asset_body] == ["breeding-latest"]
    assert asset_body[0]["kind"] == "snapshot"
    assert asset_body[0]["content_type"] == "image/jpeg"
    assert asset_body[0]["signed_url"].startswith("https://assets.test/")


async def test_cloud_asset_source_scope_supports_latest_asset_reads(
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                CloudAsset(
                    asset_id="main-before-rename",
                    site_id="homebox",
                    source_tent_id=1,
                    source_zone_id=10,
                    object_key="homebox/main/snapshots/before.jpg",
                    content_type="image/jpeg",
                    byte_size=10,
                    captured_at=FIXED_NOW,
                    uploaded_at=FIXED_NOW,
                ),
                CloudAsset(
                    asset_id="main-after-rename",
                    site_id="homebox",
                    source_tent_id=1,
                    source_zone_id=10,
                    object_key="homebox/flower/snapshots/after.jpg",
                    content_type="image/jpeg",
                    byte_size=11,
                    captured_at=FIXED_NOW + timedelta(minutes=1),
                    uploaded_at=FIXED_NOW + timedelta(minutes=1),
                ),
                CloudAsset(
                    asset_id="breeding-latest",
                    site_id="homebox",
                    source_tent_id=2,
                    source_zone_id=20,
                    object_key="homebox/breeding/snapshots/latest.jpg",
                    content_type="image/jpeg",
                    byte_size=12,
                    captured_at=FIXED_NOW + timedelta(minutes=2),
                    uploaded_at=FIXED_NOW + timedelta(minutes=2),
                ),
            ]
        )
        await session.commit()

    async with sessionmaker() as session:
        tent_rows = (
            (
                await session.execute(
                    select(CloudAsset)
                    .where(
                        CloudAsset.site_id == "homebox",
                        CloudAsset.source_tent_id == 1,
                    )
                    .order_by(CloudAsset.captured_at.desc())
                )
            )
            .scalars()
            .all()
        )
        zone_rows = (
            (
                await session.execute(
                    select(CloudAsset)
                    .where(
                        CloudAsset.site_id == "homebox",
                        CloudAsset.source_zone_id == 10,
                    )
                    .order_by(CloudAsset.captured_at.desc())
                )
            )
            .scalars()
            .all()
        )

    assert [row.asset_id for row in tent_rows] == [
        "main-after-rename",
        "main-before-rename",
    ]
    assert [row.asset_id for row in zone_rows] == [
        "main-after-rename",
        "main-before-rename",
    ]


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
        "/api/tents/1/metrics/history"
        "?range=24h&metric=soil_moisture_raw"
        "&device_id=plant-a-node&capability_id=soil_moisture_raw"
    )
    invalid = await authed_client.get(
        "/api/tents/1/metrics/history"
        "?range=24h&metric=soil_moisture_raw&device_id=plant-a-node"
    )

    assert response.status_code == 200
    assert [point["avg"] for point in response.json()["points"]] == [1800.0]
    assert invalid.status_code == 400


async def test_browser_plants_require_auth(client: AsyncClient) -> None:
    response = await client.get("/api/tents/1/plants")

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
            "source_tent_id": 1,
            "display_name": "Main flower",
            "role": None,
            "grid_position": None,
        },
        {
            "source_tent_id": 2,
            "display_name": "Breeding tent",
            "role": None,
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
                _plant_location(
                    "b",
                    grid_position="B1",
                    end_at=FIXED_NOW - timedelta(days=1),
                ),
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
        "strain": "Sirius Black x BS01",
        "generation": "R1",
        "parents_label": "Sirius Black x BS01 x R1",
        "sex_key": "unknown",
        "stage_key": "germinating",
        "stage_day": 51,
        "is_clone": False,
        "germinated_at": "2026-03-15T03:45:00Z",
        "germinated_on": "2026-03-15",
        "taken_at": None,
        "taken_on": None,
        "rooted_at": None,
        "rooted_on": None,
        "veg_started_at": None,
        "veg_started_on": None,
        "flower_started_at": None,
        "flower_started_on": None,
        "culled_at": None,
        "culled_on": None,
        "culled_reason": None,
        "harvested_at": None,
        "harvested_on": None,
        "selected_for_breeding_at": None,
        "selected_for_breeding_on": None,
        "selected_for_breeding_reason": None,
        "current_tent_id": 1,
        "current_tent_name": "Tent 1",
        "grid_position": "A1",
        "seed_lot_label": "SBBS R1 #1",
        "last_note": "",
        "telemetry_summary": "1 plant stream",
        "sex_tests": [],
    }
    assert with_culled.status_code == 200
    assert with_culled.json()["culled_count"] == 1
    assert [row["key"] for row in with_culled.json()["plants"]] == [
        "SBBS-R1-001",
        "SBBS-R1-002",
    ]


async def test_breeding_logbook_plant_list_handles_timeline_note_fallbacks(
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
                _plant("b", display_order=2),
                _plant("c", display_order=3, is_active=False),
                _plant_location("a", grid_position=None),
                _plant_location("b", grid_position="B1"),
                _plant_location("c", grid_position="C1"),
                _plant_event(
                    10,
                    plant_id="a",
                    occurred_at=FIXED_NOW - timedelta(hours=1),
                    is_sex_observation=True,
                    reason="Confirmed female",
                ),
                _plant_note(
                    11,
                    plant_id="a",
                    observed_at=FIXED_NOW - timedelta(hours=2),
                    body="Latest canopy note",
                ),
                _plant_event(
                    12,
                    plant_id="b",
                    occurred_at=FIXED_NOW - timedelta(hours=1),
                    is_transplant=True,
                    notes="Moved into flower",
                ),
            ]
        )
        await session.commit()

    response = await authed_client.get(
        "/api/breeding-logbook/plants?include_culled=true&group_by=stage"
    )

    assert response.status_code == 200
    plants = {plant["key"]: plant for plant in response.json()["plants"]}
    assert plants["SBBS-R1-001"]["current_tent_id"] == 1
    assert plants["SBBS-R1-001"]["current_tent_name"] == "Tent 1"
    assert plants["SBBS-R1-001"]["grid_position"] is None
    assert plants["SBBS-R1-001"]["last_note"] == "Latest canopy note"
    assert plants["SBBS-R1-002"]["last_note"] == "Moved into flower"
    assert plants["SBBS-R1-003"]["last_note"] == "test fixture"


async def test_breeding_logbook_plants_include_sorted_sex_tests(
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
                _plant("b", display_order=2),
                _plant_location("a", grid_position="A1"),
                _plant_location("b", grid_position="B1"),
                _plant_sex_test(
                    1000,
                    plant_id="a",
                    vendor_test_code="FF-PENDING-OLD",
                    sample_collected_at=FIXED_NOW - timedelta(days=4),
                    notes="First sample.",
                ),
                _plant_sex_test(
                    1001,
                    plant_id="a",
                    vendor_test_code="FF-RESULT",
                    sample_collected_at=FIXED_NOW - timedelta(days=5),
                    result_received_at=FIXED_NOW - timedelta(days=1),
                    result_sex_key="female",
                ),
                _plant_sex_test(
                    1002,
                    plant_id="a",
                    vendor_test_code="FF-PENDING-NEW",
                    sample_collected_at=FIXED_NOW - timedelta(days=2),
                ),
                _plant_sex_test(
                    2000,
                    plant_id="b",
                    vendor_test_code="FF-B",
                    sample_collected_at=FIXED_NOW - timedelta(days=1),
                ),
            ]
        )
        await session.commit()

    listed = await authed_client.get("/api/breeding-logbook/plants")
    detail = await authed_client.get("/api/breeding-logbook/plants/SBBS-R1-001")

    assert listed.status_code == 200
    plant_a = {plant["key"]: plant for plant in listed.json()["plants"]}["SBBS-R1-001"]
    assert [sex_test["source_sex_test_id"] for sex_test in plant_a["sex_tests"]] == [
        1002,
        1000,
        1001,
    ]
    assert plant_a["sex_tests"][0] == {
        "id": "1002",
        "source_sex_test_id": 1002,
        "source_plant_id": 1,
        "vendor_name": "Farmer Freeman",
        "assay_name": "EZ-XY",
        "vendor_test_code": "FF-PENDING-NEW",
        "sample_collected_at": "2026-05-03T03:45:00Z",
        "sample_sent_at": None,
        "result_received_at": None,
        "result_sex_key": None,
        "is_inconclusive": False,
        "notes": None,
    }
    assert detail.status_code == 200
    assert detail.json()["plant"]["sex_tests"] == plant_a["sex_tests"]


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
            "strain": "Sirius Black x BS01",
            "cultivar": "R1",
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
            "strain": "Sirius Black x BS01",
            "cultivar": "R1",
            "generation": "R1",
            "source": "cross",
            "source_label": "in-house cross",
            "parents_label": "Sirius Black x BS01 x R1",
            "sex_type_key": "regular",
            "seed_count": None,
        },
    ]


async def test_breeding_logbook_seed_lot_detail_includes_inventory_and_source_context(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(_plant_line())
        session.add_all(
            [
                _seed_lot(
                    1,
                    vendor_name="Archive",
                    notes="Stored cold.",
                ),
                _seed_lot(
                    2,
                    sex_type_key="regular",
                    is_purchased=False,
                    seed_count=18,
                    produced_by_cross_event_source_id=42,
                    notes="Lower branch harvest.",
                ),
                _plant("a", display_order=1, source_seed_lot_id=2),
                _plant("b", display_order=2, source_seed_lot_id=None),
                _plant("c", display_order=3, source_seed_lot_id=None),
                _cross_event(
                    42,
                    seed_parent="b",
                    pollen_parent="c",
                    pollen_parent_is_reversed=True,
                ),
            ]
        )
        await session.commit()

    purchased = await authed_client.get("/api/breeding-logbook/seed-lots/1")
    cross = await authed_client.get("/api/breeding-logbook/seed-lots/2")
    missing = await authed_client.get("/api/breeding-logbook/seed-lots/999")

    assert purchased.status_code == 200
    purchased_body = purchased.json()
    assert purchased_body["id"] == "1"
    assert purchased_body["label"] == "SBBS R1 #1"
    assert purchased_body["source_seed_lot_id"] == 1
    assert purchased_body["source"] == "purchased"
    assert purchased_body["vendor_name"] == "Archive"
    assert purchased_body["acquired_at"] == "2026-03-06T03:45:00Z"
    assert purchased_body["notes"] == "Stored cold."
    assert purchased_body["created_plant_count"] == 0
    assert purchased_body["line"] == {
        "source_line_id": 1,
        "prefix": "SBBS",
        "generation": "R1",
        "strain": "Sirius Black x BS01",
        "cultivar": "R1",
        "source_name": "Unknown vendor",
        "description": None,
    }
    assert purchased_body["cross"] is None

    assert cross.status_code == 200
    cross_body = cross.json()
    assert cross_body["id"] == "2"
    assert cross_body["source"] == "cross"
    assert cross_body["vendor_name"] is None
    assert cross_body["acquired_at"] is None
    assert cross_body["seed_count"] == 18
    assert cross_body["notes"] == "Lower branch harvest."
    assert cross_body["created_plant_count"] == 1
    assert cross_body["produced_by_cross_event_source_id"] == 42
    assert cross_body["cross"] == {
        "source_cross_event_id": 42,
        "pollinated_at": "2026-04-25T03:45:00Z",
        "pollen_parent_is_reversed": True,
        "seed_parent_source_plant_id": 2,
        "seed_parent_key": "SBBS-R1-002",
        "seed_parent_name": "Plant B",
        "seed_parent_label": "Plant B (SBBS-R1-002)",
        "pollen_parent_source_plant_id": 3,
        "pollen_parent_key": "SBBS-R1-003",
        "pollen_parent_name": "Plant C",
        "pollen_parent_label": "Plant C (SBBS-R1-003)",
        "parents_label": "Plant B (SBBS-R1-002) x Plant C (SBBS-R1-003) (reversed)",
        "notes": None,
    }
    assert missing.status_code == 404


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
                _seed_lot(
                    2,
                    is_purchased=False,
                    produced_by_cross_event_source_id=42,
                ),
                _seed_lot(
                    3,
                    is_purchased=False,
                    produced_by_cross_event_source_id=43,
                ),
                _plant("a", display_order=1, source_seed_lot_id=2),
                _plant("b", display_order=2),
                _plant("c", display_order=3),
                _plant("d", display_order=4, source_seed_lot_id=3),
                _plant_location("a", grid_position="A1"),
                _cross_event(
                    42,
                    seed_parent="b",
                    pollen_parent="c",
                    pollen_parent_is_reversed=True,
                ),
                _cross_event(43, seed_parent="a", pollen_parent="b"),
                _plant_note(
                    101,
                    plant_id="a",
                    observed_at=FIXED_NOW - timedelta(hours=2),
                    body="Trichomes stacking",
                ),
                _plant_event(
                    201,
                    plant_id="a",
                    occurred_at=FIXED_NOW - timedelta(hours=1),
                    is_sex_observation=True,
                    reason="Confirmed female",
                ),
                _plant_event(
                    202,
                    plant_id="a",
                    occurred_at=FIXED_NOW - timedelta(hours=3),
                    is_seed_production=True,
                    notes="Pollinated lower branch",
                ),
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
    assert detail_body["plant"]["last_note"] == "Trichomes stacking"
    assert detail_body["lineage"] == {
        "parents": ("Plant B (SBBS-R1-002) x Plant C (SBBS-R1-003) (reversed)"),
        "offspring": "Cross #43: SBBS R1 #3 (1 plant)",
    }
    assert detail_body["metrics"] == [
        {"label": "Substrate Temp", "value": "69.8°F", "tone": "ok"}
    ]
    assert [
        (event["id"], event["tag"], event["body"]) for event in detail_body["events"]
    ] == [
        ("event-201", "sex", "Confirmed female"),
        ("note-101", "note", "Trichomes stacking"),
        ("event-202", "cross", "Pollinated lower branch"),
    ]
    assert detail_body["wiki_content"] is None
    assert history.status_code == 200
    assert history.json()["streams"][0]["metric"] == "substrate_temp_c"
    assert history.json()["streams"][0]["points"][0]["avg"] == 69.8
    assert missing.status_code == 404


def _breeding_write_cases() -> list[tuple[str, dict[str, object], dict[str, object]]]:
    return [
        (
            "/api/breeding-logbook/seed-lots",
            {
                "idempotency_key": "create-seed-lot",
                "source": "purchased",
                "generation": "R2",
                "prefix": "SBBS",
                "strain": "Sirius Black x BS01",
                "cultivar": "R2",
                "source_name": "Archive pack",
                "vendor_name": "Archive",
                "acquired_at": None,
                "seed_count": 10,
                "sex_type_key": "feminized",
                "notes": None,
            },
            {
                "source": "purchased",
                "generation": "R2",
                "prefix": "SBBS",
                "strain": "Sirius Black x BS01",
                "cultivar": "R2",
                "source_name": "Archive pack",
                "vendor_name": "Archive",
                "acquired_at": None,
                "seed_parent_plant_key": None,
                "pollen_parent_plant_key": None,
                "pollinated_at": None,
                "pollen_parent_is_reversed": None,
                "seed_count": 10,
                "sex_type_key": "feminized",
                "notes": None,
            },
        ),
        (
            "/api/breeding-logbook/seed-lots/1:update",
            {
                "idempotency_key": "update-seed-lot",
                "seed_lot_source_id": 1,
                "sex_type_key": "regular",
                "seed_count": 9,
                "notes": "Inventory recounted.",
                "vendor_name": "Archive",
                "acquired_at": None,
            },
            {
                "seed_lot_source_id": 1,
                "sex_type_key": "regular",
                "seed_count": 9,
                "notes": "Inventory recounted.",
                "vendor_name": "Archive",
                "acquired_at": None,
            },
        ),
        (
            "/api/breeding-logbook/plants:germinate",
            {
                "idempotency_key": "germinate-plants",
                "seed_lot_id": "1",
                "count": 2,
                "source_tent_id": 2,
                "grid_position": None,
                "germinated_at": None,
            },
            {
                "seed_lot_source_id": 1,
                "count": 2,
                "source_tent_id": 2,
                "grid_position": None,
                "germinated_at": None,
            },
        ),
        (
            "/api/breeding-logbook/plants:clone",
            {
                "idempotency_key": "clone-plants",
                "mother_plant_key": "SBBS-R1-001",
                "count": 2,
                "source_tent_id": 2,
                "grid_position": None,
                "taken_at": None,
            },
            {
                "mother_plant_key": "SBBS-R1-001",
                "count": 2,
                "source_tent_id": 2,
                "grid_position": None,
                "taken_at": None,
            },
        ),
        (
            "/api/breeding-logbook/plants:bulk-sex",
            {
                "idempotency_key": "bulk-sex",
                "plant_keys": ["SBBS-R1-001", "SBBS-R1-002"],
                "sex_key": "female",
            },
            {"plant_keys": ["SBBS-R1-001", "SBBS-R1-002"], "sex_key": "female"},
        ),
        (
            "/api/breeding-logbook/sex-tests:bulk-create",
            {
                "idempotency_key": "bulk-create-sex-tests",
                "vendor_name": " Farmer Freeman ",
                "assay_name": "EZ-XY",
                "sample_collected_at": "2026-06-18T16:00:00Z",
                "sample_sent_at": None,
                "tests": [
                    {
                        "plant_key": "SBBS-R1-001",
                        "vendor_test_code": " FF-001 ",
                        "notes": " fresh cutting ",
                    },
                    {
                        "plant_key": "SBBS-R1-002",
                        "vendor_test_code": "FF-002",
                        "notes": None,
                    },
                ],
            },
            {
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "sample_collected_at": "2026-06-18T16:00:00Z",
                "sample_sent_at": None,
                "tests": [
                    {
                        "plant_key": "SBBS-R1-001",
                        "vendor_test_code": "FF-001",
                        "notes": "fresh cutting",
                    },
                    {
                        "plant_key": "SBBS-R1-002",
                        "vendor_test_code": "FF-002",
                        "notes": None,
                    },
                ],
            },
        ),
        (
            "/api/breeding-logbook/sex-tests/1000:update",
            {
                "idempotency_key": "update-sex-test",
                "sex_test_source_id": 1000,
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "vendor_test_code": "FF-EXISTING",
                "sample_collected_at": "2026-06-17T16:00:00Z",
                "sample_sent_at": None,
                "result_received_at": "2026-06-22T16:00:00Z",
                "result_sex_key": "female",
                "is_inconclusive": False,
                "notes": "Lab result entered.",
            },
            {
                "sex_test_source_id": 1000,
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "vendor_test_code": "FF-EXISTING",
                "sample_collected_at": "2026-06-17T16:00:00Z",
                "sample_sent_at": None,
                "result_received_at": "2026-06-22T16:00:00Z",
                "result_sex_key": "female",
                "is_inconclusive": False,
                "notes": "Lab result entered.",
            },
        ),
        (
            "/api/breeding-logbook/sex-tests:bulk-result",
            {
                "idempotency_key": "bulk-result-sex-tests",
                "result_received_at": "2026-06-22T16:00:00Z",
                "results": [
                    {
                        "sex_test_source_id": 1000,
                        "result_sex_key": "female",
                        "is_inconclusive": False,
                    }
                ],
            },
            {
                "result_received_at": "2026-06-22T16:00:00Z",
                "results": [
                    {
                        "sex_test_source_id": 1000,
                        "result_sex_key": "female",
                        "is_inconclusive": False,
                    }
                ],
            },
        ),
        (
            "/api/breeding-logbook/plants:bulk-move",
            {
                "idempotency_key": "bulk-move",
                "plant_keys": ["SBBS-R1-001", "SBBS-R1-002"],
                "source_tent_id": 2,
                "grid_position": None,
            },
            {
                "plant_keys": ["SBBS-R1-001", "SBBS-R1-002"],
                "source_tent_id": 2,
                "grid_position": None,
            },
        ),
        (
            "/api/breeding-logbook/plants:update-facts",
            {
                "idempotency_key": "update-facts",
                "plant_keys": ["SBBS-R1-001", "SBBS-R1-002"],
                "updates": [
                    {"field": "taken_at", "value": "2026-06-18T16:00:00Z"},
                    {"field": "rooted_at", "value": "2026-06-19T16:00:00Z"},
                    {"field": "veg_started_at", "value": "2026-06-20T16:00:00Z"},
                    {"field": "sex_key", "value": "female"},
                    {"field": "flower_started_at", "value": None},
                ],
            },
            {
                "plant_keys": ["SBBS-R1-001", "SBBS-R1-002"],
                "updates": [
                    {"field": "taken_at", "value": "2026-06-18T16:00:00Z"},
                    {"field": "rooted_at", "value": "2026-06-19T16:00:00Z"},
                    {"field": "veg_started_at", "value": "2026-06-20T16:00:00Z"},
                    {"field": "sex_key", "value": "female"},
                    {"field": "flower_started_at", "value": None},
                ],
            },
        ),
        (
            "/api/breeding-logbook/plants:bulk-cull",
            {
                "idempotency_key": "bulk-cull",
                "plant_keys": ["SBBS-R1-002"],
                "reason": "selected male",
                "culled_at": "2026-06-21T16:00:00Z",
            },
            {
                "plant_keys": ["SBBS-R1-002"],
                "reason": "selected male",
                "culled_at": "2026-06-21T16:00:00Z",
            },
        ),
        (
            "/api/breeding-logbook/plants/SBBS-R1-001/notes",
            {
                "idempotency_key": "plant-note",
                "body": "Stem rub improved.",
                "observed_at": None,
            },
            {
                "plant_key": "SBBS-R1-001",
                "body": "Stem rub improved.",
                "observed_at": None,
            },
        ),
        (
            "/api/breeding-logbook/plants:bulk-note",
            {
                "idempotency_key": "bulk-note",
                "plant_keys": ["SBBS-R1-001", "SBBS-R1-002"],
                "body": "Canopy improved.",
                "observed_at": None,
            },
            {
                "plant_keys": ["SBBS-R1-001", "SBBS-R1-002"],
                "body": "Canopy improved.",
                "observed_at": None,
            },
        ),
    ]


async def _seed_breeding_write_projection(cloud_engine: AsyncEngine) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add_all(
            [
                _tent("breeding", "Breeding tent"),
                _plant_line(),
                _seed_lot(),
                _plant("a", display_order=1),
                _plant("b", display_order=2),
                _plant_sex_test(
                    1000,
                    plant_id="a",
                    vendor_test_code="FF-EXISTING",
                    sample_collected_at=FIXED_NOW - timedelta(days=3),
                ),
            ]
        )
        await session.commit()


async def test_breeding_logbook_write_routes_require_auth(client: AsyncClient) -> None:
    for path, body, _ in _breeding_write_cases():
        response = await client.post(path, json=body)
        assert response.status_code == 401


async def test_breeding_logbook_write_routes_enqueue_typed_commands_idempotently(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    await _seed_breeding_write_projection(cloud_engine)

    for path, body, expected_payload in _breeding_write_cases():
        first = await authed_client.post(path, json=body)
        second = await authed_client.post(path, json=body)

        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json()["command_id"] == first.json()["command_id"]
        first_body = first.json()
        assert first_body["target"] is None
        assert first_body["payload"] == expected_payload
        assert datetime.fromisoformat(first.json()["expires_at"]) == (
            FIXED_NOW + timedelta(seconds=3600)
        )

    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        rows = (
            (
                await session.execute(
                    select(CloudCommand).order_by(CloudCommand.queued_at)
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == len(_breeding_write_cases())
    assert {row.command_type for row in rows} == {
        "breeding_seed_lot_create",
        "breeding_seed_lot_update",
        "breeding_plants_germinate",
        "breeding_plants_clone",
        "breeding_plants_bulk_sex",
        "breeding_sex_tests_bulk_create",
        "breeding_sex_test_update",
        "breeding_sex_tests_bulk_result",
        "breeding_plants_bulk_move",
        "breeding_plants_update_facts",
        "breeding_plants_bulk_cull",
        "breeding_plant_note_create",
        "breeding_plants_bulk_note",
    }
    assert all(row.source_tent_id is None for row in rows)


async def test_breeding_logbook_write_routes_return_503_when_commands_disabled(
    cloud_engine: AsyncEngine,
    settings,
) -> None:
    from dirt_control.app import create_app

    await _seed_breeding_write_projection(cloud_engine)
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
        for path, body, _ in _breeding_write_cases():
            response = await client.post(path, json=body)
            assert response.status_code == 503
    await transport.aclose()


async def test_breeding_logbook_write_routes_reject_obvious_bad_inputs(
    authed_client: AsyncClient,
    cloud_engine: AsyncEngine,
) -> None:
    await _seed_breeding_write_projection(cloud_engine)
    invalid_cases = [
        (
            "/api/breeding-logbook/seed-lots",
            {
                "idempotency_key": "bad-cross",
                "source": "cross",
                "generation": "F1",
                "prefix": "SBX",
                "seed_parent_plant_key": "SBBS-R1-001",
                "pollen_parent_plant_key": "missing",
                "sex_type_key": "regular",
            },
        ),
        (
            "/api/breeding-logbook/plants:germinate",
            {
                "idempotency_key": "bad-germ",
                "seed_lot_id": "missing",
                "count": 1,
                "source_tent_id": 2,
                "grid_position": None,
            },
        ),
        (
            "/api/breeding-logbook/seed-lots/999:update",
            {
                "idempotency_key": "bad-seed-update-missing",
                "seed_lot_source_id": 999,
                "sex_type_key": "regular",
                "seed_count": 9,
                "notes": None,
                "vendor_name": "Archive",
                "acquired_at": None,
            },
        ),
        (
            "/api/breeding-logbook/seed-lots/1:update",
            {
                "idempotency_key": "bad-seed-update-mismatch",
                "seed_lot_source_id": 2,
                "sex_type_key": "regular",
                "seed_count": 9,
                "notes": None,
                "vendor_name": "Archive",
                "acquired_at": None,
            },
        ),
        (
            "/api/breeding-logbook/seed-lots/1:update",
            {
                "idempotency_key": "bad-seed-update-shape",
                "seed_lot_source_id": 1,
                "sex_type_key": "regular",
                "seed_count": -1,
                "notes": None,
                "vendor_name": "Archive",
                "acquired_at": None,
            },
        ),
        (
            "/api/breeding-logbook/plants:germinate",
            {
                "idempotency_key": "bad-germ-grid",
                "seed_lot_id": "1",
                "count": 1,
                "source_tent_id": 2,
                "grid_position": "A1",
            },
        ),
        (
            "/api/breeding-logbook/plants:clone",
            {
                "idempotency_key": "bad-clone",
                "mother_plant_key": "missing",
                "count": 1,
                "source_tent_id": 2,
                "grid_position": None,
            },
        ),
        (
            "/api/breeding-logbook/plants:clone",
            {
                "idempotency_key": "bad-clone-grid",
                "mother_plant_key": "SBBS-R1-001",
                "count": 1,
                "source_tent_id": 2,
                "grid_position": "A1",
            },
        ),
        (
            "/api/breeding-logbook/plants:bulk-sex",
            {
                "idempotency_key": "bad-sex",
                "plant_keys": ["missing"],
                "sex_key": "female",
            },
        ),
        (
            "/api/breeding-logbook/plants:bulk-move",
            {
                "idempotency_key": "bad-move",
                "plant_keys": ["SBBS-R1-001"],
                "source_tent_id": 999,
                "grid_position": None,
            },
        ),
        (
            "/api/breeding-logbook/plants:bulk-move",
            {
                "idempotency_key": "bad-move-grid",
                "plant_keys": ["SBBS-R1-001"],
                "source_tent_id": 2,
                "grid_position": "A1",
            },
        ),
        (
            "/api/breeding-logbook/plants:update-facts",
            {
                "idempotency_key": "bad-update-facts-plant",
                "plant_keys": ["SBBS-R1-001", "missing"],
                "updates": [{"field": "veg_started_at", "value": None}],
            },
        ),
        (
            "/api/breeding-logbook/plants:update-facts",
            {
                "idempotency_key": "bad-update-facts-shape",
                "plant_keys": ["SBBS-R1-001"],
                "updates": [{"field": "sex_key", "value": None}],
            },
        ),
        (
            "/api/breeding-logbook/sex-tests:bulk-create",
            {
                "idempotency_key": "bad-sex-test-plant",
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "sample_collected_at": "2026-06-18T16:00:00Z",
                "sample_sent_at": None,
                "tests": [
                    {
                        "plant_key": "missing",
                        "vendor_test_code": "FF-001",
                        "notes": None,
                    }
                ],
            },
        ),
        (
            "/api/breeding-logbook/sex-tests:bulk-create",
            {
                "idempotency_key": "bad-sex-test-blank-code",
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "sample_collected_at": "2026-06-18T16:00:00Z",
                "sample_sent_at": None,
                "tests": [
                    {
                        "plant_key": "SBBS-R1-001",
                        "vendor_test_code": "   ",
                        "notes": None,
                    }
                ],
            },
        ),
        (
            "/api/breeding-logbook/sex-tests:bulk-create",
            {
                "idempotency_key": "bad-sex-test-blank-note",
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "sample_collected_at": "2026-06-18T16:00:00Z",
                "sample_sent_at": None,
                "tests": [
                    {
                        "plant_key": "SBBS-R1-001",
                        "vendor_test_code": "FF-001",
                        "notes": "   ",
                    }
                ],
            },
        ),
        (
            "/api/breeding-logbook/sex-tests/999:update",
            {
                "idempotency_key": "bad-sex-test-update-missing",
                "sex_test_source_id": 999,
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "vendor_test_code": "FF-999",
                "sample_collected_at": "2026-06-18T16:00:00Z",
                "sample_sent_at": None,
                "result_received_at": None,
                "result_sex_key": None,
                "is_inconclusive": False,
                "notes": None,
            },
        ),
        (
            "/api/breeding-logbook/sex-tests/1000:update",
            {
                "idempotency_key": "bad-sex-test-update-mismatch",
                "sex_test_source_id": 1001,
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "vendor_test_code": "FF-001",
                "sample_collected_at": "2026-06-18T16:00:00Z",
                "sample_sent_at": None,
                "result_received_at": None,
                "result_sex_key": None,
                "is_inconclusive": False,
                "notes": None,
            },
        ),
        (
            "/api/breeding-logbook/sex-tests:bulk-result",
            {
                "idempotency_key": "bad-sex-test-result-missing-id",
                "result_received_at": "2026-06-22T16:00:00Z",
                "results": [
                    {
                        "sex_test_source_id": 999,
                        "result_sex_key": "female",
                        "is_inconclusive": False,
                    }
                ],
            },
        ),
        (
            "/api/breeding-logbook/sex-tests:bulk-result",
            {
                "idempotency_key": "bad-sex-test-result-missing-time",
                "results": [
                    {
                        "sex_test_source_id": 1000,
                        "result_sex_key": "female",
                        "is_inconclusive": False,
                    }
                ],
            },
        ),
        (
            "/api/breeding-logbook/plants:bulk-cull",
            {
                "idempotency_key": "bad-cull",
                "plant_keys": ["SBBS-R1-001"],
                "reason": "   ",
                "culled_at": "2026-06-21T16:00:00Z",
            },
        ),
        (
            "/api/breeding-logbook/plants/missing/notes",
            {"idempotency_key": "bad-note", "body": "Looks better."},
        ),
        (
            "/api/breeding-logbook/plants:bulk-note",
            {
                "idempotency_key": "bad-bulk-note-plant",
                "plant_keys": ["SBBS-R1-001", "missing"],
                "body": "Looks better.",
            },
        ),
        (
            "/api/breeding-logbook/plants:bulk-note",
            {
                "idempotency_key": "bad-bulk-note-body",
                "plant_keys": ["SBBS-R1-001"],
                "body": "   ",
            },
        ),
    ]

    for path, body in invalid_cases:
        response = await authed_client.post(path, json=body)
        assert 400 <= response.status_code < 500


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

    response = await authed_client.get("/api/tents/1/plants")

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

    response = await authed_client.get("/api/tents/1/plants/SBBS-R1-001")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["key"] == "SBBS-R1-001"
    assert body["sex_key"] == "unknown"
    assert body["grid_position"] == "A1"
    assert body["current_location"] == {
        "id": 1,
        "current_tent_id": 1,
        "current_tent_name": "Tent 1",
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

    listed = await authed_client.get("/api/tents/1/plants")
    detail = await authed_client.get("/api/tents/1/plants/SBBS-R1-001")

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

    missing = await authed_client.get("/api/tents/1/plants/missing")
    detail = await authed_client.get("/api/tents/1/plants/SBBS-R1-002")

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

    response = await authed_client.get("/api/tents/1/plants/SBBS-R1-001")

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
        "/api/tents/1/plants/SBBS-R1-001/metrics/history?range=24h"
    )
    empty = await authed_client.get(
        "/api/tents/1/plants/SBBS-R1-003/metrics/history?range=24h"
    )
    invalid = await authed_client.get(
        "/api/tents/1/plants/SBBS-R1-001/metrics/history?range=180d"
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
        "/api/tents/1/plants/SBBS-R1-001/moisture/history?range=24h"
    )
    comparison_history = await authed_client.get(
        "/api/tents/1/plants/moisture/history?range=24h"
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
        "/api/tents/1/metrics/history?range=24h&metric=fan_pct"
    )
    humidifier = await authed_client.get(
        "/api/tents/1/metrics/history?range=24h&metric=humidifier_intensity_pct"
    )
    heater = await authed_client.get(
        "/api/tents/1/metrics/history?range=24h&metric=heater_intensity_pct"
    )
    dehumidifier = await authed_client.get(
        "/api/tents/1/metrics/history?range=24h&metric=dehumidifier_runtime_pct"
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
        "target": {
            "kind": "ptz",
            "source_tent_id": 1,
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
        },
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


async def test_command_creation_accepts_ptz_target_shape(
    authed_client: AsyncClient,
    gateway_headers: dict[str, str],
) -> None:
    body = {
        "idempotency_key": "target-click",
        "target": {
            "kind": "ptz",
            "source_tent_id": 1,
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
        },
        "command_type": "ptz_preset",
        "payload": {"preset_id": "overview"},
    }

    created = await authed_client.post("/api/commands", json=body)

    assert created.status_code == 201
    created_body = created.json()
    assert created_body["target"] == body["target"]

    claim = await authed_client.post(
        "/api/gateway/v1/commands/claim",
        headers=gateway_headers,
        json={"site_id": "homebox", "limit": 1},
    )

    assert claim.status_code == 200
    command = claim.json()["commands"][0]
    assert command["command_id"] == created_body["command_id"]
    assert "tent_id" not in command
    assert "source_tent_id" not in command
    assert "device_id" not in command
    assert "capability_id" not in command
    assert command["target"] == body["target"]


async def test_command_openapi_uses_final_target_shape(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    create_schema = schemas["CommandCreateRequest"]
    create_properties = create_schema["properties"]
    response_schema = schemas["CommandResponse"]
    response_properties = response_schema["properties"]

    assert "target" in create_properties
    assert "target" in create_schema.get("required", [])
    for flat_field in ("source_tent_id", "device_id", "capability_id"):
        assert flat_field not in create_properties
        assert flat_field not in response_properties
    assert "legacy_target_tent_id" not in response_properties
    assert "target" in response_properties
    assert "target" not in response_schema.get("required", [])


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
        "target": {
            "kind": "ptz",
            "source_tent_id": 1,
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
        },
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
            "source_tent_id": 1,
            "asset_id": "asset-1",
            "object_key": "tents/1/asset-1.jpg",
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
            "source_tent_id": 1,
            "asset_id": "asset-1",
            "object_key": "tents/1/asset-1.jpg",
            "content_type": "image/jpeg",
            "byte_size": 25_000_000,
            "sha256": "a" * 64,
            "captured_at": "2026-05-05T03:40:00Z",
            "source_zone_id": None,
        },
    )
    assert complete.status_code == 200
    async with sessionmaker() as session:
        asset = (
            await session.execute(
                select(CloudAsset).where(CloudAsset.asset_id == "asset-1")
            )
        ).scalar_one()
    assert asset.source_tent_id == 1
    assert asset.source_zone_id is None

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


async def test_asset_complete_persists_source_scope_from_request(
    client: AsyncClient,
    gateway_headers: dict[str, str],
    cloud_engine: AsyncEngine,
) -> None:
    response = await client.post(
        "/api/gateway/v1/assets/complete",
        headers=gateway_headers,
        json={
            "site_id": "homebox",
            "source_tent_id": 2,
            "source_zone_id": 21,
            "device_id": "obsbot-sidecar",
            "asset_id": "asset-zone-scoped",
            "object_key": "tents/2/snapshots/clone-rack.jpg",
            "content_type": "image/jpeg",
            "byte_size": 12_000,
            "sha256": "c" * 64,
            "captured_at": "2026-05-05T03:41:00Z",
        },
    )

    assert response.status_code == 200
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        asset = (
            await session.execute(
                select(CloudAsset).where(CloudAsset.asset_id == "asset-zone-scoped")
            )
        ).scalar_one()
    assert asset.source_tent_id == 2
    assert asset.source_zone_id == 21


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
            "source_tent_id": 1,
            "asset_id": "asset-old",
            "object_key": "tents/1/snapshots/plant-a.jpg",
            "content_type": "image/jpeg",
            "byte_size": 10,
            "sha256": "a" * 64,
            "captured_at": "2026-05-05T03:40:00Z",
            "source_zone_id": None,
        },
    )
    second = await client.post(
        "/api/gateway/v1/assets/complete",
        headers=gateway_headers,
        json={
            "site_id": "homebox",
            "source_tent_id": 1,
            "asset_id": "asset-new",
            "object_key": "tents/1/snapshots/plant-a.jpg",
            "content_type": "image/jpeg",
            "byte_size": 20,
            "sha256": "b" * 64,
            "captured_at": "2026-05-05T03:45:00Z",
            "source_zone_id": None,
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
                        CloudAsset.object_key == "tents/1/snapshots/plant-a.jpg"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(assets) == 1
    assert assets[0].asset_id == "asset-new"
    assert assets[0].source_tent_id == 1
    assert assets[0].source_zone_id is None
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
            "target": {
                "kind": "ptz",
                "source_tent_id": 1,
                "device_id": "obsbot-main",
                "capability_id": "ptz_move",
            },
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
            "source_tent_id": 1,
            "asset_id": "asset-1",
            "object_key": "tents/1/asset-1.jpg",
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
                source_tent_id=1,
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
                source_tent_id=1,
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
    assert event.subject_id == "site=homebox;source_tent=1;device=env-main"
    assert event.event_metadata == {
        "source_tent_id": 1,
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
            "target": {
                "kind": "ptz",
                "source_tent_id": 1,
                "device_id": "obsbot-main",
                "capability_id": "ptz_move",
            },
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
                "target": {
                    "kind": "ptz",
                    "source_tent_id": 1,
                    "device_id": "obsbot-main",
                    "capability_id": "ptz_move",
                },
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
                source_tent_id=1,
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
                source_tent_id=1,
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
            "target": {
                "kind": "ptz",
                "source_tent_id": 1,
                "device_id": "obsbot-main",
                "capability_id": "ptz_move",
            },
            "command_type": "ptz_preset",
            "payload": {"preset_id": "overview"},
        },
    )
    fresh = await authed_client.post(
        "/api/commands",
        json={
            "idempotency_key": "fresh-click",
            "target": {
                "kind": "ptz",
                "source_tent_id": 1,
                "device_id": "obsbot-main",
                "capability_id": "ptz_move",
            },
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
            "target": {
                "kind": "ptz",
                "source_tent_id": 1,
                "device_id": "obsbot-main",
                "capability_id": "ptz_move",
            },
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
