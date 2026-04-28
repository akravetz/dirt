"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Codex hooks and MUST NOT be modified by
the agent. If this test fails, the agent must fix its code to satisfy
the test, never modify this file.

Purpose: enforce the dirt_web FastAPI auth boundary under the Phase-2
contract. Replaces the pre-rewrite "every non-public route redirects
302 → /login" invariant, which was valid under the Jinja/form-post
auth scheme but is wrong for the new JSON-cookie contract.

The Phase-2 contract (as landed by the backend.auth feature):

- `/api/auth/*` — PUBLIC. Login, logout, me. Unauthenticated requests
  reach the route handler (handler responses vary: 200 login success,
  204 logout, 401 on /me without cookie, 422 on login body validation,
  etc.) and are NOT intercepted by AuthMiddleware. In particular they
  never carry a Location header and never return 302.
- `/api/*` (everything else under /api/) — cookie-session gated. An
  unauthenticated request must return `401` with a JSON body and
  NO Location header.
- Non-/api/ routes — served by route handlers or SPA static/fallback
  infrastructure. Whatever they return, it MUST NOT be a 302 to /login.
  AuthMiddleware no longer redirects; any residual 302 here is a
  regression. Specific responses vary (200 for SPA shell, 404 for
  unknown paths, 503 if the dist bundle is missing at startup).
- `/mcp/*` — bearer-auth. Covered by the two dedicated tests at the
  bottom of this file.

Phase 0 note: sensor ingest moved to dirt_hwd.service (port 8000) and
is no longer served by dirt_web. That endpoint's bearer-auth contract
is re-validated in test_hwd_routes.py.
"""

import pytest
from httpx import ASGITransport, AsyncClient

# Prefix carving out the public auth endpoints (login / logout / me).
AUTH_PREFIX = "/api/auth/"

# FastAPI auto-generated paths excluded from auth checks.
FRAMEWORK_PATHS = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

# Paths that use bearer token auth instead of cookie/session auth.
# These are excluded from the cookie-auth tests and validated
# separately (test_mcp_*).
BEARER_AUTH_PREFIXES = ("/mcp",)


def _get_app_routes():
    """Collect all application-defined routes (excluding framework-generated)."""
    from dirt_web.app import app

    routes = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is None or path in FRAMEWORK_PATHS:
            continue
        if any(path.startswith(prefix) for prefix in BEARER_AUTH_PREFIXES):
            continue
        methods = getattr(route, "methods", None) or {"GET"}
        for method in methods:
            if method in ("HEAD",):
                continue
            routes.append((method, path))
    return routes


def _api_non_auth_routes():
    return [
        (m, p)
        for (m, p) in _get_app_routes()
        if p.startswith("/api/") and not p.startswith(AUTH_PREFIX)
    ]


def _api_auth_routes():
    return [(m, p) for (m, p) in _get_app_routes() if p.startswith(AUTH_PREFIX)]


@pytest.fixture
async def unauthenticated_client():
    from dirt_web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac


@pytest.mark.parametrize("method,path", _get_app_routes())
async def test_no_middleware_302_anywhere(
    unauthenticated_client: AsyncClient, method: str, path: str
):
    """AuthMiddleware must NOT issue 302 redirects for any route.

    Pre-Phase-2, the middleware redirected unauthenticated callers to
    /login for every gated route. The new contract returns 401 JSON on
    /api/* (except /api/auth/*) and lets the SPA shell render for
    everything else. A 302 response from ANY route is a regression in
    the middleware's behaviour — no legitimate handler returns 302 in
    the current route map.
    """
    response = await unauthenticated_client.request(method, path)
    assert response.status_code != 302, (
        f"{method} {path} returned 302 → {response.headers.get('location')!r}. "
        "AuthMiddleware must not issue 302 redirects; /api/* should 401 "
        "JSON, and everything else should serve the SPA shell or the "
        "handler's own non-redirect response."
    )


@pytest.mark.parametrize("method,path", _api_non_auth_routes())
async def test_api_paths_return_401_json_unauthenticated(
    unauthenticated_client: AsyncClient, method: str, path: str
):
    """Every /api/* route (except /api/auth/*) must 401-JSON for unauth."""
    response = await unauthenticated_client.request(method, path)
    assert response.status_code == 401, (
        f"{method} {path} returned {response.status_code} instead of 401 "
        f"for an unauthenticated caller. /api/* must be cookie-session gated."
    )
    assert "location" not in {k.lower(): v for k, v in response.headers.items()}, (
        f"{method} {path} returned 401 but also set a Location header "
        f"({response.headers.get('location')!r}); the auth 401 must be a "
        f"clean JSON response with no redirect hint."
    )
    ctype = response.headers.get("content-type", "")
    assert "json" in ctype.lower(), (
        f"{method} {path} 401 response content-type is {ctype!r}; "
        f"must be JSON (e.g. application/json)."
    )


@pytest.mark.parametrize("method,path", _api_auth_routes())
async def test_api_auth_endpoints_reach_handler_unauthenticated(
    unauthenticated_client: AsyncClient, method: str, path: str
):
    """/api/auth/* endpoints are public — unauthenticated requests reach the
    route handler, not AuthMiddleware.

    Handler responses vary by endpoint + input: 401 on /me without cookie,
    422 on login with an invalid body, 204 on logout, 200 on login
    success, 405 if a wrong method hits a known auth path. What we
    assert is "not middleware-intercepted": no Location header, no 302.
    """
    response = await unauthenticated_client.request(method, path)
    assert response.status_code != 302, (
        f"{method} {path} is under /api/auth/ but returned 302; no auth "
        f"endpoint should redirect (login returns 200 + Set-Cookie; logout "
        f"returns 204; me returns 200 or 401 JSON)."
    )
    location = response.headers.get("location")
    assert location is None, (
        f"{method} {path} is under /api/auth/ but the response has a "
        f"Location header ({location!r}); AuthMiddleware must not touch "
        f"/api/auth/*."
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
        f"GET /mcp/ with invalid token returned {response.status_code} "
        f"instead of 401. MCP endpoint must reject invalid bearer tokens."
    )
