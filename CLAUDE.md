# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Dirt** — Home grow monitoring and tracking system. Two halves:

1. **Monitoring app** — Webcam live feed, temperature/humidity sensors graphed over time, and an MCP server for Claude Desktop integration. Python >=3.13, managed with `uv`.
2. **Grow wiki** — Agent-maintained knowledge base tracking 4 plants over time. Raw materials (daily photos, sensor readings, chat notes) are synthesized into a structured, non-duplicated wiki.

- **Repo**: https://github.com/akravetz/dirt
- **Project Board**: https://github.com/users/akravetz/projects/1/views/1

## Framework/API References

Knowledge packs live in `docs/references/`. Before writing code that touches any of these concepts, read the linked `INDEX.md` first — the pack anchors to current practice and should override any conflicting training-data instincts.

- **Deepgram TTS (Aura-2)** — `docs/references/deepgram-tts-aura-2/INDEX.md`. Consult when writing any code that calls Deepgram text-to-speech (REST `POST /v1/speak` or WebSocket `wss://api.deepgram.com/v1/speak`), picking a voice/model id, setting up the voice agent's TTS output, or handling Deepgram auth.
- **Modern Idiomatic TypeScript** — `docs/references/modern-idiomatic-typescript/INDEX.md`. Consult when writing or refactoring any `.ts`/`.tsx` file, choosing lint/format tooling, or editing `tsconfig.json` — anchors to current practice (`satisfies`, discriminated unions, branded types, Biome) and overrides training-data defaults like `enum`, `namespace`, `any`, and ESLint+Prettier scaffolds.
- **TanStack Router v1** — `docs/references/tanstack-router-v1/INDEX.md`. Consult when writing or modifying routes in `src/routes/`, using `createFileRoute` / `createRootRoute` / `createRouter`, handling route loaders (`loader`, `beforeLoad`, `loaderDeps`, `staleTime`), or reading/writing URL search params (`validateSearch`, `useSearch`, `<Link search>`, search middlewares) in a TanStack Router v1 app. Overrides training-data instincts to reach for `react-router-dom`, v0 `new Router()` / `new RootRoute()` syntax, `useSearchParams`, or `useEffect`-based data fetching.
- **Pipecat v1.0** — `docs/references/pipecat/INDEX.md`. Consult when writing code that imports from `pipecat.*`, building a `Pipeline`/`PipelineTask`/`PipelineRunner`, instantiating a Pipecat service (`AnthropicLLMService`, `DeepgramSTTService`, `ElevenLabsTTSService`, etc.), configuring a transport (`LocalAudioTransport`, `DailyTransport`), or wiring a VAD/`SileroVADAnalyzer` into a pipeline. Pipecat v1.0.0 shipped 2026-04-14 with major breaking changes from v0.x — training data will suggest `OpenAILLMContext`, `llm.create_context_aggregator(...)`, `TransportParams(vad_analyzer=...)`, and `allow_interruptions=True`, all of which are gone or relocated in v1.0.
- **Claude Agent SDK (Python)** — `docs/references/claude-agent-sdk/INDEX.md`. Consult when writing code that imports from `claude_agent_sdk`, calls `query()` or `ClaudeSDKClient`, configures `ClaudeAgentOptions` (cwd, allowed_tools, disallowed_tools, permission_mode, system_prompt, hooks, can_use_tool), or builds a local Claude-Code-style research sub-agent — e.g. any edit to `src/dirt/tools/wiki.py` or a new sub-agent under `src/dirt/tools/`. The package was renamed from `claude-code-sdk` at v0.1.0; training data suggests `ClaudeCodeOptions`, `api_key=...` parameters, and `allowed_tools` as an availability filter — all wrong for current versions.

## Commands

### Monitoring App

- **Run**: `uv run python main.py`
- **Test all**: `uv run pytest -v`
- **Unit tests**: `uv run pytest tests/ --ignore=tests/e2e --ignore=tests/invariants -v`
- **Invariants**: `uv run pytest tests/invariants/ -v`
- **E2E tests**: `uv run pytest tests/e2e/ -v`
- **Single test**: `uv run pytest tests/test_foo.py::test_name -v`
- **Lint**: `uv run ruff check src/ tests/`
- **Format**: `uv run ruff format src/ tests/`
- **Add dependency**: `uv add <package>` (dev: `uv add --optional dev <package>`)
- **Firmware test**: `cd firmware && pio test -e native` (runs on host, no hardware needed)
- **Firmware build**: `cd firmware && pio run -e nano`
- **Firmware upload**: `cd firmware && pio run -e nano -t upload`

### PTZ Camera

- **Go to a preset**: `scripts/camera look <overview|plant_a|plant_b|plant_c|plant_d|home>`
- **Relative move** (user-frame): `scripts/camera nudge left 5` or compound `scripts/camera nudge left=3 up=2`
- **Zoom**: `scripts/camera zoom +0.2` (relative) or `scripts/camera zoom-to 1.5` (absolute)
- **Current state**: `scripts/camera where` (adds `--json` for structured output)
- **Daemon status**: `systemctl --user status dirt-camera` / `journalctl --user -u dirt-camera -f`
- **Full operational spec**: `wiki/hardware/ptz-camera.md`. Do NOT bypass the CLI by calling the daemon's socket directly or running debug/obsbot_* binaries — the CLI handles user-frame translation, preset lookup, and error reporting.

### Voice Channel (Claudia)

- **Service status**: `systemctl --user status dirt-voice` / `journalctl --user -u dirt-voice -f`
- **Stop / start / restart**: `systemctl --user {stop,start,restart} dirt-voice`
- **Session transcripts**: `sessions/voice/YYYY-MM-DD.jsonl` — append-only, one JSON event per line (`wake`, `conversation_end`, etc.)
- **Emergency stop (bypass systemd)**: `kill $(cat logs/voice.pid)`. PID file is written on startup, unlinked on clean exit. Use over `pkill -f` — pattern matching the voice-channel string will SIGKILL the invoking shell.
- **Full operational spec**: `wiki/hardware/voice-channel.md` (pipeline, tools, config); `wiki/hardware/jabra.md` (device quirks). Do NOT run `python -m dirt.channels.voice` directly while the service is up — both processes will fight for the Jabra ALSA handle.
- **Manual foreground run (dev)**: `systemctl --user stop dirt-voice && uv run python -m dirt.channels.voice`. Restart the service when done.
- **Pipecat v1.0 is a major departure from v0.x** — training data will suggest obsolete patterns (`OpenAILLMContext`, `TransportParams(vad_analyzer=...)`, `allow_interruptions=True`). Always read `docs/references/pipecat/INDEX.md` before editing `src/dirt/channels/voice.py`, `_audio_transport.py`, or `src/dirt/tools/`.

### Daily Report (automated 14:00 MDT)

- **Manual run**: `scripts/daily_report` (today, skip if marker exists) or `scripts/daily_report --force` (re-run today) or `scripts/daily_report --date 2026-04-19 --force`.
- **Service / timer status**: `systemctl --user status dirt-daily-report.timer` and `journalctl --user -u dirt-daily-report.service -n 100`.
- **Marker files**: `logs/daily_report/<DATE>.completed` and `logs/daily_report/<DATE>.failed`. The `.completed` marker is what makes the next run skip — delete it (or pass `--force`) to re-run.
- **Synthesis trace**: `logs/daily_report/<DATE>.synthesis.json` — full sub-agent tool trace, usage, cost. Produced even on failure.
- **Failure → Telegram alert**: Phases 1–4 (capture, validate, snapshot, synthesize) all bail-on-fail and post a `<b>⚠ Daily report failed</b>` message to the configured chat. Phase 5 (Telegram delivery) is non-fatal — wiki is the durable record; failed deliveries log to journal only.
- **Pipeline source**: `src/dirt/services/daily_report.py` (orchestrator), `src/dirt/services/{photos,daily_sensors,daily_synthesis,telegram}.py` (per-phase). Workflow detail in `wiki/CLAUDE.md` (Daily Update Workflow).

## Documentation (Progressive Disclosure)

This file is the discovery layer. Read deeper docs before starting work in an area.

- **`docs/README.md`** — Full project description, documentation map
- **`docs/adrs/`** — Architecture Decision Records. Read before proposing alternatives to settled choices.
- **`docs/epics/`** — Epic context and scope. Read the relevant epic README before starting work. Issues are tracked on the [GitHub project board](https://github.com/users/akravetz/projects/1/views/1) — find issues for an epic with `gh issue list --repo akravetz/dirt --label "epic:<slug>"`.
- **`docs/progress/`** — Feature progress tracking between PRs. Update after completing work.
- **`docs/rules/`** — Codebase rules and conventions. Read before making changes.
- **`docs/references/`** — Version-pinned reference packs. See the "Framework/API References" section at the top of this file for the list and triggers.

## Test Ownership

- **`tests/invariants/`** — HUMAN-OWNED. You MUST NOT modify these files. They encode sacred architectural rules (auth boundaries, import boundaries). If an invariant test fails, fix your code to satisfy the test — never modify the test. Flag invariant failures to the user.
- **`tests/e2e/`** — Agent-owned. Playwright E2E tests you can create and update freely.
- **`tests/`** (other) — Agent-owned. Unit and integration tests you can create and update freely.

## Scratch / Sandbox

- **`debug/`** — Agent sandbox. Write scratch scripts here freely when you need to probe an API, exercise a library, capture a throwaway artifact, or test hardware interaction before wiring it into the real app. Nothing in this directory is production code, imported by the app, or covered by tests. Use it instead of cluttering `src/` or `scripts/` with one-off experiments.

## Observability

Logs are first-class diagnostic artifacts. Two families with different contracts:

### `sessions/<channel>/YYYY-MM-DD.jsonl` — conversation records (long-lived)

What the user and agent said. Append-only, agent-readable. Kept indefinitely (ops cleanup only). One JSON object per line with channel-specific fields. Streams:
- `sessions/voice/` — voice channel turns (wake, conversation_end). See `wiki/hardware/voice-channel.md`.
- `sessions/telegram/` — telegram channel turns (future).

### `logs/<stream>/YYYY-MM-DD.jsonl` — operational instrumentation (short-lived)

Structured JSONL for debugging. Rotated by filename date on first write of the day. All events share one envelope: `{ts, conversation_id, stream, event, ...fields}`.

| Stream | What it records | Retention | Source |
|---|---|---|---|
| `wake_scores` | Every wake-model score ≥ `WAKE_NEAR_MISS_FLOOR` (`near_miss`) and every threshold-crossing wake (`wake_detected`). | 1 day | `src/dirt/channels/voice.py:wait_for_wake` |
| `audio_rms` | Input amplitude (int16 RMS) at ~1 Hz during pipecat conversations. Only fires while a conversation is active; silent otherwise. | 1 day | `src/dirt/channels/_audio_transport.py:SoundDeviceInputTransport` |
| `audio_playback` | Per-assistant-turn duration metric: `tts_stream_duration_s` (pipecat's "bot done speaking" time) vs `playback_duration_s` (speaker actually finished), and `excess_buffer_s` gap. Detects ring-buffer decoupling anomalies. | 1 day | `src/dirt/channels/_audio_transport.py:SoundDeviceOutputTransport` |
| `pipecat_frames` | Every non-raw-data frame pushed through the pipeline — turn lifecycle (`BotSpeakingFrame`, `UserStartedSpeakingFrame`, …), STT/LLM/TTS signals (`TranscriptionFrame`, `TTSStoppedFrame`, `LLMRunFrame`, …), interruptions, errors. Denylist excludes `AudioRawFrame`, `ImageRawFrame`, `HeartbeatFrame`. | 1 day | `src/dirt/channels/_observers.py:FrameFlowObserver` |
| `subagent_calls` | Full Claude Agent SDK trace per `ask_wiki` invocation — question, every tool_use/tool_result, final answer, usage, cost, duration. | 10 days | `src/dirt/tools/wiki.py:_ask_wiki` |
| `humidifier` | State transitions of the Kasa EP10 plug controlling the Raydrop humidifier. One event per on/off change with `reason`, `rh`, `rh_age_s`. | 30 days | `src/dirt/services/humidifier.py:humidifier_loop` |
| `daily_report` | Per-phase markers for the daily report run (`run_started`, `capture_finished`, `validate_finished`, `snapshot_finished`, `synthesis_finished`, `deliver_finished`, `run_completed`, `run_failed`, `deliver_failed`). | 30 days | `src/dirt/services/daily_report.py` |

### Adding a new log stream

Call `log_event(stream, event, **fields)` from `dirt.observability`. It handles path, rotation, timestamp, and correlation ID. Register non-default retention in `_RETENTION` in `src/dirt/observability.py`. That's the whole API — don't invent per-stream helpers.

### Correlation across streams

Every entry stamped with `conversation_id` (UUID generated per voice wake). To reconstruct a single user interaction:

```bash
CID=f1918a9c-1545-4033-beaa-9adc4f5b3dbf
jq -c "select(.conversation_id==\"$CID\")" \
  sessions/voice/*.jsonl logs/*/*.jsonl 2>/dev/null
```

### Free-text operational logs

Loguru output (voice service) goes to stderr → systemd journal:

```bash
journalctl --user -u dirt-voice -f           # live tail
journalctl --user -u dirt-voice --since "1 hour ago"
```

Retention is governed by systemd's journal config, not us. Use this for free-text tailing during a live incident; use the `logs/*/` JSONL streams for programmatic / agent-readable analysis.

## Grow Wiki

Agent-maintained knowledge base at `wiki/`. For ANY work touching the wiki — ingestion, daily updates, page conventions, linting, query filing, plant labeling, or routing a question to the right file — **start at [`wiki/CLAUDE.md`](wiki/CLAUDE.md)**. That file is the full operating manual (data architecture across `sessions/`/`raw/`/`wiki/`/`outputs/`, wiki-specific commands, page conventions, workflows, linting, plant labeling A-D). The `ask_wiki` sub-agent (`src/dirt/tools/wiki.py`) also reads it as its first step.
