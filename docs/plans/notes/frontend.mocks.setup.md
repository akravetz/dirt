# Notes — frontend.mocks.setup

Generator lane: frontend. Branch: `feat/fe/frontend.mocks.setup`
(worktree branch `worktree-agent-afc3dc7e`). Pnpm 10.33, Node via fnm.

## Done

- Installed `msw@^2.13.4` as a devDependency; also added `jsdom@^26.1.0`
  (Vitest jsdom env). `typescript-eslint`/`typescript` peer warning is
  pre-existing and unrelated (openapi-typescript wants `typescript@^5`,
  project pins `~6.0.2`).
- Ran `pnpm exec msw init public --save` once. Output:
  `web-ui/public/mockServiceWorker.js` (committed; regenerated only on
  MSW major upgrades) and `msw.workerDirectory: ["public"]` appended to
  `web-ui/package.json`.
- Created `web-ui/src/mocks/handlers.ts` — exports
  `handlers: RequestHandler[] = []`. Future FE features append their own
  `http.{get,post,...}` resolvers here. v2 signatures only
  (`({ request, params, cookies }) => HttpResponse.json(...)`).
- `web-ui/src/mocks/browser.ts` — `setupWorker(...handlers)` from
  `msw/browser`.
- `web-ui/src/mocks/server.ts` — `setupServer(...handlers)` from
  `msw/node`.
- `web-ui/src/test-setup.ts` — node-mode lifecycle (`listen` /
  `resetHandlers` / `close`) with `onUnhandledRequest: "error"`.
- `web-ui/vitest.config.ts` — merges `vite.config.ts`, sets
  `environment: "jsdom"`, `setupFiles: ["./src/test-setup.ts"]`.
- `web-ui/src/main.tsx` — added `enableMocking()` that early-returns
  unless `import.meta.env.DEV`, then **dynamically** imports
  `./mocks/browser` and calls `worker.start({ onUnhandledRequest: "bypass" })`.
  `createRoot(...).render(...)` now runs inside
  `enableMocking().then(...)`. The DEV gate + dynamic import are the
  mechanism that lets Rollup tree-shake msw out of prod.
- Smoke test at `web-ui/src/mocks/__tests__/handlers.test.ts` — registers
  a per-test `http.get("http://localhost/api/__smoke", ...)` via
  `server.use(...)`, `fetch`es it, asserts body. Passes under
  `pnpm test`.
- Root shim `web-ui/eslint.config.ts` — added a file-scoped override
  that turns off `no-restricted-globals` for
  `src/mocks/__tests__/*.{ts,tsx}`. The MSW smoke test needs raw
  `fetch` to *prove* interception at the network layer; running it
  through the generated api-client would defeat the purpose (api-client
  only knows contract paths, smoke test uses a synthetic
  `/api/__smoke`). Scope is tight (test files under
  `src/mocks/__tests__/` only) and the meta-invariant
  `test_webui_invariants_wired.py` still passes (5 tests green after
  the edit).

## Acceptance status

- `pnpm lint` — PASS (biome check + eslint; `exit 0`).
- `pnpm typecheck` — PASS.
- `pnpm knip` — PASS (`exit 0`; only configuration hints, no errors).
- `pnpm build` — PASS. Tree-shake verified:
  `grep -rli 'mock-service-worker\|msw' web-ui/dist/` returns only
  `dist/mockServiceWorker.js` (the static-asset copy of
  `public/mockServiceWorker.js`, not referenced by `dist/index.html`).
  No msw bytes in any `dist/assets/*.js`.
- `pnpm test` — PASS (1 file, 1 test).
- `uv run pytest apps/tests/invariants/ -q` — PASS (94 passed).
- `kind: invariant` (boundaries-rule-demonstration) —
  **DEFERRED-PENDING-PLANNER** (see Escalation below).

## Escalation — planner action required

The plan JSON `implementation_notes` section (f) requires adding a new
boundaries `element-type` `mocks` to the `ELEMENT_TYPES` array in
`web-ui/invariants/eslint.config.ts` and a matching dependency rule
restricting imports to the mocks layer. That file is on the
`off_limits` list (`web-ui/invariants/**`, human-owned), so this
generator cannot land the change. Describe the exact edit here so the
planner can land it in a follow-up commit.

### Observed behaviour without the invariant edit

Throwaway demo file `web-ui/src/ui/_forbidden_import_demo.tsx` that
imports `@/mocks/handlers` was created and `pnpm lint` was run:

```
> biome check . && eslint .
Checked 24 files in 35ms. No fixes applied.
exit=0
```

Direct ESLint on just that file:

```
$ pnpm exec eslint src/ui/_forbidden_import_demo.tsx
exit=0
```

No `boundaries/dependencies` error fires. That's because
`src/mocks/**` is not classified as any `element-type` in the current
`ELEMENT_TYPES` array, so files under it resolve to the
unknown-element bucket and the dependency rule can't match them. The
throwaway file has been removed.

### Exact edit the planner should land in `web-ui/invariants/eslint.config.ts`

1. Add a `mocks` element-type to `ELEMENT_TYPES`. Insert before the
   `api-client` entry (specific-before-generic is the convention for
   this array). Verbatim snippet to splice in:

   ```ts
   // mocks/** — MSW v2 request handlers + setupWorker/setupServer
   // wiring. Only the composition root (src/main.tsx) and test files
   // may import from this element; UI / routes / features / api-client
   // / shared MUST NOT. Keeps the mock surface from leaking into
   // production code paths even though msw itself is tree-shaken out
   // of the prod bundle.
   { type: "mocks", pattern: "src/mocks/**", mode: "folder" },
   ```

2. Extend the `boundaries/dependencies` `rules:` array with the
   import-direction rules for the new element. The `main` override
   already allows `main → *` implicitly only if its `allow.to.type`
   list names every element; the current list does not include
   `"mocks"`, so main must be amended. Verbatim edit to the existing
   `from: { type: "main" }` rule — append `"mocks"` to the `type:`
   array:

   ```ts
   {
     from: { type: "main" },
     allow: {
       to: { type: ["main", "routes", "features", "api-client", "ui", "shared", "mocks"] },
     },
   },
   ```

3. Append a new rule after the existing `from: { type: "shared" }`
   block so type="mocks" itself is allowed to import nothing outside
   its own element + shared (handlers pull in msw + `HttpResponse`;
   they shouldn't reach into ui/features/api-client):

   ```ts
   {
     from: { type: "mocks" },
     allow: { to: { type: ["mocks", "shared"] } },
   },
   ```

4. No rule is added for `features → mocks`, `routes → mocks`,
   `api-client → mocks`, or `ui → mocks`. The `default: "disallow"`
   global already rejects any import direction not explicitly allowed,
   so omitting these is the mechanism that turns forbidden imports
   into lint errors.

5. Because test files live under `src/<dir>/__tests__/` (per Vitest
   `include` pattern in `vitest.config.ts` — `src/**/*.{test,spec}.{ts,tsx}`),
   they will currently inherit the element-type of their parent
   folder (e.g. a test under `src/mocks/__tests__/handlers.test.ts`
   matches `src/mocks/**` → `type: "mocks"`; a future test under
   `src/ui/Button/__tests__/Button.test.tsx` would be `type: "ui"`).
   That's acceptable: tests for a layer are part of that layer and
   should respect its import rules. If the planner later wants to
   allow tests under any layer to reach into `mocks/` (e.g. to
   `import { server } from "@/mocks/server"` for test scaffolding),
   add a tests element-type with a pattern like
   `src/**/*.{test,spec}.{ts,tsx}` BEFORE the generic layer patterns
   (first-match-wins) and allow `tests → mocks`. Not required for
   this feature — the smoke test lives under `src/mocks/__tests__/`
   which is already type="mocks", and from mocks → mocks is allowed.

### Verification once the planner lands the edit

After the invariant change is in place, the generator's acceptance
criterion can be proven with:

```bash
cd web-ui
cat > src/ui/_forbidden_import_demo.tsx <<'EOF'
import { handlers } from "@/mocks/handlers";
export const _forbidden = handlers;
EOF
pnpm lint 2>&1 | grep -i boundaries
# expected: a boundaries/dependencies error pointing at
#   "No rule allows the dependency" or similar for ui → mocks.
rm src/ui/_forbidden_import_demo.tsx
```

Record the exact lint error text in this section when re-run.

## Concerns flagged for the planner / next agent

1. **Meta-invariant comment-stripping regex has a glob-pattern
   collision.** `apps/tests/invariants/test_webui_invariants_wired.py::_strip_line_comments`
   does `re.sub(r'/\*.*?\*/', '', src, flags=re.DOTALL)` BEFORE
   stripping `//` line comments. If the shim contains a `/**` glob
   inside a line comment AND a later `*/` anywhere in the file, the
   block-comment regex matches across them and eats real code. I hit
   this when my override's `files: ["…/**/*.{ts,tsx}"]` glob combined
   with a `/**` inside the docstring-style banner comment. Worked
   around by splitting the glob into two patterns. Worth the
   human-owner's attention because it's a latent footgun for any
   future shim edit.

2. **Peer-dep warning on install.** `openapi-typescript@7.13.0` expects
   `typescript@^5`, project pins `typescript@~6.0.2`. Pre-existing,
   unchanged by this feature.

## Suggested next move

1. Planner lands the boundaries-rule edit to `web-ui/invariants/eslint.config.ts`
   per "Exact edit" section above (one commit, no code changes).
2. Re-run the throwaway forbidden-import verification and record the
   lint error text here.
3. Flip `features[].acceptance` (the `kind: "invariant"` entry) from
   deferred to pass in the evaluator verdict.

DONE modulo one deferred acceptance item (planner-owned invariant edit).
