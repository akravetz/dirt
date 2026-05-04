"""Read-only catalog of local controller sites, tents, and devices."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Device
from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone
from dirt_shared.services.scope import DEFAULT_SITE_ID, resolve_scope


@dataclass(frozen=True)
class SiteSummary:
    site_id: str
    name: str
    location: str | None
    timezone: str
    is_default: bool


@dataclass(frozen=True)
class TentSummary:
    site_id: str
    tent_id: str
    name: str
    role: str
    is_default: bool
    active: bool


@dataclass(frozen=True)
class ScopedDeviceSummary:
    site_id: str
    tent_id: str | None
    zone_id: str | None
    device_id: str
    name: str
    kind: str
    controller: str
    enabled: bool


class ScopeCatalogService:
    """List scoped identity rows exposed by Phase 1 read-only APIs."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def list_sites(self) -> list[SiteSummary]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(Site).order_by(Site.is_default.desc(), Site.site_id)
                )
            ).all()
        return [
            SiteSummary(
                site_id=row.site_id,
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
        site_id: str = DEFAULT_SITE_ID,
    ) -> list[TentSummary]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(Tent, Site.site_id)
                    .join(Site, Site.id == Tent.site_id)
                    .where(Site.site_id == site_id)
                    .order_by(Tent.is_default.desc(), Tent.tent_id)
                )
            ).all()
        return [
            TentSummary(
                site_id=resolved_site_id,
                tent_id=tent.tent_id,
                name=tent.name,
                role=tent.role,
                is_default=tent.is_default,
                active=tent.active,
            )
            for tent, resolved_site_id in rows
        ]

    async def list_tent_devices(
        self,
        *,
        tent_id: str,
        site_id: str = DEFAULT_SITE_ID,
    ) -> list[ScopedDeviceSummary] | None:
        async with AsyncSession(self._engine) as session:
            scope = await resolve_scope(session, site_id=site_id, tent_id=tent_id)
            if scope is None:
                return None
            rows = (
                await session.exec(
                    select(Device, Site.site_id, Tent.tent_id, Zone.zone_id)
                    .join(Site, Site.id == Device.site_id)
                    .outerjoin(Tent, Tent.id == Device.tent_id)
                    .outerjoin(Zone, Zone.id == Device.zone_id)
                    .where(Site.id == scope.site_pk)
                    .where(Device.tent_id == scope.tent_pk)
                    .order_by(Device.device_id)
                )
            ).all()
        return [
            ScopedDeviceSummary(
                site_id=resolved_site_id,
                tent_id=resolved_tent_id,
                zone_id=zone_id,
                device_id=device.device_id,
                name=device.name,
                kind=device.kind,
                controller=device.controller,
                enabled=device.enabled,
            )
            for device, resolved_site_id, resolved_tent_id, zone_id in rows
        ]
