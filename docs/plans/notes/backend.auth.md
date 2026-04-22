# backend.auth — generator notes

## Status: DONE

Generator exited STUCK on the first pass — pre-commit blocked the
implementation commit because `apps/tests/invariants/test_auth_boundary.py`
(human-owned) still asserted the pre-rewrite "every non-public route
redirects 302 → /login" contract, which this feature's plan explicitly
replaces with JSON 401 on `/api/*` + SPA fallback on everything else.

Planner landed the invariant rewrite (accompanying this branch; see
the `invariant(auth)` commit that precedes this feature's commit on
the branch). With the invariant matching the new contract, the
implementation's pre-commit passes and the generator's work lands
cleanly. Full invariant suite: 96 passed (up from 94 — the new
invariant parametrizes three tests, two of which expand across multiple
/api/ routes). Full per-app web suite: 28 passed, including the 8
test_auth_endpoints + 8 test_spa_serving tests this feature added.

## What's done

- **Auth API** — `POST /api/auth/login`, `POST /api/auth/logout`,
  `GET /api/auth/me` live on `apps/web/src/dirt_web/api/auth.py`. All
  three are carved out of AuthMiddleware as `/api/auth/*`. Login
  accepts JSON (`LoginRequest` from the generated contract models),
  sets `dirt_session` httponly+SameSite=Lax cookie, returns `User`.
  Logout clears the cookie and returns 204. `/me` returns `User` on
  valid cookie, 401 JSON on missing/expired/tampered cookie.
- **AuthMiddleware rewrite** (`apps/web/src/dirt_web/auth.py`) — gates
  only `/api/*` (401 JSON, no more 302 redirect). `/api/auth/*` and
  any `exclude_prefixes` (currently just `/mcp`) pass through. Every
  non-/api/ path falls through untouched so the SPA shell can render
  pre-auth.
- **SPA serving** (`apps/web/src/dirt_web/app.py`) — mounts
  `<web-ui-dist>/assets` at `/assets` via StaticFiles, and a new
  `SPAFallbackMiddleware` rewrites any 404 whose path is neither
  `/api/*` nor `/mcp` nor `/assets/*` into a FileResponse of
  `<web-ui-dist>/index.html`. Missing dist → logs WARN and returns
  503 placeholder.
- **Why middleware, not catch-all route** — a `@app.get("/{full_path:path}")`
  handler would register as a route and break `test_api_contract.py`
  (the `/{full_path:path}` pattern is not in the OpenAPI contract and
  not in `legacy_routes`). The middleware approach keeps the registered
  route table identical to the contract while still serving SPA
  deeplinks. This preserves an existing green invariant without
  widening `contract_status.json`.
- **Cleanup** — dropped `apps/web/src/dirt_web/templates/{index,login}.html`,
  `TEMPLATES_DIR` constant in `apps/web/src/dirt_web/__init__.py`, and
  `jinja2` + `python-multipart` deps from `apps/web/pyproject.toml`
  (deptry's per-rule DEP002 ignores for them went away with them).
- **New Settings field** — `web_ui_dist_dir: Path` on
  `dirt_shared.config.Settings` (default: `<repo>/web-ui/dist`,
  override via `DIRT_WEB_UI_DIST_DIR` env var). Also added a
  `web_ui_dist_dir` kwarg to `create_app()` so tests can point at a
  tmp_path fixture without having to fight
  `pydantic_settings.BaseSettings`' `validation_alias` behaviour (the
  field name isn't kwarg-settable when an alias is declared).
- **contract_status.json bookkeeping** —
  - removed from `expected_missing`: `POST /api/auth/login`,
    `POST /api/auth/logout`, `GET /api/auth/me`
  - removed from `legacy_routes`: `GET /`, `GET /login`,
    `POST /login`, `GET /logout`
- **Tests** — `apps/web/tests/test_auth_endpoints.py` (8 tests,
  login/logout/me happy paths + 401 unauth + request-body validation
  + proves /api/grow/current now 401s JSON instead of 302ing) and
  `apps/web/tests/test_spa_serving.py` (8 tests: index at /, catch-all
  for /live and nested client routes, /assets/main.js pass-through,
  /api/unknown → 404 JSON authed and 401 JSON unauthed — both
  different from the SPA shell, /api/auth/me without cookie → 401 JSON
  not 302, missing dist → 503 placeholder).
- **Legacy test updates** — `test_auth.py` + `test_app.py` deleted
  (superseded). `test_grow_endpoint.py`, `test_sensors_api.py`,
  `test_snapshots_api.py` updated to log in via
  `POST /api/auth/login {json}` instead of the old form-POST.
  `test_grow_current_requires_auth` flipped from `302 → /login` to
  `401 JSON`.

Full app suite:

```
$ uv run pytest apps/web/tests/ apps/shared/tests/ apps/mcp/tests/ apps/hwd/tests/ -q
143 passed in 25.09s
```

All 8 auth_endpoint + 8 spa_serving tests green.

## What's NOT done — and why

### Commit is blocked by pre-commit invariant failures

`uv run pytest apps/tests/invariants/ -q` fails with 13 failures — 3
pre-existing (see below, not mine), 10 caused by this feature but
inherent to the plan's mandate.

**10 failures in `apps/tests/invariants/test_auth_boundary.py`** —
parameterised over every route on `dirt_web.app.app`. The invariant
asserts that every route not in `PUBLIC_PATHS = {"/login", "/logout"}`
must respond to unauthenticated requests with `302 → /login`. This is
exactly the behaviour the plan explicitly removes:

> `implementation_notes`: "AuthMiddleware changes: gate only /api/* on
> auth (401 JSON on fail, no more 302 redirect). /api/auth/login,
> /api/auth/logout, /api/auth/me are carved out as public via
> security: []. Every non-/api/* path falls through to SPA serving —
> auth status is checked client-side via GET /api/auth/me."

The invariant file header declares it human-owned and protected by
hook. Per `CLAUDE.md` and the generator prompt, the agent must not
modify it and must escalate when an invariant fails. The conflict is
not a bug in my implementation — the invariant was written against
the pre-rewrite Jinja auth contract and needs a corresponding planner
edit to reflect the new cookie-session-gates-/api/* contract:

- `PUBLIC_PATHS` should become empty (or disappear entirely) — the
  legacy `/login` / `/logout` handlers are gone.
- The parameterised assertion should split by path prefix:
  - `/api/auth/*` — public, unauthenticated request is expected to
    hit the route handler (200 for login with good creds, 401 for me
    without cookie, 204 for logout, etc — or simpler, just "not a
    middleware interception").
  - `/api/*` otherwise — expect `401` + `application/json` body
    (`{"detail": "unauthorized"}`), no `Location` header.
  - non-/api/ paths — covered by SPA fallback, expect either 200
    (index.html) or 503 (dist missing) but NEVER 302.
- `test_mcp_*` cases are fine as-is — /mcp is still bearer-gated and
  I didn't touch it.

Once the invariant is updated by the planner, the pre-commit hook
passes and the worktree commits cleanly. All the implementation code
is ready.

### 3 pre-existing web-ui invariant failures (unrelated to this feature)

Confirmed green on local main before I touched anything; confirmed red
in my worktree before I wrote any code; confirmed still red after. Not
mine to fix:

```
FAILED apps/tests/invariants/test_typescript_dead_code.py::test_no_unused_files_exports_or_deps
FAILED apps/tests/invariants/test_webui_invariants_wired.py::test_tsc_showconfig_sentinels
FAILED apps/tests/invariants/test_webui_invariants_wired.py::test_eslint_printconfig_sentinels
```

Root cause looks like `pnpm exec biome`/`tsc`/`eslint` not resolving
in the worktree environment (stderr empty but exit non-zero). Probably
a pnpm-install-on-worktree-setup issue upstream; nothing in my diff
touches `web-ui/`.

### `/simplify` pass not yet run

Deferred until the invariant conflict is resolved and the first commit
lands. No point running simplify on uncommitted changes the hook won't
accept.

## Out-of-scope concerns noticed

### Legacy non-/api/ routes are now publicly accessible

Pre-rewrite, `/feed/live`, `/feed/image`, `/feed/status`,
`/sensors/current`, `/sensors/readings` (under the `/feed` + top-level
`/sensors` routers) all required auth because AuthMiddleware gated
every path. With the new "only /api/* is gated" rule they are
accessible without a cookie. They're all in `legacy_routes` and will
be deleted by their replacement features (`backend.feed.live`,
`backend.sensors.current`, `backend.sensors.history`) — so the
exposure window closes naturally as those features land. But if any
of them are queued behind this one's merge, there's a transient
"anyone can pull live JPEGs" exposure on the deployed stack.

Fix, if the planner wants it: extend `AuthMiddleware.PUBLIC_API_PREFIXES`
logic to a more general "gate /api/* AND these specific legacy paths"
set. Not implemented here because it sits outside this feature's
written scope and the plan's quoted language is unambiguous ("gate
only /api/*"). Flag for planner awareness.

### `SPAFallbackMiddleware` order-of-ops subtlety

The middleware has to be registered AFTER `AuthMiddleware` in the
Python code so that Starlette's reverse-order wrapping makes
SPAFallback the outer middleware. If a future hand pokes at the
`add_middleware` order, the SPA fallback will start intercepting 401
responses from auth and rewriting them to 200 index.html — a fairly
silent breakage. Comment in `app.py` explains; a unit test that
asserts the authed/unauthed order specifically would harden it, but I
didn't add one (already covered indirectly by
`test_api_auth_me_without_cookie_returns_401_json`).

### `dirt_web/__init__.py` is now empty

Not a problem in itself, but `TEMPLATES_DIR` was the only export.
Kept as `__init__.py` (empty) per Python conventions rather than
deleting the file.

## Suggested next move

1. Human/planner updates `apps/tests/invariants/test_auth_boundary.py`
   to match the new /api/*-only-gated semantics (see exact shape
   above, under "10 failures"). The three `/login`-public-path
   clauses should go; the parameterised assertion should branch on
   path prefix.
2. Re-run `uv run pytest apps/tests/invariants/ -q` — should go
   green on the 10 auth_boundary failures (the 3 web-ui ones are
   environment-level, not feature-level).
3. Re-run `scripts/agent-fix`, `git add -A && git commit`. Pre-commit
   should now pass.
4. Run `/simplify` pass on the worktree; recommit as
   `chore(backend.auth): simplify pass`.
5. Evaluator spawn.
