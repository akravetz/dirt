"""Generic Telegram Bot API client.

Outbound-only for V1 (used by the daily report). Designed so the future
inbound channel can layer `get_updates` / `set_webhook` onto the same module
without restructuring.

Take an `httpx.AsyncClient` and a bot token at construction time so callers
can swap the transport (real network vs `httpx.MockTransport` in tests)
without monkeypatching.
"""

from __future__ import annotations

import json
import mimetypes
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

API_BASE = "https://api.telegram.org"

# Bot API limits (source: core.telegram.org/bots/api).
# sendMessage body hard cap is 4096 chars; the 50-char margin covers any
# delivery wrapper text and rounding in the sub-agent's character counter.
TELEGRAM_MAX_MESSAGE_CHARS = 4046

# Tag names Telegram's HTML parser accepts. The Bot API's HTML mode
# whitelist — anything outside this set is rejected at sendMessage time.
TELEGRAM_HTML_WHITELIST = (
    "b",
    "i",
    "u",
    "s",
    "code",
    "pre",
    "a",
    "blockquote",
)


class TelegramError(RuntimeError):
    """Raised on non-OK Bot API responses or transport failures."""


class TelegramClient:
    def __init__(self, token: str, http: httpx.AsyncClient) -> None:
        if not token:
            raise ValueError("telegram bot token is required")
        self._token = token
        self._http = http

    def _url(self, method: str) -> str:
        return f"{API_BASE}/bot{self._token}/{method}"

    async def _post(
        self,
        method: str,
        *,
        data: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        try:
            r = await self._http.post(self._url(method), data=data, files=files)
        except httpx.HTTPError as e:
            raise TelegramError(f"transport error calling {method}: {e}") from e
        try:
            body = r.json()
        except json.JSONDecodeError as e:
            raise TelegramError(
                f"non-json response from {method} (status={r.status_code}): "
                f"{r.text[:200]!r}"
            ) from e
        if not body.get("ok"):
            raise TelegramError(
                f"{method} failed: status={r.status_code} "
                f"description={body.get('description')!r}"
            )
        return body.get("result", {})

    async def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: str | None = "HTML",
        disable_web_page_preview: bool = True,
    ) -> dict[str, Any]:
        """Send a single text message. HTML mode escapes only `< > &`,
        which is much friendlier than MarkdownV2's full punctuation list."""
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true" if disable_web_page_preview else "false",
        }
        if parse_mode is not None:
            data["parse_mode"] = parse_mode
        return await self._post("sendMessage", data=data)

    async def send_media_group(
        self,
        chat_id: str,
        photo_paths: Sequence[Path],
        *,
        caption: str | None = None,
        caption_parse_mode: str | None = "HTML",
    ) -> list[dict[str, Any]]:
        """Send a photo album (2-10 photos as one group). The caption,
        if given, attaches to the first photo only — the Bot API does not
        support per-album captions, only per-photo. Photos are uploaded as
        multipart attachments referenced via `attach://` in the media spec.
        """
        if not photo_paths:
            raise ValueError("photo_paths must contain at least one path")
        if len(photo_paths) > 10:
            raise ValueError(
                f"telegram albums support max 10 photos, got {len(photo_paths)}"
            )

        media: list[dict[str, Any]] = []
        files: dict[str, tuple[str, bytes, str]] = {}
        for i, p in enumerate(photo_paths):
            attach_name = f"photo{i}"
            mime = mimetypes.guess_type(str(p))[0] or "image/jpeg"
            files[attach_name] = (p.name, p.read_bytes(), mime)
            entry: dict[str, Any] = {
                "type": "photo",
                "media": f"attach://{attach_name}",
            }
            if i == 0 and caption is not None:
                entry["caption"] = caption
                if caption_parse_mode is not None:
                    entry["parse_mode"] = caption_parse_mode
            media.append(entry)

        data = {"chat_id": chat_id, "media": json.dumps(media)}
        result = await self._post("sendMediaGroup", data=data, files=files)
        # sendMediaGroup returns a list of message objects.
        return result if isinstance(result, list) else [result]
