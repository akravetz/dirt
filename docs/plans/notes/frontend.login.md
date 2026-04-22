# frontend.login — generator notes

## Status: DONE

Generator exited without writing this file (observed flaky wrap-up
pattern from the /simplify handoff — the skill's "returning control"
message was taken as an exit cue; addressed in the updated generator
prompt). Orchestrator is filling in after the fact based on the
committed diff + agent's stdout summary.

## What's done

- **Route** — `web-ui/src/routes/login.tsx`. File-based TanStack
  Router route for `/login`. Uses `useMutation` against the typed
  api-client. Derives the error message from `mutation.error` (no
  redundant local `errorMessage` state); on success, imperatively
  navigates to `/`.
- **Form component** — `web-ui/src/ui/LoginScreen.tsx`. Botanical
  split-screen per the `docs/plans/refs/login.png` mockup. Uses the
  dirt paper/ink/magenta palette tokens from `web-ui/src/styles.css`.
  Idiomatic ARIA: form is a `<form>`, inputs have `name=` attributes
  the acceptance script queries, the error is a `<div role="alert">`
  + `aria-invalid="true"` on the inputs when invalid. Explicitly
  documented in a header comment that no sr-only mirror / parallel
  structure / data-testid is used.
- **MSW handlers** — `web-ui/src/mocks/handlers.ts` appended with
  `/api/auth/login`, `/api/auth/logout`, `/api/auth/me` handlers.
  Login accepts `{username: "admin", password: "changeme"}` → 200
  + User body + Set-Cookie; anything else → 401 JSON error. Logout
  → 204 + cookie-clear. /me returns the last-login'd user while
  `sessionUser` is set, else 401. Types come from
  `web-ui/src/api-client/generated/schema.ts` via the generated
  `components["schemas"]` (duck-typed at the fixture level because
  `mocks → api-client` is disallowed by the boundaries invariant
  — the shapes still match because both import the same frozen
  contract). After the simplify pass, `authHandlers` intermediate
  array was collapsed into the direct `handlers` export.
- **Root layout** — small tweak to `web-ui/src/routes/__root.tsx`
  to coexist with the new `/login` route (doesn't render TopBar on
  login).
- **Palette tokens** — new entries in `web-ui/src/styles.css` for
  the botanical split-screen surfaces (no arbitrary hex values per
  TS-15 invariant).
- **Routes** — regenerated `web-ui/src/routeTree.gen.ts` reflecting
  the new `/login` route.

## Acceptance

- `docs/plans/evaluator-checks/login.sh` — PASS end-to-end against
  `pnpm dev` on :5173. Form renders, bad creds show error, good
  creds navigate to `/`, console clean.
- `pnpm lint` / `typecheck` / `knip` / `build` — all clean.
- `pnpm test` — passes (includes the MSW smoke from
  `frontend.mocks.setup`; no new tests added here, but the existing
  smoke confirms MSW node-mode + the new handlers interoperate).

## Parallel-lane context

This is the first FE feature built against MSW mocks in parallel with
its backing BE (`backend.auth`). The MSW handlers will remain active
in dev/test after merge; in prod (FastAPI-served `dist/`), MSW is
tree-shaken out and the real `/api/auth/*` endpoints (from
`backend.auth`) serve the requests. No post-merge "wire-up" step is
needed — the same component code talks to the mock in dev and the
real endpoint in prod.

## Surprises / out-of-scope concerns

- The `mocks → api-client` import-boundary rule forces the fixture's
  type shape to be duck-typed against `components["schemas"]` rather
  than directly importing the generated types. Current types match
  the contract; if future FE features want to reuse the generated
  types in mocks, the boundaries rule could be relaxed to allow
  `mocks → api-client/generated/` (not the whole api-client).
- The login response mock sets `Set-Cookie` header literally; MSW's
  Service Worker doesn't always persist cookies the way a real
  browser+server dance would. Acceptance script relies on the
  client-side navigation cue (URL changes to `/` after 200), not on
  cookie verification. Works for dev; real `/api/auth/me` roundtrip
  post-merge will verify the cookie with the real BE.

## Next move

Cherry-pick `feat/fe/frontend.login` onto main after `backend.auth`
lands. Flip plan JSON status to `done`, commit verdict file.
