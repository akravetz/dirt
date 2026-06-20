from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from dirt_control.api.browser_schemas.common import BrowserResponse


class GatewayCredentialRotateRequest(BaseModel):
    token_sha256: str = Field(min_length=64, max_length=64)


class GatewayCredentialRotateResponse(BrowserResponse):
    credential_id: str
    gateway_id: str
    allowed_site_id: str
    rotated_at: datetime | None
