from __future__ import annotations

from datetime import datetime

from dirt_control.api.browser_schemas.common import BrowserResponse


class TentResponse(BrowserResponse):
    site_id: str
    source_tent_id: int
    name: str
    role: str | None
    is_active: bool
    synced_at: datetime


class TentStateResponse(BrowserResponse):
    site_id: str
    source_tent_id: int
    name: str
    role: str | None
    is_active: bool
    gateway_last_seen_at: datetime | None
    last_catalog_sync_at: datetime | None


class DeviceResponse(BrowserResponse):
    device_id: str
    name: str
    kind: str
    controller: str | None
    is_active: bool
    last_seen_at: datetime | None


class LightScheduleResponse(BrowserResponse):
    site_id: str
    source_tent_id: int
    tent_name: str
    source_zone_id: int | None
    device_id: str | None
    capability_id: str | None
    source_schedule_id: int
    kind: str
    enabled: bool
    timezone: str
    starts_local: str
    ends_local: str
    duration_hours: float
    is_on: bool
    minutes_until_off: float
    minutes_until_on: float


class LightSchedulesResponse(BrowserResponse):
    site_id: str
    source_tent_id: int
    tent_name: str
    schedules: list[LightScheduleResponse]
