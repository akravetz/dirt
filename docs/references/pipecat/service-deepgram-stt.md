---
title: DeepgramSTTService (Nova-3 streaming STT)
concept: pipecat
updated: 2026-04-17
source: src/pipecat/services/deepgram/stt.py
---

> Anchors agents to Pipecat v1.0.0 + deepgram-sdk v6. `LiveOptions` still works as a compatibility shim but is deprecated — use `settings=DeepgramSTTService.Settings(...)`.

# `DeepgramSTTService`

## Import

```python
from pipecat.services.deepgram.stt import DeepgramSTTService
```

## Minimal construction

```python
stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))
```

That's enough to get streaming Nova-3 English STT. Defaults are sensible: `model="nova-3-general"`, `language="en"`, `encoding="linear16"`, `channels=1`, `smart_format=True`, `interim_results=True`.

## Explicit configuration

```python
from pipecat.services.deepgram.stt import DeepgramSTTService

stt = DeepgramSTTService(
    api_key=os.getenv("DEEPGRAM_API_KEY"),
    sample_rate=16000,        # match your transport / VAD
    channels=1,
    encoding="linear16",
    settings=DeepgramSTTService.Settings(
        model="nova-3-general",
        language="en-US",
        smart_format=True,
        interim_results=True,
        punctuate=True,
        profanity_filter=False,
    ),
)
```

### Constructor parameters

Verified against `src/pipecat/services/deepgram/stt.py`:

| Param | Type | Default | Notes |
|---|---|---|---|
| `api_key` | `str` | — | Required. |
| `encoding` | `str` | `"linear16"` | Audio format sent to Deepgram. |
| `channels` | `int` | `1` | Mono is almost always right for voice. |
| `sample_rate` | `int \| None` | `None` (inherits) | If `None`, uses `PipelineParams.audio_in_sample_rate`. |
| `settings` | `DeepgramSTTService.Settings \| None` | `None` | Runtime-updatable options. |
| `live_options` | `LiveOptions \| None` | `None` | **Deprecated** (v0.0.105+); use `settings`. |
| `base_url` | `str` | `""` | Custom endpoint (self-hosted Deepgram). |
| `callback` | `str \| None` | `None` | Async delivery URL — not useful for streaming. |
| `tag` | `Any` | `None` | Custom billing tag. |

### `DeepgramSTTService.Settings` fields

Runtime-updatable. Common fields (mirrors Deepgram's `LiveOptions`):

```python
model: str               # "nova-3-general" (default), "nova-2-general", "nova-2-phonecall", "nova-2-meeting", etc.
language: str            # "en", "en-US", "es", "es-ES", ...
punctuate: bool
smart_format: bool
interim_results: bool    # True is usually right — aggregator deals with finalization
profanity_filter: bool
numerals: bool
dictation: bool
diarize: bool
multichannel: bool
keyterm: list[str]       # keyterm boosting (Nova-3)
keywords: list[str]      # legacy keyword boosting
utterance_end_ms: int    # ms of silence before UtteranceEnd event
endpointing: int | bool  # endpointing sensitivity
redact: list[str]        # ["pci", "ssn", "numbers"]
```

## Runtime updates

You can change the model/language live without rebuilding the service:

```python
await stt.update_settings(DeepgramSTTService.Settings(language="es"))
```

## Interaction with VAD

The `DeepgramSTTService` emits `VADUserStartedSpeakingFrame` / `VADUserStoppedSpeakingFrame` on its own (Deepgram's server-side endpointing) in addition to the client-side `SileroVADAnalyzer`. Both can coexist — Silero gates the user aggregator locally; Deepgram's events feed into turn tracking. You don't need to disable one.

## Sample-rate alignment

The sample rate flowing from `transport.input()` to `stt` is set by:
1. `DeepgramSTTService(sample_rate=...)` if provided (wins), else
2. `PipelineParams.audio_in_sample_rate` (default `16000`).

For a `LocalAudioTransport` it's usually easiest to leave `sample_rate=None` on the STT service and let `PipelineParams.audio_in_sample_rate=16000` drive everything. If your mic is hardware-locked to a different rate, set both to match.

## Common mistakes

| Training-data default | Correct in v1.0 |
|---|---|
| `DeepgramSTTService(api_key=..., live_options=LiveOptions(model="nova-3", language="en"))` | Use `settings=DeepgramSTTService.Settings(model="nova-3-general", language="en")`. |
| Passing `smart_format="true"` as a string | Use Python `bool`: `smart_format=True`. (Raw Deepgram websocket wants strings, but the SDK converts.) |
| Model name `"nova-3"` | Use `"nova-3-general"` (full name). `"nova-3"` will work via alias but full name is canonical. |
| Setting `model="general"` (old Deepgram naming) | Use the full name: `"nova-3-general"`, `"nova-2-general"`, etc. |
