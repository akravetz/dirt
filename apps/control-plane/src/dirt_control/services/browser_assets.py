from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.assets import AssetResponse
from dirt_control.models import CloudAsset
from dirt_control.security import expires_from
from dirt_control.services.browser_tents import get_cloud_tent_by_source_id
from dirt_control.settings import CloudSettings
from dirt_control.storage import AssetStore


async def latest_assets(
    session: AsyncSession,
    *,
    settings: CloudSettings,
    asset_store: AssetStore,
    source_tent_id: int,
    now: datetime,
) -> list[AssetResponse]:
    await get_cloud_tent_by_source_id(
        session, site_id=settings.default_site_id, source_tent_id=source_tent_id
    )
    rows = (
        await session.execute(
            select(CloudAsset)
            .where(
                CloudAsset.site_id == settings.default_site_id,
                CloudAsset.source_tent_id == source_tent_id,
            )
            .order_by(desc(CloudAsset.captured_at))
            .limit(10)
        )
    ).scalars()
    return [
        asset_response(
            row,
            settings=settings,
            asset_store=asset_store,
            now=now,
        )
        for row in rows
    ]


async def asset_signed_url(
    session: AsyncSession,
    *,
    settings: CloudSettings,
    asset_store: AssetStore,
    asset_id: str,
    now: datetime,
) -> AssetResponse:
    asset = (
        await session.execute(select(CloudAsset).where(CloudAsset.asset_id == asset_id))
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    return asset_response(
        asset,
        settings=settings,
        asset_store=asset_store,
        now=now,
    )


def asset_response(
    asset: CloudAsset,
    *,
    settings: CloudSettings,
    asset_store: AssetStore,
    now: datetime,
) -> AssetResponse:
    expires_at = expires_from(now, settings.asset_url_ttl_s)
    signed_url = asset_store.presign_get(
        object_key=asset.object_key,
        expires_in_s=settings.asset_url_ttl_s,
    )
    return AssetResponse(
        asset_id=asset.asset_id,
        kind=asset.kind,
        content_type=asset.content_type,
        byte_size=asset.byte_size,
        sha256=asset.sha256,
        captured_at=asset.captured_at,
        uploaded_at=asset.uploaded_at,
        signed_url=signed_url,
        signed_url_expires_at=expires_at,
    )
