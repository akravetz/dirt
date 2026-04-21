# frontend.app.shell — generator notes

Branch: `worktree-agent-a3a047f9` (prefix `feat/fe/` in spec; this worktree
kept its pre-existing name).

## Done

- `web-ui/src/ui/TopBar.tsx` — `<header>` with brand `<h1>dirt.</h1>`,
  `<nav aria-label="Primary">` wrapping three `<button>` tabs
  (Dashboard / Live / Wiki), theme toggle button (aria-label matches
  `/theme|light|dark/i`), log-out button. Active tab carries
  `aria-current="page"` only — no sr-only tablist mirror, no
  `role="tab"`, no `aria-selected`, no `data-*` test hooks.
- `web-ui/src/routes/live.tsx` and `web-ui/src/routes/wiki.tsx` —
  placeholder file-based routes so `navigate({ to: "/live" | "/wiki" })`
  is typed against the regenerated `routeTree.gen.ts`.
- `web-ui/src/routes/__root.tsx` — mounts `<TopBar />` above `<Outlet />`
  and switches the layout to `flex flex-col`.
- `web-ui/src/routes/index.tsx` — dropped the duplicate brand `<h1>`
  (now lives in the TopBar) and left a minimal Dashboard placeholder.
- `web-ui/vite.config.ts` — added `resolve.alias['@']` → `./src` so
  runtime resolution mirrors the `@/*` tsconfig path. Without this the
  dev server failed to resolve `@/ui/TopBar`.
- Theme persistence goes through `web-ui/src/shared/storage.ts` (TS-09
  compliant); `<html data-theme="…">` is applied in a `useEffect`.

## Acceptance

- `docs/plans/evaluator-checks/app-shell.sh` → `PASS` against a live
  `pnpm dev` on :5173.
- `pnpm lint` (biome + eslint) → clean, 17 files.
- `pnpm typecheck` → clean.
- `pnpm build` → clean.
- `pnpm knip` → only the pre-existing "Configuration hints" that live
  in the human-owned `invariants/knip.json` (same list on `main`).
- `uv run pytest apps/tests/invariants/ -q` → 94 passed.

## Not done / out of scope

- The log-out button is a placeholder — it navigates to `/` rather than
  calling `/api/auth/logout`. The auth endpoint is not listed under
  this feature's `files` and no auth feature has landed yet. Wire this
  in a follow-up feature once the auth endpoint ships.
- No `@custom-variant dark` rule in `styles.css` yet. Toggling the
  theme flips `<html data-theme>` and persists the choice, but the
  palette does not yet change on dark. That's a styling-only feature
  for a later pass; the shell is theme-ready.

## Surprises

- The worktree was spawned at the `contract(webapp-v1)` commit but
  `main` had advanced with the rewritten acceptance script + element-
  types boundary update. Rebased onto the local `main` branch before
  starting; the latest plan JSON + script are the ones this feature
  targets.
- Three stale `vite` processes from the prior `agent-ad3d50d9`
  worktree were squatting ports 5173-5175. Had to kill them before
  my dev server could bind 5173 for the acceptance script. Might be
  worth giving the orchestrator a pre-spawn cleanup hook.

## Prior-run rejection — avoided

The prior run was rejected for adding a visually-hidden
`role="tablist"` ARIA mirror whose only purpose was to make the old
acceptance script's a11y-tree grep detect the active tab. This run
carries no such structure: the primary nav is `<button>` elements
inside `<nav aria-label="Primary">`, active state is solely the
native `aria-current="page"` attribute, and the acceptance script
reads the DOM directly via `agent-browser eval`.

DONE
