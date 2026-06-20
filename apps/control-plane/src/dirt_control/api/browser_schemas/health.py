from __future__ import annotations

from datetime import datetime
from typing import Literal

from dirt_control.api.browser_schemas.common import BrowserResponse, SyncStatusLabel


class HealthResponse(BrowserResponse):
    service: Literal["control-plane-api"]
    ok: bool
    site_id: str
    status: SyncStatusLabel
    gateway_last_seen_at: datetime | None
    gateway_heartbeat_age_s: int | None
    gateway_backlog_depth: int
    command_backlog_depth: int
    command_failures_24h: int
    asset_failures_24h: int
    asset_retention_days: int
    commands_enabled: bool


class SyncStatusResponse(BrowserResponse):
    site_id: str
    gateway_last_seen_at: datetime | None
    gateway_backlog_depth: int
    last_catalog_sync_at: datetime | None
    command_backlog_depth: int
    status: SyncStatusLabel
