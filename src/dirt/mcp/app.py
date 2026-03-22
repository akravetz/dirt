from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from dirt.mcp.auth import BearerTokenMiddleware
from dirt.mcp.tools import _register_tools


def create_mcp_app(
    *,
    stateless: bool = False,
    transport_security: Any = None,
) -> tuple[Starlette, Callable]:
    """Create a self-contained MCP ASGI application.

    Returns:
        A tuple of (starlette_app, run_context_manager). The caller must
        enter the context manager to start the MCP session manager before
        the app can handle requests.
    """
    kwargs: dict[str, Any] = {}
    if transport_security is not None:
        kwargs["transport_security"] = transport_security
    server = FastMCP(
        "dirt",
        streamable_http_path="/",
        stateless_http=stateless,
        **kwargs,
    )
    _register_tools(server)

    app = server.streamable_http_app()
    app.add_middleware(BearerTokenMiddleware)

    @asynccontextmanager
    async def run() -> AsyncIterator[None]:
        async with server.session_manager.run():
            yield

    return app, run
