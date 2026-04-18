---
title: Deepgram TTS errors and rate limits
concept: deepgram-tts-aura-2
updated: 2026-04-17
source: https://developers.deepgram.com/docs/errors
---

> This file anchors agents to current Deepgram error-handling practice. Prefer what's written here over training-data recollection.

# Errors and rate limits

## HTTP status codes

Source: https://developers.deepgram.com/docs/errors

Deepgram returns: `400`, `401`, `402`, `403`, `404`, `408`, `411`, `413`, `414`, `429`, `499`, `500`, `502`, `503`, `504`.

| Code | Meaning | Retryable? |
|---|---|---|
| `400` | Bad request (malformed body, invalid query param, unknown `model`) | No — fix and resend |
| `401` | Auth failed (missing/invalid `Authorization: Token` header) | No |
| `402` | Payment required / plan limit | No |
| `403` | Forbidden (project disabled, model not on plan) | No |
| `404` | Wrong endpoint path | No |
| `408` / `499` | Request timeout / client closed | Yes |
| `413` / `414` | Payload / URL too long | No — chunk the text |
| `429` | Rate limit hit (concurrency exceeded) | Yes — exponential backoff |
| `500` / `502` / `503` / `504` | Server error | Yes — exponential backoff |

Retryable errors (`408`, `500`, `502`, `503`, `504`, `429`) "may succeed if retried" per Deepgram's guidance — wrap retries in exponential backoff with jitter.

## Error response body

```json
{
  "err_code": "ERROR_CODE",
  "err_msg": "Human readable message",
  "request_id": "uuid"
}
```

Some responses also include `category` and `details`. Always log `request_id` — Deepgram support will ask for it.

Source: https://developers.deepgram.com/docs/errors

## Rate limits (concurrency-based)

Deepgram rate-limits by **concurrent requests/connections**, not requests-per-minute. Source: https://developers.deepgram.com/reference/api-rate-limits

### Pay as You Go

| Surface | Concurrency |
|---|---|
| TTS REST (Aura / Aura-2) | **15 concurrent requests** |
| TTS WebSocket streaming (Aura / Aura-2) | **45 concurrent connections** |
| Voice Agent | 45 concurrent connections |
| Speech-to-Text streaming | 150 concurrent requests |

### Growth

| Surface | NA / EU |
|---|---|
| TTS WebSocket streaming | 60 / 45 concurrent |
| Voice Agent | 60 / 45 concurrent |

### Enterprise

Customizable, starting from 25–150+ concurrent TTS.

## 429 handling

For `429` specifically, Deepgram recommends "an exponential-backoff retry strategy ... to accommodate rate-limiting when submitting a large volume of concurrent requests." Source: https://developers.deepgram.com/docs/errors

Reasonable defaults for a voice agent:

- First retry: 250 ms
- Double up to a cap (e.g. 8 s)
- Add jitter (`delay * random(0.5, 1.5)`)
- Max 5 attempts; after that, surface the failure
- Keep a per-request-id log so repeat 429s on the same utterance aren't retried forever

If 429s are chronic, raise the plan tier or split traffic across NA and EU endpoints — they have separate concurrency budgets.

## WebSocket-specific errors

- `NET-0001` — idle timeout (>10 s of silence). Fix: send `{"type":"KeepAlive"}` every 3–5 s. See [wire-format-websocket.md](wire-format-websocket.md).
- A `Warning` JSON frame (`{"type":"Warning","description":"...","code":"..."}`) is non-fatal — log and continue.

## Common mistakes

- Treating 429 as fatal. It's retryable — back off and retry.
- Polling for rate-limit headers. Deepgram's public docs don't surface an `X-RateLimit-*` header set with remaining-quota numbers — use success/429 signals and concurrency accounting on the client side.
- Retrying 4xx errors other than 408/429 — those require a request fix, not a retry.
- Not logging `request_id` — makes Deepgram support triage impossible.
