---
title: ElevenLabsTTSService (WebSocket TTS)
concept: pipecat
updated: 2026-04-17
source: src/pipecat/services/elevenlabs/tts.py
---

> Anchors agents to Pipecat v1.0.0. Top-level `voice_id=` and `model=` kwargs are **deprecated** — pass them via `settings=ElevenLabsTTSService.Settings(voice=..., model=...)`. Also note the kwarg is `voice`, not `voice_id`, in `Settings`.

# `ElevenLabsTTSService`

## Import

```python
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
```

There's also an `ElevenLabsHttpTTSService` in the same module for the non-streaming REST path. Prefer the WebSocket one for voice agents — it's the default and gives word-level timestamps.

## Minimal construction

```python
tts = ElevenLabsTTSService(
    api_key=os.getenv("ELABS_API_KEY"),
    settings=ElevenLabsTTSService.Settings(
        voice=os.getenv("ELABS_VOICE_ID"),
        model="eleven_multilingual_v2",
    ),
)
```

## Full configuration

```python
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.tts_service import TextAggregationMode

tts = ElevenLabsTTSService(
    api_key=os.getenv("ELABS_API_KEY"),
    sample_rate=24000,          # match PipelineParams.audio_out_sample_rate (default 24000)
    text_aggregation_mode=TextAggregationMode.SENTENCE,  # default; TOKEN for lower latency
    auto_mode=None,             # None = auto-enable with SENTENCE aggregation
    settings=ElevenLabsTTSService.Settings(
        voice=os.getenv("ELABS_VOICE_ID"),
        model="eleven_multilingual_v2",
        stability=0.55,
        similarity_boost=1.0,
        speed=1.08,
        apply_text_normalization="auto",
    ),
)
```

### Constructor parameters

Verified against `src/pipecat/services/elevenlabs/tts.py`:

| Param | Type | Notes |
|---|---|---|
| `api_key` | `str` | Required. |
| `voice_id` | `str \| None` | **Deprecated**; use `settings.voice`. |
| `model` | `str \| None` | **Deprecated**; use `settings.model`. |
| `url` | `str` | WebSocket endpoint. Default `"wss://api.elevenlabs.io"`. |
| `sample_rate` | `int \| None` | Output rate. Falls back to `PipelineParams.audio_out_sample_rate` (default `24000`). |
| `auto_mode` | `bool \| None` | ElevenLabs server-side chunk scheduling. `None` → auto (enabled for `SENTENCE`, disabled for `TOKEN`). |
| `text_aggregation_mode` | `TextAggregationMode \| None` | `SENTENCE` (default) or `TOKEN`. |
| `enable_ssml_parsing` | `bool \| None` | |
| `enable_logging` | `bool \| None` | Server-side logging on ElevenLabs. |
| `pronunciation_dictionary_locators` | `list[PronunciationDictionaryLocator]` | |
| `settings` | `ElevenLabsTTSService.Settings \| None` | Runtime-updatable voice settings. |

### `ElevenLabsTTSService.Settings` fields

Verified against `src/pipecat/services/elevenlabs/tts.py` (`ElevenLabsTTSSettings`):

```python
voice: str                  # voice ID
model: str                  # e.g. "eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5"
language: str | None        # BCP-47; only honored by multilingual models (eleven_flash_v2_5, eleven_turbo_v2_5)
stability: float            # 0.0-1.0
similarity_boost: float     # 0.0-1.0
style: float                # 0.0-1.0
use_speaker_boost: bool
speed: float                # WebSocket: 0.7-1.2  (HTTP: 0.25-4.0)
apply_text_normalization: Literal["auto", "on", "off"]
```

**WebSocket vs HTTP speed range:** WebSocket TTS is clamped to `0.7 <= speed <= 1.2`. Only the HTTP service accepts the wider `0.25-4.0` range.

**Reconnection semantics:** Changing `voice`, `model`, or `language` at runtime forces a WebSocket reconnect (see `URL_FIELDS` in the settings class). Changing voice-character fields (`stability`, `similarity_boost`, `style`, `use_speaker_boost`, `speed`) closes and reopens the audio context but keeps the WebSocket.

## Sample-rate → ElevenLabs format mapping

Internally the service maps `sample_rate` to ElevenLabs' `output_format` string:

| `sample_rate` | ElevenLabs `output_format` |
|---|---|
| `8000` | `pcm_8000` |
| `16000` | `pcm_16000` |
| `22050` | `pcm_22050` |
| `24000` | `pcm_24000` |
| `32000` | `pcm_32000` |
| `44100` | `pcm_44100` |
| `48000` | `pcm_48000` |

If your output device has a specific hardware rate (e.g. 48 kHz), set `sample_rate=48000` on the service **and** set `PipelineParams(audio_out_sample_rate=48000)` so the transport and TTS agree. Otherwise Pipecat will resample internally, which is fine but wastes CPU.

## Text aggregation modes

- `SENTENCE` (default) — waits for complete sentences before sending to TTS. Better for natural prosody; enables `auto_mode` which reduces latency by disabling server-side chunk scheduling.
- `TOKEN` — sends each LLM token as it arrives. Lower latency for the first word; prosody is worse. Disables `auto_mode`.

For voice assistants, `SENTENCE` is the right default. Use `TOKEN` only if you need sub-200ms first-word latency and can live with slightly choppier delivery.

## Common mistakes

| Training-data default | Correct in v1.0 |
|---|---|
| `ElevenLabsTTSService(api_key=..., voice_id="...", model="...")` | Pass via `settings=ElevenLabsTTSService.Settings(voice="...", model="...")`. |
| `ElevenLabsTTSService.Settings(voice_id=...)` | Field is named `voice`, not `voice_id`, in the `Settings` dataclass. |
| `speed=1.5` on WebSocket TTS | Cap at `1.2` — anything above is silently clamped / rejected. Use `ElevenLabsHttpTTSService` if you need wider range. |
| Setting `output_format="pcm_48000"` manually | Set `sample_rate=48000`; the service maps to the right `output_format`. |
| Passing `language="es"` with `eleven_multilingual_v2` | That model is auto-language; the `language` kwarg only applies to `eleven_flash_v2_5` / `eleven_turbo_v2_5`. Using the wrong model just ignores the kwarg silently. |
