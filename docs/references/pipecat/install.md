---
title: Installing Pipecat — package name, extras, and what you actually need
concept: pipecat
updated: 2026-04-17
source: src/pyproject.toml
---

> Anchors agents to Pipecat v1.0.0. The PyPI package is `pipecat-ai`, **not** `pipecat`. Training data will often suggest `pip install pipecat` — that's a different, unrelated package.

# Install

## Package name

```bash
# ✅ correct
uv add "pipecat-ai[<extras>]"

# using pip
pip install "pipecat-ai[<extras>]"
```

**Do not** install `pipecat` — that's a different, unrelated PyPI package. Pipecat the framework is published as `pipecat-ai`.

## Python version

v1.0 requires **Python 3.11+**. v0.x supported 3.10; if you see 3.10 guidance in training data, it's outdated.

## Extras (what each one pulls in)

From `src/pyproject.toml` on the v1.0.0 branch. Only the relevant subset is shown here — full list has 60+ entries for every supported provider.

| Extra | Pulls in | Needed for |
|---|---|---|
| `anthropic` | `anthropic>=0.49` | `AnthropicLLMService` |
| `deepgram` | `deepgram-sdk>=6.1.1` + websockets-base | `DeepgramSTTService` (and `DeepgramTTSService`) |
| `elevenlabs` | websockets-base | `ElevenLabsTTSService` |
| `silero` | (empty — uses core `onnxruntime`) | `SileroVADAnalyzer` |
| `local` | `pyaudio~=0.2.14` | `LocalAudioTransport` |
| `openai` | websockets-base | `OpenAILLMService`, `OpenAITTSService` |
| `daily` | `daily-python~=0.27` | `DailyTransport` |
| `cartesia` | websockets-base | `CartesiaTTSService` |

## For an Anthropic + Deepgram + ElevenLabs + Silero + local-audio loop

```bash
uv add "pipecat-ai[anthropic,deepgram,elevenlabs,silero,local]"
```

On macOS you also need PortAudio for PyAudio:

```bash
brew install portaudio
```

On Debian/Ubuntu:

```bash
apt install portaudio19-dev
```

## Core dependencies (always installed)

Worth knowing what you get for free:

- `numpy`, `Pillow`, `pydantic`, `openai` (yes — the OpenAI SDK is a core dep, used internally as the universal context/message shape)
- `loguru` (all logging)
- `aiohttp`, `aiofiles`
- `onnxruntime` (used by Silero VAD and other on-device models)
- `resampy`, `soxr` (audio resampling)
- `numba`, `transformers` (pulled in by LocalSmartTurnAnalyzerV3 which is enabled by default)

## Import smoke test

After install, verify the stack comes up clean:

```python
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair, LLMUserAggregatorParams,
)
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
```

Any `ModuleNotFoundError` here points at a missing extra.

## Common mistakes

| Training-data default | Correct in v1.0 |
|---|---|
| `pip install pipecat` | `pip install "pipecat-ai[extras]"` — the package name is `pipecat-ai`. |
| `uv add pipecat-ai` (no extras) | Without extras, service imports will fail with a helpful `ModuleNotFoundError`. Add the ones you use. |
| Python 3.10 | Python 3.11+ required for v1.0. |
| `pip install pipecat-silero` / `pip install pipecat-anthropic` | They're extras on `pipecat-ai`, not separate packages. |
