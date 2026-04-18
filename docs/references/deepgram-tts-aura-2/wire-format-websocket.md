---
title: Deepgram TTS WebSocket — Wire format
concept: deepgram-tts-aura-2
updated: 2026-04-17
source: https://developers.deepgram.com/docs/tts-websocket
---

> This file anchors agents to current Deepgram TTS WebSocket practice. Prefer what's written here over training-data recollection — streaming protocols are where training-data drift is worst.

# Deepgram TTS WebSocket — Wire format

## Connection

```
wss://api.deepgram.com/v1/speak?model=aura-2-thalia-en&encoding=linear16&sample_rate=24000
```

EU region: `wss://api.eu.deepgram.com/v1/speak`.

### Authentication

Send auth via a WebSocket `Authorization` header during the upgrade handshake:

```
Authorization: Token <YOUR_DEEPGRAM_API_KEY>
```

Bearer JWT auth is also accepted (`Authorization: Bearer <JWT>`). See [auth.md](auth.md). Browsers that cannot set custom headers on WebSockets must use a short-lived JWT via a `token` query parameter; use the Deepgram auth API to mint one.

### Query parameters

Same parameter names as REST, with the streaming-specific restriction that `encoding` must be one of `linear16`, `mulaw`, or `alaw`. Source: https://developers.deepgram.com/docs/tts-media-output-settings

- `model` — voice id (e.g. `aura-2-thalia-en`). Format `aura-2-<voice>-<lang>`.
- `encoding` — `linear16` | `mulaw` | `alaw`.
- `sample_rate` — matches the encoding's supported rates (e.g. `24000` for `linear16`).
- `container` — usually omit; for VoIP use `container=none`.

## Client → server messages (JSON, text frames)

All control messages are JSON objects with a `type` field. **Do not invent message types; only the four below exist.**

### Speak — feed text into the synth buffer

Source: https://developers.deepgram.com/docs/tts-websocket

```json
{
  "type": "Speak",
  "text": "Your text to transform to speech"
}
```

You may send multiple `Speak` messages back-to-back to stream text as the upstream LLM produces it. Audio will not start flowing until a `Flush` (or enough text to trigger an implicit flush).

### Flush — force the server to synthesize buffered text

Source: https://developers.deepgram.com/docs/tts-websocket

```json
{
  "type": "Flush"
}
```

After `Flush`, the server begins emitting binary audio frames followed by a `Flushed` JSON confirmation.

### Clear — cancel buffered text and in-flight audio (barge-in)

Source: https://developers.deepgram.com/docs/tts-ws-clear

```json
{
  "type": "Clear"
}
```

Use this for barge-in: when the user starts talking over the agent, send `Clear` to stop audio ASAP. Server replies with a `Cleared` confirmation.

### KeepAlive — prevent the 10-second idle timeout

Source: https://developers.deepgram.com/docs/audio-keep-alive

```json
{
  "type": "KeepAlive"
}
```

If no `Speak` or `KeepAlive` messages are sent within a **10-second window**, the connection closes with error `NET-0001`. Send `KeepAlive` every **3–5 seconds** during idle periods.

### Close — shut down cleanly

Source: https://developers.deepgram.com/docs/tts-ws-close

```json
{
  "type": "Close"
}
```

Server responds with WebSocket close frame `1000 Normal Closure`.

## Server → client messages

The server sends **two kinds of frames**:

1. **Binary frames** — raw audio bytes in the requested encoding. No envelope, no base64 (the web/JS SDK may expose base64-encoded strings for convenience, but the raw WebSocket frame is binary). Pipe these to your audio sink.
2. **JSON text frames** — control/status messages with a `type` field.

### JSON message types

Source: https://developers.deepgram.com/docs/tts-websocket, https://developers.deepgram.com/docs/tts-ws-clear

| `type` | When | Shape |
|---|---|---|
| `Metadata` | Immediately after connect | `{"type": "Metadata", "request_id": "...", ...}` |
| `Flushed` | After a `Flush` finishes emitting audio | `{"type": "Flushed", "sequence_id": <int>}` |
| `Cleared` | After a `Clear` takes effect | `{"type": "Cleared", "sequence_id": <int>}` |
| `Warning` | Non-fatal issue | `{"type": "Warning", "description": "...", "code": "..."}` |

Use `sequence_id` to correlate `Flushed` / `Cleared` with the originating client action.

## End-to-end flow

```
client → server:  {"type": "Speak", "text": "Hello, how can I help you today?"}
client → server:  {"type": "Flush"}
server → client:  {"type": "Metadata", "request_id": "..."}
server → client:  <binary audio frame>
server → client:  <binary audio frame>
...
server → client:  {"type": "Flushed", "sequence_id": 0}
client → server:  {"type": "KeepAlive"}   (every 3-5s while idle)
...
client → server:  {"type": "Close"}
server → client:  close 1000
```

## Python SDK (streaming)

Source: https://github.com/deepgram/deepgram-python-sdk

```python
from deepgram import DeepgramClient, SpeakWebSocketEvents, SpeakWSOptions

client = DeepgramClient()
dg = client.speak.websocket.v("1")

def on_binary_data(self, data, **kwargs):
    # data: bytes, raw PCM in the requested encoding
    audio_sink.write(data)

def on_flushed(self, flushed, **kwargs):
    print(f"flushed seq={flushed.sequence_id}")

dg.on(SpeakWebSocketEvents.AudioData, on_binary_data)
dg.on(SpeakWebSocketEvents.Flushed, on_flushed)

options = SpeakWSOptions(
    model="aura-2-thalia-en",
    encoding="linear16",
    sample_rate=24000,
)
dg.start(options)

dg.send_text("Hello, how can I help you today?")
dg.flush()
# ... later, on barge-in:
# dg.clear()
# ... on shutdown:
dg.finish()
```

## Common mistakes

- Using message type `"chunk"`, `"partial"`, `"delta"`, or `"tts"` — none exist. Client types are exactly `Speak` | `Flush` | `Clear` | `KeepAlive` | `Close`.
- Putting `text` under a different key (e.g. `"content"`, `"input"`, `"prompt"`). The field is `text`, at the top level of the `Speak` message.
- Expecting server audio as JSON/base64 on the raw WebSocket — the raw frames are **binary**. SDKs may wrap this.
- Omitting `KeepAlive` during idle — the socket closes after 10 seconds of silence with `NET-0001`.
- Requesting `encoding=mp3` / `opus` / `flac` / `aac` on WebSocket — streaming only supports `linear16`, `mulaw`, `alaw`. Use REST for compressed formats.
- Using `Flush` before sending any `Speak` — harmless but emits nothing; you still need text in the buffer.
- Confusing `Clear` with `Close`. `Clear` cancels current audio and keeps the socket open for the next utterance (barge-in). `Close` tears the socket down.
