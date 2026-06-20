from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from dirt_control.api.browser_schemas.common import BrowserResponse
from dirt_shared.cloud_contract import PtzCommandTarget

PTZ_COMMAND_TYPES = Literal["ptz_preset", "ptz_look", "ptz_zoom"]


class CommandCreateRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=160)
    site_id: str | None = None
    source_tent_id: int | None = Field(
        default=None,
        gt=0,
        json_schema_extra={"deprecated": True},
        description="Deprecated flat PTZ target field; use target.source_tent_id.",
    )
    device_id: Literal["obsbot-main"] | None = Field(
        default=None,
        json_schema_extra={"deprecated": True},
        description="Deprecated flat PTZ target field; use target.device_id.",
    )
    capability_id: Literal["ptz_move"] | None = Field(
        default=None,
        json_schema_extra={"deprecated": True},
        description="Deprecated flat PTZ target field; use target.capability_id.",
    )
    target: PtzCommandTarget | None = None
    command_type: PTZ_COMMAND_TYPES
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _target_is_complete(self) -> CommandCreateRequest:
        if self.target is None:
            if (
                self.source_tent_id is None
                or self.device_id is None
                or self.capability_id is None
            ):
                raise ValueError(
                    "PTZ commands require either target or flat PTZ target fields"
                )
            return self

        if self.target.source_tent_id is None and self.source_tent_id is None:
            raise ValueError("PTZ target requires source_tent_id")
        if (
            self.source_tent_id is not None
            and self.target.source_tent_id is not None
            and self.source_tent_id != self.target.source_tent_id
        ):
            raise ValueError("flat source_tent_id must match target.source_tent_id")
        if self.device_id is not None and self.device_id != self.target.device_id:
            raise ValueError("flat device_id must match target.device_id")
        if (
            self.capability_id is not None
            and self.capability_id != self.target.capability_id
        ):
            raise ValueError("flat capability_id must match target.capability_id")
        return self

    def resolved_target(self) -> PtzCommandTarget:
        target = self.target
        source_tent_id = (
            target.source_tent_id
            if target is not None and target.source_tent_id is not None
            else self.source_tent_id
        )
        if source_tent_id is None:
            raise ValueError("validated PTZ command is missing source_tent_id")
        if target is not None:
            return target.model_copy(update={"source_tent_id": source_tent_id})
        if self.device_id is None or self.capability_id is None:
            raise ValueError("validated PTZ command is missing flat target fields")
        return PtzCommandTarget(
            kind="ptz",
            source_tent_id=source_tent_id,
            device_id=self.device_id,
            capability_id=self.capability_id,
        )


class CommandResponse(BrowserResponse):
    command_id: str
    idempotency_key: str
    site_id: str
    source_tent_id: int | None = Field(
        default=None,
        json_schema_extra={"deprecated": True},
        description="Deprecated flat PTZ target field; use target.source_tent_id.",
    )
    legacy_target_tent_id: str | None = Field(
        default=None,
        json_schema_extra={"deprecated": True},
        description="Deprecated transition field for legacy cloud text command scope.",
    )
    device_id: str | None = Field(
        default=None,
        json_schema_extra={"deprecated": True},
        description="Deprecated flat PTZ target field; use target.device_id.",
    )
    capability_id: str | None = Field(
        default=None,
        json_schema_extra={"deprecated": True},
        description="Deprecated flat PTZ target field; use target.capability_id.",
    )
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
