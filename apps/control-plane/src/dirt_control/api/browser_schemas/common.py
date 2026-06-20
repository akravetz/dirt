from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class BrowserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BrowserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


SyncStatusLabel = Literal["live", "stale", "offline"]


def clean_nonblank(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if stripped == "":
        raise ValueError(f"{field_name} must not be blank")
    return stripped


def clean_nonblank_list(values: list[str], *, field_name: str) -> list[str]:
    cleaned = [clean_nonblank(value, field_name=field_name) for value in values]
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"{field_name} must not contain duplicates")
    return cleaned
