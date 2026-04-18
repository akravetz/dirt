---
title: SileroVADAnalyzer — voice activity detection
concept: pipecat
updated: 2026-04-17
source: src/pipecat/audio/vad/{silero,vad_analyzer}.py
---

> Anchors agents to Pipecat v1.0.0. **VAD no longer attaches to `TransportParams` — it goes on `LLMUserAggregatorParams`.** This is the single most common training-data mistake.

# `SileroVADAnalyzer` and `VADParams`

## Imports

```python
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
```

No extra install needed — `onnxruntime` is already a core Pipecat dependency, and the Silero ONNX model ships with the package.

## Minimal use (v1.0)

```python
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)

user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(
        vad_analyzer=SileroVADAnalyzer(),
    ),
)
```

## `SileroVADAnalyzer` constructor

```python
SileroVADAnalyzer(
    sample_rate=None,         # 8000 or 16000; None → pick up from pipeline
    params=None,              # VADParams; default VADParams() if None
)
```

**Silero only supports 8 kHz or 16 kHz input.** The analyzer's `num_frames_required()` returns 512 at 16 kHz, 256 at 8 kHz. If your mic runs at a different rate, put a resampler in the pipeline or set `PipelineParams(audio_in_sample_rate=16000)` (and match on the transport/STT).

## `VADParams` fields + defaults

Verified against `src/pipecat/audio/vad/vad_analyzer.py`:

```python
@dataclass
class VADParams:
    confidence: float = 0.7     # min confidence score to count as speech (0-1)
    start_secs: float = 0.2     # sustained speech before entering SPEAKING state
    stop_secs: float = 0.2      # sustained silence before leaving SPEAKING state  ⚠️ v0.x default was 0.8
    min_volume: float = 0.6     # min smoothed volume to count as speech (0-1)
```

**`stop_secs=0.2` is the v1.0 default** (v0.x was `0.8`). If you're porting a v0.x bot that felt sluggish, that's probably why — you can keep the faster default. If you're porting and getting clipped turns, raise `stop_secs` to `0.4-0.8`.

## State machine (what confidence does)

Internally the analyzer tracks `QUIET → STARTING → SPEAKING → STOPPING → QUIET`. A buffer frame counts as speech iff **both** `confidence >= params.confidence` **and** `volume >= params.min_volume`. The two thresholds gate each other — setting `confidence` alone doesn't stop the analyzer from firing on a loud cough, and setting `min_volume` alone doesn't stop it firing on quiet breath noise.

## Tuning for hard acoustic environments

- **Self-hear / echo**: if your mic picks up your own TTS, VAD will false-trigger during playback. Options:
  - Hardware: use a speakerphone with built-in AEC (Jabra, Yealink).
  - Software: mute the mic during playback; re-enable after a tail-quench delay (the DIY pattern). Pipecat's default handling usually suffices, but the framework doesn't do AEC itself.
- **Quiet speakers / far-field mic**: lower `min_volume` to `0.3-0.4`.
- **Noisy room**: raise `confidence` to `0.8` and `min_volume` to `0.7` to cut false triggers from HVAC, fans, etc.
- **Short conversational turns getting cut off**: raise `stop_secs` to `0.4-0.6`. Too high (`>1.0`) and the bot feels slow to respond.

## Custom `VADParams` example

```python
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

vad = SileroVADAnalyzer(
    sample_rate=16000,
    params=VADParams(
        confidence=0.75,
        start_secs=0.2,
        stop_secs=0.35,     # slightly longer tail for natural pauses
        min_volume=0.5,
    ),
)

user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(vad_analyzer=vad),
)
```

## Alternatives in v1.0

- `AICVADAnalyzer` (`pipecat.audio.vad.aic_vad`) — heavier but higher-accuracy VAD from AIC. Same attachment point.
- `KrispVivaVADAnalyzer` (`pipecat.audio.vad.krisp_viva_vad`) — Krisp's commercial VAD with noise suppression. Same attachment point.
- Server-side VAD via Deepgram / OpenAI Realtime. In that case you don't need `vad_analyzer` at all; the STT service emits `VADUserStartedSpeakingFrame` / `VADUserStoppedSpeakingFrame` on its own.

## Common mistakes

| Training-data default | Correct in v1.0 |
|---|---|
| `TransportParams(audio_in_enabled=True, vad_analyzer=SileroVADAnalyzer())` | `TransportParams(audio_in_enabled=True)` + `LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())`. |
| `DailyParams(vad_analyzer=...)` / `FastAPIWebsocketParams(vad_analyzer=...)` | Same — `vad_analyzer` is NOT a field on any transport-params class in v1.0. |
| `VADParams(stop_secs=0.8)` as if it were the default | `stop_secs=0.2` is the v1.0 default; explicitly set only if you want a longer tail. |
| `SileroVADAnalyzer(sample_rate=24000)` | Only `8000` or `16000` — Silero constraint. |
| `from pipecat.vad import SileroVADAnalyzer` | `from pipecat.audio.vad.silero import SileroVADAnalyzer`. |
