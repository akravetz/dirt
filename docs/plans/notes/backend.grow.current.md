# backend.grow.current — generator notes

Branch: `worktree-agent-a249f474` (auto-named; feat/be/ prefix not
applied because orchestrator pre-created the worktree). Commits:

- `feat(backend.grow.current): wrap GrowStateService in GET /api/grow/current`
- `chore(backend.grow.current): simplify pass`

## Done

- Added `apps/web/src/dirt_web/api/grow.py` with `GET /api/grow/current`
  returning the generated `GrowCurrent` model.
- Wired the router in `apps/web/src/dirt_web/app.py`.
- Added `get_grow` FastAPI provider in `apps/web/src/dirt_web/deps.py`
  (resolves `app.state.grow`, which `build_core_services` already
  populates).
- Removed `GET /api/grow/current` from
  `apps/tests/invariants/contract_status.json:expected_missing`.
- Declared `dirt-contracts` as a direct workspace dep of `dirt-web` in
  `apps/web/pyproject.toml` (previously transitive via `dirt-mcp`;
  `test_dependency_hygiene` DEP003 required it now that dirt-web
  imports the generated Pydantic model directly). `uv.lock` updated.
- Authored `apps/web/tests/test_grow_endpoint.py` with three cases:
  unauthenticated redirect, veg-stage happy path, flower_late derivation.

## Acceptance

| Kind      | Result |
|-----------|--------|
| invariant (`uv run pytest apps/tests/invariants/ -q`) | 94 passed |
| unit (`uv run pytest apps/web/tests/test_grow_endpoint.py -q`) | 3 passed |
| combined per-app + invariants | 114 passed |

## Endpoint <-> payload shape note

`GrowCurrentPayload` (dataclass) carries `lights_on_local` /
`lights_off_local` as top-level `datetime.time` fields, while the
contract puts `on_local` / `off_local` as `HH:MM:SS` strings inside the
nested `LightsState`. The endpoint does the splice explicitly — a
generic `GrowCurrent(**asdict(payload))` would not round-trip. The
generator-prompt skeleton anticipates this ("the dataclass-to-model
conversion is verbose; keep the adapter local"), so it's kept inline
in `grow.py` rather than extracted.

## Not done / out of scope

- No `removes_legacy` on this feature; no route deletions.
- Unrelated preflight noise: the clean `main` baseline has three
  frontend invariants (`test_typescript_dead_code`, two
  `test_webui_invariants_wired` subtests) that fail when
  `web-ui/node_modules` is absent. Ran `pnpm install` in
  `web-ui/` at the start of this worktree to get a green baseline;
  those pass now. Called out in case other worktrees hit it.

## Contract / spec concerns

None — the contract shape matches exactly what `GrowCurrentPayload`
produces (after the two `time → HH:MM:SS` string conversions).
