"""Auth JSON endpoints — login / logout / me.

The SPA calls these; there are no HTML forms. All three are carved out
of AuthMiddleware's cookie check (``PUBLIC_API_PREFIXES``). /me is the
SPA's session probe on boot: 200 with {username} when the cookie is
valid, 401 when it's missing/expired/tampered.
"""

from dirt_contracts.webapp_v1.models import LoginRequest, User
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from dirt_shared.config import Settings
from dirt_web.auth import SessionManager, get_sessions
from dirt_web.deps import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=User)
async def login(
    payload: LoginRequest,
    response: Response,
    sessions: SessionManager = Depends(get_sessions),
    settings: Settings = Depends(get_settings),
) -> User:
    """Validate credentials and set the dirt_session cookie."""
    if (
        payload.username != settings.auth_username
        or payload.password != settings.auth_password
    ):
        raise HTTPException(status_code=401, detail="unauthorized")

    sessions.create_cookie(response, payload.username)
    return User(username=payload.username)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    sessions: SessionManager = Depends(get_sessions),
) -> Response:
    """Clear the dirt_session cookie."""
    sessions.clear_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=User)
async def me(
    request: Request,
    sessions: SessionManager = Depends(get_sessions),
) -> User:
    """Return the current user or 401."""
    username = sessions.get_current_user(request)
    if username is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return User(username=username)
