# Webapp rewrite — agent handoff

**Status**: Phase 0 complete (uv workspace + hardware-daemon split). Phase 1 (OpenAPI contract) not started. Phase 2 (parallel FE + BE generation) blocked on Phase 1.

You (the agent reading this) are picking up where the previous session stopped. This doc gives you enough to get started without re-reading the prior conversation. Read it end-to-end before you do anything.

---

## 1. What you're inheriting

Phase 0 reshaped the repo from a single `dirt` FastAPI monolith into a `uv` workspace with five packages. The live hardware loop (serial reader, humidifier, camera capture, archive, ESP32 ingest) is now **isolated** in `dirt-hwd.service`. The web/MCP half lives in `dirt-web.service` and is **expendable** — its code is slated for rewrite in Phase 2.

You have two jobs:

1. **Phase 1** — design an OpenAPI contract for the new web UI → backend boundary and freeze it. You do this work yourself (not via agents).
2. **Phase 2** — once the contract is frozen and invariant-tested, orchestrate two parallel generator agents (frontend + backend lanes) via the Claude Code `Agent` tool with `isolation: "worktree"`. An evaluator agent gates merges.

**Critical rule**: `apps/hwd/` is off-limits to the Phase 2 generators. The hardware loops there are running in production and must not be touched. Invariant `test_hwd_routes.py` + `test_import_boundaries.py` will enforce this.

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
var/           runtime data: dirt.db, snapshots/, logs/, sessions/, raw/photos/, outputs/, db-backups/
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
- **Evaluator** — drives the running app with Playwright MCP, verifies features end-to-end against acceptance criteria, files followups for failures.

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
| **Evaluator** | 1 (Phase 2) | Sonnet with Playwright MCP | Boots the stack locally, drives the UI, checks feature acceptance criteria, updates plan JSON status. |

### Phasing

- **Phase 1 (sequential, ~1 session)** — Contract author writes `contracts/webapp-v1.yaml`, generates Pydantic models + TS client, adds `test_api_contract.py` invariant that asserts every contract endpoint exists in the FastAPI app and round-trips through the models. Freeze at a git SHA.
- **Phase 2 (parallel, many sessions)** — Two Generator worktrees land separate branches. Evaluator runs on `main` after each lane merge. Loop.

### Gating

Feature status flips to `done` when **both** of these are true:

1. All invariant + unit tests pass in CI.
2. The Evaluator's Playwright run against the live stack matches the feature's acceptance criteria.

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

The Evaluator agent typically runs **foreground** — you want its report before you merge. Give it the Playwright MCP server in its allowed tools.

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
          "kind": "playwright",
          "spec": "web-ui/tests/e2e/dashboard-gauges.spec.ts",
          "description": "Load /, five gauges render with values matching GET /api/sensors/current, warn color when value outside target band."
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
| Testing (FE) | Vitest for unit, Playwright for e2e (new specs under `web-ui/tests/`) |

### Layout after Phase 2

```
apps/        (unchanged; Python backend stays in uv workspace)
contracts/   OpenAPI spec + generated TS client + generated Pydantic models (new — Phase 1)
web-ui/      Vite + React + TanStack Router app (new — Phase 2)
  src/
    routes/
    components/
    lib/     (generated API client lives here)
  tests/
    e2e/     (Playwright specs referenced by plan JSON)
  package.json, vite.config.ts, tsconfig.json, biome.json
docs/plans/
  webapp-rewrite.json     (the plan, owned by planner + evaluator)
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

### API surface implied by the mockup

This is a first-pass sketch. Phase 1 owns finalizing it.

- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` — JSON replacement for the current form-post `/login`
- `GET /api/sensors/current` — envelope with `{value, target:[lo,hi]|null, status, stale, ts}` per metric
- `GET /api/sensors/history?range=1h|24h|7d&metric=…` — labels + values (partly exists)
- `GET /api/humidifier/state` + `GET /api/humidifier/history?range=…` — on/off + duty cycle
- `GET /api/plants` + `GET /api/plants/{id}` — moisture, pH, distance, nodes, timeline, primary flag
- `GET /api/system/devices` — per-device `{name, status, last_seen}`
- `GET /api/feed/live.jpg` + `GET /api/feed/snapshot/latest` (snapshot exists, live too via dirt-web)
- `GET /api/ptz/state`, `POST /api/ptz/preset/{id}`, `POST /api/ptz/nudge`, `POST /api/ptz/look`, `POST /api/ptz/zoom` — thin HTTP wrappers over `scripts/camera`
- `GET /api/wiki/tree`, `GET /api/wiki/file?path=…`, `GET /api/wiki/search?q=…` — filesystem-backed, path-restricted to `wiki/`

Endpoints already live (mostly in `apps/web/src/dirt_web/api/`) for: feed, sensors/readings, snapshots, login (form-post). Phase 1 will audit and decide what to replace vs. reuse.

---

## 9. Off-limits and invariants

### Hard off-limits for Phase 2 generators

- `apps/hwd/` — the hardware daemon (serial reader, humidifier loop, archive loop, ingest endpoint). Do not edit code here, do not add endpoints here, do not import from here in non-hwd code. `test_import_boundaries.py` enforces the last rule.
- `systemd/dirt-hwd.service` — do not modify; its live process is serving the ESP32s.
- `var/dirt.db` (live DB) — never delete or overwrite. Tests must use a tmp DB per-test.
- `apps/tests/invariants/*` — human-owned per existing hooks. Generators must make code match the invariants, not the other way around.

### Invariants the evaluator checks after each feature

1. `uv run pytest apps/tests/invariants/ apps/*/tests/ -q` green.
2. Contract test (`test_api_contract.py`, Phase 1 introduces) green — proves OpenAPI spec ↔ FastAPI routes ↔ Pydantic models ↔ TS client all agree.
3. `cd web-ui && biome check .` clean.
4. `cd web-ui && pnpm test` (Vitest) green.
5. Feature-specific Playwright spec green against the live stack on :8001.
6. All four systemd services still `active` after the feature's local dev cycle.

---

## 10. First actions for this agent (the one reading this)

Do these in order:

1. **Verify Phase 0 is intact**. Run:
   ```
   systemctl --user is-active dirt-hwd dirt-web dirt-camera dirt-voice
   uv run pytest -q
   ```
   Both should be green. If not, stop and investigate — don't proceed on a broken base.

2. **Read the references**. In order of importance for orientation:
   - The two Anthropic harness blog posts (links below). Read both.
   - `docs/references/tanstack-router-v1/INDEX.md` (if the handoff goes anywhere near frontend).
   - `docs/references/modern-idiomatic-typescript/INDEX.md`.
   - `docs/references/claude-agent-sdk/INDEX.md` — we're NOT using the SDK directly, but it explains options + tradeoffs.

3. **Unzip and re-read the mockup** if you're doing contract design: `unzip debug/webapp.zip -d /tmp/webapp_review/` then skim `Dirt WebApp.html` + the four component JSX files. Only needed if you're the contract author.

4. **Kick off Phase 1 (OpenAPI contract)**. No agents yet — you do this yourself. Deliverables:
   - `contracts/webapp-v1.yaml` (OpenAPI 3.1).
   - `apps/tests/invariants/test_api_contract.py` — asserts every endpoint in the spec exists in `dirt_web.app.app` with matching methods; response schemas round-trip through generated Pydantic models.
   - `docs/plans/webapp-rewrite.json` — full feature list + acceptance criteria + dependencies, all lanes. See section 6 for shape.
   - Get the user's sign-off on the plan before freezing.

5. **Once the plan is approved**: tag the HEAD commit (`contract-frozen-<date>`), record that SHA in `docs/plans/webapp-rewrite.json` under `contract.frozen_at_sha`, and commit. That's the boundary agents can't cross.

6. **Kick off Phase 2**. Two `Agent` calls in a single message, both `run_in_background: true`, one `frontend` lane + one `backend` lane, each with a self-contained prompt pointing at the plan JSON + the frozen contract SHA. The prompt must list off-limits paths (section 9) explicitly. Reserve a foreground `Agent` call for the Evaluator after each round.

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

- `CLAUDE.md` — project overview, discovery layer. Also lists the framework reference packs and when to consult each.
- `docs/references/tanstack-router-v1/INDEX.md` — read before writing any route.
- `docs/references/modern-idiomatic-typescript/INDEX.md` — read before writing TS.
- `docs/references/claude-agent-sdk/INDEX.md` — read before considering a custom runner.
- `docs/references/pipecat/INDEX.md` — only if you touch voice (you shouldn't in Phase 1/2).
- `docs/references/deepgram-tts-aura-2/INDEX.md` — only if you touch voice TTS (you shouldn't).
- `wiki/CLAUDE.md` — start here for any wiki-related work (if the wiki UI feature involves read-through to the markdown store).
- `.claude/plans/cuddly-twirling-starlight.md` — Phase 0 plan. Historical; Phase 0 is done. Read if you want to understand why the split looks the way it does.
- `debug/webapp.zip` — the high-fidelity React+Babel mockup from Claude Design. Visual truth for the rewrite.

---

## 13. What success looks like

At the end of Phase 2:

- `web-ui/` ships a working Vite + React + TanStack Router app hitting `dirt-web` on :8001.
- Every endpoint in the mockup works against real backend data.
- All invariants green; Playwright specs green; Biome clean; Vitest green.
- `dirt-hwd.service` has been untouched by agents the entire time (verify with `git log apps/hwd/` — should show only pre-Phase-2 commits or author = you).
- The old Jinja templates + HTMX endpoints in `dirt-web` are removed.
- `dirt.service` (retired Phase 0) still absent.

At that point the original mockup from `debug/webapp.zip` is approximately reproduced as a real product, and the long-running harness has validated itself as a tool we can use for future rewrites.

---

*Written at end of Phase 0 cutover session, 2026-04-19. If this document is more than a couple of weeks stale, re-verify section 2 (Phase 0 recap) against current repo state before trusting the rest.*
