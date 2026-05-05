from __future__ import annotations

import subprocess
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from dirt_control.app import create_app
from dirt_control.db import create_sessionmaker
from dirt_control.models import GatewayCredential
from dirt_control.security import sha256_hexdigest, sha256_password_hash
from dirt_control.settings import CloudSettings

FIXED_NOW = datetime(2026, 5, 5, 3, 45, tzinfo=UTC)
ADMIN_PASSWORD = "test-password"
GATEWAY_TOKEN = "gateway-token"
REPO_ROOT = Path(__file__).resolve().parents[3]
CLOUD_MIGRATIONS = REPO_ROOT / "cloud" / "migrations"


def _local_pg_parts() -> tuple[str, str, str, int]:
    from dirt_shared.config import Settings

    settings = Settings()
    return (
        settings.dirt_pg_user,
        settings.dirt_pg_password,
        settings.dirt_pg_host,
        settings.dirt_pg_port,
    )


def _pg_url(dbname: str) -> str:
    user, password, host, port = _local_pg_parts()
    return f"postgres://{user}:{password}@{host}:{port}/{dbname}?sslmode=disable"


def _async_pg_url(dbname: str) -> str:
    user, password, host, port = _local_pg_parts()
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"


@pytest_asyncio.fixture
async def cloud_engine() -> AsyncIterator[AsyncEngine]:
    dbname = f"dirt_cloud_test_{uuid.uuid4().hex[:12]}"
    admin = await asyncpg.connect(_pg_url("postgres"))
    try:
        await admin.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await admin.close()

    result = subprocess.run(  # noqa: ASYNC221
        [
            "atlas",
            "migrate",
            "apply",
            "--dir",
            f"file://{CLOUD_MIGRATIONS}",
            "--url",
            _pg_url(dbname),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "cloud atlas migrate apply failed for test database:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    engine = create_async_engine(_async_pg_url(dbname), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()
        admin = await asyncpg.connect(_pg_url("postgres"))
        try:
            await admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
        finally:
            await admin.close()


@pytest_asyncio.fixture
async def settings(cloud_engine: AsyncEngine) -> CloudSettings:
    return CloudSettings(
        DIRT_CLOUD_DATABASE_URL=str(cloud_engine.url),
        DIRT_CLOUD_ADMIN_USERNAME="admin",
        DIRT_CLOUD_ADMIN_PASSWORD_HASH=sha256_password_hash(ADMIN_PASSWORD),
        DIRT_CLOUD_SESSION_SECRET="test-session-secret-at-least-16",
        DIRT_CLOUD_SESSION_COOKIE_SECURE=False,
        DIRT_CLOUD_ASSET_PUBLIC_BASE_URL="https://assets.test",
    )


@pytest_asyncio.fixture
async def seeded_gateway(cloud_engine: AsyncEngine) -> None:
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(
            GatewayCredential(
                credential_id="gateway-main",
                gateway_id="gateway-main",
                token_sha256=sha256_hexdigest(GATEWAY_TOKEN),
                allowed_site_id="homebox",
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        await session.commit()


@pytest_asyncio.fixture
async def client(
    cloud_engine: AsyncEngine,
    settings: CloudSettings,
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=settings, engine=cloud_engine, clock=lambda: FIXED_NOW)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def authed_client(client: AsyncClient) -> AsyncClient:
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    client.cookies = response.cookies
    return client


@pytest_asyncio.fixture
async def gateway_headers(seeded_gateway: None) -> dict[str, str]:
    return {"authorization": f"Bearer {GATEWAY_TOKEN}"}
