"""Unit tests for POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me.

The three JSON endpoints replace the old Jinja /login GET + form-POST
/login + GET /logout handlers. Assertions:

- Login with good creds → 200, ``User`` body, ``dirt_session`` cookie set.
- Login with bad creds → 401, no cookie.
- /me without cookie → 401 JSON (NOT a 302 redirect — the SPA probes
  auth here and routes itself).
- /me with cookie → 200, User(username=...).
- Logout → 204, cookie cleared; follow-up /me → 401.
"""

import pytest
from dirt_contracts.webapp_v1.models import User
from httpx import ASGITransport, AsyncClient

from dirt_web.app import create_app


@pytest.fixture
async def client():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac


async def test_login_success_sets_cookie(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "changeme"},
    )
    assert response.status_code == 200
    model = User.model_validate(response.json())
    assert model.username == "admin"
    assert "dirt_session" in response.cookies


async def test_login_bad_password_returns_401_json(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert "dirt_session" not in response.cookies


async def test_login_unknown_user_returns_401_json(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "anything"},
    )
    assert response.status_code == 401


async def test_me_without_cookie_returns_401_json(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    # Must NOT be the legacy 302 → /login redirect.
    assert "location" not in response.headers


async def test_me_with_cookie_returns_user(client: AsyncClient):
    login = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "changeme"},
    )
    client.cookies = login.cookies

    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    model = User.model_validate(response.json())
    assert model.username == "admin"


async def test_logout_clears_cookie_and_me_returns_401(client: AsyncClient):
    login = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "changeme"},
    )
    client.cookies = login.cookies

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204

    # Follow the cookie jar the server sent back (Set-Cookie with a
    # Max-Age=0 or equivalent deletion directive).
    client.cookies = logout.cookies
    me = await client.get("/api/auth/me")
    assert me.status_code == 401


async def test_login_validates_request_body(client: AsyncClient):
    # Pydantic rejects missing/empty fields before we reach auth logic.
    response = await client.post("/api/auth/login", json={"username": "admin"})
    assert response.status_code == 422


async def test_api_routes_require_auth_with_401_json(client: AsyncClient):
    # Formerly returned 302 → /login. Now must return 401 JSON so the
    # SPA can route itself client-side.
    response = await client.get("/api/grow/current")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert "location" not in response.headers
