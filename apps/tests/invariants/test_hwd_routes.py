"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by
the agent. If this test fails, the agent must fix the hwd app to satisfy
the test, never modify this file.

Purpose: The dirt_hwd FastAPI app (port 8000, the keep-alive daemon) must
expose only sensor ingest endpoints. Any route not in the allowlist is a
boundary violation — web UI / sensors API / MCP belong on dirt_web.

Additional contract: /api/ingest/sensors must reject unauthenticated
requests with 401 (bearer-token check). Unlike dirt_web (cookie sessions)
the hwd app has no AuthMiddleware — each endpoint carries its own auth
dependency.
"""

import pytest
from httpx import ASGITransport, AsyncClient

# FastAPI framework-generated paths — not subject to our route allowlist.
FRAMEWORK_PATHS = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

# Paths the hwd app IS allowed to expose. Keep this list tight.
ALLOWED_HWD_PATHS = {
    "/api/ingest/sensors",
}


def _get_hwd_routes():
    from dirt_hwd.app import app

    routes = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is None:
            continue
        routes.append(path)
    return routes


def test_hwd_exposes_only_ingest_paths():
    """dirt_hwd must not grow UI/API routes — it's an ingest daemon."""
    paths = set(_get_hwd_routes())
    unexpected = paths - FRAMEWORK_PATHS - ALLOWED_HWD_PATHS
    assert not unexpected, (
        f"dirt_hwd.app exposes paths outside the ingest allowlist: {sorted(unexpected)}.\n"
        "FIX: move the route to dirt_web (cookie auth) or dirt_mcp (bearer auth).\n"
        "Keep dirt_hwd scope to ingest + HW lifespan only."
    )


@pytest.fixture
async def unauthenticated_hwd_client():
    from dirt_hwd.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac


async def test_ingest_rejects_unauthenticated_post(
    unauthenticated_hwd_client: AsyncClient,
):
    """POST /api/ingest/sensors with no bearer must 401."""
    response = await unauthenticated_hwd_client.post(
        "/api/ingest/sensors",
        json={"location": "test", "metrics": {"x": 1.0}},
    )
    assert response.status_code == 401, (
        f"POST /api/ingest/sensors returned {response.status_code}; "
        "expected 401 (bearer-token auth)."
    )


async def test_ingest_rejects_invalid_bearer(
    unauthenticated_hwd_client: AsyncClient,
):
    """POST /api/ingest/sensors with a wrong bearer must 401."""
    response = await unauthenticated_hwd_client.post(
        "/api/ingest/sensors",
        json={"location": "test", "metrics": {"x": 1.0}},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401, (
        f"POST /api/ingest/sensors with bad bearer returned {response.status_code}; "
        "expected 401."
    )
