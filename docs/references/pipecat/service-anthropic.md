---
title: AnthropicLLMService (Claude)
concept: pipecat
updated: 2026-04-17
source: src/pipecat/services/anthropic/llm.py
---

> Anchors agents to Pipecat v1.0.0. The `model=` top-level kwarg and `params=InputParams(...)` are v0.x and deprecated — use `settings=AnthropicLLMService.Settings(...)`.

# `AnthropicLLMService`

## Import

```python
from pipecat.services.anthropic.llm import AnthropicLLMService
```

The canonical import path in v1.0 is `pipecat.services.anthropic.llm`. (The shorter `pipecat.services.anthropic` still re-exports, but prefer the explicit path.)

## Construction

```python
from pipecat.services.anthropic.llm import AnthropicLLMService

llm = AnthropicLLMService(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    settings=AnthropicLLMService.Settings(
        model="claude-sonnet-4-6",
        system_instruction="You are a warm, helpful voice assistant. Keep responses short and conversational.",
        max_tokens=1024,
        temperature=0.7,
        enable_prompt_caching=True,
    ),
)
```

### Constructor parameters

Verified against `src/pipecat/services/anthropic/llm.py:140-175`:

| Param | Type | Notes |
|---|---|---|
| `api_key` | `str` | Required. Anthropic API key. |
| `model` | `str \| None` | **Deprecated**; use `settings.model`. |
| `params` | `InputParams \| None` | **Deprecated**; use `settings`. |
| `settings` | `AnthropicLLMService.Settings \| None` | Runtime-updatable settings. |
| `client` | `AsyncAnthropic \| None` | Optional custom client (useful for Bedrock / Vertex). |
| `retry_timeout_secs` | `float \| None` | Request timeout. Default `5.0`. |
| `retry_on_timeout` | `bool \| None` | Retry once on timeout. Default `False`. |

Service default model (when neither `model` nor `settings.model` is provided): `"claude-sonnet-4-6"` (see `src/pipecat/services/anthropic/llm.py:182`). Override to the current latest — e.g. `"claude-sonnet-4-6"`, `"claude-opus-4-7"`, `"claude-haiku-4-5"`.

### `AnthropicLLMService.Settings` fields

Verified against `src/pipecat/services/anthropic/llm.py` and `src/pipecat/services/settings.py`:

```python
# Inherited from LLMSettings
model: str
max_tokens: int | None          # default 4096
temperature: float | None
top_p: float | None
top_k: int | None
system_instruction: str | None  # ← system prompt lives here, not in LLMContext

# Anthropic-specific
enable_prompt_caching: bool | None
thinking: AnthropicLLMService.ThinkingConfig | None
```

## System prompt

System prompt belongs on the service `Settings`, **not** as a message in `LLMContext`. The adapter extracts `system_instruction` from settings and sends it to Anthropic's `system` parameter; user/assistant messages go through the `messages` array.

```python
llm = AnthropicLLMService(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    settings=AnthropicLLMService.Settings(
        model="claude-sonnet-4-6",
        system_instruction=(
            "You are Claudia, a warm, confident, sassy 28-year-old Colombian woman. "
            "You're speaking aloud, so no markdown or bullet points. "
            "Keep replies short and conversational — 1-2 sentences unless asked for more."
        ),
    ),
)
```

## Extended thinking (reasoning)

```python
from pipecat.services.anthropic.llm import AnthropicLLMService

llm = AnthropicLLMService(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    settings=AnthropicLLMService.Settings(
        model="claude-opus-4-7",
        thinking=AnthropicLLMService.ThinkingConfig(
            type="enabled",
            budget_tokens=2048,  # minimum 1024 per Anthropic docs
        ),
        system_instruction="...",
    ),
)
```

With thinking enabled, the service emits `LLMThoughtStartFrame` / `LLMThoughtTextFrame` / `LLMThoughtEndFrame` frames during generation — don't send these to TTS. (They're automatically filtered from the assistant aggregator's output.)

## Prompt caching

```python
settings=AnthropicLLMService.Settings(
    model="claude-sonnet-4-6",
    enable_prompt_caching=True,
    system_instruction="<long stable prompt>",
)
```

Caching applies to `system_instruction` and the front of the `messages` array. For voice conversations with a fixed system prompt, this can cut input-token cost by ~90% on long sessions. See the `claude-api` skill for general Anthropic caching guidance.

## Function calling / tools

Tools live on the `LLMContext`, not the service:

```python
from pipecat.adapters.schemas.tools_schema import ToolsSchema, FunctionSchema

context = LLMContext(
    tools=ToolsSchema(standard_tools=[
        FunctionSchema(
            name="get_temperature",
            description="Read the current tent temperature in °F.",
            properties={},
            required=[],
        ),
    ]),
)
```

Register the handler on the service with `llm.register_function("get_temperature", async_handler)` or `llm.register_direct_function(async_handler)`. Handlers must be `async`. See `examples/thinking/thinking-functions-anthropic.py` in Pipecat source.

## Common mistakes

| Training-data default | Correct in v1.0 |
|---|---|
| `AnthropicLLMService(api_key=..., model="claude-3-5-sonnet")` | Use `settings=AnthropicLLMService.Settings(model="claude-sonnet-4-6")`; top-level `model=` is deprecated. |
| `AnthropicLLMService(params=AnthropicLLMService.InputParams(...))` | Use `settings=Settings(...)`; `InputParams` is deprecated. |
| System prompt as `{"role": "system", "content": "..."}` in `LLMContext.messages` | Put it in `Settings(system_instruction=...)`. |
| `from pipecat.services.anthropic import AnthropicLLMContext` | `LLMContext` (unified) from `pipecat.processors.aggregators.llm_context`. |
| `model="claude-3-5-sonnet-20241022"` | Use current model IDs — `claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5`. |
