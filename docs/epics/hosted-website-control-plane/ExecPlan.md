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
- [ ] Milestone 1: decide and document hosted platform, auth, database, object storage, and deployment boundaries.
- [ ] Milestone 2: implement the cloud control-plane schema and thin hosted API locally, with tests.
- [ ] Milestone 3: implement local outbound gateway sync for read-only catalog, latest state, freshness, rollups, and assets.
- [ ] Milestone 4: deploy the read-only hosted dashboard and prove stale/offline behavior.
- [ ] Milestone 5: add the PTZ-only cloud command loop.
- [ ] Milestone 6: harden operations, recovery, and rollout documentation.


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


## Outcomes & Retrospective

No implementation milestones have been completed yet. At completion, this section must name the deployed frontend URL, hosted API URL, database/storage providers, gateway systemd unit status, validation commands run, and any intentionally deferred controls.


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

Create a short decision record in this ExecPlan before coding. Decide:

- whether the cloud API V1 runs as Vercel Python/FastAPI Functions, a separately hosted long-lived FastAPI service, or a user-approved hybrid;
- which managed Postgres provider stores cloud state;
- which object storage provider stores snapshots and future video clips;
- which browser auth provider protects the hosted website;
- which non-browser credential model authenticates the local gateway;
- which environments exist, at minimum local dev, preview, and production;
- which public domain names and CORS origins are allowed.

Recommended default unless new information changes it: Vercel hosts the `web-ui` production build, and the first prototype uses Vercel Python/FastAPI only for the thin cloud API if package size and cold-start behavior are acceptable. The local gateway performs frequent sync, so Vercel Cron is not required. If the Vercel Python beta runtime or bundle shape creates friction, switch the cloud API to a small long-lived FastAPI deployment without changing the schema or browser contract.

Milestone 2: Cloud Control-Plane Schema And API.

Add a new Python workspace package, tentatively `apps/control-plane/` with import package `dirt_control`. Do not reuse `dirt_web.app.create_app()` for the public API. The new package owns public auth dependencies, gateway auth dependencies, cloud settings, cloud SQLModel metadata, and the cloud FastAPI app.

Add a separate cloud migration path. Do not mix cloud tables into the local `migrations/` directory unless the implementer explicitly records why that is safer. A clean shape is:

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

Add a local gateway service as a separate app, tentatively `apps/gateway/` with import package `dirt_gateway`. It should use existing `dirt_shared` services to read local state and should not import hardware-loop modules from `dirt_hwd`.

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

Read-only sync responsibilities:

- upsert catalog rows for `homebox`, `main`, `breeding`, zones, devices, and capabilities;
- push latest current metrics and expected stale windows;
- push rollup buckets for dashboard ranges rather than raw high-volume telemetry;
- push gateway heartbeat and backlog depth;
- upload latest snapshot assets directly to object storage, then report `cloud_asset` metadata;
- retry idempotently when the internet or cloud API is unavailable;
- expose structured logs through `log_event()` for a new `cloud_gateway` stream and use the test isolation pattern from `docs/observability.md`.

Milestone 4: Hosted Read-Only Frontend.

Make `web-ui` support both same-origin local mode and hosted API mode. Before editing TypeScript or route files, read:

- `docs/references/modern-idiomatic-typescript/INDEX.md`
- `docs/references/tanstack-router-v1/INDEX.md`
- `docs/references/tailwind-v4/INDEX.md`
- `docs/references/msw-v2/INDEX.md` if mocks or handlers change.

Expected frontend changes:

- add a supported API base URL environment variable, likely `VITE_DIRT_API_BASE_URL`;
- keep same-origin local development working for `dirt-web`;
- add hosted session/bootstrap handling after the auth decision from Milestone 1;
- add site/tent selector state even if only `homebox/main` has live data at first;
- render gateway last-seen, per-metric source time, stale/offline state, and cloud sync backlog;
- ensure read-only hosted mode hides or disables all actuator controls until command Milestone 5 is complete;
- add MSW fixtures for live, stale, offline, empty breeding tent, and asset-unavailable states;
- configure Vercel build for `web-ui` without embedding local hardware credentials or gateway tokens.

Milestone 5: PTZ-Only Cloud Command Loop.

Add browser-facing cloud command routes:

- `POST /api/commands` with an idempotency key and target scope;
- `GET /api/commands/{command_id}`;
- optionally `GET /api/commands?status=...` for recent command history.

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

The hosted live page should show command lifecycle states clearly. If the gateway is offline or stale, PTZ buttons should be disabled and the UI should not imply live control.

Milestone 6: Operations, Rollout, And Recovery.

Add operator docs and service units:

- `systemd/dirt-gateway.service` or equivalent if the gateway is a long-running process;
- install wiring in `scripts/install-systemd` if appropriate;
- deployment instructions for Vercel project setup, cloud API settings, cloud DB migrations, object storage, and gateway secrets;
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

Milestone 4 is accepted when a hosted or preview deployment shows:

- login or deployment protection blocks unauthenticated public access;
- the dashboard shows current main-tent state from cloud, not from the local LAN API;
- breeding tent appears as an empty or inactive scoped tent without breaking main-tent views;
- stale/offline state is visible when the gateway is stopped;
- actuator controls are hidden or disabled in read-only mode;
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
- `uv run pytest -q` and frontend validation pass, or any skipped command is recorded with a reason.


## Idempotence and Recovery

Catalog, latest metric, rollup, asset metadata, heartbeat, command result, and audit writes must be idempotent. Use stable idempotency keys derived from site ID, stable local IDs, metric bucket timestamps, asset hashes or file paths, and cloud command IDs.

The local gateway must be safe to restart at any point. On startup it reads `cloud_sync_cursor` and `cloud_outbox`, resumes retries, and never re-executes a terminal cloud command. If the cloud API is offline, the gateway logs the failure, backs off, and keeps local hardware automation untouched.

Cloud command expiration is mandatory. A stale command must be marked `expired` or `rejected`, not executed late after network recovery.

If hosted command behavior is suspect, the first rollback is configuration-only: disable command creation or command claiming while leaving read-only sync enabled. The second rollback is to stop `dirt-gateway.service`; local `dirt-hwd` and `dirt-web` continue to run.

Do not force-push, hard reset, delete unknown runtime data, or rotate production secrets without explicit user confirmation.


## Artifacts and Notes

The initial JSON sketch remains at `docs/epics/hosted-website-control-plane/plan.json`. Treat it as historical inspiration. This Markdown ExecPlan is the canonical implementation plan unless the user says otherwise.

Provider facts checked on 2026-05-04:

- Vercel Python runtime docs say Python runtime is beta, supports FastAPI, and currently lists Python 3.13 support: https://vercel.com/docs/functions/runtimes/python.
- Vercel Functions limits docs currently list Python bundle size and request/response constraints relevant to keeping media out of functions: https://vercel.com/docs/functions/limitations.
- Vercel Blob server-upload docs currently call out the 4.5 MB Vercel Function body limit and recommend larger direct/client upload flows: https://vercel.com/docs/vercel-blob/server-upload.
- Vercel Cron docs currently make frequent sync unsuitable on Hobby cron; the local gateway should poll outbound instead: https://vercel.com/docs/cron-jobs/usage-and-pricing.

Current local implementation facts:

- `apps/shared/src/dirt_shared/services/commands.py` must be extended carefully for cloud-origin accepted commands; it currently rejects non-local sources.
- `apps/web/src/dirt_web/app.py` mounts MCP and local SPA fallback and should not be repurposed wholesale as a public cloud app.
- `web-ui/src/api-client/client.ts` already centralizes API client construction, which is the right place to support hosted base URLs.


## Interfaces and Dependencies

New or changed repository interfaces expected by this plan:

- `apps/control-plane/pyproject.toml`
- `apps/control-plane/src/dirt_control/app.py`
- `apps/control-plane/src/dirt_control/settings.py`
- `apps/control-plane/src/dirt_control/models/`
- `apps/control-plane/src/dirt_control/api/browser.py`
- `apps/control-plane/src/dirt_control/api/gateway.py`
- `apps/control-plane/tests/`
- a cloud Atlas migration environment and migration directory
- `apps/gateway/pyproject.toml`
- `apps/gateway/src/dirt_gateway/main.py`
- `apps/gateway/src/dirt_gateway/sync.py`
- `apps/gateway/src/dirt_gateway/commands.py`
- `apps/gateway/tests/`
- local sync durability models, either in `apps/shared/src/dirt_shared/models/` or a clearly scoped gateway model module
- `systemd/dirt-gateway.service`
- `contracts/cloud-control-plane-v1.yaml` or an explicitly documented extension of `contracts/webapp-v1.yaml`
- generated Python/TypeScript clients for any new browser-facing API contract
- `web-ui` support for `VITE_DIRT_API_BASE_URL` or the final chosen equivalent

External dependencies to decide in Milestone 1:

- hosted frontend: Vercel unless explicitly changed;
- cloud API runtime: Vercel Python/FastAPI Functions or a long-lived FastAPI host;
- managed Postgres provider;
- object storage provider;
- browser auth provider or deployment protection strategy;
- gateway credential storage and rotation mechanism.

Runtime environment variables likely needed:

- `DIRT_CLOUD_API_BASE_URL`
- `DIRT_CLOUD_DATABASE_URL`
- `DIRT_CLOUD_OBJECT_STORAGE_*` provider-specific settings
- `DIRT_CLOUD_AUTH_*` provider-specific browser auth settings
- `DIRT_CLOUD_GATEWAY_TOKEN`
- `DIRT_CLOUD_GATEWAY_ID`
- `DIRT_CLOUD_SITE_ID`
- `DIRT_CLOUD_SYNC_INTERVAL_S`
- `DIRT_CLOUD_COMMAND_POLL_INTERVAL_S`
- `DIRT_CLOUD_DRY_RUN`
- `VITE_DIRT_API_BASE_URL`


## Revision Notes

- 2026-05-04 / Codex: Created the initial Markdown ExecPlan from the old JSON sketch, current multi-tent implementation, current local API shape, and current Vercel platform docs.
