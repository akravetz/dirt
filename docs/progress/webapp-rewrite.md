# Webapp rewrite — agent handoff

**Status (2026-04-20, end of session 3)**:
- ✅ **Phase 0** — uv workspace + hardware-daemon split. Harness installed. `web-ui/` skeleton exists.
- ✅ **Phase 1 design** — API + data-model proposals written and agreed (`docs/proposals/{API.md, data_model.md}`). Postgres cutover executed (ADR-006). New service modules that back the future endpoints are implemented and tested. Test suite green on Postgres (143 tests).
- ✅ **Architectural-invariant hardening (session 3)** — full per-language invariant suites landed: PY-01..09 (layered contracts, no-asyncio-run, no-print, no-module-level-singletons, ruff TID/PLR/RUF/S audit, Hypothesis at pure-function boundaries, etc.) under `apps/tests/invariants/`; TS-01..16 (tsconfig strict, eslint-plugin-boundaries, banned training-data-drift imports, no `enum`/`namespace`/`as any`, no fetch outside api-client, no `useEffect` data-fetching, no string-literal route paths, Tailwind v4 palette guard, no inline style, knip dead-code, etc.) under `web-ui/invariants/`; XX-01/02 meta rules (uniform failure-message template + protected `web-ui/invariants/` shims). These are the guardrails the Phase 2 generators will run under.
- ✅ **Phase 1 contract freeze (session 3)** — `contracts/webapp-v1.yaml` (OpenAPI 3.1) authored from `docs/proposals/API.md`. `dirt-contracts` workspace member ships the generated Pydantic models at `contracts/python/src/dirt_contracts/webapp_v1/models.py`. Generated TypeScript schema at `web-ui/src/api-client/generated/schema.ts` + a typed `openapi-fetch` wrapper at `web-ui/src/api-client/{client,index}.ts`. Regenerator: `scripts/gen-contract`. Invariant `apps/tests/invariants/test_api_contract.py` enforces spec ⊆ app, app ⊆ spec, and pydantic-model importability with an `EXPECTED_MISSING` table that shrinks as Phase 2 endpoints land + a `LEGACY_ROUTES` allowlist that shrinks as the old HTML/HTMX endpoints are deleted. Plan JSON at `docs/plans/webapp-rewrite.json` lists 29 features (19 BE + 10 FE) with acceptance criteria. Frozen tag: `contract-frozen-2026-04-20`. 226 tests green.
- 🟢 **Phase 2** — ready to start. Spawn one BE-lane + one FE-lane Agent (worktree, background) per the plan JSON's `depends_on` ordering; reserve a foreground evaluator pass after each merge.

You (the agent reading this) are picking up where session 2 stopped. Read this doc end-to-end before you do anything.

## Harness smoke test — verify before you start

These four commands must all succeed. They're the baseline evaluator loop; if any break, fix before proceeding.

```bash
# 1. dev server on :5173 (background)
pnpm --dir web-ui dev &
sleep 4

# 2. navigate, snapshot, read console + network
agent-browser open http://localhost:5173/
agent-browser snapshot                        # compact accessibility tree with @eN refs
agent-browser console                         # JS console output (should have no errors)
agent-browser network requests --type fetch   # filter Network tab by type

# 3. cleanup
kill %1
```

Expected: `snapshot` returns a ~3-line tree containing `heading "dirt." [level=1, ref=e2]`. `console` shows only Vite HMR chatter. If you see errors, the skeleton is broken — don't proceed.

---

## 1. What you're inheriting

Phase 0 reshaped the repo from a `dirt` monolith into a `uv` workspace with five packages (hwd / web / shared / mcp / voice). The live hardware loop (serial reader, humidifier, camera capture, archive, ESP32 ingest) is **isolated** in `dirt-hwd.service`. The web/MCP half is **expendable** — slated for rewrite in Phase 2.

**Session 2 (2026-04-19) also completed the DB migration + Phase 1 design work** so that Phase 2 generators have a clean foundation:

- **Postgres 17 + Atlas migrations** replace SQLite + hand-rolled column-migration tuple. See [ADR-006](../adrs/006-postgres-and-atlas.md). Service module `engine`s point at pg via `DIRT_PG_*` creds in `.env`. Rollback sqlite artifact at `var/dirt.db.pre-pg-cutover` until ~2026-05-03.
- **New schema + seed data**: `plant` table (4 rows A/B/C/D), `sensornode` seeded with one row per `sensor_location` enum value, `growstate.is_current` partial-unique-index singleton (future-proofs multi-grow), real FKs everywhere. See `migrations/20260420003127_init.sql`.
- **`docs/proposals/{API.md, data_model.md}`** — agreed endpoint-by-endpoint API spec + data-model spec. These ARE the Phase 1 design. Next agent turns API.md into formal OpenAPI YAML.
- **Six new service modules in `apps/shared/src/dirt_shared/services/`** back the future endpoints: `plants`, `humidifier_state`, `system_status`, `plant_detail`, `wiki`, `mock_sensors`. Each has a `get_*_payload` helper that already produces the shape the API.md endpoints expect — the Phase 2 BE generator's job is the thin FastAPI wrapper, not re-implementing this logic.
- **Test fixture overhaul**: `pg_engine` per-test fixture in `apps/shared/src/dirt_shared/testing.py` clones a session-wide template DB via `CREATE DATABASE ... TEMPLATE`. 143 tests green end-to-end.
- **Shared helpers**: `band_status(value, band) → ok|warn|crit` + `get_grow_current_payload()` in `grow_state.py`; `get_plant_detail_payload(code)` in `plants.py`. The endpoint layer stays thin.
- **Invariant `test_schema_managed_by_atlas.py`** — blocks any agent from re-introducing `metadata.create_all` or hand-rolled column-migration tuples.

Your two jobs:

1. **Phase 1 freeze** — translate `docs/proposals/API.md` into `contracts/webapp-v1.yaml`, write `test_api_contract.py`, author `docs/plans/webapp-rewrite.json`, get user sign-off, tag + record the frozen SHA.
2. **Phase 2** — once the contract is frozen and invariant-tested, orchestrate two parallel generator agents (frontend + backend lanes) via the Claude Code `Agent` tool with `isolation: "worktree"`. An evaluator agent gates merges.

**Critical rule**: `apps/hwd/` is off-limits to the Phase 2 generators. The hardware loops there are running in production and must not be touched. Invariant `test_hwd_routes.py` + `test_import_boundaries.py` enforce this.

---

## 2. Phase 0 recap (30 seconds)

Current `main` has:

```
apps/
  hwd/       dirt-hwd package; /api/ingest/sensors; serial/humidifier/archive loops; port 8000
  web/       dirt-web package; login/feed/sensors/snapshots API + MCP mount; port 8001
  shared/    dirt-shared package; db, config, observability, models, non-HW services
  mcp/       dirt-mcp package; MCP server mounted into dirt-web
  voice/     dirt-voice package; Claudia wake→pipecat→Jabra pipeline
  tests/
    invariants/    three AST-driven cross-app boundary tests
  <app>/tests/     per-app unit/integration tests
var/           runtime data: snapshots/, logs/, sessions/, raw/photos/, outputs/, db-backups/, dirt.db.pre-pg-cutover (rollback artifact)
systemd/       six user-level .service + .timer units
scripts/       install-systemd, daily_report, camera, lint.py, etc.
docs/          ADRs, epics, progress, references, rules
wiki/          agent-maintained grow wiki (4 plants, daily entries, concepts, hardware, decisions)
conftest.py    root — autouse observability-logs isolation fixture
pyproject.toml root — workspace-only; per-app pyprojects carry their own deps
```

Runtime services (all user-level except where noted):

| Unit | Port | Responsibility |
|---|---|---|
| `dirt-hwd.service` | 8000 | ESP32 ingest endpoint, serial reader, humidifier loop, archive loop, capture loop |
| `dirt-web.service` | 8001 | UI + API (cookie session auth) + MCP mount (bearer) — slated for rewrite |
| `dirt-camera.service` | Unix socket | OBSBOT PTZ daemon (C++ wrapper) |
| `dirt-voice.service` | — | Voice channel (Claudia) |
| `dirt-daily-report.service` + `.timer` | — | Daily synthesis → wiki → Telegram at 14:00 MDT |

Verify before starting: `systemctl --user is-active dirt-hwd dirt-web dirt-camera dirt-voice` should print `active` four times.

Rollback assets: git tag `pre-phase-0-snapshot` + `.venv.pre-phase0/` (gitignored 1.3G copy of the pre-reorg venv).

---

## 3. Harness engineering — the concept

Anthropic coined this term for how you structure a long-running agent (minutes to hours, possibly days) so it keeps producing useful work without losing the plot. The core problem: a single agent loop degrades over time — context grows, memory blurs, the agent starts making changes that undo previous changes or drift from the plan.

The solution is to split the work across **specialized agent roles** communicating through **file-based artifacts** (not through shared context), grounded by a **structured JSON plan** that encodes features, dependencies, and pass/fail acceptance criteria. The plan is load-bearing: agents aren't allowed to edit or delete its test/acceptance entries. That's the anchor that prevents drift.

Anthropic's canonical shape is three agents running serially:

- **Planner** — expands a short prompt ("build a habit tracker") into a full product spec + structured feature list.
- **Generator** — picks one feature at a time from the plan, implements it, marks it in progress then done.
- **Evaluator** — drives the running app with `agent-browser` (Rust CLI, ~82% fewer tokens than Playwright MCP), verifies features end-to-end against acceptance criteria, files followups for failures.

The Generator and Evaluator iterate in a loop (5–15 iterations per feature) until the Evaluator signs off. Then they move to the next feature. Total build time in their examples: four hours for a full app.

### How we adapt it

Anthropic's harness is **sequential** — one feature at a time, one generator at a time. We add one twist: **the frozen API contract lets two generators work in parallel** (frontend lane + backend lane) because they can't collide. This works only because:

- The contract is an invariant test — neither generator can modify it without failing CI.
- The generators live in isolated git worktrees, so filesystem changes don't clobber each other.
- Each generator completes its lane feature fully end-to-end before it moves on (same "one feature at a time" discipline, just two lanes in parallel).

This is a deliberate departure from the Anthropic blog post. Read their posts (linked at the bottom) before you do any harness design work — the patterns there dominate your intuition otherwise.

---

## 4. Our harness shape for this project

### Agent roles

| Role | Count | Model suggestion | Owns |
|---|---|---|---|
| **Planner** | 1 | Opus | Writes `docs/plans/webapp-rewrite.json`. You (the handoff agent) do this work directly — not via sub-agent. |
| **Contract author** | 1 | Opus (or you directly) | Writes `contracts/webapp-v1.yaml` (OpenAPI 3.1). Also you, during Phase 1. |
| **Backend generator** | 1 (Phase 2) | Opus | Implements new FastAPI endpoints in `apps/web/` (or a new `apps/api/`) against the frozen contract. |
| **Frontend generator** | 1 (Phase 2) | Opus | Implements the Vite + React + TanStack Router app in `web-ui/` against the same contract. |
| **Evaluator** | 1 (Phase 2) | Sonnet with `agent-browser` CLI | Boots the stack locally, drives the UI, checks feature acceptance criteria, updates plan JSON status. |

### Phasing

- **Phase 1 (sequential, ~1 session)** — Contract author writes `contracts/webapp-v1.yaml`, generates Pydantic models + TS client, adds `test_api_contract.py` invariant that asserts every contract endpoint exists in the FastAPI app and round-trips through the models. Freeze at a git SHA.
- **Phase 2 (parallel, many sessions)** — Two Generator worktrees land separate branches. Evaluator runs on `main` after each lane merge. Loop.

### Gating

Feature status flips to `done` when **both** of these are true:

1. All invariant + unit tests pass in CI.
2. The Evaluator's `agent-browser` run against the live stack matches the feature's acceptance criteria.

No per-feature human sign-off. Merges into `main` are auto-approved when the invariants + evaluator agree. You still own strategic direction (approve the overall plan, review surprises) but not feature-by-feature gates.

### Parallelism boundaries

- Two generators run concurrently only when their features are in different lanes (`frontend` vs `backend`).
- Within a lane, features are still sequential — one at a time — to preserve Anthropic's "no context drift" discipline.
- `lane: contract` features (e.g., adding an endpoint to the OpenAPI spec) must complete and freeze before any dependent FE/BE feature starts. The plan's `depends_on` field encodes this.

---

## 5. Invocation: `Agent` tool with worktrees

This is a Claude Code session (like the one you're in now). You orchestrate sub-agents via the `Agent` tool. Example call (pseudo-code — schema may need a ToolSearch):

```
Agent(
  description="FE lane: build dashboard gauges",
  subagent_type="general-purpose",
  isolation="worktree",
  model="opus",
  prompt="<full self-contained brief; include the plan file path, the feature id,
          the contract SHA, what's off-limits, the acceptance criteria, and where
          to write the result>",
  run_in_background=true,
)
```

Key properties:

- **`isolation: "worktree"`** — the agent gets its own git worktree off the current branch. Filesystem edits don't affect your workspace. If it makes no changes, the worktree is cleaned up automatically; otherwise the branch name + path come back in the result.
- **`run_in_background: true`** for parallel work — you get a notification when it completes. Do NOT poll.
- **To run FE + BE in parallel**: issue a single message with TWO Agent tool calls, both with `run_in_background: true`. They wake up as they finish.

The Evaluator agent typically runs **foreground** — you want its report before you merge. Give it Bash access; the `agent-browser` CLI is on `$PATH` (installed globally). No MCP server needed.

### Why not separate Claude Code sessions or the Agent SDK directly?

- Separate sessions — you'd lose the shared plan file coordination and have to manually babysit each.
- Agent SDK directly — more control, but you'd be building infrastructure instead of shipping the product. The `Agent` tool + worktrees gets 90% of Anthropic's harness shape for free.

If the sub-agent approach hits scaling limits (long runs exceeding CC's agent budget), fall back to SDK-based runners — but don't start there.

---

## 6. The plan JSON format

Central artifact. Grounds every agent. Lives at `docs/plans/webapp-rewrite.json`. Shape:

```json
{
  "contract": {
    "openapi": "contracts/webapp-v1.yaml",
    "frozen_at_sha": "<filled at end of phase 1>",
    "invariant_test": "apps/tests/invariants/test_api_contract.py"
  },
  "invariants": [
    "apps/tests/invariants/test_api_contract.py",
    "apps/tests/invariants/test_auth_boundary.py",
    "apps/tests/invariants/test_import_boundaries.py",
    "apps/tests/invariants/test_hwd_routes.py"
  ],
  "features": [
    {
      "id": "dashboard.gauges",
      "lane": "frontend",
      "depends_on": ["contract.sensors.current", "backend.sensors.current"],
      "user_story": "Operator sees temp/humidity/VPD/fan/reservoir on the dashboard with target-band status colors.",
      "acceptance": [
        {
          "kind": "agent-browser",
          "script": "docs/plans/evaluator-checks/dashboard-gauges.sh",
          "description": "Open /, snapshot the dashboard, assert 5 gauge headings + matching values from GET /api/sensors/current, assert warn color class when value outside target band, assert no console errors."
        },
        {
          "kind": "visual",
          "reference_screenshot": "docs/plans/refs/dashboard-gauges.png",
          "description": "Layout matches the mockup's comfortable-density gauge grid."
        }
      ],
      "status": "pending"
    },
    { "id": "backend.sensors.current", "lane": "backend", "...": "..." }
  ]
}
```

Rules the generators MUST NOT break (enforce via prompt and via the evaluator):

- Never add, remove, or modify the `acceptance` array of an existing feature. Only the `status` field can flip.
- Never reorder features or edit `depends_on` after the plan is frozen — request a new feature instead.
- Never merge a feature marked `in_progress` into `main` without first flipping to `done`.

### Status values

- `pending` — not started, no worktree.
- `in_progress` — generator worktree exists for this feature.
- `done` — merged into main; invariants + evaluator passed.
- `blocked` — evaluator failed; explanatory note in a sibling `evaluator_notes` field.

---

## 7. Tech stack decisions (frozen)

Decided with the user in the prior session. Do not relitigate.

| Concern | Choice |
|---|---|
| Frontend build tool | **Vite** |
| Frontend framework | **React** (TypeScript) |
| Frontend router | **TanStack Router v1** — see `docs/references/tanstack-router-v1/INDEX.md` before writing any route code |
| TypeScript style | Modern idiomatic (`satisfies`, discriminated unions, branded types, no `enum`/`namespace`/`any`) — see `docs/references/modern-idiomatic-typescript/INDEX.md` |
| Lint + format | **Biome** (not ESLint + Prettier) |
| Frontend location | **`web-ui/`** at repo root (not under `apps/`; JS ≠ uv workspace) |
| Backend framework | **FastAPI** — extend existing `apps/web/` with new JSON endpoints, don't rewrite |
| OpenAPI version | 3.1 |
| TS client generation | Let Phase 1 decide — leading candidates: `openapi-ts`, `orval`, or FastAPI's own spec → manual models |
| Auth | Keep the cookie-session middleware already in `apps/web/src/dirt_web/auth.py` |
| Testing (FE) | Vitest for unit tests. E2E acceptance is `agent-browser` scripts under `docs/plans/evaluator-checks/*.sh` referenced from the plan JSON. |
| Browser tool | `agent-browser` (globally installed, `agent-browser --version`). Replaces Playwright MCP. Supports snapshot (`@eN` refs), click, type, console, network (list/filter/HAR), trace, profiler. |

### Layout after Phase 2

```
apps/        (unchanged; Python backend stays in uv workspace)
contracts/   OpenAPI spec + generated TS client + generated Pydantic models (new — Phase 1)
web-ui/      Vite + React + TanStack Router + Tailwind v4 app (SKELETON + INVARIANTS — Phase 2 extends)
  src/
    routes/          (TanStack file-based routing; __root.tsx + index.tsx exist)
    components/      (sparse — generators add per feature)
    lib/             (generated OpenAPI client lives here — Phase 1 populates)
    styles.css       (single global import of Tailwind + @theme design tokens)
  invariants/        (TS-01..16 + XX-02 architectural-invariant harness: eslint.config.ts, knip.json, rules/, tsconfig.base.json)
  package.json, vite.config.ts, tsconfig.*.json, biome.json, eslint.config.ts
docs/plans/
  webapp-rewrite.json        (the plan, owned by planner + evaluator)
  evaluator-checks/*.sh      (agent-browser scripts referenced by plan JSON)
  refs/                   (reference screenshots from the mockup)
```

---

## 8. The mockup

Location: `debug/webapp.zip` (unzip to `/tmp/webapp_review/` to inspect). React + Babel-in-browser prototype (NOT our target stack — we use Vite + TSX). Four screens:

1. **Login** — three visual variants (botanical / minimal / terminal); operator chooses via tweaks panel.
2. **Dashboard** — five sensor gauges (temperature, humidity, VPD, inline fan, reservoir) with target-band arcs + humidifier on/off tile. Sparklines below (1h / 24h / 7d range switcher, shared crosshair hover). Plants strip (A–D with soil-moisture bars, click opens drawer). System-device status table.
3. **Live** — PTZ camera feed with crosshair overlay. Presets for overview + plant_{a,b,c,d}. Three manual control modes (click-to-look, d-pad, joystick) selected via tweaks panel. Zoom slider.
4. **Wiki** — file tree sidebar (overview / plants / daily / concepts / hardware / decisions / environment), markdown rendering with frontmatter + backlinks, Cmd+K search (filename + content).

Plus a plant-detail drawer (overlay, clicked from dashboard) showing moisture chart, vitals table, and timeline.

Design language: paper/ink palette, JetBrains-Mono for numbers, Crimson-Pro-italic for brand, low-contrast dotted/gridded backgrounds. Keep it verbatim — don't let generators redesign.

### API surface

**Source of truth: [`docs/proposals/API.md`](../proposals/API.md)** — session 2 wrote this endpoint-by-endpoint spec with agreed JSON response shapes, agreed-on decisions (code/id rename, vitals dropped, band-status helper pattern), and an explicit add/modify/remove table against today's `apps/web/src/dirt_web/api/` routes. Session 3 added the "Resolved" subsection at the bottom after a mockup-vs-API audit: login field-notes are hardcoded (no pre-auth endpoint); `week_number` → `grow_week_number` + new `flower_week_number`; `/api/auth/me` on SPA boot (no `localStorage` auth flag); PTZ preset entries gain `yaw`/`pitch`/`zoom`; wiki `lint ✓` badge dropped from the UI; Cmd+K "recent" is client-side via `shared/storage.ts`. Phase 1 turns this into `contracts/webapp-v1.yaml`. Do NOT re-design or cherry-pick shapes — the proposal was iterated on with the user and is the contract baseline.

Paired reference: [`docs/proposals/data_model.md`](../proposals/data_model.md) — schema, types, resolved open questions, per-endpoint "which service produces this field" notes.

---

## 9. Off-limits and invariants

### Hard off-limits for Phase 2 generators

- `apps/hwd/` — the hardware daemon (serial reader, humidifier loop, archive loop, ingest endpoint). Do not edit code here, do not add endpoints here, do not import from here in non-hwd code. `test_import_boundaries.py` enforces the last rule.
- `systemd/dirt-hwd.service` — do not modify; its live process is serving the ESP32s.
- Live Postgres `dirt` database (see ADR-006) — never `DROP TABLE`, `TRUNCATE`, or overwrite production data. Tests clone from `dirt_test_template` via `pg_engine` fixture; see `dirt_shared.testing`.
- `apps/tests/invariants/*` — human-owned per existing hooks. Generators must make code match the invariants, not the other way around.

### Invariants the evaluator checks after each feature

1. `uv run pytest -q` green (invariants + per-app suites per the root `testpaths`).
2. Contract test (`test_api_contract.py`, Phase 1 introduces) green — proves OpenAPI spec ↔ FastAPI routes ↔ Pydantic models ↔ TS client all agree.
3. `cd web-ui && pnpm lint && pnpm typecheck && pnpm build` clean.
4. `cd web-ui && pnpm test` (Vitest) green.
5. Feature-specific `agent-browser` script (under `docs/plans/evaluator-checks/`) green against the live stack on :8001, with no console errors and expected network calls observed.
6. All four systemd services still `active` after the feature's local dev cycle.

---

## 10. First actions for this agent (the one reading this)

Do these in order:

1. **Verify the foundation is intact**. Run:
   ```
   systemctl --user is-active dirt-hwd dirt-web dirt-camera dirt-voice postgresql
   set -a; source .env; set +a
   uv run pytest -q                       # should report 143 passed
   ```
   All services active + 143 tests green. If not, stop and investigate — don't proceed on a broken base.

2. **Read the proposals** (in order — they are short and were iterated on with the user):
   - `docs/proposals/API.md` — the frozen API design. Your OpenAPI YAML is a translation of this.
   - `docs/proposals/data_model.md` — schema + resolved decisions + per-endpoint service mapping.
   - `docs/adrs/006-postgres-and-atlas.md` — DB engine + migration tool decision (context for any schema concerns).

3. **Read the references** (only what you'll actually touch):
   - Two Anthropic harness blog posts (links in §12). Read before designing the Phase 2 orchestration.
   - `docs/references/tanstack-router-v1/INDEX.md` + `docs/references/modern-idiomatic-typescript/INDEX.md` + `docs/references/tailwind-v4/INDEX.md` — FE stack anchors. Required reading for the FE generator's prompt.
   - `docs/references/atlas/INDEX.md` — only if you're changing the DB schema in Phase 1 (you probably aren't).
   - `docs/references/claude-agent-sdk/INDEX.md` — we're NOT using the SDK directly, but it clarifies options.

4. **Unzip and re-read the mockup** if you're finalizing contract details: `unzip debug/webapp.zip -d /tmp/webapp_review/` then skim `Dirt WebApp.html` + the four component JSX files. Cross-check against `docs/proposals/API.md` section numbers.

5. **Phase 1 freeze — do this yourself, not via agents.** Deliverables:
   - `contracts/webapp-v1.yaml` (OpenAPI 3.1) — translation of `docs/proposals/API.md`. Don't redesign; translate. Include request/response schemas, error codes, auth scheme.
   - `apps/tests/invariants/test_api_contract.py` — asserts every path+method in the spec exists in `dirt_web.app.app`, and response schemas round-trip through the generated Pydantic models.
   - `docs/plans/webapp-rewrite.json` — full feature list + acceptance criteria + dependencies + lane per feature. See §6 for shape.
   - Generated TS client in `web-ui/src/lib/` (pick `openapi-ts` vs `orval` — that's a Phase 1 decision; lean `openapi-ts` for minimal-footprint output).
   - Get the user's sign-off on the plan JSON before freezing.

6. **Once approved**: tag the HEAD commit (`contract-frozen-YYYY-MM-DD`), record that SHA in `docs/plans/webapp-rewrite.json` under `contract.frozen_at_sha`, and commit.

7. **Kick off Phase 2**. Two `Agent` calls in a single message, both `run_in_background: true`, one `frontend` lane + one `backend` lane. Each prompt must:
   - Point at the plan JSON + the frozen contract SHA.
   - List off-limits paths (§9) explicitly.
   - Remind the BE generator that the hard logic is in `dirt_shared.services.{plants, humidifier_state, system_status, plant_detail, wiki, mock_sensors, grow_state, readings}` — they just thread FastAPI endpoints through. `get_*_payload()` composites already shape the responses.
   - Remind the FE generator to use the generated TS client from `web-ui/src/lib/`, not hand-author fetch calls.

   Reserve a foreground `Agent` call for the Evaluator after each round.

---

## 11. Process hygiene

- **Commit strategy**: generators commit to their worktree branch. You merge into `main` only after Evaluator + invariants agree. Squash-merge is fine; preserve feature id in the commit subject (`feat(dashboard.gauges): …`).
- **Plan JSON updates**: only the Evaluator flips `status` to `done` or `blocked`. Planner (you) adds new features via explicit JSON edits with a commit message `plan: add feature <id>`.
- **When the Evaluator says blocked**: read its `evaluator_notes` field, decide whether to (a) re-brief the generator with a more specific prompt, (b) split the feature, or (c) mark as deferred. Don't silently retry — the generator will drift.
- **Context budget**: each Agent invocation starts fresh. Keep prompts self-contained — don't assume the sub-agent has conversational context from you. Include file paths, line numbers, and references to the plan id. See the "Writing the prompt" guidance in Claude Code's Agent tool docs.

---

## 12. Reference links

### External — harness engineering (read these first)

- **[Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)** (Anthropic engineering blog) — the canonical 3-agent shape. Mentions Planner/Generator/Evaluator and the sprint-contract negotiation pattern.
- **[Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)** (Anthropic) — deeper on the JSON-based feature registry, the "never edit tests" rule, and the smoke-test-at-session-start pattern.
- **[Anthropic designs three-agent harness — InfoQ](https://www.infoq.com/news/2026/04/anthropic-three-agent-harness-ai/)** — external summary of both posts. Faster read; use as a refresher.

### External — frontend stack

- **TanStack Router v1** — framework homepage: <https://tanstack.com/router/latest>. Always read `docs/references/tanstack-router-v1/INDEX.md` first; the reference pack overrides training-data instincts toward `react-router-dom`.
- **Vite** — <https://vitejs.dev>. Stable enough to follow the official guide.
- **Biome** — <https://biomejs.dev>. The reference pack in `docs/references/modern-idiomatic-typescript/` covers configuration choices.

### Internal references (in this repo)

**Must-read (session 2 output — these ARE the Phase 1 design):**
- `docs/proposals/API.md` — agreed API spec; your `contracts/webapp-v1.yaml` translates this.
- `docs/proposals/data_model.md` — schema + resolved open questions + per-endpoint service mapping.
- `docs/adrs/006-postgres-and-atlas.md` — DB engine decision + cutover context.

**Framework reference packs (read before writing any code in that area):**
- `CLAUDE.md` — project overview, discovery layer. `### Database` subsection covers pg ops; `## Framework/API References` lists the packs below.
- `docs/references/tanstack-router-v1/INDEX.md` — read before writing any route.
- `docs/references/modern-idiomatic-typescript/INDEX.md` — read before writing TS.
- `docs/references/tailwind-v4/INDEX.md` — read before writing any Tailwind class (v4 is a rewrite; training data is stuck on v3).
- `docs/references/atlas/INDEX.md` — only if Phase 1 requires a schema change (unlikely).
- `docs/references/claude-agent-sdk/INDEX.md` — read before considering a custom runner.
- `docs/references/pipecat/INDEX.md` + `docs/references/deepgram-tts-aura-2/INDEX.md` — only if you touch voice (you shouldn't in Phase 1/2).

**Service modules already implemented for Phase 2 BE to consume:**
- `apps/shared/src/dirt_shared/services/plants.py` — `list_plants()`, `get_plant_by_code()`, `get_plant_detail_payload()` (composite), `get_plant_moisture_history()`.
- `apps/shared/src/dirt_shared/services/humidifier_state.py` — `get_state()`, `get_history()`.
- `apps/shared/src/dirt_shared/services/system_status.py` — `get_device_statuses()`.
- `apps/shared/src/dirt_shared/services/plant_detail.py` — `get_plant_detail(code)` (wiki markdown parser).
- `apps/shared/src/dirt_shared/services/wiki.py` — `get_tree()`, `get_file(path)`, `search(q)`.
- `apps/shared/src/dirt_shared/services/mock_sensors.py` — `get_fan_pct(ts)`, `get_reservoir_in(ts)`, history helpers.
- `apps/shared/src/dirt_shared/services/grow_state.py` — plus `band_status(value, band)` + `get_grow_current_payload()`.

**Historical (read only if you need background):**
- `wiki/CLAUDE.md` — start here for any wiki-related work (if the wiki UI feature involves read-through to the markdown store).
- `.claude/plans/cuddly-twirling-starlight.md` — Phase 0 plan. Historical.
- `debug/webapp.zip` — the high-fidelity React+Babel mockup from Claude Design. Visual truth for the rewrite.

---

## 13. What success looks like

At the end of Phase 2:

- `web-ui/` ships a working Vite + React + TanStack Router app hitting `dirt-web` on :8001.
- Every endpoint in the mockup works against real backend data.
- All invariants green; every feature's `agent-browser` check passes; Biome clean; Vitest green.
- `dirt-hwd.service` has been untouched by agents the entire time (verify with `git log apps/hwd/` — should show only pre-Phase-2 commits or author = you).
- The old Jinja templates + HTMX endpoints in `dirt-web` are removed.
- `dirt.service` (retired Phase 0) still absent.

At that point the original mockup from `debug/webapp.zip` is approximately reproduced as a real product, and the long-running harness has validated itself as a tool we can use for future rewrites.

---

*Written at end of Phase 0 cutover session. Updated 2026-04-19 at end of session 2 (pg cutover + Phase 1 design work). Updated 2026-04-20 at end of session 3 (architectural-invariant hardening: PY-01..09, TS-01..16, XX-01/02 landed; Phase 1 contract freeze landed: `contracts/webapp-v1.yaml`, `dirt-contracts` workspace member with generated Pydantic models, `web-ui/src/api-client/{generated/schema,client,index}.ts`, `apps/tests/invariants/test_api_contract.py`, `docs/plans/webapp-rewrite.json` with 29 features; stale pointers to deleted `docs/proposals/{pg-cutover-plan,singleton-retirement}.md` and `docs/progress/architectural-invariants*.json` removed; tag `contract-frozen-2026-04-20`). If this document is more than a couple of weeks stale, re-verify the top-of-doc status banner + section 2 (Phase 0/1 recap) against current repo state before trusting the rest.*
