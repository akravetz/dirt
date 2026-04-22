# Generator notes — backend.plants cluster

Three backend features landed in one worktree (branch
`feat/be/plants-cluster`), each as its own `feat(...)` commit with
simplify folded in:

1. `backend.plants.list` — `GET /api/plants`
2. `backend.plants.detail` — `GET /api/plants/{code}`
3. `backend.plants.moisture` — `GET /api/plants/{code}/moisture`

## Cluster summary

All three endpoints are thin FastAPI wrappers around
`PlantsService` + `PlantDetailService`; the services were already shaped
to match the contract. Wiring added:

- `dirt_web/api/plants.py` — new router, one file per resource.
- `dirt_web/app.py` — `include_router(plants_router)`.
- `dirt_web/deps.py` — new `get_plants` provider.
- `dirt_shared/services/plants.py` — added `PlantsService.now()` so API
  handlers can derive range cutoffs through the injected clock without
  tripping the no-concrete-clock-in-production invariant.

Contract bookkeeping: all three entries removed from
`apps/tests/invariants/contract_status.json#expected_missing`. Plan
JSON lists no `removes_legacy` for any of the three features, so
`legacy_routes` is untouched.

## Per-feature detail

### 1. `backend.plants.list`

- **Endpoint**: `GET /api/plants` → `PlantsResponse { day, plants[] }`.
- **Implementation**: `plants_list()` awaits `PlantsService.list_plants`
  + `GrowStateService.get_grow_current_payload` (for the top-level
  `day`), converts each `PlantSummary` dataclass to the contract
  `Plant` model.
- **Tests**: `apps/web/tests/test_plants_list_endpoint.py` — auth gate,
  cold-cluster (no readings → null moisture), happy path with a seeded
  calibration + reading on plant-a (raw=380, cal=[0,1000] → 62%).

### 2. `backend.plants.detail`

- **Endpoint**: `GET /api/plants/{code}` → `PlantDetail`.
- **Implementation**: `plants_detail()` validates `code` against
  `PlantCode` (a|b|c|d) and 404s on anything else — chosen over letting
  FastAPI's enum validation 422 so the contract's "404 for unknown
  plant id" mapping holds (API.md §"Errors"). Delegates to
  `PlantsService.get_plant_detail_payload(code)` which composes the DB
  row + live moisture + parsed wiki. The method on the service is
  `get_plant_detail_payload`, not `get_plant_detail` as the spawn
  prompt's "note: the method is `get`, not `get_plant_detail`" implied
  — `get()` is actually on `PlantDetailService`, not `PlantsService`.
  The endpoint goes through `PlantsService` since it needs the live
  moisture join too; no plan deviation.
- Timeline entries are filtered to ones with both `date` and `day >= 1`
  so the contract `TimelineEntry` validator passes (the wiki parser
  emits `None` for either when a bullet doesn't match the expected
  shape).
- `note` is only populated when the wiki parse produced BOTH a text
  paragraph AND an `updated` frontmatter date; the contract requires
  `updated` on non-null notes so a partial note is dropped.
- `label` falls back to the empty string when the DB row has
  `label=NULL` — contract requires `str`, not `str | None`.
- **Tests**: `test_plants_detail_endpoint.py` — auth gate, 404 for
  unknown code, happy path against the template-seeded plant-a.md (the
  wiki file ships with the repo, so the note + timeline assertions are
  stable), cold-cluster null-moisture case.

### 3. `backend.plants.moisture`

- **Endpoint**: `GET /api/plants/{code}/moisture?range=1h|24h|7d` →
  `PlantMoistureHistory`.
- **Implementation**: `plants_moisture()` reuses
  `PlantsService.get_plant_moisture_history` + the existing
  `count_irrigation_events` heuristic (upward jumps ≥ 5% between
  adjacent samples — the default already encoded in the service
  module).
- Irrigation-events-in-24h is deliberately computed over a **24h
  window regardless of the requested range** so the drawer's "events
  today" badge reads the same when the user toggles 1h / 24h / 7d.
  When `range=1h`, the endpoint fetches the 24h series in parallel
  with the 1h series via `asyncio.gather` — saves the sequential
  round-trip. When `range ∈ {24h, 7d}` the 24h window is a subset of
  the already-fetched points, so we filter in memory instead of
  re-querying.
- Uses `plants.now()` (new method, see above) instead of
  `datetime.now(UTC)` to satisfy the no-concrete-clock invariant.
- **Tests**: `test_plants_moisture_endpoint.py` — auth gate, 404
  unknown code, 422 invalid range (FastAPI enum validation), empty
  series (no readings → empty points, 0 events, target band still
  populated from the Plant row's defaults), 24h happy path with three
  seeded irrigation events, 1h range preserves the 24h event count
  (coverage of the parallel-query branch).

## Surprises / deviations

- **Node_modules missing in this worktree** — first commit's
  pre-commit hooks tripped `test_webui_invariants_wired.py` /
  `test_typescript_dead_code.py` because the worktree lacked a
  `web-ui/node_modules/`. Fixed in-place with
  `pnpm --dir web-ui install --prefer-offline`. Not a code issue,
  just a worktree-provisioning step worth noting in the cluster
  runbook. After that, all 98 → 106 invariants passed cleanly.
- **Clock-boundary invariant hit on feature 3** — first draft of
  the moisture endpoint called `datetime.now(UTC)` directly and tripped
  `test_no_concrete_clock_in_production`. Fixed by adding
  `PlantsService.now()` mirroring `ReadingsService.now()`. The
  invariant pointer was clear; no deviation from the spirit.
- **Spawn-prompt nit**: the prompt for feature 2 said
  `PlantDetailService.get(code)` is the method; that's correct, but the
  endpoint in practice goes through `PlantsService.get_plant_detail_payload`
  because it also needs the live DB moisture join. The plan JSON's
  `implementation_notes` already matched this reality.

## Not done / next

Everything in the cluster's scope is committed and green. No follow-ups
queued.
