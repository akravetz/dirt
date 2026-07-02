from __future__ import annotations

import httpx

from dirt_gateway.cloud import HttpCloudGatewayClient
from dirt_shared.cloud_contract import (
    CatalogRequest,
    CatalogSchedule,
    CatalogSite,
    CatalogTent,
    CatalogZone,
)


async def test_upload_asset_sends_file_bytes_with_async_client(tmp_path) -> None:
    asset_file = tmp_path / "snapshot.jpg"
    asset_file.write_bytes(b"jpeg-bytes")
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        seen["content_type"] = request.headers.get("content-type")
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://assets.test",
    ) as http_client:
        client = HttpCloudGatewayClient(
            base_url="https://api.test",
            gateway_token="token",
            http_client=http_client,
        )
        await client.upload_asset(
            file_path=asset_file,
            upload_url="https://assets.test/upload",
            headers={"Content-Type": "image/jpeg"},
            content_type="image/jpeg",
        )

    assert seen == {"body": b"jpeg-bytes", "content_type": "image/jpeg"}


async def test_catalog_request_omits_legacy_scope_fields() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        return httpx.Response(
            200,
            json={
                "sites": 1,
                "tents": 1,
                "zones": 1,
                "devices": 0,
                "capabilities": 0,
                "schedules": 1,
                "plant_lines": 0,
                "seed_lots": 0,
                "plants": 0,
                "sex_tests": 0,
                "plant_locations": 0,
                "cross_events": 0,
                "plant_notes": 0,
                "plant_events": 0,
                "plant_metric_streams": 0,
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.test",
    ) as http_client:
        client = HttpCloudGatewayClient(
            base_url="https://api.test",
            gateway_token="token",
            http_client=http_client,
        )
        await client.put_catalog(
            CatalogRequest(
                site_id="homebox",
                site=CatalogSite(source_site_id=1, name="Homebox"),
                tents=[
                    CatalogTent(
                        source_tent_id=1,
                        name="Main",
                        role="flower",
                    )
                ],
                zones=[
                    CatalogZone(
                        source_tent_id=1,
                        source_zone_id=10,
                        name="Canopy",
                    )
                ],
                schedules=[
                    CatalogSchedule(
                        source_site_id=1,
                        source_tent_id=1,
                        source_zone_id=10,
                        source_schedule_id=100,
                        starts_local="09:00",
                        ends_local="21:00",
                    )
                ],
                sex_tests=[],
            ),
            idempotency_key="catalog-key",
        )

    body = seen["body"]
    assert isinstance(body, bytes)
    assert b"legacy_tent_id" not in body
    assert b"legacy_zone_id" not in body
    assert b"legacy_schedule_id" not in body
