"""Unit tests for GET /api/feed/snapshot/latest.

This is the rename of the old ``/api/snapshots/latest``. Covers:

- 404 when the archive is empty
- 200 + image/jpeg when a row + file exist on disk
- 401 without a session cookie
- Old ``/api/snapshots/latest`` is no longer registered
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.snapshot import Snapshot
from dirt_shared.services.scope import resolve_scope
from dirt_web.app import create_app


@pytest.fixture
async def client(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)
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


async def test_latest_snapshot_404_when_empty(client: AsyncClient):
    response = await client.get("/api/feed/snapshot/latest")
    assert response.status_code == 404


async def test_latest_snapshot_returns_image(client: AsyncClient, app_engine, tmp_path):
    img_path = tmp_path / "archive.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xe0archived-frame")

    async with AsyncSession(app_engine) as session:
        session.add(Snapshot(ts=datetime.now(UTC), file_path=str(img_path)))
        await session.commit()

    response = await client.get("/api/feed/snapshot/latest")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


async def test_latest_snapshot_accepts_tent_scope_without_unscoped_leak(
    client: AsyncClient, app_engine, tmp_path
):
    unscoped_path = tmp_path / "unscoped.jpg"
    breeding_path = tmp_path / "breeding.jpg"
    unscoped_path.write_bytes(b"\xff\xd8\xff\xe0unscoped-frame")
    breeding_path.write_bytes(b"\xff\xd8\xff\xe0breeding-frame")

    async with AsyncSession(app_engine) as session:
        breeding = await resolve_scope(session, tent_id="breeding")
        assert breeding is not None
        session.add(
            Snapshot(
                ts=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
                file_path=str(breeding_path),
                site_id=breeding.site_pk,
                tent_id=breeding.tent_pk,
            )
        )
        session.add(
            Snapshot(
                ts=datetime(2026, 5, 4, 13, 0, tzinfo=UTC),
                file_path=str(unscoped_path),
            )
        )
        await session.commit()

    response = await client.get(
        "/api/feed/snapshot/latest", params={"tent_id": "breeding"}
    )

    assert response.status_code == 200
    assert response.content == b"\xff\xd8\xff\xe0breeding-frame"


async def test_latest_snapshot_scoped_404_when_only_unscoped_exists(
    client: AsyncClient, app_engine, tmp_path
):
    img_path = tmp_path / "archive.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xe0archived-frame")

    async with AsyncSession(app_engine) as session:
        session.add(Snapshot(ts=datetime.now(UTC), file_path=str(img_path)))
        await session.commit()

    response = await client.get(
        "/api/feed/snapshot/latest", params={"tent_id": "breeding"}
    )

    assert response.status_code == 404


async def test_latest_snapshot_unknown_scope_404_without_unscoped_leak(
    client: AsyncClient, app_engine, tmp_path
):
    img_path = tmp_path / "archive.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xe0archived-frame")

    async with AsyncSession(app_engine) as session:
        session.add(Snapshot(ts=datetime.now(UTC), file_path=str(img_path)))
        await session.commit()

    response = await client.get(
        "/api/feed/snapshot/latest", params={"tent_id": "unknown"}
    )

    assert response.status_code == 404


async def test_latest_snapshot_requires_auth():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/feed/snapshot/latest")
        assert response.status_code == 401


def test_legacy_snapshots_latest_unregistered():
    """``GET /api/snapshots/latest`` MUST be gone after the rename.

    Unlike the /feed/* HTMX routes, this path IS under ``/api/`` so
    ``SPAFallbackMiddleware`` would leave a live handler's response
    untouched — but the durable check is still structural.
    """
    app = create_app(run_mcp=False)
    registered = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set()) or set()
    }
    assert ("/api/snapshots/latest", "GET") not in registered, (
        "legacy route GET /api/snapshots/latest still registered; delete the handler"
    )
