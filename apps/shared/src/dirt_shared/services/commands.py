"""Local command-intent lifecycle for hardware actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.command import Command
from dirt_shared.models.device import Capability, Device
from dirt_shared.models.zone import Zone
from dirt_shared.services.scope import require_default_site_pk, require_default_tent_pk

LOCAL_COMMAND_SOURCES = frozenset({"local_api", "local_loop", "cloud_gateway", "test"})
TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


class CommandSourceError(ValueError):
    """Raised when a command source is not allowed to enqueue locally."""


class CommandTargetError(ValueError):
    """Raised when a command target cannot be resolved inside the local scope."""


class CommandService:
    """DB-backed, idempotent command-intent ledger.

    This service records local command intent and lifecycle only. It does not
    execute commands. Cloud-origin rows are allowed only for the local outbound
    gateway after it has claimed and locally validated a command intent.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def enqueue(  # noqa: PLR0913
        self,
        *,
        command_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        requested_by: str,
        source: str,
        site_pk: int | None = None,
        tent_pk: int | None = None,
        zone_pk: int | None = None,
        use_default_tent: bool = True,
        device_id: str | None = None,
        capability_id: str | None = None,
    ) -> Command:
        """Create or return the queued command for ``idempotency_key``."""
        _validate_local_source(source)
        async with AsyncSession(self._engine) as session:
            existing = (
                await session.exec(
                    select(Command).where(Command.idempotency_key == idempotency_key)
                )
            ).first()
            if existing is not None:
                return existing

            target = await _resolve_command_target(
                session,
                site_pk=site_pk,
                tent_pk=tent_pk,
                zone_pk=zone_pk,
                use_default_tent=use_default_tent,
                device_id=device_id,
                capability_id=capability_id,
            )
            command = Command(
                command_id=f"cmd-{uuid4().hex}",
                idempotency_key=idempotency_key,
                site_id=target.site_pk,
                tent_id=target.tent_pk,
                zone_id=target.zone_pk,
                device_id=target.device_pk,
                capability_id=target.capability_pk,
                command_type=command_type,
                payload=payload,
                requested_by=requested_by,
                source=source,
                status="queued",
                queued_at=self._clock(),
            )
            session.add(command)
            await session.commit()
            await session.refresh(command)
            return command

    async def enqueue_from_source_scope(  # noqa: PLR0913
        self,
        *,
        command_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        requested_by: str,
        source: str,
        source_site_id: int | None = None,
        source_tent_id: int | None,
        source_zone_id: int | None = None,
        device_id: str | None = None,
        capability_id: str | None = None,
    ) -> Command:
        """Boundary adapter for cloud command source integer scope fields."""
        if source_site_id is None:
            async with AsyncSession(self._engine) as session:
                source_site_id = await require_default_site_pk(session)
        return await self.enqueue(
            command_type=command_type,
            payload=payload,
            idempotency_key=idempotency_key,
            requested_by=requested_by,
            source=source,
            site_pk=source_site_id,
            tent_pk=source_tent_id,
            zone_pk=source_zone_id,
            use_default_tent=source_tent_id is not None,
            device_id=device_id,
            capability_id=capability_id,
        )

    async def start(self, command_id: str) -> Command:
        """Mark a queued command running; no-op for running/terminal rows."""
        return await self._transition(command_id, "running")

    async def succeed(self, command_id: str, result: dict[str, Any]) -> Command:
        """Mark a command succeeded; repeated calls return the terminal row."""
        return await self._transition(command_id, "succeeded", result=result)

    async def fail(self, command_id: str, error: dict[str, Any]) -> Command:
        """Mark a command failed; repeated calls return the terminal row."""
        return await self._transition(command_id, "failed", error=error)

    async def _transition(
        self,
        command_id: str,
        target_status: str,
        *,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> Command:
        now = self._clock()
        async with AsyncSession(self._engine) as session:
            command = (
                await session.exec(
                    select(Command).where(Command.command_id == command_id)
                )
            ).first()
            if command is None:
                raise CommandTargetError(f"unknown command_id: {command_id}")
            if command.status in TERMINAL_STATUSES:
                return command
            if target_status == "running":
                if command.status == "queued":
                    command.status = "running"
                    command.started_at = now
            elif target_status == "succeeded":
                if command.started_at is None:
                    command.started_at = now
                command.status = "succeeded"
                command.succeeded_at = now
                command.result = result or {}
            elif target_status == "failed":
                if command.started_at is None:
                    command.started_at = now
                command.status = "failed"
                command.failed_at = now
                command.error = error or {}
            else:
                raise ValueError(f"unsupported command status: {target_status}")
            session.add(command)
            await session.commit()
            await session.refresh(command)
            return command


def _validate_local_source(source: str) -> None:
    if source not in LOCAL_COMMAND_SOURCES:
        raise CommandSourceError(f"unsupported local command source: {source}")


@dataclass(frozen=True)
class _CommandTarget:
    site_pk: int
    tent_pk: int | None
    zone_pk: int | None
    device_pk: int | None
    capability_pk: int | None


async def _resolve_command_target(  # noqa: PLR0913
    session: AsyncSession,
    *,
    site_pk: int | None,
    tent_pk: int | None,
    zone_pk: int | None,
    use_default_tent: bool,
    device_id: str | None,
    capability_id: str | None,
) -> _CommandTarget:
    if site_pk is None:
        site_pk = await require_default_site_pk(session)
    if use_default_tent and tent_pk is None:
        tent_pk = await require_default_tent_pk(session, site_pk=site_pk)

    zone_pk = await _validate_zone_pk(session, site_pk, tent_pk, zone_pk)
    device_pk = await _resolve_device_pk(session, site_pk, tent_pk, device_id)
    capability_pk = await _resolve_capability_pk(
        session,
        device_pk=device_pk,
        capability_id=capability_id,
        site_pk=site_pk,
        tent_pk=tent_pk,
    )
    return _CommandTarget(site_pk, tent_pk, zone_pk, device_pk, capability_pk)


async def _validate_zone_pk(
    session: AsyncSession,
    site_pk: int,
    tent_pk: int | None,
    zone_pk: int | None,
) -> int | None:
    if zone_pk is None:
        return None
    stmt = select(Zone.id).where(Zone.site_id == site_pk).where(Zone.id == zone_pk)
    if tent_pk is None:
        stmt = stmt.where(Zone.tent_id.is_(None))
    else:
        stmt = stmt.where(Zone.tent_id == tent_pk)
    resolved_zone_pk = (await session.exec(stmt)).first()
    if resolved_zone_pk is None:
        raise CommandTargetError(f"unknown zone id: {zone_pk}")
    return resolved_zone_pk


async def _resolve_device_pk(
    session: AsyncSession,
    site_pk: int,
    tent_pk: int | None,
    device_id: str | None,
) -> int | None:
    if device_id is None:
        return None
    stmt = (
        select(Device.id)
        .where(Device.site_id == site_pk)
        .where(Device.device_id == device_id)
    )
    if tent_pk is None:
        stmt = stmt.where(Device.tent_id.is_(None))
    else:
        stmt = stmt.where((Device.tent_id == tent_pk) | Device.tent_id.is_(None))
    device_pk = (await session.exec(stmt)).first()
    if device_pk is None:
        raise CommandTargetError(f"unknown device_id: {device_id}")
    return device_pk


async def _resolve_capability_pk(
    session: AsyncSession,
    *,
    device_pk: int | None,
    capability_id: str | None,
    site_pk: int,
    tent_pk: int | None,
) -> int | None:
    if capability_id is None:
        return None
    stmt = (
        select(Capability.id)
        .join(Device, Device.id == Capability.device_id)
        .where(Capability.capability_id == capability_id)
        .where(Device.site_id == site_pk)
    )
    if device_pk is not None:
        stmt = stmt.where(Device.id == device_pk)
    if tent_pk is None:
        stmt = stmt.where(Device.tent_id.is_(None))
    else:
        stmt = stmt.where((Device.tent_id == tent_pk) | Device.tent_id.is_(None))
    capability_pk = (await session.exec(stmt.limit(2))).all()
    if not capability_pk:
        raise CommandTargetError(f"unknown capability_id: {capability_id}")
    if len(capability_pk) > 1:
        raise CommandTargetError(
            f"ambiguous capability_id without device_id: {capability_id}"
        )
    return capability_pk[0]
