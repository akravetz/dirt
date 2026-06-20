from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.auth import LoginRequest, UserResponse
from dirt_control.audit import add_audit_event
from dirt_control.security import verify_password
from dirt_control.settings import CloudSettings


async def login_user(
    body: LoginRequest,
    *,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
) -> UserResponse:
    if body.username != settings.admin_username or not verify_password(
        body.password, settings.admin_password_hash
    ):
        add_audit_event(
            session,
            now=now,
            event_type="auth_login_failed",
            actor_type="browser",
            actor_id=body.username,
        )
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    add_audit_event(
        session,
        now=now,
        event_type="auth_login_succeeded",
        actor_type="browser",
        actor_id=body.username,
    )
    await session.commit()
    return UserResponse(username=body.username)
