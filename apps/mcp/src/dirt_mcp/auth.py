from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from dirt_shared.config import settings


class BearerTokenMiddleware:
    """Validates Bearer token on all requests to the MCP sub-app."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != settings.mcp_bearer_token:
            response = JSONResponse(
                {"detail": "Invalid or missing bearer token"}, status_code=401
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
