---
title: Deepgram TTS (Aura-2) Reference Pack
concept: deepgram-tts-aura-2
mode: api
version: Aura-2 (current generation as of 2026-04-17)
updated: 2026-04-17
---

# Deepgram TTS (Aura-2)

This pack covers Deepgram's current-generation text-to-speech API, which uses the **Aura-2** voice family over the `v1/speak` REST and WebSocket endpoints. There is no "Aura v3" or "Deepgram TTS v3" product — Deepgram versioned the **voice models** (Aura → Aura-2), not the API surface, which remains `v1`. Training data frequently hallucinates field names and request shapes for this API; this pack is authoritative.

## When to consult this pack

Read this INDEX first (and the relevant topic files below) before writing any code that calls Deepgram TTS — synthesizing audio, configuring the voice agent's speech output, opening a streaming socket, picking a voice/model id, or handling Deepgram auth. Prefer what's in this pack over recollection. Training data commonly suggests field names like `voice_id`, `voice.name`, or body field `model` — none of those are correct for Deepgram.

## Topics

- **[Wire format — REST](wire-format-rest.md)** — Exact POST `/v1/speak` request: endpoint, query params (`model`, `encoding`, `container`, `sample_rate`, `bit_rate`), the one-field JSON body (`{"text": "..."}`), response headers, and full curl + SDK examples. Read first.
- **[Wire format — WebSocket streaming](wire-format-websocket.md)** — Streaming `wss://api.deepgram.com/v1/speak` protocol: connection query params, all client message types (`Speak`, `Flush`, `Clear`, `Close`, `KeepAlive`), server messages (`Metadata`, `Flushed`, `Cleared`, `Warning`), and how binary audio frames are delivered.
- **[Auth](auth.md)** — `Authorization: Token ...` header format, short-lived JWT Bearer tokens, regional base URLs (`api.deepgram.com` vs `api.eu.deepgram.com`).
- **[Voice models](voice-models.md)** — Full enum of valid `model` values, naming convention (`aura-2-<voice>-<lang>`), default behavior, and Aura-1 → Aura-2 migration notes.
- **[Errors and rate limits](errors-and-rate-limits.md)** — HTTP status codes, error JSON shape, 429 backoff guidance, and concurrency caps by plan tier (TTS REST = 15 concurrent on PAYG, streaming = 45).
- **[Quick start](quick-start.md)** — Minimal runnable Python and curl examples for both REST (text → mp3 file) and WebSocket (text → streamed PCM).

## Version-specific warnings

Training data will confidently suggest any of the following — **all are wrong**:

- `voice_id` as a request field. **Not a Deepgram field at any layer.** See [wire-format-rest.md](wire-format-rest.md).
- `voice` as a nested object (e.g. `{"voice": {"name": "..."}}`). **Does not exist.** Deepgram has no `voice.*` key.
- `model` inside the JSON body. **Wrong location.** `model` is a **query-string parameter** on the URL (e.g. `?model=aura-2-thalia-en`), not a body field. The body contains only `{"text": "..."}`.
- `aura-asteria-en` as the only model. Aura-1 still works but Aura-2 (`aura-2-*-*`) is the current generation — prefer it. See [voice-models.md](voice-models.md).
- WebSocket message type `"chunk"` or `"partial"`. Wrong — client sends `{"type":"Speak"}`, server emits binary audio + JSON control frames like `{"type":"Metadata"}` / `{"type":"Flushed"}`. See [wire-format-websocket.md](wire-format-websocket.md).
- Endpoint paths `/v1/tts`, `/v1/generate`, `/v1/synthesize`. Wrong — the endpoint is `/v1/speak` for both REST and WebSocket.

## Sources

- https://developers.deepgram.com/docs/text-to-speech — REST getting started
- https://developers.deepgram.com/docs/tts-rest — REST feature docs
- https://developers.deepgram.com/docs/tts-websocket — WebSocket streaming overview
- https://developers.deepgram.com/docs/tts-models — Voice model catalog
- https://developers.deepgram.com/docs/tts-media-output-settings — Audio format combinations
- https://developers.deepgram.com/docs/tts-ws-clear — Clear control message
- https://developers.deepgram.com/docs/tts-ws-close — Close control message
- https://developers.deepgram.com/docs/audio-keep-alive — KeepAlive message
- https://developers.deepgram.com/docs/errors — Error codes and retry guidance
- https://developers.deepgram.com/reference/api-rate-limits — Concurrency limits
- https://github.com/deepgram/deepgram-python-sdk — Official Python SDK
