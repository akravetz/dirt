from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from dirt_control.audit import add_audit_event
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.models import (
    CloudAsset,
    CloudCapability,
    CloudCommand,
    CloudDevice,
    CloudLatestMetric,
    CloudMetricRollup,
    CloudSchedule,
    CloudSite,
    CloudTent,
    CloudZone,
    GatewayCredential,
)
from dirt_control.retention import prune_expired_assets
from dirt_control.security import (
    GatewayPrincipal,
    UrlSigner,
    authenticate_gateway,
    expires_from,
    require_gateway_scope,
)
from dirt_control.settings import CloudSettings
from dirt_control.storage import S3ObjectStore
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
    RollupItem,
    RollupsRequest,
    SignUploadResponse,
    UpsertCountResponse,
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
    credential = await session.get(GatewayCredential, principal.credential_id)
    if credential is not None:
        credential.last_used_at = now
        credential.updated_at = now
    site = await session.get(CloudSite, body.site_id)
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
    require_gateway_scope(principal, body.site.site_id)
    now = clock()
    await _upsert(
        session,
        CloudSite,
        body.site.site_id,
        {
            "site_id": body.site.site_id,
            "name": body.site.name,
            "timezone": body.site.timezone,
            "is_active": True,
            "last_catalog_sync_at": now,
            "created_at": now,
            "updated_at": now,
        },
        now=now,
    )
    for tent in body.tents:
        await _upsert(
            session,
            CloudTent,
            _tent_key(body.site.site_id, tent.tent_id),
            {
                "tent_key": _tent_key(body.site.site_id, tent.tent_id),
                "site_id": body.site.site_id,
                "tent_id": tent.tent_id,
                "name": tent.name,
                "is_active": tent.is_active,
                "synced_at": now,
                "created_at": now,
                "updated_at": now,
            },
            now=now,
        )
    for zone in body.zones:
        await _upsert(
            session,
            CloudZone,
            _zone_key(body.site.site_id, zone.tent_id, zone.zone_id),
            {
                "zone_key": _zone_key(body.site.site_id, zone.tent_id, zone.zone_id),
                "site_id": body.site.site_id,
                "tent_id": zone.tent_id,
                "zone_id": zone.zone_id,
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
        await _upsert(
            session,
            CloudDevice,
            _device_key(body.site.site_id, device.tent_id, device.device_id),
            {
                "device_key": _device_key(
                    body.site.site_id, device.tent_id, device.device_id
                ),
                "site_id": body.site.site_id,
                "tent_id": device.tent_id,
                "zone_id": device.zone_id,
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
        await _upsert(
            session,
            CloudCapability,
            _capability_key(
                body.site.site_id, capability.tent_id, capability.capability_id
            ),
            {
                "capability_key": _capability_key(
                    body.site.site_id, capability.tent_id, capability.capability_id
                ),
                "site_id": body.site.site_id,
                "tent_id": capability.tent_id,
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
        require_gateway_scope(principal, schedule.site_id)
        key = _schedule_key(schedule.site_id, schedule.tent_id, schedule.schedule_id)
        await _upsert(
            session,
            CloudSchedule,
            key,
            {
                "schedule_key": key,
                "site_id": schedule.site_id,
                "tent_id": schedule.tent_id,
                "zone_id": schedule.zone_id,
                "device_id": schedule.device_id,
                "capability_id": schedule.capability_id,
                "schedule_id": schedule.schedule_id,
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
    await session.commit()
    return CatalogResponse(
        sites=1,
        tents=len(body.tents),
        zones=len(body.zones),
        devices=len(body.devices),
        capabilities=len(body.capabilities),
        schedules=len(body.schedules),
    )


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
        key = _metric_key(
            metric.site_id, metric.tent_id, metric.capability_id, metric.metric
        )
        await _upsert(
            session,
            CloudLatestMetric,
            key,
            {
                "metric_key": key,
                "site_id": metric.site_id,
                "tent_id": metric.tent_id,
                "zone_id": metric.zone_id,
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
            select(CloudDevice)
            .where(CloudDevice.site_id == site_id)
            .where(CloudDevice.device_id == camera_device_id)
            .where(CloudDevice.kind == "camera")
            .order_by(CloudDevice.is_active.desc(), CloudDevice.synced_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if camera is None:
        return _open_capture_policy(
            site_id=site_id,
            tent_id=None,
            camera_device_id=camera_device_id,
            timezone=site_timezone,
            reason="camera_not_found",
        )
    if not camera.is_active:
        return CapturePolicyResponse(
            site_id=site_id,
            tent_id=camera.tent_id,
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
            .where(CloudSchedule.site_id == camera.site_id)
            .where(CloudSchedule.tent_id == camera.tent_id)
            .where(CloudSchedule.kind == "lights")
            .where(CloudSchedule.is_enabled.is_(True))
            .order_by(CloudSchedule.synced_at.desc(), CloudSchedule.schedule_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if schedule is None:
        return _open_capture_policy(
            site_id=site_id,
            tent_id=camera.tent_id,
            camera_device_id=camera_device_id,
            timezone=site_timezone,
            reason="lights_schedule_not_found",
        )

    return CapturePolicyResponse(
        site_id=site_id,
        tent_id=camera.tent_id,
        camera_device_id=camera_device_id,
        enabled=True,
        require_lights_on=True,
        lights_on_local=schedule.starts_local,
        lights_off_local=schedule.ends_local,
        timezone=schedule.timezone,
        source_schedule_id=schedule.schedule_id,
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
        key = _rollup_key(rollup)
        await _upsert(
            session,
            CloudMetricRollup,
            key,
            {
                "rollup_key": key,
                "site_id": rollup.site_id,
                "tent_id": rollup.tent_id,
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
    clock: Callable[[], datetime] = Depends(get_clock),
) -> dict[str, Any]:
    require_gateway_scope(principal, body.site_id)
    expires_at = expires_from(clock(), settings.upload_url_ttl_s)
    object_store = _object_store(settings)
    if object_store is None:
        signer = UrlSigner(settings.session_secret)
        upload_url = signer.build_signed_url(
            base_url=settings.public_asset_base_url,
            subject=body.object_key,
            expires_at=expires_at,
            params={"method": "PUT", "content_type": body.content_type},
        )
    else:
        upload_url = object_store.presign_put(
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
    await _upsert_cloud_asset(
        session,
        {
            "asset_id": asset_id,
            "site_id": body.site_id,
            "tent_id": body.tent_id,
            "zone_id": body.zone_id,
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
            "tent_id": body.tent_id,
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
            "tent_id": body.tent_id,
            "object_key": body.object_key,
            "stage": body.stage,
            "error": body.error,
        },
    )
    await session.commit()
    return {"ok": True, "received_at": now}


@router.post("/assets/prune-expired", response_model=PruneAssetsResponse)
async def prune_assets(
    body: AssetRetentionRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    settings: CloudSettings = Depends(get_settings),
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
        object_store=_object_store(settings),
    )
    return {
        "cutoff": result.cutoff,
        "matched": result.matched,
        "objects_deleted": result.objects_deleted,
    }


@router.post("/commands/claim", response_model=CommandClaimResponse)
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


@router.post("/commands/{command_id}/result", response_model=CommandResultResponse)
async def command_result(
    command_id: str,
    body: CommandResultRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResultResponse:
    require_gateway_scope(principal, body.site_id)
    command = await session.get(CloudCommand, command_id)
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


async def _upsert(
    session: AsyncSession,
    model: type[ModelT],
    primary_key: Any,
    values: dict[str, Any],
    *,
    now: datetime,
) -> ModelT:
    row = await session.get(model, primary_key)
    if row is None:
        row = model(**values)
        session.add(row)
        return row

    for key, value in values.items():
        if key == "created_at":
            continue
        setattr(row, key, value)
    if hasattr(row, "updated_at"):
        row.updated_at = now
    return row


def _open_capture_policy(
    *,
    site_id: str,
    tent_id: str | None,
    camera_device_id: str,
    timezone: str,
    reason: CapturePolicyReason,
) -> CapturePolicyResponse:
    return CapturePolicyResponse(
        site_id=site_id,
        tent_id=tent_id,
        camera_device_id=camera_device_id,
        enabled=True,
        require_lights_on=False,
        lights_on_local=None,
        lights_off_local=None,
        timezone=timezone,
        source_schedule_id=None,
        reason=reason,
    )


async def _upsert_cloud_asset(
    session: AsyncSession,
    values: dict[str, Any],
    *,
    now: datetime,
) -> CloudAsset:
    asset_id = values["asset_id"]
    row = await session.get(CloudAsset, asset_id)
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

    for key, value in values.items():
        if key == "created_at":
            continue
        setattr(row, key, value)
    if hasattr(row, "updated_at"):
        row.updated_at = now
    return row


def _tent_key(site_id: str, tent_id: str) -> str:
    return f"{site_id}:{tent_id}"


def _zone_key(site_id: str, tent_id: str, zone_id: str) -> str:
    return f"{site_id}:{tent_id}:{zone_id}"


def _device_key(site_id: str, tent_id: str, device_id: str) -> str:
    return f"{site_id}:{tent_id}:{device_id}"


def _capability_key(site_id: str, tent_id: str, capability_id: str) -> str:
    return f"{site_id}:{tent_id}:{capability_id}"


def _schedule_key(site_id: str, tent_id: str, schedule_id: str) -> str:
    return f"{site_id}:{tent_id}:{schedule_id}"


def _metric_key(site_id: str, tent_id: str, capability_id: str, metric: str) -> str:
    return f"{site_id}:{tent_id}:{capability_id}:{metric}"


def _rollup_key(rollup: RollupItem) -> str:
    return (
        f"{rollup.site_id}:{rollup.tent_id}:{rollup.capability_id}:"
        f"{rollup.metric}:{rollup.bucket}:{rollup.bucket_start_at.isoformat()}"
    )


def _command_payload(command: CloudCommand) -> CommandResultResponse:
    return CommandResultResponse(
        command_id=command.command_id,
        site_id=command.site_id,
        tent_id=command.tent_id,
        device_id=command.device_id,
        capability_id=command.capability_id,
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


def _object_store(settings: CloudSettings) -> S3ObjectStore | None:
    if not (
        settings.s3_endpoint
        and settings.s3_region
        and settings.s3_access_key_id
        and settings.s3_secret_access_key
    ):
        return None
    return S3ObjectStore(settings=settings)
