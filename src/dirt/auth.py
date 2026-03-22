from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from dirt.config import settings

SESSION_COOKIE = "dirt_session"
PUBLIC_PATHS = {"/login", "/logout"}

_serializer = URLSafeSerializer(settings.secret_key)


def create_session_cookie(response: Response, username: str) -> None:
    """Set a signed session cookie on the response."""
    value = _serializer.dumps({"user": username})
    response.set_cookie(SESSION_COOKIE, value, httponly=True, samesite="lax")


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie."""
    response.delete_cookie(SESSION_COOKIE)


def get_current_user(request: Request) -> str | None:
    """Return the username from the session cookie, or None."""
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie is None:
        return None
    try:
        data = _serializer.loads(cookie)
        return data.get("user")
    except BadSignature:
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        user = get_current_user(request)
        if user is None:
            return RedirectResponse(url="/login", status_code=302)

        return await call_next(request)
