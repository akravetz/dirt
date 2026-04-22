# backend.sensors.history — generator notes

## What landed

- `GET /api/sensors/history?range=<1h|24h|7d>&metric=<SensorMetric>` wired
  into `apps/web/src/dirt_web/api/sensors.py`, typed as
  `response_model=SensorsHistoryResponse`.
- `ReadingsService.get_metric_history(metric, range_key)` on
  `apps/shared/src/dirt_shared/services/readings.py` — native-datetime
  bucketed points for DB-backed metrics. Introduces `_BUCKET_SQL_NATIVE`
  alongside the legacy `_BUCKET_SQL` so the contract path doesn't
  re-parse 'Z'-suffixed label strings. Adds a small `_as_utc` normaliser
  for the aware/naive asyncpg return mismatch.
- Mock metrics (`fan_pct`, `reservoir_in`) synthesize via the existing
  `get_fan_history` / `get_reservoir_history` helpers in
  `mock_sensors.py` — shape-identical series to the DB path, bounded
  to the documented physical ranges.
- Legacy `GET /api/sensors/readings` handler removed; its test file
  (`apps/web/tests/test_sensors_api.py`) deleted in the same commit.
- Contract bookkeeping in `apps/tests/invariants/contract_status.json`:
  `expected_missing["GET /api/sensors/history"]` dropped;
  `legacy_routes["GET /api/sensors/readings"]` dropped.
- Unit suite: `apps/web/tests/test_sensors_history_endpoint.py` (11
  cases). Covers auth 401, happy-path shape across all three ranges for
  DB-backed metrics, happy-path for both mocks, 4xx on invalid range,
  4xx on invalid metric, 4xx on missing required params, and 404 on the
  now-deleted legacy route.

## Acceptance status

- `kind: invariant` — `apps/tests/invariants/test_api_contract.py` all
  21 tests pass (95/95 invariants overall after `pnpm install` in the
  worktree; 3 TS-wired invariants require `web-ui/node_modules` which
  is not committed).
- `kind: unit` — `apps/web/tests/test_sensors_history_endpoint.py` 11/11
  pass.

## Design notes

- FastAPI rejects out-of-enum `Range` / `SensorMetric` query params
  with 422, not the contract's specified 400. Treated as compatible
  (same "invalid input" semantics; SPA treats any 4xx as "don't retry")
  and the tests assert `400 <= status < 500` rather than pinning a
  specific code. If the FE needs a stricter shape, a thin exception
  handler can narrow this later without changing the endpoint.
- Per-metric units are duplicated between `sensors_current` (inline
  literals) and the new `_METRIC_UNITS` map. Consolidating them is a
  nice-to-have but touches the `sensors.current` feature code, so left
  as-is to keep the diff feature-local.
- Bucket-point counts for mock metrics mirror DB-backed density (60 /
  288 / 168 for 1h / 24h / 7d) — arbitrary but reasonable for a
  sparkline. No direct mapping to the DB's 1h raw mode (which has no
  bucketing).

## Out-of-scope observations

- `_BUCKET_SQL` still declares a `30d` key that `RANGE_DELTAS` also
  supports, but the new `Range` contract enum drops it. The legacy
  `get_sensor_history` path keeps `30d` usable internally. If the FE
  migration fully removes the legacy callers, the `30d` arms can come
  out of both tables; not in this feature's scope.

## Pre-flight note

Ran `pnpm install` inside `web-ui/` at start-of-work to unblock the 3
TS-wired invariants (`test_tsc_showconfig_sentinels`,
`test_eslint_printconfig_sentinels`, `test_no_unused_files_exports_or_deps`)
which had been red from missing `node_modules`. No `pnpm-lock.yaml`
change was produced; `node_modules/` is gitignored. Flag this for the
orchestrator in case other worktrees hit the same 3 failures on a cold
clone.
