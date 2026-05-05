from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.models import GatewayCredential


def sha256_hexdigest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_password_hash(password: str) -> str:
    return f"sha256:{sha256_hexdigest(password)}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash.startswith("sha256:"):
        return False
    expected = stored_hash.removeprefix("sha256:")
    return secrets.compare_digest(sha256_hexdigest(password), expected)


class BrowserSessionManager:
    cookie_name = "dirt_cloud_session"

    def __init__(
        self,
        serializer: URLSafeSerializer,
        *,
        secure_cookie: bool,
        max_age_s: int = 60 * 60 * 24 * 14,
    ) -> None:
        self._serializer = serializer
        self._secure_cookie = secure_cookie
        self._max_age_s = max_age_s

    def create_cookie(self, response: Response, username: str) -> None:
        response.set_cookie(
            self.cookie_name,
            self._serializer.dumps({"user": username}),
            httponly=True,
            secure=self._secure_cookie,
            samesite="lax",
            max_age=self._max_age_s,
        )

    def clear_cookie(self, response: Response) -> None:
        response.delete_cookie(self.cookie_name)

    def current_user(self, request: Request) -> str | None:
        cookie = request.cookies.get(self.cookie_name)
        if cookie is None:
            return None
        try:
            data = self._serializer.loads(cookie)
        except BadSignature:
            return None
        user = data.get("user")
        return user if isinstance(user, str) else None


def require_browser_user(request: Request) -> str:
    user = request.app.state.sessions.current_user(request)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unauthorized")
    return user


@dataclass(frozen=True)
class GatewayPrincipal:
    credential_id: str
    gateway_id: str
    allowed_site_id: str


async def authenticate_gateway(
    *,
    request: Request,
    session: AsyncSession,
    now: datetime,
) -> GatewayPrincipal:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing gateway token")

    token_hash = sha256_hexdigest(token)
    result = await session.execute(
        select(GatewayCredential).where(
            GatewayCredential.token_sha256 == token_hash,
            GatewayCredential.is_active.is_(True),
            GatewayCredential.revoked_at.is_(None),
        )
    )
    credential = result.scalar_one_or_none()
    if credential is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid gateway token")

    return GatewayPrincipal(
        credential_id=credential.credential_id,
        gateway_id=credential.gateway_id,
        allowed_site_id=credential.allowed_site_id,
    )


def require_gateway_scope(principal: GatewayPrincipal, site_id: str) -> None:
    if principal.allowed_site_id != site_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "gateway credential scope denied"
        )


class UrlSigner:
    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def sign(self, *, subject: str, expires_at: datetime) -> str:
        payload = f"{subject}:{int(expires_at.timestamp())}"
        digest = hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256)
        return f"{payload}:{digest.hexdigest()}"

    def build_signed_url(
        self,
        *,
        base_url: str,
        subject: str,
        expires_at: datetime,
        params: dict[str, Any] | None = None,
    ) -> str:
        query = {
            "expires": int(expires_at.timestamp()),
            "signature": self.sign(subject=subject, expires_at=expires_at),
        }
        if params:
            query.update({key: str(value) for key, value in params.items()})
        rendered = "&".join(f"{key}={value}" for key, value in query.items())
        return f"{base_url.rstrip('/')}/{subject}?{rendered}"


def expires_from(now: datetime, seconds: int) -> datetime:
    return now + timedelta(seconds=seconds)
