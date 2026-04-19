"""Tests for the Telegram Bot API client.

Uses httpx.MockTransport — no monkeypatching, no real network. The client
takes its httpx.AsyncClient by injection so tests can swap the transport
without touching module globals.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from dirt.services.telegram import TelegramClient, TelegramError


def _ok(result: object) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "result": result})


def _err(status: int, description: str) -> httpx.Response:
    return httpx.Response(status, json={"ok": False, "description": description})


def _make_client(handler) -> TelegramClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return TelegramClient(token="TEST_TOKEN", http=http)


async def test_send_message_posts_correct_payload():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return _ok({"message_id": 42})

    client = _make_client(handler)
    result = await client.send_message("12345", "hello <world>", parse_mode="HTML")

    assert result == {"message_id": 42}
    assert seen["url"] == "https://api.telegram.org/botTEST_TOKEN/sendMessage"
    body = seen["body"].decode()
    assert "chat_id=12345" in body
    # httpx URL-encodes the form fields
    assert "hello+%3Cworld%3E" in body or "hello%20%3Cworld%3E" in body
    assert "parse_mode=HTML" in body
    assert "disable_web_page_preview=true" in body


async def test_send_message_omits_parse_mode_when_none():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return _ok({"message_id": 1})

    client = _make_client(handler)
    await client.send_message("12345", "plain text", parse_mode=None)
    assert "parse_mode" not in seen["body"]


async def test_send_message_raises_on_api_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return _err(400, "Bad Request: chat not found")

    client = _make_client(handler)
    with pytest.raises(TelegramError, match="chat not found"):
        await client.send_message("0", "x")


async def test_send_message_raises_on_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope")

    client = _make_client(handler)
    with pytest.raises(TelegramError, match="transport error"):
        await client.send_message("12345", "x")


async def test_send_message_raises_on_non_json_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>oops</html>")

    client = _make_client(handler)
    with pytest.raises(TelegramError, match="non-json response"):
        await client.send_message("12345", "x")


async def test_send_media_group_uploads_photos_and_captions_first(tmp_path: Path):
    # Two minimal JPEGs (SOI+EOI is enough for telegram to accept; we don't
    # actually round-trip through telegram in this test — we assert the
    # multipart request shape).
    p1 = tmp_path / "overview.jpg"
    p1.write_bytes(b"\xff\xd8\xff\xd9aaa")
    p2 = tmp_path / "plant-a.jpg"
    p2.write_bytes(b"\xff\xd8\xff\xd9bbb")

    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["content_type"] = request.headers.get("content-type", "")
        seen["body"] = request.read()
        return _ok([{"message_id": 100}, {"message_id": 101}])

    client = _make_client(handler)
    result = await client.send_media_group(
        "12345", [p1, p2], caption="<b>Daily Report</b>"
    )

    assert result == [{"message_id": 100}, {"message_id": 101}]
    assert "sendMediaGroup" in seen["url"]
    assert seen["content_type"].startswith("multipart/form-data")

    body = seen["body"].decode("latin-1")  # binary-safe
    # chat_id form field present
    assert 'name="chat_id"' in body and "12345" in body
    # media JSON references the two attachments
    assert 'name="media"' in body
    media_json_start = body.index('name="media"')
    media_section = body[media_json_start : media_json_start + 1000]
    assert "attach://photo0" in media_section
    assert "attach://photo1" in media_section
    # caption only on the first photo
    media_decoded = json.loads(
        media_section.split("\r\n\r\n", 1)[1].split("\r\n", 1)[0]
    )
    assert media_decoded[0].get("caption") == "<b>Daily Report</b>"
    assert "caption" not in media_decoded[1]
    # both files attached
    assert 'name="photo0"' in body and "overview.jpg" in body
    assert 'name="photo1"' in body and "plant-a.jpg" in body


async def test_send_media_group_rejects_too_many_or_zero_photos(tmp_path: Path):
    client = _make_client(lambda r: _ok([]))
    with pytest.raises(ValueError, match="at least one"):
        await client.send_media_group("12345", [])
    too_many = []
    for i in range(11):
        p = tmp_path / f"p{i}.jpg"
        p.write_bytes(b"\xff\xd8\xff\xd9")
        too_many.append(p)
    with pytest.raises(ValueError, match="max 10 photos"):
        await client.send_media_group("12345", too_many)


def test_constructor_rejects_empty_token():
    http = httpx.AsyncClient()
    with pytest.raises(ValueError, match="token is required"):
        TelegramClient(token="", http=http)
