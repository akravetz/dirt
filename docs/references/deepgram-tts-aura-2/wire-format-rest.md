---
title: Deepgram TTS REST — Wire format
concept: deepgram-tts-aura-2
updated: 2026-04-17
source: https://developers.deepgram.com/docs/text-to-speech
---

> This file anchors agents to current Deepgram TTS practice. Prefer what's written here over training-data recollection — training data commonly lags the current version and hallucinates field names for this API.

# Deepgram TTS REST — Wire format

## Endpoint

```
POST https://api.deepgram.com/v1/speak
```

For EU traffic, swap to `https://api.eu.deepgram.com/v1/speak` (see [auth.md](auth.md)).

## Headers

```
Authorization: Token <YOUR_DEEPGRAM_API_KEY>
Content-Type: application/json
```

Source: https://developers.deepgram.com/docs/text-to-speech

## Request body

**The body contains exactly one required field: `text`.** Nothing else goes in the body. Voice selection, encoding, sample rate, etc. all go in the **query string**, not the body.

```json
{
  "text": "Hello, how can I help you today?"
}
```

## Query parameters

Everything that configures the synthesis is a query parameter on the URL, not a JSON field.

Source: https://developers.deepgram.com/docs/tts-media-output-settings

| Param | Required | Notes |
|---|---|---|
| `model` | No (defaults to an Aura model) | **Voice selector.** Format `aura-2-<voice>-<lang>` (e.g. `aura-2-thalia-en`, `aura-2-zeus-en`). Aura-1 names like `aura-asteria-en` still work. Full list: [voice-models.md](voice-models.md). |
| `encoding` | No (default `mp3`) | One of `linear16`, `mulaw`, `alaw`, `mp3`, `opus`, `flac`, `aac`. |
| `container` | No | `wav` or `none` for `linear16`/`mulaw`/`alaw`; `ogg` for `opus` (defaults shown in table below). |
| `sample_rate` | No (depends on encoding) | See combinations table. |
| `bit_rate` | No (mp3/opus/aac only) | mp3 default `48000`; opus default `12000` (range 4000–650000); aac default `48000` (range 4000–192000). |
| `callback` | No | Webhook URL for async delivery. |

### Audio format combinations (verbatim from docs)

Source: https://developers.deepgram.com/docs/tts-media-output-settings

| Encoding | Container | Sample Rate (Hz) | Bit rate (bps) |
|---|---|---|---|
| `linear16` | `wav` (default), `none` | `8000`, `16000`, `24000` (default), `32000`, `48000` | N/A |
| `mulaw` | `wav` (default), `none` | `8000` (default), `16000` | N/A |
| `alaw` | `wav` (default), `none` | `8000` (default), `16000` | N/A |
| `mp3` (default encoding) | N/A | Fixed at `22050` | `32000`, `48000` (default) |
| `opus` | `ogg` (default) | Fixed at `48000` | Default `12000`, range `>=4000` and `<=650000` |
| `flac` | N/A | `8000`, `16000`, `22050`, `32000`, `48000` | N/A |
| `aac` | N/A | Fixed at `22050` | Default `48000`, range `>=4000` and `<=192000` |

Note: Streaming (WebSocket) only supports `linear16`, `mulaw`, and `alaw`. The others are REST-only.

## Response

- **Success (2xx):** Body is the raw binary audio (the MIME/container matches the requested `encoding`/`container`). Stream it directly to a file or audio sink.
- **Error (4xx/5xx):** JSON body `{"err_code": "...", "err_msg": "...", "request_id": "..."}`. See [errors-and-rate-limits.md](errors-and-rate-limits.md).

## Complete curl example

Source: https://developers.deepgram.com/docs/text-to-speech

```bash
curl --request POST \
     --header "Content-Type: application/json" \
     --header "Authorization: Token $DEEPGRAM_API_KEY" \
     --output hello.mp3 \
     --data '{"text":"Hello, how can I help you today?"}' \
     --url "https://api.deepgram.com/v1/speak?model=aura-2-thalia-en"
```

## Complete Python SDK example

Source: https://github.com/deepgram/deepgram-python-sdk

```python
from deepgram import DeepgramClient, SpeakOptions

client = DeepgramClient()  # reads DEEPGRAM_API_KEY from env

options = SpeakOptions(
    model="aura-2-thalia-en",
    encoding="linear16",
    container="wav",
    sample_rate=24000,
)

response = client.speak.rest.v("1").stream_memory(
    {"text": "Hello, how can I help you today?"},
    options,
)

with open("hello.wav", "wb") as f:
    f.write(response.stream_memory.getvalue())
```

Notes:
- The SDK accepts the same parameter names as the REST query string (`model`, `encoding`, `container`, `sample_rate`, `bit_rate`).
- The input dict passed in has exactly one key: `text`. There is no `voice`, `voice_id`, or `voice_name` option anywhere.

## Complete JavaScript SDK example

Source: https://developers.deepgram.com/docs/text-to-speech

```javascript
const { createClient } = require("@deepgram/sdk");
const deepgram = createClient(process.env.DEEPGRAM_API_KEY);

const response = await deepgram.speak.request(
  { text: "Hello, how can I help you today?" },
  {
    model: "aura-2-thalia-en",
    encoding: "linear16",
    container: "wav",
  },
);

const stream = await response.getStream();
// pipe stream to a file / audio sink
```

## Common mistakes

Training data defaults that are **wrong** — do not write any of these:

- `{"voice_id": "aura-2-thalia-en", "text": "..."}` — `voice_id` is **not a Deepgram field at any layer**. The correct place is `?model=aura-2-thalia-en` in the query string.
- `{"voice": {"name": "aura-2-thalia-en"}, "text": "..."}` — Deepgram has no nested `voice` object. This pattern is from OpenAI / Google Cloud TTS.
- `{"model": "aura-2-thalia-en", "text": "..."}` — Wrong location. `model` is a **query parameter**, not a body field. Putting it in the body is silently ignored; the server picks the default model.
- `POST /v1/tts` or `POST /v1/generate` or `POST /v1/synthesize` — the endpoint is `/v1/speak`.
- `Authorization: Bearer <API_KEY>` with a raw API key — must be `Authorization: Token <API_KEY>`. `Bearer` is reserved for short-lived JWTs obtained from the auth API. See [auth.md](auth.md).
- Specifying `voice` or `voice_name` as top-level SDK options — the SDK option is `model`, matching the query param.
- Assuming the response is JSON — the 2xx body is raw audio bytes. Stream/write it binary-safe.
