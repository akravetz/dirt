from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from dirt_control.app import create_app
from dirt_control.db import create_sessionmaker
from dirt_control.models import CloudAsset, CloudSite
from dirt_control.security import sha256_password_hash
from dirt_control.settings import CloudSettings

FIXED_NOW = datetime(2026, 5, 5, 3, 45, tzinfo=UTC)
ADMIN_PASSWORD = "test-password"


def _local_asset_settings(
    cloud_engine: AsyncEngine,
    *,
    asset_root: Path,
) -> CloudSettings:
    return CloudSettings(
        DIRT_CLOUD_DATABASE_URL=str(cloud_engine.url),
        DIRT_CLOUD_ADMIN_USERNAME="admin",
        DIRT_CLOUD_ADMIN_PASSWORD_HASH=sha256_password_hash(ADMIN_PASSWORD),
        DIRT_CLOUD_SESSION_SECRET="test-session-secret-at-least-16",
        DIRT_CLOUD_SESSION_COOKIE_SECURE=False,
        DIRT_CLOUD_ASSET_STORE="local",
        DIRT_CLOUD_LOCAL_ASSET_ROOT=asset_root,
        DIRT_CLOUD_ASSET_PUBLIC_BASE_URL="http://test/api/dev-assets",
    )


async def test_local_asset_signed_url_serves_file_and_preserves_object_key(
    cloud_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    asset_root = tmp_path / "assets"
    object_key = "homebox/main/asset-1.jpg"
    asset_path = asset_root / "homebox" / "main" / "asset-1.jpg"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"local jpeg bytes")
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(
            CloudAsset(
                asset_id="asset-1",
                site_id="homebox",
                tent_id="main",
                object_key=object_key,
                content_type="image/jpeg",
                byte_size=16,
                captured_at=FIXED_NOW,
                uploaded_at=FIXED_NOW,
            )
        )
        await session.commit()

    settings = _local_asset_settings(cloud_engine, asset_root=asset_root)
    app = create_app(settings=settings, engine=cloud_engine, clock=lambda: FIXED_NOW)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert login.status_code == 200
        client.cookies = login.cookies

        signed = await client.get("/api/assets/asset-1/signed-url")
        assert signed.status_code == 200
        signed_url = signed.json()["signed_url"]
        assert signed_url.startswith(f"http://test/api/dev-assets/{object_key}?")
        assert "expires=" in signed_url
        assert "signature=" in signed_url

        loaded = await client.get(signed_url)
    await transport.aclose()

    assert loaded.status_code == 200
    assert loaded.content == b"local jpeg bytes"
    async with sessionmaker() as session:
        asset = await session.get(CloudAsset, "asset-1")
    assert asset is not None
    assert asset.object_key == object_key


async def test_local_asset_route_rejects_missing_expired_and_traversal(
    cloud_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    (tmp_path / "secret.txt").write_bytes(b"outside root")
    settings = _local_asset_settings(cloud_engine, asset_root=asset_root)
    app = create_app(settings=settings, engine=cloud_engine, clock=lambda: FIXED_NOW)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        missing_url = app.state.asset_store.presign_get(
            object_key="homebox/main/missing.jpg",
            expires_in_s=300,
        )
        expired_url = app.state.asset_store.presign_get(
            object_key="homebox/main/missing.jpg",
            expires_in_s=-1,
        )
        traversal_url = app.state.asset_store.presign_get(
            object_key="../secret.txt",
            expires_in_s=300,
        )

        missing = await client.get(missing_url)
        expired = await client.get(expired_url)
        traversal = await client.get(traversal_url)
    await transport.aclose()

    assert missing.status_code == 404
    assert expired.status_code == 403
    assert traversal.status_code in {403, 404}
    assert traversal.content != b"outside root"


async def test_local_asset_store_is_used_for_gateway_sign_upload(
    cloud_engine: AsyncEngine,
    gateway_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    asset_root = tmp_path / "assets"
    settings = _local_asset_settings(cloud_engine, asset_root=asset_root)
    app = create_app(settings=settings, engine=cloud_engine, clock=lambda: FIXED_NOW)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        response = await client.post(
            "/api/gateway/v1/assets/sign-upload",
            headers=gateway_headers,
            json={
                "site_id": "homebox",
                "tent_id": "main",
                "asset_id": "asset-1",
                "object_key": "homebox/main/asset-1.jpg",
                "content_type": "image/jpeg",
                "byte_size": 25_000_000,
                "sha256": "a" * 64,
            },
        )
        assert response.status_code == 200
        upload_url = response.json()["upload_url"]
        uploaded = await client.put(
            upload_url,
            content=b"uploaded through local store",
            headers={"Content-Type": "image/jpeg"},
        )
        get_url = app.state.asset_store.presign_get(
            object_key="homebox/main/asset-1.jpg",
            expires_in_s=300,
        )
        loaded = await client.get(get_url)
    await transport.aclose()

    assert upload_url.startswith("http://test/api/dev-assets/homebox/main/asset-1.jpg?")
    assert uploaded.status_code == 204
    assert loaded.status_code == 200
    assert loaded.content == b"uploaded through local store"
    assert (asset_root / "homebox" / "main" / "asset-1.jpg").read_bytes() == (
        b"uploaded through local store"
    )


async def test_local_asset_put_rejects_path_traversal(
    cloud_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"outside root")
    settings = _local_asset_settings(cloud_engine, asset_root=asset_root)
    app = create_app(settings=settings, engine=cloud_engine, clock=lambda: FIXED_NOW)
    traversal_url = app.state.asset_store.presign_put(
        object_key="../secret.txt",
        content_type="text/plain",
        expires_in_s=300,
    )
    parsed = urlsplit(traversal_url)
    traversal_url = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            "/api/dev-assets/%2E%2E/secret.txt",
            parsed.query,
            parsed.fragment,
        )
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        response = await client.put(
            traversal_url,
            content=b"overwritten",
            headers={"Content-Type": "text/plain"},
        )
    await transport.aclose()

    assert response.status_code in {403, 404}
    assert outside.read_bytes() == b"outside root"


async def test_local_retention_deletes_configured_store_files(
    cloud_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    asset_root = tmp_path / "assets"
    old_path = asset_root / "homebox" / "main" / "old.jpg"
    fresh_path = asset_root / "homebox" / "main" / "fresh.jpg"
    old_path.parent.mkdir(parents=True)
    old_path.write_bytes(b"old")
    fresh_path.write_bytes(b"fresh")
    sessionmaker = create_sessionmaker(cloud_engine)
    async with sessionmaker() as session:
        session.add(
            CloudSite(
                site_id="homebox",
                name="Homebox",
                timezone="UTC",
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        session.add(
            CloudAsset(
                asset_id="old-asset",
                site_id="homebox",
                tent_id="main",
                object_key="homebox/main/old.jpg",
                content_type="image/jpeg",
                byte_size=3,
                captured_at=FIXED_NOW.replace(year=2026, month=4, day=1),
                uploaded_at=FIXED_NOW.replace(year=2026, month=4, day=1),
            )
        )
        session.add(
            CloudAsset(
                asset_id="fresh-asset",
                site_id="homebox",
                tent_id="main",
                object_key="homebox/main/fresh.jpg",
                content_type="image/jpeg",
                byte_size=5,
                captured_at=FIXED_NOW,
                uploaded_at=FIXED_NOW,
            )
        )
        await session.commit()

    settings = _local_asset_settings(cloud_engine, asset_root=asset_root)
    app = create_app(settings=settings, engine=cloud_engine, clock=lambda: FIXED_NOW)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert login.status_code == 200
        client.cookies = login.cookies
        response = await client.post("/api/admin/assets/prune-expired")
    await transport.aclose()

    assert response.status_code == 200
    assert response.json()["matched"] == 1
    assert response.json()["objects_deleted"] == 1
    assert not old_path.exists()
    assert fresh_path.exists()
