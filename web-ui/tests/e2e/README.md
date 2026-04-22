# web-ui e2e suite (Playwright)

Typed end-to-end acceptance tests. Replaces the shell-script pattern at
`docs/plans/evaluator-checks/*.sh` for every FE feature landed after
`frontend.e2e.setup`.

## Layout

```
web-ui/
  playwright.config.ts              # test runner config
  tests/e2e/
    README.md                       # this file
    _helpers.ts                     # shared utilities (kept minimal)
    <feature_id>.spec.ts            # one file per FE feature
```

Helpers and spec files import from `@playwright/test`. The
`boundaries`-rule classification in `web-ui/invariants/eslint.config.ts`
is scoped to `src/**`, so e2e specs are free to import whatever they
need without triggering the layered-architecture lint.

## One-time setup per machine

```bash
pnpm --dir web-ui exec playwright install --with-deps chromium
```

This fetches the browser binaries into Playwright's machine-level
cache (`~/.cache/ms-playwright/`). It is NOT per-worktree; a fresh
`git worktree add` does not re-trigger the download. The orchestrator
runs this once on the host before merging; individual generator /
implementer agents do not need to run it themselves.

## Running the suite

With a `pnpm dev` already up on :5173:

```bash
pnpm --dir web-ui test:e2e                          # headless, all specs
pnpm --dir web-ui test:e2e -- app-shell.spec.ts     # one spec
pnpm --dir web-ui test:e2e:ui                       # interactive UI mode
```

If another worktree has already claimed :5173, point Playwright at the
port your dev server actually bound to:

```bash
PLAYWRIGHT_BASE_URL=http://localhost:5180 pnpm --dir web-ui test:e2e
```

## Authoring conventions — MANDATORY for implementer agents

### 1. One spec file per FE feature

Name it after the plan-JSON `features[].id`:

```
tests/e2e/<feature_id>.spec.ts
```

The plan-JSON `acceptance[].test_file` entry will point here. A single
spec file belonging to two features is a sign the plan split is wrong,
not that the convention should bend.

### 2. One `test(...)` block per plan-description assertion

The evaluator runs a **coverage audit**: it reads
`acceptance[].description` from the plan JSON, identifies each distinct
assertion (usually separated by commas or semicolons), and looks for a
matching `test(...)` case in your spec. **Coverage gaps fail the
audit.** So does a tautology (`expect(true).toBe(true)`) or a weaker
assertion than the plan asked for.

Split assertions generously. It is better to have seven one-line
`test(...)` blocks that each name a single behavior than one monster
`test("does everything", ...)` that is indistinguishable from a green
stub at grep-time.

### 3. Use typed locators — `getByRole`, `getByLabel`, `getByText`

These map onto the same accessibility tree that real users (and
screen-readers) see. Prefer them to raw `page.locator(".tab-btn")` CSS
selectors. Where an assertion asks about an ARIA attribute (like
`aria-current="page"`) that isn't exposed as a locator role, read it
directly with `toHaveAttribute` or fall back to a scoped
`page.evaluate`:

```ts
await expect(page.getByRole("button", { name: "Live" }))
  .toHaveAttribute("aria-current", "page");
```

Avoid inventing `data-testid` attributes to paper over markup that is
hard to select. If the markup is hard to select, it's probably also
hard to use — fix the markup first.

### 4. Wire console-error collection before navigation

`collectConsoleErrors(page)` from `_helpers.ts` must be called BEFORE
`page.goto(...)` — Playwright does not buffer earlier events:

```ts
import { collectConsoleErrors } from "./_helpers";

test("...", async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await page.goto("/");
  // ...exercises...
  expect(errors.read()).toEqual([]);
});
```

### 5. Document deviations in NOTES.md, not by weakening the test

If a plan-description assertion cannot be expressed idiomatically (say
it names a selector that conflicts with a lint rule, or a class that
isn't semantically meaningful), test the **equivalent-intent
behavior** and add a note to
`docs/plans/notes/<feature_id>.md` explaining: plan asserts X via Y;
implemented equivalent via Z because `<reason>`. Undocumented
deviations read as coverage gaps to the evaluator.

### 6. Don't start servers from the config

`playwright.config.ts` intentionally has **no** `webServer` block. The
operator (or CI) starts `pnpm dev` externally. This avoids worktree
collisions on :5173 when multiple lanes run in parallel.

## Reference spec

`app-shell.spec.ts` is the canonical example. It mirrors every
assertion in `docs/plans/evaluator-checks/app-shell.sh` as a typed
Playwright test and is the pattern future FE features should copy.

## Relationship to the legacy `.sh` scripts

The shell-script acceptance checks under
`docs/plans/evaluator-checks/*.sh` remain the evaluator's current
target for features landed before `frontend.e2e.setup`. They are
frozen — do not modify them, do not port them into e2e specs wholesale.
Each pre-setup feature migrates to a Playwright spec when its next
update lands.
