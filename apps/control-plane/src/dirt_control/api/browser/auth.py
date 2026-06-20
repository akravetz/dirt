from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status

from dirt_control.api.browser_schemas.auth import LoginRequest, UserResponse
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.browser_auth import login_user
from dirt_control.settings import CloudSettings

router = APIRouter()


@router.post("/auth/login", response_model=UserResponse)
async def login(  # noqa: PLR0913
    body: LoginRequest,
    response: Response,
    request: Request,
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> UserResponse:
    result = await login_user(body, settings=settings, session=session, now=clock())
    request.app.state.sessions.create_cookie(response, body.username)
    return result


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def logout(response: Response, request: Request) -> None:
    request.app.state.sessions.clear_cookie(response)


@router.get("/auth/me", response_model=UserResponse)
async def me(user: str = Depends(require_browser_user)) -> UserResponse:
    return UserResponse(username=user)
