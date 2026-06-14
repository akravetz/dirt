"""Default local site/tent scope resolution."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent

DEFAULT_SITE_ID = "homebox"
DEFAULT_TENT_ID = "main"


@dataclass(frozen=True)
class Scope:
    site_pk: int
    tent_pk: int
    site_id: str
    tent_id: str


async def resolve_scope(
    session: AsyncSession,
    *,
    site_id: str = DEFAULT_SITE_ID,
    tent_id: str = DEFAULT_TENT_ID,
) -> Scope | None:
    """Resolve public site/tent ids to database primary keys."""
    result = await session.exec(
        select(Site.id, Site.site_id, Tent.id, Tent.tent_id)
        .join(Tent, Tent.site_id == Site.id)
        .where(Site.site_id == site_id)
        .where(Tent.tent_id == tent_id)
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    site_pk, resolved_site_id, tent_pk, resolved_tent_id = row
    return Scope(
        site_pk=site_pk,
        tent_pk=tent_pk,
        site_id=resolved_site_id,
        tent_id=resolved_tent_id,
    )
