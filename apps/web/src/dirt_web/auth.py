"""Cookie-session auth for dirt-web.

The SPA is served as static files from any non-/api/ path and does its
own client-side routing; auth status is discovered by the browser via
``GET /api/auth/me`` on boot. Only /api/* endpoints are gated here, and
an unauthenticated /api/* request returns ``401 {"detail": "unauthorized"}``
— no redirects. /api/auth/* is carved out so the SPA can log in.
"""

from collections.abc import Iterable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, URLSafeSerializer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class SessionManager:
    """Signs and parses the session cookie. Constructed in the composition
    root with a fresh URLSafeSerializer; passed to AuthMiddleware and
    exposed to handlers via ``request.app.state.sessions``."""

    SESSION_COOKIE = "dirt_session"

    def __init__(self, serializer: URLSafeSerializer) -> None:
        self._serializer = serializer

    def create_cookie(self, response: Response, username: str) -> None:
        value = self._serializer.dumps({"user": username})
        response.set_cookie(self.SESSION_COOKIE, value, httponly=True, samesite="lax")

    def clear_cookie(self, response: Response) -> None:
        response.delete_cookie(self.SESSION_COOKIE)

    def get_current_user(self, request: Request) -> str | None:
        cookie = request.cookies.get(self.SESSION_COOKIE)
        if cookie is None:
            return None
        try:
            data = self._serializer.loads(cookie)
            return data.get("user")
        except BadSignature:
            return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Gate /api/* on a valid dirt_session cookie.

    Non-/api/* paths pass through untouched so the SPA bundle and
    deeplinked client-side routes can render pre-auth. /api/auth/* is
    public (login/logout/me must be reachable without the cookie).
    Additional exempt prefixes (e.g. /mcp, which carries its own bearer
    auth) are passed in by the composition root.
    """

    PUBLIC_API_PREFIXES = ("/api/auth/",)

    def __init__(
        self,
        app,
        sessions: SessionManager,
        exclude_prefixes: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._sessions = sessions
        self._exclude_prefixes = tuple(exclude_prefixes or [])

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Anything outside /api/* is served without auth — the SPA shell
        # renders and decides what to do based on /api/auth/me.
        if not path.startswith("/api/"):
            return await call_next(request)

        if path.startswith(self._exclude_prefixes):
            return await call_next(request)

        if path.startswith(self.PUBLIC_API_PREFIXES):
            return await call_next(request)

        if self._sessions.get_current_user(request) is None:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)

        return await call_next(request)


def get_sessions(request: Request) -> SessionManager:
    """FastAPI dependency: resolve the SessionManager wired into app.state."""
    return request.app.state.sessions
