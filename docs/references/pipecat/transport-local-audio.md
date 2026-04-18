---
title: LocalAudioTransport — PyAudio-backed I/O
concept: pipecat
updated: 2026-04-17
source: src/pipecat/transports/local/audio.py
---

> Anchors agents to Pipecat v1.0.0. `LocalAudioTransportParams` only adds device indices on top of `TransportParams`; audio flags (`audio_in_enabled`, etc.) are inherited. VAD is **not** configured here — see [vad-silero.md](vad-silero.md).

# `LocalAudioTransport`

PyAudio-backed transport for running a Pipecat pipeline directly against the host's mic/speakers. Best for local development, desktop/CLI agents, and hardware prototypes. Not suitable for multi-client / webRTC use — use `DailyTransport` or `SmallWebRTCTransport` for that.

## Imports

```python
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
```

## Install

```bash
uv add "pipecat-ai[local]"
# On macOS: brew install portaudio    (PyAudio native dep)
# On Debian/Ubuntu: apt install portaudio19-dev
```

## Minimal construction

```python
transport = LocalAudioTransport(
    LocalAudioTransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    )
)
```

The transport opens default input and output devices on PyAudio.

## `LocalAudioTransportParams` fields

Verified against `src/pipecat/transports/local/audio.py:34-44`:

```python
class LocalAudioTransportParams(TransportParams):
    input_device_index: int | None = None   # PyAudio device index for mic; None = default
    output_device_index: int | None = None  # PyAudio device index for speaker; None = default
```

All other fields come from `TransportParams`:

```python
# Most-used fields (inherited)
audio_in_enabled: bool = False
audio_in_sample_rate: int | None = None    # falls back to PipelineParams.audio_in_sample_rate
audio_in_channels: int = 1
audio_in_filter: BaseAudioFilter | None = None
audio_in_passthrough: bool = True
audio_in_stream_on_start: bool = True

audio_out_enabled: bool = False
audio_out_sample_rate: int | None = None   # falls back to PipelineParams.audio_out_sample_rate
audio_out_channels: int = 1
audio_out_bitrate: int = 96000
audio_out_10ms_chunks: int = 4              # buffer size (40ms of audio)
audio_out_end_silence_secs: int = 2
audio_out_auto_silence: bool = True
```

**There is no `vad_analyzer` or `turn_analyzer` field.** Those moved to the user aggregator in v1.0.

## Picking specific input/output devices

```python
import pyaudio
pa = pyaudio.PyAudio()
for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    print(i, info["name"], info["maxInputChannels"], info["maxOutputChannels"])
pa.terminate()
```

Then set:

```python
transport = LocalAudioTransport(
    LocalAudioTransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        input_device_index=5,     # from the listing above
        output_device_index=5,
    )
)
```

The input/output indices are independent — you can route mic from one device and speaker to another.

## Sample rates

The transport opens its PyAudio streams at:
- Input: `audio_in_sample_rate` (params) if set, else `PipelineParams.audio_in_sample_rate` (default 16000).
- Output: `audio_out_sample_rate` (params) if set, else `PipelineParams.audio_out_sample_rate` (default 24000).

For a voice agent hitting a USB speakerphone that's locked to 48 kHz (e.g. Jabra SPEAK), set both sample rates explicitly to match hardware:

```python
PipelineParams(audio_in_sample_rate=16000, audio_out_sample_rate=48000)
transport = LocalAudioTransport(
    LocalAudioTransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_in_sample_rate=16000,     # mic runs at 16 kHz mono
        audio_out_sample_rate=48000,    # speakerphone hardware clock
        audio_out_channels=2,           # Jabra playback endpoint is stereo-only
        input_device_index=<jabra_idx>,
        output_device_index=<jabra_idx>,
    )
)
```

Pipecat will upsample LLM/TTS output to 48 kHz internally if the TTS service produces a lower rate. You can also set `ElevenLabsTTSService(sample_rate=48000)` to produce 48 kHz directly and skip the internal resample.

## Integration with wake-word gating

Pipecat's transport opens its mic when the pipeline starts and closes it when the pipeline ends. For a wake-word-gated agent, you typically:

1. Run your wake-word detector in a separate loop against the raw mic (via `sounddevice` or `pyaudio` directly).
2. On detection, spin up a new Pipecat `PipelineTask` + `PipelineRunner`, let it run to end-of-turn, then tear it down.
3. Resume the wake-word loop.

You can NOT use the same PyAudio device from both the wake-word loop and `LocalAudioTransport` simultaneously — only one process-level PyAudio handle may own the device. Release the wake-word stream before calling `runner.run(task)`, and re-acquire it after.

## Common mistakes

| Training-data default | Correct in v1.0 |
|---|---|
| `LocalAudioTransportParams(vad_analyzer=SileroVADAnalyzer())` | Field doesn't exist. VAD goes on `LLMUserAggregatorParams`. |
| `LocalAudioTransportParams(camera_in_enabled=True)` | `video_in_enabled=True` (v1.0 renamed `camera_*` → `video_*`). |
| Using `sounddevice` inside Pipecat processors | Use the default PyAudio-backed transport unless you need a specific `sounddevice` feature; mixing creates two audio-subsystem clients. |
| Holding a `sounddevice.RawInputStream` open while starting `LocalAudioTransport` on the same device | Release it first. Only one owner per device. |
| Passing `sample_rate` only to `PipelineParams` and expecting the transport to follow | That works for the input — it propagates via `StartFrame`. But if the hardware is locked to a specific rate (Jabra 48 kHz), set `audio_in_sample_rate` / `audio_out_sample_rate` **explicitly on the transport params too** so PyAudio opens the stream at the right rate. |
