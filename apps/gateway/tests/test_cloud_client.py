from __future__ import annotations

import httpx

from dirt_gateway.cloud import HttpCloudGatewayClient


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
