# Local Dev Environment Harness

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a human or agent can run one command, `make dev-up`, and get a local frontend connected to the real hosted control-plane API with local-only credentials and seeded data. This replaces the need to hand-maintain MSW fixtures for the dashboard and live pages while keeping production safe.

The observable result is a browser at the Vite URL that can log in, render dashboard sites/tents/metrics/schedules/devices through the control-plane API, and iterate on frontend code without touching the deployed Railway services. The user should not need to know the Atlas cloud migration command, the control-plane env vars, the gateway token bootstrap step, or how to point Vite at the API.

The public interface should be the root `Makefile`. The implementation script should be named `scripts/dev-env`, not `scripts/dev-up`, because it manages the whole local environment lifecycle: start, stop, reset, and status.


## Progress

- [x] (2026-05-25) Reviewed `.agents/PLANS.md`, `docs/rules/simple-clean-architecture.md`, `docs/commands.md`, `docs/database.md`, `docs/hosted-control-plane.md`, control-plane startup/config, cloud migrations, gateway one-shot sync, and web-ui API base selection.
- [x] (2026-05-25) Decided on root `Makefile` as the canonical public command catalog and `scripts/dev-env` as the direct implementation harness.
- [ ] Implement root `Makefile` targets.
- [ ] Implement `scripts/dev-env`.
- [ ] Add focused validation for the command surface and safe env generation.
- [ ] Update `docs/commands.md` and relevant agent-facing instructions to prefer `make` targets.
- [ ] Run the harness end to end and record the resulting URLs and health checks.


## Surprises & Discoveries

- Observation: The current repository has no root `Makefile`, `Taskfile`, or `justfile`, so adding a root `Makefile` is not a migration from an existing public command surface.
  Evidence: `find /home/akcom/code/dirt -maxdepth 2 -type f \( -iname 'Makefile' -o -iname 'Taskfile.yml' -o -iname 'Taskfile.yaml' -o -iname 'justfile' \) -print` returned no files.

- Observation: The control plane does not create or migrate its own schema at startup. Startup only calls `ping(engine)`, and tests create throwaway cloud databases by applying `cloud/migrations` explicitly.
  Evidence: `apps/control-plane/src/dirt_control/db.py:24` says `Atlas owns all cloud DDL`; `apps/control-plane/tests/conftest.py` applies `atlas migrate apply --dir file://cloud/migrations --url ...`.

- Observation: Local browser auth will fail over plain HTTP unless `DIRT_CLOUD_SESSION_COOKIE_SECURE=false` is set for the control-plane process.
  Evidence: `apps/control-plane/src/dirt_control/settings.py` defaults `DIRT_CLOUD_SESSION_COOKIE_SECURE` to `true`, and `BrowserSessionManager` uses that setting when writing the login cookie.

- Observation: One-shot gateway sync is enough to populate real catalog/latest metrics/rollup/asset-retention projections, but continuous gateway command polling can execute real PTZ commands.
  Evidence: `apps/gateway/src/dirt_gateway/main.py` has `run_gateway_once`; `apps/gateway/src/dirt_gateway/sync.py` collects heartbeat, catalog, latest metrics, rollups, and optional asset upload; continuous `run_gateway()` also starts `GatewayCommandService`.

- Observation: Asset upload is the least clean local path because the no-S3 fallback returns signed URLs under `DIRT_CLOUD_ASSET_PUBLIC_BASE_URL`, but it does not serve local bytes.
  Evidence: `apps/control-plane/src/dirt_control/api/gateway.py` signs upload URLs with `UrlSigner` when no object store is configured; `apps/control-plane/src/dirt_control/api/browser.py` returns signed asset URLs the same way.


## Decision Log

- Decision: Use a root `Makefile` as the public command surface.
  Rationale: `make` is broadly available and is already a familiar entry point for humans and agents. A Makefile is well suited to `.PHONY` command targets such as `dev-up` and `agent-fix`, but not to complex process orchestration.
  Date/Author: 2026-05-25 / Codex.

- Decision: Put lifecycle logic in `scripts/dev-env`, not in Make recipes.
  Rationale: The harness must generate local secrets, create/migrate/drop a database on explicit reset, bootstrap a gateway credential, start and stop child processes, trap signals, write logs and state files, and report status. That belongs in a real script with explicit control flow.
  Date/Author: 2026-05-25 / Codex.

- Decision: Name the implementation script `scripts/dev-env` rather than `scripts/dev-up`.
  Rationale: The script owns environment lifecycle commands, not only startup. `dev-env --down`, `dev-env --reset`, and `dev-env --status` should live with the same implementation.
  Date/Author: 2026-05-25 / user request and Codex.

- Decision: Seed local cloud data through the real gateway projection by default, but run only one sync cycle.
  Rationale: This preserves backend/frontend cohesion without continuous command polling. It avoids MSW fixture maintenance and avoids making `/live` clicks move real hardware by default.
  Date/Author: 2026-05-25 / Codex.

- Decision: Disable asset sync by default for `make dev-up`.
  Rationale: Dashboard catalog/metrics/schedules/devices are the primary frontend iteration data. Asset upload requires a local object serving strategy that is separate from control-plane API cohesion. Leaving it disabled avoids broken signed image URLs and retry churn while the rest of the stack works.
  Date/Author: 2026-05-25 / Codex.

- Decision: Use explicit Atlas `--dir` and `--url` arguments for the dev cloud database instead of `atlas migrate apply --env cloud`.
  Rationale: The harness should never depend on ambient `DIRT_CLOUD_DATABASE_URL` or production Railway env. An explicit URL to an isolated dev database is simpler and safer.
  Date/Author: 2026-05-25 / Codex.


## Outcomes & Retrospective

No implementation has been completed yet. The expected outcome is a small root command catalog plus a lifecycle script that can be run repeatedly by agents without knowing the underlying control-plane setup.


## Context and Orientation

The frontend lives in `web-ui/`. It is a Vite React app. Its API client reads `VITE_DIRT_API_BASE_URL` from `web-ui/src/api-client/hosted.ts`; if unset, it uses `/` as the API base. For local control-plane development, Vite should run on its deterministic worktree port and set `VITE_DIRT_API_BASE_URL=http://127.0.0.1:<api-port>`.

The hosted control-plane API lives in `apps/control-plane/`. The Railway start command in `apps/control-plane/railway.json` is:

    PYTHONPATH=/app/src uvicorn dirt_control.app:create_app --factory --host 0.0.0.0 --port $PORT

For local development, the equivalent command should bind to `127.0.0.1` and use a local port. The FastAPI app is created by `dirt_control.app:create_app`. It requires `CloudSettings`, including:

- `DIRT_CLOUD_DATABASE_URL`
- `DIRT_CLOUD_ADMIN_USERNAME`
- `DIRT_CLOUD_ADMIN_PASSWORD_HASH`
- `DIRT_CLOUD_SESSION_SECRET`
- `DIRT_CLOUD_SESSION_COOKIE_SECURE=false` for local HTTP
- `DIRT_CLOUD_ALLOWED_ORIGINS` matching the Vite origin
- `DIRT_CLOUD_SITE_ID=homebox`

The cloud database schema is in `cloud/migrations/`, separate from the local hardware database schema in `migrations/`. The harness must use a separate development cloud database, for example `dirt_cloud_dev_<worktree_hash>`, and must not use the live local `dirt` database or production Railway database.

The local gateway lives in `apps/gateway/`. The one-shot command:

    uv run --package dirt-gateway python -m dirt_gateway.main --once

uses `DIRT_CLOUD_API_BASE_URL`, `DIRT_CLOUD_GATEWAY_ID`, `DIRT_CLOUD_GATEWAY_TOKEN`, and `DIRT_CLOUD_SITE_ID` from environment via shared settings. It reads local operational state from the live local hardware database and writes projections to the configured cloud API. It should run once during `make dev-up` to seed the local control-plane database. The continuous gateway should not be started by default because it also runs cloud command polling and can execute real PTZ operations.

The existing script `scripts/worktree-port` returns a deterministic Vite port per worktree in the `5170-5199` range. `scripts/dev-env` should reuse that for the web UI and derive a separate deterministic API port from the same worktree identity, such as `8020-8049`.


## Plan of Work

Milestone 1: Add the public command catalog.

Create a root `Makefile` with `.PHONY` targets:

- `help`
- `dev-up`
- `dev-down`
- `dev-reset`
- `dev-status`
- `agent-fix`
- `fix`

Each target should delegate to scripts. The Makefile should not embed the orchestration logic. `agent-fix` should call `scripts/agent-fix`; `fix` should be an alias. The dev targets should call `scripts/dev-env` with the relevant lifecycle flag.

Milestone 2: Implement `scripts/dev-env`.

Use a strict script with clear subcommands:

- default or `up`
- `--down` or `down`
- `--reset` or `reset`
- `--status` or `status`

The script may be Bash or Python. Prefer Python if implementing process supervision and state-file handling becomes awkward in Bash. The script should:

1. Resolve repo root.
2. Compute deterministic web and API ports.
3. Create `var/dev/control-plane/`.
4. Generate or reuse local-only credentials in `var/dev/control-plane/env`.
5. Create a dedicated cloud dev database if missing.
6. Apply `cloud/migrations` to that database with explicit `--dir` and `--url`.
7. Bootstrap the gateway credential using `uv run --package dirt-control-plane python -m dirt_control.bootstrap_gateway`.
8. Start uvicorn for `apps/control-plane`.
9. Wait for `http://127.0.0.1:<api-port>/healthz`.
10. Run one gateway sync cycle with `DIRT_CLOUD_ASSET_SYNC_ENABLED=false`.
11. Start Vite through `pnpm --dir web-ui dev` with `VITE_DIRT_API_BASE_URL` set.
12. Trap process exit and clean up child processes it started.

The script should write logs under `var/dev/control-plane/logs/` and a state file under `var/dev/control-plane/state.json` containing ports, PIDs, database name, and URLs. It must not print generated secrets by default. It may print the local username and where the password file lives.

Milestone 3: Add local database recovery and status behavior.

`make dev-status` should report whether the API and web ports are reachable, show the dev database name, and point to logs. `make dev-down` should stop processes recorded in the state file if still running. `make dev-reset` should stop processes and drop/recreate only the computed `dirt_cloud_dev_<worktree_hash>` database before starting again.

The script must refuse to drop databases whose names do not start with the expected prefix. This is a hard safety rule.

Milestone 4: Update documentation.

Update `docs/commands.md` so the canonical frontend iteration path is:

    make dev-up

Document lower-level commands only as debugging details. Update the commit instructions to prefer:

    make agent-fix

The existing `scripts/agent-fix` remains the implementation command because hooks and humans may still call it directly, but docs should present the Make target as the public interface.

Milestone 5: Validate end to end.

Run the validation commands listed below. Then open the Vite URL, log in with local credentials, and confirm the dashboard renders using the local control-plane API. If the local hardware database has no current gateway-projected data, the page should still load with real API empty states rather than mock data.


## Concrete Steps

From the repo root:

    cd /home/akcom/code/dirt

Create the Makefile and script:

    $EDITOR Makefile
    $EDITOR scripts/dev-env
    chmod +x scripts/dev-env

Run format/fix and tests:

    make agent-fix
    uv run pytest apps/control-plane/tests -q
    uv run pytest apps/gateway/tests -q
    pnpm --dir web-ui typecheck

Run the harness:

    make dev-up

Expected terminal behavior:

- It prints the API URL, web URL, and log paths.
- It does not print gateway tokens, session secrets, password hashes, or production env values.
- It eventually leaves Vite running in the foreground.

In a separate terminal:

    make dev-status

Expected behavior:

- It reports the control-plane API as reachable at `http://127.0.0.1:<api-port>/healthz`.
- It reports the web UI as reachable at `http://127.0.0.1:<web-port>/`.
- It reports the dev database name under the safe `dirt_cloud_dev_` prefix.

Stop the environment:

    make dev-down

Reset the environment:

    make dev-reset

Expected behavior:

- It only drops the computed dev cloud database.
- It recreates and migrates the database.
- It starts the environment again.


## Validation and Acceptance

The change is accepted when:

- `make help` lists `dev-up`, `dev-down`, `dev-reset`, `dev-status`, `agent-fix`, and `fix`.
- `make agent-fix` runs the existing `scripts/agent-fix` workflow.
- `make dev-up` can be run from a clean shell with no `DIRT_CLOUD_DATABASE_URL` pointed at production and still creates a local-only dev cloud database.
- `make dev-up` does not use `.env.prod`.
- `make dev-up` applies `cloud/migrations` to the dev cloud database.
- `make dev-up` starts the local control-plane API and web UI.
- The Vite frontend has `VITE_DIRT_API_BASE_URL` set to the local API URL.
- Local browser login succeeds over HTTP because `DIRT_CLOUD_SESSION_COOKIE_SECURE=false`.
- CORS allows the Vite origin because `DIRT_CLOUD_ALLOWED_ORIGINS` includes the computed web URL.
- Dashboard API calls go to the local control-plane API, not Railway and not MSW.
- `make dev-down` stops started processes without killing unrelated services.
- `make dev-reset` refuses to drop any database outside the expected dev prefix.

Automated validation should include at least:

    uv run pytest apps/control-plane/tests -q
    uv run pytest apps/gateway/tests -q
    pnpm --dir web-ui typecheck

If adding unit tests around `scripts/dev-env`, prefer behavior checks such as safe database name validation, env-file generation without leaking secrets, and command construction. Do not test mutable generated passwords or exact port numbers except when the deterministic algorithm itself is the behavior under test.


## Idempotence and Recovery

Normal `make dev-up` should be safe to repeat. It should reuse the existing dev cloud database, re-apply migrations idempotently, refresh the gateway credential, run one gateway sync, and restart local child processes as needed.

`make dev-reset` is intentionally destructive only for the computed dev cloud database. It must stop existing child processes first, verify the database name prefix, drop the database, recreate it, apply migrations, and then start the environment.

`make dev-down` should be safe if no processes are running. It should report stale PIDs and remove or update the state file without failing loudly.

If Atlas migration fails, the script should stop the API/web startup path and print the migration log path. If the API starts but gateway seeding fails, the script should keep the API and Vite available but report that the dashboard may show empty data. That failure should be visible in logs and terminal output.

If Vite exits, the foreground `make dev-up` process should shut down the API child it started before returning.


## Artifacts and Notes

Relevant existing files:

- `scripts/worktree-port` computes deterministic Vite ports.
- `web-ui/src/api-client/hosted.ts` reads `VITE_DIRT_API_BASE_URL`.
- `apps/control-plane/railway.json` documents the production uvicorn factory command.
- `apps/control-plane/src/dirt_control/app.py` creates the FastAPI app and installs CORS only when origins are configured.
- `apps/control-plane/src/dirt_control/settings.py` defines required cloud settings and local cookie behavior.
- `apps/control-plane/src/dirt_control/bootstrap_gateway.py` seeds the gateway credential.
- `apps/gateway/src/dirt_gateway/main.py` exposes the one-shot gateway sync path.
- `cloud/migrations/` holds the hosted control-plane schema migrations.

External references consulted while designing this plan:

- GNU Make manual, `.PHONY` targets: `https://www.gnu.org/software/make/manual/html_node/Phony-Targets.html`
- Taskfile guide: `https://taskfile.dev/docs/guide`
- Twelve-Factor App, dev/prod parity and backing services: `https://12factor.net/dev-prod-parity` and `https://12factor.net/backing-services`


## Interfaces and Dependencies

Public command interface:

- `make help`
- `make dev-up`
- `make dev-down`
- `make dev-reset`
- `make dev-status`
- `make agent-fix`
- `make fix`

Implementation script interface:

- `scripts/dev-env`
- `scripts/dev-env up`
- `scripts/dev-env down` or `scripts/dev-env --down`
- `scripts/dev-env reset` or `scripts/dev-env --reset`
- `scripts/dev-env status` or `scripts/dev-env --status`

Generated local state:

- `var/dev/control-plane/env`
- `var/dev/control-plane/state.json`
- `var/dev/control-plane/logs/control-plane.log`
- `var/dev/control-plane/logs/gateway-seed.log`
- `var/dev/control-plane/logs/web-ui.log` if web output is logged separately

Environment variables set for the control-plane process:

- `DIRT_CLOUD_DATABASE_URL`
- `DIRT_CLOUD_ADMIN_USERNAME`
- `DIRT_CLOUD_ADMIN_PASSWORD_HASH`
- `DIRT_CLOUD_SESSION_SECRET`
- `DIRT_CLOUD_SESSION_COOKIE_SECURE=false`
- `DIRT_CLOUD_ALLOWED_ORIGINS`
- `DIRT_CLOUD_SITE_ID=homebox`
- `DIRT_CLOUD_GATEWAY_COMMAND_CLAIM_ENABLED=false`
- `DIRT_CLOUD_COMMAND_CREATION_ENABLED` may remain true; commands can be created but not claimed unless a user explicitly starts a continuous local gateway.

Environment variables set for one-shot gateway seeding:

- `DIRT_CLOUD_API_BASE_URL=http://127.0.0.1:<api-port>`
- `DIRT_CLOUD_SITE_ID=homebox`
- `DIRT_CLOUD_GATEWAY_ID=gateway-main`
- `DIRT_CLOUD_GATEWAY_TOKEN`
- `DIRT_CLOUD_ASSET_SYNC_ENABLED=false`

Environment variables set for web UI:

- `VITE_DIRT_API_BASE_URL=http://127.0.0.1:<api-port>`
- `WEBUI_DEV_PORT=<computed-web-port>`

External tools required:

- `make`
- `uv`
- `pnpm`
- `atlas`
- local PostgreSQL reachable through the repo's `DIRT_PG_*` settings


## Revision Notes

- 2026-05-25: Initial plan created after reviewing the local control-plane code path and deciding to use root Make targets backed by `scripts/dev-env`.
