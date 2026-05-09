"""Read models for scoped light schedules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models import (
    Capability,
    Device,
    Schedule,
    Site,
    Tent,
    Zone,
)
from dirt_shared.services.grow_state import derive_lights_from_times
from dirt_shared.services.scope import DEFAULT_SITE_ID


@dataclass(frozen=True)
class LightScheduleView:
    site_id: str
    tent_id: str
    zone_id: str | None
    device_id: str | None
    capability_id: str | None
    schedule_id: str
    kind: str
    enabled: bool
    timezone: str
    starts_local: time
    ends_local: time
    duration_hours: float
    is_on: bool
    minutes_until_off: float
    minutes_until_on: float


class LightScheduleService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def list_light_schedules(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str | None = None,
    ) -> list[LightScheduleView]:
        async with AsyncSession(self._engine) as session:
            statement = (
                select(
                    Schedule,
                    Site.site_id,
                    Tent.tent_id,
                    Zone.zone_id,
                    Device.device_id,
                    Capability.capability_id,
                )
                .join(Site, Site.id == Schedule.site_id)
                .join(Tent, Tent.id == Schedule.tent_id)
                .outerjoin(Device, Device.id == Schedule.device_id)
                .outerjoin(Zone, Zone.id == Device.zone_id)
                .outerjoin(Capability, Capability.id == Schedule.capability_id)
                .where(Site.site_id == site_id)
                .where(Schedule.kind == "lights")
                .where(col(Schedule.starts_local).is_not(None))
                .where(col(Schedule.ends_local).is_not(None))
                .order_by(Tent.tent_id, Schedule.schedule_id)
            )
            if tent_id is not None:
                statement = statement.where(Tent.tent_id == tent_id)
            rows = (await session.exec(statement)).all()

        schedules: list[LightScheduleView] = []
        for (
            schedule,
            public_site_id,
            public_tent_id,
            zone_id,
            device_id,
            cap_id,
        ) in rows:
            if schedule.starts_local is None or schedule.ends_local is None:
                continue
            lights = derive_lights_from_times(
                schedule.starts_local,
                schedule.ends_local,
                self._clock().astimezone(ZoneInfo(schedule.timezone)),
            )
            schedules.append(
                LightScheduleView(
                    site_id=public_site_id,
                    tent_id=public_tent_id,
                    zone_id=zone_id,
                    device_id=device_id,
                    capability_id=cap_id,
                    schedule_id=schedule.schedule_id,
                    kind=schedule.kind,
                    enabled=schedule.enabled,
                    timezone=schedule.timezone,
                    starts_local=schedule.starts_local,
                    ends_local=schedule.ends_local,
                    duration_hours=_duration_hours(
                        schedule.starts_local, schedule.ends_local
                    ),
                    is_on=lights.on,
                    minutes_until_off=lights.minutes_until_off,
                    minutes_until_on=lights.minutes_until_on,
                )
            )
        return schedules


def _duration_hours(starts_local: time, ends_local: time) -> float:
    start_seconds = _seconds_since_midnight(starts_local)
    end_seconds = _seconds_since_midnight(ends_local)
    return ((end_seconds - start_seconds) % (24 * 60 * 60)) / (60 * 60)


def _seconds_since_midnight(value: time) -> float:
    return (
        value.hour * 60 * 60
        + value.minute * 60
        + value.second
        + value.microsecond / 1_000_000
    )
