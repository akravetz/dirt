from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.sites import SiteResponse
from dirt_control.api.browser_schemas.tents import (
    DeviceResponse,
    LightScheduleResponse,
    LightSchedulesResponse,
    TentResponse,
    TentStateResponse,
)
from dirt_control.models import (
    CloudDevice,
    CloudPlantLocation,
    CloudSchedule,
    CloudSite,
    CloudTent,
)


@dataclass(frozen=True)
class LightState:
    is_on: bool
    minutes_until_off: float
    minutes_until_on: float


async def list_sites(session: AsyncSession) -> list[SiteResponse]:
    rows = (
        await session.execute(select(CloudSite).order_by(CloudSite.site_id))
    ).scalars()
    return [
        SiteResponse(
            site_id=row.site_id,
            name=row.name,
            timezone=row.timezone,
            is_active=row.is_active,
            gateway_last_seen_at=row.gateway_last_seen_at,
            last_catalog_sync_at=row.last_catalog_sync_at,
        )
        for row in rows
    ]


async def list_tents(session: AsyncSession, *, site_id: str) -> list[TentResponse]:
    rows = (
        await session.execute(
            select(CloudTent)
            .where(CloudTent.site_id == site_id)
            .where(CloudTent.source_tent_id.is_not(None))
            .order_by(CloudTent.source_tent_id, CloudTent.name)
        )
    ).scalars()
    return [
        TentResponse(
            site_id=row.site_id,
            source_tent_id=required_source_tent_id(row),
            name=row.name,
            role=row.role,
            is_active=row.is_active,
            synced_at=row.synced_at,
        )
        for row in rows
    ]


async def get_tent_state(
    session: AsyncSession, *, site_id: str, source_tent_id: int
) -> TentStateResponse:
    site = (
        await session.execute(select(CloudSite).where(CloudSite.site_id == site_id))
    ).scalar_one_or_none()
    tent = await get_cloud_tent_by_source_id(
        session, site_id=site_id, source_tent_id=source_tent_id
    )
    return TentStateResponse(
        site_id=tent.site_id,
        source_tent_id=required_source_tent_id(tent),
        name=tent.name,
        role=tent.role,
        is_active=tent.is_active,
        gateway_last_seen_at=site.gateway_last_seen_at if site else None,
        last_catalog_sync_at=site.last_catalog_sync_at if site else None,
    )


async def list_devices(
    session: AsyncSession, *, site_id: str, source_tent_id: int
) -> list[DeviceResponse]:
    rows = (
        await session.execute(
            select(CloudDevice)
            .where(
                CloudDevice.site_id == site_id,
                CloudDevice.source_tent_id == source_tent_id,
            )
            .order_by(CloudDevice.device_id)
        )
    ).scalars()
    return [
        DeviceResponse(
            device_id=row.device_id,
            name=row.name,
            kind=row.kind,
            controller=row.controller,
            is_active=row.is_active,
            last_seen_at=row.last_seen_at,
        )
        for row in rows
    ]


async def list_light_schedules(
    session: AsyncSession, *, site_id: str, source_tent_id: int, now: datetime
) -> LightSchedulesResponse:
    tent = await get_cloud_tent_by_source_id(
        session, site_id=site_id, source_tent_id=source_tent_id
    )
    rows = (
        await session.execute(
            select(CloudSchedule)
            .where(
                CloudSchedule.site_id == site_id,
                CloudSchedule.source_tent_id == source_tent_id,
                CloudSchedule.kind == "lights",
                CloudSchedule.source_schedule_id.is_not(None),
            )
            .order_by(CloudSchedule.source_schedule_id)
        )
    ).scalars()
    schedules = []
    for row in rows:
        state = light_state(
            row.starts_local, row.ends_local, now, timezone=row.timezone
        )
        schedules.append(
            LightScheduleResponse(
                site_id=row.site_id,
                source_tent_id=required_schedule_source_tent_id(row),
                tent_name=tent.name,
                source_zone_id=row.source_zone_id,
                device_id=row.device_id,
                capability_id=row.capability_id,
                source_schedule_id=required_source_schedule_id(row),
                kind=row.kind,
                enabled=row.is_enabled,
                timezone=row.timezone,
                starts_local=row.starts_local.strftime("%H:%M:%S"),
                ends_local=row.ends_local.strftime("%H:%M:%S"),
                duration_hours=duration_hours(row.starts_local, row.ends_local),
                is_on=state.is_on,
                minutes_until_off=state.minutes_until_off,
                minutes_until_on=state.minutes_until_on,
            )
        )
    return LightSchedulesResponse(
        site_id=site_id,
        source_tent_id=source_tent_id,
        tent_name=tent.name,
        schedules=schedules,
    )


async def get_cloud_tent_by_source_id(
    session: AsyncSession, *, site_id: str, source_tent_id: int
) -> CloudTent:
    tent = (
        await session.execute(
            select(CloudTent).where(
                CloudTent.site_id == site_id,
                CloudTent.source_tent_id == source_tent_id,
            )
        )
    ).scalar_one_or_none()
    if tent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tent not found")
    return tent


async def cloud_tents_by_source_id(
    session: AsyncSession, *, site_id: str, source_tent_ids: set[int]
) -> dict[int, CloudTent]:
    if not source_tent_ids:
        return {}
    rows = (
        await session.execute(
            select(CloudTent).where(
                CloudTent.site_id == site_id,
                CloudTent.source_tent_id.in_(source_tent_ids),
            )
        )
    ).scalars()
    return {required_source_tent_id(row): row for row in rows}


def required_source_tent_id(tent: CloudTent) -> int:
    if tent.source_tent_id is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "cloud tent missing source_tent_id",
        )
    return tent.source_tent_id


def required_location_source_tent_id(location: CloudPlantLocation) -> int:
    if location.source_tent_id is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "cloud plant location missing source_tent_id",
        )
    return location.source_tent_id


def location_tent_name(tent: CloudTent | None, location: CloudPlantLocation) -> str:
    if tent is not None:
        return tent.name
    return f"Tent {required_location_source_tent_id(location)}"


def required_schedule_source_tent_id(schedule: CloudSchedule) -> int:
    if schedule.source_tent_id is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "cloud schedule missing source_tent_id",
        )
    return schedule.source_tent_id


def required_source_schedule_id(schedule: CloudSchedule) -> int:
    if schedule.source_schedule_id is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "cloud schedule missing source_schedule_id",
        )
    return schedule.source_schedule_id


def light_state(
    starts_local: time,
    ends_local: time,
    now: datetime,
    *,
    timezone: str,
) -> LightState:
    now_local = now.astimezone(ZoneInfo(timezone))
    now_t = now_local.time()
    if starts_local < ends_local:
        is_on = starts_local <= now_t < ends_local
    else:
        is_on = now_t >= starts_local or now_t < ends_local

    off_dt = datetime.combine(now_local.date(), ends_local, tzinfo=now_local.tzinfo)
    if off_dt <= now_local:
        off_dt = datetime.combine(
            now_local.date() + timedelta(days=1),
            ends_local,
            tzinfo=now_local.tzinfo,
        )
    on_dt = datetime.combine(now_local.date(), starts_local, tzinfo=now_local.tzinfo)
    if on_dt <= now_local:
        on_dt = datetime.combine(
            now_local.date() + timedelta(days=1),
            starts_local,
            tzinfo=now_local.tzinfo,
        )
    return LightState(
        is_on=is_on,
        minutes_until_off=(off_dt - now_local).total_seconds() / 60.0,
        minutes_until_on=(on_dt - now_local).total_seconds() / 60.0,
    )


def duration_hours(starts_local: time, ends_local: time) -> float:
    start_seconds = seconds_since_midnight(starts_local)
    end_seconds = seconds_since_midnight(ends_local)
    return ((end_seconds - start_seconds) % (24 * 60 * 60)) / (60 * 60)


def seconds_since_midnight(value: time) -> float:
    return (
        value.hour * 60 * 60
        + value.minute * 60
        + value.second
        + value.microsecond / 1_000_000
    )
