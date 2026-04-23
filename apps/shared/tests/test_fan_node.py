"""Tests for the fan-controller HTTP client.

Uses httpx.MockTransport — no monkeypatching, no real network.
"""

from __future__ import annotations

import httpx
import pytest

from dirt_shared.services.fan_node import FanNodeClient, FanNodeError


def _make_client(handler) -> FanNodeClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return FanNodeClient(http, base_url="http://fan-controller.local")


async def test_set_duty_posts_json_and_returns_acknowledged_value():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"duty_pct": 55})

    client = _make_client(handler)
    ack = await client.set_duty(55)

    assert ack == 55
    assert seen["method"] == "POST"
    assert seen["url"] == "http://fan-controller.local/fan"
    import json as _json

    assert _json.loads(seen["body"]) == {"duty_pct": 55}


async def test_set_duty_rejects_out_of_range():
    client = _make_client(lambda _req: httpx.Response(200, json={"duty_pct": 0}))
    with pytest.raises(ValueError, match=r"duty_pct"):
        await client.set_duty(-1)
    with pytest.raises(ValueError, match=r"duty_pct"):
        await client.set_duty(101)


async def test_set_duty_accepts_boundary_values():
    acks: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        # Mirror back the requested value so we can check both ends.
        import json as _json

        acks.append(_json.loads(body)["duty_pct"])
        return httpx.Response(200, json={"duty_pct": acks[-1]})

    client = _make_client(handler)
    assert await client.set_duty(0) == 0
    assert await client.set_duty(100) == 100
    assert acks == [0, 100]


async def test_get_state_returns_set_and_reported_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "http://fan-controller.local/fan"
        return httpx.Response(
            200,
            json={"set_duty_pct": 42, "reported_duty_pct": 42},
        )

    client = _make_client(handler)
    state = await client.get_state()
    assert state == {"set_duty_pct": 42, "reported_duty_pct": 42}


async def test_http_error_status_raises_fan_node_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text='{"error":"bad duty"}')

    client = _make_client(handler)
    with pytest.raises(FanNodeError, match="HTTP 400"):
        await client.set_duty(50)


async def test_transport_error_raises_fan_node_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope")

    client = _make_client(handler)
    with pytest.raises(FanNodeError, match="transport error"):
        await client.get_state()


async def test_non_json_body_raises_fan_node_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = _make_client(handler)
    with pytest.raises(FanNodeError, match="non-JSON"):
        await client.get_state()


async def test_base_url_trailing_slash_is_stripped():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"duty_pct": 10})

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    client = FanNodeClient(http, base_url="http://fan-controller.local/")
    await client.set_duty(10)
    assert seen["url"] == "http://fan-controller.local/fan"
