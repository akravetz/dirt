---
title: Pipeline, PipelineTask, PipelineRunner
concept: pipecat
updated: 2026-04-17
source: src/pipecat/pipeline/{pipeline,task,runner}.py
---

> Anchors agents to Pipecat v1.0.0. Training data will suggest v0.x patterns (`allow_interruptions`, `OpenAILLMContextFrame`, etc.). Prefer what's written here.

# Pipeline core: `Pipeline`, `PipelineTask`, `PipelineParams`, `PipelineRunner`

## Mental model

A Pipecat app is a **list of `FrameProcessor` instances** wrapped in a `Pipeline`. Frames flow through the list in order: audio enters at `transport.input()`, text transcriptions flow to the LLM, LLM tokens flow to TTS, audio exits at `transport.output()`. The `PipelineTask` orchestrates the run; the `PipelineRunner` handles signals (SIGINT/SIGTERM) and lifecycle.

## Imports

```python
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import LLMRunFrame
```

## Canonical pipeline order (STT → LLM → TTS)

Order matters. The standard voice-agent pipeline is:

```python
pipeline = Pipeline([
    transport.input(),       # raw audio in
    stt,                     # audio → transcription frames
    user_aggregator,         # transcription → context (user side)
    llm,                     # context → LLM tokens
    tts,                     # LLM tokens → audio
    transport.output(),      # audio out
    assistant_aggregator,    # LLM tokens → context (assistant side)
])
```

**`assistant_aggregator` goes AFTER `transport.output()`.** That's intentional — it lets the aggregator capture word-level timestamps from the audio output stage. Training data often places it before `transport.output()`; that's wrong.

## `PipelineTask` construction

```python
task = PipelineTask(
    pipeline,
    params=PipelineParams(
        enable_metrics=True,
        enable_usage_metrics=True,
    ),
    # Optional:
    idle_timeout_secs=300,           # None to disable; default 300
    cancel_on_idle_timeout=True,
    enable_tracing=False,
    enable_turn_tracking=True,
    conversation_id=None,
)
```

Frames to queue manually (most common):

```python
# Kick off the conversation with an instruction, then run the LLM once.
context.add_message({"role": "developer", "content": "Introduce yourself."})
await task.queue_frames([LLMRunFrame()])
```

`LLMRunFrame()` triggers the LLM service to read the current context and respond. Use this instead of manually constructing `LLMContextFrame`.

## `PipelineParams` fields (v1.0)

Verified against `src/pipecat/pipeline/task.py`:

| Field | Type | Default |
|---|---|---|
| `audio_in_sample_rate` | `int` | `16000` |
| `audio_out_sample_rate` | `int` | `24000` |
| `enable_metrics` | `bool` | `False` |
| `enable_usage_metrics` | `bool` | `False` |
| `enable_heartbeats` | `bool` | `False` |
| `heartbeats_period_secs` | `float` | `1.0` |
| `heartbeats_monitor_secs` | `float` | `10.0` |
| `report_only_initial_ttfb` | `bool` | `False` |
| `send_initial_empty_metrics` | `bool` | `True` |
| `start_metadata` | `dict` | `{}` |

**There is no `allow_interruptions` field.** Interruptions are inherent in v1.0 — the user-aggregator handles them via turn strategies. See [llm-context.md](llm-context.md).

## `PipelineRunner`

```python
runner = PipelineRunner(
    name=None,                # optional instance name
    handle_sigint=True,       # catch Ctrl-C gracefully
    handle_sigterm=False,
    force_gc=False,           # force gc after task completes
    loop=None,                # defaults to current running loop
)
await runner.run(task)
```

`runner.run(task)` blocks until the task completes or is cancelled. Call `await task.cancel()` from an event handler to stop cleanly.

## Complete minimal example (LocalAudioTransport + Claude)

Adapted from `raw/example-voice-agent-local.py` — swapping OpenAI+Cartesia for Anthropic+ElevenLabs:

```python
import asyncio
import os

from dotenv import load_dotenv

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams

load_dotenv()


async def main():
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        )
    )

    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    tts = ElevenLabsTTSService(
        api_key=os.getenv("ELABS_API_KEY"),
        settings=ElevenLabsTTSService.Settings(
            voice=os.getenv("ELABS_VOICE_ID"),
            model="eleven_multilingual_v2",
        ),
    )

    llm = AnthropicLLMService(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        settings=AnthropicLLMService.Settings(
            model="claude-sonnet-4-6",
            system_instruction="You are a helpful voice assistant. Keep responses brief.",
        ),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        llm,
        tts,
        transport.output(),
        assistant_aggregator,
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
    )

    context.add_message({"role": "developer", "content": "Introduce yourself briefly."})
    await task.queue_frames([LLMRunFrame()])

    await PipelineRunner().run(task)


if __name__ == "__main__":
    asyncio.run(main())
```

## Common mistakes

| Training-data default | Correct in v1.0 |
|---|---|
| `PipelineTask(pipeline, allow_interruptions=True)` | Remove — there is no such kwarg. Interruptions are inherent. |
| `PipelineParams(allow_interruptions=True)` | Remove — field does not exist. |
| `StartInterruptionFrame` | `InterruptionFrame` |
| `from pipecat.frames.frames import OpenAILLMContextFrame` | `from pipecat.frames.frames import LLMContextFrame` |
| `task.queue_frame(TTSSpeakFrame("hi"))` to kick off a greeting | Use `context.add_message({"role": "developer", "content": "..."})` + `await task.queue_frames([LLMRunFrame()])` so the LLM drives the response naturally. |
| Placing `assistant_aggregator` before `transport.output()` | Place it **after** `transport.output()` for word-level timestamp accuracy. |
