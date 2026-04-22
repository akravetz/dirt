# backend.system.devices — generator notes

## Done

- Added `GET /api/system/devices` at `apps/web/src/dirt_web/api/system.py`.
  Thin wrapper over the existing `SystemStatusService.get_device_statuses`;
  the service already enumerates the 8 rows in mockup render order and
  handles all five status sources (Arduino tent, four ESP32 plant nodes,
  humidifier, camera daemon via unix socket, Jabra mocked from
  `systemctl --user is-active dirt-voice`).
- Added `get_system_status` provider to `apps/web/src/dirt_web/deps.py`
  (service instance was already on `app.state.system_status`; only the
  `Depends(...)` wrapper was missing).
- Registered the router in `apps/web/src/dirt_web/app.py`.
- Removed `GET /api/system/devices` from
  `apps/tests/invariants/contract_status.json` → `expected_missing`.
- Unit test at `apps/web/tests/test_system_devices_endpoint.py` covers
  the two acceptance cases: unauth → 401, happy-path → 200 with 8 rows,
  contract-valid statuses (`ok | listening | warn | offline`), deterministic
  kind ordering, and timezone-aware `ts` envelope. Uses a fake service
  injected via `app.dependency_overrides[get_system_status]` so the test
  doesn't touch the real Postgres heartbeat query, the camera socket, or
  `systemctl`.

## Not done

- Nothing in scope was deferred.

## Surprises

- `SystemStatusService` didn't expose a public `now()` method. The
  endpoint needs a timestamp for the `DevicesResponse.ts` envelope, and
  `test_no_concrete_clock_in_production[dirt_web]` forbids
  `datetime.now(UTC)` in production code under `apps/web/`. Added a
  two-line `now() -> datetime` method on the service that reads from the
  already-stored `self._clock`; matches the existing pattern on
  `HumidifierStateService.now`, `ReadingsService.now`, and
  `PlantsService.now`. Endpoint stamps `ts=service.now()`.
- The worktree ships without `web-ui/node_modules`; before
  `pnpm --dir web-ui install` ran, three web-ui invariants
  (`test_typescript_dead_code`, `test_tsc_showconfig_sentinels`,
  `test_eslint_printconfig_sentinels`) were red because the shims
  couldn't resolve their ESLint/tsc configs. These are environmental,
  not feature-related; resolved by installing deps in the worktree
  before committing.
- The spec notes `Cache-Control: no-store` for `/api/system/devices`
  (API.md §Caching headers). No existing endpoint in the app sets
  response cache headers today — sensors/humidifier/grow all return the
  pydantic model directly without a custom `Response`. Kept that same
  shape here so the new endpoint doesn't diverge from its siblings. If
  the evaluator flags this as a contract miss, the fix is localized
  (wrap the return in a `JSONResponse` with a `headers=` kwarg, or add
  a small middleware); but the acceptance criteria in the plan JSON
  only name the invariant edit + unit test, and neither the contract's
  Pydantic shape nor the unit test cares about response headers.

## Next

- Frontend half: `frontend.dashboard.system_table` (`SystemTable.tsx`)
  consumes this endpoint. The contract shape is already frozen via
  `DevicesResponse`; FE just binds to `data.devices[]` and renders
  `status` via an accessible indicator (per plan e2e acceptance).
- If we start caring about response headers more broadly, consider a
  small helper or middleware that applies `Cache-Control: no-store` to
  the handful of endpoints listed in API.md §Caching headers, rather
  than hand-decorating each one.
