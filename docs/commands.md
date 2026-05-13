# Commands Reference

Every dev/test/lint/firmware/web-ui command an agent typically reaches for. Read before running anything; pull the exact command from here rather than reconstructing it.

## Browser automation

Use the **`agent-browser`** CLI for every agentic browser interaction (navigating, screenshotting, snapshotting the a11y tree, clicking, typing, evaluating JS). Do NOT reach for a Playwright MCP, a raw `playwright` script, or `curl` + HTML parsing when the goal is actually "drive a browser". Run `agent-browser --help` (and `agent-browser skills get core --full`) to get the full command surface on demand.

## Committing

Before `git add` + `git commit`, run **`scripts/agent-fix`**. It applies every formatter and safe lint-fix in one pass (ruff format, ruff check --fix, Biome check --write, ESLint --fix) so the pre-commit hooks don't bounce you back for cosmetic drift.

The pre-commit hooks run in **write-mode** (not check-mode). If a hook still modifies files during the commit, pre-commit aborts with "files were modified by this hook" — the recovery is `git add -A && git commit ...` again, NOT chasing each formatter's `--write` flag separately. If a hook fails for a non-cosmetic reason (test failure, type error, invariant violation), fix the underlying code; never edit the hook config or skip with `--no-verify`.

## Monitoring app (Python services)

The local backend runs as systemd-managed processes. `dirt-hwd` is hardware + ingest (:8000), `dirt-web` is UI + MCP (:8001), and `dirt-gateway` is the outbound-only hosted control-plane sync. There is no single `main.py`.

- **Service control**: `systemctl --user {start,stop,restart,status} dirt-hwd dirt-web dirt-gateway`
- **Tail logs**: `journalctl --user -u dirt-hwd -f` (or `dirt-web`, `dirt-gateway`)
- **Dev foreground run**: `systemctl --user stop dirt-hwd && uv run --package dirt-hwd python -m dirt_hwd.main` (same pattern for `dirt-web`)
- **Gateway dry run**: `uv run --package dirt-gateway python -m dirt_gateway.main --once --dry-run` after stopping `dirt-gateway` if it is already running
- **Install systemd units from repo**: `scripts/install-systemd`
- **Test all**: `uv run pytest -q` (runs invariants + all per-app suites per `testpaths`)
- **Invariants only**: `uv run pytest apps/tests/invariants/ -q`
- **One app's tests**: `cd apps/hwd && uv run pytest -q` (or `apps/web`, `apps/shared`, `apps/mcp`)
- **Single test**: `uv run pytest apps/<app>/tests/test_foo.py::test_name -v`
- **Lint**: `uv run ruff check`
- **Format**: `uv run ruff format`
- **Add dependency**: `uv add --package dirt-<app> <package>` (targets a specific workspace member; dev deps stay at root via `uv add --dev`)

## Remote boxes

- **dirt2 SSH**: `ssh dirt2` uses the local `akcom` SSH key and logs in as `akcom` on `dirt2` (`192.168.1.123` on the LAN). Do not print or copy private keys.
- **Host key**: expected ED25519 fingerprint is `SHA256:+y8RJWANUEEFZl3muWoQu6cclm4qqU1Oxgge+uo33II`. If `known_hosts` is missing the alias, verify the fingerprint before adding it.

## Hosted control plane (Railway)

Read `docs/database.md` and `docs/references/atlas/INDEX.md` before changing cloud schema or running cloud migrations. The supported production deploy flow is:

```bash
scripts/deploy-control-plane
```

That script loads ignored `.env` first and `.env.prod` second by default, syncs the required Railway service variables without printing values, runs `atlas migrate apply --env cloud`, upserts the V1 gateway credential row, deploys `apps/control-plane/` to Railway service `control-plane-api`, deploys `web-ui/` to Railway service `web-ui`, then waits for smoke checks at `DIRT_CLOUD_API_BASE_URL/api/health` and `DIRT_CLOUD_UI_BASE_URL/`. Hosted browser auth uses `DIRT_CLOUD_ADMIN_USERNAME` plus `DIRT_CLOUD_ADMIN_PASSWORD_HASH`; it does not read local `AUTH_USERNAME` / `AUTH_PASSWORD`. If `DIRT_CLOUD_DATABASE_URL` is unset locally, it reads `DATABASE_PUBLIC_URL` from the Railway Postgres service without printing it. Do not print `.env` / `.env.prod`, do not run app-start DDL, and do not bypass this script with ad hoc `railway up`.

- **Cloud API health**: `curl -fsS "$DIRT_CLOUD_API_BASE_URL/api/health" | jq .`
- **Hosted sync status**: login through the hosted UI, then use `/api/sync/status` from the browser session if you need the browser-shaped response.
- **Gateway service**: `systemctl --user {start,stop,restart,status} dirt-gateway`
- **Gateway logs**: `journalctl --user -u dirt-gateway -f` and `var/logs/cloud_gateway/YYYY-MM-DD.jsonl`
- **Disable hosted command creation**: set Railway `DIRT_CLOUD_COMMAND_CREATION_ENABLED=false` on `control-plane-api` and redeploy/restart through Railway. Read-only sync remains active.
- **Disable gateway command claiming**: set Railway `DIRT_CLOUD_GATEWAY_COMMAND_CLAIM_ENABLED=false` on `control-plane-api`; the gateway will continue read-only sync and asset retention but receive no commands to execute.

## Firmware

- **Firmware test**: `cd firmware && pio test -e native` (runs on host, no hardware needed)
- **Firmware build**: `cd firmware && pio run -e nano`
- **Firmware upload**: `cd firmware && pio run -e nano -t upload`

## Web UI

- **Dev server**: `pnpm --dir web-ui dev` (Vite on :5173, MSW mocks on)
- **Production build**: `pnpm --dir web-ui build` — writes `web-ui/dist/` which the running `dirt-web` service serves directly (SPA fallback + `/assets/` mount; no restart needed, just reload the browser).
- **Typecheck / lint / test**: `pnpm --dir web-ui {typecheck,lint,test}`

## Web API auth (when curl-ing dirt-web :8001)

`dirt-web` enforces cookie-session auth on every `/api/*` route except `/api/auth/*`. An unauthenticated `curl http://127.0.0.1:8001/api/...` returns `{"detail":"unauthorized"}`. **Prefer psql for ad-hoc state checks** — the DB has the same data without the auth dance. Only reach for the API when you specifically need an API-shaped response (e.g. reproducing a UI bug).

- **Credentials**: `AUTH_USERNAME` / `AUTH_PASSWORD` in `.env` (defaults `admin` / `changeme`). Loaded into `settings.auth_username` / `settings.auth_password` via Pydantic env mapping in `apps/shared/src/dirt_shared/config.py`.
- **Login + call pattern (with cookie jar):**
  ```bash
  set -a; source .env; set +a
  COOKIES=$(mktemp)
  curl -sS -c "$COOKIES" -H 'Content-Type: application/json' \
    -d "{\"username\":\"$AUTH_USERNAME\",\"password\":\"$AUTH_PASSWORD\"}" \
    http://127.0.0.1:8001/api/auth/login >/dev/null
  curl -sS -b "$COOKIES" http://127.0.0.1:8001/api/system/devices | jq .
  ```
- **MCP** (`/mcp` mount) uses a separate bearer token (`MCP_BEARER_TOKEN` env / `settings.mcp_bearer_token`), not the session cookie.

## PTZ camera

- **Go to a preset**: `scripts/camera look <overview|plant_a|plant_b|plant_c|plant_d|home>`
- **Relative move** (user-frame): `scripts/camera nudge left 5` or compound `scripts/camera nudge left=3 up=2`
- **Zoom**: `scripts/camera zoom +0.2` (relative) or `scripts/camera zoom-to 1.5` (absolute)
- **Current state**: `scripts/camera where` (adds `--json` for structured output)
- **Daemon status**: `systemctl --user status dirt-camera` / `journalctl --user -u dirt-camera -f`
- **Host-specific capture device**: set `DIRT_CAMERA_VIDEO_DEVICE=/dev/video0` in ignored `.env.dirt-camera` when the host does not provide `/dev/webcam`.
- **Full operational spec**: `wiki/hardware/ptz-camera.md`. Do NOT bypass the CLI by calling the daemon's socket directly or running debug/obsbot_* binaries — the CLI handles user-frame translation, preset lookup, and error reporting.

## Camera agent

Periodic PTZ capture on both mainbox and camera-only hosts uses the shared `CameraCapturePublisher`. On mainbox, `dirt-hwd` wires the publisher to `LocalSnapshotSink`, which writes local `snapshot` rows for the feed and gateway. On camera-only hosts such as `dirt2`, `dirt-camera-agent` wires the same publisher to `CloudAssetSink`, reads shared repo config from `.env` if present plus required host-local camera/cloud identity config from ignored `.env.dirt2-camera-agent`, fetches the camera capture policy from the hosted control plane, and uploads directly to hosted assets.

- **Service status (read-only)**: `systemctl --user status dirt-camera-agent --no-pager`
- **Recent logs (read-only)**: `journalctl --user -u dirt-camera-agent -n 100 --no-pager`
- **Follow logs (read-only)**: `journalctl --user -u dirt-camera-agent -f`
- **Manual foreground run (dev)**: `systemctl --user stop dirt-camera-agent && set -a; source .env; [ ! -f .env.dirt2-camera-agent ] || source .env.dirt2-camera-agent; set +a; uv run --package dirt-camera-agent python -m dirt_camera_agent.main --once`
- **Lights-off skip policy**: the agent calls `GET /api/gateway/v1/cameras/{camera_device_id}/capture-policy`; the hosted control plane derives the schedule from synced camera and lights rows with the same site/tent. Skipped cycles log `capture_skipped` and do not call the camera or upload a JPEG.

## Voice channel (Claudia)

- **Service status**: `systemctl --user status dirt-voice` / `journalctl --user -u dirt-voice -f`
- **Stop / start / restart**: `systemctl --user {stop,start,restart} dirt-voice`
- **Session transcripts**: `var/sessions/voice/YYYY-MM-DD.jsonl` — append-only, one JSON event per line (`wake`, `conversation_end`, etc.)
- **Emergency stop (bypass systemd)**: `kill $(cat var/logs/voice.pid)`. PID file is written on startup, unlinked on clean exit. Use over `pkill -f` — pattern matching the voice-channel string will SIGKILL the invoking shell.
- **Full operational spec**: `wiki/hardware/voice-channel.md` (pipeline, tools, config); `wiki/hardware/jabra.md` (device quirks). Do NOT run `python -m dirt_voice.channels.voice` directly while the service is up — both processes will fight for the Jabra ALSA handle.
- **Manual foreground run (dev)**: `systemctl --user stop dirt-voice && uv run --package dirt-voice python -m dirt_voice.channels.voice`. Restart the service when done.
- **Pipecat v1.0 is a major departure from v0.x** — training data will suggest obsolete patterns (`OpenAILLMContext`, `TransportParams(vad_analyzer=...)`, `allow_interruptions=True`). Always read `docs/references/pipecat/INDEX.md` before editing `apps/voice/src/dirt_voice/channels/voice.py`, `_audio_transport.py`, or `apps/voice/src/dirt_voice/tools/`.

## Daily report (automated 14:00 MDT)

- **Manual run**: `scripts/daily_report` (today, skip if marker exists) or `scripts/daily_report --force` (re-run today) or `scripts/daily_report --date 2026-04-19 --force`.
- **Service / timer status**: `systemctl --user status dirt-daily-report.timer` and `journalctl --user -u dirt-daily-report.service -n 100`.
- **Scoped inputs**: `DIRT_DAILY_REPORT_TENT_IDS` controls sensor sections, `DIRT_DAILY_REPORT_REQUIRED_TENT_IDS` controls validation-critical tents, and `DIRT_DAILY_REPORT_PHOTO_TENT_IDS` controls hosted tent overview photos. The systemd unit loads optional `.env.prod` so hosted signed-asset reads can use `DIRT_CLOUD_SESSION_SECRET` without printing it.
- **Marker files**: `var/logs/daily_report/<DATE>.completed` and `var/logs/daily_report/<DATE>.failed`. The `.completed` marker is what makes the next run skip — delete it (or pass `--force`) to re-run.
- **Synthesis trace**: `var/logs/daily_report/<DATE>.synthesis.json` — full sub-agent tool trace, usage, cost. Produced even on failure.
- **Failure → Telegram alert**: Phases 1–4 (capture, validate, snapshot, synthesize) all bail-on-fail and post a `<b>⚠ Daily report failed</b>` message to the configured chat. Phase 5 (Telegram delivery) is non-fatal — wiki is the durable record; failed deliveries log to journal only.
- **Pipeline source**: `apps/shared/src/dirt_shared/services/daily_report.py` (orchestrator), `apps/shared/src/dirt_shared/services/{photos,daily_sensors,daily_synthesis,telegram}.py` (per-phase). Workflow detail in `wiki/AGENTS.md` (Daily Update Workflow).
