"""Unit tests for the live feed endpoint.

Covers the renamed ``GET /api/feed/live.jpg`` + 404 for the three
legacy HTMX/feed routes removed by ``backend.feed.live``:

- ``GET /feed/live``
- ``GET /feed/image``
- ``GET /feed/status``

The endpoint is a thin wrapper over ``capture_frame()`` — tests
inject a fake capturer via ``app.dependency_overrides`` to avoid
touching the camera daemon socket.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from dirt_web.app import create_app
from dirt_web.deps import get_frame_capturer

# Minimal valid JPEG magic — enough to assert "image bytes round-tripped".
_FAKE_JPEG = b"\xff\xd8\xff\xe0fake-live-frame"


@pytest.fixture
async def client(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)

    async def _fake_capture() -> bytes | None:
        return _FAKE_JPEG

    app.dependency_overrides[get_frame_capturer] = lambda: _fake_capture
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "changeme"},
        )
        ac.cookies = login.cookies
        yield ac


async def test_live_jpg_returns_bytes_and_no_store(client: AsyncClient):
    response = await client.get("/api/feed/live.jpg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    # Cache-Control: no-store is required by the API spec so intermediate
    # caches don't serve a stale frame to a second client hitting the
    # same cache-busted URL.
    assert response.headers["cache-control"] == "no-store"
    assert response.content == _FAKE_JPEG


async def test_live_jpg_returns_503_when_daemon_unreachable(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)

    async def _down_capture() -> bytes | None:
        return None

    app.dependency_overrides[get_frame_capturer] = lambda: _down_capture
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "changeme"},
        )
        ac.cookies = login.cookies
        response = await ac.get("/api/feed/live.jpg")
        assert response.status_code == 503


async def test_live_jpg_requires_auth(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/feed/live.jpg")
        assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    ["/feed/live", "/feed/image", "/feed/status"],
)
def test_legacy_feed_routes_unregistered(app_engine, path: str):
    """The three legacy HTMX/feed routes MUST no longer be registered.

    The SPA-fallback middleware rewrites all non-``/api/`` 404s into
    503 (dist missing) or an ``index.html`` 200 (dist present), so we
    can't simply assert a 404 at the transport layer. The durable
    assertion is structural: the handler entries are gone from
    ``app.routes``.
    """
    app = create_app(engine=app_engine, run_mcp=False)
    registered = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set()) or set()
    }
    assert (path, "GET") not in registered, (
        f"legacy route GET {path} still registered; delete the handler"
    )
