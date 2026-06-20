from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.common import SyncStatusLabel
from dirt_control.api.browser_schemas.health import HealthResponse, SyncStatusResponse
from dirt_control.audit import add_audit_event
from dirt_control.models import (
    CloudAuditEvent,
    CloudCommand,
    CloudDevice,
    CloudLatestMetric,
    CloudSite,
)
from dirt_control.settings import CloudSettings


async def health_status(
    session: AsyncSession, *, settings: CloudSettings, now: datetime
) -> HealthResponse:
    site = (
        await session.execute(
            select(CloudSite).where(CloudSite.site_id == settings.default_site_id)
        )
    ).scalar_one_or_none()
    backlog_depth = await command_backlog_depth(
        session, site_id=settings.default_site_id
    )
    command_failures_24h = (
        await session.scalar(
            select(func.count())
            .select_from(CloudCommand)
            .where(
                CloudCommand.site_id == settings.default_site_id,
                CloudCommand.status.in_(["failed", "rejected", "expired"]),
                CloudCommand.updated_at >= now - timedelta(days=1),
            )
        )
    ) or 0
    asset_failures_24h = (
        await session.scalar(
            select(func.count())
            .select_from(CloudAuditEvent)
            .where(
                CloudAuditEvent.site_id == settings.default_site_id,
                CloudAuditEvent.event_type == "asset_upload_failed",
                CloudAuditEvent.created_at >= now - timedelta(days=1),
            )
        )
    ) or 0
    gateway_heartbeat_age_s = None
    if site is not None and site.gateway_last_seen_at is not None:
        gateway_heartbeat_age_s = int((now - site.gateway_last_seen_at).total_seconds())
    sync_status = sync_status_label(
        site.gateway_last_seen_at if site else None, now=now
    )
    if site is not None:
        await audit_missing_device_liveness(
            session,
            site_id=settings.default_site_id,
            now=now,
        )
    return HealthResponse(
        service="control-plane-api",
        ok=True,
        site_id=settings.default_site_id,
        status=sync_status,
        gateway_last_seen_at=site.gateway_last_seen_at if site else None,
        gateway_heartbeat_age_s=gateway_heartbeat_age_s,
        gateway_backlog_depth=site.gateway_backlog_depth if site else 0,
        command_backlog_depth=backlog_depth,
        command_failures_24h=command_failures_24h,
        asset_failures_24h=asset_failures_24h,
        asset_retention_days=settings.asset_retention_days,
        commands_enabled=settings.command_creation_enabled
        and settings.gateway_command_claim_enabled,
    )


async def sync_status_response(
    session: AsyncSession, *, settings: CloudSettings, now: datetime
) -> SyncStatusResponse:
    site = (
        await session.execute(
            select(CloudSite).where(CloudSite.site_id == settings.default_site_id)
        )
    ).scalar_one_or_none()
    backlog_depth = await command_backlog_depth(
        session, site_id=settings.default_site_id
    )
    if site is None:
        return SyncStatusResponse(
            site_id=settings.default_site_id,
            gateway_last_seen_at=None,
            gateway_backlog_depth=0,
            last_catalog_sync_at=None,
            command_backlog_depth=backlog_depth,
            status="offline",
        )
    return SyncStatusResponse(
        site_id=site.site_id,
        gateway_last_seen_at=site.gateway_last_seen_at,
        gateway_backlog_depth=site.gateway_backlog_depth,
        last_catalog_sync_at=site.last_catalog_sync_at,
        command_backlog_depth=backlog_depth,
        status=sync_status_label(site.gateway_last_seen_at, now=now),
    )


def sync_status_label(
    last_seen_at: datetime | None, *, now: datetime
) -> SyncStatusLabel:
    if last_seen_at is None:
        return "offline"
    age_s = (now - last_seen_at).total_seconds()
    if age_s > 300:
        return "offline"
    if age_s > 90:
        return "stale"
    return "live"


async def audit_missing_device_liveness(
    session: AsyncSession,
    *,
    site_id: str,
    now: datetime,
) -> None:
    rows = (
        await session.execute(
            select(CloudDevice, CloudLatestMetric)
            .join(
                CloudLatestMetric,
                and_(
                    CloudLatestMetric.site_id == CloudDevice.site_id,
                    CloudLatestMetric.tent_id == CloudDevice.tent_id,
                    CloudLatestMetric.device_id == CloudDevice.device_id,
                ),
            )
            .where(
                CloudDevice.site_id == site_id,
                CloudDevice.is_active.is_(True),
                CloudDevice.last_seen_at.is_(None),
            )
            .order_by(CloudDevice.device_id, CloudLatestMetric.metric)
        )
    ).all()
    current_by_device: dict[str, tuple[CloudDevice, list[CloudLatestMetric]]] = {}
    for device, metric in rows:
        if not metric_is_current(metric, now=now):
            continue
        subject_id = device_audit_subject_id(device)
        _, metrics = current_by_device.setdefault(subject_id, (device, []))
        metrics.append(metric)
    if not current_by_device:
        return

    recent_subject_ids = set(
        (
            await session.execute(
                select(CloudAuditEvent.subject_id).where(
                    CloudAuditEvent.site_id == site_id,
                    CloudAuditEvent.event_type
                    == "data_consistency_missing_device_liveness",
                    CloudAuditEvent.created_at >= now - timedelta(hours=1),
                )
            )
        )
        .scalars()
        .all()
    )
    emitted = False
    for subject_id, (device, metrics) in current_by_device.items():
        if subject_id in recent_subject_ids:
            continue
        emitted = True
        add_audit_event(
            session,
            now=now,
            event_type="data_consistency_missing_device_liveness",
            actor_type="system",
            site_id=site_id,
            subject_type="cloud_device",
            subject_id=subject_id,
            metadata={
                "tent_id": device.tent_id,
                "device_id": device.device_id,
                "metrics": sorted({metric.metric for metric in metrics}),
                "capability_ids": sorted({metric.capability_id for metric in metrics}),
            },
        )
    if emitted:
        await session.commit()


def device_audit_subject_id(device: CloudDevice) -> str:
    return f"site={device.site_id};tent={device.tent_id};device={device.device_id}"


def metric_is_current(metric: CloudLatestMetric, *, now: datetime) -> bool:
    updated_at = same_timezone(metric.source_updated_at, now)
    return updated_at + timedelta(seconds=metric.stale_after_s) >= now


def same_timezone(value: datetime, reference: datetime) -> datetime:
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


async def command_backlog_depth(session: AsyncSession, *, site_id: str) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(CloudCommand)
            .where(
                CloudCommand.site_id == site_id,
                CloudCommand.status.in_(["queued", "claimed", "running"]),
            )
        )
    ) or 0
