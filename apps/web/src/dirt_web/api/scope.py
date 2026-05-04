"""Scoped site/tent read APIs for the local controller model."""

from __future__ import annotations

from dirt_contracts.webapp_v1.models import (
    GrowCurrent,
    ScopedDevice,
    Site,
    SitesResponse,
    Tent,
    TentDevicesResponse,
    TentsResponse,
)
from fastapi import APIRouter, Depends, HTTPException, Query

from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.scope import DEFAULT_SITE_ID
from dirt_shared.services.scope_catalog import ScopeCatalogService
from dirt_web.api.grow import _grow_current_response
from dirt_web.deps import get_grow, get_scope_catalog

router = APIRouter(tags=["scope"])


@router.get("/api/sites", response_model=SitesResponse)
async def sites_list(
    catalog: ScopeCatalogService = Depends(get_scope_catalog),
) -> SitesResponse:
    """Return physical controller sites known to this local box."""
    sites = await catalog.list_sites()
    return SitesResponse(
        sites=[
            Site(
                site_id=site.site_id,
                name=site.name,
                location=site.location,
                timezone=site.timezone,
                is_default=site.is_default,
            )
            for site in sites
        ]
    )


@router.get("/api/tents", response_model=TentsResponse)
async def tents_list(
    site_id: str = Query(default=DEFAULT_SITE_ID),
    catalog: ScopeCatalogService = Depends(get_scope_catalog),
) -> TentsResponse:
    """Return tents for a site, defaulting to the local homebox site."""
    tents = await catalog.list_tents(site_id=site_id)
    return TentsResponse(
        tents=[
            Tent(
                site_id=tent.site_id,
                tent_id=tent.tent_id,
                name=tent.name,
                role=tent.role,
                is_default=tent.is_default,
                active=tent.active,
            )
            for tent in tents
        ]
    )


@router.get("/api/tents/{tent_id}/grow/current", response_model=GrowCurrent)
async def tent_grow_current(
    tent_id: str,
    site_id: str = Query(default=DEFAULT_SITE_ID),
    grow: GrowStateService = Depends(get_grow),
) -> GrowCurrent:
    """Return the current grow for one tent, or 404 if that tent has none."""
    current = await grow.current_grow_run(site_id=site_id, tent_id=tent_id)
    if current is None:
        raise HTTPException(status_code=404, detail="current grow not found")
    payload = await grow.get_grow_current_payload(site_id=site_id, tent_id=tent_id)
    return _grow_current_response(payload)


@router.get("/api/tents/{tent_id}/devices", response_model=TentDevicesResponse)
async def tent_devices(
    tent_id: str,
    site_id: str = Query(default=DEFAULT_SITE_ID),
    catalog: ScopeCatalogService = Depends(get_scope_catalog),
) -> TentDevicesResponse:
    """Return canonical devices assigned to one tent."""
    devices = await catalog.list_tent_devices(site_id=site_id, tent_id=tent_id)
    if devices is None:
        raise HTTPException(status_code=404, detail="tent not found")
    return TentDevicesResponse(
        site_id=site_id,
        tent_id=tent_id,
        devices=[
            ScopedDevice(
                site_id=device.site_id,
                tent_id=device.tent_id,
                zone_id=device.zone_id,
                device_id=device.device_id,
                name=device.name,
                kind=device.kind,
                controller=device.controller,
                enabled=device.enabled,
            )
            for device in devices
        ],
    )
