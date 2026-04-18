---
title: Deepgram auth
concept: deepgram-tts-aura-2
updated: 2026-04-17
source: https://developers.deepgram.com/reference/deepgram-api-overview
---

> This file anchors agents to current Deepgram auth practice. Prefer what's written here over training-data recollection.

# Deepgram auth

## API key (server-side, default)

Include this header on every REST call and on the WebSocket upgrade handshake:

```
Authorization: Token <YOUR_DEEPGRAM_API_KEY>
```

**Critical:** the scheme is `Token`, not `Bearer`. Training data routinely writes `Authorization: Bearer <API_KEY>` — that is wrong for raw API keys and will 401.

Source: https://developers.deepgram.com/reference/deepgram-api-overview

## Short-lived JWT (Bearer)

Deepgram supports ephemeral Bearer JWTs for browser/client-side code that cannot safely hold a long-lived API key. Mint one from the auth API using your API key, then send it as:

```
Authorization: Bearer <JWT>
```

For WebSockets from browsers (where custom headers on WebSocket connections aren't possible), pass the JWT as a `token` query parameter on the connection URL.

## Base URLs by region

Source: https://developers.deepgram.com/reference/api-rate-limits

| Region | REST base | WebSocket base |
|---|---|---|
| North America (default) | `https://api.deepgram.com` | `wss://api.deepgram.com` |
| Europe | `https://api.eu.deepgram.com` | `wss://api.eu.deepgram.com` |

Rate limits differ per region — pick the region closest to the caller to avoid cross-region latency, then set concurrency accordingly.

## Key hygiene

- Store `DEEPGRAM_API_KEY` in environment / secret manager. Never commit.
- The SDKs read `DEEPGRAM_API_KEY` from the environment if no key is passed to the client constructor.
- Rotate via the Deepgram console; there is no in-place key rotation endpoint required for client code.

## Common mistakes

- `Authorization: Bearer <API_KEY>` — wrong scheme for raw keys; use `Token`.
- `X-API-Key: ...` — not a Deepgram header; only `Authorization` is recognized.
- Passing the API key as `?api_key=...` in the query string — not supported.
- Assuming the EU endpoint is a drop-in alias — it's a separate deployment with its own concurrency budget.
