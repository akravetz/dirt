"""Read-only catalog of local controller sites, tents, and devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Device
from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone
from dirt_shared.services.scope import require_default_site_pk


@dataclass(frozen=True)
class SiteSummary:
    site_pk: int
    name: str
    location: str | None
    timezone: str
    is_default: bool


@dataclass(frozen=True)
class TentSummary:
    tent_pk: int
    site_pk: int
    name: str
    role: str
    is_default: bool
    active: bool


@dataclass(frozen=True)
class ScopedDeviceSummary:
    site_pk: int
    tent_pk: int | None
    zone_pk: int | None
    device_id: str
    name: str
    kind: str
    controller: str
    enabled: bool
    last_seen: datetime | None


class ScopeCatalogService:
    """List scoped identity rows exposed by Phase 1 read-only APIs."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def list_sites(self) -> list[SiteSummary]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(Site).order_by(Site.is_default.desc(), Site.id)
                )
            ).all()
        return [
            SiteSummary(
                site_pk=row.id,
                name=row.name,
                location=row.location,
                timezone=row.timezone,
                is_default=row.is_default,
            )
            for row in rows
        ]

    async def list_tents(
        self,
        *,
        site_pk: int | None = None,
    ) -> list[TentSummary]:
        async with AsyncSession(self._engine) as session:
            if site_pk is None:
                site_pk = await require_default_site_pk(session)
            rows = (
                await session.exec(
                    select(Tent)
                    .join(Site, Site.id == Tent.site_id)
                    .where(Tent.site_id == site_pk)
                    .order_by(Tent.is_default.desc(), Tent.name)
                )
            ).all()
        return [
            TentSummary(
                tent_pk=tent.id,
                site_pk=tent.site_id,
                name=tent.name,
                role=tent.role,
                is_default=tent.is_default,
                active=tent.active,
            )
            for tent in rows
        ]

    async def list_tent_devices(
        self,
        *,
        tent_pk: int,
        site_pk: int | None = None,
    ) -> list[ScopedDeviceSummary] | None:
        async with AsyncSession(self._engine) as session:
            if site_pk is None:
                site_pk = await require_default_site_pk(session)
            rows = (
                await session.exec(
                    select(Device, Tent.id, Zone.id)
                    .join(Site, Site.id == Device.site_id)
                    .outerjoin(Tent, Tent.id == Device.tent_id)
                    .outerjoin(Zone, Zone.id == Device.zone_id)
                    .where(Device.site_id == site_pk)
                    .where(Device.tent_id == tent_pk)
                    .order_by(Device.device_id)
                )
            ).all()
        return [
            ScopedDeviceSummary(
                site_pk=device.site_id,
                tent_pk=resolved_tent_pk,
                zone_pk=zone_pk,
                device_id=device.device_id,
                name=device.name,
                kind=device.kind,
                controller=device.controller,
                enabled=device.enabled,
                last_seen=device.last_seen,
            )
            for device, resolved_tent_pk, zone_pk in rows
        ]
