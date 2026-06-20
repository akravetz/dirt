from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dirt_control.api.browser_schemas.common import BrowserResponse
from dirt_shared.cloud_contract import PtzCommandTarget

PTZ_COMMAND_TYPES = Literal["ptz_preset", "ptz_look", "ptz_zoom"]


class CommandCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=160)
    site_id: str | None = None
    target: PtzCommandTarget
    command_type: PTZ_COMMAND_TYPES
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _target_is_complete(self) -> CommandCreateRequest:
        if self.target.source_tent_id is None:
            raise ValueError("PTZ target requires source_tent_id")
        return self

    def resolved_target(self) -> PtzCommandTarget:
        return self.target


class CommandResponse(BrowserResponse):
    model_config = ConfigDict(extra="forbid")

    command_id: str
    idempotency_key: str
    site_id: str
    target: PtzCommandTarget | None = None
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
