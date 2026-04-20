from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from dirt_mcp.auth import BearerTokenMiddleware
from dirt_mcp.tools import _register_tools
from dirt_shared.services.snapshots import SnapshotsService


def create_mcp_app(
    *,
    snapshots: SnapshotsService,
    bearer_token: str,
    stateless: bool = False,
    transport_security: Any = None,
) -> tuple[Starlette, Callable]:
    """Create a self-contained MCP ASGI application.

    Args:
        snapshots: SnapshotsService passed in by the composition root
            (typically ``dirt_web.app.create_app``). Captured by tool
            closures registered via ``_register_tools``.
        bearer_token: required bearer token for the MCP sub-app's auth
            middleware. Tests pass a known value; production reads from
            ``Settings.mcp_bearer_token`` at the composition root.

    Returns:
        A tuple of (starlette_app, run_context_manager). The caller must
        enter the context manager to start the MCP session manager before
        the app can handle requests.
    """
    if transport_security is None:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )
    server = FastMCP(
        "dirt",
        streamable_http_path="/",
        stateless_http=stateless,
        transport_security=transport_security,
    )
    _register_tools(server, snapshots=snapshots)

    app = server.streamable_http_app()
    app.add_middleware(BearerTokenMiddleware, token=bearer_token)

    @asynccontextmanager
    async def run() -> AsyncIterator[None]:
        async with server.session_manager.run():
            yield

    return app, run
