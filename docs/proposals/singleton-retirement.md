# Singleton Retirement: engine + settings → constructor DI

**Status:** in progress
**Started:** 2026-04-19
**Drives:** Invariant C (no module-level singletons) green;
            Invariant B (no patching production code) ~12 violations eliminated;
            Invariant E (no bare app imports in tests) green.

## Problem

Two module-level singletons keep ~30 modules in dirt entangled with global
state and force ~12 `mock.patch("dirt_*")` calls in tests:

- `apps/shared/src/dirt_shared/db.py:21` — `engine = create_async_engine(...)`
- `apps/shared/src/dirt_shared/config.py:100` — `settings = Settings()`

The `_ENGINE_HOLDERS` registry at `apps/shared/src/dirt_shared/testing.py:180`
enumerates 8 production modules whose module-level `engine` binding is
monkey-patched per test. That registry **is the architectural debt expressed
as code.** Deleting it is the success metric.

## Architectural target

Three layers:

1. **Service classes** with constructor DI:
   `class ReadingsService: def __init__(self, engine, config): ...`
   Testable in isolation, no FastAPI involvement.

2. **FastAPI `Depends` providers** at the API layer:
   `def get_readings(request) -> ReadingsService: return request.app.state.readings`
   Tests use `app.dependency_overrides[get_readings] = lambda: FakeReadings()`
   instead of `mock.patch`.

3. **`create_app(...)` factory** as the composition root:
   `app = create_app(engine=test_engine, background_services=[])` for tests;
   `app = create_app()` at module level for `uvicorn dirt_<app>.app:app`.

Settings becomes purpose-specific dataclasses (`CaptureConfig`, `ArchiveConfig`,
…) sliced from a `Settings` object at the composition root. Services take the
slice, not the whole `Settings` — keeps signatures honest about what each
service depends on.

## Phased PR sequence (merge-safe at each step)

| PR | Scope | Risk | Ends with |
|----|-------|------|-----------|
| 0  | `app_engine` fixture sibling + this doc | none | tests still green |
| 1  | `SnapshotsService` worked example + `create_app` skeleton on web | low | one service migrated; user review gate |
| 2  | Convert remaining read services (readings, grow_state, plants, humidifier_state, system_status, plant_detail) with delegate functions for back-compat | low | back-compat preserves old call sites |
| 3  | Settings refactor — purpose-specific dataclasses; delete module-level `settings = Settings()` | medium | invariant C: `Settings()` violation gone |
| 4  | Background loops → classes; hwd test fixtures use `create_app(background_services=[])` | medium | invariant B: ~10 patches eliminated |
| 5  | **Touches hwd.** Delete delegates, retire engine singleton, delete `_ENGINE_HOLDERS`. | **HIGH** | invariants C+B green; Invariant E enabled |
| —  | (Invariant E ships in PR 5 atomically, not as a separate PR) | | |

## Decisions made (locked)

1. **Settings shape:** purpose-specific dataclasses, not whole-`Settings` injection.
2. **dirt_voice:** in scope (PR 5). Calls `build_core_services()` at voice startup since it's not a FastAPI app.
3. **Invariant E timing:** lands in PR 5 same-PR with the implementation.
4. **`scripts/daily_report`:** stays a script outside `apps/*/src/`, exempt from the invariant scope. Becomes a composition root in its own right.
5. **Observability `settings.data_dir`:** drop the settings fallback; `DIRT_LOGS_DIR` env var is authoritative (matches existing test isolation pattern).

## Risk: PR 5 touches hwd

`apps/hwd/` is described in CLAUDE.md as "OFF-LIMITS to routine rewrites — it's the keep-alive daemon running in production." This refactor touches it because `apps/hwd/src/dirt_hwd/app.py` is the composition root for hwd's engine + four background loops.

**Mitigations baked into PR 5:**

- Add `apps/hwd/tests/test_app_factory.py` and `test_humidifier_loop_unit.py` BEFORE modifying production code.
- Smoke test: dev-machine boot, verify all four loops log "Starting X loop" within 5 sec; hit `/api/ingest/sensors`; let run 10 min; verify snapshot JPEG + DB write; graceful SIGTERM.
- Module-level `app = create_app()` preserved in `hwd/app.py` so the systemd unit (`uvicorn dirt_hwd.app:app`) doesn't need updating.
- Rollback: single-commit `git revert <sha>` + `systemctl --user restart dirt-hwd`.
- **User sign-off gate** before merging PR 5.

## Definition of done

```bash
uv run pytest apps/tests/invariants/                          # all 4 invariants green
uv run pytest -q                                              # full suite green
uv run ruff check                                             # no new lints
grep -rn "_ENGINE_HOLDERS" apps/                              # zero results
grep -rn "engine = create_async_engine" apps/shared/src/      # zero results
grep -rn "settings = Settings()" apps/shared/src/             # zero results
grep -rn "from dirt_shared.db import engine" apps/ scripts/   # only composition roots
```

After: any new service is a `class FooService: def __init__(self, engine, config)` with a 2-line `get_foo(request)` provider. No registry to update, no monkey-patching to add.

## Worked example (PR 1)

Concretely, `SnapshotsService` migration:

**Service module:**
```python
# apps/shared/src/dirt_shared/services/snapshots.py
class SnapshotsService:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def latest(self) -> Snapshot | None: ...
    async def list_recent(self, limit: int = 24) -> list[Snapshot]: ...
```

**Provider:**
```python
# apps/web/src/dirt_web/deps.py (new)
def get_snapshots(request: Request) -> SnapshotsService:
    return request.app.state.snapshots
```

**Endpoint:**
```python
# apps/web/src/dirt_web/api/snapshots.py
@router.get("/latest")
async def latest_snapshot(snaps: SnapshotsService = Depends(get_snapshots)):
    return await snaps.latest()
```

**App factory:**
```python
# apps/web/src/dirt_web/app.py
def create_app(*, engine=None, settings=None, run_mcp=True) -> FastAPI:
    settings = settings or Settings()
    engine = engine or create_async_engine(settings.database_url)
    app = FastAPI(title="Dirt Web", lifespan=lifespan)
    app.state.engine = engine
    app.state.snapshots = SnapshotsService(engine)
    # ... more services in PR 2
    return app

app = create_app()  # preserves uvicorn dirt_web.app:app
```

**Test (no patches):**
```python
async def test_latest_snapshot(pg_engine):
    snaps = SnapshotsService(pg_engine)
    # seed via pg_engine directly
    assert (await snaps.latest()).id == 1
```

Same shape applied to all 8 services in PRs 2–5.

## Origin

Plan generated by Plan subagent on 2026-04-19 from a brief that included the
current state of the three invariant tests, the `SessionManager` precedent
landed earlier in the same session, the hwd off-limits constraint, and the
FastAPI `dependency_overrides` discussion. Full plan in conversation history.
