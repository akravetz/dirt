from fastapi import Request, Response
from fastapi.responses import RedirectResponse
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
    PUBLIC_PATHS = frozenset({"/login", "/logout"})

    def __init__(
        self,
        app,
        sessions: SessionManager,
        exclude_prefixes: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._sessions = sessions
        self._exclude_prefixes = tuple(exclude_prefixes or [])

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.PUBLIC_PATHS or request.url.path.startswith(
            self._exclude_prefixes
        ):
            return await call_next(request)

        if self._sessions.get_current_user(request) is None:
            return RedirectResponse(url="/login", status_code=302)

        return await call_next(request)


def get_sessions(request: Request) -> SessionManager:
    """FastAPI dependency: resolve the SessionManager wired into app.state."""
    return request.app.state.sessions
