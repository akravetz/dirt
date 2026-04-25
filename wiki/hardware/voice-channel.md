---
title: "Hardware — Voice Channel (Claudia) — Pipecat pipeline"
type: hardware
sources: []
related: [wiki/hardware/jabra.md, wiki/decisions/2026-04-16-voice-pipeline-selections.md, wiki/decisions/2026-04-16-wake-word-training-strategy.md, wiki/decisions/2026-04-23-wake-word-v5-passive-harvest.md, docs/adrs/005-agent-architecture.md, docs/references/pipecat/INDEX.md, docs/epics/live-audio/README.md]
created: 2026-04-18
updated: 2026-04-23
---

# Voice Channel (Claudia)

Production voice agent. Runs as a systemd user service, holds the Jabra's ALSA capture handle continuously (wake-word loop) and claims the playback device during conversations. Companion to the [Jabra hardware page](jabra.md) which documents the device itself; this page is about the **pipeline on top of it**.

Deployed 2026-04-18.

## Daily Operations

```bash
# Status + recent logs
systemctl --user status dirt-voice
journalctl --user -u dirt-voice -f

# Stop / start / restart
systemctl --user stop dirt-voice
systemctl --user start dirt-voice
systemctl --user restart dirt-voice

# Session transcripts (append-only JSONL)
tail -f sessions/voice/$(date -u +%Y-%m-%d).jsonl | jq
```

**Do NOT** run `python -m dirt.channels.voice` directly while the service is running — both will fight for the Jabra ALSA handle. Stop the service first: `systemctl --user stop dirt-voice`.

### Emergency stop (bypassing systemd)

The process writes its Python PID to `logs/voice.pid` on startup:

```bash
kill $(cat logs/voice.pid)           # clean shutdown via signal handler
kill -9 $(cat logs/voice.pid)        # hard, only if wedged
```

Reliable because it targets the actual Python PID — avoids the `pkill -f` self-match pitfall (pkill matching its own shell command) and the `uv run` parent/child orphaning problem (killing uv leaves the python child running).

## Pipeline Architecture

```
openWakeWord ("hey Claudia")  →  Pipecat pipeline:
    SoundDeviceTransport.input()    (Jabra mic, 16 kHz mono, callback mode)
    DeepgramSTTService              (Nova-3, streaming)
    LLMUserAggregator               (Silero VAD + Smart Turn v3)
    AnthropicLLMService             (Claude Haiku 4.5, tool calling)
    ElevenLabsTTSService            (turbo_v2_5, "Claudia" voice, 48 kHz)
    SoundDeviceTransport.output()   (Jabra speaker, 48 kHz stereo, +12 dB)
    LLMAssistantAggregator
```

Custom `SoundDeviceTransport` (in `src/dirt/channels/_audio_transport.py`) wraps `python-sounddevice` in portaudio **callback mode**. Decouples the pipeline's asyncio loop from the 48 kHz hardware clock via a thread-safe ring buffer — lets us run `latency='low'` without ALSA xruns and makes barge-in truly instant (one `bytearray.clear()` on `InterruptionFrame`). Upstream Pipecat `LocalAudioTransport` doesn't do this; the design rationale is in the [Pipecat reference pack](../../docs/references/pipecat/INDEX.md).

## Agent Tools Exposed on This Channel

All defined in `src/dirt/tools/`, shared with future channels (e.g., Telegram) via the framework-agnostic `ToolSpec` registry:

- **`get_current_status`** — latest tent sensor readings (temp, RH, VPD, pressure, dew point) + in-range / out-of-range flags against flower-stage targets. <200ms, direct Postgres read.
- **`get_sensor_trend`** — min / max / avg / direction (rising|falling|stable) for a single metric over N hours. <200ms, direct Postgres read.
- **`ask_wiki`** — delegated Sonnet 4.6 sub-agent with `read_wiki` + `grep_wiki` tools scoped to `wiki/`. Returns a spoken-ready 1-3 sentence answer plus cited source paths. `cancel_on_interruption=False`, 15s timeout.

When adding new tools, the default should be **narrow and well-typed for voice-turn-critical paths**, with a codegen-style sub-agent (via `ask_wiki`-style delegation) as the escape hatch for open-ended queries.

## Session Log Format

One JSON object per line in `sessions/voice/YYYY-MM-DD.jsonl`. Event types:

- `channel_started` — service boot (`device_index`)
- `wake` — wake-word fired (`score`)
- `conversation_end` — conversation reached idle timeout or errored. `reason: "idle" | "error"`. Includes `turns: [{role, text}]` for the `user`/`assistant` speech (developer seeds and tool internals are filtered).
- `channel_stopped` — service clean shutdown

## Configuration

All tunables in `src/dirt/channels/voice.py` module constants. The usual levers:

- `WAKE_THRESHOLD=0.35` / `WAKE_DEBOUNCE_S=3.0` — raise threshold if false-positives, lower if missed wakes
- `SESSION_IDLE_TIMEOUT_S=15` — how long silence before the conversation ends
- `VADParams(confidence=0.7, stop_secs=0.2, ...)` — speech detection tuning
- LLM + TTS model IDs and voice settings — swap Haiku↔Sonnet for quality, turbo↔multilingual_v2 for latency-vs-code-switching tradeoff

Four env vars required (all in `.env`, consumed via `dirt.config.settings`):
`DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`, `ELABS_API_KEY`, `ELABS_VOICE_ID`.

## Production Code Layout

- `src/dirt/channels/voice.py` — main voice loop (wake → Pipecat → back to wake). Entry: `python -m dirt.channels.voice`. Writes PID to `logs/voice.pid`.
- `src/dirt/channels/_audio_transport.py` — custom `SoundDeviceTransport` (callback mode + Jabra knobs: 48 kHz stereo upmix, +12 dB gain, `latency='low'`).
- `src/dirt/tools/` — shared agent tool library (framework-agnostic `ToolSpec` dataclass; channel adapters translate to Pipecat/Anthropic SDK/etc.).
- `~/.config/systemd/user/dirt-voice.service` — systemd user unit.
- `docs/references/pipecat/INDEX.md` — Pipecat v1.0 reference pack anchoring agents away from v0.x training-data patterns (required reading before editing any code above).

## Known Issues

### Intermittent: follow-up turn swallowed (observed 2026-04-18)

**Symptom.** Wake → greeting → user question 1 → Claudia answers → user question 2 → **no response**. Pipeline sits silent until `SESSION_IDLE_TIMEOUT_S` elapses and tears down. The `conversation_end` event in `sessions/voice/YYYY-MM-DD.jsonl` shows only one `user` turn captured, not two.

**Intermittent.** Ruled out as a fixed cause: was reproducible across multiple conversations in a row during one session, then stopped on its own mid-debugging (same code, same env, same speaker, same Jabra). Not correlated with restart, wake score, or user volume.

**What it is NOT.**
- Not `SESSION_IDLE_TIMEOUT_S=15` being too short — reproduced with back-to-back questions well inside 15s.
- Not `VADParams(min_volume=...)` — reproduced at both `0.5` and `0.35`. First question always triggered VAD fine; second got swallowed.
- Not the in-flight wake-word `model.reset()` / warmup change (that only affects the *wake-word loop between conversations* — phantom wakes from TTS echo tail — not in-conversation turn-taking).

**Suspected.** State-machine issue somewhere in `DeepgramSTTService` WebSocket, `LLMContextAggregatorPair` turn state, or the Silero VAD internal state after the first `UserStopped → LLMRun → BotSpeaking` cycle. Not yet diagnosed.

**For the next agent debugging this.** The next time it reproduces, flip logging to DEBUG and capture a full journal for one bad conversation:

```python
# src/dirt/channels/voice.py main()
logger.add(sys.stderr, level="DEBUG")
```

Then `systemctl --user restart dirt-voice` and reproduce. In the DEBUG output, check for each of these on question 2:

1. `VADUserStartedSpeakingFrame` / `UserSpeakingFrame` — is VAD firing at all?
2. Deepgram interim/final transcript log lines — is STT receiving audio and transcribing?
3. `User started speaking (strategy: ...)` from `LLMUserContextAggregator` — did the aggregator see a new turn?
4. `LLMRunFrame` → Anthropic request — did the LLM run?

Whichever stage is missing its event on the failed turn is where the bug lives. Revert to INFO when done; DEBUG is noisy.

## Harvest-only mode (wake-word v5 passive negative collection)

Set `DIRT_VOICE_HARVEST_ONLY=1` in the service environment and restart `dirt-voice` to enter passive-harvest mode: every wake fire is logged + saved as a WAV, but **no Pipecat conversation opens**. Used to bulk-collect guaranteed-negative captures during a "no wake word said" window for v5 retraining. Capture floor drops from 0.3 → 0.15 and debounce rises from 3 s → 5 s. Wake events in `sessions/voice/*.jsonl` get a `harvest_only: true` flag for filtering. Full operator workflow + rationale: [Wake-Word v5 Plan](../decisions/2026-04-23-wake-word-v5-passive-harvest.md).

## Deferred Enhancements

### "Meeting mode" / conversation lock (deferred 2026-04-18)

**Problem.** A single false-positive wake during a conference call or in-person meeting opens the pipeline for as long as the user keeps talking (VAD resets the idle timer on every utterance). Claudia then interjects repeatedly into the meeting side of the conversation, transcribing meeting audio as garbled user turns and responding to each fragment. Witnessed 2026-04-18 during a Zoom call: one wake at `score=0.74`, pipeline stayed live ~3.5 minutes, Claudia injected 8+ responses into the meeting. Mitigation at the time: `systemctl --user stop dirt-voice`.

**Immediate fix applied.** `WAKE_THRESHOLD` raised from 0.35 → 0.6. Clears every intentional wake recorded in `sessions/voice/*.jsonl` (real wakes score 0.82–0.97) while rejecting the meeting false-positive at 0.74.

**Longer-term design to revisit if this recurs.** Options in rough preference order:

1. **Double-wake confirmation.** Require two wake-word hits within ~2s before opening the pipeline. Cheap to add (modify `wait_for_wake`), high-impact against one-shot false positives, costs a small amount of wake latency.
2. **Meeting-mode toggle.** A local flag file or a lightweight IPC (socket, signal, CLI) that puts the service into "listening for wake suppressed" without stopping the daemon. Useful when the user wants predictable silence for a known window.
3. **Calendar-aware muting.** Read the user's Google Calendar (via the existing `mcp__claude_ai_Google_Calendar__*` tools) and auto-suppress wakes during events marked busy. Highest UX value; also the most infra to build.
4. **Physical button.** Press a button on or near the Jabra to arm/disarm wakes. Requires hardware beyond what's deployed.

Pick one of (1) / (2) if this happens again and the threshold bump isn't enough. (3) is the "full" answer but premature without evidence the threshold fix is insufficient.

## Pipecat Version Gotchas

Pipecat v1.0 (2026-04-14) is a breaking-change release from v0.x. Training-data-era patterns that are WRONG in our code:

- `OpenAILLMContext`, `AnthropicLLMContext` → `LLMContext` (unified)
- `llm.create_context_aggregator(context)` → `LLMContextAggregatorPair(context, user_params=..., assistant_params=...)`
- `TransportParams(vad_analyzer=SileroVADAnalyzer())` → VAD moved to `LLMUserAggregatorParams(vad_analyzer=...)`
- `PipelineParams(allow_interruptions=True)` → flag removed; interruptions are inherent
- `from pipecat.services.anthropic import AnthropicLLMService` → `from pipecat.services.anthropic.llm import AnthropicLLMService`

Read `docs/references/pipecat/INDEX.md` before editing any Pipecat code.
