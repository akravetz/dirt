from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.snapshot import Snapshot
from dirt_web.app import create_app


@pytest.fixture
async def client(app_engine):
    """Per-test app wired to the test engine, no MCP, no module-level patches."""
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


async def test_latest_snapshot_404_when_empty(client: AsyncClient):
    response = await client.get("/api/snapshots/latest")
    assert response.status_code == 404


async def test_latest_snapshot_returns_image(
    client: AsyncClient, app_engine, tmp_path
):
    img_path = tmp_path / "test.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-data")

    async with AsyncSession(app_engine) as session:
        snapshot = Snapshot(ts=datetime.now(UTC), file_path=str(img_path))
        session.add(snapshot)
        await session.commit()

    response = await client.get("/api/snapshots/latest")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
