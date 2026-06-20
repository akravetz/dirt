from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends

from dirt_control.api.browser_schemas.assets import AssetResponse
from dirt_control.deps import get_asset_store, get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.browser_assets import (
    asset_signed_url as asset_signed_url_service,
)
from dirt_control.services.browser_assets import (
    latest_assets as latest_assets_service,
)
from dirt_control.settings import CloudSettings
from dirt_control.storage import AssetStore

router = APIRouter()


@router.get("/tents/{source_tent_id}/assets/latest", response_model=list[AssetResponse])
async def latest_assets(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    asset_store: AssetStore = Depends(get_asset_store),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> list[AssetResponse]:
    return await latest_assets_service(
        session,
        settings=settings,
        asset_store=asset_store,
        source_tent_id=source_tent_id,
        now=clock(),
    )


@router.get("/assets/{asset_id}/signed-url", response_model=AssetResponse)
async def asset_signed_url(
    asset_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    asset_store: AssetStore = Depends(get_asset_store),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> AssetResponse:
    return await asset_signed_url_service(
        session,
        settings=settings,
        asset_store=asset_store,
        asset_id=asset_id,
        now=clock(),
    )
