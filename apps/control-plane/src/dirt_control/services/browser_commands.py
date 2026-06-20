from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.commands import (
    CommandCreateRequest,
    CommandResponse,
)
from dirt_control.audit import add_audit_event
from dirt_control.models import CloudCommand
from dirt_control.settings import CloudSettings
from dirt_shared.cloud_contract import (
    BreedingCommandPayload,
    CommandType,
    PtzCommandTarget,
)

COMMAND_EXPIRY_SECONDS = 60
BREEDING_COMMAND_EXPIRY_SECONDS = 3600
BREEDING_SITE_WIDE_TENT_ID = "breeding-logbook"
PTZ_COMMAND_TYPE_VALUES = frozenset({"ptz_preset", "ptz_look", "ptz_zoom"})


async def create_command(
    body: CommandCreateRequest,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
) -> CommandResponse:
    if not settings.command_creation_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "commands disabled")
    existing = (
        await session.execute(
            select(CloudCommand).where(
                CloudCommand.requested_by == user,
                CloudCommand.idempotency_key == body.idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return command_response(existing)

    site_id = body.site_id or settings.default_site_id
    if site_id != settings.default_site_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unsupported site")
    target = body.resolved_target()
    if target.source_tent_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "PTZ target requires source_tent_id",
        )
    source_tent_id = target.source_tent_id
    command = CloudCommand(
        command_id=str(uuid.uuid4()),
        idempotency_key=body.idempotency_key,
        site_id=site_id,
        tent_id=storage_compat_tent_id(source_tent_id),
        source_tent_id=source_tent_id,
        device_id=target.device_id,
        capability_id=target.capability_id,
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
    add_audit_event(
        session,
        now=now,
        event_type="command_created",
        actor_type="browser",
        actor_id=user,
        site_id=site_id,
        subject_type="cloud_command",
        subject_id=command.command_id,
        metadata={
            "command_type": command.command_type,
            "source_tent_id": command.source_tent_id,
            "device_id": command.device_id,
            "capability_id": command.capability_id,
        },
    )
    await session.commit()
    await session.refresh(command)
    return command_response(command)


async def get_command(
    session: AsyncSession, *, command_id: str, user: str
) -> CommandResponse:
    command = (
        await session.execute(
            select(CloudCommand).where(CloudCommand.command_id == command_id)
        )
    ).scalar_one_or_none()
    if command is None or command.requested_by != user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "command not found")
    return command_response(command)


async def list_commands(
    session: AsyncSession, *, user: str, status_filter: str | None
) -> list[CommandResponse]:
    stmt = select(CloudCommand).where(CloudCommand.requested_by == user)
    if status_filter is not None:
        stmt = stmt.where(CloudCommand.status == status_filter)
    rows = (
        await session.execute(stmt.order_by(desc(CloudCommand.queued_at)).limit(50))
    ).scalars()
    return [command_response(command) for command in rows]


async def enqueue_breeding_command(  # noqa: PLR0913
    idempotency_key: str,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
    command_type: CommandType,
    target_tent_id: str,
    source_tent_id: int | None,
    payload: BreedingCommandPayload,
) -> CommandResponse:
    if not settings.command_creation_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "commands disabled")
    existing = (
        await session.execute(
            select(CloudCommand).where(
                CloudCommand.requested_by == user,
                CloudCommand.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return command_response(existing)

    command = CloudCommand(
        command_id=str(uuid.uuid4()),
        idempotency_key=idempotency_key,
        site_id=settings.default_site_id,
        tent_id=target_tent_id,
        source_tent_id=source_tent_id,
        device_id=None,
        capability_id=None,
        command_type=command_type,
        payload=payload.model_dump(mode="json"),
        requested_by=user,
        status="queued",
        queued_at=now,
        expires_at=now + timedelta(seconds=BREEDING_COMMAND_EXPIRY_SECONDS),
        created_at=now,
        updated_at=now,
    )
    session.add(command)
    add_audit_event(
        session,
        now=now,
        event_type="command_created",
        actor_type="browser",
        actor_id=user,
        site_id=settings.default_site_id,
        subject_type="cloud_command",
        subject_id=command.command_id,
        metadata={
            "command_type": command.command_type,
            "tent_id": command.tent_id,
            "device_id": command.device_id,
            "capability_id": command.capability_id,
        },
    )
    await session.commit()
    await session.refresh(command)
    return command_response(command)


def command_response(command: CloudCommand) -> CommandResponse:
    return CommandResponse(
        command_id=command.command_id,
        idempotency_key=command.idempotency_key,
        site_id=command.site_id,
        source_tent_id=command.source_tent_id,
        legacy_target_tent_id=command.tent_id,
        device_id=command.device_id,
        capability_id=command.capability_id,
        target=_command_target(command),
        command_type=command.command_type,
        payload=command.payload,
        status=command.status,
        queued_at=command.queued_at,
        expires_at=command.expires_at,
        claimed_by=command.claimed_by,
        claimed_at=command.claimed_at,
        started_at=command.started_at,
        finished_at=command.finished_at,
        result=command.result,
        error=command.error,
    )


def storage_compat_tent_id(source_tent_id: int) -> str:
    return str(source_tent_id)


def _command_target(command: CloudCommand) -> PtzCommandTarget | None:
    if command.command_type not in PTZ_COMMAND_TYPE_VALUES:
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
