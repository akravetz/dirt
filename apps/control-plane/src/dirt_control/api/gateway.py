from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from dirt_control.audit import add_audit_event
from dirt_control.deps import get_asset_store, get_clock, get_session, get_settings
from dirt_control.models import (
    CloudAsset,
    CloudCapability,
    CloudCommand,
    CloudCrossEvent,
    CloudDevice,
    CloudLatestMetric,
    CloudMetricRollup,
    CloudPlant,
    CloudPlantEvent,
    CloudPlantLine,
    CloudPlantLocation,
    CloudPlantMetricStream,
    CloudPlantNote,
    CloudSchedule,
    CloudSeedLot,
    CloudSite,
    CloudTent,
    CloudWikiPage,
    CloudZone,
    GatewayCredential,
)
from dirt_control.retention import prune_expired_assets
from dirt_control.security import (
    GatewayPrincipal,
    authenticate_gateway,
    expires_from,
    require_gateway_scope,
)
from dirt_control.settings import CloudSettings
from dirt_control.storage import AssetStore
from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetCompleteResponse,
    AssetFailureRequest,
    AssetFailureResponse,
    AssetRetentionRequest,
    AssetSignUploadRequest,
    CapturePolicyReason,
    CapturePolicyResponse,
    CatalogRequest,
    CatalogResponse,
    CommandClaimRequest,
    CommandClaimResponse,
    CommandResultRequest,
    CommandResultResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    LatestMetricsRequest,
    PruneAssetsResponse,
    PtzCommandTarget,
    RollupsRequest,
    SignUploadResponse,
    UpsertCountResponse,
    WikiProjectionRequest,
    WikiProjectionResponse,
)

router = APIRouter(prefix="/api/gateway/v1")
ModelT = TypeVar("ModelT", bound=SQLModel)


async def require_gateway(
    request: Request,
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> GatewayPrincipal:
    return await authenticate_gateway(request=request, session=session, now=clock())


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    body: HeartbeatRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> HeartbeatResponse:
    require_gateway_scope(principal, body.site_id)
    now = clock()
    credential = (
        await session.execute(
            select(GatewayCredential).where(
                GatewayCredential.credential_id == principal.credential_id
            )
        )
    ).scalar_one_or_none()
    if credential is not None:
        credential.last_used_at = now
        credential.updated_at = now
    site = (
        await session.execute(
            select(CloudSite).where(CloudSite.site_id == body.site_id)
        )
    ).scalar_one_or_none()
    if site is None:
        site = CloudSite(
            site_id=body.site_id,
            name=body.site_id,
            timezone="America/Denver",
            gateway_last_seen_at=now,
            gateway_backlog_depth=body.backlog_depth,
            created_at=now,
            updated_at=now,
        )
        session.add(site)
    else:
        site.gateway_last_seen_at = now
        site.gateway_backlog_depth = body.backlog_depth
        site.updated_at = now
    await session.commit()
    return HeartbeatResponse(
        ok=True,
        site_id=body.site_id,
        gateway_id=body.gateway_id,
        backlog_depth=body.backlog_depth,
        received_at=now,
    )


@router.put("/catalog", response_model=CatalogResponse)
async def catalog(
    body: CatalogRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CatalogResponse:
    require_gateway_scope(principal, body.site_id)
    now = clock()
    await _upsert_by_columns(
        session,
        CloudSite,
        {"site_id": body.site_id},
        {
            "site_id": body.site_id,
            "source_site_id": body.site.source_site_id,
            "name": body.site.name,
            "timezone": body.site.timezone,
            "is_active": True,
            "last_catalog_sync_at": now,
            "created_at": now,
            "updated_at": now,
        },
        now=now,
    )
    storage_tent_ids = {
        tent.source_tent_id: _storage_tent_id(tent.source_tent_id)
        for tent in body.tents
    }
    storage_zone_ids = {
        zone.source_zone_id: _storage_zone_id(zone.source_zone_id)
        for zone in body.zones
    }
    for tent in body.tents:
        storage_tent_id = storage_tent_ids[tent.source_tent_id]
        await _upsert_with_legacy_bridge(
            session,
            CloudTent,
            {"site_id": body.site_id, "source_tent_id": tent.source_tent_id},
            {"site_id": body.site_id, "tent_id": storage_tent_id},
            {
                "site_id": body.site_id,
                "source_site_id": body.site.source_site_id,
                "source_tent_id": tent.source_tent_id,
                "tent_id": storage_tent_id,
                "name": tent.name,
                "role": tent.role,
                "is_active": tent.is_active,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for zone in body.zones:
        storage_tent_id = _storage_tent_id_from_map(
            zone.source_tent_id, storage_tent_ids=storage_tent_ids
        )
        storage_zone_id = storage_zone_ids[zone.source_zone_id]
        await _upsert_with_legacy_bridge(
            session,
            CloudZone,
            {"site_id": body.site_id, "source_zone_id": zone.source_zone_id},
            {
                "site_id": body.site_id,
                "tent_id": storage_tent_id,
                "zone_id": storage_zone_id,
            },
            {
                "site_id": body.site_id,
                "source_tent_id": zone.source_tent_id,
                "source_zone_id": zone.source_zone_id,
                "tent_id": storage_tent_id,
                "zone_id": storage_zone_id,
                "name": zone.name,
                "kind": zone.kind,
                "is_active": zone.is_active,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for device in body.devices:
        storage_tent_id = _storage_tent_id_from_map(
            device.source_tent_id,
            storage_tent_ids=storage_tent_ids,
        )
        storage_zone_id = _storage_zone_id_from_map(
            device.source_zone_id,
            storage_zone_ids=storage_zone_ids,
        )
        await _upsert_with_legacy_bridge(
            session,
            CloudDevice,
            {
                "site_id": body.site_id,
                "source_tent_id": device.source_tent_id,
                "device_id": device.device_id,
            },
            {
                "site_id": body.site_id,
                "tent_id": storage_tent_id,
                "device_id": device.device_id,
            },
            {
                "site_id": body.site_id,
                "source_tent_id": device.source_tent_id,
                "source_zone_id": device.source_zone_id,
                "tent_id": storage_tent_id,
                "zone_id": storage_zone_id,
                "device_id": device.device_id,
                "name": device.name,
                "kind": device.kind,
                "controller": device.controller,
                "is_active": device.is_active,
                "last_seen_at": device.last_seen_at,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for capability in body.capabilities:
        storage_tent_id = _storage_tent_id_from_map(
            capability.source_tent_id,
            storage_tent_ids=storage_tent_ids,
        )
        await _upsert_with_legacy_bridge(
            session,
            CloudCapability,
            {
                "site_id": body.site_id,
                "source_tent_id": capability.source_tent_id,
                "device_id": capability.device_id,
                "capability_id": capability.capability_id,
            },
            {
                "site_id": body.site_id,
                "tent_id": storage_tent_id,
                "device_id": capability.device_id,
                "capability_id": capability.capability_id,
            },
            {
                "site_id": body.site_id,
                "source_tent_id": capability.source_tent_id,
                "tent_id": storage_tent_id,
                "device_id": capability.device_id,
                "capability_id": capability.capability_id,
                "metric_name": capability.metric_name,
                "kind": capability.kind,
                "unit": capability.unit,
                "is_enabled": capability.is_enabled,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for schedule in body.schedules:
        storage_tent_id = _storage_tent_id_from_map(
            schedule.source_tent_id,
            storage_tent_ids=storage_tent_ids,
        )
        storage_zone_id = _storage_zone_id_from_map(
            schedule.source_zone_id,
            storage_zone_ids=storage_zone_ids,
        )
        storage_schedule_id = _storage_schedule_id(schedule.source_schedule_id)
        await _upsert_with_legacy_bridge(
            session,
            CloudSchedule,
            {
                "site_id": body.site_id,
                "source_schedule_id": schedule.source_schedule_id,
            },
            {
                "site_id": body.site_id,
                "tent_id": storage_tent_id,
                "schedule_id": storage_schedule_id,
            },
            {
                "site_id": body.site_id,
                "source_site_id": schedule.source_site_id,
                "source_tent_id": schedule.source_tent_id,
                "source_zone_id": schedule.source_zone_id,
                "source_schedule_id": schedule.source_schedule_id,
                "tent_id": storage_tent_id,
                "zone_id": storage_zone_id,
                "device_id": schedule.device_id,
                "capability_id": schedule.capability_id,
                "schedule_id": storage_schedule_id,
                "kind": schedule.kind,
                "starts_local": schedule.starts_local,
                "ends_local": schedule.ends_local,
                "timezone": schedule.timezone,
                "is_enabled": schedule.is_enabled,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for line in body.plant_lines:
        await _upsert_by_columns(
            session,
            CloudPlantLine,
            {
                "site_id": body.site_id,
                "source_line_id": line.source_line_id,
            },
            {
                "site_id": body.site_id,
                "source_line_id": line.source_line_id,
                "project_code": line.project_code,
                "generation_label": line.generation_label,
                "strain": line.strain,
                "cultivar": line.cultivar,
                "description": line.description,
                "source_name": line.source_name,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for seed_lot in body.seed_lots:
        await _upsert_by_columns(
            session,
            CloudSeedLot,
            {
                "site_id": body.site_id,
                "source_seed_lot_id": seed_lot.source_seed_lot_id,
            },
            {
                "site_id": body.site_id,
                "source_seed_lot_id": seed_lot.source_seed_lot_id,
                "line_source_id": seed_lot.line_source_id,
                "sex_type_key": seed_lot.sex_type_key,
                "is_purchased": seed_lot.is_purchased,
                "vendor_name": seed_lot.vendor_name,
                "acquired_at": seed_lot.acquired_at,
                "produced_by_cross_event_source_id": (
                    seed_lot.produced_by_cross_event_source_id
                ),
                "seed_count": seed_lot.seed_count,
                "notes": seed_lot.notes,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for plant in body.plants:
        await _upsert_by_columns(
            session,
            CloudPlant,
            {
                "site_id": body.site_id,
                "source_plant_id": plant.source_plant_id,
            },
            {
                "site_id": body.site_id,
                "source_plant_id": plant.source_plant_id,
                "line_source_id": plant.line_source_id,
                "sex_key": plant.sex_key,
                "source_seed_lot_id": plant.source_seed_lot_id,
                "clone_source_plant_id": plant.clone_source_plant_id,
                "key": plant.key,
                "name": plant.name,
                "germinated_at": plant.germinated_at,
                "rooted_at": plant.rooted_at,
                "veg_started_at": plant.veg_started_at,
                "flower_started_at": plant.flower_started_at,
                "culled_at": plant.culled_at,
                "culled_reason": plant.culled_reason,
                "harvested_at": plant.harvested_at,
                "selected_for_breeding_at": plant.selected_for_breeding_at,
                "selected_for_breeding_reason": plant.selected_for_breeding_reason,
                "is_active": plant.is_active,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for location in body.plant_locations:
        storage_tent_id = _storage_tent_id_from_map(
            location.source_tent_id,
            storage_tent_ids=storage_tent_ids,
        )
        await _upsert_by_columns(
            session,
            CloudPlantLocation,
            {
                "site_id": body.site_id,
                "source_location_id": location.source_location_id,
            },
            {
                "site_id": body.site_id,
                "source_location_id": location.source_location_id,
                "source_plant_id": location.source_plant_id,
                "source_tent_id": location.source_tent_id,
                "tent_id": storage_tent_id,
                "grid_position": location.grid_position,
                "start_at": location.start_at,
                "end_at": location.end_at,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for cross_event in body.cross_events:
        await _upsert_by_columns(
            session,
            CloudCrossEvent,
            {
                "site_id": body.site_id,
                "source_cross_event_id": cross_event.source_cross_event_id,
            },
            {
                "site_id": body.site_id,
                "source_cross_event_id": cross_event.source_cross_event_id,
                "resulting_line_source_id": cross_event.resulting_line_source_id,
                "seed_parent_source_plant_id": (
                    cross_event.seed_parent_source_plant_id
                ),
                "pollen_parent_source_plant_id": (
                    cross_event.pollen_parent_source_plant_id
                ),
                "pollinated_at": cross_event.pollinated_at,
                "pollen_parent_is_reversed": cross_event.pollen_parent_is_reversed,
                "notes": cross_event.notes,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for note in body.plant_notes:
        await _upsert_by_columns(
            session,
            CloudPlantNote,
            {
                "site_id": body.site_id,
                "source_note_id": note.source_note_id,
            },
            {
                "site_id": body.site_id,
                "source_note_id": note.source_note_id,
                "source_plant_id": note.source_plant_id,
                "observed_at": note.observed_at,
                "body": note.body,
                "created_by": note.created_by,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for event in body.plant_events:
        await _upsert_by_columns(
            session,
            CloudPlantEvent,
            {
                "site_id": body.site_id,
                "source_event_id": event.source_event_id,
            },
            {
                "site_id": body.site_id,
                "source_event_id": event.source_event_id,
                "source_plant_id": event.source_plant_id,
                "is_pollen_collection": event.is_pollen_collection,
                "is_seed_production": event.is_seed_production,
                "is_clone_taken": event.is_clone_taken,
                "is_sex_observation": event.is_sex_observation,
                "is_reversal": event.is_reversal,
                "is_transplant": event.is_transplant,
                "is_selection_for_breeding": event.is_selection_for_breeding,
                "occurred_at": event.occurred_at,
                "reason": event.reason,
                "notes": event.notes,
                "metadata_json": event.metadata,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for stream in body.plant_metric_streams:
        await _upsert_by_columns(
            session,
            CloudPlantMetricStream,
            {
                "site_id": body.site_id,
                "source_plant_id": stream.source_plant_id,
                "device_id": stream.device_id,
                "capability_id": stream.capability_id,
                "metric": stream.metric,
            },
            {
                "site_id": body.site_id,
                "source_plant_id": stream.source_plant_id,
                "device_id": stream.device_id,
                "capability_id": stream.capability_id,
                "metric": stream.metric,
                "display_order": stream.display_order,
                "is_active": stream.is_active,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    await session.commit()
    return CatalogResponse(
        sites=1,
        tents=len(body.tents),
        zones=len(body.zones),
        devices=len(body.devices),
        capabilities=len(body.capabilities),
        schedules=len(body.schedules),
        plant_lines=len(body.plant_lines),
        seed_lots=len(body.seed_lots),
        plants=len(body.plants),
        plant_locations=len(body.plant_locations),
        cross_events=len(body.cross_events),
        plant_notes=len(body.plant_notes),
        plant_events=len(body.plant_events),
        plant_metric_streams=len(body.plant_metric_streams),
    )


@router.put("/wiki", response_model=WikiProjectionResponse)
async def wiki_projection(
    body: WikiProjectionRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> WikiProjectionResponse:
    require_gateway_scope(principal, body.site_id)
    now = clock()
    incoming_paths = {page.path for page in body.pages}
    upserted = 0
    for page in body.pages:
        await _upsert_by_columns(
            session,
            CloudWikiPage,
            {"site_id": body.site_id, "path": page.path},
            {
                "site_id": body.site_id,
                "path": page.path,
                "title": page.title,
                "frontmatter": page.frontmatter,
                "body_markdown": page.body_markdown,
                "sha256": page.sha256,
                "source_updated_at": page.source_updated_at,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
        upserted += 1

    existing = (
        await session.execute(
            select(CloudWikiPage).where(CloudWikiPage.site_id == body.site_id)
        )
    ).scalars()
    deleted = 0
    for row in existing:
        if row.path not in incoming_paths:
            await session.delete(row)
            deleted += 1

    await session.commit()
    return WikiProjectionResponse(upserted=upserted, deleted=deleted, synced_at=now)


@router.put("/metrics/latest", response_model=UpsertCountResponse)
async def metrics_latest(
    body: LatestMetricsRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> UpsertCountResponse:
    require_gateway_scope(principal, body.site_id)
    now = clock()
    for metric in body.metrics:
        require_gateway_scope(principal, metric.site_id)
        storage_tent_id = await _storage_tent_id_from_projection(
            session,
            site_id=metric.site_id,
            source_tent_id=metric.source_tent_id,
        )
        storage_zone_id = await _storage_zone_id_from_projection(
            session,
            site_id=metric.site_id,
            source_zone_id=metric.source_zone_id,
        )
        await _upsert_with_legacy_bridge(
            session,
            CloudLatestMetric,
            {
                "site_id": metric.site_id,
                "source_tent_id": metric.source_tent_id,
                "device_id": metric.device_id,
                "capability_id": metric.capability_id,
                "metric": metric.metric,
            },
            {
                "site_id": metric.site_id,
                "tent_id": storage_tent_id,
                "device_id": metric.device_id,
                "capability_id": metric.capability_id,
                "metric": metric.metric,
            },
            {
                "site_id": metric.site_id,
                "source_site_id": metric.source_site_id,
                "source_tent_id": metric.source_tent_id,
                "source_zone_id": metric.source_zone_id,
                "tent_id": storage_tent_id,
                "zone_id": storage_zone_id,
                "device_id": metric.device_id,
                "capability_id": metric.capability_id,
                "metric": metric.metric,
                "value": metric.value,
                "unit": metric.unit,
                "source_updated_at": metric.source_updated_at,
                "received_at": now,
                "stale_after_s": metric.stale_after_s,
            },
            now=now,
        )
    await session.commit()
    return UpsertCountResponse(upserted=len(body.metrics))


@router.get(
    "/cameras/{camera_device_id}/capture-policy",
    response_model=CapturePolicyResponse,
)
async def camera_capture_policy(
    camera_device_id: str,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
) -> CapturePolicyResponse:
    site_id = principal.allowed_site_id
    site_timezone = (
        await session.scalar(
            select(CloudSite.timezone).where(CloudSite.site_id == site_id).limit(1)
        )
        or "America/Denver"
    )
    camera = (
        await session.execute(
            select(CloudDevice, CloudTent)
            .outerjoin(
                CloudTent,
                (CloudTent.site_id == CloudDevice.site_id)
                & (CloudTent.source_tent_id == CloudDevice.source_tent_id),
            )
            .where(CloudDevice.site_id == site_id)
            .where(CloudDevice.device_id == camera_device_id)
            .where(CloudDevice.kind == "camera")
            .order_by(CloudDevice.is_active.desc(), CloudDevice.synced_at.desc())
            .limit(1)
        )
    ).first()
    if camera is None:
        return _open_capture_policy(
            site_id=site_id,
            source_site_id=None,
            source_tent_id=None,
            tent_name=None,
            camera_device_id=camera_device_id,
            timezone=site_timezone,
            reason="camera_not_found",
        )
    camera_device, tent = camera
    if not camera_device.is_active:
        return CapturePolicyResponse(
            site_id=site_id,
            source_site_id=None if tent is None else tent.source_site_id,
            source_tent_id=camera_device.source_tent_id,
            tent_name=None if tent is None else tent.name,
            camera_device_id=camera_device_id,
            enabled=False,
            require_lights_on=False,
            lights_on_local=None,
            lights_off_local=None,
            timezone=site_timezone,
            source_schedule_id=None,
            reason="camera_disabled",
        )

    schedule = (
        await session.execute(
            select(CloudSchedule)
            .where(CloudSchedule.site_id == camera_device.site_id)
            .where(CloudSchedule.source_tent_id == camera_device.source_tent_id)
            .where(CloudSchedule.kind == "lights")
            .where(CloudSchedule.is_enabled.is_(True))
            .order_by(CloudSchedule.synced_at.desc(), CloudSchedule.source_schedule_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if schedule is None:
        return _open_capture_policy(
            site_id=site_id,
            source_site_id=None if tent is None else tent.source_site_id,
            source_tent_id=camera_device.source_tent_id,
            tent_name=None if tent is None else tent.name,
            camera_device_id=camera_device_id,
            timezone=site_timezone,
            reason="lights_schedule_not_found",
        )

    return CapturePolicyResponse(
        site_id=site_id,
        source_site_id=schedule.source_site_id,
        source_tent_id=camera_device.source_tent_id,
        tent_name=None if tent is None else tent.name,
        camera_device_id=camera_device_id,
        enabled=True,
        require_lights_on=True,
        lights_on_local=schedule.starts_local,
        lights_off_local=schedule.ends_local,
        timezone=schedule.timezone,
        source_schedule_id=schedule.source_schedule_id,
        reason=None,
    )


@router.post("/metrics/rollups", response_model=UpsertCountResponse)
async def metrics_rollups(
    body: RollupsRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> UpsertCountResponse:
    require_gateway_scope(principal, body.site_id)
    now = clock()
    for rollup in body.rollups:
        require_gateway_scope(principal, rollup.site_id)
        storage_tent_id = await _storage_tent_id_from_projection(
            session,
            site_id=rollup.site_id,
            source_tent_id=rollup.source_tent_id,
        )
        await _upsert_with_legacy_bridge(
            session,
            CloudMetricRollup,
            {
                "site_id": rollup.site_id,
                "source_tent_id": rollup.source_tent_id,
                "device_id": rollup.device_id,
                "capability_id": rollup.capability_id,
                "metric": rollup.metric,
                "bucket": rollup.bucket,
                "bucket_start_at": rollup.bucket_start_at,
            },
            {
                "site_id": rollup.site_id,
                "tent_id": storage_tent_id,
                "device_id": rollup.device_id,
                "capability_id": rollup.capability_id,
                "metric": rollup.metric,
                "bucket": rollup.bucket,
                "bucket_start_at": rollup.bucket_start_at,
            },
            {
                "site_id": rollup.site_id,
                "source_site_id": rollup.source_site_id,
                "source_tent_id": rollup.source_tent_id,
                "tent_id": storage_tent_id,
                "device_id": rollup.device_id,
                "capability_id": rollup.capability_id,
                "metric": rollup.metric,
                "bucket": rollup.bucket,
                "bucket_start_at": rollup.bucket_start_at,
                "bucket_end_at": rollup.bucket_end_at,
                "min_value": rollup.min_value,
                "avg_value": rollup.avg_value,
                "max_value": rollup.max_value,
                "sample_count": rollup.sample_count,
                "unit": rollup.unit,
                "received_at": now,
            },
            now=now,
        )
    await session.commit()
    return UpsertCountResponse(upserted=len(body.rollups))


@router.post("/assets/sign-upload", response_model=SignUploadResponse)
async def sign_upload(
    body: AssetSignUploadRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    settings: CloudSettings = Depends(get_settings),
    asset_store: AssetStore = Depends(get_asset_store),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> dict[str, Any]:
    require_gateway_scope(principal, body.site_id)
    expires_at = expires_from(clock(), settings.upload_url_ttl_s)
    upload_url = asset_store.presign_put(
        object_key=body.object_key,
        content_type=body.content_type,
        expires_in_s=settings.upload_url_ttl_s,
    )
    return {
        "asset_id": body.asset_id,
        "object_key": body.object_key,
        "upload_url": upload_url,
        "method": "PUT",
        "headers": {"Content-Type": body.content_type},
        "expires_at": expires_at,
        "byte_size": body.byte_size,
    }


@router.post("/assets/complete", response_model=AssetCompleteResponse)
async def complete_asset(
    body: AssetCompleteRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> dict[str, Any]:
    require_gateway_scope(principal, body.site_id)
    now = clock()
    asset_id = body.asset_id or body.sha256 or body.object_key
    tent_id = await _asset_storage_tent_id(session, body)
    zone_id = await _storage_zone_id_from_projection(
        session,
        site_id=body.site_id,
        source_zone_id=body.source_zone_id,
    )
    await _upsert_cloud_asset(
        session,
        {
            "asset_id": asset_id,
            "site_id": body.site_id,
            "source_tent_id": body.source_tent_id,
            "source_zone_id": body.source_zone_id,
            "tent_id": tent_id,
            "zone_id": zone_id,
            "device_id": body.device_id,
            "kind": body.kind,
            "object_key": body.object_key,
            "content_type": body.content_type,
            "byte_size": body.byte_size,
            "sha256": body.sha256,
            "captured_at": body.captured_at,
            "uploaded_at": now,
        },
        now=now,
    )
    add_audit_event(
        session,
        now=now,
        event_type="asset_upload_completed",
        actor_type="gateway",
        actor_id=principal.gateway_id,
        site_id=body.site_id,
        subject_type="cloud_asset",
        subject_id=asset_id,
        metadata={
            "source_tent_id": body.source_tent_id,
            "tent_id": tent_id,
            "object_key": body.object_key,
            "content_type": body.content_type,
            "byte_size": body.byte_size,
        },
    )
    await session.commit()
    return {"asset_id": asset_id, "object_key": body.object_key, "uploaded_at": now}


@router.post("/assets/upload-failure", response_model=AssetFailureResponse)
async def asset_upload_failure(
    body: AssetFailureRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> dict[str, Any]:
    require_gateway_scope(principal, body.site_id)
    now = clock()
    add_audit_event(
        session,
        now=now,
        event_type="asset_upload_failed",
        actor_type="gateway",
        actor_id=principal.gateway_id,
        site_id=body.site_id,
        subject_type="cloud_asset",
        subject_id=body.asset_id,
        metadata={
            "source_tent_id": body.source_tent_id,
            "object_key": body.object_key,
            "stage": body.stage,
            "error": body.error,
        },
    )
    await session.commit()
    return {"ok": True, "received_at": now}


@router.post("/assets/prune-expired", response_model=PruneAssetsResponse)
async def prune_assets(  # noqa: PLR0913
    body: AssetRetentionRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    settings: CloudSettings = Depends(get_settings),
    asset_store: AssetStore = Depends(get_asset_store),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> dict[str, Any]:
    require_gateway_scope(principal, body.site_id)
    result = await prune_expired_assets(
        session,
        settings=settings,
        now=clock(),
        actor_type="gateway",
        actor_id=principal.gateway_id,
        site_id=body.site_id,
        object_store=asset_store,
    )
    return {
        "cutoff": result.cutoff,
        "matched": result.matched,
        "objects_deleted": result.objects_deleted,
    }


@router.post(
    "/commands/claim",
    response_model=CommandClaimResponse,
)
async def claim_commands(
    body: CommandClaimRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandClaimResponse:
    require_gateway_scope(principal, body.site_id)
    now = clock()
    if not settings.gateway_command_claim_enabled:
        return CommandClaimResponse(commands=[])
    expired_rows = (
        await session.execute(
            select(CloudCommand).where(
                CloudCommand.site_id == body.site_id,
                CloudCommand.status.in_(["queued", "claimed"]),
                CloudCommand.expires_at <= now,
            )
        )
    ).scalars()
    for command in expired_rows:
        command.status = "expired"
        command.finished_at = now
        command.error = "command expired before local execution"
        command.updated_at = now

    previously_claimed = (
        await session.execute(
            select(CloudCommand)
            .where(
                CloudCommand.site_id == body.site_id,
                CloudCommand.status == "claimed",
                CloudCommand.claimed_by == principal.gateway_id,
                CloudCommand.expires_at > now,
            )
            .order_by(CloudCommand.claimed_at, CloudCommand.queued_at)
            .limit(body.limit)
        )
    ).scalars()
    commands = [_command_payload(command) for command in previously_claimed]
    remaining = body.limit - len(commands)
    if remaining <= 0:
        await session.commit()
        return CommandClaimResponse(commands=commands)

    rows = (
        await session.execute(
            select(CloudCommand)
            .where(
                CloudCommand.site_id == body.site_id,
                CloudCommand.status == "queued",
                CloudCommand.expires_at > now,
            )
            .order_by(CloudCommand.queued_at)
            .limit(remaining)
        )
    ).scalars()
    for command in rows:
        command.status = "claimed"
        command.claimed_by = principal.gateway_id
        command.claimed_at = now
        command.updated_at = now
        add_audit_event(
            session,
            now=now,
            event_type="command_claimed",
            actor_type="gateway",
            actor_id=principal.gateway_id,
            site_id=body.site_id,
            subject_type="cloud_command",
            subject_id=command.command_id,
            metadata={"command_type": command.command_type},
        )
        commands.append(_command_payload(command))
    await session.commit()
    return CommandClaimResponse(commands=commands)


@router.post(
    "/commands/{command_id}/result",
    response_model=CommandResultResponse,
)
async def command_result(
    command_id: str,
    body: CommandResultRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResultResponse:
    require_gateway_scope(principal, body.site_id)
    command = (
        await session.execute(
            select(CloudCommand).where(CloudCommand.command_id == command_id)
        )
    ).scalar_one_or_none()
    if command is None or command.site_id != body.site_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "command not found")
    if command.status in {"succeeded", "failed", "rejected", "expired"}:
        return _command_payload(command)

    now = clock()
    command.status = body.status
    command.result = body.result
    command.error = body.error
    command.updated_at = now
    if body.status == "running" and command.started_at is None:
        command.started_at = now
    if body.status in {"succeeded", "failed", "rejected", "expired"}:
        command.finished_at = now
    add_audit_event(
        session,
        now=now,
        event_type="command_result_reported",
        actor_type="gateway",
        actor_id=principal.gateway_id,
        site_id=body.site_id,
        subject_type="cloud_command",
        subject_id=command.command_id,
        metadata={"status": body.status, "error": body.error},
    )
    await session.commit()
    await session.refresh(command)
    return _command_payload(command)


async def _upsert_by_columns(
    session: AsyncSession,
    model: type[ModelT],
    identity: dict[str, Any],
    values: dict[str, Any],
    *,
    now: datetime,
) -> ModelT:
    row = (
        await session.execute(
            select(model).where(
                *(getattr(model, key) == value for key, value in identity.items())
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = model(**values)
        session.add(row)
        return row

    _apply_upsert_values(row, values, now=now)
    return row


async def _upsert_with_legacy_bridge(  # noqa: PLR0913
    session: AsyncSession,
    model: type[ModelT],
    source_identity: dict[str, Any],
    legacy_identity: dict[str, Any],
    values: dict[str, Any],
    *,
    now: datetime,
) -> ModelT:
    row = await _find_by_identity(session, model, source_identity)
    if row is None:
        row = await _find_by_identity(session, model, legacy_identity)
    if row is None:
        row = model(**values)
        session.add(row)
        return row

    _apply_upsert_values(row, values, now=now)
    return row


async def _find_by_identity(
    session: AsyncSession,
    model: type[ModelT],
    identity: dict[str, Any],
) -> ModelT | None:
    return (
        await session.execute(
            select(model).where(
                *(getattr(model, key) == value for key, value in identity.items())
            )
        )
    ).scalar_one_or_none()


def _storage_tent_id(source_tent_id: int) -> str:
    return str(source_tent_id)


def _storage_tent_id_from_map(
    source_tent_id: int,
    *,
    storage_tent_ids: dict[int, str],
) -> str:
    return storage_tent_ids.get(source_tent_id, str(source_tent_id))


def _storage_zone_id(source_zone_id: int) -> str:
    return str(source_zone_id)


def _storage_zone_id_from_map(
    source_zone_id: int | None,
    *,
    storage_zone_ids: dict[int, str],
) -> str | None:
    if source_zone_id is None:
        return None
    return storage_zone_ids.get(source_zone_id, str(source_zone_id))


def _storage_schedule_id(source_schedule_id: int) -> str:
    return str(source_schedule_id)


async def _storage_tent_id_from_projection(
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
) -> str:
    storage_tent_id = await session.scalar(
        select(CloudTent.tent_id)
        .where(CloudTent.site_id == site_id)
        .where(CloudTent.source_tent_id == source_tent_id)
        .limit(1)
    )
    return storage_tent_id or str(source_tent_id)


async def _storage_zone_id_from_projection(
    session: AsyncSession,
    *,
    site_id: str,
    source_zone_id: int | None,
) -> str | None:
    if source_zone_id is None:
        return None
    storage_zone_id = await session.scalar(
        select(CloudZone.zone_id)
        .where(CloudZone.site_id == site_id)
        .where(CloudZone.source_zone_id == source_zone_id)
        .limit(1)
    )
    return storage_zone_id or str(source_zone_id)


def _open_capture_policy(  # noqa: PLR0913
    *,
    site_id: str,
    source_site_id: int | None,
    source_tent_id: int | None,
    tent_name: str | None,
    camera_device_id: str,
    timezone: str,
    reason: CapturePolicyReason,
) -> CapturePolicyResponse:
    return CapturePolicyResponse(
        site_id=site_id,
        source_site_id=source_site_id,
        source_tent_id=source_tent_id,
        tent_name=tent_name,
        camera_device_id=camera_device_id,
        enabled=True,
        require_lights_on=False,
        lights_on_local=None,
        lights_off_local=None,
        timezone=timezone,
        source_schedule_id=None,
        reason=reason,
    )


async def _asset_storage_tent_id(
    session: AsyncSession,
    body: AssetCompleteRequest,
) -> str:
    if body.source_tent_id is not None:
        storage_tent_id = await _storage_tent_id_from_projection(
            session,
            site_id=body.site_id,
            source_tent_id=body.source_tent_id,
        )
        return storage_tent_id
    if body.device_id is not None:
        device_tent_id = await session.scalar(
            select(CloudDevice.tent_id)
            .where(CloudDevice.site_id == body.site_id)
            .where(CloudDevice.device_id == body.device_id)
            .order_by(CloudDevice.synced_at.desc())
            .limit(1)
        )
        if device_tent_id is not None:
            return device_tent_id
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="asset completion requires source_tent_id or device_id",
    )


async def _upsert_cloud_asset(
    session: AsyncSession,
    values: dict[str, Any],
    *,
    now: datetime,
) -> CloudAsset:
    asset_id = values["asset_id"]
    row = (
        await session.execute(select(CloudAsset).where(CloudAsset.asset_id == asset_id))
    ).scalar_one_or_none()
    if row is None:
        source_tent_id = values.get("source_tent_id")
        if source_tent_id is not None:
            row = (
                await session.execute(
                    select(CloudAsset).where(
                        CloudAsset.site_id == values["site_id"],
                        CloudAsset.source_tent_id == source_tent_id,
                        CloudAsset.object_key == values["object_key"],
                    )
                )
            ).scalar_one_or_none()
    if row is None:
        row = (
            await session.execute(
                select(CloudAsset).where(
                    CloudAsset.site_id == values["site_id"],
                    CloudAsset.tent_id == values["tent_id"],
                    CloudAsset.object_key == values["object_key"],
                )
            )
        ).scalar_one_or_none()
    if row is None:
        row = CloudAsset(**values)
        session.add(row)
        return row

    _apply_upsert_values(row, values, now=now)
    return row


def _apply_upsert_values(row: ModelT, values: dict[str, Any], *, now: datetime) -> None:
    for key, value in values.items():
        if key == "created_at":
            continue
        setattr(row, key, value)
    if hasattr(row, "updated_at"):
        row.updated_at = now


def _command_payload(command: CloudCommand) -> CommandResultResponse:
    return CommandResultResponse(
        command_id=command.command_id,
        site_id=command.site_id,
        target=_command_target(command),
        command_type=command.command_type,
        payload=command.payload,
        status=command.status,
        queued_at=command.queued_at,
        expires_at=command.expires_at,
        claimed_by=command.claimed_by,
        claimed_at=command.claimed_at,
        requested_by=command.requested_by,
        started_at=command.started_at,
        finished_at=command.finished_at,
        result=command.result,
        error=command.error,
    )


def _command_target(command: CloudCommand) -> PtzCommandTarget | None:
    if command.command_type not in {"ptz_preset", "ptz_look", "ptz_zoom"}:
        return None
    if command.source_tent_id is None:
        return None
    if command.device_id != "obsbot-main" or command.capability_id != "ptz_move":
        return None
    return PtzCommandTarget(
        kind="ptz",
        source_tent_id=command.source_tent_id,
        device_id="obsbot-main",
        capability_id="ptz_move",
    )
