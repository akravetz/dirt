from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from dirt_control.api.browser_schemas.common import BrowserResponse

PTZ_COMMAND_TYPES = Literal["ptz_preset", "ptz_look", "ptz_zoom"]


class CommandCreateRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=160)
    site_id: str | None = None
    source_tent_id: int = Field(gt=0)
    device_id: Literal["obsbot-main"]
    capability_id: Literal["ptz_move"]
    command_type: PTZ_COMMAND_TYPES
    payload: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BrowserResponse):
    command_id: str
    idempotency_key: str
    site_id: str
    source_tent_id: int | None
    legacy_target_tent_id: str
    device_id: str | None
    capability_id: str | None
    command_type: str
    payload: dict[str, Any]
    status: str
    queued_at: datetime
    expires_at: datetime
    claimed_by: str | None
    claimed_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    result: dict[str, Any] | None
    error: str | None
