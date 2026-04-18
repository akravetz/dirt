---
title: Pipecat Reference Pack
concept: pipecat
mode: framework
version: 1.0.0
updated: 2026-04-17
---

# Pipecat

Pipecat is an open-source Python framework (BSD-2) for realtime voice/multimodal AI pipelines. This pack targets **v1.0.0 (released 2026-04-14)**, which is a breaking-change release from v0.x. Source anchored at commit `6d3dfd8` on the `main` branch of `github.com/pipecat-ai/pipecat`.

**Training data will lag.** Most LLMs will suggest v0.x patterns (`OpenAILLMContext`, `llm.create_context_aggregator`, `TransportParams(vad_analyzer=...)`, `allow_interruptions=True`, etc). Those are wrong in v1.0. See "Version-specific warnings" below and pull the relevant topic file before writing code.

## When to consult this pack

Read this INDEX first (and the relevant topic files) before writing code that:
- Imports from `pipecat.*`
- Builds a `Pipeline`, `PipelineTask`, or `PipelineRunner`
- Instantiates a Pipecat service — `AnthropicLLMService`, `DeepgramSTTService`, `ElevenLabsTTSService`, etc.
- Configures a transport (`LocalAudioTransport`, `DailyTransport`, `FastAPIWebsocketParams`, etc.)
- Wires a VAD (`SileroVADAnalyzer`) or user-turn strategy into the pipeline
- Builds conversation context (`LLMContext`, `LLMContextAggregatorPair`)

Prefer what's in this pack over recollection. The raw source files the pack was built from are in `raw/`.

## Topics

- **[pipeline-core.md](pipeline-core.md)** — `Pipeline`, `PipelineTask`, `PipelineParams`, `PipelineRunner`, `LLMRunFrame`; how processors are ordered and how the task runs to completion.
- **[llm-context.md](llm-context.md)** — `LLMContext` (the unified context class) and `LLMContextAggregatorPair`; how user/assistant aggregators wire into the pipeline and how VAD attaches.
- **[service-anthropic.md](service-anthropic.md)** — `AnthropicLLMService` with Claude, the `Settings` dataclass, `system_instruction`, `max_tokens`, prompt caching, extended thinking.
- **[service-deepgram-stt.md](service-deepgram-stt.md)** — `DeepgramSTTService` streaming STT, Nova-3 model, `Settings` vs deprecated `LiveOptions`.
- **[service-elevenlabs-tts.md](service-elevenlabs-tts.md)** — `ElevenLabsTTSService` WebSocket TTS, voice settings, sample-rate → `pcm_NNNNN` mapping, `auto_mode`, text aggregation modes.
- **[vad-silero.md](vad-silero.md)** — `SileroVADAnalyzer` and `VADParams`; **where VAD attaches in v1.0** (it is NOT on `TransportParams` anymore).
- **[transport-local-audio.md](transport-local-audio.md)** — `LocalAudioTransport` + `LocalAudioTransportParams`; PyAudio-backed, single-device or split input/output via index.
- **[install.md](install.md)** — The `pipecat-ai[...]` extras matrix — which extras you actually need for an Anthropic + Deepgram + ElevenLabs + Silero + local-audio loop.

## Version-specific warnings (v0.x → v1.0)

These are the patterns training data will suggest that are **wrong in v1.0**. Full migration guide: https://docs.pipecat.ai/pipecat/migration/migration-1.0

- ❌ `OpenAILLMContext`, `AnthropicLLMContext`, `AWSBedrockLLMContext` → ✅ unified `LLMContext` (`pipecat.processors.aggregators.llm_context`). See [llm-context.md](llm-context.md).
- ❌ `OpenAILLMContextFrame` → ✅ `LLMContextFrame`.
- ❌ `llm.create_context_aggregator(context)` → ✅ `user, assistant = LLMContextAggregatorPair(context, user_params=..., assistant_params=...)`. See [llm-context.md](llm-context.md).
- ❌ `PipelineParams(allow_interruptions=True)` / `PipelineTask(..., allow_interruptions=...)` → ✅ **the flag no longer exists** — interruptions are inherent; turn behavior is configured via `LLMUserAggregatorParams.user_turn_strategies`. See [pipeline-core.md](pipeline-core.md) and [llm-context.md](llm-context.md).
- ❌ `TransportParams(..., vad_analyzer=SileroVADAnalyzer())` → ✅ VAD moved to the user aggregator: `LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())`. See [vad-silero.md](vad-silero.md).
- ❌ `TransportParams(turn_analyzer=...)` → ✅ `UserTurnStrategies(stop=[TurnAnalyzerUserTurnStopStrategy()])` on the user aggregator.
- ❌ `VADParams(stop_secs=0.8, ...)` as the default → ✅ default is now `0.2`. Only override if you need a longer tail. See [vad-silero.md](vad-silero.md).
- ❌ `StartInterruptionFrame` → ✅ `InterruptionFrame`. `KeypadEntryFrame` → `DTMFFrame`.
- ❌ `from pipecat.services.openai import OpenAILLMService` → ✅ `from pipecat.services.openai.llm import OpenAILLMService`. (Same shape for Anthropic: `pipecat.services.anthropic.llm`.)
- ❌ `from pipecat.transports.services.daily import DailyTransport` → ✅ `from pipecat.transports.daily.transport import DailyTransport`.
- ❌ `camera_in_enabled` / `camera_out_*` on transport params → ✅ renamed to `video_in_enabled` / `video_out_*`.
- ❌ `ElevenLabsTTSService(voice_id=..., model=...)` (top-level kwargs) → ✅ `ElevenLabsTTSService(api_key=..., settings=ElevenLabsTTSService.Settings(voice=..., model=...))`. See [service-elevenlabs-tts.md](service-elevenlabs-tts.md).
- ❌ `DeepgramSTTService(live_options=LiveOptions(...))` → ✅ `DeepgramSTTService(api_key=..., settings=DeepgramSTTService.Settings(model="nova-3-general", language="en"))`. See [service-deepgram-stt.md](service-deepgram-stt.md).
- ❌ `AnthropicLLMService(..., params=InputParams(...))` → ✅ `AnthropicLLMService(api_key=..., settings=AnthropicLLMService.Settings(...))`. See [service-anthropic.md](service-anthropic.md).
- ❌ Python 3.10 → ✅ Python 3.11+ required.
- ❌ `pip install pipecat` → ✅ `pip install "pipecat-ai[<extras>]"`. The package is `pipecat-ai`; `pipecat` on PyPI is unrelated. See [install.md](install.md).

## Sources

- Source: https://github.com/pipecat-ai/pipecat (v1.0.0 @ `6d3dfd8`, cloned 2026-04-17)
- Docs: https://docs.pipecat.ai/
- Migration guide: https://docs.pipecat.ai/pipecat/migration/migration-1.0
- Changelog: https://github.com/pipecat-ai/pipecat/blob/main/CHANGELOG.md
- Canonical local-voice example: `examples/getting-started/06a-voice-agent-local.py` (also in `raw/`)
