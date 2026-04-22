"""Unit tests for SPA static serving.

The built web-ui bundle lives at ``settings.web_ui_dist_dir``. Contract:

- ``GET /`` → the index.html contents (SPA shell).
- ``GET /live`` (or any non-/api/ path that doesn't match a backend
  route) → the SAME index.html, so TanStack Router can take over on
  refresh / deeplink.
- ``GET /assets/<file>`` → the bundled asset bytes, with the right
  content-type (JS / CSS / PNG / …).
- ``GET /api/<unknown>`` → 404 JSON, NOT the SPA shell. API paths must
  NEVER fall through the catch-all; otherwise real 404s get silently
  masked as "did you mean to render the SPA?" pages.
- ``GET /api/auth/me`` with no cookie → 401 JSON (not 302 redirect).

A tmp_path dist fixture stands in for a real built bundle.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from dirt_web.app import create_app

_INDEX_HTML = (
    "<!doctype html><html><head><title>SPA</title></head>"
    "<body><div id='root'></div><script src='/assets/main.js'></script>"
    "</body></html>"
)
_MAIN_JS = "console.log('spa');"


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    """Minimal built SPA bundle: index.html + assets/main.js."""
    assets = tmp_path / "assets"
    assets.mkdir()
    (tmp_path / "index.html").write_text(_INDEX_HTML, encoding="utf-8")
    (assets / "main.js").write_text(_MAIN_JS, encoding="utf-8")
    return tmp_path


@pytest.fixture
async def client(app_engine, dist_dir: Path):
    app = create_app(engine=app_engine, web_ui_dist_dir=dist_dir, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac


async def test_root_returns_index_html(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == _INDEX_HTML


async def test_client_routed_path_returns_same_index_html(client: AsyncClient):
    # /live is a TanStack-Router client route — the server must hand
    # back index.html unchanged so the router bootstraps and navigates
    # to the correct view.
    response = await client.get("/live")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == _INDEX_HTML


async def test_nested_client_route_returns_index_html(client: AsyncClient):
    response = await client.get("/wiki/hardware/fan")
    assert response.status_code == 200
    assert response.text == _INDEX_HTML


async def test_assets_pass_through_as_js(client: AsyncClient):
    response = await client.get("/assets/main.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        ("application/javascript", "text/javascript")
    )
    assert response.text == _MAIN_JS


async def test_unknown_api_returns_404_json_not_spa_shell(client: AsyncClient):
    # Critical: the catch-all must NOT mask real API 404s. An unknown
    # /api/* path is a server-side 404, full stop — never the SPA
    # shell. (Authenticate first so AuthMiddleware doesn't intercept
    # with a 401; the point of this test is the catch-all behaviour,
    # not auth gating.)
    login = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "changeme"},
    )
    client.cookies = login.cookies

    response = await client.get("/api/unknown")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.text != _INDEX_HTML


async def test_unknown_api_unauthenticated_returns_401_not_spa_shell(
    client: AsyncClient,
):
    # Belt-and-braces: even the unauthenticated path must not leak the
    # SPA shell. 401 is fine (AuthMiddleware short-circuits), but the
    # response body must NOT be index.html.
    response = await client.get("/api/unknown")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert response.text != _INDEX_HTML


async def test_api_auth_me_without_cookie_returns_401_json(client: AsyncClient):
    # Critical: AuthMiddleware on /api/* must emit JSON 401, never a
    # 302 → /login redirect. The SPA does its own routing based on the
    # body.
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert "location" not in response.headers


async def test_missing_dist_returns_503(app_engine, tmp_path: Path):
    # Fresh clone without `pnpm --dir web-ui build` — the app must boot
    # and non-/api/ 404s become 503 placeholders rather than ambiguous
    # 404s or a crash.
    missing_dist = tmp_path / "nope"
    app = create_app(engine=app_engine, web_ui_dist_dir=missing_dist, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/")
        assert response.status_code == 503
        assert response.headers["content-type"].startswith("application/json")

        # /api/* still responds cleanly without leaking the placeholder.
        # Unknown /api/* auth-gated path → 401, not 503 or SPA shell.
        api_response = await ac.get("/api/unknown")
        assert api_response.status_code == 401
        assert api_response.headers["content-type"].startswith("application/json")
