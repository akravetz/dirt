from __future__ import annotations

from datetime import datetime

from dirt_control.api.browser_schemas.common import BrowserResponse


class AssetResponse(BrowserResponse):
    asset_id: str
    kind: str
    content_type: str
    byte_size: int
    sha256: str | None
    captured_at: datetime
    uploaded_at: datetime
    signed_url: str
    signed_url_expires_at: datetime
