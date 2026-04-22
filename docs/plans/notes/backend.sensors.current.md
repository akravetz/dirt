# backend.sensors.current — generator notes

## Status: DONE

## What landed

- `GET /api/sensors/current` handler in `apps/web/src/dirt_web/api/sensors.py`,
  registered via the existing `sensors_router` (no `app.py` changes needed —
  it's already `include_router`'d). Response is the contract's
  `SensorsCurrent` model composed from:
  - `ReadingsService.get_latest_reading()` for temperature_f / humidity_pct /
    vpd_kpa.
  - `STAGE_TARGETS[stage]` + `band_status(value, band)` for target bands and
    ok|warn|crit classification (server-computed — client is a pure renderer).
  - `mock_sensors.get_fan_pct(ts)` / `get_reservoir_in(ts)` for the two
    metrics we don't have hardware for yet. Pure functions keyed on the
    envelope's top-level ts so the dashboard's "as of …" label stays
    coherent across tiles.
  - `ReadingsService.is_sensor_stale()` for the `stale` flag.
- Legacy `GET /sensors/current` HTMX fragment route deleted; its test
  (`test_current_readings` in `test_sensors_api.py`) removed.
- `contract_status.json` updated — removed the `expected_missing` entry for
  `GET /api/sensors/current` and the `legacy_routes` entry for
  `GET /sensors/current` in the same commit.
- Added `ReadingsService.now()` as a test seam — the endpoint's
  cold-cluster `top_ts` fallback reads from the injected clock rather than
  calling `datetime.now(UTC)` directly, satisfying
  `test_no_concrete_clock_in_production`.
- Simplify pass concurrency-gathered the five independent DB calls
  (stage, temp, hum, vpd, stale) into one `asyncio.gather` — 5x fewer
  round-trips on every dashboard render.

## Acceptance evidence

- **invariant**: `uv run pytest apps/tests/invariants/ -q` → 96 passed.
  `contract_status.json` changes verified by
  `test_api_contract.py::test_expected_missing_entries_are_actually_missing`
  and `test_legacy_routes_still_present`.
- **unit**: `uv run pytest apps/web/tests/test_sensors_current_endpoint.py -v`
  → 3 passed:
  - `test_sensors_current_requires_auth` — unauth GET returns 401 JSON.
  - `test_sensors_current_returns_contract_shape` — all 5 metrics
    populated, target bands present on temp/humidity/VPD, absent on
    fan/reservoir, status=ok for seeded-in-band values.
  - `test_sensors_current_stale_flag` — stale flag true when identical
    readings exceed the service's default threshold (read from the
    function signature, not hardcoded — per the prompt's "use the
    service's own threshold; don't hardcode" instruction).
- Full web suite: 30 passed. All-app suite (`apps/hwd apps/web apps/shared
  apps/mcp apps/voice`): 145 passed.

## Interpretation note — "stale" semantics

The feature prompt says "stale flag is true when the latest reading
exceeds a staleness threshold". The frozen API spec
(`docs/proposals/API.md` §3) documents `stale` as "sensor-stuck flag"
and explicitly says it wraps `is_sensor_stale()` — which in the current
implementation means "last N temperature_f readings are identical"
(value-stuck, not age-exceeded). I implemented per the contract. The
test follows the prompt's "use the service's own threshold" instruction
by reading `is_sensor_stale`'s default via `inspect.signature` so it
never hardcodes `10`.

If the planner intended an age-based threshold, the service needs a
new method (not just a different test) — flagging as a potential
spec-level clarification, not a generator-side fix.

## Pre-flight environment gotcha

The pre-flight `uv run pytest apps/tests/invariants/ -q` failed at the
start of this run with 3 frontend invariants red
(`test_typescript_dead_code`, `test_tsc_showconfig_sentinels`,
`test_eslint_printconfig_sentinels`) — all three were caused by the
worktree having no `web-ui/node_modules` directory yet. Running
`pnpm --dir web-ui install` (656ms, no script prompts accepted) fixed
them without any code change. This might be worth mentioning in the
generator-prompts doc so future BE worktrees don't burn iterations on
FE-tooling red herrings.

## Pre-commit gotcha (workflow)

Pre-commit stashes unstaged changes and runs against staged state
only. During one iteration I had `apps/shared/...readings.py`
unstaged while `apps/web/tests/test_sensors_current_endpoint.py` was
staged; the hook saw the tests without the implementation and
reported 404. The fix is `git add -A` before `git commit`, which the
generator-prompts doc already prescribes — reminder for future
runs.

## Commits on branch

1. `feat(backend.sensors.current): GET /api/sensors/current with bands+status+stale`
2. `chore(backend.sensors.current): simplify pass`
3. `docs(backend.sensors.current): generator notes` (this commit)
