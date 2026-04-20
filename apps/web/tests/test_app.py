import pytest
from httpx import ASGITransport, AsyncClient

from dirt_web.app import create_app


@pytest.fixture
async def client(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        login = await ac.post(
            "/login", data={"username": "admin", "password": "changeme"}
        )
        ac.cookies = login.cookies
        yield ac


async def test_index_returns_200(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Dirt" in response.text
