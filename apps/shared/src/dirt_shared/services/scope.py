"""Default local site/tent scope resolution."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent

DEFAULT_SITE_PK = 1
DEFAULT_TENT_PK = 1


class ScopeResolutionError(ValueError):
    """Raised when the configured local site/tent scope is missing or ambiguous."""


@dataclass(frozen=True)
class Scope:
    site_pk: int
    tent_pk: int


async def require_default_site(session: AsyncSession) -> Site:
    """Return the single default local site or fail with a clear configuration error."""
    rows = (
        await session.exec(select(Site).where(Site.is_default.is_(True)).limit(2))
    ).all()
    if not rows:
        raise ScopeResolutionError("default site is not configured")
    if len(rows) > 1:
        raise ScopeResolutionError("multiple default sites are configured")
    return rows[0]


async def require_default_site_pk(session: AsyncSession) -> int:
    site = await require_default_site(session)
    if site.id is None:
        raise ScopeResolutionError("default site has no database id")
    return site.id


async def require_default_tent(
    session: AsyncSession,
    *,
    site_pk: int | None = None,
) -> Tent:
    """Return the single default tent for the default site or fail clearly."""
    if site_pk is None:
        site_pk = await require_default_site_pk(session)
    rows = (
        await session.exec(
            select(Tent)
            .where(Tent.site_id == site_pk)
            .where(Tent.is_default.is_(True))
            .where(Tent.active.is_(True))
            .limit(2)
        )
    ).all()
    if not rows:
        raise ScopeResolutionError("default tent is not configured")
    if len(rows) > 1:
        raise ScopeResolutionError("multiple default tents are configured")
    return rows[0]


async def require_default_tent_pk(
    session: AsyncSession,
    *,
    site_pk: int | None = None,
) -> int:
    tent = await require_default_tent(session, site_pk=site_pk)
    if tent.id is None:
        raise ScopeResolutionError("default tent has no database id")
    return tent.id


async def resolve_scope(
    session: AsyncSession,
    *,
    site_pk: int | None = None,
    tent_pk: int | None = None,
) -> Scope | None:
    """Resolve the default or explicit site/tent primary keys."""
    if site_pk is None:
        site_pk = await require_default_site_pk(session)
    if tent_pk is None:
        tent_pk = await require_default_tent_pk(session, site_pk=site_pk)
    row = (
        await session.exec(
            select(Tent.id)
            .where(Tent.site_id == site_pk)
            .where(Tent.id == tent_pk)
            .where(Tent.active.is_(True))
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return Scope(
        site_pk=site_pk,
        tent_pk=tent_pk,
    )
