from __future__ import annotations

from fastapi import APIRouter, Depends

from dirt_control.api.browser_schemas.sites import SiteResponse
from dirt_control.deps import get_session
from dirt_control.security import require_browser_user
from dirt_control.services.browser_tents import list_sites

router = APIRouter()


@router.get("/sites", response_model=list[SiteResponse])
async def sites(
    _: str = Depends(require_browser_user),
    session=Depends(get_session),
) -> list[SiteResponse]:
    return await list_sites(session)
