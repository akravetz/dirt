# Local Dev Environment Harness

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a human or agent can run one command, `make dev-up`, and get a local frontend connected to the real hosted control-plane API with local-only credentials and a local database restored from a compressed Railway control-plane dump. This replaces the need to hand-maintain MSW fixtures for the dashboard and live pages while keeping production safe.

The observable result is a browser at the Vite URL that can log in, render dashboard sites/tents/metrics/schedules/devices through the control-plane API, and iterate on frontend code without touching the deployed Railway services. The user should not need to know the Railway dump/restore command, the control-plane env vars, the local credential sanitization step, or how to point Vite at the API.

The public interface should be the root `Makefile`. The implementation script should be named `scripts/dev-env`, not `scripts/dev-up`, because it manages the whole local environment lifecycle: start, stop, reset, and status.

The primary local data path should be a repeatable refresh from the deployed Railway Postgres database into a local dev database. The refresh command must be read-only against Railway and destructive only against the computed local dev database. Active commands must be cleared after restore, production gateway credentials must be replaced with local dev credentials, and cloud audit rows should be kept for realistic operational history. Asset behavior is intentionally deferred and should be decided separately.


## Progress

- [x] (2026-05-25) Reviewed `.agents/PLANS.md`, `docs/rules/simple-clean-architecture.md`, `docs/commands.md`, `docs/database.md`, `docs/hosted-control-plane.md`, control-plane startup/config, cloud migrations, gateway one-shot sync, and web-ui API base selection.
- [x] (2026-05-25) Decided on root `Makefile` as the canonical public command catalog and `scripts/dev-env` as the direct implementation harness.
- [x] (2026-05-25) Revised the data strategy from one-shot gateway seed to Railway compressed dump restore with local post-restore sanitization.
- [x] (2026-05-25) Simplified the public fix command to only `make fix`; the lower-level formatter script remains an implementation detail.
- [x] (2026-05-25) Decided `scripts/dev-env` should be implemented in Python for clearer process supervision, safer database handling, and testable helpers.
- [x] (2026-05-25) Added a minimal root `Makefile` with `help` and `fix` so active agent guidance can point at `make fix` immediately.
- [ ] Implement root `Makefile` dev lifecycle targets.
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

- Observation: A compressed `pg_dump` from Railway is a simpler and more cohesive frontend dev seed than re-synthesizing cloud state through the gateway. It preserves realistic cross-table state, metric history, audit history, and edge cases from the deployed control-plane API database.
  Evidence: The browser API reads only the cloud tables in `apps/control-plane/src/dirt_control/models/cloud.py`; a local restore of that schema provides the same backend data surface the hosted UI uses.

- Observation: Asset upload is the least clean local path because the no-S3 fallback returns signed URLs under `DIRT_CLOUD_ASSET_PUBLIC_BASE_URL`, but it does not serve local bytes.
  Evidence: `apps/control-plane/src/dirt_control/api/gateway.py` signs upload URLs with `UrlSigner` when no object store is configured; `apps/control-plane/src/dirt_control/api/browser.py` returns signed asset URLs the same way.


## Decision Log

- Decision: Use a root `Makefile` as the public command surface.
  Rationale: `make` is broadly available and is already a familiar entry point for humans and agents. A Makefile is well suited to `.PHONY` command targets such as `dev-up` and `fix`, but not to complex process orchestration.
  Date/Author: 2026-05-25 / Codex.

- Decision: Put lifecycle logic in `scripts/dev-env`, not in Make recipes.
  Rationale: The harness must generate local secrets, create/migrate/drop a database on explicit reset, bootstrap a gateway credential, start and stop child processes, trap signals, write logs and state files, and report status. That belongs in a real script with explicit control flow.
  Date/Author: 2026-05-25 / Codex.

- Decision: Name the implementation script `scripts/dev-env` rather than `scripts/dev-up`.
  Rationale: The script owns environment lifecycle commands, not only startup. `dev-env --down`, `dev-env --reset`, and `dev-env --status` should live with the same implementation.
  Date/Author: 2026-05-25 / user request and Codex.

- Decision: Expose only `make fix` for formatting and safe lint-fix work.
  Rationale: Two public names for the same command create unnecessary decision points for agents. The Makefile should be the single public command catalog; lower-level scripts can remain implementation details.
  Date/Author: 2026-05-25 / user and Codex.

- Decision: Implement `scripts/dev-env` in Python.
  Rationale: The harness needs process supervision, signal handling, JSON state files, database name safety checks, subprocess command construction, and testable helper functions. Python is clearer and easier to lint/test for this than a large shell script.
  Date/Author: 2026-05-25 / user and Codex.

- Decision: Use a compressed Railway Postgres dump as the primary local dev database seed, with an explicit `make dev-refresh-db` command.
  Rationale: Restoring the deployed control-plane database is simpler than reconstructing cloud state through the local gateway. It gives the frontend realistic catalog, metric, schedule, command, asset metadata, and audit data without running any gateway process or maintaining mock fixtures.
  Date/Author: 2026-05-25 / Codex.

- Decision: After every local restore, clear queued/running cloud commands.
  Rationale: Active command rows are operational state, not useful frontend fixture data. Clearing non-terminal commands prevents stale production command state from appearing as actionable local work and avoids confusing command backlog/status behavior.
  Date/Author: 2026-05-25 / user and Codex.

- Decision: Keep `cloud_audit_event` rows in the local dev database.
  Rationale: Audit rows provide useful realistic operational history and do not trigger side effects by themselves. They should not be cleared as part of normal dev restore.
  Date/Author: 2026-05-25 / user and Codex.

- Decision: Replace production `gateway_credential` rows with local dev credentials after restore.
  Rationale: Production gateway credentials are secrets and should not be usable in local dev. The local control plane should contain only generated local credentials stored under ignored `var/dev/control-plane/`.
  Date/Author: 2026-05-25 / user and Codex.

- Decision: Defer local asset serving behavior.
  Rationale: The database restore preserves asset metadata, but whether local dev should load images through production S3, local files, placeholder assets, or a proxy is a separate product/security decision. The harness should not solve assets in the first implementation beyond avoiding secret leakage.
  Date/Author: 2026-05-25 / Codex.

- Decision: Use `pg_dump -Fc` and `pg_restore` for refresh/reset rather than Atlas migrations as the normal dev data path.
  Rationale: The source database is already migrated by production deploys. A custom-format dump restores schema and data together, preserves realistic state, and can be reused locally without contacting Railway. Atlas remains relevant for schema changes and production deploys, not for normal `make dev-up`.
  Date/Author: 2026-05-25 / Codex.


## Outcomes & Retrospective

No implementation has been completed yet. The expected outcome is a small root command catalog plus a lifecycle script that can refresh and run a local control-plane database from a Railway dump without exposing production secrets or requiring agents to know the underlying setup.


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

The cloud database schema is in `cloud/migrations/`, separate from the local hardware database schema in `migrations/`. The harness must use a separate development cloud database, for example `dirt_cloud_dev_<worktree_hash>`, and must not use the live local `dirt` database or production Railway database as a restore target.

The deployed Railway control-plane database is the canonical source for local dev data snapshots. The refresh flow should use a read-only source URL for Railway Postgres, produce a compressed custom-format dump under ignored `var/dev/control-plane/dumps/`, restore it into the local dev cloud database, then run local-only sanitization. The restore path should not use `.env.prod` implicitly. If the source database URL is needed, the script should accept it from an explicit env var such as `DIRT_DEV_SOURCE_CLOUD_DATABASE_URL`, or retrieve it through the same Railway CLI mechanism used by `scripts/deploy-control-plane` without printing it.

Local post-restore sanitization must:

- Replace all rows in `gateway_credential` with a generated dev credential.
- Clear active non-terminal rows from `cloud_command`, at minimum statuses `queued`, `claimed`, and `running`.
- Keep terminal `cloud_command` history unless later implementation discovers it causes confusing UI behavior.
- Keep `cloud_audit_event` rows.
- Avoid printing gateway tokens, session secrets, password hashes, or Railway database URLs.

The local gateway lives in `apps/gateway/`, but the default dev environment should not use it for seeding. It remains useful for explicit integration testing. Continuous gateway mode should not be started by default because it also runs cloud command polling and can execute real PTZ operations.

The existing script `scripts/worktree-port` returns a deterministic Vite port per worktree in the `5170-5199` range. `scripts/dev-env` should reuse that for the web UI and derive a separate deterministic API port from the same worktree identity, such as `8020-8049`.


## Plan of Work

Milestone 1: Add the public command catalog.

Create a root `Makefile` with `.PHONY` targets:

- `help`
- `dev-up`
- `dev-down`
- `dev-reset`
- `dev-refresh-db`
- `dev-status`
- `fix`

Each target should delegate to implementation scripts. The Makefile should not embed orchestration logic. `fix` should run the existing formatter/lint-fix workflow through its lower-level script. The dev targets should call `scripts/dev-env` with the relevant lifecycle flag.

Milestone 2: Implement `scripts/dev-env`.

Use a strict script with clear subcommands:

- default or `up`
- `--down` or `down`
- `--reset` or `reset`
- `--refresh-db` or `refresh-db`
- `--status` or `status`

Implement `scripts/dev-env` as Python. Keep the executable path extensionless so the public command remains `scripts/dev-env`, but put normal Python code behind it: dataclasses or typed helpers for paths/state, small functions for database commands, and subprocess wrappers that are easy to test. The script should:

1. Resolve repo root.
2. Compute deterministic web and API ports.
3. Create `var/dev/control-plane/`.
4. Generate or reuse local-only credentials in `var/dev/control-plane/env`.
5. Verify a dedicated cloud dev database exists and has been restored from a local dump.
6. Refuse to start if no dev database exists, and tell the user to run `make dev-refresh-db`, unless the implementation chooses to auto-refresh on first run.
7. Start uvicorn for `apps/control-plane`.
8. Wait for `http://127.0.0.1:<api-port>/healthz`.
9. Start Vite through `pnpm --dir web-ui dev` with `VITE_DIRT_API_BASE_URL` set.
10. Trap process exit and clean up child processes it started.

The script should write logs under `var/dev/control-plane/logs/`, dumps under `var/dev/control-plane/dumps/`, and a state file under `var/dev/control-plane/state.json` containing ports, PIDs, database name, dump path, and URLs. It must not print generated secrets by default. It may print the local username and where the password file lives. `var/` is already gitignored, but the script and docs should still describe this location as the only approved storage for local dumps and secrets.

Milestone 3: Implement `dev-refresh-db`, restore, and sanitization.

`make dev-refresh-db` should:

1. Stop local dev processes if they are using the dev cloud database.
2. Resolve the Railway source database URL without printing it.
3. Run `pg_dump -Fc` into `var/dev/control-plane/dumps/`.
4. Drop and recreate only the computed local dev database.
5. Restore the dump with `pg_restore`.
6. Run post-restore sanitization:
   - delete or replace all `gateway_credential` rows with one generated dev row;
   - delete active `cloud_command` rows where status is `queued`, `claimed`, or `running`;
   - keep `cloud_audit_event` unchanged.
7. Write the latest dump path and restore timestamp to the state file.

`make dev-reset` should restore the local dev database from the most recent local compressed dump without contacting Railway. If no local dump exists, it should tell the user to run `make dev-refresh-db`.

`make dev-status` should report whether the API and web ports are reachable, show the dev database name, show the latest dump timestamp/path, and point to logs. `make dev-down` should stop processes recorded in the state file if still running.

The script must refuse to drop databases whose names do not start with the expected prefix. This is a hard safety rule.

Milestone 4: Update documentation.

Update `docs/commands.md` so the canonical frontend iteration path is:

    make dev-up

Document lower-level commands only as debugging details. Update the commit instructions to prefer:

    make fix

The lower-level formatter script remains an implementation detail because hooks and humans may still call it directly when debugging, but docs should present the Make target as the public interface.

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

    make fix
    uv run pytest apps/control-plane/tests -q
    uv run pytest apps/gateway/tests -q
    pnpm --dir web-ui typecheck

Run the harness:

    make dev-up

If no local dump has been restored yet, refresh the dev DB first:

    make dev-refresh-db

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
- It restores the database from the latest local compressed dump.
- It starts the environment again.


## Validation and Acceptance

The change is accepted when:

- `make help` lists `dev-up`, `dev-down`, `dev-reset`, `dev-refresh-db`, `dev-status`, and `fix`.
- `make fix` runs the existing formatter/lint-fix workflow.
- `make dev-refresh-db` creates a compressed local dump from the Railway control-plane database without printing the source URL or secrets.
- `make dev-refresh-db` restores only into the computed local dev database and refuses any unsafe target database name.
- `make dev-refresh-db` replaces production gateway credentials with local dev credentials.
- `make dev-refresh-db` clears active `cloud_command` rows with statuses `queued`, `claimed`, and `running`.
- `make dev-refresh-db` keeps `cloud_audit_event` rows.
- `make dev-up` can be run from a clean shell with no `DIRT_CLOUD_DATABASE_URL` pointed at production and uses the local-only dev cloud database.
- `make dev-up` does not use `.env.prod`.
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

Normal `make dev-up` should be safe to repeat. It should reuse the existing dev cloud database and restart local child processes as needed. It should not contact Railway or mutate the dev database except for normal API runtime writes such as login audit rows.

`make dev-refresh-db` is intentionally destructive only for the computed dev cloud database. It must stop existing child processes first, verify the database name prefix, dump Railway read-only, drop the local dev database, recreate it, restore the compressed dump, sanitize local-only state, and then exit or optionally start the environment if invoked through `make dev-reset`.

`make dev-reset` is intentionally destructive only for the computed dev cloud database and does not contact Railway. It must restore from the most recent local dump, run the same post-restore sanitization, and then start the environment.

`make dev-down` should be safe if no processes are running. It should report stale PIDs and remove or update the state file without failing loudly.

If `pg_dump` fails, the script must leave the existing local dev database untouched and print the dump log path. If `pg_restore` fails, the script should not start the API/web stack and should print the restore log path. If post-restore sanitization fails, the script should stop and warn that production credentials may still be present in the local database; it should not start the API until sanitization succeeds.

If Vite exits, the foreground `make dev-up` process should shut down the API child it started before returning.


## Artifacts and Notes

Relevant existing files:

- `scripts/worktree-port` computes deterministic Vite ports.
- `web-ui/src/api-client/hosted.ts` reads `VITE_DIRT_API_BASE_URL`.
- `apps/control-plane/railway.json` documents the production uvicorn factory command.
- `apps/control-plane/src/dirt_control/app.py` creates the FastAPI app and installs CORS only when origins are configured.
- `apps/control-plane/src/dirt_control/settings.py` defines required cloud settings and local cookie behavior.
- `apps/control-plane/src/dirt_control/bootstrap_gateway.py` seeds gateway credentials and provides a useful implementation reference for replacing restored production gateway credentials with dev credentials.
- `apps/gateway/src/dirt_gateway/main.py` exposes one-shot sync for explicit integration testing, but it is no longer the default dev data path.
- `cloud/migrations/` holds the hosted control-plane schema migrations.
- `.gitignore` ignores `var/`; local dumps and generated secrets must live under `var/dev/control-plane/`.

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
- `make dev-refresh-db`
- `make dev-status`
- `make fix`

Implementation script interface:

- `scripts/dev-env`
- `scripts/dev-env up`
- `scripts/dev-env down` or `scripts/dev-env --down`
- `scripts/dev-env reset` or `scripts/dev-env --reset`
- `scripts/dev-env refresh-db` or `scripts/dev-env --refresh-db`
- `scripts/dev-env status` or `scripts/dev-env --status`

Generated local state:

- `var/dev/control-plane/env`
- `var/dev/control-plane/state.json`
- `var/dev/control-plane/dumps/*.dump`
- `var/dev/control-plane/logs/control-plane.log`
- `var/dev/control-plane/logs/dump.log`
- `var/dev/control-plane/logs/restore.log`
- `var/dev/control-plane/logs/sanitize.log`
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

Environment variables used only for dev DB refresh:

- `DIRT_DEV_SOURCE_CLOUD_DATABASE_URL`, optional explicit Railway source database URL. If unset, the script may resolve the source URL through Railway CLI/project variables without printing it.
- Local `DIRT_CLOUD_GATEWAY_ID` and `DIRT_CLOUD_GATEWAY_TOKEN` values generated under `var/dev/control-plane/env` for post-restore credential replacement.

Environment variables set for web UI:

- `VITE_DIRT_API_BASE_URL=http://127.0.0.1:<api-port>`
- `WEBUI_DEV_PORT=<computed-web-port>`

External tools required:

- `make`
- `uv`
- `pnpm`
- `atlas`
- `pg_dump`
- `pg_restore`
- local PostgreSQL reachable through the repo's `DIRT_PG_*` settings


## Revision Notes

- 2026-05-25: Initial plan created after reviewing the local control-plane code path and deciding to use root Make targets backed by `scripts/dev-env`.
- 2026-05-25: Revised plan to use compressed Railway `pg_dump` restore as the primary dev database path. Added `make dev-refresh-db`, local post-restore sanitization, gateway credential replacement, active command clearing, audit retention, and asset deferral.
