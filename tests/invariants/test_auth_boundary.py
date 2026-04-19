"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by the agent.
If this test fails, the agent must fix its code to satisfy the test, never modify
this file.

Purpose: Ensures every route in the application requires authentication except
for the explicitly listed public paths.
"""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

# Paths that MUST be accessible without authentication.
# Any route not listed here MUST redirect unauthenticated requests to /login.
PUBLIC_PATHS = {
    "/login",
    "/logout",
}

# FastAPI auto-generated paths excluded from auth checks.
FRAMEWORK_PATHS = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

# Paths that use bearer token auth instead of cookie/session auth.
# These are excluded from the cookie-auth test and validated separately.
BEARER_AUTH_PREFIXES = ("/mcp", "/api/ingest")


def _get_app_routes():
    """Collect all application-defined routes (excluding framework-generated ones)."""
    with patch("dirt.services.capture.capture_loop"):
        from dirt_web.app import app

    routes = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is None or path in FRAMEWORK_PATHS:
            continue
        if any(path.startswith(prefix) for prefix in BEARER_AUTH_PREFIXES):
            continue
        methods = getattr(route, "methods", {"GET"})
        for method in methods:
            if method in ("HEAD",):
                continue
            routes.append((method, path))
    return routes


@pytest.fixture
async def unauthenticated_client():
    with patch("dirt.services.capture.capture_loop"):
        from dirt_web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac


@pytest.mark.parametrize("method,path", _get_app_routes())
async def test_unauthenticated_request_is_blocked(
    unauthenticated_client: AsyncClient, method: str, path: str
):
    """Every non-public route must redirect unauthenticated requests to /login."""
    response = await unauthenticated_client.request(method, path)

    if path in PUBLIC_PATHS:
        # Public paths must reach the actual route handler, not be intercepted
        # by auth middleware. Auth middleware returns a bare 302 with no body
        # and no set-cookie header — route handlers include additional headers.
        if response.status_code == 302 and response.headers.get("location") == "/login":
            # This is OK if the route handler itself redirects to /login
            # (e.g., /logout clears session then redirects). Auth middleware
            # redirects have no set-cookie header; route handlers do.
            has_set_cookie = "set-cookie" in response.headers
            assert has_set_cookie, (
                f"{method} {path} is listed as public but was intercepted by "
                f"auth middleware (bare redirect to /login with no set-cookie)"
            )
    else:
        # All other paths MUST redirect to login
        assert response.status_code == 302, (
            f"{method} {path} returned {response.status_code} instead of redirecting "
            f"to /login. All non-public routes must require authentication."
        )
        assert response.headers["location"] == "/login", (
            f"{method} {path} redirected to {response.headers['location']} "
            f"instead of /login"
        )


async def test_mcp_rejects_unauthenticated_requests(
    unauthenticated_client: AsyncClient,
):
    """MCP endpoint must return 401 when no bearer token is provided."""
    response = await unauthenticated_client.get("/mcp/")
    assert response.status_code == 401, (
        f"GET /mcp/ returned {response.status_code} instead of 401. "
        f"MCP endpoint must require bearer token authentication."
    )


async def test_mcp_rejects_invalid_bearer_token(unauthenticated_client: AsyncClient):
    """MCP endpoint must return 401 for an invalid bearer token."""
    response = await unauthenticated_client.get(
        "/mcp/", headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401, (
        f"GET /mcp/ with invalid token returned {response.status_code} instead of 401. "
        f"MCP endpoint must reject invalid bearer tokens."
    )
