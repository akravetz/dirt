# backend.wiki cluster — generator notes

Three filesystem-backed wiki endpoints wired as thin FastAPI wrappers
around the pre-existing `dirt_shared.services.wiki` service. All three
live in one router file (`apps/web/src/dirt_web/api/wiki.py`) and share
a single `fake_wiki` tmp_path-seeded fixture pattern in tests.

## Cluster-level summary

- **Delivered:** `GET /api/wiki/tree`, `GET /api/wiki/file`, `GET /api/wiki/search` — contract-shape responses validated by the generated `dirt_contracts.webapp_v1.models` pydantic models in every unit test.
- **Hot-spot refactor (shared):** `dirt_shared.services.wiki.WIKI_DIR` (module-level constant captured at import) was converted into a `wiki_dir()` function that reads `DIRT_WIKI_DIR` per-call. This lets the endpoint tests redirect the service at a tmp_path-seeded fake wiki via `monkeypatch.setenv` instead of `monkeypatch.setattr('dirt_shared.*')`, which the `test_no_patching_production_code` invariant forbids.
    - Side-effect: the `WIKI_DIR` module-level binding (a one-line default `Path` capture) would have tripped `test_no_module_level_singletons[dirt_shared]`, so it was removed entirely. `plant_detail.PlantDetailService.__init__` was the sole external consumer; it now calls `wiki_dir()` per-construction.
- **No off-limits writes.** Only `contract_status.json` was touched under `apps/tests/invariants/` (explicitly agent-editable).
- **Pre-existing invariant noise:** three `web-ui/` infra invariants (`test_eslint_printconfig_sentinels`, `test_tsc_showconfig_sentinels`, `test_no_unused_files_exports_or_deps`) fail on a fresh worktree until `pnpm --dir web-ui install --frozen-lockfile` has run — noted for future worktrees.

## Feature 1 — backend.wiki.tree

**Done.**
- Endpoint walks `wiki/` via `WikiService.get_tree()`, returns `{tree: [files_at_root..., folders...]}`.
- Plant folder children get the stable `sticker_color` (yellow/orange/pink/blue for `plant-a..d`). Non-plant folders and files have `sticker_color: null`.
- `CLAUDE.md` and hidden files/folders excluded per the service's `_IGNORED_NAMES`.

**Surprises / deviations:**
- The `WikiTreeResponse.tree` is a flat list of discriminated `WikiTreeNode` (file|folder). Root-level loose `.md` files are returned as top-level `WikiTreeFile` entries (type=file), *not* wrapped in a synthetic folder — this matches the `WikiTree` dataclass shape and API.md §9 example, and lets the SPA render loose files separately.

**Unit tests:** `apps/web/tests/test_wiki_tree_endpoint.py` — auth required; contract shape; plant sticker colors; concept-folder sticker is null.

## Feature 2 — backend.wiki.file

**Done.**
- Endpoint accepts `?path=foo/bar.md` or `?path=wiki/foo/bar.md` (service's `_normalize_path` handles both).
- Traversal (`../etc/passwd`) → 400 JSON error (service raises `ValueError`).
- Nonexistent but safe path → 404 (service returns `None`).
- Empty/missing `path` → 422 from FastAPI's `Query(..., min_length=1)`.
- Response carries `frontmatter` (parsed YAML subset), raw `body_markdown` (frontmatter stripped), optional `subtitle` (first italic line after H1), and `backlinks` (via the service's mtime-cached grep pass).

**Surprises / deviations:**
- Contract says traversal → 400 "with 400" (see yaml description on the `path` param); implemented as 400 accordingly. Nonexistent file → 404 (contract has both 400 and 404 declared). Clean split: 400 = malformed input, 404 = well-formed-but-missing.

**Unit tests:** `apps/web/tests/test_wiki_file_endpoint.py` — auth required; full payload shape including subtitle + frontmatter + backlink recovery; `wiki/`-prefixed path aliasing; 400 traversal; 404 missing; 422 empty.

## Feature 3 — backend.wiki.search

**Done.**
- Endpoint dispatches to `WikiService.search(q)`, returns `{q, results: [{path, title, match_type, snippet?}]}`.
- Ranking: `title` > `path` > `content`; each file classified once.
- Empty/missing `q` → 422 (FastAPI `min_length=1`); whitespace-only `q` → 400 (the service would otherwise return everything — the explicit branch here preserves the "no implicit-all-match" contract invariant called out in API.md §9).

**Surprises / deviations:**
- None. Service-side behavior is appropriate for V1; test seeds three files that hit each match-type branch.

**Unit tests:** `apps/web/tests/test_wiki_search_endpoint.py` — auth required; title-over-content ranking; path-only hit; 400 whitespace `q`; 422 empty `q`; no-match empty array.

## Next

- Frontend `frontend.wiki` feature is unblocked (its `depends_on` listed all three of these, plus `frontend.app.shell`/`mocks.setup`/`e2e.setup`). All three endpoints are served under cookie-session auth; the generated `openapi-fetch` client in `web-ui/src/api-client/generated/` already carries the operation ids (`wikiTree`, `wikiFile`, `wikiSearch`).
- `PlantDetailService` no longer captures `WIKI_DIR` at import time — downstream tests that previously relied on a fixed module-level value may need to construct the service with an explicit `wiki_root=` or rely on the `DIRT_WIKI_DIR` env var.
