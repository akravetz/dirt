# backend.camera cluster — generator notes

Six-feature backend cluster shipping the camera domain as
contract-shaped JSON endpoints. Six thin FastAPI wrappers over the
existing `dirt-camera` daemon protocol (`get_state`, `move_motor`,
`set_zoom`) plus the on-disk `~/.config/dirt/camera.json` preset
config.

## Cluster-level summary

- **New shared service**: `apps/shared/src/dirt_shared/services/ptz.py`
  (`PTZService`, `UnknownPresetError`, motor-limit + look-range
  constants). Constructor-injectable RPC + config_path so tests drive
  it without a daemon socket.
- **New router**: `apps/web/src/dirt_web/api/ptz.py` — 4 endpoints
  sharing one `PTZService` resolved via `get_ptz` from app.state.
- **Extended router**: `apps/web/src/dirt_web/api/feed.py` —
  `/api/feed/live.jpg` + `/api/feed/snapshot/latest` replace the old
  `/feed/*` HTMX/image routes and `/api/snapshots/latest`.
- **Deleted**: `apps/web/src/dirt_web/api/snapshots.py` and its test
  file; the three HTMX handlers on the old feed router.
- **New deps providers**: `get_ptz`, `get_frame_capturer` in
  `apps/web/src/dirt_web/deps.py`.
- **Contract bookkeeping**: all 6 endpoints removed from
  `expected_missing`; both legacy entries (`GET /feed/live|image|status`,
  `GET /api/snapshots/latest`) removed from `legacy_routes`.
- Daemon wire protocol is `get_state` / `move_motor <pitch> <yaw>` /
  `set_zoom <value>` (see `services/camera-daemon/README.md`). The
  prompt's conceptual RPC names (`look_preset`, `look_at_motor_xy`,
  `zoom_to`, `zoom_by`) are implemented as `PTZService` methods that
  issue the real wire commands.

## Drive-by fix folded into commit 1

`apps/shared/tests/test_grow_state.py::test_current_targets_tracks_stage`
was asserting against the live wall clock (flower_start_date +
(today - flower_start).days). It failed today (2026-04-22) because
day-21+ flips the stage to `flower_late`, making the test non-
deterministic past 2026-04-21. Fixed by threading the existing `_svc`
fixture's frozen-clock helper through both assertions. Unblocks the
pre-commit hook for every future commit on any branch.

## Per-feature notes

### 1. backend.feed.live (commit 4408af5)

- New: `GET /api/feed/live.jpg` with `Cache-Control: no-store`.
- Delegates to `capture_frame()` via a `get_frame_capturer` DI seam
  so tests can inject a fake. Added to `deps.py`.
- Dropped: `/feed/live`, `/feed/image` (HTMX fragment), `/feed/status`
  (HTMX fragment). Legacy-route assertion in the test checks the
  registered-routes table rather than transport-level 404 — the
  `SPAFallbackMiddleware` rewrites non-`/api/` 404s to 503/200 so a
  plain `client.get('/feed/live')` doesn't reach the assertion.

### 2. backend.feed.snapshot (commit 3dc925f)

- New: `GET /api/feed/snapshot/latest` on the feed router.
- Deleted `apps/web/src/dirt_web/api/snapshots.py` +
  `apps/web/tests/test_snapshots_api.py`. `app.py` no longer imports
  the snapshots router.
- Reuses `SnapshotsService.latest` + `get_snapshot_path` — no service
  changes.

### 3. backend.ptz.state (commit 4f19a2d)

- New service module `dirt_shared.services.ptz` — not a DB-backed
  service, just a daemon+config facade. Constructor:
  `PTZService(rpc=..., config_path=..., sticker_colors=...)`.
- Preset list parsed from `~/.config/dirt/camera.json` with
  underscore-prefixed keys stripped (the repo's comment convention).
  Labels are title-cased from the id (`plant_a` → `Plant A`).
  Sticker color is augmented from a module-level default map
  (A=yellow, B=orange, C=pink, D=blue) because `camera.json` doesn't
  carry colors; the contract wants them per preset.
- `preset` field in the response matches against current state with
  `PRESET_TOLERANCE_DEG=2.0` + `PRESET_TOLERANCE_ZOOM=0.1`.
- When the daemon is unreachable, the response still carries the
  preset list (FE renders the preset row regardless) with
  `connected: false`.

### 4. backend.ptz.preset (commit 0343f20)

- New: `POST /api/ptz/preset/{id}`. Validates against `camera.json`
  → 404 with `UnknownPresetError` message if unknown.
- Issues `move_motor` + `set_zoom` concurrently via `asyncio.gather`
  — the two commands don't interact on the daemon side and the tent
  moves faster.
- `ok: false` path returns `preset: null` so the FE can't
  false-positive the indicator on a partial failure.

### 5. backend.ptz.look (commit 7b9f004)

- New: `POST /api/ptz/look`. Server-side math: `yaw_delta = x * 60°`,
  `pitch_delta = y * 40°` (module constants `LOOK_YAW_RANGE_DEG` /
  `LOOK_PITCH_RANGE_DEG`).
- Clamp is applied BEFORE the `move_motor` RPC (yaw: [-150, 150],
  pitch: [-90, 30]). Test asserts the clamp happens pre-RPC by
  inspecting the recorded command string, not just the response.
- Pydantic body validator (generated) has `extra="forbid"` +
  `confloat(ge=-0.5, le=0.5)`, so 422s come from FastAPI validation
  without any hand-written guard in the endpoint.

### 6. backend.ptz.zoom (commit e2941d7)

- New: `POST /api/ptz/zoom`. XOR via `has_zoom == has_delta` → 400
  when neither or both fields are present.
- Absolute path: single `set_zoom` RPC.
- Relative path: `get_state` to read current zoom, then `set_zoom
  (cur + delta)`, with `ZOOM_MIN=1.0` / `ZOOM_MAX=2.0` clamp in
  `zoom_to`.

## Surprises

- The `test_grow_state.py` wall-clock dependency (see above) — not
  camera-related but blocked every commit in the cluster.
- `SPAFallbackMiddleware` changes what "route not found" looks like
  at the transport layer. The legacy-route test for the three `/feed/*`
  paths has to assert against `app.routes` directly, not `response.
  status_code == 404`.
- Ruff flagged the `id` path parameter as shadowing the builtin
  (rule A002). The OpenAPI spec uses `{id}` and the generator-produced
  path operation mirrors it; the comment explains why we keep the
  name.

## Not-done

None — all 6 features landed with invariants + unit tests green.
