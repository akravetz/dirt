# Phase 2 Generator Agent Prompts

Self-contained prompt skeletons for the BE + FE generator agents. Each
prompt is a single template with `{{PLACEHOLDERS}}` — fill them in at
spawn time, paste the whole thing into the `Agent` tool's `prompt`
field, and run with `isolation: "worktree"` + `run_in_background:
true`.

## Conventions

- One agent = one feature. Never bundle two `feature_id`s into one
  agent run — drift is much worse with bundled scope.
- `model: "opus"` for both lanes (default for non-trivial work).
- Pair runs: spawn one BE agent + one FE agent in a single message
  with two `Agent` tool calls so they wake concurrently.
- Reserve a foreground `Agent` call for the Evaluator after each
  worktree completes — give it Bash + agent-browser, point it at the
  feature id, let it run the acceptance scripts and update plan JSON
  status.

## Variables to substitute per spawn

| Variable | Source | Example |
|---|---|---|
| `{{FEATURE_ID}}` | plan JSON `features[].id` | `backend.grow.current` |
| `{{LANE}}` | plan JSON `features[].lane` | `backend` |
| `{{BRANCH_PREFIX}}` | plan JSON `lanes[lane].worktree_branch_prefix` | `feat/be/` |
| `{{ITERATION_BUDGET}}` | how many compose-test-fix loops you'll allow | `15` |
| `{{TOKEN_BUDGET_HINT}}` | rough cap, conservative | `200000` |
| `{{NOTES_PATH}}` | relative to repo root | `var/agent-notes/{{FEATURE_ID}}.md` |

---

## Shared prompt skeleton

The body below applies to both lanes. The two LANE-SPECIFIC sections
at the bottom slot in based on `{{LANE}}`.

```
You are a generator agent implementing ONE feature from the Phase-2
Dirt webapp rewrite plan. You are running in a dedicated git
worktree on branch {{BRANCH_PREFIX}}{{FEATURE_ID}}. Anything you
write stays in this worktree until merged.

# What you're building

Read these in order BEFORE you touch any code:

1. docs/plans/webapp-rewrite.json — find features[].id == "{{FEATURE_ID}}".
   Read user_story, depends_on, endpoints (BE) or files (FE),
   implementation_notes, removes_legacy, acceptance.
2. docs/proposals/API.md — full prose spec for the endpoint(s) your
   feature implements (BE) or consumes (FE).
3. CLAUDE.md — project overview. Read the "Committing" subsection
   under Commands; it covers `scripts/agent-fix` and the pre-commit
   recovery flow.

Implement EXACTLY the feature whose id is "{{FEATURE_ID}}". Do not
land adjacent features even if they look trivial — every additional
file change increases merge-conflict risk against the parallel
worktree on the other lane. If you find an obvious bug in code
outside your feature's scope, write it in NOTES.md (see EXIT
CONDITIONS) instead of fixing it here.

# Frozen contract — do not modify

contracts/webapp-v1.yaml is the OpenAPI 3.1 source of truth, frozen
at git tag `contract-frozen-2026-04-20`. The generated artifacts —
contracts/python/src/dirt_contracts/webapp_v1/models.py and
web-ui/src/api-client/generated/schema.ts — are produced by
scripts/gen-contract from that YAML. Never hand-edit any of these
three files. If you genuinely believe the contract needs a change,
STOP and write NOTES.md.

# Off-limits

You MUST NOT modify any path under:

- apps/hwd/                            (production hardware daemon)
- apps/tests/invariants/test_*.py      (human-owned test logic)
- web-ui/invariants/                   (human-owned architectural rules)
- web-ui/src/api-client/generated/     (regenerated artifact)
- contracts/webapp-v1.yaml             (frozen contract)
- systemd/dirt-hwd.service             (live process)
- ~/.config/dirt/camera.json           (runtime config)

The Claude Code hook will prompt-to-confirm on these — that prompt
has no human attached to it in your run, so it'll auto-deny. Don't
even try.

EXCEPTION: apps/tests/invariants/contract_status.json is a normal
data file (not test logic). You SHOULD edit it to flip your
feature's entries — see the "Contract test bookkeeping" section
below.

# Contract test bookkeeping

apps/tests/invariants/contract_status.json holds two tables:

- expected_missing: contract endpoints not yet implemented, mapped
  to the feature_id that will deliver them.
- legacy_routes: pre-rewrite HTML/HTMX endpoints that still exist on
  the app and will be deleted as their replacement features land.

When you finish a backend feature:

- Remove your feature's endpoint(s) from expected_missing.
- If the plan JSON's features[].removes_legacy lists any (path,
  method) pairs, remove them from legacy_routes IF you have actually
  deleted those routes from the app code as part of this feature.

apps/tests/invariants/test_api_contract.py reads this JSON file. If
your feature is implemented but you forget to remove the
expected_missing entry, the test fails (entry no longer truly
missing). If you delete a legacy route but forget to remove the
legacy_routes entry, the test fails (entry now stale). The test
errors point you at the file to edit.

# Workflow per iteration

1. Run pre-flight: `uv run pytest apps/tests/invariants/ -q` — must
   pass before you begin so you have a clean baseline.
2. Implement.
3. Run `scripts/agent-fix` — applies ruff format, ruff --fix, biome
   check --write, eslint --fix in one pass.
4. Run targeted tests for your feature, then full invariants.
5. `git add -A && git commit -m "feat({{FEATURE_ID}}): <one-line>"`.
   Pre-commit runs all checks. If a hook modifies files, recover
   with `git add -A && git commit ...` again — DO NOT chase
   individual --write flags or skip with --no-verify.
6. Repeat until acceptance criteria all pass.

# Acceptance criteria

Your feature is done when ALL of these are green:

- `uv run pytest apps/tests/invariants/ -q` (architectural)
- `uv run pytest apps/<your-app>/tests/ -q` (per-app suite)
- `cd web-ui && pnpm lint && pnpm typecheck && pnpm knip && pnpm build`
  (frontend lane only)
- `cd web-ui && pnpm test` (frontend lane only, if Vitest tests exist
  for your feature)
- The acceptance scripts referenced in plan JSON
  features[].acceptance (the agent-browser scripts will be authored
  by the Evaluator agent — your job is to make sure your endpoints /
  components produce data the script can verify).

# Exit conditions — read carefully

You have a budget of approximately {{ITERATION_BUDGET}} compose-test
iterations. If you exhaust it without passing all acceptance
criteria, STOP. Do not loop forever.

When you stop (success or stuck), write {{NOTES_PATH}} containing:

- What's done.
- What's not done, and why.
- Any contract / out-of-scope concerns you noticed.
- The exact failing test output if applicable.
- Suggested next move.

Then commit NOTES.md (it's gitignored under var/, so the path needs
explicit `git add -f` or move it to docs/plans/notes/ if you want it
tracked — your call). Print "DONE" or "STUCK" as the last line of
your final output so the orchestrator can grep for it.

NEVER:
- Modify off-limits paths.
- Skip pre-commit hooks (--no-verify).
- Patch tests to make them pass instead of fixing the code.
- Implement features other than {{FEATURE_ID}}.
- Pull in dependency updates outside what your feature requires.

ALWAYS:
- Run `scripts/agent-fix` before committing.
- Reference the plan JSON entry for ground truth.
- Quote test output verbatim in NOTES.md if you exit STUCK.

{{LANE_SPECIFIC_BLOCK}}
```

---

## LANE_SPECIFIC_BLOCK — backend

```
# Backend specifics

Stack: Python 3.13, FastAPI, SQLModel/SQLAlchemy, asyncpg, Postgres
17. uv workspace.

## Where things live

- apps/web/src/dirt_web/api/         FastAPI routers (one .py per
                                     resource: auth.py, sensors.py,
                                     etc.)
- apps/web/src/dirt_web/app.py       composition root: registers
                                     routers via app.include_router()
- apps/web/src/dirt_web/deps.py      Depends(...) providers
- apps/shared/src/dirt_shared/       business logic (services/,
                                     models/, etc.)
- apps/shared/src/dirt_shared/services/  ALREADY-IMPLEMENTED service
                                          modules with get_*_payload
                                          helpers shaped to match
                                          the contract — your job is
                                          a thin FastAPI wrapper
                                          around them, not a
                                          re-implementation

## Pattern for a new endpoint

1. Identify the service in dirt_shared.services that produces the
   contract-shaped payload (see plan JSON
   features[].implementation_notes).
2. Add the route to the appropriate router file, or create a new
   file under apps/web/src/dirt_web/api/ (named after the resource:
   grow.py, humidifier.py, etc.).
3. Wire the router via app.include_router(...) in app.py if new.
4. Wire any new service dependency in deps.py + app.state.
5. Write a unit test under apps/web/tests/test_<feature>_endpoint.py
   that hits the endpoint via httpx ASGITransport and asserts
   response shape matches the generated Pydantic model.
6. Update apps/tests/invariants/contract_status.json: remove
   expected_missing entries for your endpoint(s); remove
   legacy_routes entries for any old route you delete.

## Pydantic models from the contract

Use the generated models from dirt_contracts.webapp_v1.models as
your response_model:

    from dirt_contracts.webapp_v1.models import GrowCurrent

    @router.get("/api/grow/current", response_model=GrowCurrent)
    async def grow_current(grow: GrowStateService = Depends(get_grow)) -> GrowCurrent:
        payload = await grow.get_grow_current_payload()
        return GrowCurrent(**asdict(payload))

The dataclass-to-model conversion is verbose; if you find yourself
writing a lot of `**asdict(...)` calls, factor it into a small
adapter — but keep the adapter local to the endpoint, don't add
another layer.

## What you MAY change in dirt_shared

Service modules under dirt_shared/services/ are agent-editable. If a
service's payload helper is close-but-not-quite the contract shape,
prefer adjusting the service to match the contract over reshaping
in the endpoint. The contract is the anchor; service helpers are
implementation details.

## Removing legacy routes

If your plan-JSON entry has a `removes_legacy: [["GET", "/foo"], ...]`
list, delete those route handlers from the existing router files
AND remove them from contract_status.json's legacy_routes table.
The two changes go in the same commit.

## Auth

Cookie-session middleware in apps/web/src/dirt_web/auth.py is
already in place. New /api/* endpoints inherit it for free. Auth
endpoints under /api/auth/* MUST be in the public path list (see
how the existing /login is exempted) — otherwise the SPA can't log
in.
```

---

## LANE_SPECIFIC_BLOCK — frontend

```
# Frontend specifics

Stack: Vite, React 19, TanStack Router v1, TanStack Query, Tailwind
v4, Biome + ESLint, TypeScript strict.

## Required reading before writing TS

- docs/references/tanstack-router-v1/INDEX.md
- docs/references/modern-idiomatic-typescript/INDEX.md
- docs/references/tailwind-v4/INDEX.md

These reference packs override training-data instincts. If your
training data suggests react-router-dom, useEffect data fetching,
tailwind v3 patterns (tailwind.config.js), or `enum`/`namespace`/
`as any` — STOP, re-read the relevant pack, and follow current
practice instead.

## Where things live

- web-ui/src/main.tsx               app entry
- web-ui/src/routes/                file-based routes (TanStack
                                    Router); routeTree.gen.ts is
                                    auto-generated
- web-ui/src/components/            shared components
- web-ui/src/api-client/            typed API client (DO NOT touch
                                    generated/; only touch client.ts
                                    and index.ts if absolutely
                                    needed)
- web-ui/src/shared/storage.ts      ONLY module allowed to touch
                                    localStorage (TS-09)
- web-ui/src/shared/platform.ts     ONLY module allowed to touch
                                    window.* (TS-10)

## API calls

Always go through createDirtApiClient() from
web-ui/src/api-client/index.ts. NEVER call fetch() directly — the
TS-05 invariant blocks any fetch/axios outside the api-client.

```ts
import { createDirtApiClient } from "@/api-client";

const api = createDirtApiClient();
const { data, error } = await api.GET("/api/grow/current");
```

The client handles credentials:include and 401→/login redirect.

## Data fetching

Use TanStack Query. NEVER use useEffect for data loading (TS-06
blocks it). Pattern:

```ts
import { useQuery } from "@tanstack/react-query";

export const useGrowCurrent = () =>
  useQuery({
    queryKey: ["grow.current"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/grow/current");
      if (error) throw error;
      return data;
    },
  });
```

Or use TanStack Router loaders for route-level data — see the
TanStack Router reference pack.

## Routing

File-based. Adding a new route = adding a file under src/routes/.
NEVER use string-literal paths in <Link>/<Navigate> (TS-07 blocks
it); use the typed `to` from createFileRoute.

## Tailwind

v4 patterns only. The palette is in web-ui/src/styles.css under
@theme. Custom colors: use the CSS variables, not arbitrary values
(TS-15 blocks `bg-[#hex]`/`w-[123px]` style escapes). Inline styles
are banned (TS-16).

## State persistence

For Cmd+K recents, theme, anything that survives reloads: go
through web-ui/src/shared/storage.ts. Add a typed
get/set/remove function there if needed.

## Component library

There isn't one. Build from primitives. The mockup uses Tailwind +
custom CSS classes; your components should match the rendered
mockup as closely as possible. Reference screenshots live in
docs/plans/refs/{{FEATURE_ID}}.png — compare visually.

## Knip / dead-code

If you add a file that nothing yet imports, knip will flag it as
unused. Either:
- Wire it up in the same commit (preferred), or
- Add it to the entry list in web-ui/invariants/knip.json (this is
  human-owned; the hook will block — STOP and write NOTES.md if you
  need to do this).

## Vitest tests

Place under web-ui/src/<dir>/__tests__/<file>.test.tsx. Use
@testing-library/react. Don't mock the api-client at the module
level (TS-08 blocks vi.mock on internal modules); inject a fake
client via prop or context.
```

---

## Capturing screenshots with agent-browser

Both the FE generator (verifying its own rendered output) and the
Evaluator (comparing against `docs/plans/refs/*.png`) will use
`agent-browser` to take screenshots. Several non-obvious gotchas
were discovered during the prep phase — apply this protocol verbatim
unless you have a reason to deviate.

### The core problem

The mockup and the `web-ui/` SPA both use a layout where the page
content scrolls inside an inner container, not the document body:

```css
.app-root  { min-height: 100vh; display: flex; flex-direction: column; }
.main      { overflow: auto; flex: 1; }   /* this is what scrolls */
```

The default Chromium viewport is roughly 1280×633. Calling
`agent-browser screenshot --full <out>` captures the document scroll
surface. But the document doesn't scroll — `.main` does, internally.
So `--full` returns a viewport-sized image (1280×633) with everything
below the fold silently clipped.

### The protocol

For each screen you want to capture:

```bash
# 1. Set viewport tall enough that any reasonable screen fits
agent-browser set viewport 1280 2800
agent-browser wait 500

# 2. Measure the actual content bottom for the screen you're on
#    (max of the content selectors — see table below)
H=$(agent-browser eval "Math.max(
  document.querySelector('.dash')?.getBoundingClientRect().bottom || 0,
  document.querySelector('.syscard')?.getBoundingClientRect().bottom || 0
)" | tail -1 | tr -d '"')

# 3. Resize viewport to fit content + ~30px margin
agent-browser set viewport 1280 $((${H%.*} + 30))
agent-browser wait 400

# 4. Now --full actually works because the content fits in the viewport
agent-browser screenshot --full docs/plans/refs/<screen>.png
```

### Per-screen content selectors

Use these to measure the content bottom for each route. Pass the
union of the listed selectors to the `Math.max(...)` eval.

| Screen | Selectors |
|---|---|
| `/login` | `.app-root` (or any login form root) |
| `/` (Dashboard) | `.dash`, `.syscard` |
| Plant detail drawer | `.pd-links` (last child of the drawer) |
| `/live` | `.live-feed`, `.live-controls` |
| `/wiki` | `.wiki-sidebar`, `.wiki-doc` |
| Wiki Cmd+K palette open | same as `/wiki` (palette is fixed overlay) |

Your FE feature's selectors will be different from the mockup — adjust
this list as you build new components.

### Other things that bit the prep agent

1. **Don't trust `@eN` accessibility refs across navigation.** They
   re-number after every state change (tab switch, modal open). For
   tab navigation, use a JS click instead of `agent-browser click @eN`:
   ```bash
   agent-browser eval "document.querySelectorAll('.tab-btn')[1].click()"
   ```
   In the mockup specifically, ref-based clicks sometimes did not
   trigger React's onClick — JS click via `querySelectorAll` was more
   reliable. Your real SPA uses TanStack Router; click via a
   route-specific selector or use `agent-browser open <url>` to
   navigate directly.

2. **Drawer / modal state leaks across screen changes.** If you open
   the Plant detail drawer and then navigate to /live without
   closing it first, the drawer overlay carries over and contaminates
   the next screenshot. Cheapest reset: `agent-browser open <url>`
   (full reload) between distinct captures. Don't rely on
   `agent-browser press Escape` — it works sometimes, full reload
   always works.

3. **Auth state persists in cookies (or localStorage in the
   prototype).** To re-capture a logged-out screen, clear the
   relevant storage and reload:
   ```bash
   agent-browser eval "localStorage.clear()"
   # For your real SPA, clear the dirt_session cookie:
   agent-browser eval "document.cookie = 'dirt_session=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'"
   agent-browser open <url>
   ```

4. **Wait briefly between actions.** React re-renders are async; a
   click that returns "✓ Done" may not have produced its DOM update
   yet when the next command runs. `agent-browser wait 500` to
   `wait 1000` covers nearly all cases. The `wait` command takes
   either a selector (waits for it to exist) or a millisecond count.

5. **`agent-browser set viewport <w> <h>`**, not `agent-browser viewport`
   (which is a settings-help noun, not a command).

6. **Element-level screenshots (`agent-browser screenshot <selector>
   <path>`) sound clean but don't help with the inner-scroll problem
   either** — passing `.app-root` returns the viewport-sized
   bounding rect of `.app-root`, not its scrollHeight. Stick with the
   resize-and-fit protocol above.

### Comparing to a reference

For the Evaluator's `kind: visual` acceptance check, compare your
captured PNG to `docs/plans/refs/<feature>.png`:

```bash
# Same viewport height as the reference, then capture
REF_H=$(identify -format "%h" docs/plans/refs/dashboard.png)
agent-browser set viewport 1280 ${REF_H}
agent-browser wait 400
agent-browser screenshot --full /tmp/dashboard-actual.png
# Visual diff — pixelmatch or compare from imagemagick
compare -metric AE /tmp/dashboard-actual.png docs/plans/refs/dashboard.png /tmp/diff.png
```

Threshold for "matches reference" is a judgement call; ~1% pixel
difference accommodates anti-aliasing variance, font rendering
differences, etc. Investigate anything beyond that.

---

## Example: spawn one BE + one FE in parallel

```
[Single message, two Agent tool calls, both run_in_background: true]

Agent 1:
  description: "BE lane: backend.grow.current"
  subagent_type: general-purpose
  model: opus
  isolation: worktree
  run_in_background: true
  prompt: <SHARED skeleton + LANE_SPECIFIC_BLOCK backend, with
           {{FEATURE_ID}}=backend.grow.current,
           {{LANE}}=backend,
           {{BRANCH_PREFIX}}=feat/be/,
           {{ITERATION_BUDGET}}=10,
           {{NOTES_PATH}}=docs/plans/notes/backend.grow.current.md>

Agent 2:
  description: "FE lane: frontend.app.shell"
  subagent_type: general-purpose
  model: opus
  isolation: worktree
  run_in_background: true
  prompt: <SHARED skeleton + LANE_SPECIFIC_BLOCK frontend, with
           {{FEATURE_ID}}=frontend.app.shell,
           {{LANE}}=frontend,
           {{BRANCH_PREFIX}}=feat/fe/,
           {{ITERATION_BUDGET}}=15,
           {{NOTES_PATH}}=docs/plans/notes/frontend.app.shell.md>
```

Both wake on completion. Inspect the worktree branches, run the
Evaluator (foreground) against each, merge the green ones, repeat
with the next pair from the plan JSON's depends_on graph.

---

## Evaluator prompt (foreground, per-feature)

Drafted separately. The evaluator's job is narrower: drive the
running stack with agent-browser, verify acceptance criteria,
update plan JSON status. TODO once we've watched a couple of
generator runs end-to-end.
