---
title: LLMContext and aggregators (turn management + VAD attachment)
concept: pipecat
updated: 2026-04-17
source: src/pipecat/processors/aggregators/{llm_context,llm_response_universal}.py
---

> Anchors agents to Pipecat v1.0.0. `OpenAILLMContext`, `AnthropicLLMContext`, and `llm.create_context_aggregator(...)` are all v0.x — gone in v1.0.

# `LLMContext` and `LLMContextAggregatorPair`

## Single unified context (v1.0 change)

v0.x had per-provider context classes — `OpenAILLMContext`, `AnthropicLLMContext`, `AWSBedrockLLMContext`. **v1.0 collapses all of these into a single `LLMContext`** in `pipecat.processors.aggregators.llm_context`. The service-specific adapter handles translation to each provider's wire format internally.

```python
from pipecat.processors.aggregators.llm_context import LLMContext

context = LLMContext()
# or with initial messages:
context = LLMContext(messages=[
    {"role": "developer", "content": "Keep responses short."},
])
```

Messages follow the OpenAI chat-completion shape (`{"role": ..., "content": ...}`). `LLMContext.add_message(...)` appends; `set_messages(...)` replaces.

## System prompt goes in service `Settings`, not in the context

**Do not put the system prompt in `LLMContext.messages`.** Put it in the LLM service's `Settings`:

```python
llm = AnthropicLLMService(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    settings=AnthropicLLMService.Settings(
        model="claude-sonnet-4-6",
        system_instruction="You are a helpful voice assistant.",  # ← here
    ),
)
```

This matters because the system prompt should be stable across context updates, summarization, and persistence. A system message in `context.messages` would get mangled by those paths.

## `LLMContextAggregatorPair` — the v1.0 pattern

v0.x pattern — **gone in v1.0**:

```python
# ❌ v0.x — DO NOT USE
user_aggregator, assistant_aggregator = llm.create_context_aggregator(context)
```

v1.0 pattern:

```python
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    LLMAssistantAggregatorParams,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer

user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    assistant_params=LLMAssistantAggregatorParams(),
)
```

`LLMContextAggregatorPair` implements `__iter__`, so you can tuple-unpack it directly. You can also hold the instance and call `.user()` / `.assistant()`.

## VAD attaches HERE, not on the transport

In v1.0 **VAD lives on the user aggregator**, not on `TransportParams`. This is one of the most common training-data mistakes — every v0.x example puts VAD on the transport.

```python
# ❌ v0.x — WRONG IN v1.0
transport = LocalAudioTransport(LocalAudioTransportParams(
    audio_in_enabled=True,
    audio_out_enabled=True,
    vad_analyzer=SileroVADAnalyzer(),  # ← this field doesn't exist on TransportParams
))

# ✅ v1.0
transport = LocalAudioTransport(LocalAudioTransportParams(
    audio_in_enabled=True,
    audio_out_enabled=True,
))
user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(
        vad_analyzer=SileroVADAnalyzer(),
    ),
)
```

See [vad-silero.md](vad-silero.md) for VAD tuning.

## `LLMUserAggregatorParams` fields (v1.0)

Verified against `src/pipecat/processors/aggregators/llm_response_universal.py:94-125`:

```python
@dataclass
class LLMUserAggregatorParams:
    user_turn_strategies: UserTurnStrategies | None = None
    user_mute_strategies: list[BaseUserMuteStrategy] = field(default_factory=list)
    user_turn_stop_timeout: float = 5.0
    user_idle_timeout: float = 0              # 0 disables idle detection
    vad_analyzer: VADAnalyzer | None = None
    audio_idle_timeout: float = 1.0           # force turn-stop if mic goes silent
    filter_incomplete_user_turns: bool = False
    user_turn_completion_config: UserTurnCompletionConfig | None = None
```

Turn management notes:
- `user_turn_strategies=UserTurnStrategies(start=[...], stop=[...])` lets you compose start/stop detectors (VAD, min-words, end-pointing, smart-turn). For simple VAD-only, leave `user_turn_strategies=None` and just set `vad_analyzer`.
- `audio_idle_timeout=1.0` is a safety net — if the user mutes mic mid-speech, the turn force-stops after 1s.
- `user_idle_timeout` emits an `on_user_turn_idle` event — 0 disables.

## `LLMAssistantAggregatorParams` fields (v1.0)

```python
@dataclass
class LLMAssistantAggregatorParams:
    enable_auto_context_summarization: bool = False
    auto_context_summarization_config: LLMAutoContextSummarizationConfig | None = None
```

Default is fine for most voice bots. Enable auto-summarization for long-running conversations that would otherwise exceed the LLM's context window.

## Pipeline placement

The user aggregator goes **after the STT** (it needs transcripts). The assistant aggregator goes **after `transport.output()`** (it needs timing from the audio emit stage, not the raw LLM tokens).

```python
pipeline = Pipeline([
    transport.input(),
    stt,
    user_aggregator,        # after STT
    llm,
    tts,
    transport.output(),
    assistant_aggregator,   # after transport.output
])
```

## Common mistakes

| Training-data default | Correct in v1.0 |
|---|---|
| `OpenAILLMContext(messages=...)` or `AnthropicLLMContext(...)` | `LLMContext(messages=...)` — one class for all providers. |
| `context = OpenAILLMContext(messages=[{"role": "system", "content": "..."}, ...])` | Put system prompt in `Settings(system_instruction=...)`; only `developer`/`user`/`assistant` messages go in the context. |
| `user_aggregator, assistant_aggregator = llm.create_context_aggregator(context)` | `LLMContextAggregatorPair(context, user_params=..., assistant_params=...)` |
| `TransportParams(vad_analyzer=SileroVADAnalyzer())` | `LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())` |
| `PipelineParams(allow_interruptions=True)` | Remove — use `user_turn_strategies` on `LLMUserAggregatorParams` if you need custom turn behavior; otherwise defaults handle interruptions. |
| `assistant_aggregator` placed before `transport.output()` | Place after `transport.output()`. |
