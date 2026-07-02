"""Local state projection for the hosted control-plane gateway."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_gateway.protocols import AssetUploadProjection
from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetSignUploadRequest,
    CatalogCapability,
    CatalogCrossEvent,
    CatalogDevice,
    CatalogPlant,
    CatalogPlantEvent,
    CatalogPlantLine,
    CatalogPlantLocation,
    CatalogPlantMetricStream,
    CatalogPlantNote,
    CatalogPlantSexTest,
    CatalogRequest,
    CatalogSchedule,
    CatalogSeedLot,
    CatalogSite,
    CatalogTent,
    CatalogZone,
    LatestMetricItem,
    LatestMetricsRequest,
    RollupItem,
    RollupsRequest,
    WikiProjectionPage,
    WikiProjectionRequest,
)
from dirt_shared.models import (
    Capability,
    CrossEvent,
    Device,
    Plant,
    PlantEvent,
    PlantLine,
    PlantLocationHistory,
    PlantMetricStream,
    PlantNote,
    PlantSexTest,
    Schedule,
    SeedLot,
    Snapshot,
    Tent,
    Zone,
)
from dirt_shared.observability import log_event
from dirt_shared.services.light_schedules import LightScheduleService
from dirt_shared.services.readings import (
    PRODUCT_PLANT_MOISTURE_METRIC,
    get_latest_product_plant_moisture_readings,
)
from dirt_shared.services.scope import require_default_site, require_default_site_pk
from dirt_shared.services.scope_catalog import ScopeCatalogService
from dirt_shared.services.snapshots import get_snapshot_path

ROLLUP_SPECS: tuple[tuple[str, timedelta, int], ...] = (
    ("5m", timedelta(hours=24), 300),
    ("1h", timedelta(days=7), 3600),
    ("4h", timedelta(days=30), 14400),
    ("1d", timedelta(days=90), 86400),
)
WIKI_ROOT = Path(__file__).resolve().parents[4] / "wiki"
WIKI_EXCLUDED_PATHS = ("wiki/AGENTS.md", "wiki/private/**", "wiki/raw/**")
WIKI_PLANT_PAGE_GLOB = "grows/*/plants/*.md"


class GatewayLocalServiceBundle:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock,
        stale_after_s: int = 300,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._stale_after_s = stale_after_s
        self._catalog = ScopeCatalogService(engine)
        self._light_schedules = LightScheduleService(engine, clock=clock)

    async def collect_catalog(self, site_id: str) -> CatalogRequest:
        async with AsyncSession(self._engine) as session:
            site = await require_default_site(session)
            site_pk = site.id
        if site_pk is None:
            return CatalogRequest(
                site_id=site_id,
                site=CatalogSite(
                    source_site_id=0,
                    name=site_id,
                    timezone="America/Denver",
                ),
                sex_tests=[],
            )
        tents = await self._catalog.list_tents(site_pk=site_pk)

        return CatalogRequest(
            site_id=site_id,
            site=CatalogSite(
                source_site_id=site_pk,
                name=site.name,
                timezone=site.timezone,
            ),
            tents=[
                CatalogTent(
                    source_tent_id=tent.tent_pk,
                    name=tent.name,
                    role=tent.role,
                    is_active=tent.active,
                )
                for tent in tents
            ],
            zones=await self._collect_zones(site_pk=site_pk),
            devices=await self._collect_devices(site_pk=site_pk),
            capabilities=await self._collect_capabilities(site_pk=site_pk),
            schedules=await self._collect_schedules(site_pk=site_pk),
            plant_lines=await self._collect_plant_lines(),
            seed_lots=await self._collect_seed_lots(),
            plants=await self._collect_plants(site_pk=site_pk),
            sex_tests=await self._collect_plant_sex_tests(site_pk=site_pk),
            plant_locations=await self._collect_plant_locations(site_pk=site_pk),
            cross_events=await self._collect_cross_events(),
            plant_notes=await self._collect_plant_notes(site_pk=site_pk),
            plant_events=await self._collect_plant_events(site_pk=site_pk),
            plant_metric_streams=await self._collect_plant_metric_streams(
                site_pk=site_pk
            ),
        )

    async def collect_latest_metrics(self, site_id: str) -> LatestMetricsRequest:
        metrics: list[LatestMetricItem] = []
        async with AsyncSession(self._engine) as session:
            site_pk = await require_default_site_pk(session)
            result = await session.exec(
                text(_latest_metrics_sql()),
                params={"site_pk": site_pk},
            )
            for row in result.mappings().all():
                metrics.append(
                    LatestMetricItem(
                        site_id=site_id,
                        source_site_id=site_pk,
                        source_tent_id=row["source_tent_id"],
                        source_zone_id=row["source_zone_id"],
                        device_id=row["device_id"],
                        capability_id=row["capability_id"],
                        metric=row["metric"],
                        value=float(row["value"]),
                        unit=row["unit"],
                        source_updated_at=_as_utc(row["source_updated_at"]),
                        stale_after_s=self._stale_after_s,
                    )
                )
            for reading in await get_latest_product_plant_moisture_readings(
                session,
                now=self._clock(),
                site_pk=site_pk,
                use_default_tent=False,
            ):
                metrics.append(
                    LatestMetricItem(
                        site_id=site_id,
                        source_site_id=site_pk,
                        source_tent_id=reading.source_tent_id,
                        source_zone_id=reading.source_zone_id,
                        device_id=reading.device_id,
                        capability_id=reading.capability_id,
                        metric=PRODUCT_PLANT_MOISTURE_METRIC,
                        value=float(reading.value),
                        unit="%",
                        source_updated_at=reading.timestamp,
                        stale_after_s=self._stale_after_s,
                    )
                )
        return LatestMetricsRequest(site_id=site_id, metrics=metrics)

    async def collect_rollups(
        self, site_id: str, *, bucket_names: set[str] | None = None
    ) -> RollupsRequest:
        now = self._clock()
        rollups: list[RollupItem] = []
        async with AsyncSession(self._engine) as session:
            site_pk = await require_default_site_pk(session)
            for bucket, window, bucket_s in ROLLUP_SPECS:
                if bucket_names is not None and bucket not in bucket_names:
                    continue
                rollups.extend(
                    await collect_canonical_history_rollups(
                        session,
                        site_id=site_id,
                        site_pk=site_pk,
                        since=now - window,
                        bucket=bucket,
                        bucket_s=bucket_s,
                    )
                )
                rollups.extend(
                    await collect_dehumidifier_runtime_rollups(
                        session,
                        site_id=site_id,
                        site_pk=site_pk,
                        since=now - window,
                        bucket=bucket,
                        bucket_s=bucket_s,
                    )
                )
        return RollupsRequest(site_id=site_id, rollups=rollups)

    async def collect_wiki_pages(self, site_id: str) -> WikiProjectionRequest:
        pages = [
            _wiki_projection_page(path)
            for path in sorted(WIKI_ROOT.glob(WIKI_PLANT_PAGE_GLOB))
            if _wiki_path_is_projected(path)
        ]
        return WikiProjectionRequest(
            site_id=site_id,
            generated_at=self._clock(),
            pages=pages,
            excluded_paths=list(WIKI_EXCLUDED_PATHS),
            content_hash=_wiki_projection_hash(pages, WIKI_EXCLUDED_PATHS),
        )

    async def latest_snapshot_asset(self, site_id: str) -> AssetUploadProjection | None:
        async with AsyncSession(self._engine) as session:
            site_pk = await require_default_site_pk(session)
        tents = await self._catalog.list_tents(site_pk=site_pk)
        for tent in sorted(tents, key=lambda item: (not item.is_default, item.name)):
            snapshot = await self._latest_usable_snapshot(
                site_id=site_id,
                site_pk=site_pk,
                tent_pk=tent.tent_pk,
            )
            if snapshot is None:
                continue
            path = get_snapshot_path(snapshot)
            if path is None:
                continue
            byte_size = path.stat().st_size
            digest = _file_sha256(path)
            object_key = f"tents/{tent.tent_pk}/snapshots/{path.name}"
            sign_request = AssetSignUploadRequest(
                site_id=site_id,
                source_tent_id=tent.tent_pk,
                content_type="image/jpeg",
                byte_size=byte_size,
                object_key=object_key,
                asset_id=digest,
                sha256=digest,
                kind=snapshot.kind,
            )
            complete_request = AssetCompleteRequest(
                **sign_request.model_dump(),
                captured_at=_as_utc(snapshot.ts),
                source_zone_id=snapshot.zone_id,
                device_id=await self._public_device_id(snapshot),
            )
            return AssetUploadProjection(
                sign_request=sign_request,
                complete_request=complete_request,
                file_path=path,
            )
        return None

    async def _latest_usable_snapshot(
        self,
        *,
        site_id: str,
        site_pk: int,
        tent_pk: int,
    ) -> Snapshot | None:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(Snapshot)
                    .where(Snapshot.site_id == site_pk)
                    .where(Snapshot.tent_id == tent_pk)
                    .order_by(Snapshot.ts.desc())
                    .limit(10)
                )
            ).all()
        for snapshot in rows:
            path = get_snapshot_path(snapshot)
            if path is None:
                continue
            byte_size = path.stat().st_size
            if byte_size > 0:
                return snapshot
            log_event(
                "cloud_gateway",
                "asset_skipped",
                site_id=site_id,
                source_tent_id=tent_pk,
                snapshot_id=snapshot.id,
                file_path=str(path),
                reason="empty_file",
            )
        return None

    async def _collect_zones(self, *, site_pk: int) -> list[CatalogZone]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(Zone, Tent.id)
                    .join(Tent, Tent.id == Zone.tent_id)
                    .where(Zone.site_id == site_pk)
                    .order_by(Tent.name, Zone.name)
                )
            ).all()
        return [
            CatalogZone(
                source_tent_id=source_tent_id,
                source_zone_id=zone.id,
                name=zone.name,
                kind=zone.zone_type,
                is_active=zone.active,
            )
            for zone, source_tent_id in rows
            if zone.id is not None and source_tent_id is not None
        ]

    async def _collect_devices(self, *, site_pk: int) -> list[CatalogDevice]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(Device, Tent.id, Zone.id)
                    .outerjoin(Tent, Tent.id == Device.tent_id)
                    .outerjoin(Zone, Zone.id == Device.zone_id)
                    .where(Device.site_id == site_pk)
                    .order_by(Tent.name, Device.device_id)
                )
            ).all()
        return [
            CatalogDevice(
                source_tent_id=source_tent_id,
                source_zone_id=source_zone_id,
                device_id=device.device_id,
                name=device.name,
                kind=device.kind,
                controller=device.controller,
                is_active=device.enabled,
                last_seen_at=device.last_seen,
            )
            for device, source_tent_id, source_zone_id in rows
            if source_tent_id is not None
        ]

    async def _collect_capabilities(self, *, site_pk: int) -> list[CatalogCapability]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(Capability, Device.device_id, Tent.id)
                    .join(Device, Device.id == Capability.device_id)
                    .outerjoin(Tent, Tent.id == Device.tent_id)
                    .where(Device.site_id == site_pk)
                    .order_by(Tent.name, Device.device_id, Capability.capability_id)
                )
            ).all()
        return [
            CatalogCapability(
                source_tent_id=source_tent_id,
                device_id=device_id,
                capability_id=capability.capability_id,
                metric_name=capability.metric_name,
                kind=capability.kind,
                unit=capability.unit,
                is_enabled=capability.enabled,
            )
            for capability, device_id, source_tent_id in rows
            if source_tent_id is not None
        ]

    async def _collect_schedules(self, *, site_pk: int) -> list[CatalogSchedule]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(
                        Schedule,
                        Device.device_id,
                        Device.zone_id,
                        Capability.capability_id,
                    )
                    .outerjoin(Device, Device.id == Schedule.device_id)
                    .outerjoin(Capability, Capability.id == Schedule.capability_id)
                    .where(Schedule.site_id == site_pk)
                    .where(Schedule.kind == "lights")
                    .where(col(Schedule.starts_local).is_not(None))
                    .where(col(Schedule.ends_local).is_not(None))
                    .order_by(Schedule.tent_id, Schedule.id)
                )
            ).all()
        return [
            CatalogSchedule(
                source_site_id=schedule.site_id,
                source_tent_id=schedule.tent_id,
                source_zone_id=source_zone_id,
                source_schedule_id=schedule.id,
                device_id=device_id,
                capability_id=capability_id,
                kind=schedule.kind,
                starts_local=schedule.starts_local,
                ends_local=schedule.ends_local,
                timezone=schedule.timezone,
                is_enabled=schedule.enabled,
            )
            for schedule, device_id, source_zone_id, capability_id in rows
            if (
                schedule.id is not None
                and schedule.starts_local is not None
                and schedule.ends_local is not None
            )
        ]

    async def _collect_plant_lines(self) -> list[CatalogPlantLine]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(PlantLine)
                    .distinct()
                    .order_by(PlantLine.strain, PlantLine.cultivar, PlantLine.id)
                )
            ).all()
        return [
            CatalogPlantLine(
                source_line_id=line.id,
                project_code=line.project_code,
                generation_label=line.generation_label,
                strain=line.strain,
                cultivar=line.cultivar,
                description=line.description,
                source_name=line.source_name,
            )
            for line in rows
            if line.id is not None
        ]

    async def _collect_seed_lots(self) -> list[CatalogSeedLot]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(select(SeedLot).distinct().order_by(SeedLot.id))
            ).all()
        return [
            CatalogSeedLot(
                source_seed_lot_id=seed_lot.id,
                line_source_id=seed_lot.line_id,
                sex_type_key=seed_lot.sex_type_key,
                is_purchased=seed_lot.is_purchased,
                vendor_name=seed_lot.vendor_name,
                acquired_at=seed_lot.acquired_at,
                produced_by_cross_event_source_id=seed_lot.produced_by_cross_event_id,
                seed_count=seed_lot.seed_count,
                notes=seed_lot.notes,
            )
            for seed_lot in rows
            if seed_lot.id is not None
        ]

    async def _collect_plants(self, *, site_pk: int) -> list[CatalogPlant]:
        async with AsyncSession(self._engine) as session:
            site_plant_ids = select(PlantLocationHistory.plant_id).where(
                PlantLocationHistory.site_id == site_pk
            )
            rows = (
                await session.exec(
                    select(Plant)
                    .where(col(Plant.id).in_(site_plant_ids))
                    .order_by(Plant.key)
                )
            ).all()
        return [
            CatalogPlant(
                source_plant_id=plant.id,
                line_source_id=plant.line_id,
                sex_key=plant.sex_key,
                source_seed_lot_id=plant.source_seed_lot_id,
                clone_source_plant_id=plant.clone_source_plant_id,
                key=plant.key,
                name=plant.name,
                germinated_at=plant.germinated_at,
                taken_at=plant.taken_at,
                rooted_at=plant.rooted_at,
                veg_started_at=plant.veg_started_at,
                flower_started_at=plant.flower_started_at,
                culled_at=plant.culled_at,
                culled_reason=plant.culled_reason,
                harvested_at=plant.harvested_at,
                selected_for_breeding_at=plant.selected_for_breeding_at,
                selected_for_breeding_reason=plant.selected_for_breeding_reason,
                is_active=plant.culled_at is None and plant.harvested_at is None,
            )
            for plant in rows
            if plant.id is not None
        ]

    async def _collect_plant_locations(
        self, *, site_pk: int
    ) -> list[CatalogPlantLocation]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(PlantLocationHistory, Plant, Tent.id)
                    .join(Plant, Plant.id == PlantLocationHistory.plant_id)
                    .join(Tent, Tent.id == PlantLocationHistory.tent_id)
                    .where(PlantLocationHistory.site_id == site_pk)
                    .order_by(
                        Tent.name,
                        PlantLocationHistory.grid_position,
                        PlantLocationHistory.start_at,
                        Plant.key,
                    )
                )
            ).all()
        return [
            CatalogPlantLocation(
                source_location_id=location.id,
                source_plant_id=plant.id,
                source_tent_id=source_tent_id,
                grid_position=location.grid_position,
                start_at=location.start_at,
                end_at=location.end_at,
            )
            for location, plant, source_tent_id in rows
            if location.id is not None and plant.id is not None
        ]

    async def _collect_plant_sex_tests(
        self, *, site_pk: int
    ) -> list[CatalogPlantSexTest]:
        async with AsyncSession(self._engine) as session:
            site_plant_ids = select(PlantLocationHistory.plant_id).where(
                PlantLocationHistory.site_id == site_pk
            )
            rows = (
                await session.exec(
                    select(PlantSexTest)
                    .where(col(PlantSexTest.plant_id).in_(site_plant_ids))
                    .order_by(
                        PlantSexTest.plant_id,
                        PlantSexTest.sample_collected_at,
                        PlantSexTest.id,
                    )
                )
            ).all()
        return [
            CatalogPlantSexTest(
                source_sex_test_id=sex_test.id,
                source_plant_id=sex_test.plant_id,
                vendor_name=sex_test.vendor_name,
                assay_name=sex_test.assay_name,
                vendor_test_code=sex_test.vendor_test_code,
                sample_collected_at=sex_test.sample_collected_at,
                sample_sent_at=sex_test.sample_sent_at,
                result_received_at=sex_test.result_received_at,
                result_sex_key=sex_test.result_sex_key,
                is_inconclusive=sex_test.is_inconclusive,
                notes=sex_test.notes,
            )
            for sex_test in rows
            if sex_test.id is not None
        ]

    async def _collect_cross_events(self) -> list[CatalogCrossEvent]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(CrossEvent).order_by(CrossEvent.pollinated_at, CrossEvent.id)
                )
            ).all()
        return [
            CatalogCrossEvent(
                source_cross_event_id=cross_event.id,
                resulting_line_source_id=cross_event.resulting_line_id,
                seed_parent_source_plant_id=cross_event.seed_parent_plant_id,
                pollen_parent_source_plant_id=cross_event.pollen_parent_plant_id,
                pollinated_at=cross_event.pollinated_at,
                pollen_parent_is_reversed=cross_event.pollen_parent_is_reversed,
                notes=cross_event.notes,
            )
            for cross_event in rows
            if cross_event.id is not None
        ]

    async def _collect_plant_notes(self, *, site_pk: int) -> list[CatalogPlantNote]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(PlantNote)
                    .join(Plant, Plant.id == PlantNote.plant_id)
                    .join(
                        PlantLocationHistory,
                        PlantLocationHistory.plant_id == Plant.id,
                    )
                    .where(PlantLocationHistory.site_id == site_pk)
                    .distinct()
                    .order_by(PlantNote.observed_at, PlantNote.id)
                )
            ).all()
        return [
            CatalogPlantNote(
                source_note_id=note.id,
                source_plant_id=note.plant_id,
                observed_at=note.observed_at,
                body=note.body,
                created_by=note.created_by,
            )
            for note in rows
            if note.id is not None
        ]

    async def _collect_plant_events(self, *, site_pk: int) -> list[CatalogPlantEvent]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(PlantEvent)
                    .join(Plant, Plant.id == PlantEvent.plant_id)
                    .join(
                        PlantLocationHistory,
                        PlantLocationHistory.plant_id == Plant.id,
                    )
                    .where(PlantLocationHistory.site_id == site_pk)
                    .distinct()
                    .order_by(PlantEvent.occurred_at, PlantEvent.id)
                )
            ).all()
        return [
            CatalogPlantEvent(
                source_event_id=event.id,
                source_plant_id=event.plant_id,
                is_pollen_collection=event.is_pollen_collection,
                is_seed_production=event.is_seed_production,
                is_clone_taken=event.is_clone_taken,
                is_sex_observation=event.is_sex_observation,
                is_reversal=event.is_reversal,
                is_transplant=event.is_transplant,
                is_selection_for_breeding=event.is_selection_for_breeding,
                occurred_at=event.occurred_at,
                reason=event.reason,
                notes=event.notes,
                metadata=event.metadata_json,
            )
            for event in rows
            if event.id is not None
        ]

    async def _collect_plant_metric_streams(
        self, *, site_pk: int
    ) -> list[CatalogPlantMetricStream]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(
                        PlantMetricStream,
                        Plant.id,
                        Plant.key,
                        PlantLocationHistory.grid_position,
                        Tent.name,
                        Device.device_id,
                        Capability.capability_id,
                        Capability.metric_name,
                    )
                    .join(Plant, Plant.id == PlantMetricStream.plant_id)
                    .join(
                        PlantLocationHistory,
                        PlantLocationHistory.plant_id == Plant.id,
                    )
                    .join(Tent, Tent.id == PlantLocationHistory.tent_id)
                    .join(Capability, Capability.id == PlantMetricStream.capability_id)
                    .join(Device, Device.id == Capability.device_id)
                    .where(PlantLocationHistory.site_id == site_pk)
                    .where(PlantLocationHistory.end_at.is_(None))
                    .where(Capability.metric_name.is_not(None))
                    .order_by(
                        Tent.name,
                        PlantLocationHistory.grid_position,
                        Plant.key,
                        PlantMetricStream.display_order,
                        Capability.capability_id,
                    )
                )
            ).all()
        streams: list[CatalogPlantMetricStream] = []
        for (
            stream,
            source_plant_id,
            _plant_key,
            _grid_position,
            _tent_id,
            device_id,
            capability_id,
            metric_name,
        ) in rows:
            if metric_name is None:
                continue
            streams.append(
                CatalogPlantMetricStream(
                    source_plant_id=source_plant_id,
                    device_id=device_id,
                    capability_id=capability_id,
                    metric=metric_name,
                    display_order=stream.display_order,
                    is_active=stream.is_active,
                )
            )
        return streams

    async def _public_device_id(self, snapshot: Snapshot) -> str | None:
        if snapshot.device_id is None:
            return None
        async with AsyncSession(self._engine) as session:
            device = await session.get(Device, snapshot.device_id)
            return None if device is None else device.device_id


async def collect_canonical_history_rollups(  # noqa: PLR0913
    session: AsyncSession,
    *,
    site_id: str,
    site_pk: int,
    since: datetime,
    bucket: str,
    bucket_s: int,
) -> list[RollupItem]:
    sql = """
SELECT
  d.site_id AS source_site_id,
  t.id AS source_tent_id,
  d.device_id,
  c.capability_id,
  c.metric_name AS metric,
  c.unit,
  date_bin(
    make_interval(secs => :bucket_s),
    sr.ts,
    TIMESTAMPTZ '1970-01-01'
  ) AS bucket_start_at,
  min(sr.value) AS min_value,
  avg(sr.value) AS avg_value,
  max(sr.value) AS max_value,
  count(*) AS sample_count
FROM sensorreading sr
JOIN capability c ON c.id = sr.capability_id
JOIN metric_presentation mp
  ON mp.metric = c.metric_name
 AND mp.history_enabled = true
JOIN device d ON d.id = c.device_id
JOIN tent t ON t.id = d.tent_id
WHERE d.site_id = :site_pk
  AND sr.ts >= :since
  AND c.enabled = true
  AND c.metric_name IS NOT NULL
  AND sr.metric = c.metric_name
GROUP BY
  d.site_id,
  t.id,
  d.device_id,
  c.capability_id,
  c.metric_name,
  c.unit,
  bucket_start_at
ORDER BY bucket_start_at, t.id, d.device_id, c.capability_id, c.metric_name
"""
    result = await session.exec(
        text(sql),
        params={"site_pk": site_pk, "since": since, "bucket_s": bucket_s},
    )
    return _rollup_items_from_rows(
        result.mappings().all(),
        site_id=site_id,
        bucket=bucket,
        bucket_s=bucket_s,
    )


async def collect_dehumidifier_runtime_rollups(  # noqa: PLR0913
    session: AsyncSession,
    *,
    site_id: str,
    site_pk: int,
    since: datetime,
    bucket: str,
    bucket_s: int,
) -> list[RollupItem]:
    sql = """
SELECT
  d.site_id AS source_site_id,
  t.id AS source_tent_id,
  d.device_id,
  c.capability_id,
  mp.metric AS metric,
  mp.unit,
  date_bin(
    make_interval(secs => :bucket_s),
    sr.ts,
    TIMESTAMPTZ '1970-01-01'
  ) AS bucket_start_at,
  round((min(sr.value) * 100.0)::numeric, 4)::double precision AS min_value,
  round((avg(sr.value) * 100.0)::numeric, 4)::double precision AS avg_value,
  round((max(sr.value) * 100.0)::numeric, 4)::double precision AS max_value,
  count(*) AS sample_count
FROM sensorreading sr
JOIN capability c ON c.id = sr.capability_id
JOIN metric_presentation mp
  ON mp.metric = 'dehumidifier_runtime_pct'
 AND mp.history_enabled = true
JOIN device d ON d.id = c.device_id
JOIN tent t ON t.id = d.tent_id
WHERE d.site_id = :site_pk
  AND sr.ts >= :since
  AND c.enabled = true
  AND c.metric_name = 'dehumidifier_on'
  AND sr.metric = 'dehumidifier_on'
GROUP BY
  d.site_id,
  t.id,
  d.device_id,
  c.capability_id,
  mp.metric,
  mp.unit,
  bucket_start_at
ORDER BY bucket_start_at, t.id, d.device_id, c.capability_id, mp.metric
"""
    result = await session.exec(
        text(sql),
        params={"site_pk": site_pk, "since": since, "bucket_s": bucket_s},
    )
    return _rollup_items_from_rows(
        result.mappings().all(),
        site_id=site_id,
        bucket=bucket,
        bucket_s=bucket_s,
    )


def _latest_metrics_sql() -> str:
    return """
WITH latest AS (
  SELECT DISTINCT ON (capability_id)
    capability_id,
    value,
    ts
  FROM sensorreading
  ORDER BY capability_id, ts DESC
),
base AS (
  SELECT
    d.site_id AS source_site_id,
    t.id AS source_tent_id,
    z.id AS source_zone_id,
    d.device_id,
    c.capability_id,
    c.metric_name AS metric,
    latest.value,
    c.unit,
    latest.ts AS source_updated_at
  FROM capability c
  JOIN latest ON latest.capability_id = c.id
  JOIN device d ON d.id = c.device_id
  JOIN tent t ON t.id = d.tent_id
  LEFT JOIN zone z ON z.id = d.zone_id
  WHERE d.site_id = :site_pk
    AND c.enabled = true
    AND c.metric_name IS NOT NULL
    AND c.metric_name NOT IN ('soil_moisture_raw', 'soil_moisture_pct')
)
SELECT
  source_site_id,
  source_tent_id,
  source_zone_id,
  device_id,
  capability_id,
  metric,
  value,
  unit,
  source_updated_at
FROM base
ORDER BY device_id, capability_id, metric
"""


def _rollup_items_from_rows(
    rows: list[Any],
    *,
    site_id: str,
    bucket: str,
    bucket_s: int,
) -> list[RollupItem]:
    rollups: list[RollupItem] = []
    for row in rows:
        bucket_start = _as_utc(row["bucket_start_at"])
        rollups.append(
            RollupItem(
                site_id=site_id,
                source_site_id=row["source_site_id"],
                source_tent_id=row["source_tent_id"],
                device_id=row["device_id"],
                capability_id=row["capability_id"],
                metric=row["metric"],
                bucket=bucket,
                bucket_start_at=bucket_start,
                bucket_end_at=bucket_start + timedelta(seconds=bucket_s),
                min_value=_maybe_float(row["min_value"]),
                avg_value=_maybe_float(row["avg_value"]),
                max_value=_maybe_float(row["max_value"]),
                sample_count=int(row["sample_count"]),
                unit=row["unit"],
            )
        )
    return rollups


def _as_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def _maybe_float(value: Any) -> float | None:
    return None if value is None else round(float(value), 4)


def _wiki_projection_page(path: Path) -> WikiProjectionPage:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    frontmatter, body = _split_frontmatter(text)
    title = _wiki_title(path, frontmatter=frontmatter, body_markdown=body)
    return WikiProjectionPage(
        path=_wiki_payload_path(path),
        title=title,
        frontmatter=frontmatter,
        body_markdown=body,
        sha256=_wiki_content_hash(frontmatter=frontmatter, body_markdown=body),
        source_updated_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
    )


def _wiki_path_is_projected(path: Path) -> bool:
    payload_path = _wiki_payload_path(path)
    return (
        payload_path not in WIKI_EXCLUDED_PATHS
        and not payload_path.startswith("wiki/private/")
        and not payload_path.startswith("wiki/raw/")
    )


def _wiki_payload_path(path: Path) -> str:
    return f"wiki/{path.relative_to(WIKI_ROOT).as_posix()}"


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    remainder = text.removeprefix("---\n")
    if "\n---\n" not in remainder:
        return {}, text
    frontmatter_text, body = remainder.split("\n---\n", 1)
    return _parse_frontmatter(frontmatter_text), body


def _parse_frontmatter(text: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        values[key.strip()] = _parse_frontmatter_value(raw_value.strip())
    return values


def _parse_frontmatter_value(value: str) -> Any:
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_strip_yaml_quotes(item.strip()) for item in inner.split(",")]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "~"}:
        return None
    return _strip_yaml_quotes(value)


def _strip_yaml_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _wiki_title(path: Path, *, frontmatter: dict[str, Any], body_markdown: str) -> str:
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in body_markdown.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return path.stem


def _wiki_content_hash(*, frontmatter: dict[str, Any], body_markdown: str) -> str:
    return _sha256_json(
        {
            "frontmatter": frontmatter,
            "body_markdown": body_markdown,
        }
    )


def _wiki_projection_hash(
    pages: list[WikiProjectionPage], excluded_paths: tuple[str, ...]
) -> str:
    return _sha256_json(
        {
            "pages": [
                page.model_dump(
                    mode="json",
                    exclude={"source_updated_at"},
                )
                for page in pages
            ],
            "excluded_paths": list(excluded_paths),
        }
    )


def _sha256_json(value: dict[str, Any]) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
