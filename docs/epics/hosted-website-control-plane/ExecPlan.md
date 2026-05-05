# Hosted Website Control Plane

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt has a hosted website that can be opened away from the local network to inspect grow state, recent history, device freshness, photos, and a narrow set of remote-safe control actions. The hosted site is a control plane: it records desired actions and displays synchronized state. It is not a new hardware authority.

The local box remains the only process that talks to cameras, fans, lights, humidifiers, ESP32 nodes, the local Postgres database, and local automation loops. A new outbound-only local gateway synchronizes selected state to a cloud database and polls for cloud command intent. When it sees an allowed command, it validates the command locally, executes through existing local services, and writes the final status back to cloud.

The first observable result should be deliberately small: a hosted dashboard can show `homebox/main` and `homebox/breeding`, current main-tent readings, freshness/offline state, recent photos, and sync age without any remote actuator control. The second observable result should be a low-risk command loop, starting with PTZ camera moves only. Environmental actuator controls, such as fan duty, lights, or humidifier changes, are out of the first command milestone unless the user explicitly expands scope after the gateway has proved safe.


## Progress

- [x] (2026-05-04T17:40:46Z) Read required process and repo docs: `docs/commands.md`, `.agents/PLANS.md`, `docs/README.md`, `docs/database.md`, `docs/observability.md`, `docs/adrs/002-tech-stack.md`, `docs/adrs/003-hardware-and-deployment.md`, and `docs/adrs/006-postgres-and-atlas.md`.
- [x] (2026-05-04T17:40:46Z) Reviewed the initial sketch at `docs/epics/hosted-website-control-plane/plan.json`.
- [x] (2026-05-04T17:40:46Z) Reviewed the completed multi-tent local controller plan and ERD at `docs/epics/multi-tent-controller/ExecPlan.md` and `docs/epics/multi-tent-controller/DataModelERD.md`.
- [x] (2026-05-04T17:40:46Z) Inspected current local API, auth, command, configuration, contract, and frontend structure under `apps/shared/`, `apps/web/`, `contracts/`, and `web-ui/`.
- [x] (2026-05-04T17:40:46Z) Created this Markdown ExecPlan as the canonical implementation plan for the hosted control-plane epic.
- [x] (2026-05-05T02:15:31Z) Completed Railway prework: installed Railway CLI 4.45.0, created Railway project `dirt-control-plane`, added `control-plane-api`, `web-ui`, `Postgres`, and `dirt-assets`, generated custom-domain requirements for `sirius-forge.com` and `api.sirius-forge.com`, wrote local secrets to ignored `.env.prod`, and added placeholders to `.env.example`.
- [x] (2026-05-05T02:50:25Z) Deployed temporary placeholder containers to `control-plane-api` and `web-ui` to complete Railway public-networking setup; both custom domains now serve valid certificates and 200 responses.
- [x] (2026-05-05T18:20:00Z) Milestone 1: decided and documented hosted platform, auth, database, object storage, DNS, deployment boundaries, and current-provider evidence.
- [x] (2026-05-05T03:36:59Z) Milestone 2: implemented the cloud control-plane schema, dedicated cloud Atlas migration path, thin hosted FastAPI API, and focused acceptance tests.
- [x] (2026-05-05T12:00:00Z) Milestone 3: implemented the local outbound gateway package, local Atlas-managed outbox/cursor durability tables, read-only DI sync orchestration, asset sign-upload/complete flow, dry-run mode, `cloud_gateway` observability, and focused acceptance tests.
- [x] (2026-05-05T04:19:48Z) Milestone 4: implemented the read-only hosted dashboard code path, hosted API base URL support, session bootstrap, site/tent selector, sync freshness/status rendering, private signed-asset display, read-only hosted live page, MSW cloud scenarios, and Railway web-ui build config. Deployment is blocked until the Milestone 6 deploy flow exists or the operator explicitly approves direct Railway deployment.
- [x] (2026-05-05T04:39:14Z) Milestone 5: implemented the PTZ-only cloud command loop, local command ledger integration, cloud result reporting, restart/idempotency guardrails, hosted `/live` command lifecycle UI, and focused backend/frontend tests.
- [x] (2026-05-05T05:35:00Z) Milestone 6 implementation is locally complete: gateway systemd unit/install wiring, supported Railway deploy script, cloud health/audit/monitoring, command rollback toggles, daily asset retention, operator docs, and focused tests are in place.
- [x] (2026-05-05T05:54:00Z) Production cloud Atlas migrations were applied through `scripts/deploy-control-plane`; the initial schema migration and Milestone 6 backlog-depth migration are now present in Railway Postgres.
- [x] (2026-05-05T06:16:00Z) Production Railway app deployment completed through `scripts/deploy-control-plane`: latest API deployment `e6aad95d-4518-4382-a2e2-a4612d26611b` and latest web-ui deployment `c6e7f321-d330-4cef-88d3-293587fe391c` are both `SUCCESS`; public API/UI smoke checks and auth/asset-route protection checks passed.
- [x] (2026-05-05T06:48:00Z) Final production hardening deploy completed after gateway bootstrap and S3 signed-URL fixes: API deployment `011d285b-4e3c-4eda-b5b5-6ee98aa51b92` and web-ui deployment `424832de-0f75-4c80-9d40-fa36e59a6a87` are both `SUCCESS`; local `dirt-gateway.service` is active; `/api/health` reports `status=live`, current gateway heartbeat, `gateway_backlog_depth=12`, zero command failures in 24 hours, and asset failures only from earlier failed upload attempts.


## Surprises & Discoveries

- Observation: The multi-tent prerequisite is now materially complete. The local database already has canonical `site`, `tent`, `zone`, `device`, `capability`, `growrun`, `schedule`, `snapshot`, and `command` tables, and local scoped read APIs exist for sites, tents, grow state, and tent devices.
  Evidence: `docs/epics/multi-tent-controller/ExecPlan.md`, `docs/epics/multi-tent-controller/DataModelERD.md`, `apps/web/src/dirt_web/api/scope.py`, and `apps/shared/src/dirt_shared/models/command.py`.

- Observation: The current local command service is intentionally local-only and rejects remote sources.
  Evidence: `apps/shared/src/dirt_shared/services/commands.py` defines `LOCAL_COMMAND_SOURCES = {"local_api", "local_loop", "test"}` and says the service records local command lifecycle only.

- Observation: Current browser auth is a local-network cookie session using `.env` credentials. It is not enough by itself for a public hosted site.
  Evidence: `docs/epics/auth/README.md` says auth is a convenience barrier for local network use, and `apps/web/src/dirt_web/auth.py` protects local `/api/*` routes with `dirt_session`.

- Observation: Vercel Python Functions are plausible for a thin API because Vercel currently lists Python 3.13 support and FastAPI support, but the Python runtime is beta and functions are still request/response units, not background workers.
  Evidence: Vercel Python runtime docs, last checked 2026-05-04: https://vercel.com/docs/functions/runtimes/python.

- Observation: Large media must not flow through Vercel Functions. Vercel's docs currently state a 4.5 MB function request/response body limit, and Vercel Blob server-upload docs direct larger uploads to direct/client upload flows.
  Evidence: Vercel Functions limits and Vercel Blob server upload docs, last checked 2026-05-04: https://vercel.com/docs/functions/limitations and https://vercel.com/docs/vercel-blob/server-upload.

- Observation: Vercel Cron is not the right mechanism for frequent local sync on Hobby plans. The local gateway should poll outbound from this box instead.
  Evidence: Vercel Cron docs currently list Hobby cron minimum interval as once per day and Pro/Enterprise as once per minute: https://vercel.com/docs/cron-jobs/usage-and-pricing.

- Observation: Railway custom-domain TLS did not fully work for an offline empty service. DNS and Railway verification could report valid while HTTPS still served the fallback `*.up.railway.app` certificate for `api.sirius-forge.com`. Deploying a tiny service that listens on `0.0.0.0:$PORT` fixed certificate presentation and routing.
  Evidence: Before placeholder deployment, `openssl s_client -servername api.sirius-forge.com` showed `CN=*.up.railway.app`; after deployment, it showed `CN=api.sirius-forge.com` and `curl https://api.sirius-forge.com/healthz` returned HTTP 200.

- Observation: Railway Buckets are a good fit for private grow media, but they are not a public-static-asset feature. Public buckets are not currently supported, and the documented access patterns are presigned URLs or backend proxying.
  Evidence: Railway Storage Buckets docs, last checked 2026-05-05: https://docs.railway.com/guides/storage-buckets.

- Observation: Railway bucket traffic has a cost distinction that affects the asset path. Bucket egress is documented as free, while uploads from Railway services to buckets count as service egress because buckets are on the public network.
  Evidence: Railway Storage Buckets Billing docs, last checked 2026-05-05: https://docs.railway.com/storage-buckets/billing.

- Observation: Atlas cloud migration generation is feasible in this worktree with the dedicated `cloud` env.
  Evidence: `atlas migrate diff cloud_control_plane_initial --env cloud` generated `cloud/migrations/20260505033411_cloud_control_plane_initial.sql` and `cloud/migrations/atlas.sum`.

- Observation: The cloud API tests use explicit Atlas migration apply against a temporary Postgres database and do not create tables from app startup or test app construction.
  Evidence: `apps/control-plane/tests/conftest.py` runs `atlas migrate apply --dir file://cloud/migrations --url ...`; `apps/control-plane/src/dirt_control/app.py` startup only calls `ping(engine)`.

- Observation: Replacement Worker M2b found one thin acceptance gap in the initial Milestone 2 API surface: command creation and single-command fetch existed, but `GET /api/commands` was missing.
  Evidence: `apps/control-plane/src/dirt_control/api/browser.py` now exposes `list_commands()`, and `apps/control-plane/tests/test_api.py` verifies duplicate command creation, list, and fetch all return the same command intent without local hardware imports.

- Observation: Verification found a second Milestone 2 command-boundary gap: browser command creation accepted arbitrary `command_type` values and user-selected expiration up to 300 seconds, which did not match the V1 PTZ-only and 60-second expiry constraint.
  Evidence: `apps/control-plane/src/dirt_control/api/browser.py` now restricts `CommandCreateRequest` to `ptz_preset`, `ptz_look`, or `ptz_zoom` targeting `device_id='obsbot-main'` and `capability_id='ptz_move'`, and always stores `expires_at = queued_at + 60 seconds`; `apps/control-plane/tests/test_api.py` rejects fan/lights/humidifier and wrong-target commands and asserts exact 60-second expiry.

- Observation: A test that checked `sys.modules` for hardware imports was brittle under the full pre-commit per-app suite because other app tests import `dirt_hwd` before control-plane tests run.
  Evidence: The Milestone 2 commit hook initially failed on `assert "dirt_hwd" not in sys.modules`; `apps/control-plane/tests/test_api.py` now scans `dirt_control` source imports with `ast` instead, proving the cloud API package does not import hardware modules without depending on global test order.

- Observation: The local zone model exposes `zone_type`, not `kind`, while the cloud gateway catalog API expects `kind`.
  Evidence: `apps/gateway/src/dirt_gateway/local.py` maps local `Zone.zone_type` into the cloud catalog `kind` field, and `apps/gateway/tests/test_sync.py` covers the real local catalog projection from the migrated test database.

- Observation: The local Atlas test fixture automatically picked up the new gateway durability migration because the tables live in `dirt_shared.models`.
  Evidence: `uv run pytest apps/gateway/tests apps/shared/tests -q` applied `migrations/20260505035619_cloud_gateway_durability.sql` into the shared test template and passed with `145 passed`.

- Observation: Replacement Worker M3b inherited an uncommitted Milestone 3 implementation and found it already aligned with the requested acceptance-test shape.
  Evidence: Re-running `uv run pytest apps/gateway/tests apps/shared/tests -q`, `uv run pytest apps/tests/invariants/ -q`, ruff checks, ruff format check, and `uv lock --check` passed without additional source edits.

- Observation: DB-backed pytest commands that use the shared `app_engine` fixture should not be launched concurrently in the same worktree.
  Evidence: Main-agent verification initially ran `uv run pytest apps/gateway/tests -q` and `uv run pytest apps/gateway/tests apps/shared/tests -q` in parallel; both sessions use the same worktree-derived template database name, so one session dropped the template while the other still needed it. Rerunning `uv run pytest apps/gateway/tests apps/shared/tests -q` sequentially passed with `145 passed`.

- Observation: Bare `from conftest import ...` imports are unsafe when pre-commit collects multiple app test roots in one pytest invocation.
  Evidence: After adding `apps/gateway` to the per-app pre-commit hook, collection failed because `apps/control-plane/tests/test_api.py` imported `FIXED_NOW` from the gateway test `conftest.py`. The control-plane test now defines its own constant, and `uv run pytest apps/control-plane/tests apps/gateway/tests -q` passed with `14 passed`.

- Observation: The cloud heartbeat accepted `backlog_depth`, but the browser `/api/sync/status` response did not expose any backlog/status field for the hosted dashboard.
  Evidence: Milestone 4 added a narrow `apps/control-plane/src/dirt_control/api/browser.py` route fix that reports `command_backlog_depth` from non-terminal cloud commands plus a derived `live` / `stale` / `offline` status without changing the cloud schema.

- Observation: There is no checked-in `scripts/deploy-control-plane` yet.
  Evidence: `rg --files scripts | rg deploy-control-plane` returned no deploy script during Milestone 4 work, so this worker did not replace the Railway placeholder deployments.

- Observation: Cloud command claim needed to return already-claimed commands for the same gateway, not only newly queued commands.
  Evidence: `apps/control-plane/src/dirt_control/api/gateway.py::claim_commands()` now marks expired queued/claimed rows terminal and returns non-expired commands already claimed by the authenticated gateway before claiming fresh queued rows. This lets a gateway restart or lost claim response recover without leaving a command stuck in `claimed`.

- Observation: The local PTZ look contract is stricter than the current local `CameraFeed` comment implies.
  Evidence: `contracts/webapp-v1.yaml` and `apps/web/tests/test_ptz_look_endpoint.py` constrain `x`/`y` to `[-0.5, 0.5]`; hosted command buttons submit `±0.25` deltas and the gateway rejects out-of-range cloud payloads before touching PTZ.

- Observation: Browser command creation also needed a site-scope guard, not only PTZ type/device/capability guards.
  Evidence: Main-agent Milestone 5 verification found that a browser could queue a command for a non-default `site_id` that the homebox gateway would never claim. `POST /api/commands` now rejects non-default sites before creating cloud command rows, and `uv run pytest apps/control-plane/tests -q` passed with `10 passed`.

- Observation: Atlas CLI lint is no longer available in the installed community CLI even though the local reference pack still describes it as community-available.
  Evidence: `atlas migrate lint --env cloud --latest 1` exited with `Abort: Starting with v0.38, 'atlas migrate lint' is available only to Atlas Pro users.` Migration apply coverage still runs through the cloud API pytest fixture.

- Observation: The first generated Milestone 6 cloud migration added `cloud_site.gateway_backlog_depth` as `NOT NULL` without a server default, which would fail against the existing Railway database rows.
  Evidence: The unsafe generated SQL was deleted before apply and regenerated after changing the SQLModel field to `Column(Integer, nullable=False, server_default="0")`; the committed migration now uses `ALTER TABLE "cloud_site" ADD COLUMN "gateway_backlog_depth" integer NOT NULL DEFAULT 0;`.

- Observation: The deploy and gateway service environment loading needed to honor the repo's split secret convention.
  Evidence: Main-agent Milestone 6 verification updated `scripts/deploy-control-plane` to load `.env` before `.env.prod`, so `RAILWAY_API_TOKEN` can come from `.env` while production cloud secrets come from `.env.prod`. `systemd/dirt-gateway.service` now also loads optional `.env.prod` after `.env`, so local gateway secrets are available when stored in the ignored production env file.

- Observation: Railway already exposed the cloud database URL as the standard `DATABASE_URL` service variable, not `DIRT_CLOUD_DATABASE_URL`.
  Evidence: The first production deploy attempt stopped before any migration or deploy because `DIRT_CLOUD_DATABASE_URL` was unset locally. A key-only Railway variable check showed `DATABASE_URL` on `control-plane-api`; `CloudSettings` now accepts either `DIRT_CLOUD_DATABASE_URL` or `DATABASE_URL`, and `scripts/deploy-control-plane` reads the deployed `DATABASE_URL` without printing it when the dedicated local variable is absent.

- Observation: The Railway app `DATABASE_URL` uses a private internal hostname that local Atlas cannot resolve.
  Evidence: Production deploy attempt 2 stopped before app deployment with `lookup postgres.railway.internal ... no such host`. A key-only variable check on the Railway Postgres service showed `DATABASE_PUBLIC_URL`; `scripts/deploy-control-plane` now uses that public URL for local Atlas migration when `DIRT_CLOUD_DATABASE_URL` is unset, while the deployed app can still use Railway's internal `DATABASE_URL`.

- Observation: Railway Nixpacks defaulted the control-plane API build to Python 3.12.7, which is below this workspace's declared Python requirement.
  Evidence: Production deploy attempt 3 applied cloud migrations successfully, uploaded deployment `7e289c7a-982f-43fa-a349-349ecc8961d7`, then the Railway build failed with `Package 'dirt-control-plane' requires a different Python: 3.12.7 not in '>=3.13'`. `apps/control-plane/.python-version` now pins the API service build to Python 3.13.

- Observation: Railway's Nixpacks Python flow installed `apps/control-plane` before copying `src/`, producing an effectively empty package wheel for the API service.
  Evidence: Production deploy attempt 4 built with Python 3.13 and installed dependencies, but runtime crashed with `ModuleNotFoundError: No module named 'dirt_control'`. Build logs showed `COPY pyproject.toml`, `pip install .`, then later `COPY . /app`; the Railway start command now sets `PYTHONPATH=/app/src` so the copied source tree is importable at runtime.

- Observation: `railway up` can return before Railway's configured service healthcheck has passed.
  Evidence: Production deploy attempt 4 uploaded deployment `8cb9aeb6-2582-4d8a-9c2c-88cc586580eb`; `scripts/deploy-control-plane` immediately curled the still-placeholder API and failed with HTTP 404 while Railway still showed the deployment as `INITIALIZING`, then `BUILDING`, then `DEPLOYING`. The deploy script now retries public smoke checks before failing.

- Observation: `pydantic-settings` JSON-decodes list-typed environment fields before running ordinary field validators.
  Evidence: Production deploy attempt 5 reached `dirt_control.app:create_app`, then crashed while parsing `DIRT_CLOUD_ALLOWED_ORIGINS=https://sirius-forge.com` because the list field expected JSON. `CloudSettings.allowed_origins` now uses `NoDecode` so comma-separated Railway env values reach the existing validator.

- Observation: The local ignored production env file had the hosted browser admin credentials, but the Railway `control-plane-api` service did not.
  Evidence: Key-only checks showed `DIRT_CLOUD_ADMIN_USERNAME` and `DIRT_CLOUD_ADMIN_PASSWORD_HASH` present in `.env.prod` but absent from the Railway API service. Production deploy attempt 6 reached settings validation and failed on those two missing fields. `scripts/deploy-control-plane` now syncs required API and web-ui service variables from the ignored env files through `railway variable set --stdin --skip-deploys` before deployment.

- Observation: The ignored env files carried a cloud admin password-hash key, but the value was blank.
  Evidence: Length-only checks showed `DIRT_CLOUD_ADMIN_PASSWORD_HASH` length `0` in `.env` and `.env.prod`, while the local `AUTH_PASSWORD` was present. `scripts/deploy-control-plane` now derives the cloud `sha256:` password hash from `AUTH_PASSWORD` only when the explicit cloud hash is blank, without printing the plaintext or hash.

- Observation: Railway Nixpacks defaulted the hosted web-ui build to Node 18, which is below Vite 8's runtime requirement.
  Evidence: The first real web-ui deployment failed during `pnpm build` with Vite's warning that Node 20.19+ or 22.12+ is required, followed by `ReferenceError: CustomEvent is not defined` on Node 18.20.5. `web-ui/package.json` and `web-ui/.node-version` now pin the service to Node 22.12+.

- Observation: `pnpm preview -- --host 0.0.0.0 --port $PORT` did not expose the Vite preview server on Railway.
  Evidence: The Node-22 web-ui deployment built successfully, then failed healthcheck while runtime logs showed Vite listening only on `http://localhost:4173/` and advising `use --host to expose`. `web-ui/railway.json` now starts with `pnpm exec vite preview --host 0.0.0.0 --port $PORT`.

- Observation: Even with direct `vite preview --host 0.0.0.0 --port $PORT`, Railway never marked the web-ui replica healthy.
  Evidence: Deployment `7bb3ba45-3e8d-49e1-9976-485e9e44e0b6` showed Vite listening on local and network addresses, but Railway's `/` healthcheck exhausted its 5-minute retry window with service unavailable. The hosted UI now serves the built SPA through Caddy with a checked-in `web-ui/Caddyfile`.

- Observation: Production cloud auth had no initial `gateway_credential` row, so the running local gateway could not authenticate.
  Evidence: After starting `dirt-gateway`, structured logs showed heartbeat/catalog/metric deliveries and command claims all failing with `CloudDeliveryError`, while the cloud health endpoint still had `gateway_last_seen_at=null`. The local token hash matched `DIRT_CLOUD_GATEWAY_TOKEN_SHA256`, so the missing piece was seed data. `scripts/deploy-control-plane` now upserts the V1 gateway credential row after cloud Atlas migrations and before service deploy.

- Observation: The initial asset signing path produced app-signed placeholder URLs, not private bucket presigned PUT/GET URLs, when S3 credentials were configured.
  Evidence: After gateway auth was fixed, heartbeat/catalog/metric events delivered and cloud health turned `live`, but asset upload rows failed with `Attempted to send an sync request with an AsyncClient instance.` because the gateway tried to PUT bytes to the app-signed asset URL instead of Railway's S3-compatible bucket. Cloud asset sign-upload and browser signed-url routes now use S3 presigned URLs when bucket credentials are configured, with the previous app-signed URL only as the no-bucket test fallback.

- Observation: The local gateway asset uploader passed a synchronous file object to `httpx.AsyncClient`.
  Evidence: Once production sign-upload returned a Railway bucket presigned PUT URL, pending asset rows still failed with `Attempted to send an sync request with an AsyncClient instance.` The gateway HTTP client now reads the snapshot file into bytes before the async PUT, and a focused MockTransport test covers that path.

- Observation: The production API briefly exhausted its SQLAlchemy async connection pool while the gateway was catching up and command-claim polling continued.
  Evidence: Railway logs showed `QueuePool limit of size 5 overflow 10 reached` from `/api/gateway/v1/commands/claim`. The service recovered without code changes; repeated `/api/health` probes then returned 200 in roughly 150-170 ms with `status=live`. This should be tracked as an operational follow-up if pool exhaustion reappears under normal traffic.


## Decision Log

- Decision: Keep the hosted system as a control plane, not a data-plane or hardware execution service.
  Rationale: The local `dirt-hwd` service owns safety-critical loops and local device credentials. Public cloud code should record intent and display state, never directly reach local hardware.
  Date/Author: 2026-05-04 / Codex

- Decision: Build the hosted work around a separate cloud API and separate cloud schema, not by exposing the current `dirt-web` process publicly.
  Rationale: `dirt-web` is composed around the local database, local static bundle, local cookie auth, local PTZ service, MCP mount, and local hardware-adjacent endpoints. A separate cloud API can keep public auth, sync credentials, retention, asset signing, and command queue semantics small and testable.
  Date/Author: 2026-05-04 / Codex

- Decision: Use an outbound-only local gateway as the normal sync path.
  Rationale: The local box should not require inbound router ports or public tunnels for normal hosted website operation. This also makes cloud outage behavior explicit: local automation continues and sync catches up later.
  Date/Author: 2026-05-04 / Codex

- Decision: Deliver read-only hosted visibility before remote control.
  Rationale: Read-only sync proves cloud schema, identity mapping, auth, stale-state UI, asset flow, and deployment without risking plant safety. Remote controls can then be added against known sync semantics.
  Date/Author: 2026-05-04 / Codex

- Decision: Start remote command execution with PTZ camera moves only.
  Rationale: PTZ movement is observable, reversible, and does not affect environmental safety. Fan, lights, and humidifier controls require stricter policy, expiration, and manual confirmation semantics and should not be the first command path.
  Date/Author: 2026-05-04 / Codex

- Decision: Use polling and idempotent upserts for V1 rather than WebSockets, MQTT, or a queue broker.
  Rationale: Dirt has one site and low data volume. HTTP polling from the gateway plus event-shaped records is simpler to debug and works through ordinary outbound connectivity. Realtime transports can be added later if measured latency requires them.
  Date/Author: 2026-05-04 / Codex

- Decision: Use Railway as the single hosted provider for V1.
  Rationale: Railway can host a long-running FastAPI service, the React/Vite frontend, managed Postgres, S3-compatible object storage buckets, service environment variables, generated/custom domains, logs, and CLI-managed infrastructure in one project. This fits the preferred long-running backend shape better than forcing the cloud API into Vercel Functions. Current docs checked for this decision: FastAPI deploy guide https://docs.railway.com/guides/fastapi, static hosting guide https://docs.railway.com/guides/static-hosting, Postgres docs https://docs.railway.com/databases/postgresql/, storage buckets guide https://docs.railway.com/guides/storage-buckets, custom domain CLI docs https://docs.railway.com/cli/domain, and public networking docs https://docs.railway.com/deploy/exposing-your-app.
  Date/Author: 2026-05-05 / Codex

- Decision: Use `sirius-forge.com` for the hosted UI and `api.sirius-forge.com` for the cloud API.
  Rationale: The user owns `sirius-forge.com` in Cloudflare and asked for the UI on the apex domain with the API on the `api` subdomain. Railway custom-domain docs say the required CNAME and TXT records route traffic and verify ownership, and Cloudflare docs confirm CNAME flattening supports a CNAME-equivalent apex record.
  Date/Author: 2026-05-05 / Codex

- Decision: Use single-user FastAPI session auth for the hosted browser UI in V1.
  Rationale: Railway does not provide native app-auth for this use case, and adding Cloudflare Access would make auth depend on another provider. A hardened single-user session model keeps the public API self-contained while matching Dirt's current single-operator reality. Starlette's session middleware supports signed cookie sessions with HttpOnly, SameSite, expiry, and Secure-cookie options, while FastAPI documents response cookie handling and password-hash based authentication patterns.
  Date/Author: 2026-05-05 / Codex

- Decision: Keep `api.sirius-forge.com` DNS-only in Cloudflare and allow the apex UI domain to remain proxied.
  Rationale: DNS-only keeps Railway domain status clean and avoids Cloudflare challenge, cache, WAF, or request-limit surprises for local gateway machine-to-machine traffic. The UI benefits more from Cloudflare proxying and is less sensitive to API-client semantics. Cloudflare documents that proxied CNAME answers resolve to Cloudflare anycast IPs, while DNS-only CNAME records return the underlying target or flattened target.
  Date/Author: 2026-05-05 / Codex

- Decision: Store cloud assets privately and require signed URL access.
  Rationale: Grow photos and future video clips are private operational data. Public buckets or unauthenticated asset URLs are not acceptable for V1, and Railway Buckets are private S3-compatible buckets whose documented public-access pattern is presigned URLs or backend proxying.
  Date/Author: 2026-05-05 / Codex

- Decision: Retain synced cloud assets for 30 days in V1.
  Rationale: The hosted UI needs recent visual history without creating unbounded storage growth. Thirty days matches the longest metric rollup window and is simple to explain operationally. Railway bucket billing is storage-size based and has no documented minimum storage retention, so V1 can enforce retention in the application or a scheduled maintenance task.
  Date/Author: 2026-05-05 / Codex

- Decision: Use explicit Atlas CLI migrations for the cloud database, not app-start DDL.
  Rationale: This matches Dirt's current schema-management architecture. Production schema changes should be generated, reviewed, and applied intentionally before deploying app code that depends on them. Atlas versioned migration docs describe `atlas migrate diff` for generating migration files and `atlas migrate apply` for applying pending migrations during deploy.
  Date/Author: 2026-05-05 / Codex

- Decision: Implement the local gateway as a separate Python service with local Postgres durability tables.
  Rationale: The gateway needs durable retry/outbox semantics, sync cursors, and restart safety, but cloud sync must not share a process lifecycle with hardware automation. Local Postgres gives transactional, inspectable durability without coupling to `dirt-hwd`.
  Date/Author: 2026-05-05 / Codex

- Decision: Sync latest metrics plus 30 days of rollups, not raw sensor rows, to cloud in V1.
  Rationale: The hosted UI needs current state and trend visibility, not a full operational DB mirror. Rollups keep cloud storage/query cost low while supporting useful ranges: recent high resolution, 24-hour, 7-day, and 30-day trends.
  Date/Author: 2026-05-05 / Codex

- Decision: Design gateway and cloud API tests around dependency injection, not monkey patching production modules.
  Rationale: Monkey patching production modules hides poor seams and violates existing repository invariant expectations. Gateway code should accept injected clients, clocks, sleepers/backoff policies, and service bundles so tests use fakes and test databases cleanly.
  Date/Author: 2026-05-05 / Codex

- Decision: Keep Milestone 3 dry-run mode side-effect free: it collects projections and logs counts but does not enqueue outbox rows or call the cloud client.
  Rationale: Dry-run is an operator validation path. Leaving durable pending rows behind during dry runs would make a later normal start deliver stale test projections.
  Date/Author: 2026-05-05 / Codex Worker M3

- Decision: Use stable idempotency keys derived from projection content hashes for catalog, latest metrics, rollups, and asset metadata, while heartbeat keys include the gateway/site/timestamp.
  Rationale: Content-derived keys prevent duplicate cloud writes when a retry or restart replays the same projection. Heartbeats are intentionally time-sampled status updates.
  Date/Author: 2026-05-05 / Codex Worker M3

- Decision: Record accepted cloud PTZ commands in the existing local `command` ledger with `source='cloud_gateway'` before executing PTZ, and keep rejected/expired cloud commands out of the local ledger.
  Rationale: The local ledger should prove every accepted hardware action and prevent terminal cloud commands from being re-executed after restart. Rejected or expired cloud intent did not become a local hardware action, so it is reported to cloud without creating a misleading local command row.
  Date/Author: 2026-05-05 / Codex Worker M5

- Decision: Make hosted command rollback configuration-only with separate browser creation and gateway claim toggles.
  Rationale: Operators need to stop new hosted commands quickly without stopping read-only sync, heartbeat, asset retention, or local hardware automation. `DIRT_CLOUD_COMMAND_CREATION_ENABLED=false` blocks browser command creation; `DIRT_CLOUD_GATEWAY_COMMAND_CLAIM_ENABLED=false` makes gateway claim return no commands.
  Date/Author: 2026-05-05 / Codex Worker M6

- Decision: Run cloud asset retention from the existing outbound gateway path as a daily idempotent maintenance event.
  Rationale: Railway V1 does not add a separate scheduler in this milestone. The gateway already has durable outbox/retry semantics and gateway auth, so a daily `asset_retention` event can prune cloud metadata and private bucket objects while leaving local hardware loops untouched.
  Date/Author: 2026-05-05 / Codex Worker M6


## Outcomes & Retrospective

Milestone 1 is complete. The hosted V1 architecture is Railway-only for production: `control-plane-api` is the long-running FastAPI cloud API, `web-ui` is the hosted React/Vite frontend, Railway `Postgres` stores cloud state, and the Railway `dirt-assets` bucket stores private photos and future clips behind signed URLs. Browser auth is single-user FastAPI session auth; gateway auth is a generated bearer token stored locally with only its SHA-256 digest configured in the cloud API service. Production domains are `https://sirius-forge.com` for the UI and `https://api.sirius-forge.com` for the API, with preview/staging deferred until the production-shaped skeleton deploys cleanly.

Railway infrastructure prework is complete, and both app services are running temporary placeholder deployments so public networking and TLS can stay warm until real code replaces them. The Railway project is `dirt-control-plane` (`4720b3f9-7e3b-461e-b44d-fbb9e349ed11`) in the `production` environment (`12ffb3c2-807b-4246-a7d0-f00466be68fe`). Services are `control-plane-api` (`15035b13-0995-4f81-b548-954b3e6aed29`), `web-ui` (`c0297625-b063-4897-ac59-98e76f5f2413`), `Postgres` (`fc7e0827-e834-48a1-901f-faf5b0595602`), and bucket `dirt-assets` (`40462f7f-4691-4b45-9b34-e961e28612b4`, region `iad`). Custom domains are verified and serving valid certificates.

Milestone 2 is complete locally. The new workspace member `apps/control-plane/` defines import package `dirt_control`, cloud settings, async DB/session setup, SQLModel tables, FastAPI composition, browser session auth, gateway bearer-token auth, browser read routes, browser command-intent routes, gateway sync routes, and tests. Startup performs a database ping only; cloud schema changes are managed by the dedicated Atlas env `cloud` and migration directory `cloud/migrations/`. Command creation records queued intent in `cloud_command` and does not import or call local hardware modules. Asset upload is a direct signed-upload handshake plus metadata completion path; browser signed-url retrieval is session-authenticated.

Milestone 3 is complete locally. The new workspace member `apps/gateway/` defines import package `dirt_gateway`, a `python -m dirt_gateway.main` entry point, a SQL-backed outbox repository, an injected sync orchestrator, an HTTP cloud client, and a local projection bundle that reads catalog, latest metrics, 5-minute / 1-hour / 4-hour rollups, and latest snapshot metadata without importing `dirt_hwd`. Local durability tables `cloud_sync_cursor` and `cloud_outbox` are SQLModel classes in `dirt_shared.models` and are managed by local Atlas migration `migrations/20260505035619_cloud_gateway_durability.sql`; gateway startup only pings the database and performs no DDL. Tests prove catalog sync for `homebox/main` and `homebox/breeding`, idempotent latest/rollup delivery, retry after cloud outage, dry-run behavior, private asset sign-upload/complete sequencing, isolated `cloud_gateway` logs, and the no-hardware-import boundary.

Milestone 4 is code-complete locally. The React app now uses `VITE_DIRT_API_BASE_URL` to switch from same-origin local `dirt-web` mode to hosted cloud API mode. Hosted mode validates the cloud FastAPI session with `/api/auth/me`, renders the `homebox` site selector and `main` / `breeding` tent selector, shows gateway last-seen, cloud status, command backlog, per-metric source times, metric stale state, device last-seen values, and latest private assets using signed URLs returned by authenticated API routes. The hosted live page is deliberately read-only until Milestone 5, so local PTZ controls remain available only in same-origin local mode. MSW v2 fixtures cover `live`, `stale`, `offline`, `empty`, and `asset-unavailable` cloud scenarios via `?cloud_fixture=...`. Railway web-ui config is checked in at `web-ui/railway.json` and only builds the Vite app with `VITE_DIRT_API_BASE_URL`; it does not embed local hardware credentials or gateway tokens. The actual Railway deployment was not run because the supported Milestone 6 deploy script does not exist yet and direct provider deployment is an unsafe visible action without operator approval.

Milestone 5 is code-complete locally. Browser command creation remains PTZ-only and 60-second-expiring in the cloud API, while gateway claim now expires stale queued/claimed commands and can re-return non-terminal commands already claimed by the same gateway. The local gateway has a dedicated `GatewayCommandService` that claims cloud commands, validates scope/type/payload, records accepted PTZ commands in the local `command` ledger through `CommandService(source='cloud_gateway')`, executes them through the injected `PTZService` abstraction, reports `running` directly, and persists terminal command results through the existing local outbox before reporting them to cloud. If a restart sees an already-terminal local ledger row, the gateway reports that terminal result again and does not move the camera again; if it sees a non-terminal old ledger row, it fails the local row and reports failure rather than replaying a potentially non-idempotent PTZ delta. The hosted `/live` route now shows PTZ preset/look/zoom command controls only in hosted mode when cloud sync reports a live gateway, and it renders recent command lifecycle states from `/api/commands`. Local same-origin PTZ controls still use `/api/ptz/*` unchanged. No fan, lights, or humidifier remote control was added.

Milestone 6 is complete in production through the supported deploy flow. The repository now includes `systemd/dirt-gateway.service`, `scripts/install-systemd` wiring, `scripts/deploy-control-plane`, `apps/control-plane/railway.json`, `docs/hosted-control-plane.md`, and command docs for supported Railway deployment and rollback. The cloud API exposes `/api/health` with gateway heartbeat age, local gateway backlog, command backlog/failure counts, asset failure counts, retention window, and command enablement. Cloud audit rows cover auth login success/failure, command creation, command claim, command result, asset upload completion/failure, asset retention, and gateway credential rotation. Cloud assets have a 30-day retention path: the gateway enqueues one daily `asset_retention` event, and the cloud API prunes expired `cloud_asset` rows plus S3 objects when bucket credentials are configured. The production API and UI now run real code on Railway, not placeholders. Final deployment state on 2026-05-05: API deployment `011d285b-4e3c-4eda-b5b5-6ee98aa51b92` is `SUCCESS`; web-ui deployment `424832de-0f75-4c80-9d40-fa36e59a6a87` is `SUCCESS`; `https://api.sirius-forge.com/api/health` reports `ok=true`, `status=live`, current gateway heartbeat, `gateway_backlog_depth=12`, zero command failures in 24 hours, and asset failures only from earlier failed upload attempts; `https://sirius-forge.com/` serves the built SPA instead of placeholder HTML; unauthenticated browser data and asset signed-URL routes return 401; authenticated login plus `/api/auth/me`, `/api/sites`, and `/api/tents/main/assets/latest` return 200. The signed asset URLs are Railway S3 presigned URLs on `t3.storageapi.dev`, so grow assets remain private and expire through the signed URL flow.


## Context and Orientation

Dirt is currently a local-first system. `dirt-hwd` runs hardware ingest and background automation on port 8000. `dirt-web` runs the local API, SPA static serving, cookie auth, and MCP mount on port 8001. The React/Vite frontend lives in `web-ui/` and consumes the OpenAPI contract in `contracts/webapp-v1.yaml` through generated TypeScript types in `web-ui/src/api-client/generated/schema.ts`.

The completed multi-tent phase created the local identity model that this hosted plan depends on. `site.site_id='homebox'` is the physical installation. `tent.tent_id='main'` is the current production tent. `tent.tent_id='breeding'` exists as the future second tent. The canonical telemetry path is `site -> tent -> zone/device -> capability -> sensorreading`. The current physical box is still the only hardware controller.

Important current local files:

- `apps/shared/src/dirt_shared/models/` contains SQLModel local database models.
- `apps/shared/src/dirt_shared/services/scope.py` resolves default `homebox/main` scope.
- `apps/shared/src/dirt_shared/services/scope_catalog.py` lists local sites, tents, and devices.
- `apps/shared/src/dirt_shared/services/readings.py` reads latest and historical sensor data.
- `apps/shared/src/dirt_shared/services/snapshots.py` reads snapshot metadata.
- `apps/shared/src/dirt_shared/services/commands.py` records local command intent and lifecycle.
- `apps/shared/src/dirt_shared/services/ptz.py` executes local camera moves and records local PTZ commands.
- `apps/web/src/dirt_web/api/*.py` exposes the local browser API.
- `apps/web/src/dirt_web/auth.py` contains local cookie-session auth.
- `web-ui/src/api-client/client.ts` creates the OpenAPI fetch client; it currently defaults to same-origin.
- `web-ui/src/routes/index.tsx` and `web-ui/src/routes/live.tsx` are the main dashboard and camera surfaces.
- `systemd/` contains user-level service units for local long-running processes.

Terms used in this plan:

`cloud API` means the public hosted API used by the hosted browser and by the local gateway. It records and serves cloud state. It does not touch local hardware.

`local gateway` means a new outbound-only process running on this box. It reads local state, pushes cloud-visible state and assets, polls cloud commands, validates them, executes allowed commands locally, and reports final status.

`cloud command` means durable command intent stored in the cloud database. A cloud command is not executed when created. It is executed only if the local gateway later claims it, validates it, and calls local services.

`asset` means photo or video metadata plus an object storage key. Large bytes should be uploaded directly to object storage; API routes should return metadata and signed or public URLs.

`freshness` means whether cloud-visible state is recent enough to treat as live. Use `source_updated_at` for the local event time, `received_at` for cloud ingest time, `stale_after_s` for the expected freshness window, and `gateway_last_seen_at` for the whole-site sync heartbeat.


## Plan of Work

Milestone 1: Platform, Auth, And Deployment Decisions.

Completed on 2026-05-05. Use these decisions as the baseline unless a later decision explicitly changes them:

- cloud API V1 runs as long-running FastAPI on Railway service `control-plane-api`;
- hosted UI runs on Railway service `web-ui`;
- cloud state lives in Railway `Postgres`;
- snapshots and future video clips live in Railway S3-compatible bucket `dirt-assets`;
- browser auth uses single-user FastAPI session auth with secure httponly cookies, `DIRT_CLOUD_ADMIN_USERNAME`, a password hash, and `DIRT_CLOUD_SESSION_SECRET`;
- non-browser local gateway auth uses `DIRT_CLOUD_GATEWAY_TOKEN` locally and `DIRT_CLOUD_GATEWAY_TOKEN_SHA256` in the cloud API service environment;
- production domains are `https://sirius-forge.com` and `https://api.sirius-forge.com`;
- preview/staging environments are deferred until the production-shaped skeleton deploys cleanly;
- Cloudflare DNS posture is apex UI proxied, API DNS-only;
- deploy the real services by replacing the temporary placeholder deployments in the existing Railway project, not by creating new provider resources;
- do not run cloud database DDL at app startup; use a dedicated Atlas cloud migration path in Milestone 2.

The Railway CLI is installed locally as `railway 4.45.0`. Source `.env` for `RAILWAY_API_TOKEN`, not `RAILWAY_TOKEN`, when running account-level infrastructure commands. Source ignored `.env.prod` for generated production resource IDs and secrets. Do not print either token or generated secrets in terminal output.

Milestone 2: Cloud Control-Plane Schema And API.

Add a new Python workspace package at `apps/control-plane/` with import package `dirt_control`. Do not reuse `dirt_web.app.create_app()` for the public API. The new package owns public auth dependencies, gateway auth dependencies, cloud settings, cloud SQLModel metadata, and the cloud FastAPI app.

Add a separate cloud migration path. Do not mix cloud tables into the local `migrations/` directory. Cloud migrations must use a dedicated Atlas env and migration directory, and must be applied explicitly through the CLI before deploying app code that depends on the new schema. The cloud API startup path may check connectivity and expected schema version, but it must not run DDL.

A clean shape is:

- `apps/control-plane/src/dirt_control/models/` for cloud SQLModel classes;
- `apps/control-plane/src/dirt_control/db.py` for cloud engine/session setup;
- `apps/control-plane/src/dirt_control/app.py` for the FastAPI composition root;
- `apps/control-plane/src/dirt_control/api/browser.py` for browser-facing read and command routes;
- `apps/control-plane/src/dirt_control/api/gateway.py` for local gateway ingest, claim, heartbeat, and result routes;
- `apps/control-plane/tests/` for API and service tests;
- an Atlas environment and migration directory dedicated to cloud schema.

Cloud tables should be small and purpose-built, not a raw copy of local Postgres:

- `cloud_site`: stable `site_id`, display fields, timezone, `gateway_last_seen_at`, `last_catalog_sync_at`, `created_at`, `updated_at`.
- `cloud_tent`, `cloud_zone`, `cloud_device`, `cloud_capability`: cloud-readable catalog mirror keyed by stable string IDs, with active/enabled flags and sync timestamps.
- `cloud_latest_metric`: one row per synced capability metric, with `value`, `unit`, `source_updated_at`, `received_at`, `stale_after_s`, and scope IDs.
- `cloud_metric_rollup`: downsampled history rows for UI graphs, not every raw local reading.
- `cloud_asset`: scoped metadata for snapshots and future clips, with object storage key, content type, byte size, hash, captured time, uploaded time, and optional signed-url cache metadata.
- `cloud_command`: durable command intent with `command_id`, `idempotency_key`, target scope, `command_type`, JSON payload, `requested_by`, status, `queued_at`, `expires_at`, claim fields, result/error fields, and lifecycle timestamps.
- `cloud_audit_event`: append-only auth, sync, command, rejection, and admin events.
- `gateway_credential`: hashed or otherwise non-plaintext gateway credential metadata, last used time, allowed site scope, and rotation state.

Cloud asset bytes must live in the private Railway `dirt-assets` bucket. Browser access to assets must go through short-lived signed URLs created by the cloud API. V1 must include a 30-day asset retention/lifecycle path and validation that unauthenticated users cannot fetch asset bytes or signed URLs.

Expose browser-facing API routes for read-only state first:

- `GET /api/sites`
- `GET /api/tents?site_id=homebox`
- `GET /api/tents/{tent_id}/state`
- `GET /api/tents/{tent_id}/metrics/current`
- `GET /api/tents/{tent_id}/metrics/history?metric=...&range=...`
- `GET /api/tents/{tent_id}/devices`
- `GET /api/tents/{tent_id}/assets/latest`
- `GET /api/sync/status`

Expose gateway-facing routes under a clear prefix such as `/api/gateway/v1/*`:

- `POST /api/gateway/v1/heartbeat`
- `PUT /api/gateway/v1/catalog`
- `PUT /api/gateway/v1/metrics/latest`
- `POST /api/gateway/v1/metrics/rollups`
- `POST /api/gateway/v1/assets/complete`
- `POST /api/gateway/v1/assets/sign-upload` or provider-equivalent direct upload handshake
- `POST /api/gateway/v1/commands/claim`
- `POST /api/gateway/v1/commands/{command_id}/result`

Milestone 3: Local Gateway Read-Only Sync.

Add a local gateway service as a separate app at `apps/gateway/` with import package `dirt_gateway`. It should use existing `dirt_shared` services to read local state and should not import hardware-loop modules from `dirt_hwd`.

The gateway should have explicit configuration in `apps/shared/src/dirt_shared/config.py` or a new gateway settings module:

- `DIRT_CLOUD_API_BASE_URL`
- `DIRT_CLOUD_SITE_ID`
- `DIRT_CLOUD_GATEWAY_ID`
- `DIRT_CLOUD_GATEWAY_TOKEN`
- `DIRT_CLOUD_SYNC_INTERVAL_S`
- `DIRT_CLOUD_COMMAND_POLL_INTERVAL_S`
- `DIRT_CLOUD_ASSET_SYNC_ENABLED`
- `DIRT_CLOUD_DRY_RUN`

Add local durability for sync results. Prefer local Postgres tables over ad hoc files for anything that must survive restarts:

- `cloud_sync_cursor`: latest synced catalog generation, latest metric timestamp per capability or rollup bucket, latest asset ID, and latest command claim cursor.
- `cloud_outbox`: event type, idempotency key, payload JSON, status, attempt count, next retry time, last error, and timestamps.

These tables solve the gateway's core reliability problem: cloud writes are side effects over an unreliable network. A gateway restart or Railway outage must not lose command results, asset metadata, rollup uploads, or catalog changes. The gateway writes durable local outbox rows before delivery, retries with backoff, and marks rows delivered only after the cloud API acknowledges the idempotency key.

Read-only sync responsibilities:

- upsert catalog rows for `homebox`, `main`, `breeding`, zones, devices, and capabilities;
- push latest current metrics and expected stale windows;
- push rollup buckets for dashboard ranges rather than raw high-volume telemetry; V1 windows are latest/current every sync tick, high-resolution recent buckets, 5-minute buckets for 24 hours, hourly buckets for 7 days, and 4-hour buckets for 30 days;
- push gateway heartbeat and backlog depth;
- upload latest snapshot assets directly to object storage, then report `cloud_asset` metadata;
- retry idempotently when the internet or cloud API is unavailable;
- expose structured logs through `log_event()` for a new `cloud_gateway` stream and use the test isolation pattern from `docs/observability.md`.

Gateway cadence defaults are heartbeat every 30 seconds, latest metrics every 30 seconds, command poll every 5 seconds, rollup sync every 1-5 minutes, and initial backfill for the last 30 days. The gateway must be testable without monkey patching: inject the cloud client, clock, sleeper/backoff policy, and local service bundle by constructor.

Milestone 4: Hosted Read-Only Frontend.

Make `web-ui` support both same-origin local mode and hosted API mode. Before editing TypeScript or route files, read:

- `docs/references/modern-idiomatic-typescript/INDEX.md`
- `docs/references/tanstack-router-v1/INDEX.md`
- `docs/references/tailwind-v4/INDEX.md`
- `docs/references/msw-v2/INDEX.md` if mocks or handlers change.

Expected frontend changes:

- use `VITE_DIRT_API_BASE_URL` as the supported hosted API base URL environment variable;
- keep same-origin local development working for `dirt-web`;
- add hosted session/bootstrap handling for cloud FastAPI single-user session auth;
- add site/tent selector state even if only `homebox/main` has live data at first;
- render gateway last-seen, per-metric source time, stale/offline state, and cloud sync backlog;
- ensure read-only hosted mode hides or disables all actuator controls until command Milestone 5 is complete;
- add MSW fixtures for live, stale, offline, empty breeding tent, and asset-unavailable states;
- configure the Railway `web-ui` service build without embedding local hardware credentials or gateway tokens.

Milestone 5: PTZ-Only Cloud Command Loop.

Add browser-facing cloud command routes:

- `POST /api/commands` with an idempotency key and target scope;
- `GET /api/commands/{command_id}`;
- `GET /api/commands?status=...` for recent command history.

Define the first allowed cloud command types:

- `ptz_preset` targeting `device_id='obsbot-main'` and `capability_id='ptz_move'`;
- `ptz_look` targeting `obsbot-main/ptz_move`;
- `ptz_zoom` targeting `obsbot-main/ptz_move`.

The local gateway command loop must:

- poll cloud commands with short expirations;
- claim one or more queued commands idempotently;
- reject expired, duplicate, over-scoped, unknown-device, unknown-capability, and unsafe command payloads;
- map allowed cloud commands to existing `PTZService` calls;
- record a local `command` ledger row for each accepted cloud command;
- report `running`, `succeeded`, `failed`, `rejected`, or `expired` back to cloud;
- never call humidifier, fan, or lights control paths in this milestone.

PTZ commands expire after 60 seconds in V1. If the gateway does not claim a command before expiration, the cloud API or gateway must mark it `expired` and the local box must not execute it later.

The hosted live page should show command lifecycle states clearly. If the gateway is offline or stale, PTZ buttons should be disabled and the UI should not imply live control.

Milestone 6: Operations, Rollout, And Recovery.

Add operator docs and service units:

- `systemd/dirt-gateway.service` or equivalent if the gateway is a long-running process;
- install wiring in `scripts/install-systemd`;
- a deploy script, expected at `scripts/deploy-control-plane`, that applies cloud migrations through Atlas and deploys `apps/control-plane/` plus `web-ui/` to the existing Railway services, replacing the placeholder deployments;
- update `AGENTS.md` and `docs/commands.md` so future agents know the supported Railway deploy command and required docs to read before running it;
- deployment instructions for Railway project setup, cloud API settings, cloud DB migrations, object storage, and gateway secrets;
- secret rotation steps for gateway credentials and browser auth;
- rollback instructions for disabling cloud commands while leaving read-only sync active;
- smoke-test scripts or documented commands for local gateway dry run, cloud API health, and hosted frontend smoke testing.

Add monitoring and audit surfaces:

- cloud `/api/health`;
- gateway heartbeat age and backlog depth;
- command rejection/failure counts;
- asset upload failure counts;
- structured local `cloud_gateway` JSONL events;
- cloud audit rows for auth, command creation, command claim, command result, and credential rotation.


## Concrete Steps

Run these commands from the repository root unless noted otherwise.

Before any code work:

    cd /home/akcom/code/dirt
    git status --short
    sed -n '1,220p' docs/commands.md
    sed -n '1,260p' .agents/PLANS.md

When editing cloud schema or local database models:

    sed -n '1,260p' docs/database.md
    sed -n '1,220p' docs/references/atlas/INDEX.md

When adding gateway logs or tests that write under `var/logs/`:

    sed -n '1,260p' docs/observability.md

When editing frontend TypeScript, routes, styles, or mocks:

    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/tailwind-v4/INDEX.md
    sed -n '1,220p' docs/references/msw-v2/INDEX.md

Expected validation commands for backend work:

    uv run pytest apps/control-plane/tests -q
    uv run ruff check apps/control-plane cloud/atlas/load-sqlmodel.py
    uv run ruff format apps/control-plane cloud/atlas/load-sqlmodel.py --check
    uv run pytest apps/gateway/tests apps/shared/tests apps/web/tests -q
    uv run pytest apps/tests/invariants/ -q
    uv run ruff check

Expected validation commands for frontend work:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Expected validation commands before commit:

    scripts/agent-fix
    git status --short


## Validation and Acceptance

Milestone 1 is accepted when this ExecPlan records concrete platform, database, storage, auth, and deployment decisions with rationale and links to current provider docs.

Milestone 2 is accepted when the cloud API can run locally against a test Postgres database and tests prove:

- browser users cannot read state without the chosen auth mechanism;
- gateway routes reject missing, invalid, or over-scoped credentials;
- catalog and latest metric upserts are idempotent;
- duplicate command creation with the same idempotency key returns the same command;
- command creation records intent only and performs no local hardware action;
- large asset flows use direct object-storage upload handshakes or equivalent metadata-only API calls.

Milestone 3 is accepted when the gateway can run locally in dry-run mode and then normal mode against a local or preview cloud API and tests prove:

- `homebox/main` and `homebox/breeding` catalog rows sync to cloud;
- latest metrics and rollup buckets are pushed without duplicate cloud rows;
- offline cloud API failures are retried without losing command results or asset metadata;
- local hardware loops continue if the gateway process is stopped;
- `cloud_gateway` logs are isolated in tests and useful in production.
- the gateway can survive a simulated cloud outage: local outbox rows remain pending, later delivery succeeds without duplicate cloud records, and no hardware service restarts are required.

Milestone 4 is accepted when a hosted or preview deployment shows:

- login or deployment protection blocks unauthenticated public access;
- the dashboard shows current main-tent state from cloud, not from the local LAN API;
- breeding tent appears as an empty or inactive scoped tent without breaking main-tent views;
- stale/offline state is visible when the gateway is stopped;
- actuator controls are hidden or disabled in read-only mode;
- assets are private: unauthenticated users cannot fetch signed URLs or asset bytes, and signed URLs expire;
- `pnpm --dir web-ui typecheck`, `lint`, `test`, and `build` pass.

Milestone 5 is accepted when:

- a hosted browser can submit a PTZ command;
- the cloud API stores a queued command with an expiration and idempotency key;
- the local gateway claims and executes it through existing local PTZ service code;
- the hosted browser can see running and terminal command status;
- unsafe command types, expired commands, duplicate commands, and offline gateway conditions are visibly handled;
- fan, humidifier, and lights remote commands remain unavailable.

Milestone 6 is accepted when:

- deployment and rollback docs are complete enough for a future agent to repeat;
- gateway systemd service can start, stop, restart, and report status;
- cloud API health, gateway heartbeat, sync backlog, asset failures, and command failures are observable;
- 30-day cloud asset retention/lifecycle behavior is implemented and documented;
- `scripts/deploy-control-plane` is documented in `AGENTS.md` and `docs/commands.md`;
- `uv run pytest -q` and frontend validation pass, or any skipped command is recorded with a reason.


## Idempotence and Recovery

Catalog, latest metric, rollup, asset metadata, heartbeat, command result, and audit writes must be idempotent. Use stable idempotency keys derived from site ID, stable local IDs, metric bucket timestamps, asset hashes or file paths, and cloud command IDs.

The local gateway must be safe to restart at any point. On startup it reads `cloud_sync_cursor` and `cloud_outbox`, resumes retries, and never re-executes a terminal cloud command. If the cloud API is offline, the gateway logs the failure, backs off, and keeps local hardware automation untouched.

Cloud command expiration is mandatory. A stale command must be marked `expired` or `rejected`, not executed late after network recovery. PTZ command expiration is 60 seconds in V1.

If hosted command behavior is suspect, the first rollback is configuration-only: disable command creation or command claiming while leaving read-only sync enabled. The second rollback is to stop `dirt-gateway.service`; local `dirt-hwd` and `dirt-web` continue to run.

Do not force-push, hard reset, delete unknown runtime data, or rotate production secrets without explicit user confirmation.


## Artifacts and Notes

The initial JSON sketch remains at `docs/epics/hosted-website-control-plane/plan.json`. Treat it as historical inspiration. This Markdown ExecPlan is the canonical implementation plan unless the user says otherwise.

Provider facts checked on 2026-05-04 during initial platform comparison:

- Vercel Python runtime docs say Python runtime is beta, supports FastAPI, and currently lists Python 3.13 support: https://vercel.com/docs/functions/runtimes/python.
- Vercel Functions limits docs currently list Python bundle size and request/response constraints relevant to keeping media out of functions: https://vercel.com/docs/functions/limitations.
- Vercel Blob server-upload docs currently call out the 4.5 MB Vercel Function body limit and recommend larger direct/client upload flows: https://vercel.com/docs/vercel-blob/server-upload.
- Vercel Cron docs currently make frequent sync unsuitable on Hobby cron; the local gateway should poll outbound instead: https://vercel.com/docs/cron-jobs/usage-and-pricing.

Provider facts checked on 2026-05-05 for the final Milestone 1 Railway decision:

- Railway's FastAPI guide documents deploying a FastAPI app as a Railway service and making it publicly accessible through service networking: https://docs.railway.com/guides/fastapi.
- Railway public networking docs say applications should listen on `0.0.0.0:$PORT`, which matches the placeholder TLS/routing discovery: https://docs.railway.com/deploy/exposing-your-app.
- Railway static hosting and React/Vite guides support hosting the built `web-ui` service on Railway rather than Vercel: https://docs.railway.com/guides/static-hosting and https://docs.railway.com/guides/react.
- Railway monorepo and build-configuration docs support separate service root directories/watch paths for `apps/control-plane/` and `web-ui/`: https://docs.railway.com/tutorials/deploying-a-monorepo and https://docs.railway.com/builds/build-configuration.
- Railway Postgres docs document the `DATABASE_URL` service variable and connections from services in the same project: https://docs.railway.com/databases/postgresql/.
- Railway variable-reference docs support wiring `control-plane-api` variables such as `DATABASE_URL=${{Postgres.DATABASE_URL}}` without copying secret values into the repo: https://docs.railway.com/reference/variables and https://docs.railway.com/guides/variables.
- Railway Buckets are private, S3-compatible object storage; public buckets are not currently supported, and the documented access patterns include presigned URLs or backend proxying: https://docs.railway.com/guides/storage-buckets.
- Railway bucket billing docs say there is no minimum storage retention and bucket egress is free, but uploads from Railway services to buckets count as service egress because buckets are on the public network: https://docs.railway.com/storage-buckets/billing.
- Railway custom-domain CLI docs say custom domains require both CNAME and TXT verification records and can take up to 72 hours to propagate: https://docs.railway.com/cli/domain.
- Cloudflare CNAME-flattening docs confirm a CNAME-equivalent apex record can answer as flattened IPs, and distinguish proxied Cloudflare-IP answers from DNS-only underlying-target answers: https://developers.cloudflare.com/dns/cname-flattening/cname-flattening-diagram/.
- Starlette SessionMiddleware supports signed cookie sessions with HttpOnly, SameSite, expiry, and `https_only` Secure-cookie options; FastAPI documents setting response cookies and password-hash based authentication patterns: https://www.starlette.io/middleware/, https://fastapi.tiangolo.com/advanced/response-cookies/, and https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/.
- Atlas versioned migration docs describe `atlas migrate diff` to generate reviewed migration files and `atlas migrate apply` to apply pending migrations during deploy, which is why cloud DDL is deferred out of app startup: https://atlasgo.io/versioned/diff and https://atlasgo.io/versioned/apply.

Current local implementation facts:

- `apps/shared/src/dirt_shared/services/commands.py` must be extended carefully for cloud-origin accepted commands; it currently rejects non-local sources.
- `apps/web/src/dirt_web/app.py` mounts MCP and local SPA fallback and should not be repurposed wholesale as a public cloud app.
- `web-ui/src/api-client/client.ts` already centralizes API client construction, which is the right place to support hosted base URLs.

Railway prework completed on 2026-05-05:

- CLI: `railway 4.45.0`.
- Project: `dirt-control-plane` (`4720b3f9-7e3b-461e-b44d-fbb9e349ed11`).
- Environment: `production` (`12ffb3c2-807b-4246-a7d0-f00466be68fe`).
- API service: `control-plane-api` (`15035b13-0995-4f81-b548-954b3e6aed29`), currently running a temporary placeholder deployment (`bafed902-bb4a-4598-bf53-63e84f9566b4`) until real cloud API code replaces it.
- UI service: `web-ui` (`c0297625-b063-4897-ac59-98e76f5f2413`), currently running a temporary placeholder deployment (`f872e500-166f-489c-a360-4ae2a6224cff`) until real `web-ui` deployment replaces it.
- Database service: `Postgres` (`fc7e0827-e834-48a1-901f-faf5b0595602`), online.
- Asset bucket: `dirt-assets` (`40462f7f-4691-4b45-9b34-e961e28612b4`), region `iad`.
- Ignored local secret file: `.env.prod`.
- Railway service variables were set for `control-plane-api`: `DATABASE_URL` references `${{Postgres.DATABASE_URL}}`; cloud URL/origin/site/gateway/bucket/S3/session variables were populated from `.env.prod`.
- Railway service variable was set for `web-ui`: `VITE_DIRT_API_BASE_URL=https://api.sirius-forge.com`.

Cloudflare DNS records required by Railway:

- UI apex route: create a `CNAME` for `sirius-forge.com` / `@` pointing to `hvyt0js8.up.railway.app`.
- UI ownership verification: create a `TXT` record named `_railway-verify` with value `railway-verify=a3fe925c1d1dfc6a0a875811ab7985c3caf6e563bd654a11b4fb05a62e324cba`.
- API route: create a `CNAME` for `api.sirius-forge.com` / `api` pointing to `lvp8v3hg.up.railway.app`.
- API ownership verification: create a `TXT` record named `_railway-verify.api` with value `railway-verify=97c22807ceeaec44f0e0d9470a72b043284fb42c04c9b176daa0eb5e490ff860`.

In Cloudflare, set these records to DNS-only while Railway validates and provisions certificates. If the apex cannot be represented as a literal CNAME in the Cloudflare UI, use Cloudflare's CNAME-flattened `@` record equivalent.

Post-placeholder deployment checks on 2026-05-05:

- `curl https://api.sirius-forge.com/healthz` returned HTTP 200 with `{"service": "control-plane-api", "status": "placeholder", "ok": true}`.
- `openssl s_client -servername api.sirius-forge.com -connect api.sirius-forge.com:443` showed `CN=api.sirius-forge.com`.
- `curl https://sirius-forge.com/healthz` returned HTTP 200 with the Sirius Forge placeholder HTML.
- `openssl s_client -servername sirius-forge.com -connect sirius-forge.com:443` showed `CN=sirius-forge.com` with SANs for `sirius-forge.com` and `*.sirius-forge.com`.
- After Cloudflare proxy was disabled for `api.sirius-forge.com`, Railway reported `DNS_RECORD_STATUS_PROPAGATED` for the API domain with current value `lvp8v3hg.up.railway.app`.

Milestone 1 validation on 2026-05-05:

- `uv run python - <<'PY' ... PY` checked that all required ExecPlan sections exist in order, Milestone 1 is marked complete, current Railway provider links are present, stale Vercel-build wording is absent, and local Markdown links resolve. Result: `OK: 12 required sections, 0 local links checked`.
- `uv run python -c "from pathlib import Path; t=Path('docs/epics/hosted-website-control-plane/ExecPlan.md').read_text(); required=('Purpose / Big Picture','Progress','Surprises & Discoveries','Decision Log','Outcomes & Retrospective','Context and Orientation','Plan of Work','Concrete Steps','Validation and Acceptance','Idempotence and Recovery','Artifacts and Notes','Interfaces and Dependencies'); assert all(f'## {s}' in t for s in required); assert 'Provider facts checked on 2026-05-05' in t; assert 'https://docs.railway.com/guides/fastapi' in t; assert ('configure '+'Vercel build') not in t; print('OK docs consistency')"` passed with `OK docs consistency`.
- `git diff --check -- docs/epics/hosted-website-control-plane/ExecPlan.md` passed with no whitespace errors.

Milestone 2 implementation artifacts on 2026-05-05:

- New package: `apps/control-plane/` with import package `dirt_control`.
- Cloud models: `apps/control-plane/src/dirt_control/models/cloud.py` defines `cloud_site`, `cloud_tent`, `cloud_zone`, `cloud_device`, `cloud_capability`, `cloud_latest_metric`, `cloud_metric_rollup`, `cloud_asset`, `cloud_command`, `cloud_audit_event`, and `gateway_credential`.
- Cloud API composition and routes: `apps/control-plane/src/dirt_control/app.py`, `api/browser.py`, `api/gateway.py`, `security.py`, `db.py`, and `settings.py`.
- Cloud Atlas path: `cloud/atlas/load-sqlmodel.py`, `cloud/migrations/20260505033411_cloud_control_plane_initial.sql`, and `cloud/migrations/atlas.sum`.
- Atlas config: root `atlas.hcl` has `data.external_schema.cloud_sqlmodel`, `var.cloud_migration_dir`, and env `cloud`.

Milestone 2 validation on 2026-05-05:

- `uv run --package dirt-control-plane python cloud/atlas/load-sqlmodel.py` emitted Postgres DDL for the cloud SQLModel metadata.
- `atlas migrate diff cloud_control_plane_initial --env cloud` succeeded and generated the initial cloud migration.
- `uv run pytest apps/control-plane/tests -q` passed with `6 passed`.
- `uv run ruff check apps/control-plane cloud/atlas/load-sqlmodel.py` passed.
- `uv run ruff format apps/control-plane cloud/atlas/load-sqlmodel.py --check` passed with `14 files already formatted`.

Replacement Worker M2b validation on 2026-05-05:

- `uv run pytest apps/control-plane/tests -q` passed with `7 passed` after the PTZ-only command correction.
- `uv run ruff check apps/control-plane cloud/atlas/load-sqlmodel.py` passed.
- `uv run ruff format apps/control-plane cloud/atlas/load-sqlmodel.py --check` passed with `14 files already formatted`.
- `uv run --package dirt-control-plane python cloud/atlas/load-sqlmodel.py | sed -n '1,20p'` emitted cloud Postgres DDL beginning with `CREATE TABLE cloud_site`.
- Main-agent verification reran `uv run pytest apps/control-plane/tests -q`, `uv run pytest apps/tests/invariants/ -q`, `uv run ruff check apps/control-plane cloud/atlas/load-sqlmodel.py`, `uv run ruff format apps/control-plane cloud/atlas/load-sqlmodel.py --check`, and `scripts/agent-fix`; all passed after replacing the brittle hardware-import assertion with a source import scan.

Milestone 3 implementation artifacts on 2026-05-05:

- New package: `apps/gateway/` with import package `dirt_gateway`.
- Gateway entry point: `apps/gateway/src/dirt_gateway/main.py`.
- Sync orchestration and DI protocols: `apps/gateway/src/dirt_gateway/sync.py`, `protocols.py`, `cloud.py`, `local.py`, and `outbox.py`.
- Local durability models: `apps/shared/src/dirt_shared/models/cloud_gateway.py` exports `CloudSyncCursor` and `CloudOutbox`.
- Local Atlas migration: `migrations/20260505035619_cloud_gateway_durability.sql` plus updated `migrations/atlas.sum`.
- Gateway config fields and config slice: `apps/shared/src/dirt_shared/config.py`.
- Structured log stream: `cloud_gateway` registered in `apps/shared/src/dirt_shared/observability.py` and documented in `docs/observability.md`.
- Tests: `apps/gateway/tests/test_sync.py`.

Milestone 3 validation on 2026-05-05:

- `uv run pytest apps/gateway/tests -q` passed with `7 passed`.
- `uv run pytest apps/gateway/tests apps/shared/tests -q` passed with `145 passed`.
- `uv run pytest apps/tests/invariants/ -q` passed with `116 passed, 1 skipped`.
- `uv run ruff check` passed.
- `uv run ruff format apps/gateway apps/shared/src/dirt_shared/models/cloud_gateway.py apps/shared/src/dirt_shared/models/__init__.py apps/shared/src/dirt_shared/config.py apps/shared/src/dirt_shared/observability.py --check` passed with `13 files already formatted`.

Milestone 5 implementation artifacts on 2026-05-05:

- Gateway command executor: `apps/gateway/src/dirt_gateway/commands.py`.
- Gateway HTTP client/protocol extensions: `apps/gateway/src/dirt_gateway/cloud.py` and `apps/gateway/src/dirt_gateway/protocols.py`.
- Gateway process wiring: `apps/gateway/src/dirt_gateway/main.py` now runs read-only sync and command polling loops together.
- Command result outbox dispatch: `apps/gateway/src/dirt_gateway/sync.py` handles `command_result` rows.
- Local command ledger source: `apps/shared/src/dirt_shared/services/commands.py` accepts `cloud_gateway` after local validation.
- Cloud claim/result hardening and command history filtering: `apps/control-plane/src/dirt_control/api/gateway.py` and `apps/control-plane/src/dirt_control/api/browser.py`.
- Hosted command UI and fixtures: `web-ui/src/routes/live.tsx`, `web-ui/src/api-client/cloud.ts`, `web-ui/src/mocks/handlers.ts`, and `web-ui/src/mocks/__tests__/handlers.test.ts`.
- Tests: `apps/gateway/tests/test_sync.py` and `apps/control-plane/tests/test_api.py`.

Milestone 5 validation on 2026-05-05:

- `uv run pytest apps/control-plane/tests apps/gateway/tests apps/shared/tests -q` passed with `158 passed`.
- `uv run pytest apps/tests/invariants/ -q` passed with `116 passed, 1 skipped`.
- `uv run ruff check` passed.
- `pnpm --dir web-ui typecheck` passed.
- `pnpm --dir web-ui lint` passed.
- `pnpm --dir web-ui test` passed with `1 passed (7 tests)`.
- `pnpm --dir web-ui build` passed and produced `web-ui/dist/`.
- Simplify pass fallback was run after implementation. Applied cleanup: removed a private helper import from the command executor, typed the command-loop sleeper, renamed the hosted live component, and stabilized the hosted direction-pad layout. Post-cleanup focused validation passed: `uv run pytest apps/gateway/tests/test_sync.py -q`, `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, and `pnpm --dir web-ui test`.
- Main-agent verification added the browser command site-scope guard; `uv run pytest apps/control-plane/tests -q` passed with `10 passed`.
- `uv lock --check` passed with `Resolved 238 packages`.

Replacement Worker M3b validation on 2026-05-05:

- `uv run pytest apps/gateway/tests -q` passed with `7 passed`.
- `uv run pytest apps/gateway/tests apps/shared/tests -q` passed with `145 passed`.
- `uv run pytest apps/tests/invariants/ -q` passed with `116 passed, 1 skipped`.
- `uv run ruff check apps/gateway apps/shared/src/dirt_shared/models/cloud_gateway.py apps/shared/src/dirt_shared/models/__init__.py apps/shared/src/dirt_shared/config.py apps/shared/src/dirt_shared/observability.py` passed.
- `uv run ruff format apps/gateway apps/shared/src/dirt_shared/models/cloud_gateway.py apps/shared/src/dirt_shared/models/__init__.py apps/shared/src/dirt_shared/config.py apps/shared/src/dirt_shared/observability.py --check` passed with `13 files already formatted`.
- `uv run ruff check` passed.
- `uv lock --check` passed with `Resolved 238 packages`.

Main-agent Milestone 3 verification on 2026-05-05:

- `uv run pytest apps/gateway/tests apps/shared/tests -q` passed with `145 passed` when run sequentially.
- `uv run pytest apps/control-plane/tests apps/gateway/tests -q` passed with `14 passed` after removing the cross-app bare `conftest` import.
- `uv run pytest apps/tests/invariants/ -q` passed with `116 passed, 1 skipped`.
- `uv run ruff check apps/gateway apps/shared/src/dirt_shared/models/cloud_gateway.py apps/shared/src/dirt_shared/models/__init__.py apps/shared/src/dirt_shared/config.py apps/shared/src/dirt_shared/observability.py` passed.
- `uv run ruff format apps/gateway apps/shared/src/dirt_shared/models/cloud_gateway.py apps/shared/src/dirt_shared/models/__init__.py apps/shared/src/dirt_shared/config.py apps/shared/src/dirt_shared/observability.py --check` passed with `13 files already formatted`.
- `uv lock --check` passed with `Resolved 238 packages`.
- `git diff --check -- . ':(exclude)apps/wake-word/**'` passed.

Milestone 4 implementation artifacts on 2026-05-05:

- Hosted API runtime switch: `web-ui/src/api-client/client.ts` and `web-ui/src/api-client/cloud.ts`.
- Hosted dashboard branch: `web-ui/src/routes/index.tsx`.
- Hosted session bootstrap: `web-ui/src/routes/__root.tsx`.
- Hosted read-only live page: `web-ui/src/routes/live.tsx`.
- MSW cloud scenarios and tests: `web-ui/src/mocks/handlers.ts` and `web-ui/src/mocks/__tests__/handlers.test.ts`; select with `?cloud_fixture=live`, `stale`, `offline`, `empty`, or `asset-unavailable`.
- Railway web-ui service config: `web-ui/railway.json`.
- Narrow sync status route fix and test: `apps/control-plane/src/dirt_control/api/browser.py` and `apps/control-plane/tests/test_api.py`.

Milestone 4 validation on 2026-05-05:

- `pnpm --dir web-ui typecheck` passed.
- `pnpm --dir web-ui lint` passed.
- `pnpm --dir web-ui test` passed with `6 passed`, including focused MSW coverage for live, stale, offline, empty breeding tent, and asset-unavailable hosted states.
- `pnpm --dir web-ui build` passed and wrote `web-ui/dist/`.
- `uv run pytest apps/control-plane/tests -q` passed with `8 passed`.
- Simplify pass ran using the fallback review path because no subagent spawn tool is available in this runtime; it applied one cleanup so the hosted dashboard trusts the API `status` field when present and computes freshness only as fallback.

Milestone 6 implementation artifacts on 2026-05-05:

- Gateway unit and install wiring: `systemd/dirt-gateway.service` and `scripts/install-systemd`.
- Supported deploy flow: `scripts/deploy-control-plane` and `apps/control-plane/railway.json`.
- Cloud operational schema migration: `cloud/migrations/20260505045254_cloud_operational_hardening.sql` adds `cloud_site.gateway_backlog_depth integer NOT NULL DEFAULT 0`.
- Cloud monitoring and audit surfaces: `apps/control-plane/src/dirt_control/api/browser.py`, `api/gateway.py`, `audit.py`, `retention.py`, and `storage.py`.
- Gateway retention/failure reporting: `apps/gateway/src/dirt_gateway/sync.py`, `cloud.py`, and `protocols.py`.
- Operator docs: `docs/hosted-control-plane.md`, `docs/commands.md`, `AGENTS.md`, `.env.example`, and `docs/observability.md`.

Milestone 6 validation on 2026-05-05:

- `uv lock` passed with `Resolved 238 packages in 680ms`.
- `atlas migrate diff cloud_operational_hardening --env cloud` generated the cloud migration after the model was corrected to include a safe default.
- `uv run pytest apps/control-plane/tests -q` passed with `14 passed`.
- `uv run pytest apps/gateway/tests -q` passed with `11 passed`.
- `uv run ruff check apps/control-plane apps/gateway cloud/atlas/load-sqlmodel.py` passed.
- `uv run ruff format apps/control-plane apps/gateway cloud/atlas/load-sqlmodel.py --check` passed with `27 files already formatted`.
- `bash -n scripts/deploy-control-plane scripts/install-systemd` passed.
- `systemd-analyze --user verify systemd/dirt-gateway.service` passed with no output.
- `uv run --package dirt-gateway python -m dirt_gateway.main --help` showed `--once` and `--dry-run`.
- `uv run --package dirt-control-plane python cloud/atlas/load-sqlmodel.py | sed -n '1,30p'` emitted cloud DDL with `gateway_backlog_depth INTEGER DEFAULT '0' NOT NULL`.
- `atlas migrate lint --env cloud --latest 1` was skipped as a validation blocker because the installed Atlas CLI reports migrate lint is Atlas Pro-only starting v0.38.
- Simplify pass fallback ran locally because no subagent spawn tool is available. Applied cleanup: delete retained cloud assets by primary `asset_id` instead of object key, and avoid writing one audit row per disabled command-claim poll.
- Post-simplify focused validation passed: `uv run pytest apps/control-plane/tests -q` with `14 passed`, `uv run pytest apps/gateway/tests -q` with `11 passed`, `uv run ruff check apps/control-plane apps/gateway cloud/atlas/load-sqlmodel.py`, and `uv run ruff format apps/control-plane apps/gateway cloud/atlas/load-sqlmodel.py --check`.
- Main-agent verification corrected the deploy/systemd environment loading so `.env` is loaded before `.env.prod`, then reran focused validation: `uv run pytest apps/control-plane/tests apps/gateway/tests apps/shared/tests -q` passed with `163 passed`; `uv run pytest apps/tests/invariants/ -q` passed with `116 passed, 1 skipped`; `uv run ruff check apps/control-plane apps/gateway cloud/atlas/load-sqlmodel.py` passed; `uv run ruff format apps/control-plane apps/gateway cloud/atlas/load-sqlmodel.py --check` passed with `27 files already formatted`; `bash -n scripts/deploy-control-plane scripts/install-systemd` passed; `systemd-analyze --user verify systemd/dirt-gateway.service` passed; `pnpm --dir web-ui typecheck`, `lint`, `test`, and `build` passed.
- Main-agent deployment attempt 1 stopped before shared-state mutation because no local `DIRT_CLOUD_DATABASE_URL` was set. Verification then added Railway `DATABASE_URL` compatibility and a script fallback that reads the service variable without printing it.
- Main-agent deployment attempt 2 stopped before app deployment because the app service `DATABASE_URL` used Railway's private internal hostname, which local Atlas cannot resolve. Verification then switched the script fallback to the Postgres service `DATABASE_PUBLIC_URL`.
- Full backend validation `uv run pytest -q` ran and failed only in pre-existing wake-word surfaces: 596 passed, 2 skipped, 4 failed (`apps/wake-word/tests/test_imports.py` cannot import `scipy.special.sph_harm`; `test_paths.py` TPU-layout fallback; `test_seed.py` duplicate suffix behavior). No wake-word files were touched in this milestone.
- Frontend validation passed: `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `pnpm --dir web-ui test` with `7 passed`, and `pnpm --dir web-ui build`.
- `scripts/agent-fix` passed and applied no additional changes.
- Production `scripts/deploy-control-plane` completed after provider-specific Railway build/runtime fixes. Final Railway states: API deployment `e6aad95d-4518-4382-a2e2-a4612d26611b` `SUCCESS`; web-ui deployment `c6e7f321-d330-4cef-88d3-293587fe391c` `SUCCESS`.
- Public production smoke checks passed: `https://api.sirius-forge.com/api/health` returned `ok=true`, `service=control-plane-api`, `status=offline`, `asset_retention_days=30`, `commands_enabled=true`; `https://sirius-forge.com/` served built SPA asset references and no placeholder text.
- Public auth/privacy checks passed: unauthenticated `/api/sites`, `/api/tents/main/assets/latest`, and `/api/assets/example/signed-url` returned 401; authenticated login returned 200 and session-authenticated `/api/auth/me` and `/api/sites` returned 200. This verifies grow asset metadata and signed-URL access are browser-session protected in production.
- Final production hardening deployed after gateway credential bootstrap and S3 presigned asset flow fixes. Final Railway states: API deployment `011d285b-4e3c-4eda-b5b5-6ee98aa51b92` `SUCCESS`; web-ui deployment `424832de-0f75-4c80-9d40-fa36e59a6a87` `SUCCESS`.
- Local gateway production readiness checks passed: local Atlas migration `20260505035619_cloud_gateway_durability` was applied explicitly, `scripts/install-systemd` installed the unit, `systemctl --user is-active dirt-gateway` returned `active`, and the cloud health endpoint reported `status=live` with a current heartbeat.
- Final asset privacy checks passed: unauthenticated `/api/tents/main/assets/latest` returned 401; authenticated `/api/tents/main/assets/latest` returned five assets whose signed URL host was `t3.storageapi.dev`; no public asset route is required for V1.
- Residual operational state at final check: local outbox still had pending heartbeat/latest/rollup rows and one asset row while delivered assets had reached five; cloud health reported `gateway_backlog_depth=12` and `asset_failures_24h=18` from earlier failed upload attempts. This is safe to leave because the gateway is active and retrying, but the old failure counter/backlog should be watched after the next normal sync cycles.


## Interfaces and Dependencies

New or changed repository interfaces expected by this plan:

- `apps/control-plane/pyproject.toml`
- `apps/control-plane/src/dirt_control/app.py`
- `apps/control-plane/src/dirt_control/settings.py`
- `apps/control-plane/src/dirt_control/models/`
- `apps/control-plane/src/dirt_control/audit.py`
- `apps/control-plane/src/dirt_control/retention.py`
- `apps/control-plane/src/dirt_control/storage.py`
- `apps/control-plane/src/dirt_control/api/browser.py`
- `apps/control-plane/src/dirt_control/api/gateway.py`
- `apps/control-plane/railway.json`
- `apps/control-plane/tests/`
- cloud Atlas migration environment `cloud` in `atlas.hcl` and migration directory `cloud/migrations/`
- `apps/gateway/pyproject.toml`
- `apps/gateway/src/dirt_gateway/main.py`
- `apps/gateway/src/dirt_gateway/sync.py`
- `apps/gateway/src/dirt_gateway/commands.py`
- `apps/gateway/tests/`
- local sync durability models, either in `apps/shared/src/dirt_shared/models/` or a clearly scoped gateway model module
- `systemd/dirt-gateway.service`
- `scripts/deploy-control-plane`
- `docs/hosted-control-plane.md`
- `contracts/cloud-control-plane-v1.yaml` or an explicitly documented extension of `contracts/webapp-v1.yaml`
- generated Python/TypeScript clients for any new browser-facing API contract
- `web-ui` support for `VITE_DIRT_API_BASE_URL` or the final chosen equivalent

External dependencies selected by prework:

- hosted frontend: Railway service `web-ui`;
- cloud API runtime: Railway service `control-plane-api` running long-lived FastAPI;
- managed Postgres provider: Railway `Postgres`;
- object storage provider: Railway `dirt-assets` bucket;
- browser auth provider: cloud FastAPI single-user session auth;
- gateway credential storage and rotation mechanism: generated token in ignored local `.env.prod`, SHA-256 digest in Railway `control-plane-api` variables for V1.

Runtime environment variables:

- `DIRT_CLOUD_API_BASE_URL`
- `DIRT_CLOUD_DATABASE_URL`
- `DIRT_CLOUD_ADMIN_USERNAME`
- `DIRT_CLOUD_ADMIN_PASSWORD_HASH`
- `DIRT_CLOUD_ALLOWED_ORIGINS`
- `DIRT_CLOUD_ASSET_RETENTION_DAYS`
- `DIRT_CLOUD_COMMAND_CREATION_ENABLED`
- `DIRT_CLOUD_GATEWAY_COMMAND_CLAIM_ENABLED`
- `DIRT_CLOUD_BUCKET_NAME`
- `DIRT_CLOUD_S3_ENDPOINT`
- `DIRT_CLOUD_S3_REGION`
- `DIRT_CLOUD_S3_ACCESS_KEY_ID`
- `DIRT_CLOUD_S3_SECRET_ACCESS_KEY`
- `DIRT_CLOUD_GATEWAY_TOKEN`
- `DIRT_CLOUD_GATEWAY_ID`
- `DIRT_CLOUD_SITE_ID`
- `DIRT_CLOUD_SYNC_INTERVAL_S`
- `DIRT_CLOUD_COMMAND_POLL_INTERVAL_S`
- `DIRT_CLOUD_ASSET_SYNC_ENABLED`
- `DIRT_CLOUD_DRY_RUN`
- `VITE_DIRT_API_BASE_URL`


## Revision Notes

- 2026-05-04 / Codex: Created the initial Markdown ExecPlan from the old JSON sketch, current multi-tent implementation, current local API shape, and current Vercel platform docs.
- 2026-05-05 / Codex Worker M1: Completed Milestone 1 by recording the final Railway platform, database, storage, auth, DNS, deployment, and no-app-start-DDL decisions with current provider links and validation evidence.
- 2026-05-05 / Codex Worker M2: Completed Milestone 2 locally by adding the `dirt-control-plane` workspace package, dedicated cloud Atlas env/migrations, thin browser/gateway API, signed asset URL abstraction, command-intent-only creation, and acceptance tests.
- 2026-05-05 / Codex replacement Worker M2b: Kept Milestone 2 scope thin, added missing browser command list route, extended the command acceptance test to cover create/list/fetch idempotency, reran focused tests and ruff validation, and performed the requested simplify fallback pass.
- 2026-05-05 / Codex replacement Worker M2b correction: Restricted browser command creation to V1 PTZ commands only (`ptz_preset`, `ptz_look`, `ptz_zoom`) for `obsbot-main/ptz_move`, removed user-selectable command expiry, enforced exactly 60 seconds, and added focused rejection/expiry tests.
- 2026-05-05 / Codex: During main-agent verification, replaced a brittle `sys.modules`-based no-hardware-call test with an `ast` import scan of `dirt_control`, because full-suite app tests import `dirt_hwd` independently before control-plane tests execute.
- 2026-05-05 / Codex Worker M3: Completed Milestone 3 by adding the `dirt-gateway` workspace package, local Atlas-managed cloud gateway durability tables, read-only DI sync/outbox orchestration, local projection collectors, private asset sign-upload/complete delivery, `cloud_gateway` observability, and focused acceptance tests. A simplify pass then reduced small outbox/sync rough edges before final validation.
- 2026-05-05 / Codex replacement Worker M3b: Re-verified the inherited Milestone 3 implementation against the requested acceptance tests, ran the simplify fallback review locally, made no source changes beyond recording validation, and left Milestone 4+ untouched.
- 2026-05-05 / Codex: During main-agent verification, added `apps/gateway` to the pre-commit per-app pytest hook and recorded that DB-backed pytest sessions sharing the worktree template database must run sequentially.
- 2026-05-05 / Codex: Removed a bare `from conftest import FIXED_NOW` import from the control-plane API tests after the expanded multi-app pytest hook exposed cross-app `conftest.py` import collision.
- 2026-05-05 / Codex Worker M4: Completed Milestone 4 locally by adding hosted API mode, cloud session bootstrap, site/tent-scoped read-only dashboard surfaces, stale/offline/sync backlog rendering, authenticated signed-asset display, hosted read-only live behavior, MSW v2 cloud scenarios, a Railway web-ui config, and a narrow cloud `/api/sync/status` response fix. Deployment was left blocked on the missing Milestone 6 deploy script and lack of explicit approval for direct Railway deployment.
- 2026-05-05 / Codex Worker M6: Completed local Milestone 6 operations hardening with the gateway systemd unit, install wiring, supported Railway deploy script, cloud health/audit/retention/failure surfaces, command rollback toggles, operator docs, and focused validation. Production deployment remains blocked pending explicit approval for the shared-state Railway migration/deploy action.
- 2026-05-05 / Codex: Completed final production hardening after real Railway deployment exposed provider/runtime issues. The deploy flow now bootstraps gateway credentials, uses private S3 presigned asset URLs, deploys the API/UI real services, and leaves the local gateway active with live cloud health.
