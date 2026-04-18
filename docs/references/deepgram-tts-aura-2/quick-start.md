---
title: Deepgram TTS quick-start
concept: deepgram-tts-aura-2
updated: 2026-04-17
source: https://developers.deepgram.com/docs/text-to-speech
---

> This file anchors agents to current Deepgram TTS practice. Prefer what's written here over training-data recollection.

# Quick start

Minimum viable code for the two surfaces the voice agent will use. Both are copy-pasteable.

## 1. REST: text → mp3 file (curl)

```bash
export DEEPGRAM_API_KEY="your-key-here"

curl --request POST \
     --header "Content-Type: application/json" \
     --header "Authorization: Token $DEEPGRAM_API_KEY" \
     --output hello.mp3 \
     --data '{"text":"Hello, how can I help you today?"}' \
     --url "https://api.deepgram.com/v1/speak?model=aura-2-thalia-en"
```

What to notice:

- `model` is in the **URL query string**, not the JSON.
- The JSON body has exactly one key: `text`.
- `--output` writes the raw audio bytes to disk. The response body is binary audio, not JSON.

Source: https://developers.deepgram.com/docs/text-to-speech

## 2. REST: text → audio (Python SDK)

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

Source: https://github.com/deepgram/deepgram-python-sdk

## 3. WebSocket: streaming synth with barge-in (Python SDK)

```python
from deepgram import DeepgramClient, SpeakWebSocketEvents, SpeakWSOptions

client = DeepgramClient()
dg = client.speak.websocket.v("1")

def on_audio(self, data, **kwargs):
    # `data` is raw PCM bytes in the requested encoding.
    audio_sink.write(data)

def on_flushed(self, flushed, **kwargs):
    print("server flushed sequence", flushed.sequence_id)

dg.on(SpeakWebSocketEvents.AudioData, on_audio)
dg.on(SpeakWebSocketEvents.Flushed, on_flushed)

options = SpeakWSOptions(
    model="aura-2-thalia-en",
    encoding="linear16",
    sample_rate=24000,
)
dg.start(options)

# Stream text as the LLM produces it:
for chunk in llm_stream:
    dg.send_text(chunk)
dg.flush()               # tell the server to emit audio for what we've sent

# On user barge-in:
# dg.clear()             # cancels buffered + in-flight audio

# At shutdown:
dg.finish()              # sends {"type":"Close"} and closes the socket
```

Source: https://developers.deepgram.com/docs/tts-websocket, https://github.com/deepgram/deepgram-python-sdk

## 4. WebSocket: lower-level (no SDK)

```python
import asyncio, json, os, websockets

URL = (
    "wss://api.deepgram.com/v1/speak"
    "?model=aura-2-thalia-en"
    "&encoding=linear16"
    "&sample_rate=24000"
)
HEADERS = {"Authorization": f"Token {os.environ['DEEPGRAM_API_KEY']}"}

async def synth(text: str):
    async with websockets.connect(URL, additional_headers=HEADERS) as ws:
        await ws.send(json.dumps({"type": "Speak", "text": text}))
        await ws.send(json.dumps({"type": "Flush"}))

        async for frame in ws:
            if isinstance(frame, bytes):
                audio_sink.write(frame)
            else:
                msg = json.loads(frame)
                if msg.get("type") == "Flushed":
                    break  # one-shot: done

        await ws.send(json.dumps({"type": "Close"}))

asyncio.run(synth("Hello, how can I help you today?"))
```

Remember: during idle periods send `{"type":"KeepAlive"}` every 3-5 s or the server closes the socket with `NET-0001`.

## Checklist before first PR

- [ ] `DEEPGRAM_API_KEY` in env (or the service's secret manager).
- [ ] Auth header is `Authorization: Token <key>`. Not `Bearer`. (See [auth.md](auth.md).)
- [ ] `model` is in the query string. Not a JSON body field.
- [ ] Body is `{"text": "..."}` — no `voice`, `voice_id`, `voice_name`.
- [ ] Encoding matches the surface: REST can use mp3/opus/flac/aac; WebSocket only `linear16`/`mulaw`/`alaw`.
- [ ] Retry logic handles 429/5xx with exponential backoff (see [errors-and-rate-limits.md](errors-and-rate-limits.md)).
- [ ] WebSocket code sends `KeepAlive` while idle.
- [ ] WebSocket code handles `Clear` / `Cleared` for barge-in if the agent allows interruption.
