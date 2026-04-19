# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Dirt** — Home grow monitoring and tracking system. Two halves:

1. **Monitoring app** — Webcam live feed, temperature/humidity sensors graphed over time, and an MCP server for Claude Desktop integration. Python >=3.13, managed with `uv`.
2. **Grow wiki** — Agent-maintained knowledge base tracking 4 plants over time. Raw materials (daily photos, sensor readings, chat notes) are synthesized into a structured, non-duplicated wiki.

- **Repo**: https://github.com/akravetz/dirt
- **Project Board**: https://github.com/users/akravetz/projects/1/views/1

### Current grow

- **Germination date:** 2026-03-15 (authoritative: `growstate.germination_date` in `var/dirt.db`).
- **Flower start date:** not yet set (still in vegetative stage). Once flower is flipped, `growstate.flower_start_date` becomes the authoritative source.
- **Deriving stage without the DB:** if `flower_start_date` is NULL (or `today` is before it) → `veg`. If set and `today - flower_start_date < 21` → `flower_early`. If ≥ 21 → `flower_late`. See `apps/shared/src/dirt_shared/services/grow_state.py` for the canonical logic and `STAGE_TARGETS` (temp/RH/VPD bands per stage).
- **Update this file** whenever the grow is flipped, terminated, or a new grow is started — don't rely on the DB alone, since agents without DB access still need to know the stage.

## Repository layout

`uv` workspace with five Python packages under `apps/`, each its own package with its own `pyproject.toml` and tests:

- **`apps/hwd/`** — `dirt-hwd` service (port 8000). Serial reader, humidifier loop, archive loop, capture loop, ESP32 ingest endpoint. OFF-LIMITS to routine rewrites — it's the keep-alive daemon running in production.
- **`apps/web/`** — `dirt-web` service (port 8001). UI + JSON API + MCP mount. Cookie-session auth. Slated for rewrite.
- **`apps/shared/`** — `dirt-shared`. Models, db, config, observability, non-HW services (capture, photos, telegram, daily_report, daily_sensors, daily_synthesis, readings, snapshots, grow_state).
- **`apps/mcp/`** — `dirt-mcp`. MCP server (mounted at `/mcp` inside dirt-web).
- **`apps/voice/`** — `dirt-voice`. Claudia wake-word → Pipecat pipeline → Jabra audio I/O.
- **`apps/tests/invariants/`** — cross-cutting architectural invariants (HUMAN-OWNED).
- **`apps/<app>/tests/`** — per-app unit + integration tests.
- **`contracts/`** — (future) OpenAPI spec + generated TS client + generated Pydantic models.
- **`web-ui/`** — Vite + React + TypeScript + TanStack Router + TanStack Query + Tailwind v4 + Biome. Skeleton exists with a single placeholder route at `/`. Dev server on :5173 (`pnpm --dir web-ui dev`). Phase 2 generator agents extend this against the frozen API contract.
- **`var/`** — runtime data: `dirt.db`, `snapshots/`, `logs/`, `sessions/`, `raw/photos/`, `outputs/`, `db-backups/`. Gitignored. Override the root via `DIRT_DATA_DIR` env var (defaults to `<repo>/var`).

Services are user-level systemd units under `systemd/`; `scripts/install-systemd` symlinks them into `~/.config/systemd/user/`.

## Framework/API References

Knowledge packs live in `docs/references/`. Before writing code that touches any of these concepts, read the linked `INDEX.md` first — the pack anchors to current practice and should override any conflicting training-data instincts.

- **Deepgram TTS (Aura-2)** — `docs/references/deepgram-tts-aura-2/INDEX.md`. Consult when writing any code that calls Deepgram text-to-speech (REST `POST /v1/speak` or WebSocket `wss://api.deepgram.com/v1/speak`), picking a voice/model id, setting up the voice agent's TTS output, or handling Deepgram auth.
- **Modern Idiomatic TypeScript** — `docs/references/modern-idiomatic-typescript/INDEX.md`. Consult when writing or refactoring any `.ts`/`.tsx` file, choosing lint/format tooling, or editing `tsconfig.json` — anchors to current practice (`satisfies`, discriminated unions, branded types, Biome) and overrides training-data defaults like `enum`, `namespace`, `any`, and ESLint+Prettier scaffolds.
- **TanStack Router v1** — `docs/references/tanstack-router-v1/INDEX.md`. Consult when writing or modifying routes in `src/routes/`, using `createFileRoute` / `createRootRoute` / `createRouter`, handling route loaders (`loader`, `beforeLoad`, `loaderDeps`, `staleTime`), or reading/writing URL search params (`validateSearch`, `useSearch`, `<Link search>`, search middlewares) in a TanStack Router v1 app. Overrides training-data instincts to reach for `react-router-dom`, v0 `new Router()` / `new RootRoute()` syntax, `useSearchParams`, or `useEffect`-based data fetching.
- **Pipecat v1.0** — `docs/references/pipecat/INDEX.md`. Consult when writing code that imports from `pipecat.*`, building a `Pipeline`/`PipelineTask`/`PipelineRunner`, instantiating a Pipecat service (`AnthropicLLMService`, `DeepgramSTTService`, `ElevenLabsTTSService`, etc.), configuring a transport (`LocalAudioTransport`, `DailyTransport`), or wiring a VAD/`SileroVADAnalyzer` into a pipeline. Pipecat v1.0.0 shipped 2026-04-14 with major breaking changes from v0.x — training data will suggest `OpenAILLMContext`, `llm.create_context_aggregator(...)`, `TransportParams(vad_analyzer=...)`, and `allow_interruptions=True`, all of which are gone or relocated in v1.0.
- **Claude Agent SDK (Python)** — `docs/references/claude-agent-sdk/INDEX.md`. Consult when writing code that imports from `claude_agent_sdk`, calls `query()` or `ClaudeSDKClient`, configures `ClaudeAgentOptions` (cwd, allowed_tools, disallowed_tools, permission_mode, system_prompt, hooks, can_use_tool), or builds a local Claude-Code-style research sub-agent — e.g. any edit to `apps/voice/src/dirt_voice/tools/wiki.py` or a new sub-agent under `apps/voice/src/dirt_voice/tools/`. The package was renamed from `claude-code-sdk` at v0.1.0; training data suggests `ClaudeCodeOptions`, `api_key=...` parameters, and `allowed_tools` as an availability filter — all wrong for current versions.
- **Tailwind CSS v4** — `docs/references/tailwind-v4/INDEX.md`. Consult when writing or refactoring Tailwind utility classes in `web-ui/src/`, editing `web-ui/src/styles.css` (global `@import "tailwindcss"` + `@theme` directive), wiring `vite.config.ts` for the `@tailwindcss/vite` plugin, porting the Dirt paper/ink/magenta palette and Fraunces / IBM Plex Mono / Inter fonts from `debug/webapp.zip/colors_and_type.css`, adding custom utilities with `@utility`, or overriding dark mode with `@custom-variant`. Tailwind v4 (v4.2.x) is a ground-up rewrite — training data reliably suggests v3 patterns (`tailwind.config.js` with `content:` / `theme.extend`, the three `@tailwind base/components/utilities` directives, `postcss-cli` + `autoprefixer` boilerplate, PurgeCSS, JS plugin API, `resolveConfig()`), all obsolete in v4.

## Commands

### Monitoring App

The backend runs as two systemd-managed processes: `dirt-hwd` (hardware + ingest, :8000) and `dirt-web` (UI + MCP, :8001). There is no single `main.py`.

- **Service control**: `systemctl --user {start,stop,restart,status} dirt-hwd dirt-web`
- **Tail logs**: `journalctl --user -u dirt-hwd -f` (or `dirt-web`)
- **Dev foreground run**: `systemctl --user stop dirt-hwd && uv run --package dirt-hwd python -m dirt_hwd.main` (same pattern for `dirt-web`)
- **Install systemd units from repo**: `scripts/install-systemd`
- **Test all**: `uv run pytest -q` (runs invariants + all per-app suites per `testpaths`)
- **Invariants only**: `uv run pytest apps/tests/invariants/ -q`
- **One app's tests**: `cd apps/hwd && uv run pytest -q` (or `apps/web`, `apps/shared`, `apps/mcp`)
- **Single test**: `uv run pytest apps/<app>/tests/test_foo.py::test_name -v`
- **Lint**: `uv run ruff check`
- **Format**: `uv run ruff format`
- **Add dependency**: `uv add --package dirt-<app> <package>` (targets a specific workspace member; dev deps stay at root via `uv add --dev`)
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
- **Session transcripts**: `var/sessions/voice/YYYY-MM-DD.jsonl` — append-only, one JSON event per line (`wake`, `conversation_end`, etc.)
- **Emergency stop (bypass systemd)**: `kill $(cat var/logs/voice.pid)`. PID file is written on startup, unlinked on clean exit. Use over `pkill -f` — pattern matching the voice-channel string will SIGKILL the invoking shell.
- **Full operational spec**: `wiki/hardware/voice-channel.md` (pipeline, tools, config); `wiki/hardware/jabra.md` (device quirks). Do NOT run `python -m dirt_voice.channels.voice` directly while the service is up — both processes will fight for the Jabra ALSA handle.
- **Manual foreground run (dev)**: `systemctl --user stop dirt-voice && uv run --package dirt-voice python -m dirt_voice.channels.voice`. Restart the service when done.
- **Pipecat v1.0 is a major departure from v0.x** — training data will suggest obsolete patterns (`OpenAILLMContext`, `TransportParams(vad_analyzer=...)`, `allow_interruptions=True`). Always read `docs/references/pipecat/INDEX.md` before editing `apps/voice/src/dirt_voice/channels/voice.py`, `_audio_transport.py`, or `apps/voice/src/dirt_voice/tools/`.

### Daily Report (automated 14:00 MDT)

- **Manual run**: `scripts/daily_report` (today, skip if marker exists) or `scripts/daily_report --force` (re-run today) or `scripts/daily_report --date 2026-04-19 --force`.
- **Service / timer status**: `systemctl --user status dirt-daily-report.timer` and `journalctl --user -u dirt-daily-report.service -n 100`.
- **Marker files**: `var/logs/daily_report/<DATE>.completed` and `var/logs/daily_report/<DATE>.failed`. The `.completed` marker is what makes the next run skip — delete it (or pass `--force`) to re-run.
- **Synthesis trace**: `var/logs/daily_report/<DATE>.synthesis.json` — full sub-agent tool trace, usage, cost. Produced even on failure.
- **Failure → Telegram alert**: Phases 1–4 (capture, validate, snapshot, synthesize) all bail-on-fail and post a `<b>⚠ Daily report failed</b>` message to the configured chat. Phase 5 (Telegram delivery) is non-fatal — wiki is the durable record; failed deliveries log to journal only.
- **Pipeline source**: `apps/shared/src/dirt_shared/services/daily_report.py` (orchestrator), `apps/shared/src/dirt_shared/services/{photos,daily_sensors,daily_synthesis,telegram}.py` (per-phase). Workflow detail in `wiki/CLAUDE.md` (Daily Update Workflow).

## Documentation (Progressive Disclosure)

This file is the discovery layer. Read deeper docs before starting work in an area.

- **`docs/README.md`** — Full project description, documentation map
- **`docs/adrs/`** — Architecture Decision Records. Read before proposing alternatives to settled choices.
- **`docs/epics/`** — Epic context and scope. Read the relevant epic README before starting work. Issues are tracked on the [GitHub project board](https://github.com/users/akravetz/projects/1/views/1) — find issues for an epic with `gh issue list --repo akravetz/dirt --label "epic:<slug>"`.
- **`docs/progress/`** — Feature progress tracking between PRs. Update after completing work.
- **`docs/rules/`** — Codebase rules and conventions. Read before making changes.
- **`docs/references/`** — Version-pinned reference packs. See the "Framework/API References" section at the top of this file for the list and triggers.

## Test Ownership

- **`apps/tests/invariants/`** — HUMAN-OWNED. You MUST NOT modify these files. They encode sacred architectural rules: cross-app import boundaries, auth boundary on the web app, hwd route allowlist. If an invariant fails, fix your code to satisfy the test — never modify the test. Flag invariant failures to the user.
- **`apps/<app>/tests/`** — Agent-owned. Per-app unit + integration tests. Create and update freely.
- **`conftest.py`** (repo root) — autouse fixture that isolates observability logs to a per-test `tmp_path / "logs"`. Applies to every test under any app.

## Scratch / Sandbox

- **`debug/`** — Agent sandbox. Write scratch scripts here freely when you need to probe an API, exercise a library, capture a throwaway artifact, or test hardware interaction before wiring it into the real app. Nothing in this directory is production code, imported by the app, or covered by tests. Use it instead of cluttering `src/` or `scripts/` with one-off experiments.

## Observability

Logs are first-class diagnostic artifacts. Two families with different contracts:

### `sessions/<channel>/YYYY-MM-DD.jsonl` — conversation records (long-lived)

What the user and agent said. Append-only, agent-readable. Kept indefinitely (ops cleanup only). One JSON object per line with channel-specific fields. Streams:
- `var/sessions/voice/` — voice channel turns (wake, conversation_end). See `wiki/hardware/voice-channel.md`.
- `var/sessions/telegram/` — telegram channel turns (future).

### `logs/<stream>/YYYY-MM-DD.jsonl` — operational instrumentation (short-lived)

Structured JSONL for debugging. Rotated by filename date on first write of the day. All events share one envelope: `{ts, conversation_id, stream, event, ...fields}`.

| Stream | What it records | Retention | Source |
|---|---|---|---|
| `wake_scores` | Every wake-model score ≥ `WAKE_NEAR_MISS_FLOOR` (`near_miss`) and every threshold-crossing wake (`wake_detected`). | 1 day | `apps/voice/src/dirt_voice/channels/voice.py:wait_for_wake` |
| `audio_rms` | Input amplitude (int16 RMS) at ~1 Hz during pipecat conversations. Only fires while a conversation is active; silent otherwise. | 1 day | `apps/voice/src/dirt_voice/channels/_audio_transport.py:SoundDeviceInputTransport` |
| `audio_playback` | Per-assistant-turn duration metric: `tts_stream_duration_s` (pipecat's "bot done speaking" time) vs `playback_duration_s` (speaker actually finished), and `excess_buffer_s` gap. Detects ring-buffer decoupling anomalies. | 1 day | `apps/voice/src/dirt_voice/channels/_audio_transport.py:SoundDeviceOutputTransport` |
| `pipecat_frames` | Every non-raw-data frame pushed through the pipeline — turn lifecycle (`BotSpeakingFrame`, `UserStartedSpeakingFrame`, …), STT/LLM/TTS signals (`TranscriptionFrame`, `TTSStoppedFrame`, `LLMRunFrame`, …), interruptions, errors. Denylist excludes `AudioRawFrame`, `ImageRawFrame`, `HeartbeatFrame`. | 1 day | `apps/voice/src/dirt_voice/channels/_observers.py:FrameFlowObserver` |
| `subagent_calls` | Full Claude Agent SDK trace per `ask_wiki` invocation — question, every tool_use/tool_result, final answer, usage, cost, duration. | 10 days | `apps/voice/src/dirt_voice/tools/wiki.py:_ask_wiki` |
| `humidifier` | State transitions of the Kasa EP10 plug controlling the Raydrop humidifier. One event per on/off change with `reason` (`vpd_above_upper_band` / `vpd_below_upper_band` / `failsafe_stale_sensor` / `lights_off_prep`), `vpd`, `vpd_age_s`, `stage`, `upper_band_kpa`, `lower_band_kpa`, `lights_on`, `minutes_until_off`, `band_offset_kpa`. Loop targets the stage's VPD upper edge with lights-schedule feedforward — see `wiki/hardware/humidifier-control.md`. | 30 days | `apps/hwd/src/dirt_hwd/services/humidifier.py:humidifier_loop` |
| `daily_report` | Per-phase markers for the daily report run (`run_started`, `capture_finished`, `validate_finished`, `snapshot_finished`, `synthesis_finished`, `deliver_finished`, `run_completed`, `run_failed`, `deliver_failed`). | 30 days | `apps/shared/src/dirt_shared/services/daily_report.py` |

### Adding a new log stream

Call `log_event(stream, event, **fields)` from `dirt_shared.observability`. It handles path, rotation, timestamp, and correlation ID. Register non-default retention in `_RETENTION` in `apps/shared/src/dirt_shared/observability.py`. That's the whole API — don't invent per-stream helpers.

### Test isolation

`logs_dir()` reads the `DIRT_LOGS_DIR` env var on every write. The autouse fixture in `conftest.py` at the repo root (`isolate_observability_logs`) sets it to a per-test `tmp_path / "logs"` so no test ever appends to the production log tree. Production code paths leave `DIRT_LOGS_DIR` unset and fall back to `settings.data_dir / "logs"` — which resolves to `var/logs/` by default (override the root via `DIRT_DATA_DIR`). Apply this pattern (env-var-based isolation + autouse fixture) when adding new modules that write to disk under `var/logs/`, `var/sessions/`, or similar shared locations.

### Correlation across streams

Every entry stamped with `conversation_id` (UUID generated per voice wake). To reconstruct a single user interaction:

```bash
CID=f1918a9c-1545-4033-beaa-9adc4f5b3dbf
jq -c "select(.conversation_id==\"$CID\")" \
  var/sessions/voice/*.jsonl var/logs/*/*.jsonl 2>/dev/null
```

### Free-text operational logs

Loguru output (voice service) goes to stderr → systemd journal:

```bash
journalctl --user -u dirt-voice -f           # live tail
journalctl --user -u dirt-voice --since "1 hour ago"
```

Retention is governed by systemd's journal config, not us. Use this for free-text tailing during a live incident; use the `logs/*/` JSONL streams for programmatic / agent-readable analysis.

## Grow Wiki

Agent-maintained knowledge base at `wiki/`. For ANY work touching the wiki — ingestion, daily updates, page conventions, linting, query filing, plant labeling, or routing a question to the right file — **start at [`wiki/CLAUDE.md`](wiki/CLAUDE.md)**. That file is the full operating manual (data architecture across `var/sessions/`/`var/raw/`/`wiki/`/`var/outputs/`, wiki-specific commands, page conventions, workflows, linting, plant labeling A-D). The `ask_wiki` sub-agent (`apps/voice/src/dirt_voice/tools/wiki.py`) also reads it as its first step.
