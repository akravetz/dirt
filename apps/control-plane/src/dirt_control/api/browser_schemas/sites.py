from __future__ import annotations

from datetime import datetime

from dirt_control.api.browser_schemas.common import BrowserResponse


class SiteResponse(BrowserResponse):
    site_id: str
    name: str
    timezone: str
    is_active: bool
    gateway_last_seen_at: datetime | None
    last_catalog_sync_at: datetime | None
