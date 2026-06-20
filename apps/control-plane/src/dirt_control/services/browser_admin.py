from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.admin import (
    GatewayCredentialRotateRequest,
    GatewayCredentialRotateResponse,
)
from dirt_control.audit import add_audit_event
from dirt_control.models import GatewayCredential
from dirt_control.retention import prune_expired_assets
from dirt_control.settings import CloudSettings
from dirt_control.storage import AssetStore
from dirt_shared.cloud_contract import PruneAssetsResponse


async def rotate_gateway_credential(
    session: AsyncSession,
    *,
    credential_id: str,
    body: GatewayCredentialRotateRequest,
    user: str,
    now: datetime,
) -> GatewayCredentialRotateResponse:
    credential = (
        await session.execute(
            select(GatewayCredential).where(
                GatewayCredential.credential_id == credential_id
            )
        )
    ).scalar_one_or_none()
    if credential is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "gateway credential not found")
    credential.token_sha256 = body.token_sha256
    credential.rotated_at = now
    credential.updated_at = now
    add_audit_event(
        session,
        now=now,
        event_type="gateway_credential_rotated",
        actor_type="browser",
        actor_id=user,
        site_id=credential.allowed_site_id,
        subject_type="gateway_credential",
        subject_id=credential.credential_id,
        metadata={"gateway_id": credential.gateway_id},
    )
    await session.commit()
    return GatewayCredentialRotateResponse(
        credential_id=credential.credential_id,
        gateway_id=credential.gateway_id,
        allowed_site_id=credential.allowed_site_id,
        rotated_at=credential.rotated_at,
    )


async def prune_assets(
    session: AsyncSession,
    *,
    settings: CloudSettings,
    asset_store: AssetStore,
    user: str,
    now: datetime,
) -> PruneAssetsResponse:
    result = await prune_expired_assets(
        session,
        settings=settings,
        now=now,
        actor_type="browser",
        actor_id=user,
        site_id=settings.default_site_id,
        object_store=asset_store,
    )
    return PruneAssetsResponse(
        cutoff=result.cutoff,
        matched=result.matched,
        objects_deleted=result.objects_deleted,
    )
