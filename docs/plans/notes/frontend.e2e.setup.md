# frontend.e2e.setup — generator notes

## Done

Wired Playwright as the FE e2e harness for all features landed after
this one. The deliverables match the plan JSON `files` list:

- `web-ui/playwright.config.ts` — `testDir: "./tests/e2e"`,
  chromium-only, `baseURL` defaults to `http://localhost:5173` with a
  `PLAYWRIGHT_BASE_URL` env-var override for parallel-worktree port
  collisions. Deliberately **no** `webServer` block (see the Deviation
  section below).
- `web-ui/tests/e2e/app-shell.spec.ts` — reference translation of
  `docs/plans/evaluator-checks/app-shell.sh`. Seven `test(...)` blocks,
  one per assertion in the plan-JSON acceptance description:
  1. brand heading renders,
  2. exactly 3 tab buttons (Dashboard / Live / Wiki),
  3. theme-toggle button present,
  4. clicking Dashboard → `/` + `aria-current="page"`,
  5. clicking Live → `/live` + `aria-current="page"`,
  6. clicking Wiki → `/wiki` + `aria-current="page"`,
  7. console is clean.
- `web-ui/tests/e2e/_helpers.ts` — `collectConsoleErrors(page)` only.
  Kept intentionally minimal; the README codifies the growth rule
  ("second-use factoring, not first-anticipated-use").
- `web-ui/tests/e2e/README.md` — authoring conventions for future FE
  implementer agents (one spec per feature, one `test(...)` per
  plan-description assertion, typed locators, deviation-in-NOTES,
  etc.).
- `web-ui/package.json` — `test:e2e` + `test:e2e:ui` scripts;
  `@playwright/test` as a devDep.
- `web-ui/.gitignore` — ignores `test-results/`, `playwright-report/`,
  `.playwright/`.

## Acceptance status

| Criterion | Status | Evidence |
|---|---|---|
| lint (`pnpm lint`) | pass | `biome check . && eslint .` — no fixes applied, 26 files clean. |
| typecheck (`pnpm typecheck`) | pass | `tsc --noEmit` — exit 0, no errors. |
| knip (`pnpm knip`) | pass | 7 configuration hints, zero errors, exit 0. |
| build (`pnpm build`) | pass | `tsc -b && vite build` — all chunks emitted, no errors. |
| e2e (`pnpm test:e2e -- app-shell.spec.ts`) | pass (7/7) | Verified against `pnpm dev --port 5180` with `PLAYWRIGHT_BASE_URL=http://localhost:5180`; 7 passed in 1.9 s. |
| invariant (legacy `.sh` still passes) | not re-run here | The feature diff does **not** touch `docs/plans/evaluator-checks/app-shell.sh`; diff confined to `web-ui/**`. The legacy path is structurally unchanged, so the .sh script remains the evaluator's current rubric for `frontend.app.shell` until it's retired. |

Full invariants suite (`uv run pytest apps/tests/invariants/ -q`) also
green — 97 passed in 4.94 s.

## Deviations + rationale

### 1. No `webServer` block in `playwright.config.ts`

Plan `implementation_notes` suggested "webServer starts `pnpm dev` on
:5173 on CI (locally, assume the dev server is running)." I chose to
**omit the `webServer` block entirely** — CI and local both assume an
external `pnpm dev`. Reason: the plan explicitly supports multiple
parallel worktrees (BE + FE generator lanes), and an auto-started
webServer would race the user's already-running dev server plus any
parallel worktree's dev server on :5173, producing `EADDRINUSE`
failures that mask real test errors. The `PLAYWRIGHT_BASE_URL`
override replaces the collision-prone auto-start. If CI grows a need
for a one-shot dev server, the CI script can `pnpm dev &`
externally — same net effect, no config-level coupling.

### 2. Port override used during local acceptance

The worktree's host already had :5173 and :5174 occupied by other
agent processes at test time. To verify the spec passes, I ran the
dev server on :5180 and set `PLAYWRIGHT_BASE_URL=http://localhost:5180`.
The config still defaults to :5173 as the plan spec requires;
the override is an operational mechanism, not a config change.

### 3. Playwright browser install NOT in the commit

Plan note: "run `pnpm exec playwright install --with-deps chromium` in
the setup or document that operators run it once per clone." The
browser binaries are a machine-level cache
(`~/.cache/ms-playwright/`), not worktree-local — committing the
install would be a no-op, and running it in the generator would waste
170 MB + time per worktree. Documented as a one-time host-level step
in `tests/e2e/README.md`. The orchestrator will run the install on
the host before merging; any subsequent worktree benefits from the
shared cache.

## Contract / out-of-scope observations

None. This feature is pure e2e-infrastructure; it neither consumes
contract endpoints nor touches any of the off-limits trees
(`apps/hwd/**`, `web-ui/invariants/**`, `web-ui/src/api-client/generated/**`,
`contracts/webapp-v1.yaml`, `apps/tests/invariants/test_*.py`,
`docs/plans/evaluator-checks/**`).

## Suggested next move

Orchestrator should:

1. Run `pnpm --dir web-ui exec playwright install chromium` on the
   host once (already done during this generator's acceptance run;
   subsequent `git clone`s will need it).
2. Spawn the evaluator for `frontend.e2e.setup`. The evaluator will
   re-run lint / typecheck / knip / build / `pnpm test:e2e --
   app-shell.spec.ts` against the worktree.
3. On pass + merge, future FE feature prompts can reference
   `web-ui/tests/e2e/README.md` + `web-ui/tests/e2e/app-shell.spec.ts`
   as the authoring pattern for their own `.spec.ts` files.
