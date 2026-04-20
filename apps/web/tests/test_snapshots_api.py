from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.snapshot import Snapshot


@pytest.fixture
async def client(pg_engine):
    with patch("dirt_shared.services.capture.capture_loop"):
        from dirt_web.app import app

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


async def test_latest_snapshot_returns_image(client: AsyncClient, pg_engine, tmp_path):
    img_path = tmp_path / "test.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-data")

    async with AsyncSession(pg_engine) as session:
        snapshot = Snapshot(ts=datetime.now(UTC), file_path=str(img_path))
        session.add(snapshot)
        await session.commit()

    response = await client.get("/api/snapshots/latest")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
