"""Dispatch due irrigation pulses through DB-configured Shelly plugs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.services.shelly import (
    ShellyPlugClient,
    ShellyPlugTarget,
    shelly_target_from_db_rows,
)
from dirt_shared.models import (
    Capability,
    IrrigationRun,
    IrrigationScheduleItem,
    Schedule,
)
from dirt_shared.models import Device as DbDevice


class ShellyPulseClient(Protocol):
    async def timed_pulse(
        self,
        target: ShellyPlugTarget,
        *,
        duration_s: int,
    ) -> str: ...


@dataclass(frozen=True)
class IrrigationDispatchResult:
    source_schedule_id: int
    schedule_item_pk: int
    intended_start_at: datetime
    status: str
    device_id: str
    error: str | None = None


@dataclass(frozen=True)
class _DuePulse:
    schedule_pk: int
    source_schedule_id: int
    schedule_item_pk: int
    target: ShellyPlugTarget
    intended_start_at: datetime
    duration_s: int


class ShellyIrrigationScheduleService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        client: ShellyPulseClient | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        due_window_s: int = 60,
    ) -> None:
        if due_window_s <= 0:
            raise ValueError("due_window_s must be positive")
        self._engine = engine
        self._client = client or ShellyPlugClient()
        self._clock = clock
        self._due_window = timedelta(seconds=due_window_s)

    async def run_once(self) -> list[IrrigationDispatchResult]:
        now = _aware_utc(self._clock())
        due_pulses = await self._load_due_pulses(now)
        results: list[IrrigationDispatchResult] = []
        for pulse in due_pulses:
            result = await self._dispatch_pulse(pulse, now)
            if result is not None:
                results.append(result)
        return results

    async def _load_due_pulses(self, now: datetime) -> list[_DuePulse]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(
                        Schedule,
                        IrrigationScheduleItem,
                        DbDevice,
                        Capability,
                    )
                    .join(
                        IrrigationScheduleItem,
                        IrrigationScheduleItem.schedule_id == Schedule.id,
                    )
                    .join(DbDevice, DbDevice.id == Schedule.device_id)
                    .join(Capability, Capability.id == Schedule.capability_id)
                    .where(Schedule.kind == "irrigation")
                    .where(Schedule.enabled.is_(True))
                    .where(IrrigationScheduleItem.enabled.is_(True))
                    .where(DbDevice.enabled.is_(True))
                    .where(DbDevice.controller == "shelly")
                    .where(DbDevice.provider_uid_kind == "mac")
                    .where(col(DbDevice.provider_uid).is_not(None))
                    .where(Capability.enabled.is_(True))
                    .where(Capability.device_id == DbDevice.id)
                    .order_by(Schedule.tent_id, Schedule.id)
                )
            ).all()

        due: list[_DuePulse] = []
        for schedule, item, device, capability in rows:
            if schedule.id is None or item.id is None:
                continue
            intended_start_at = _intended_start_at(
                now,
                timezone=schedule.timezone,
                starts_local=item.starts_local,
            )
            if not _is_due(now, intended_start_at, self._due_window):
                continue
            due.append(
                _DuePulse(
                    schedule_pk=schedule.id,
                    source_schedule_id=schedule.id,
                    schedule_item_pk=item.id,
                    target=shelly_target_from_db_rows(device, capability),
                    intended_start_at=intended_start_at,
                    duration_s=item.duration_s,
                )
            )
        return due

    async def _dispatch_pulse(
        self,
        pulse: _DuePulse,
        now: datetime,
    ) -> IrrigationDispatchResult | None:
        run = await self._create_run_if_absent(pulse, now)
        if run is None:
            return None

        started_at = now
        try:
            await self._client.timed_pulse(
                pulse.target,
                duration_s=pulse.duration_s,
            )
        except Exception as exc:
            await self._finish_run(
                run.id,
                status="failed",
                timestamp=_aware_utc(self._clock()),
                started_at=started_at,
                error=repr(exc),
            )
            return IrrigationDispatchResult(
                source_schedule_id=pulse.source_schedule_id,
                schedule_item_pk=pulse.schedule_item_pk,
                intended_start_at=pulse.intended_start_at,
                status="failed",
                device_id=pulse.target.device_id,
                error=repr(exc),
            )

        await self._finish_run(
            run.id,
            status="dispatched",
            timestamp=_aware_utc(self._clock()),
            started_at=started_at,
            error=None,
        )
        return IrrigationDispatchResult(
            source_schedule_id=pulse.source_schedule_id,
            schedule_item_pk=pulse.schedule_item_pk,
            intended_start_at=pulse.intended_start_at,
            status="dispatched",
            device_id=pulse.target.device_id,
        )

    async def _create_run_if_absent(
        self,
        pulse: _DuePulse,
        now: datetime,
    ) -> IrrigationRun | None:
        async with AsyncSession(self._engine) as session:
            existing = (
                await session.exec(
                    select(IrrigationRun)
                    .where(IrrigationRun.schedule_item_id == pulse.schedule_item_pk)
                    .where(IrrigationRun.intended_start_at == pulse.intended_start_at)
                )
            ).one_or_none()
            if existing is not None:
                return None

            run = IrrigationRun(
                schedule_id=pulse.schedule_pk,
                schedule_item_id=pulse.schedule_item_pk,
                device_id=pulse.target.device_pk,
                capability_id=pulse.target.capability_pk,
                intended_start_at=pulse.intended_start_at,
                duration_s=pulse.duration_s,
                status="pending",
                created_at=now,
                updated_at=now,
            )
            session.add(run)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return None
            await session.refresh(run)
            return run

    async def _finish_run(
        self,
        run_pk: int | None,
        *,
        status: str,
        timestamp: datetime,
        started_at: datetime,
        error: str | None,
    ) -> None:
        if run_pk is None:
            return
        async with AsyncSession(self._engine) as session:
            run = await session.get(IrrigationRun, run_pk)
            if run is None:
                return
            run.started_at = started_at
            run.finished_at = timestamp
            run.status = status
            run.error = error
            run.updated_at = timestamp
            session.add(run)
            await session.commit()


def _intended_start_at(
    now: datetime,
    *,
    timezone: str,
    starts_local: time,
) -> datetime:
    zone = ZoneInfo(timezone)
    local_now = now.astimezone(zone)
    intended_local = datetime.combine(local_now.date(), starts_local, tzinfo=zone)
    return intended_local.astimezone(UTC)


def _is_due(now: datetime, intended_start_at: datetime, window: timedelta) -> bool:
    return intended_start_at <= now < intended_start_at + window


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
