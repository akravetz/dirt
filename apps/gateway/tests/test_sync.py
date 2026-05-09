from __future__ import annotations

import ast
import asyncio
import importlib
import json
import pkgutil
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import dirt_gateway
from dirt_gateway.cloud import CloudDeliveryError
from dirt_gateway.commands import GatewayCommandService
from dirt_gateway.local import GatewayLocalServiceBundle
from dirt_gateway.outbox import OutboxRepository
from dirt_gateway.protocols import AssetUploadProjection
from dirt_gateway.sync import GatewaySyncService
from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetCompleteResponse,
    AssetFailureRequest,
    AssetFailureResponse,
    AssetRetentionRequest,
    AssetSignUploadRequest,
    CatalogRequest,
    CatalogSite,
    CatalogTent,
    LatestMetricsRequest,
    PruneAssetsResponse,
    RollupItem,
    RollupsRequest,
    SignUploadResponse,
)
from dirt_shared.config import CloudGatewayConfig
from dirt_shared.models import (
    Capability,
    CloudOutbox,
    Command,
    Device,
    SensorReading,
    Site,
    Tent,
)
from dirt_shared.models.enums import SensorSource
from dirt_shared.services.commands import CommandService
from dirt_shared.testing import create_test_device

FIXED_NOW = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)


class ImmediateBackoff:
    def next_delay_s(self, attempt_count: int) -> float:
        return 0.0


class NoopSleeper:
    async def sleep(self, delay_s: float) -> None:
        del delay_s


class RecordingCloudClient:
    def __init__(self) -> None:
        self.fail = False
        self.fail_event_types: set[str] = set()
        self.upload_fail = False
        self.calls: list[tuple[str, str]] = []
        self.successful_calls: list[tuple[str, str]] = []
        self.catalogs: dict[str, dict[str, Any]] = {}
        self.latest_rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self.rollup_rows: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
        self.assets: dict[str, dict[str, Any]] = {}
        self.asset_sign_requests: list[AssetSignUploadRequest] = []
        self.asset_complete_requests: list[AssetCompleteRequest] = []
        self.call_counts: defaultdict[str, int] = defaultdict(int)
        self.claimed_commands: list[dict[str, Any]] = []
        self.command_results: list[tuple[str, dict[str, Any], str]] = []
        self.asset_failures: list[dict[str, Any]] = []
        self.retention_requests: list[dict[str, Any]] = []

    async def send_heartbeat(
        self, payload: Any, *, idempotency_key: str
    ) -> dict[str, Any]:
        payload = _payload_dict(payload)
        self._record("heartbeat", idempotency_key)
        return {"ok": True, **payload}

    async def put_catalog(
        self, payload: Any, *, idempotency_key: str
    ) -> dict[str, Any]:
        payload = _payload_dict(payload)
        self._record("catalog", idempotency_key)
        self.catalogs[idempotency_key] = payload
        return {"ok": True}

    async def put_latest_metrics(
        self, payload: Any, *, idempotency_key: str
    ) -> dict[str, Any]:
        payload = _payload_dict(payload)
        self._record("latest_metrics", idempotency_key)
        for row in payload["metrics"]:
            key = (row["site_id"], row["tent_id"], row["capability_id"], row["metric"])
            self.latest_rows[key] = row
        return {"ok": True}

    async def post_rollups(
        self, payload: Any, *, idempotency_key: str
    ) -> dict[str, Any]:
        payload = _payload_dict(payload)
        self._record("rollups", idempotency_key)
        for row in payload["rollups"]:
            key = (
                row["site_id"],
                row["tent_id"],
                row["capability_id"],
                row["metric"],
                row["bucket"],
                row["bucket_start_at"],
            )
            self.rollup_rows[key] = row
        return {"ok": True}

    async def sign_upload(
        self, payload: AssetSignUploadRequest, *, idempotency_key: str
    ) -> SignUploadResponse:
        self._record("asset_sign", idempotency_key)
        self.asset_sign_requests.append(payload)
        return SignUploadResponse(
            asset_id=payload.asset_id,
            object_key=payload.object_key,
            upload_url="https://assets.test/upload",
            method="PUT",
            headers={"content-type": payload.content_type},
            expires_at=FIXED_NOW + timedelta(minutes=10),
            byte_size=payload.byte_size,
        )

    async def upload_asset(
        self,
        *,
        file_path: Path,
        upload_url: str,
        headers: dict[str, str],
        content_type: str,
    ) -> None:
        del upload_url, headers, content_type
        assert file_path.exists()
        if self.upload_fail:
            raise CloudDeliveryError("asset byte upload failed")
        self.call_counts["asset_upload_bytes"] += 1

    async def complete_asset(
        self, payload: AssetCompleteRequest, *, idempotency_key: str
    ) -> AssetCompleteResponse:
        self._record("asset_complete", idempotency_key)
        self.asset_complete_requests.append(payload)
        asset_id = payload.asset_id or payload.sha256 or payload.object_key
        self.assets[asset_id] = payload.model_dump(mode="json")
        return AssetCompleteResponse(
            asset_id=asset_id,
            object_key=payload.object_key,
            uploaded_at=FIXED_NOW,
        )

    async def report_asset_failure(
        self, payload: AssetFailureRequest, *, idempotency_key: str
    ) -> AssetFailureResponse:
        self._record("asset_failure", idempotency_key)
        self.asset_failures.append(payload.model_dump(mode="json"))
        return AssetFailureResponse(ok=True, received_at=FIXED_NOW)

    async def prune_expired_assets(
        self, payload: AssetRetentionRequest, *, idempotency_key: str
    ) -> PruneAssetsResponse:
        self._record("asset_retention", idempotency_key)
        self.retention_requests.append(payload.model_dump(mode="json"))
        return PruneAssetsResponse(
            cutoff=FIXED_NOW - timedelta(days=30),
            matched=0,
            objects_deleted=0,
        )

    async def claim_commands(
        self, *, site_id: str, limit: int, idempotency_key: str
    ) -> dict[str, Any]:
        del site_id
        self._record("command_claim", idempotency_key)
        return {"commands": self.claimed_commands[:limit]}

    async def report_command_result(
        self,
        *,
        command_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._record("command_result", idempotency_key)
        self.command_results.append((command_id, payload, idempotency_key))
        return {"command_id": command_id, **payload}

    def _record(self, event_type: str, idempotency_key: str) -> None:
        self.call_counts[event_type] += 1
        self.calls.append((event_type, idempotency_key))
        if self.fail or event_type in self.fail_event_types:
            raise CloudDeliveryError(f"offline for {event_type}")
        self.successful_calls.append((event_type, idempotency_key))


def _payload_dict(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return payload


def _asset_projection(asset_file: Path) -> AssetUploadProjection:
    sign_request = AssetSignUploadRequest(
        site_id="homebox",
        tent_id="main",
        content_type="image/jpeg",
        byte_size=len(b"jpeg-bytes"),
        object_key="homebox/main/snapshots/snapshot.jpg",
        asset_id="asset-1",
        sha256="asset-1",
        kind="periodic",
    )
    return AssetUploadProjection(
        sign_request=sign_request,
        complete_request=AssetCompleteRequest(
            **sign_request.model_dump(),
            captured_at=FIXED_NOW,
        ),
        file_path=asset_file,
    )


class StaticLocalServices:
    def __init__(self, *, asset: AssetUploadProjection | None = None) -> None:
        self.asset = asset

    async def collect_catalog(self, site_id: str) -> CatalogRequest:
        return CatalogRequest(
            site=CatalogSite(site_id=site_id, name="Homebox", timezone="UTC"),
            tents=[CatalogTent(tent_id="main", name="Main", is_active=True)],
        )

    async def collect_latest_metrics(self, site_id: str) -> LatestMetricsRequest:
        return LatestMetricsRequest(site_id=site_id, metrics=[])

    async def collect_rollups(
        self, site_id: str, *, bucket_names: set[str] | None = None
    ) -> RollupsRequest:
        del bucket_names
        return RollupsRequest(site_id=site_id, rollups=[])

    async def latest_snapshot_asset(self, site_id: str) -> AssetUploadProjection | None:
        del site_id
        return self.asset


class ChangingRollupLocalServices(StaticLocalServices):
    def __init__(self) -> None:
        super().__init__()
        self.index = 0

    async def collect_rollups(
        self, site_id: str, *, bucket_names: set[str] | None = None
    ) -> RollupsRequest:
        self.index += 1
        buckets = sorted(bucket_names or {"5m", "1h", "4h"})
        return RollupsRequest(
            site_id=site_id,
            rollups=[
                RollupItem(
                    site_id=site_id,
                    tent_id="main",
                    capability_id="temperature_f",
                    metric="temperature_f",
                    bucket=bucket,
                    bucket_start_at=FIXED_NOW - timedelta(minutes=self.index * 5),
                    bucket_end_at=FIXED_NOW,
                    min_value=70.0,
                    avg_value=71.0,
                    max_value=72.0,
                    sample_count=self.index,
                    unit="degF",
                )
                for bucket in buckets
            ],
        )


class RecordingRollupLocalServices(StaticLocalServices):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[frozenset[str]] = []

    async def collect_rollups(
        self, site_id: str, *, bucket_names: set[str] | None = None
    ) -> RollupsRequest:
        buckets = frozenset(bucket_names or {"5m", "1h", "4h"})
        self.requests.append(buckets)
        return RollupsRequest(
            site_id=site_id,
            rollups=[
                RollupItem(
                    site_id=site_id,
                    tent_id="main",
                    capability_id="temperature_f",
                    metric="temperature_f",
                    bucket=bucket,
                    bucket_start_at=FIXED_NOW,
                    bucket_end_at=FIXED_NOW + timedelta(minutes=5),
                    min_value=70.0,
                    avg_value=71.0,
                    max_value=72.0,
                    sample_count=1,
                    unit="degF",
                )
                for bucket in sorted(buckets)
            ],
        )


class RecordingPTZ:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.presets = {"overview", "plant_a"}

    def get_preset(self, preset_id: str):
        return {"id": preset_id} if preset_id in self.presets else None

    async def apply_preset(self, preset_id: str) -> dict[str, Any]:
        self.calls.append(("preset", preset_id))
        return {
            "ok": True,
            "preset": preset_id,
            "yaw": 0.0,
            "pitch": -10.0,
            "zoom": 1.0,
        }

    async def look_at_normalized(self, x: float, y: float) -> dict[str, Any]:
        self.calls.append(("look", (x, y)))
        return {"ok": True, "preset": None, "yaw": x * 10, "pitch": y * 10, "zoom": 1.0}

    async def zoom_to(self, value: float) -> dict[str, Any]:
        self.calls.append(("zoom_to", value))
        return {"ok": True, "zoom": value}

    async def zoom_by(self, delta: float) -> dict[str, Any]:
        self.calls.append(("zoom_by", delta))
        return {"ok": True, "zoom": 1.0 + delta}


def _config(*, dry_run: bool = False, asset_sync_enabled: bool = False):
    return CloudGatewayConfig(
        api_base_url="https://api.test",
        site_id="homebox",
        gateway_id="gateway-main",
        gateway_token="test-token",
        sync_interval_s=30.0,
        command_poll_interval_s=5.0,
        asset_sync_enabled=asset_sync_enabled,
        dry_run=dry_run,
    )


def _service(
    engine: AsyncEngine,
    cloud: RecordingCloudClient,
    *,
    local_services,
    config: CloudGatewayConfig | None = None,
    clock=lambda: FIXED_NOW,
) -> GatewaySyncService:
    return GatewaySyncService(
        config=config or _config(),
        outbox=OutboxRepository(engine),
        local_services=local_services,
        cloud_client=cloud,
        clock=clock,
        sleeper=NoopSleeper(),
        backoff=ImmediateBackoff(),
    )


def _command_service(
    engine: AsyncEngine,
    cloud: RecordingCloudClient,
    ptz: RecordingPTZ,
) -> GatewayCommandService:
    return GatewayCommandService(
        config=_config(),
        cloud_client=cloud,
        command_ledger=CommandService(engine, clock=lambda: FIXED_NOW),
        outbox=OutboxRepository(engine),
        ptz=ptz,
        clock=lambda: FIXED_NOW,
        backoff=ImmediateBackoff(),
    )


def _cloud_command(
    command_id: str,
    *,
    command_type: str = "ptz_preset",
    payload: dict[str, Any] | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "command_id": command_id,
        "site_id": "homebox",
        "tent_id": "main",
        "device_id": "obsbot-main",
        "capability_id": "ptz_move",
        "command_type": command_type,
        "payload": payload or {"preset_id": "overview"},
        "status": "claimed",
        "queued_at": (FIXED_NOW - timedelta(seconds=5)).isoformat(),
        "expires_at": (expires_at or FIXED_NOW + timedelta(seconds=55)).isoformat(),
        "claimed_by": "gateway-main",
        "claimed_at": FIXED_NOW.isoformat(),
        "requested_by": "admin",
        "result": None,
        "error": None,
    }


async def _seed_temperature_readings(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        cap = (
            await session.exec(
                select(Capability)
                .join(Device, Device.id == Capability.device_id)
                .join(Site, Site.id == Device.site_id)
                .join(Tent, Tent.id == Device.tent_id)
                .where(Site.site_id == "homebox")
                .where(Tent.tent_id == "main")
                .where(Device.device_id == "fan-controller")
                .where(Capability.capability_id == "temperature_f")
            )
        ).one()
        for offset, value in (
            (timedelta(minutes=20), 72.0),
            (timedelta(minutes=10), 73.0),
            (timedelta(minutes=2), 74.0),
        ):
            session.add(
                SensorReading(
                    ts=FIXED_NOW - offset,
                    capability_id=cap.id,
                    metric="temperature_f",
                    value=value,
                    source=SensorSource.ESP32,
                )
            )
        await session.commit()


async def test_catalog_syncs_homebox_main_and_breeding(app_engine: AsyncEngine):
    async with AsyncSession(app_engine) as session:
        breeding_env = await create_test_device(
            session,
            tent_id="breeding",
            zone_id="canopy",
            device_id="test-breeding-catalog-node",
            name="Test breeding catalog node",
            kind="env_sensor",
            controller="test",
        )
        breeding_env.last_seen = FIXED_NOW
        await session.commit()

    cloud = RecordingCloudClient()
    local = GatewayLocalServiceBundle(app_engine, clock=lambda: FIXED_NOW)
    projection = await local.collect_catalog("homebox")
    assert isinstance(projection, CatalogRequest)
    breeding_projection_devices = [
        device
        for device in projection.devices
        if device.tent_id == "breeding"
        and device.device_id == "test-breeding-catalog-node"
    ]
    assert len(breeding_projection_devices) == 1
    assert breeding_projection_devices[0].last_seen_at == FIXED_NOW
    expected_breeding_device = breeding_projection_devices[0].model_dump(mode="json")

    result = await _service(app_engine, cloud, local_services=local).run_once()

    assert result.failed == 0
    assert cloud.catalogs
    catalog = next(iter(cloud.catalogs.values()))
    assert catalog["site"]["site_id"] == "homebox"
    assert {tent["tent_id"] for tent in catalog["tents"]} == {
        "main",
        "breeding",
        "clones",
    }
    assert {
        (schedule["tent_id"], schedule["device_id"], schedule["starts_local"])
        for schedule in catalog["schedules"]
    } >= {
        ("main", "kasa-lights-main", "09:00:00"),
        ("breeding", "kasa-lights-breeding", "06:00:00"),
        ("clones", "kasa-lights-clones", "06:00:00"),
    }
    breeding_devices = [
        device
        for device in catalog["devices"]
        if device["tent_id"] == "breeding"
        and device["device_id"] == "test-breeding-catalog-node"
    ]
    assert breeding_devices == [expected_breeding_device]


async def test_latest_metrics_and_rollups_are_not_duplicated(
    app_engine: AsyncEngine,
):
    await _seed_temperature_readings(app_engine)
    cloud = RecordingCloudClient()
    local = GatewayLocalServiceBundle(app_engine, clock=lambda: FIXED_NOW)
    service = _service(app_engine, cloud, local_services=local)

    first = await service.run_once()
    second = await service.run_once()

    assert first.failed == 0
    assert second.enqueued == 0
    assert cloud.call_counts["latest_metrics"] == 1
    assert cloud.call_counts["rollups"] == 1
    assert ("homebox", "main", "temperature_f", "temperature_f") in cloud.latest_rows
    assert any(key[4] == "4h" for key in cloud.rollup_rows)


async def test_offline_cloud_failures_remain_pending_then_retry_without_duplicates(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    cloud.fail = True
    local = StaticLocalServices()
    service = _service(app_engine, cloud, local_services=local)
    outbox = OutboxRepository(app_engine)

    failed = await service.run_once()
    assert failed.delivered == 0
    assert failed.failed > 0
    assert await outbox.pending_count() == failed.failed

    cloud.fail = False
    recovered = await service.run_once()

    assert recovered.failed == 0
    assert recovered.delivered == failed.failed
    assert await outbox.pending_count() == 0
    delivered_keys = [
        key for _, key in cloud.successful_calls if not key.endswith(":sign")
    ]
    assert len(delivered_keys) == len(set(delivered_keys))


async def test_heartbeat_delivery_is_not_blocked_by_rollup_backlog(
    app_engine: AsyncEngine,
):
    outbox = OutboxRepository(app_engine)
    for index in range(3):
        await outbox.enqueue(
            event_type="rollups",
            idempotency_key=f"homebox:rollups:stale-{index}",
            payload={"site_id": "homebox", "rollups": [{"index": index}]},
            now=FIXED_NOW - timedelta(minutes=5),
        )
    cloud = RecordingCloudClient()
    cloud.fail_event_types.add("rollups")
    service = _service(app_engine, cloud, local_services=StaticLocalServices())

    result = await service.run_once()

    assert result.failed == 1
    assert cloud.call_counts["heartbeat"] == 1
    assert cloud.call_counts["latest_metrics"] == 1
    assert cloud.call_counts["rollups"] == 1


async def test_read_only_outbox_replay_validates_stored_json_before_dispatch(
    app_engine: AsyncEngine,
):
    outbox = OutboxRepository(app_engine)
    await outbox.enqueue(
        event_type="catalog",
        idempotency_key="homebox:catalog:missing-last-seen",
        payload={
            "site": {"site_id": "homebox", "name": "Homebox", "timezone": "UTC"},
            "tents": [],
            "zones": [],
            "devices": [
                {
                    "tent_id": "main",
                    "device_id": "test-node",
                    "name": "Test node",
                }
            ],
            "capabilities": [],
            "schedules": [],
        },
        now=FIXED_NOW - timedelta(minutes=1),
    )
    cloud = RecordingCloudClient()
    service = _service(app_engine, cloud, local_services=StaticLocalServices())

    result = await service.run_once()

    assert result.failed == 1
    assert cloud.call_counts["catalog"] == 1
    assert "homebox:catalog:missing-last-seen" not in cloud.catalogs
    async with AsyncSession(app_engine) as session:
        row = (
            await session.exec(
                select(CloudOutbox).where(
                    CloudOutbox.idempotency_key == "homebox:catalog:missing-last-seen"
                )
            )
        ).one()
    assert row.status == "pending"
    assert row.attempt_count == 1
    assert "last_seen_at" in str(row.last_error)


async def test_pending_rollups_are_superseded_by_newer_projection(
    app_engine: AsyncEngine,
):
    now = FIXED_NOW

    def clock() -> datetime:
        return now

    cloud = RecordingCloudClient()
    cloud.fail_event_types.add("rollups")
    service = _service(
        app_engine,
        cloud,
        local_services=ChangingRollupLocalServices(),
        clock=clock,
    )

    first = await service.run_once()
    now = FIXED_NOW + timedelta(minutes=5)
    second = await service.run_once()

    assert first.failed == 1
    assert second.failed == 1
    async with AsyncSession(app_engine) as session:
        rows = (
            await session.exec(
                select(CloudOutbox)
                .where(CloudOutbox.event_type == "rollups")
                .order_by(CloudOutbox.id)
            )
        ).all()
    assert [row.status for row in rows] == ["superseded", "pending"]
    assert rows[0].last_error == "superseded by newer projection"
    assert rows[1].payload["rollups"][0]["sample_count"] == 2


async def test_rollup_buckets_use_independent_sync_intervals(
    app_engine: AsyncEngine,
):
    now = FIXED_NOW

    def clock() -> datetime:
        return now

    cloud = RecordingCloudClient()
    local = RecordingRollupLocalServices()
    service = _service(app_engine, cloud, local_services=local, clock=clock)

    await service.run_once()
    now = FIXED_NOW + timedelta(minutes=4)
    await service.run_once()
    now = FIXED_NOW + timedelta(minutes=5)
    await service.run_once()
    now = FIXED_NOW + timedelta(hours=1)
    await service.run_once()
    now = FIXED_NOW + timedelta(hours=4)
    await service.run_once()

    assert local.requests == [
        frozenset({"5m", "1h", "4h"}),
        frozenset({"5m"}),
        frozenset({"5m", "1h"}),
        frozenset({"5m", "1h", "4h"}),
    ]


async def test_dry_run_mode_does_not_call_cloud_client(app_engine: AsyncEngine):
    cloud = RecordingCloudClient()
    service = _service(
        app_engine,
        cloud,
        local_services=StaticLocalServices(),
        config=_config(dry_run=True),
    )

    result = await service.run_once()

    assert result.dry_run is True
    assert cloud.calls == []
    assert await OutboxRepository(app_engine).pending_count() == 0


async def test_asset_sync_uses_sign_upload_complete_flow(
    app_engine: AsyncEngine,
    tmp_path: Path,
):
    asset_file = tmp_path / "snapshot.jpg"
    asset_file.write_bytes(b"jpeg-bytes")
    asset = _asset_projection(asset_file)
    cloud = RecordingCloudClient()
    service = _service(
        app_engine,
        cloud,
        local_services=StaticLocalServices(asset=asset),
        config=_config(asset_sync_enabled=True),
    )

    await service.run_once()

    assert cloud.call_counts["asset_sign"] == 1
    assert cloud.call_counts["asset_upload_bytes"] == 1
    assert cloud.call_counts["asset_complete"] == 1
    assert cloud.call_counts["asset_retention"] == 1
    assert cloud.asset_sign_requests == [asset.sign_request]
    assert cloud.asset_complete_requests == [asset.complete_request]
    assert cloud.retention_requests == [
        AssetRetentionRequest(
            site_id="homebox",
            as_of_date=FIXED_NOW.date(),
        ).model_dump(mode="json")
    ]
    async with AsyncSession(app_engine) as session:
        asset_row = (
            await session.exec(
                select(CloudOutbox).where(CloudOutbox.event_type == "asset_upload")
            )
        ).one()
    assert asset_row.payload == {
        "sign_request": asset.sign_request.model_dump(mode="json"),
        "complete_request": asset.complete_request.model_dump(mode="json"),
        "file_path": str(asset_file),
    }
    assert (
        cloud.assets["asset-1"]["object_key"] == "homebox/main/snapshots/snapshot.jpg"
    )


async def test_asset_upload_outbox_replay_validates_stored_json_before_cloud_calls(
    app_engine: AsyncEngine,
    tmp_path: Path,
):
    asset_file = tmp_path / "snapshot.jpg"
    asset_file.write_bytes(b"jpeg-bytes")
    outbox = OutboxRepository(app_engine)
    await outbox.enqueue(
        event_type="asset_upload",
        idempotency_key="homebox:asset_upload:bad-sign-request",
        payload={
            "sign_request": {
                "site_id": "homebox",
                "tent_id": "main",
                "content_type": "image/jpeg",
                "object_key": "homebox/main/snapshots/snapshot.jpg",
                "asset_id": "asset-1",
                "sha256": "asset-1",
                "kind": "periodic",
            },
            "complete_request": {
                "site_id": "homebox",
                "tent_id": "main",
                "content_type": "image/jpeg",
                "byte_size": len(b"jpeg-bytes"),
                "object_key": "homebox/main/snapshots/snapshot.jpg",
                "asset_id": "asset-1",
                "sha256": "asset-1",
                "kind": "periodic",
                "captured_at": FIXED_NOW.isoformat(),
            },
            "file_path": str(asset_file),
        },
        now=FIXED_NOW - timedelta(minutes=1),
    )
    cloud = RecordingCloudClient()
    service = _service(app_engine, cloud, local_services=StaticLocalServices())

    result = await service.run_once()

    assert result.failed == 1
    assert cloud.call_counts["asset_sign"] == 0
    assert cloud.call_counts["asset_upload_bytes"] == 0
    assert cloud.call_counts["asset_complete"] == 0
    assert cloud.call_counts["asset_failure"] == 0
    async with AsyncSession(app_engine) as session:
        row = (
            await session.exec(
                select(CloudOutbox).where(
                    CloudOutbox.idempotency_key
                    == "homebox:asset_upload:bad-sign-request"
                )
            )
        ).one()
    assert row.status == "pending"
    assert row.attempt_count == 1
    assert "byte_size" in str(row.last_error)


async def test_asset_sync_reports_upload_failures_and_retries(
    app_engine: AsyncEngine,
    tmp_path: Path,
):
    asset_file = tmp_path / "snapshot.jpg"
    asset_file.write_bytes(b"jpeg-bytes")
    asset = _asset_projection(asset_file)
    cloud = RecordingCloudClient()
    cloud.upload_fail = True
    service = _service(
        app_engine,
        cloud,
        local_services=StaticLocalServices(asset=asset),
        config=_config(asset_sync_enabled=True),
    )

    failed = await service.run_once()

    assert failed.failed == 1
    assert cloud.call_counts["asset_failure"] == 1
    assert cloud.asset_failures[0]["stage"] == "upload_or_complete"
    assert cloud.asset_failures[0]["asset_id"] == "asset-1"
    assert await OutboxRepository(app_engine).pending_count() == 1


async def test_cloud_gateway_logs_are_isolated_and_useful(
    app_engine: AsyncEngine,
    isolate_observability_logs: Path,
):
    cloud = RecordingCloudClient()
    service = _service(
        app_engine,
        cloud,
        local_services=StaticLocalServices(),
    )

    await service.run_once()

    events = await _read_log_events(
        isolate_observability_logs / "cloud_gateway",
        expected={"cycle_started", "enqueued", "delivered", "cycle_finished"},
    )
    names = {event["event"] for event in events}
    assert {"cycle_started", "enqueued", "delivered", "cycle_finished"} <= names
    assert all(event["stream"] == "cloud_gateway" for event in events)
    assert {event["site_id"] for event in events} == {"homebox"}


async def test_command_loop_executes_ptz_and_records_local_ledger(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command("cloud-1", payload={"preset_id": "overview"})
    ]
    ptz = RecordingPTZ()

    result = await _command_service(app_engine, cloud, ptz).run_once()

    assert result.executed == 1
    assert ptz.calls == [("preset", "overview")]
    assert [
        (command_id, payload["status"])
        for command_id, payload, _key in cloud.command_results
    ] == [("cloud-1", "running"), ("cloud-1", "succeeded")]
    async with AsyncSession(app_engine) as session:
        command = (
            await session.exec(
                select(Command).where(
                    Command.idempotency_key == "cloud-command:cloud-1"
                )
            )
        ).one()
    assert command.source == "cloud_gateway"
    assert command.status == "succeeded"
    assert command.command_type == "ptz.preset"
    assert command.result["preset"] == "overview"


async def test_command_loop_rejects_expired_and_invalid_without_ptz(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-expired",
            expires_at=FIXED_NOW - timedelta(seconds=1),
        ),
        _cloud_command(
            "cloud-unsafe",
            command_type="fan_set_duty",
            payload={"duty_pct": 80},
        ),
        _cloud_command(
            "cloud-bad-payload",
            command_type="ptz_look",
            payload={"x": 0.8, "y": 0.0},
        ),
    ]
    ptz = RecordingPTZ()

    result = await _command_service(app_engine, cloud, ptz).run_once()

    assert result.executed == 0
    assert ptz.calls == []
    statuses = [
        payload["status"] for _command_id, payload, _key in cloud.command_results
    ]
    assert statuses == ["expired", "rejected", "rejected"]
    async with AsyncSession(app_engine) as session:
        local_commands = (await session.exec(select(Command))).all()
    assert local_commands == []


async def test_command_loop_does_not_reexecute_terminal_local_command(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command("cloud-repeat", command_type="ptz_zoom", payload={"delta": 0.1})
    ]
    ptz = RecordingPTZ()
    service = _command_service(app_engine, cloud, ptz)

    first = await service.run_once()
    second = await service.run_once()

    assert first.executed == 1
    assert second.executed == 0
    assert ptz.calls == [("zoom_by", 0.1)]
    terminal_reports = [
        payload["status"]
        for _command_id, payload, _key in cloud.command_results
        if payload["status"] == "succeeded"
    ]
    assert terminal_reports == ["succeeded", "succeeded"]


def test_gateway_package_does_not_import_hardware_loop_modules():
    dirt_hwd_modules_before = {
        name for name in sys.modules if name.startswith("dirt_hwd")
    }
    for module in pkgutil.walk_packages(dirt_gateway.__path__, "dirt_gateway."):
        importlib.import_module(module.name)

    dirt_hwd_modules_after = {
        name for name in sys.modules if name.startswith("dirt_hwd")
    }
    assert dirt_hwd_modules_after == dirt_hwd_modules_before
    gateway_root = Path(dirt_gateway.__file__).parent
    for path in gateway_root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith("dirt_hwd") for alias in node.names
                )
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith("dirt_hwd")


async def _read_log_events(
    stream_dir: Path,
    *,
    expected: set[str] | None = None,
) -> list[dict[str, Any]]:
    for _ in range(50):
        files = list(stream_dir.glob("*.jsonl"))
        if files:
            lines = files[0].read_text().splitlines()
            if lines:
                events = [json.loads(line) for line in lines]
                if expected is None or expected <= {event["event"] for event in events}:
                    return events
        await asyncio.sleep(0.01)
    return []
