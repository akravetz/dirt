from __future__ import annotations

from pydantic import BaseModel, Field

from dirt_control.api.browser_schemas.common import BrowserResponse


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserResponse(BrowserResponse):
    username: str
