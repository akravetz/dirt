from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.models import (
    CloudAsset,
    CloudCommand,
    CloudDevice,
    CloudLatestMetric,
    CloudMetricRollup,
    CloudSite,
    CloudTent,
)
from dirt_control.security import (
    UrlSigner,
    expires_from,
    require_browser_user,
    verify_password,
)
from dirt_control.settings import CloudSettings

router = APIRouter(prefix="/api")
COMMAND_EXPIRY_SECONDS = 60
PTZ_COMMAND_TYPES = Literal["ptz_preset", "ptz_look", "ptz_zoom"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class CommandCreateRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=160)
    site_id: str | None = None
    tent_id: str = Field(min_length=1, max_length=80)
    device_id: Literal["obsbot-main"]
    capability_id: Literal["ptz_move"]
    command_type: PTZ_COMMAND_TYPES
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/auth/login")
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    settings: CloudSettings = Depends(get_settings),
) -> dict[str, str]:
    if body.username != settings.admin_username or not verify_password(
        body.password, settings.admin_password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    request.app.state.sessions.create_cookie(response, body.username)
    return {"username": body.username}


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, request: Request) -> None:
    request.app.state.sessions.clear_cookie(response)


@router.get("/auth/me")
async def me(user: str = Depends(require_browser_user)) -> dict[str, str]:
    return {"username": user}


@router.get("/sites")
async def sites(
    _: str = Depends(require_browser_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(select(CloudSite).order_by(CloudSite.site_id))
    ).scalars()
    return [
        {
            "site_id": row.site_id,
            "name": row.name,
            "timezone": row.timezone,
            "is_active": row.is_active,
            "gateway_last_seen_at": row.gateway_last_seen_at,
            "last_catalog_sync_at": row.last_catalog_sync_at,
        }
        for row in rows
    ]


@router.get("/tents")
async def tents(
    site_id: str | None = None,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    scoped_site_id = site_id or settings.default_site_id
    rows = (
        await session.execute(
            select(CloudTent)
            .where(CloudTent.site_id == scoped_site_id)
            .order_by(CloudTent.tent_id)
        )
    ).scalars()
    return [
        {
            "site_id": row.site_id,
            "tent_id": row.tent_id,
            "name": row.name,
            "is_active": row.is_active,
            "synced_at": row.synced_at,
        }
        for row in rows
    ]


@router.get("/tents/{tent_id}/state")
async def tent_state(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    site = await session.get(CloudSite, settings.default_site_id)
    tent = (
        await session.execute(
            select(CloudTent).where(
                CloudTent.site_id == settings.default_site_id,
                CloudTent.tent_id == tent_id,
            )
        )
    ).scalar_one_or_none()
    if tent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tent not found")
    return {
        "site_id": tent.site_id,
        "tent_id": tent.tent_id,
        "name": tent.name,
        "is_active": tent.is_active,
        "gateway_last_seen_at": site.gateway_last_seen_at if site else None,
        "last_catalog_sync_at": site.last_catalog_sync_at if site else None,
    }


@router.get("/tents/{tent_id}/metrics/current")
async def current_metrics(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(CloudLatestMetric)
            .where(
                CloudLatestMetric.site_id == settings.default_site_id,
                CloudLatestMetric.tent_id == tent_id,
            )
            .order_by(CloudLatestMetric.metric)
        )
    ).scalars()
    return [
        {
            "metric": row.metric,
            "value": row.value,
            "unit": row.unit,
            "capability_id": row.capability_id,
            "device_id": row.device_id,
            "source_updated_at": row.source_updated_at,
            "received_at": row.received_at,
            "stale_after_s": row.stale_after_s,
        }
        for row in rows
    ]


@router.get("/tents/{tent_id}/metrics/history")
async def metric_history(
    tent_id: str,
    metric: str,
    range: str = "24h",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(CloudMetricRollup)
            .where(
                CloudMetricRollup.site_id == settings.default_site_id,
                CloudMetricRollup.tent_id == tent_id,
                CloudMetricRollup.metric == metric,
            )
            .order_by(CloudMetricRollup.bucket_start_at)
        )
    ).scalars()
    return {
        "metric": metric,
        "range": range,
        "points": [
            {
                "bucket": row.bucket,
                "bucket_start_at": row.bucket_start_at,
                "bucket_end_at": row.bucket_end_at,
                "min": row.min_value,
                "avg": row.avg_value,
                "max": row.max_value,
                "sample_count": row.sample_count,
                "unit": row.unit,
            }
            for row in rows
        ],
    }


@router.get("/tents/{tent_id}/devices")
async def devices(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(CloudDevice)
            .where(
                CloudDevice.site_id == settings.default_site_id,
                CloudDevice.tent_id == tent_id,
            )
            .order_by(CloudDevice.device_id)
        )
    ).scalars()
    return [
        {
            "device_id": row.device_id,
            "name": row.name,
            "kind": row.kind,
            "controller": row.controller,
            "is_active": row.is_active,
            "last_seen_at": row.last_seen_at,
        }
        for row in rows
    ]


@router.get("/tents/{tent_id}/assets/latest")
async def latest_assets(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(CloudAsset)
            .where(
                CloudAsset.site_id == settings.default_site_id,
                CloudAsset.tent_id == tent_id,
            )
            .order_by(desc(CloudAsset.captured_at))
            .limit(10)
        )
    ).scalars()
    signer = UrlSigner(settings.session_secret)
    now = clock()
    return [
        _asset_response(row, settings=settings, signer=signer, now=now) for row in rows
    ]


@router.get("/assets/{asset_id}/signed-url")
async def asset_signed_url(
    asset_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> dict[str, Any]:
    asset = await session.get(CloudAsset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    signer = UrlSigner(settings.session_secret)
    return _asset_response(asset, settings=settings, signer=signer, now=clock())


@router.get("/sync/status")
async def sync_status(
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> dict[str, Any]:
    site = await session.get(CloudSite, settings.default_site_id)
    command_backlog_depth = (
        await session.scalar(
            select(func.count())
            .select_from(CloudCommand)
            .where(
                CloudCommand.site_id == settings.default_site_id,
                CloudCommand.status.in_(["queued", "claimed", "running"]),
            )
        )
    ) or 0
    if site is None:
        return {
            "site_id": settings.default_site_id,
            "gateway_last_seen_at": None,
            "last_catalog_sync_at": None,
            "command_backlog_depth": command_backlog_depth,
            "status": "offline",
        }
    status_label = _sync_status_label(site.gateway_last_seen_at, now=clock())
    return {
        "site_id": site.site_id,
        "gateway_last_seen_at": site.gateway_last_seen_at,
        "last_catalog_sync_at": site.last_catalog_sync_at,
        "command_backlog_depth": command_backlog_depth,
        "status": status_label,
    }


@router.post("/commands", status_code=status.HTTP_201_CREATED)
async def create_command(
    body: CommandCreateRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> dict[str, Any]:
    existing = (
        await session.execute(
            select(CloudCommand).where(
                CloudCommand.requested_by == user,
                CloudCommand.idempotency_key == body.idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _command_response(existing)

    now = clock()
    site_id = body.site_id or settings.default_site_id
    if site_id != settings.default_site_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unsupported site")
    command = CloudCommand(
        command_id=str(uuid.uuid4()),
        idempotency_key=body.idempotency_key,
        site_id=site_id,
        tent_id=body.tent_id,
        device_id=body.device_id,
        capability_id=body.capability_id,
        command_type=body.command_type,
        payload=body.payload,
        requested_by=user,
        status="queued",
        queued_at=now,
        expires_at=now + timedelta(seconds=COMMAND_EXPIRY_SECONDS),
        created_at=now,
        updated_at=now,
    )
    session.add(command)
    await session.commit()
    await session.refresh(command)
    return _command_response(command)


@router.get("/commands/{command_id}")
async def get_command(
    command_id: str,
    user: str = Depends(require_browser_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    command = await session.get(CloudCommand, command_id)
    if command is None or command.requested_by != user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "command not found")
    return _command_response(command)


@router.get("/commands")
async def list_commands(
    status: str | None = None,
    user: str = Depends(require_browser_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(CloudCommand).where(CloudCommand.requested_by == user)
    if status is not None:
        stmt = stmt.where(CloudCommand.status == status)
    rows = (
        await session.execute(stmt.order_by(desc(CloudCommand.queued_at)).limit(50))
    ).scalars()
    return [_command_response(command) for command in rows]


def _asset_response(
    asset: CloudAsset,
    *,
    settings: CloudSettings,
    signer: UrlSigner,
    now: datetime,
) -> dict[str, Any]:
    expires_at = expires_from(now, settings.asset_url_ttl_s)
    signed_url = signer.build_signed_url(
        base_url=settings.public_asset_base_url,
        subject=asset.object_key,
        expires_at=expires_at,
    )
    return {
        "asset_id": asset.asset_id,
        "kind": asset.kind,
        "content_type": asset.content_type,
        "byte_size": asset.byte_size,
        "sha256": asset.sha256,
        "captured_at": asset.captured_at,
        "uploaded_at": asset.uploaded_at,
        "signed_url": signed_url,
        "signed_url_expires_at": expires_at,
    }


def _command_response(command: CloudCommand) -> dict[str, Any]:
    return {
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "site_id": command.site_id,
        "tent_id": command.tent_id,
        "device_id": command.device_id,
        "capability_id": command.capability_id,
        "command_type": command.command_type,
        "payload": command.payload,
        "status": command.status,
        "queued_at": command.queued_at,
        "expires_at": command.expires_at,
        "claimed_by": command.claimed_by,
        "claimed_at": command.claimed_at,
        "started_at": command.started_at,
        "finished_at": command.finished_at,
        "result": command.result,
        "error": command.error,
    }


def _sync_status_label(last_seen_at: datetime | None, *, now: datetime) -> str:
    if last_seen_at is None:
        return "offline"
    age_s = (now - last_seen_at).total_seconds()
    if age_s > 300:
        return "offline"
    if age_s > 90:
        return "stale"
    return "live"
