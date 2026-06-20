from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends

from dirt_control.api.browser_schemas.admin import (
    GatewayCredentialRotateRequest,
    GatewayCredentialRotateResponse,
)
from dirt_control.deps import get_asset_store, get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.browser_admin import (
    prune_assets as prune_assets_service,
)
from dirt_control.services.browser_admin import (
    rotate_gateway_credential as rotate_gateway_credential_service,
)
from dirt_control.settings import CloudSettings
from dirt_control.storage import AssetStore
from dirt_shared.cloud_contract import PruneAssetsResponse

router = APIRouter()


@router.post(
    "/admin/gateway-credentials/{credential_id}/rotate",
    response_model=GatewayCredentialRotateResponse,
)
async def rotate_gateway_credential(
    credential_id: str,
    body: GatewayCredentialRotateRequest,
    user: str = Depends(require_browser_user),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> GatewayCredentialRotateResponse:
    return await rotate_gateway_credential_service(
        session,
        credential_id=credential_id,
        body=body,
        user=user,
        now=clock(),
    )


@router.post("/admin/assets/prune-expired", response_model=PruneAssetsResponse)
async def prune_assets(
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    asset_store: AssetStore = Depends(get_asset_store),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PruneAssetsResponse:
    return await prune_assets_service(
        session,
        settings=settings,
        asset_store=asset_store,
        user=user,
        now=clock(),
    )
