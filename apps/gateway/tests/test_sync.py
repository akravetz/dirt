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
from dirt_gateway.local import GatewayLocalServiceBundle
from dirt_gateway.outbox import OutboxRepository
from dirt_gateway.protocols import AssetProjection
from dirt_gateway.sync import GatewaySyncService
from dirt_shared.config import CloudGatewayConfig
from dirt_shared.models import Capability, Device, SensorReading, Site, Tent
from dirt_shared.models.enums import SensorSource

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
        self.calls: list[tuple[str, str]] = []
        self.successful_calls: list[tuple[str, str]] = []
        self.catalogs: dict[str, dict[str, Any]] = {}
        self.latest_rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self.rollup_rows: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
        self.assets: dict[str, dict[str, Any]] = {}
        self.call_counts: defaultdict[str, int] = defaultdict(int)

    async def send_heartbeat(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._record("heartbeat", idempotency_key)
        return {"ok": True, **payload}

    async def put_catalog(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._record("catalog", idempotency_key)
        self.catalogs[idempotency_key] = payload
        return {"ok": True}

    async def put_latest_metrics(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._record("latest_metrics", idempotency_key)
        for row in payload["metrics"]:
            key = (row["site_id"], row["tent_id"], row["capability_id"], row["metric"])
            self.latest_rows[key] = row
        return {"ok": True}

    async def post_rollups(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
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
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._record("asset_sign", idempotency_key)
        return {
            "upload_url": "https://assets.test/upload",
            "headers": {"content-type": payload["content_type"]},
        }

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
        self.call_counts["asset_upload_bytes"] += 1

    async def complete_asset(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._record("asset_complete", idempotency_key)
        self.assets[payload["asset_id"]] = payload
        return {"ok": True}

    def _record(self, event_type: str, idempotency_key: str) -> None:
        self.call_counts[event_type] += 1
        self.calls.append((event_type, idempotency_key))
        if self.fail:
            raise CloudDeliveryError(f"offline for {event_type}")
        self.successful_calls.append((event_type, idempotency_key))


class StaticLocalServices:
    def __init__(self, *, asset: AssetProjection | None = None) -> None:
        self.asset = asset

    async def collect_catalog(self, site_id: str) -> dict[str, Any]:
        return {
            "site": {"site_id": site_id, "name": "Homebox", "timezone": "UTC"},
            "tents": [{"tent_id": "main", "name": "Main", "is_active": True}],
            "zones": [],
            "devices": [],
            "capabilities": [],
        }

    async def collect_latest_metrics(self, site_id: str) -> dict[str, Any]:
        return {"site_id": site_id, "metrics": []}

    async def collect_rollups(self, site_id: str) -> dict[str, Any]:
        return {"site_id": site_id, "rollups": []}

    async def latest_snapshot_asset(self, site_id: str) -> AssetProjection | None:
        del site_id
        return self.asset


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
) -> GatewaySyncService:
    return GatewaySyncService(
        config=config or _config(),
        outbox=OutboxRepository(engine),
        local_services=local_services,
        cloud_client=cloud,
        clock=lambda: FIXED_NOW,
        sleeper=NoopSleeper(),
        backoff=ImmediateBackoff(),
    )


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
    cloud = RecordingCloudClient()
    local = GatewayLocalServiceBundle(app_engine, clock=lambda: FIXED_NOW)

    result = await _service(app_engine, cloud, local_services=local).run_once()

    assert result.failed == 0
    assert cloud.catalogs
    catalog = next(iter(cloud.catalogs.values()))
    assert catalog["site"]["site_id"] == "homebox"
    assert {tent["tent_id"] for tent in catalog["tents"]} == {"main", "breeding"}


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
    await _seed_temperature_readings(app_engine)
    cloud = RecordingCloudClient()
    cloud.fail = True
    local = GatewayLocalServiceBundle(app_engine, clock=lambda: FIXED_NOW)
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
    asset = AssetProjection(
        sign_request={
            "site_id": "homebox",
            "tent_id": "main",
            "content_type": "image/jpeg",
            "byte_size": len(b"jpeg-bytes"),
            "object_key": "homebox/main/snapshots/snapshot.jpg",
            "asset_id": "asset-1",
            "sha256": "asset-1",
            "kind": "periodic",
        },
        complete_request={
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
        file_path=asset_file,
    )
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
    assert (
        cloud.assets["asset-1"]["object_key"] == "homebox/main/snapshots/snapshot.jpg"
    )


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
