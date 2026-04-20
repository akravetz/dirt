from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BearerTokenMiddleware:
    """Validates Bearer token on all requests to the MCP sub-app.

    Constructor-inject the expected token (passed in by ``create_mcp_app``).
    """

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        self.app = app
        self._token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != self._token:
            response = JSONResponse(
                {"detail": "Invalid or missing bearer token"}, status_code=401
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
