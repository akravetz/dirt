from __future__ import annotations

import ast
import asyncio
import importlib
import inspect
import json
import pkgutil
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import dirt_gateway
import dirt_gateway.local as gateway_local
from dirt_gateway.breeding_commands import BreedingCommandExecutor
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
    CatalogPlant,
    CatalogPlantMetricStream,
    CatalogRequest,
    CatalogResponse,
    CatalogSite,
    CatalogTent,
    CommandClaimResponse,
    CommandResultRequest,
    CommandResultResponse,
    HeartbeatResponse,
    LatestMetricsRequest,
    PruneAssetsResponse,
    RollupItem,
    RollupsRequest,
    SignUploadResponse,
    UpsertCountResponse,
    WikiProjectionRequest,
    WikiProjectionResponse,
)
from dirt_shared.config import CloudGatewayConfig
from dirt_shared.models import (
    Capability,
    CloudOutbox,
    Command,
    CrossEvent,
    Device,
    MetricPresentation,
    Plant,
    PlantEvent,
    PlantLine,
    PlantLocationHistory,
    PlantMetricStream,
    PlantNote,
    SeedLot,
    SensorReading,
    Site,
    Tent,
    Zone,
)
from dirt_shared.models.enums import SensorSource
from dirt_shared.services.commands import CommandService
from dirt_shared.testing import resolve_test_tent_pk, resolve_test_zone_pk

FIXED_NOW = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
SUBSTRATE_HISTORY_METRICS = {
    "substrate_temp_c",
    "substrate_ec_us_cm",
    "substrate_ph",
}


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
        self.latest_rows: dict[tuple[str, int, str, str, str], dict[str, Any]] = {}
        self.rollup_rows: dict[
            tuple[str, int, str, str, str, str, str], dict[str, Any]
        ] = {}
        self.assets: dict[str, dict[str, Any]] = {}
        self.asset_sign_requests: list[AssetSignUploadRequest] = []
        self.asset_complete_requests: list[AssetCompleteRequest] = []
        self.call_counts: defaultdict[str, int] = defaultdict(int)
        self.claimed_commands: list[dict[str, Any]] = []
        self.command_results: list[tuple[str, CommandResultRequest, str]] = []
        self.asset_failures: list[dict[str, Any]] = []
        self.retention_requests: list[dict[str, Any]] = []
        self.wiki_projections: dict[str, dict[str, Any]] = {}

    async def send_heartbeat(
        self, payload: Any, *, idempotency_key: str
    ) -> HeartbeatResponse:
        payload = _payload_dict(payload)
        self._record("heartbeat", idempotency_key)
        return HeartbeatResponse.model_validate(
            {"ok": True, **payload, "received_at": FIXED_NOW}
        )

    async def put_catalog(
        self, payload: Any, *, idempotency_key: str
    ) -> CatalogResponse:
        payload = _payload_dict(payload)
        self._record("catalog", idempotency_key)
        self.catalogs[idempotency_key] = payload
        return CatalogResponse(
            sites=1,
            tents=len(payload["tents"]),
            zones=len(payload["zones"]),
            devices=len(payload["devices"]),
            capabilities=len(payload["capabilities"]),
            schedules=len(payload["schedules"]),
            plant_lines=len(payload["plant_lines"]),
            seed_lots=len(payload["seed_lots"]),
            plants=len(payload["plants"]),
            plant_locations=len(payload["plant_locations"]),
            cross_events=len(payload["cross_events"]),
            plant_notes=len(payload["plant_notes"]),
            plant_events=len(payload["plant_events"]),
            plant_metric_streams=len(payload["plant_metric_streams"]),
        )

    async def put_latest_metrics(
        self, payload: Any, *, idempotency_key: str
    ) -> UpsertCountResponse:
        payload = _payload_dict(payload)
        self._record("latest_metrics", idempotency_key)
        for row in payload["metrics"]:
            key = (
                row["site_id"],
                row["source_tent_id"],
                row["device_id"],
                row["capability_id"],
                row["metric"],
            )
            self.latest_rows[key] = row
        return UpsertCountResponse(upserted=len(payload["metrics"]))

    async def post_rollups(
        self, payload: Any, *, idempotency_key: str
    ) -> UpsertCountResponse:
        payload = _payload_dict(payload)
        self._record("rollups", idempotency_key)
        for row in payload["rollups"]:
            key = (
                row["site_id"],
                row["source_tent_id"],
                row["device_id"],
                row["capability_id"],
                row["metric"],
                row["bucket"],
                row["bucket_start_at"],
            )
            self.rollup_rows[key] = row
        return UpsertCountResponse(upserted=len(payload["rollups"]))

    async def put_wiki_projection(
        self, payload: Any, *, idempotency_key: str
    ) -> WikiProjectionResponse:
        payload = _payload_dict(payload)
        self._record("wiki", idempotency_key)
        self.wiki_projections[idempotency_key] = payload
        return WikiProjectionResponse(
            upserted=len(payload["pages"]),
            deleted=0,
            synced_at=FIXED_NOW,
        )

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
    ) -> CommandClaimResponse:
        del site_id
        self._record("command_claim", idempotency_key)
        return CommandClaimResponse.model_validate(
            {"commands": self.claimed_commands[:limit]}
        )

    async def report_command_result(
        self,
        *,
        command_id: str,
        payload: CommandResultRequest,
        idempotency_key: str,
    ) -> CommandResultResponse:
        self._record("command_result", idempotency_key)
        self.command_results.append((command_id, payload, idempotency_key))
        return CommandResultResponse.model_validate(
            {
                "command_id": command_id,
                "target": {
                    "kind": "ptz",
                    "source_tent_id": 1,
                    "device_id": "obsbot-main",
                    "capability_id": "ptz_move",
                },
                "command_type": "ptz_preset",
                "payload": {"preset_id": "overview"},
                "queued_at": FIXED_NOW - timedelta(seconds=5),
                "expires_at": FIXED_NOW + timedelta(seconds=55),
                "claimed_by": "gateway-main",
                "claimed_at": FIXED_NOW,
                "requested_by": "admin",
                "started_at": None,
                "finished_at": None,
                **payload.model_dump(mode="python"),
            }
        )

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
        source_tent_id=1,
        content_type="image/jpeg",
        byte_size=len(b"jpeg-bytes"),
        object_key="tents/1/snapshots/snapshot.jpg",
        asset_id="asset-1",
        sha256="asset-1",
        kind="periodic",
    )
    return AssetUploadProjection(
        sign_request=sign_request,
        complete_request=AssetCompleteRequest(
            **sign_request.model_dump(),
            captured_at=FIXED_NOW,
            source_zone_id=None,
        ),
        file_path=asset_file,
    )


class StaticLocalServices:
    def __init__(self, *, asset: AssetUploadProjection | None = None) -> None:
        self.asset = asset

    async def collect_catalog(self, site_id: str) -> CatalogRequest:
        return CatalogRequest(
            site_id=site_id,
            site=CatalogSite(source_site_id=1, name="Homebox", timezone="UTC"),
            tents=[
                CatalogTent(
                    source_tent_id=1,
                    name="Main",
                    role="flower",
                    is_active=True,
                )
            ],
        )

    async def collect_latest_metrics(self, site_id: str) -> LatestMetricsRequest:
        return LatestMetricsRequest(site_id=site_id, metrics=[])

    async def collect_rollups(
        self, site_id: str, *, bucket_names: set[str] | None = None
    ) -> RollupsRequest:
        del bucket_names
        return RollupsRequest(site_id=site_id, rollups=[])

    async def collect_wiki_pages(self, site_id: str) -> WikiProjectionRequest:
        return WikiProjectionRequest(
            site_id=site_id,
            generated_at=FIXED_NOW,
            pages=[],
            excluded_paths=["wiki/AGENTS.md"],
            content_hash="0" * 64,
        )

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
        buckets = sorted(bucket_names or {"5m", "1h", "4h", "1d"})
        return RollupsRequest(
            site_id=site_id,
            rollups=[
                RollupItem(
                    site_id=site_id,
                    source_site_id=1,
                    source_tent_id=1,
                    device_id="fan-controller",
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
        buckets = frozenset(bucket_names or {"5m", "1h", "4h", "1d"})
        self.requests.append(buckets)
        return RollupsRequest(
            site_id=site_id,
            rollups=[
                RollupItem(
                    site_id=site_id,
                    source_site_id=1,
                    source_tent_id=1,
                    device_id="fan-controller",
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


class ManyRollupLocalServices(StaticLocalServices):
    async def collect_rollups(
        self, site_id: str, *, bucket_names: set[str] | None = None
    ) -> RollupsRequest:
        del bucket_names
        return RollupsRequest(
            site_id=site_id,
            rollups=[
                RollupItem(
                    site_id=site_id,
                    source_site_id=1,
                    source_tent_id=1,
                    device_id="fan-controller",
                    capability_id="temperature_f",
                    metric="temperature_f",
                    bucket="5m",
                    bucket_start_at=FIXED_NOW + timedelta(minutes=index),
                    bucket_end_at=FIXED_NOW + timedelta(minutes=index + 5),
                    min_value=70.0,
                    avg_value=71.0,
                    max_value=72.0,
                    sample_count=1,
                    unit="degF",
                )
                for index in range(1201)
            ],
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
        breeding=BreedingCommandExecutor(engine, clock=lambda: FIXED_NOW),
        clock=lambda: FIXED_NOW,
        backoff=ImmediateBackoff(),
    )


def _cloud_command(
    command_id: str,
    *,
    command_type: str = "ptz_preset",
    payload: dict[str, Any] | None = None,
    target: dict[str, object] | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    if target is None and command_type.startswith("ptz_"):
        target = {
            "kind": "ptz",
            "source_tent_id": 1,
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
        }
    command = {
        "command_id": command_id,
        "site_id": "homebox",
        "target": target,
        "command_type": command_type,
        "payload": payload or {"preset_id": "overview"},
        "status": "claimed",
        "queued_at": (FIXED_NOW - timedelta(seconds=5)).isoformat(),
        "expires_at": (expires_at or FIXED_NOW + timedelta(seconds=55)).isoformat(),
        "claimed_by": "gateway-main",
        "claimed_at": FIXED_NOW.isoformat(),
        "requested_by": "admin",
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
    return command


async def _site_and_tent_pks(
    session: AsyncSession,
    *,
    tent_id: str = "main",
) -> tuple[int, int]:
    site_pk = (
        await session.exec(select(Site.id).where(Site.is_default.is_(True)))
    ).one()
    tent_pk = await resolve_test_tent_pk(session, tent_id, site_pk=site_pk)
    assert tent_pk is not None
    return site_pk, tent_pk


async def _seed_seed_lot_for_commands(
    engine: AsyncEngine,
    *,
    project_code: str,
    generation_label: str,
    existing_keys: list[str] | None = None,
) -> int:
    async with AsyncSession(engine) as session:
        line = PlantLine(
            project_code=project_code,
            generation_label=generation_label,
            strain=f"{project_code} Strain",
            cultivar=f"{project_code} Cultivar",
            source_name=f"{project_code} source",
        )
        session.add(line)
        await session.flush()
        seed_lot = SeedLot(
            line_id=line.id,
            sex_type_key="regular",
            is_purchased=True,
            vendor_name="Fixture vendor",
        )
        session.add(seed_lot)
        await session.flush()
        for key in existing_keys or []:
            session.add(
                Plant(
                    key=key,
                    line_id=line.id,
                    sex_key="unknown",
                    source_seed_lot_id=seed_lot.id,
                    name=key,
                )
            )
        seed_lot_id = seed_lot.id
        await session.commit()
        return seed_lot_id


async def _seed_command_plants(
    engine: AsyncEngine,
    *,
    prefix: str,
    count: int,
    tent_id: str = "main",
    current_start: datetime | None = None,
) -> list[str]:
    async with AsyncSession(engine) as session:
        site_pk, tent_pk = await _site_and_tent_pks(session, tent_id=tent_id)
        line = PlantLine(
            project_code=prefix,
            generation_label="T1",
            strain=f"{prefix} Strain",
            cultivar=f"{prefix} Cultivar",
            source_name=f"{prefix} source",
        )
        session.add(line)
        await session.flush()
        seed_lot = SeedLot(
            line_id=line.id,
            sex_type_key="regular",
            is_purchased=True,
            vendor_name="Fixture vendor",
        )
        session.add(seed_lot)
        await session.flush()
        plant_keys: list[str] = []
        for index in range(1, count + 1):
            key = f"{prefix}-T1-{index:03d}"
            plant = Plant(
                key=key,
                line_id=line.id,
                sex_key="unknown",
                source_seed_lot_id=seed_lot.id,
                name=key,
                germinated_at=FIXED_NOW - timedelta(days=7),
                veg_started_at=FIXED_NOW - timedelta(days=7),
            )
            session.add(plant)
            await session.flush()
            if current_start is not None:
                session.add(
                    PlantLocationHistory(
                        plant_id=plant.id,
                        site_id=site_pk,
                        tent_id=tent_pk,
                        grid_position=f"{prefix}{index}",
                        start_at=current_start,
                    )
                )
            plant_keys.append(key)
        await session.commit()
        return plant_keys


async def _seed_parent_plants(engine: AsyncEngine) -> tuple[str, str]:
    async with AsyncSession(engine) as session:
        line = PlantLine(
            project_code="PAR",
            generation_label="P1",
            strain="Parent Strain",
            cultivar="Parent Cultivar",
            source_name="Parent fixture",
        )
        session.add(line)
        await session.flush()
        seed_parent = Plant(
            key="PAR-P1-SEED",
            line_id=line.id,
            sex_key="female",
            name="Seed Parent",
        )
        pollen_parent = Plant(
            key="PAR-P1-POLLEN",
            line_id=line.id,
            sex_key="reversed",
            name="Pollen Parent",
        )
        session.add_all([seed_parent, pollen_parent])
        seed_key = seed_parent.key
        pollen_key = pollen_parent.key
        await session.commit()
        return seed_key, pollen_key


async def _seed_mother_for_clone(engine: AsyncEngine) -> str:
    async with AsyncSession(engine) as session:
        line = PlantLine(
            project_code="MOM",
            generation_label="T1",
            strain="Mother Strain",
            cultivar="Mother Cultivar",
            source_name="Mother fixture",
        )
        session.add(line)
        await session.flush()
        mother = Plant(
            key="MOM-001",
            line_id=line.id,
            sex_key="female",
            name="Mother Plant",
        )
        session.add(mother)
        mother_key = mother.key
        await session.commit()
        return mother_key


async def _seed_temperature_readings(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        cap = (
            await session.exec(
                select(Capability)
                .join(Device, Device.id == Capability.device_id)
                .join(Tent, Tent.id == Device.tent_id)
                .where(Tent.is_default.is_(True))
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


async def _seed_history_rollup_readings(engine: AsyncEngine) -> set[str]:
    readings_by_metric = {
        "temperature_f": ("F", [72.0, 74.0]),
        "humidity_pct": ("%", [50.0, 55.0]),
        "vpd_kpa": ("kPa", [1.1, 1.3]),
        "reservoir_in": ("in", [7.0, 7.5]),
        "reservoir_ph": ("pH", [6.1, 6.3]),
        "substrate_temp_c": ("degC", [21.1, 21.4]),
        "substrate_ec_us_cm": ("us/cm", [1400.0, 1500.0]),
        "substrate_ph": ("pH", [5.8, 6.0]),
        "dehumidifier_on": ("bool", [0.0, 1.0, 1.0]),
        "reservoir_ph_voltage": ("V", [1.2, 1.3]),
        "temperature_c": ("C", [22.2, 23.3]),
    }
    device_ids = {"test-history-node", "test-history-moisture"}
    async with AsyncSession(engine) as session:
        site_pk, tent_pk = await _site_and_tent_pks(session)
        tent = (await session.exec(select(Tent).where(Tent.id == tent_pk))).one()
        device = Device(
            site_id=site_pk,
            tent_id=tent.id,
            device_id="test-history-node",
            name="Test History Node",
            kind="test",
            controller="test",
        )
        session.add(device)
        await session.flush()
        for metric, (unit, values) in readings_by_metric.items():
            capability = Capability(
                device_id=device.id,
                capability_id=metric,
                name=metric,
                kind="measurement",
                metric_name=metric,
                unit=unit,
                source="test",
            )
            session.add(capability)
            await session.flush()
            for index, value in enumerate(values, start=1):
                session.add(
                    SensorReading(
                        ts=FIXED_NOW - timedelta(minutes=index),
                        capability_id=capability.id,
                        metric=metric,
                        value=value,
                        source=SensorSource.ESP32,
                    )
                )

        moisture_device = Device(
            site_id=site_pk,
            tent_id=tent.id,
            device_id="test-history-moisture",
            name="Test History Moisture",
            kind="moisture_node",
            controller="test",
        )
        session.add(moisture_device)
        await session.flush()
        moisture_capability = Capability(
            device_id=moisture_device.id,
            capability_id="soil_moisture_pct",
            name="Soil Moisture",
            kind="measurement",
            metric_name="soil_moisture_pct",
            unit="%",
            source="test",
        )
        session.add(moisture_capability)
        await session.flush()
        for index, value in enumerate([30.0, 40.0, 50.0], start=1):
            session.add(
                SensorReading(
                    ts=FIXED_NOW - timedelta(minutes=index),
                    capability_id=moisture_capability.id,
                    metric="soil_moisture_pct",
                    value=value,
                    source=SensorSource.ESP32,
                )
            )
        await session.commit()
    return device_ids


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
    assert cloud.call_counts["wiki"] == 1
    assert (
        "homebox",
        1,
        "fan-controller",
        "temperature_f",
        "temperature_f",
    ) in cloud.latest_rows
    assert any(key[5] == "4h" for key in cloud.rollup_rows)
    assert any(key[5] == "1d" for key in cloud.rollup_rows)


async def test_collect_rollups_filters_history_from_metric_registry(
    app_engine: AsyncEngine,
) -> None:
    device_ids = await _seed_history_rollup_readings(app_engine)

    payload = await GatewayLocalServiceBundle(
        app_engine, clock=lambda: FIXED_NOW
    ).collect_rollups("homebox", bucket_names={"5m"})

    rollups = [item for item in payload.rollups if item.device_id in device_ids]
    metrics = {item.metric for item in rollups}

    assert {
        "temperature_f",
        "humidity_pct",
        "vpd_kpa",
        "reservoir_in",
        "reservoir_ph",
        "dehumidifier_runtime_pct",
        "soil_moisture_pct",
        *SUBSTRATE_HISTORY_METRICS,
    } <= metrics
    assert "dehumidifier_on" not in metrics
    assert "soil_moisture_raw" not in metrics
    assert "reservoir_ph_voltage" not in metrics
    assert "temperature_c" not in metrics
    moisture_rollups = [item for item in rollups if item.metric == "soil_moisture_pct"]
    assert moisture_rollups
    assert {item.capability_id for item in moisture_rollups} == {"soil_moisture_pct"}
    assert {item.unit for item in moisture_rollups} == {"%"}
    dehumidifier_rollups = [
        item for item in rollups if item.metric == "dehumidifier_runtime_pct"
    ]
    assert dehumidifier_rollups
    assert {item.capability_id for item in dehumidifier_rollups} == {"dehumidifier_on"}
    assert {item.unit for item in dehumidifier_rollups} == {"%"}
    assert {item.avg_value for item in dehumidifier_rollups} == {66.6667}
    substrate_rollups = [
        item for item in rollups if item.metric in SUBSTRATE_HISTORY_METRICS
    ]
    assert {item.metric for item in substrate_rollups} == SUBSTRATE_HISTORY_METRICS
    assert {(item.metric, item.unit) for item in substrate_rollups} == {
        ("substrate_temp_c", "degC"),
        ("substrate_ec_us_cm", "us/cm"),
        ("substrate_ph", "pH"),
    }


async def test_collect_rollups_disables_substrate_from_registry(
    app_engine: AsyncEngine,
) -> None:
    device_ids = await _seed_history_rollup_readings(app_engine)
    async with AsyncSession(app_engine) as session:
        substrate_rows = (
            await session.exec(
                select(MetricPresentation).where(
                    MetricPresentation.metric.in_(SUBSTRATE_HISTORY_METRICS)
                )
            )
        ).all()
        assert {row.metric for row in substrate_rows} == SUBSTRATE_HISTORY_METRICS
        for row in substrate_rows:
            row.history_enabled = False
            session.add(row)
        await session.commit()

    payload = await GatewayLocalServiceBundle(
        app_engine, clock=lambda: FIXED_NOW
    ).collect_rollups("homebox", bucket_names={"5m"})

    metrics = {item.metric for item in payload.rollups if item.device_id in device_ids}
    assert "soil_moisture_pct" in metrics
    assert SUBSTRATE_HISTORY_METRICS.isdisjoint(metrics)


async def test_collect_rollups_disables_legacy_moisture_from_registry(
    app_engine: AsyncEngine,
) -> None:
    device_ids = await _seed_history_rollup_readings(app_engine)
    async with AsyncSession(app_engine) as session:
        moisture = (
            await session.exec(
                select(MetricPresentation).where(
                    MetricPresentation.metric == "soil_moisture_pct"
                )
            )
        ).one()
        moisture.history_enabled = False
        session.add(moisture)
        await session.commit()

    payload = await GatewayLocalServiceBundle(
        app_engine, clock=lambda: FIXED_NOW
    ).collect_rollups("homebox", bucket_names={"5m"})

    metrics = {item.metric for item in payload.rollups if item.device_id in device_ids}
    assert "temperature_f" in metrics
    assert "soil_moisture_pct" not in metrics
    assert "soil_moisture_raw" not in metrics


async def test_collect_rollups_fails_closed_without_history_registry(
    app_engine: AsyncEngine,
) -> None:
    await _seed_history_rollup_readings(app_engine)
    async with AsyncSession(app_engine) as session:
        await session.exec(text("DELETE FROM metric_presentation"))
        await session.commit()

    payload = await GatewayLocalServiceBundle(
        app_engine, clock=lambda: FIXED_NOW
    ).collect_rollups("homebox", bucket_names={"5m"})

    assert payload.rollups == []


def test_canonical_rollup_projection_has_no_legacy_moisture_path() -> None:
    canonical_source = inspect.getsource(
        gateway_local.collect_canonical_history_rollups
    )

    assert "sensorcalibration" not in canonical_source
    assert "UNION ALL" not in canonical_source.upper()
    assert "soil_moisture_raw" not in canonical_source
    assert "soil_moisture_pct" not in canonical_source


async def test_collect_metrics_syncs_only_direct_plant_moisture_pct(
    app_engine: AsyncEngine,
) -> None:
    async with AsyncSession(app_engine) as session:
        site_pk, tent_pk = await _site_and_tent_pks(session)
        tent = (await session.exec(select(Tent).where(Tent.id == tent_pk))).one()
        plant_a_zone_id = await resolve_test_zone_pk(
            session,
            "plant-a",
            site_pk=site_pk,
            tent_pk=tent.id,
        )
        assert plant_a_zone_id is not None
        plant_a_zone = (
            await session.exec(select(Zone).where(Zone.id == plant_a_zone_id))
        ).one()
        plant_a_zone_id = plant_a_zone.id
        direct_device = Device(
            site_id=site_pk,
            tent_id=tent.id,
            zone_id=plant_a_zone.id,
            device_id="test-direct-moisture-node",
            name="Test Direct Moisture Node",
            kind="moisture_node",
            controller="test",
        )
        session.add(direct_device)
        await session.flush()
        direct_capability = Capability(
            device_id=direct_device.id,
            capability_id="soil_moisture_pct",
            name="Soil Moisture",
            kind="measurement",
            metric_name="soil_moisture_pct",
            unit="%",
            source="test",
        )
        session.add(direct_capability)
        await session.flush()
        raw_device = Device(
            site_id=site_pk,
            tent_id=tent.id,
            device_id="test-raw-moisture-node",
            name="Test Raw Moisture Node",
            kind="moisture_node",
            controller="test",
        )
        session.add(raw_device)
        await session.flush()
        raw_capability = Capability(
            device_id=raw_device.id,
            capability_id="soil_moisture_raw",
            name="Soil Moisture Raw",
            kind="measurement",
            metric_name="soil_moisture_raw",
            unit="raw",
            source="test",
        )
        session.add(raw_capability)
        await session.flush()
        plant_a = (
            await session.exec(select(Plant).where(Plant.key == "SBBS-R1-001"))
        ).one()
        plant_b = (
            await session.exec(select(Plant).where(Plant.key == "SBBS-R1-002"))
        ).one()
        session.add_all(
            [
                PlantMetricStream(
                    plant_id=plant_a.id,
                    capability_id=direct_capability.id,
                    is_active=True,
                ),
                PlantMetricStream(
                    plant_id=plant_b.id,
                    capability_id=raw_capability.id,
                    is_active=True,
                ),
            ]
        )
        session.add_all(
            [
                SensorReading(
                    ts=FIXED_NOW - timedelta(minutes=10),
                    capability_id=direct_capability.id,
                    metric="soil_moisture_pct",
                    value=30.0,
                    source=SensorSource.ESP32,
                ),
                SensorReading(
                    ts=FIXED_NOW - timedelta(minutes=5),
                    capability_id=direct_capability.id,
                    metric="soil_moisture_pct",
                    value=45.0,
                    source=SensorSource.ESP32,
                ),
                SensorReading(
                    ts=FIXED_NOW - timedelta(minutes=1),
                    capability_id=raw_capability.id,
                    metric="soil_moisture_raw",
                    value=1000.0,
                    source=SensorSource.ESP32,
                ),
            ]
        )
        await session.commit()

    bundle = GatewayLocalServiceBundle(app_engine, clock=lambda: FIXED_NOW)
    latest = await bundle.collect_latest_metrics("homebox")
    rollups = await bundle.collect_rollups("homebox", bucket_names={"5m"})

    latest_pct = [
        item
        for item in latest.metrics
        if item.metric == "soil_moisture_pct"
        and item.device_id in {"test-direct-moisture-node", "test-raw-moisture-node"}
    ]
    rollup_pct = [
        item
        for item in rollups.rollups
        if item.metric == "soil_moisture_pct"
        and item.device_id in {"test-direct-moisture-node", "test-raw-moisture-node"}
    ]
    assert len(latest_pct) == 1
    assert latest_pct[0].device_id == "test-direct-moisture-node"
    assert latest_pct[0].source_zone_id == plant_a_zone_id
    assert latest_pct[0].capability_id == "soil_moisture_pct"
    assert latest_pct[0].value == 45.0
    assert latest_pct[0].unit == "%"
    assert rollup_pct
    assert {item.device_id for item in rollup_pct} == {"test-direct-moisture-node"}
    assert {item.capability_id for item in rollup_pct} == {"soil_moisture_pct"}
    assert {item.unit for item in rollup_pct} == {"%"}


async def test_collect_catalog_projects_current_grow_plants(
    app_engine: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    wiki_root = tmp_path / "wiki"
    plant_dir = wiki_root / "grows" / "test-grow" / "plants"
    plant_dir.mkdir(parents=True)
    (plant_dir / "plant-x1.md").write_text("# Test X1\n", encoding="utf-8")
    monkeypatch.setattr(gateway_local, "WIKI_ROOT", wiki_root)

    async with AsyncSession(app_engine) as session:
        site_pk, _ = await _site_and_tent_pks(session)
        tent = Tent(
            site_id=site_pk,
            name="Test Plants",
            role="test",
        )
        session.add(tent)
        await session.flush()
        test_tent_source_id = tent.id
        device = Device(
            site_id=site_pk,
            tent_id=tent.id,
            device_id="test-plant-node",
            name="Test Plant Node",
            kind="moisture_node",
            controller="test",
        )
        session.add(device)
        await session.flush()
        capability = Capability(
            device_id=device.id,
            capability_id="soil_moisture_raw",
            name="Soil Moisture Raw",
            kind="measurement",
            metric_name="soil_moisture_raw",
            unit="raw",
            source="test",
        )
        session.add(capability)
        await session.flush()
        line = PlantLine(
            project_code="TEST",
            generation_label="R1",
            strain="Test Strain",
            cultivar="Test Cultivar",
            source_name="Test source",
        )
        unused_line = PlantLine(
            project_code="IDLE",
            generation_label="F1",
            strain="Idle Strain",
            cultivar="Idle Cultivar",
            source_name="Idle source",
        )
        session.add_all([line, unused_line])
        await session.flush()
        seed_lot = SeedLot(
            line_id=line.id,
            sex_type_key="regular",
            is_purchased=True,
            vendor_name="Test vendor",
        )
        unused_seed_lot = SeedLot(
            line_id=unused_line.id,
            sex_type_key="feminized",
            is_purchased=True,
            vendor_name="Unused vendor",
            seed_count=5,
            notes="No current plants yet.",
        )
        session.add_all([seed_lot, unused_seed_lot])
        await session.flush()
        plant_x1 = Plant(
            key="TEST-R1-001",
            line_id=line.id,
            sex_key="female",
            source_seed_lot_id=seed_lot.id,
            name="Test X1",
        )
        plant_x2 = Plant(
            key="TEST-R1-002",
            line_id=line.id,
            sex_key="male",
            source_seed_lot_id=seed_lot.id,
            name="Test X2",
            culled_at=FIXED_NOW,
            culled_reason="test fixture culled",
        )
        plant_x3 = Plant(
            key="TEST-R1-003",
            line_id=line.id,
            sex_key="unknown",
            source_seed_lot_id=seed_lot.id,
            name="Test X3",
            culled_at=FIXED_NOW - timedelta(days=1),
            culled_reason="moved out of active test",
        )
        session.add_all([plant_x1, plant_x2, plant_x3])
        await session.flush()
        line_source_id = line.id
        seed_lot_source_id = seed_lot.id
        unused_line_source_id = unused_line.id
        unused_seed_lot_source_id = unused_seed_lot.id
        plant_x1_source_id = plant_x1.id
        plant_x2_source_id = plant_x2.id
        plant_x3_source_id = plant_x3.id
        cross_event = CrossEvent(
            resulting_line_id=line.id,
            seed_parent_plant_id=plant_x1.id,
            pollen_parent_plant_id=plant_x2.id,
            pollinated_at=FIXED_NOW,
            pollen_parent_is_reversed=None,
            notes=None,
        )
        note = PlantNote(
            plant_id=plant_x1.id,
            observed_at=FIXED_NOW + timedelta(hours=1),
            body="Strong lateral branching.",
            created_by=None,
        )
        event = PlantEvent(
            plant_id=plant_x1.id,
            is_sex_observation=True,
            occurred_at=FIXED_NOW + timedelta(hours=2),
            reason=None,
            notes=None,
            metadata_json={"sex_key": "female"},
        )
        closed_location_note = PlantNote(
            plant_id=plant_x3.id,
            observed_at=FIXED_NOW + timedelta(hours=3),
            body="Archived plant still has timeline notes.",
            created_by=None,
        )
        closed_location_event = PlantEvent(
            plant_id=plant_x3.id,
            is_selection_for_breeding=True,
            occurred_at=FIXED_NOW + timedelta(hours=4),
            reason="archival review",
            notes=None,
            metadata_json={},
        )
        session.add_all(
            [cross_event, note, event, closed_location_note, closed_location_event]
        )
        await session.flush()
        cross_event_source_id = cross_event.id
        note_source_id = note.id
        event_source_id = event.id
        closed_location_note_source_id = closed_location_note.id
        closed_location_event_source_id = closed_location_event.id
        session.add_all(
            [
                PlantLocationHistory(
                    plant_id=plant_x1.id,
                    site_id=site_pk,
                    tent_id=tent.id,
                    grid_position="A1",
                    start_at=FIXED_NOW,
                ),
                PlantLocationHistory(
                    plant_id=plant_x2.id,
                    site_id=site_pk,
                    tent_id=tent.id,
                    grid_position="B1",
                    start_at=FIXED_NOW,
                ),
                PlantLocationHistory(
                    plant_id=plant_x3.id,
                    site_id=site_pk,
                    tent_id=tent.id,
                    grid_position="C1",
                    start_at=FIXED_NOW - timedelta(days=10),
                    end_at=FIXED_NOW - timedelta(days=9),
                ),
                PlantLocationHistory(
                    plant_id=plant_x3.id,
                    site_id=site_pk,
                    tent_id=tent.id,
                    grid_position="C1",
                    start_at=FIXED_NOW - timedelta(days=8),
                    end_at=FIXED_NOW - timedelta(days=7),
                ),
                PlantMetricStream(
                    plant_id=plant_x1.id,
                    capability_id=capability.id,
                    display_order=7,
                    is_active=True,
                ),
            ]
        )
        await session.commit()

    payload = await GatewayLocalServiceBundle(
        app_engine, clock=lambda: FIXED_NOW
    ).collect_catalog("homebox")

    test_locations = [
        location
        for location in payload.plant_locations
        if location.source_tent_id == test_tent_source_id
    ]
    test_source_ids = {location.source_plant_id for location in test_locations}
    plant_lines = [
        line
        for line in payload.plant_lines
        if line.source_line_id in {line_source_id, unused_line_source_id}
    ]
    seed_lots = [
        seed_lot
        for seed_lot in payload.seed_lots
        if seed_lot.source_seed_lot_id
        in {seed_lot_source_id, unused_seed_lot_source_id}
    ]
    plants = [
        plant for plant in payload.plants if plant.source_plant_id in test_source_ids
    ]
    assert plants == [
        CatalogPlant(
            source_plant_id=plant_x1_source_id,
            line_source_id=line_source_id,
            sex_key="female",
            source_seed_lot_id=seed_lot_source_id,
            clone_source_plant_id=None,
            key="TEST-R1-001",
            name="Test X1",
            germinated_at=None,
            rooted_at=None,
            veg_started_at=None,
            flower_started_at=None,
            culled_at=None,
            culled_reason=None,
            harvested_at=None,
            selected_for_breeding_at=None,
            selected_for_breeding_reason=None,
            is_active=True,
        ),
        CatalogPlant(
            source_plant_id=plant_x2_source_id,
            line_source_id=line_source_id,
            sex_key="male",
            source_seed_lot_id=seed_lot_source_id,
            clone_source_plant_id=None,
            key="TEST-R1-002",
            name="Test X2",
            germinated_at=None,
            rooted_at=None,
            veg_started_at=None,
            flower_started_at=None,
            culled_at=FIXED_NOW,
            culled_reason="test fixture culled",
            harvested_at=None,
            selected_for_breeding_at=None,
            selected_for_breeding_reason=None,
            is_active=False,
        ),
        CatalogPlant(
            source_plant_id=plant_x3_source_id,
            line_source_id=line_source_id,
            sex_key="unknown",
            source_seed_lot_id=seed_lot_source_id,
            clone_source_plant_id=None,
            key="TEST-R1-003",
            name="Test X3",
            germinated_at=None,
            rooted_at=None,
            veg_started_at=None,
            flower_started_at=None,
            culled_at=FIXED_NOW - timedelta(days=1),
            culled_reason="moved out of active test",
            harvested_at=None,
            selected_for_breeding_at=None,
            selected_for_breeding_reason=None,
            is_active=False,
        ),
    ]
    assert {line.source_line_id: line.strain for line in plant_lines} == {
        line_source_id: "Test Strain",
        unused_line_source_id: "Idle Strain",
    }
    assert {
        seed_lot.source_seed_lot_id: (
            seed_lot.line_source_id,
            seed_lot.sex_type_key,
            seed_lot.seed_count,
            seed_lot.notes,
        )
        for seed_lot in seed_lots
    } == {
        seed_lot_source_id: (line_source_id, "regular", None, None),
        unused_seed_lot_source_id: (
            unused_line_source_id,
            "feminized",
            5,
            "No current plants yet.",
        ),
    }
    assert [
        (location.source_plant_id, location.grid_position, location.end_at)
        for location in test_locations
    ] == [
        (plant_x1_source_id, "A1", None),
        (plant_x2_source_id, "B1", None),
        (plant_x3_source_id, "C1", FIXED_NOW - timedelta(days=9)),
        (plant_x3_source_id, "C1", FIXED_NOW - timedelta(days=7)),
    ]
    cross_events = [
        cross_event
        for cross_event in payload.cross_events
        if cross_event.source_cross_event_id == cross_event_source_id
    ]
    plant_notes = [
        note for note in payload.plant_notes if note.source_note_id == note_source_id
    ]
    closed_location_notes = [
        note
        for note in payload.plant_notes
        if note.source_note_id == closed_location_note_source_id
    ]
    plant_events = [
        event
        for event in payload.plant_events
        if event.source_event_id == event_source_id
    ]
    closed_location_events = [
        event
        for event in payload.plant_events
        if event.source_event_id == closed_location_event_source_id
    ]
    assert len(cross_events) == 1
    assert cross_events[0].seed_parent_source_plant_id == plant_x1_source_id
    assert cross_events[0].pollen_parent_source_plant_id == plant_x2_source_id
    assert cross_events[0].pollen_parent_is_reversed is None
    assert cross_events[0].notes is None
    assert len(plant_notes) == 1
    assert plant_notes[0].source_plant_id == plant_x1_source_id
    assert plant_notes[0].body == "Strong lateral branching."
    assert plant_notes[0].created_by is None
    assert len(closed_location_notes) == 1
    assert closed_location_notes[0].source_plant_id == plant_x3_source_id
    assert closed_location_notes[0].body == "Archived plant still has timeline notes."
    assert len(plant_events) == 1
    assert plant_events[0].source_plant_id == plant_x1_source_id
    assert plant_events[0].is_sex_observation is True
    assert plant_events[0].reason is None
    assert plant_events[0].notes is None
    assert plant_events[0].metadata == {"sex_key": "female"}
    assert len(closed_location_events) == 1
    assert closed_location_events[0].source_plant_id == plant_x3_source_id
    assert closed_location_events[0].is_selection_for_breeding is True
    assert closed_location_events[0].reason == "archival review"
    plant_metric_streams = [
        stream
        for stream in payload.plant_metric_streams
        if stream.source_plant_id in test_source_ids
    ]
    assert plant_metric_streams == [
        CatalogPlantMetricStream(
            source_plant_id=plant_x1_source_id,
            device_id="test-plant-node",
            capability_id="soil_moisture_raw",
            metric="soil_moisture_raw",
            display_order=7,
            is_active=True,
        )
    ]


async def test_collect_catalog_projects_current_scope_boundary_fields(
    app_engine: AsyncEngine,
):
    payload = await GatewayLocalServiceBundle(
        app_engine, clock=lambda: FIXED_NOW
    ).collect_catalog("homebox")

    tent_source_ids = {tent.source_tent_id for tent in payload.tents}
    device_by_id = {device.device_id: device for device in payload.devices}
    light_schedules = [
        schedule for schedule in payload.schedules if schedule.kind == "lights"
    ]

    assert payload.site_id == "homebox"
    assert payload.site.source_site_id > 0
    assert light_schedules
    for schedule in light_schedules:
        assert schedule.source_site_id == payload.site.source_site_id
        assert schedule.source_tent_id in tent_source_ids
        assert schedule.source_schedule_id > 0
        assert schedule.timezone
        assert schedule.starts_local is not None
        assert schedule.ends_local is not None
        if schedule.device_id is not None:
            assert (
                device_by_id[schedule.device_id].source_tent_id
                == schedule.source_tent_id
            )

    for device in payload.devices:
        serialized = device.model_dump()
        assert "last_seen_at" in serialized
        assert device.source_tent_id in tent_source_ids
        assert "tent_id" not in serialized


async def test_collect_wiki_pages_projects_grow_run_plant_markdown(
    app_engine: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wiki_root = tmp_path / "wiki"
    plant_dir = wiki_root / "grows" / "main-2026-03-15" / "plants"
    plant_dir.mkdir(parents=True)
    (wiki_root / "AGENTS.md").write_text("private agent notes\n", encoding="utf-8")
    page_path = plant_dir / "plant-a.md"
    page_path.write_text(
        "\n".join(
            [
                "---",
                "title: Plant A",
                "type: plant",
                "sources: [raw/chat-history/all-chat-summary.md, memory.md]",
                "purple: true",
                "---",
                "# Plant A",
                "",
                "Body text.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gateway_local, "WIKI_ROOT", wiki_root)

    payload = await GatewayLocalServiceBundle(
        app_engine, clock=lambda: FIXED_NOW
    ).collect_wiki_pages("homebox")

    assert payload.site_id == "homebox"
    assert payload.generated_at == FIXED_NOW
    assert payload.excluded_paths == [
        "wiki/AGENTS.md",
        "wiki/private/**",
        "wiki/raw/**",
    ]
    assert len(payload.content_hash) == 64
    assert len(payload.pages) == 1
    page = payload.pages[0]
    assert page.path == "wiki/grows/main-2026-03-15/plants/plant-a.md"
    assert page.title == "Plant A"
    assert page.frontmatter == {
        "title": "Plant A",
        "type": "plant",
        "sources": ["raw/chat-history/all-chat-summary.md", "memory.md"],
        "purple": True,
    }
    assert page.body_markdown == "# Plant A\n\nBody text.\n"
    assert len(page.sha256) == 64


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
            "site_id": "homebox",
            "site": {"source_site_id": 1, "name": "Homebox", "timezone": "UTC"},
            "tents": [],
            "zones": [],
            "devices": [
                {
                    "source_tent_id": 1,
                    "source_zone_id": None,
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


async def test_large_rollup_projection_is_delivered_in_chunks(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    service = _service(
        app_engine,
        cloud,
        local_services=ManyRollupLocalServices(),
    )

    result = await service.run_once()

    assert result.failed == 0
    assert cloud.call_counts["rollups"] == 3
    assert len(cloud.rollup_rows) == 1201
    async with AsyncSession(app_engine) as session:
        rows = (
            await session.exec(
                select(CloudOutbox)
                .where(CloudOutbox.event_type == "rollups")
                .order_by(CloudOutbox.id)
            )
        ).all()
    assert [row.status for row in rows] == ["delivered", "delivered", "delivered"]
    assert [len(row.payload["rollups"]) for row in rows] == [500, 500, 201]


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
    now = FIXED_NOW + timedelta(days=1)
    await service.run_once()

    assert local.requests == [
        frozenset({"5m", "1h", "4h", "1d"}),
        frozenset({"5m"}),
        frozenset({"5m", "1h"}),
        frozenset({"5m", "1h", "4h"}),
        frozenset({"5m", "1h", "4h", "1d"}),
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
    assert "tent_id" not in asset_row.payload["sign_request"]
    assert "tent_id" not in asset_row.payload["complete_request"]
    assert "zone_id" not in asset_row.payload["complete_request"]
    assert cloud.assets["asset-1"]["object_key"] == "tents/1/snapshots/snapshot.jpg"


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
                "source_tent_id": 1,
                "content_type": "image/jpeg",
                "object_key": "tents/1/snapshots/snapshot.jpg",
                "asset_id": "asset-1",
                "sha256": "asset-1",
                "kind": "periodic",
            },
            "complete_request": {
                "site_id": "homebox",
                "source_tent_id": 1,
                "content_type": "image/jpeg",
                "byte_size": len(b"jpeg-bytes"),
                "object_key": "tents/1/snapshots/snapshot.jpg",
                "asset_id": "asset-1",
                "sha256": "asset-1",
                "kind": "periodic",
                "captured_at": FIXED_NOW.isoformat(),
                "source_zone_id": None,
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


async def test_command_result_outbox_replay_validates_stored_json_before_cloud_call(
    app_engine: AsyncEngine,
):
    outbox = OutboxRepository(app_engine)
    await outbox.enqueue(
        event_type="command_result",
        idempotency_key="homebox:command_result:bad-result",
        payload={
            "command_id": "cloud-bad-result",
            "result": {
                "site_id": "homebox",
                "result": {"ok": True},
                "error": None,
            },
        },
        now=FIXED_NOW - timedelta(minutes=1),
    )
    cloud = RecordingCloudClient()
    service = _service(app_engine, cloud, local_services=StaticLocalServices())

    result = await service.run_once()

    assert result.failed == 1
    assert cloud.call_counts["command_result"] == 0
    async with AsyncSession(app_engine) as session:
        row = (
            await session.exec(
                select(CloudOutbox).where(
                    CloudOutbox.idempotency_key == "homebox:command_result:bad-result"
                )
            )
        ).one()
    assert row.status == "pending"
    assert row.attempt_count == 1
    assert "status" in str(row.last_error)


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
    assert "tent_id" not in cloud.asset_failures[0]
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
        (command_id, payload.status)
        for command_id, payload, _key in cloud.command_results
    ] == [("cloud-1", "running"), ("cloud-1", "succeeded")]
    assert isinstance(cloud.command_results[0][1], CommandResultRequest)
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


async def test_command_loop_uses_ptz_target_for_local_scope(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-target",
            target={
                "kind": "ptz",
                "source_tent_id": 1,
                "device_id": "obsbot-main",
                "capability_id": "ptz_move",
            },
            payload={"preset_id": "overview"},
        )
    ]
    ptz = RecordingPTZ()

    result = await _command_service(app_engine, cloud, ptz).run_once()

    assert result.executed == 1
    assert ptz.calls == [("preset", "overview")]
    async with AsyncSession(app_engine) as session:
        command = (
            await session.exec(
                select(Command).where(
                    Command.idempotency_key == "cloud-command:cloud-target"
                )
            )
        ).one()
    assert command.tent_id == 1
    assert command.device_id is not None
    assert command.capability_id is not None


async def test_command_loop_executes_purchased_seed_lot_create(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-seed-purchased",
            command_type="breeding_seed_lot_create",
            payload={
                "source": "purchased",
                "generation": "F4",
                "prefix": "PUR",
                "sex_type_key": "regular",
                "strain": "Purchased Strain",
                "cultivar": "Purchased Cultivar",
                "source_name": "Pack 12",
                "vendor_name": "Seed Vendor",
                "seed_count": 12,
                "notes": "Kept refrigerated.",
            },
        )
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 1
    assert [payload.status for _, payload, _ in cloud.command_results] == [
        "running",
        "succeeded",
    ]
    async with AsyncSession(app_engine) as session:
        command = (
            await session.exec(
                select(Command).where(
                    Command.idempotency_key == "cloud-command:cloud-seed-purchased"
                )
            )
        ).one()
        seed_lot = await session.get(SeedLot, command.result["source_seed_lot_id"])
        line = await session.get(PlantLine, command.result["line_id"])

    assert command.command_type == "breeding.seed_lot.create"
    assert command.tent_id is None
    assert seed_lot is not None
    assert seed_lot.is_purchased is True
    assert seed_lot.vendor_name == "Seed Vendor"
    assert seed_lot.seed_count == 12
    assert line is not None
    assert line.project_code == "PUR"
    assert line.generation_label == "F4"


async def test_command_loop_executes_cross_seed_lot_create(
    app_engine: AsyncEngine,
):
    seed_key, pollen_key = await _seed_parent_plants(app_engine)
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-seed-cross",
            command_type="breeding_seed_lot_create",
            payload={
                "source": "cross",
                "generation": "F1",
                "prefix": "XCR",
                "sex_type_key": "feminized",
                "seed_parent_plant_key": seed_key,
                "pollen_parent_plant_key": pollen_key,
                "pollinated_at": FIXED_NOW.isoformat(),
                "pollen_parent_is_reversed": True,
                "seed_count": 24,
                "notes": "Controlled branch pollination.",
            },
        )
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 1
    async with AsyncSession(app_engine) as session:
        command = (
            await session.exec(
                select(Command).where(
                    Command.idempotency_key == "cloud-command:cloud-seed-cross"
                )
            )
        ).one()
        seed_lot = await session.get(SeedLot, command.result["source_seed_lot_id"])
        cross = await session.get(CrossEvent, command.result["source_cross_event_id"])

    assert command.status == "succeeded"
    assert seed_lot is not None
    assert seed_lot.is_purchased is False
    assert (
        seed_lot.produced_by_cross_event_id == command.result["source_cross_event_id"]
    )
    assert cross is not None
    assert cross.pollen_parent_is_reversed is True


async def test_command_loop_germinates_plants_with_local_key_suffixes(
    app_engine: AsyncEngine,
):
    seed_lot_id = await _seed_seed_lot_for_commands(
        app_engine,
        project_code="GERM",
        generation_label="R1",
        existing_keys=["GERM-R1-001"],
    )
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-germinate",
            command_type="breeding_plants_germinate",
            payload={
                "seed_lot_source_id": seed_lot_id,
                "count": 2,
                "source_tent_id": 1,
                "grid_position": None,
                "germinated_at": FIXED_NOW.isoformat(),
            },
        )
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 1
    async with AsyncSession(app_engine) as session:
        plants = (
            await session.exec(
                select(Plant).where(col(Plant.key).in_(["GERM-R1-002", "GERM-R1-003"]))
            )
        ).all()
        locations = (
            await session.exec(
                select(PlantLocationHistory).where(
                    col(PlantLocationHistory.plant_id).in_(
                        [plant.id for plant in plants]
                    )
                )
            )
        ).all()
        command = (
            await session.exec(
                select(Command).where(
                    Command.idempotency_key == "cloud-command:cloud-germinate"
                )
            )
        ).one()

    assert command.result["created_plant_keys"] == ["GERM-R1-002", "GERM-R1-003"]
    assert {plant.sex_key for plant in plants} == {"unknown"}
    assert {plant.germinated_at for plant in plants} == {FIXED_NOW}
    assert {plant.veg_started_at for plant in plants} == {FIXED_NOW}
    assert {plant.flower_started_at for plant in plants} == {FIXED_NOW}
    assert {location.grid_position for location in locations} == {None}


async def test_command_loop_clones_plants_and_records_mother_event(
    app_engine: AsyncEngine,
):
    mother_key = await _seed_mother_for_clone(app_engine)
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-clone",
            command_type="breeding_plants_clone",
            payload={
                "mother_plant_key": mother_key,
                "count": 2,
                "source_tent_id": 2,
                "grid_position": None,
                "taken_at": FIXED_NOW.isoformat(),
            },
        )
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 1
    async with AsyncSession(app_engine) as session:
        clones = (
            await session.exec(
                select(Plant).where(
                    col(Plant.key).in_(["MOM-001-C-001", "MOM-001-C-002"])
                )
            )
        ).all()
        mother = (
            await session.exec(select(Plant).where(Plant.key == mother_key))
        ).one()
        event = (
            await session.exec(
                select(PlantEvent)
                .where(PlantEvent.plant_id == mother.id)
                .where(PlantEvent.is_clone_taken.is_(True))
            )
        ).one()

    assert {clone.clone_source_plant_id for clone in clones} == {mother.id}
    assert {clone.sex_key for clone in clones} == {"female"}
    assert {clone.rooted_at for clone in clones} == {FIXED_NOW}
    assert event.metadata_json == {"clone_keys": ["MOM-001-C-001", "MOM-001-C-002"]}


async def test_command_loop_bulk_sex_updates_plants_and_events(
    app_engine: AsyncEngine,
):
    plant_keys = await _seed_command_plants(app_engine, prefix="SEX", count=2)
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-sex",
            command_type="breeding_plants_bulk_sex",
            payload={"plant_keys": plant_keys, "sex_key": "female"},
        )
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 1
    async with AsyncSession(app_engine) as session:
        plants = (
            await session.exec(select(Plant).where(col(Plant.key).in_(plant_keys)))
        ).all()
        events = (
            await session.exec(
                select(PlantEvent).where(PlantEvent.is_sex_observation.is_(True))
            )
        ).all()
        command = (
            await session.exec(
                select(Command).where(
                    Command.idempotency_key == "cloud-command:cloud-sex"
                )
            )
        ).one()

    assert {plant.sex_key for plant in plants} == {"female"}
    assert {event.metadata_json["sex_key"] for event in events} >= {"female"}
    assert command.tent_id is None


async def test_command_loop_bulk_move_closes_current_location_and_starts_flower(
    app_engine: AsyncEngine,
):
    [plant_key] = await _seed_command_plants(
        app_engine,
        prefix="MOVE",
        count=1,
        tent_id="breeding",
        current_start=FIXED_NOW - timedelta(days=2),
    )
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-move",
            command_type="breeding_plants_bulk_move",
            payload={
                "plant_keys": [plant_key],
                "source_tent_id": 1,
                "grid_position": None,
            },
        )
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 1
    async with AsyncSession(app_engine) as session:
        plant = (await session.exec(select(Plant).where(Plant.key == plant_key))).one()
        locations = (
            await session.exec(
                select(PlantLocationHistory)
                .where(PlantLocationHistory.plant_id == plant.id)
                .order_by(PlantLocationHistory.start_at)
            )
        ).all()
        event = (
            await session.exec(
                select(PlantEvent)
                .where(PlantEvent.plant_id == plant.id)
                .where(PlantEvent.is_transplant.is_(True))
            )
        ).one()

    assert plant.flower_started_at == FIXED_NOW
    assert locations[0].end_at == FIXED_NOW
    assert locations[1].end_at is None
    assert locations[1].grid_position is None
    assert event.metadata_json == {"from_tent_id": 2, "to_tent_id": 1}


async def test_command_loop_bulk_cull_closes_current_location(
    app_engine: AsyncEngine,
):
    [plant_key] = await _seed_command_plants(
        app_engine,
        prefix="CULL",
        count=1,
        current_start=FIXED_NOW - timedelta(days=2),
    )
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-cull",
            command_type="breeding_plants_bulk_cull",
            payload={"plant_keys": [plant_key], "reason": "failed vigor check"},
        )
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 1
    async with AsyncSession(app_engine) as session:
        plant = (await session.exec(select(Plant).where(Plant.key == plant_key))).one()
        current_locations = (
            await session.exec(
                select(PlantLocationHistory)
                .where(PlantLocationHistory.plant_id == plant.id)
                .where(PlantLocationHistory.end_at.is_(None))
            )
        ).all()
        command = (
            await session.exec(
                select(Command).where(
                    Command.idempotency_key == "cloud-command:cloud-cull"
                )
            )
        ).one()

    assert plant.culled_at == FIXED_NOW
    assert plant.culled_reason == "failed vigor check"
    assert current_locations == []
    assert command.tent_id is None


async def test_command_loop_creates_plant_note_with_cloud_requester(
    app_engine: AsyncEngine,
):
    [plant_key] = await _seed_command_plants(app_engine, prefix="NOTE", count=1)
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-note",
            command_type="breeding_plant_note_create",
            payload={
                "plant_key": plant_key,
                "body": "Stem rub is citrus-heavy.",
                "observed_at": FIXED_NOW.isoformat(),
            },
        )
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 1
    async with AsyncSession(app_engine) as session:
        note = (
            await session.exec(
                select(PlantNote)
                .join(Plant, Plant.id == PlantNote.plant_id)
                .where(Plant.key == plant_key)
            )
        ).one()
        command = (
            await session.exec(
                select(Command).where(
                    Command.idempotency_key == "cloud-command:cloud-note"
                )
            )
        ).one()

    assert note.body == "Stem rub is citrus-heavy."
    assert note.created_by == "admin"
    assert command.result["source_note_id"] == note.id
    assert command.tent_id is None


async def test_command_loop_rejects_breeding_with_ptz_target_before_ledger(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-breeding-bad-target",
            command_type="breeding_plants_bulk_cull",
            payload={"plant_keys": ["missing"], "reason": "bad target"},
            target={
                "kind": "ptz",
                "source_tent_id": 1,
                "device_id": "obsbot-main",
                "capability_id": "ptz_move",
            },
        ),
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 0
    assert [payload.status for _, payload, _ in cloud.command_results] == ["rejected"]
    async with AsyncSession(app_engine) as session:
        commands = (await session.exec(select(Command))).all()
    assert commands == []


async def test_command_loop_reports_failed_for_invalid_breeding_state(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-missing-plant",
            command_type="breeding_plant_note_create",
            payload={"plant_key": "NOPE-001", "body": "Missing plant."},
        )
    ]

    result = await _command_service(app_engine, cloud, RecordingPTZ()).run_once()

    assert result.executed == 1
    statuses = [payload.status for _, payload, _ in cloud.command_results]
    assert statuses == ["running", "failed"]
    assert "unknown plant key" in cloud.command_results[-1][1].error
    async with AsyncSession(app_engine) as session:
        command = (
            await session.exec(
                select(Command).where(
                    Command.idempotency_key == "cloud-command:cloud-missing-plant"
                )
            )
        ).one()
    assert command.status == "failed"


async def test_command_loop_does_not_duplicate_breeding_terminal_local_command(
    app_engine: AsyncEngine,
):
    [plant_key] = await _seed_command_plants(app_engine, prefix="IDEMP", count=1)
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-note-repeat",
            command_type="breeding_plant_note_create",
            payload={"plant_key": plant_key, "body": "One note only."},
        )
    ]
    service = _command_service(app_engine, cloud, RecordingPTZ())

    first = await service.run_once()
    second = await service.run_once()

    assert first.executed == 1
    assert second.executed == 0
    async with AsyncSession(app_engine) as session:
        notes = (
            await session.exec(
                select(PlantNote)
                .join(Plant, Plant.id == PlantNote.plant_id)
                .where(Plant.key == plant_key)
            )
        ).all()

    assert len(notes) == 1
    terminal_reports = [
        payload.status
        for _, payload, _ in cloud.command_results
        if payload.status == "succeeded"
    ]
    assert terminal_reports == ["succeeded", "succeeded"]


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
            "cloud-unknown-preset",
            payload={"preset_id": "not-a-preset"},
        ),
        _cloud_command(
            "cloud-missing-target-scope",
            target={
                "kind": "ptz",
                "source_tent_id": None,
                "device_id": "obsbot-main",
                "capability_id": "ptz_move",
            },
        ),
    ]
    ptz = RecordingPTZ()

    result = await _command_service(app_engine, cloud, ptz).run_once()

    assert result.executed == 0
    assert ptz.calls == []
    statuses = [payload.status for _command_id, payload, _key in cloud.command_results]
    assert statuses == ["expired", "rejected", "rejected"]
    async with AsyncSession(app_engine) as session:
        local_commands = (await session.exec(select(Command))).all()
    assert local_commands == []


async def test_command_loop_rejects_malformed_claim_before_execution_and_reporting(
    app_engine: AsyncEngine,
):
    cloud = RecordingCloudClient()
    cloud.claimed_commands = [
        _cloud_command(
            "cloud-bad-payload",
            command_type="ptz_look",
            payload={"x": 0.8, "y": 0.0},
        )
    ]
    ptz = RecordingPTZ()

    result = await _command_service(app_engine, cloud, ptz).run_once()

    assert result.executed == 0
    assert result.reported == 0
    assert result.failed == 1
    assert ptz.calls == []
    assert cloud.command_results == []
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
        payload.status
        for _command_id, payload, _key in cloud.command_results
        if payload.status == "succeeded"
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
