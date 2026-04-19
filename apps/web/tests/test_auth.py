from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    with patch("dirt_shared.services.capture.capture_loop"):
        from dirt_web.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as ac:
            yield ac


async def test_unauthenticated_redirects_to_login(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_login_page_renders(client: AsyncClient):
    response = await client.get("/login")
    assert response.status_code == 200
    assert "Log in" in response.text


async def test_login_success(client: AsyncClient):
    response = await client.post(
        "/login", data={"username": "admin", "password": "changeme"}
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert "dirt_session" in response.cookies


async def test_login_failure(client: AsyncClient):
    response = await client.post(
        "/login", data={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401
    assert "Invalid username or password" in response.text
    assert "dirt_session" not in response.cookies


async def test_authenticated_access(client: AsyncClient):
    login = await client.post(
        "/login", data={"username": "admin", "password": "changeme"}
    )
    client.cookies = login.cookies

    response = await client.get("/")
    assert response.status_code == 200
    assert "Dirt" in response.text


async def test_logout_clears_session(client: AsyncClient):
    login = await client.post(
        "/login", data={"username": "admin", "password": "changeme"}
    )
    client.cookies = login.cookies

    response = await client.get("/logout")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"

    client.cookies = response.cookies
    response = await client.get("/")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_api_routes_require_auth(client: AsyncClient):
    response = await client.get("/api/snapshots/latest")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
