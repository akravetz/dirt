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
            # Authenticate
            login = await ac.post(
                "/login", data={"username": "admin", "password": "changeme"}
            )
            ac.cookies = login.cookies
            yield ac


async def test_index_returns_200(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Dirt" in response.text
