# Hosted UI Parity

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the hosted site at `https://sirius-forge.com/` should feel like the same operator dashboard as the local `dirt-web` site at `http://192.168.1.79:8001/`, with the expected safety boundary that hosted remains a read-only projection plus PTZ-only command intent. The highest-priority outcome is dashboard parity: a user should be able to open the hosted UI away from the local network and see the same six first-class dashboard gauges, stage-aware target/status semantics, and Plant A-D cards that make the local dashboard useful at a glance. The hosted UI should also restore grow context, device health, dark theme ownership, recent private assets, and a working read-only wiki.

This plan exists because the first hosted-control-plane implementation proved the Railway deployment, cloud API, gateway, private assets, and PTZ command loop, but the hosted dashboard diverged from the local UI. The hosted implementation currently has a separate `HostedDashboardPage`, cloud-specific endpoints, and no cloud wiki API. That produced visible regressions: wiki hangs or renders empty, grow context is missing, fan/humidifier cards are missing or lack target/status treatment, plant cards are absent, device health rows show `NEVER`, and theme ownership is tied to `TopBar` instead of the app root.

The final observable result is a browser comparison: log in to hosted and local, capture dashboard and wiki screenshots with `agent-browser`, and confirm both surfaces expose the same operator information. Exact data timestamps may differ by gateway sync delay, but the information architecture and status semantics must match.


## Progress

- [x] (2026-05-05T13:20:00-06:00) Created this ExecPlan from the hosted/local UI parity review and the captured `agent-browser` evidence.
- [ ] Milestone 1: establish a repeatable parity baseline and API matrix.
- [ ] Milestone 2: add cloud UI-projection schema and gateway payloads for dashboard envelopes and Plant A-D cards first, then grow context, device status, and wiki.
- [ ] Milestone 3: expose hosted read-only API routes compatible with the local SPA dashboard and plants contract.
- [ ] Milestone 4: converge the frontend so local and hosted share the dashboard and plants route code paths, then finish wiki/theme parity.
- [ ] Milestone 5: deploy through `scripts/deploy-control-plane` and capture parity evidence.


## Surprises & Discoveries

- Observation: Hosted wiki currently calls the cloud API for local wiki routes and gets `404`.
  Evidence: `agent-browser` network output showed `GET https://api.sirius-forge.com/api/wiki/tree` returning `404`, while `GET http://192.168.1.79:8001/api/wiki/tree` returned `200` and rendered the wiki sidebar.

- Observation: The hosted dashboard is not a renderer of the local dashboard contract; it is a separate cloud-specific dashboard.
  Evidence: `web-ui/src/routes/index.tsx` chooses `HostedDashboardPage` when `isHostedApiMode` is true. The hosted path reads `/api/tents/{tent_id}/metrics/current`, `/api/tents/{tent_id}/devices`, and cloud-specific TypeScript interfaces from `web-ui/src/api-client/cloud.ts`, while the local path reads `/api/grow/current`, `/api/sensors/current`, `/api/sensors/metadata`, `/api/plants`, and `/api/system/devices`.

- Observation: The cloud schema stores raw-ish latest metrics and rollups, but not the local UI envelopes that encode grow-stage target bands and status labels.
  Evidence: `apps/control-plane/src/dirt_control/models/cloud.py` has `CloudLatestMetric` and `CloudMetricRollup`, but no table for the contract-shaped `SensorsCurrent`, grow context, plants response, or system device status response.

- Observation: Device catalog sync does not currently populate the local status table semantics.
  Evidence: The hosted screenshot showed devices with `LAST SEEN` as `NEVER`, while the local screenshot showed `OK` and `OFFLINE` status values from `/api/system/devices`.

- Observation: Dark mode works after login when the `TopBar` button is clicked, but theme application is not owned by the root app shell.
  Evidence: `agent-browser` click on the theme button made `document.documentElement.getAttribute("data-theme")` return `"dark"` in both local and hosted sessions. Login and auth-loading screens do not mount `TopBar`, and the visible button label is `Auto` even though the behavior is a manual light/dark toggle.

- Observation: Hosted admin auth now uses only `DIRT_CLOUD_ADMIN_USERNAME` plus `DIRT_CLOUD_ADMIN_PASSWORD_HASH`.
  Evidence: The deploy script no longer derives hosted credentials from local `AUTH_USERNAME` / `AUTH_PASSWORD`. Do not reintroduce plaintext hosted password variables while implementing this plan.


## Decision Log

- Decision: Implement hosted parity by syncing UI projections, not by exposing the local `dirt-web` process or mirroring the local database.
  Rationale: The original hosted-control-plane boundary remains correct: the local box owns hardware and the local database; the cloud API serves selected operator projections. UI parity needs richer projections, not inbound access to the local network.
  Date/Author: 2026-05-05 / Codex

- Decision: Make the hosted cloud API provide local-contract-compatible read-only routes for dashboard and wiki data.
  Rationale: The local SPA already has tested components and OpenAPI-generated types for `/api/grow/current`, `/api/sensors/current`, `/api/sensors/metadata`, `/api/plants`, `/api/system/devices`, and `/api/wiki/*`. Reusing those shapes lets the frontend share code and reduces future drift.
  Date/Author: 2026-05-05 / Codex

- Decision: Keep V1 hosted remote commands PTZ-only.
  Rationale: UI parity means display parity, not adding remote fan, light, or humidifier control. The existing safety decision from `docs/epics/hosted-website-control-plane/ExecPlan.md` still applies.
  Date/Author: 2026-05-05 / Codex

- Decision: Use JSONB projection rows for contract-shaped UI payloads unless implementation proves a strongly typed table is materially simpler for a specific projection.
  Rationale: These payloads are read by primary key and replaced wholesale by the gateway. They are UI snapshots, not analytical records. Keeping them as named projection documents avoids duplicating every local contract model into cloud SQL columns, while metric rollups can continue using `CloudMetricRollup` for history.
  Date/Author: 2026-05-05 / Codex

- Decision: Sync wiki as an authenticated read-only cloud projection.
  Rationale: The hosted UI should not hide Wiki if the local operator experience includes it. Wiki contents are operational notes, so hosted wiki routes must require browser auth and must not become static public files.
  Date/Author: 2026-05-05 / Codex

- Decision: Move theme application to the root app shell and keep the visible control honest.
  Rationale: Theme should apply on login, auth-loading, dashboard, live, and wiki. The current `Auto` label is misleading because there is no system-preference auto mode.
  Date/Author: 2026-05-05 / Codex

- Decision: Prioritize full dashboard parity and Plant A-D cards over the other parity gaps.
  Rationale: The user explicitly identified findings 3 and 4 as the most important to get right. The implementation should first make hosted show the same six gauge cards, target/status semantics, sparklines, and plants strip as local before spending time on less central polish.
  Date/Author: 2026-05-05 / Codex


## Outcomes & Retrospective

Not yet implemented. Update this section after each milestone with what changed, what remained different between local and hosted, and any follow-up work that should be split out of this parity plan.


## Context and Orientation

The repository has a local Python web service and a hosted cloud control plane.

Local `dirt-web` runs on the homebox and serves the local SPA plus local API routes. Important local API files are:

- `apps/web/src/dirt_web/api/grow.py`: serves `/api/grow/current`.
- `apps/web/src/dirt_web/api/sensors.py`: serves `/api/sensors/current`, `/api/sensors/history`, and `/api/sensors/metadata`.
- `apps/web/src/dirt_web/api/plants.py`: serves `/api/plants`, `/api/plants/{code}`, and `/api/plants/{code}/moisture`.
- `apps/web/src/dirt_web/api/system.py`: serves `/api/system/devices`.
- `apps/web/src/dirt_web/api/wiki.py`: serves `/api/wiki/tree`, `/api/wiki/file`, and `/api/wiki/search`.
- `contracts/webapp-v1.yaml`: defines the local SPA API contract and generated TypeScript/Pydantic shapes.

Hosted `control-plane-api` runs as FastAPI on Railway. It has its own cloud schema and routes:

- `apps/control-plane/src/dirt_control/models/cloud.py`: SQLModel tables for cloud site/tent/catalog/latest metrics/rollups/assets/commands/audit.
- `apps/control-plane/src/dirt_control/api/gateway.py`: gateway-authenticated sync routes under `/api/gateway/v1`.
- `apps/control-plane/src/dirt_control/api/browser.py`: browser-authenticated hosted routes under `/api`.
- `cloud/migrations/`: dedicated Atlas migrations for the cloud database.

The local outbound gateway is a separate Python service:

- `apps/gateway/src/dirt_gateway/local.py`: collects local projections from local services and Postgres.
- `apps/gateway/src/dirt_gateway/sync.py`: enqueues and delivers projection events through local Postgres outbox tables.
- `apps/gateway/src/dirt_gateway/cloud.py`: HTTP client for cloud gateway routes.

The React frontend lives in `web-ui/`:

- `web-ui/src/routes/index.tsx`: currently contains both `HostedDashboardPage` and `LocalDashboardPage`.
- `web-ui/src/routes/wiki.tsx`: currently uses the typed API client for `/api/wiki/*`; in hosted mode that client points at `https://api.sirius-forge.com`, where the wiki routes do not exist.
- `web-ui/src/routes/__root.tsx`: owns auth bootstrap and suppresses `TopBar` on login.
- `web-ui/src/ui/TopBar.tsx`: currently owns theme application and the visible `Auto` theme label.
- `web-ui/src/api-client/client.ts`: switches API base URL with `VITE_DIRT_API_BASE_URL`.
- `web-ui/src/api-client/cloud.ts`: cloud-only TypeScript interfaces and fetch helpers used by the hosted dashboard/live routes.

Before editing TypeScript or TSX, read `docs/references/modern-idiomatic-typescript/INDEX.md`, `docs/references/tanstack-router-v1/INDEX.md`, and, for Tailwind utility work, `docs/references/tailwind-v4/INDEX.md`. Before editing cloud migrations, read `docs/database.md` and `docs/references/atlas/INDEX.md`. Before changing wiki projection behavior, read `wiki/AGENTS.md` and `apps/web/src/dirt_web/api/wiki.py`.

Do not modify `apps/tests/invariants/**`. If an invariant fails, fix the implementation.


## Plan of Work

Milestone 1 creates a reproducible baseline. Capture current local and hosted screenshots and route behavior with `agent-browser`, then record the API matrix that must converge. This prevents another migration that passes unit tests but misses visible operator behavior. The baseline must explicitly count dashboard gauges, list their names, record whether target bands/status labels are present, and record the Plant A-D card values.

Milestone 2 adds cloud projection storage and gateway collection. Add one or more cloud projection tables to `apps/control-plane/src/dirt_control/models/cloud.py`, with an Atlas migration in `cloud/migrations/`. The default shape should be a named projection document keyed by `site_id`, optional `tent_id`, `projection_type`, and optional `projection_key`, with `payload` as JSON, `source_updated_at`, `received_at`, and `etag` or content hash. Implement dashboard and plant projections first. Do not treat them as optional or deferred. The gateway should collect contract-shaped payloads for:

- grow current: equivalent to local `/api/grow/current`.
- sensors current: equivalent to local `/api/sensors/current`, including target bands and `ok` / `warn` / `crit` status.
- sensors metadata: equivalent to local `/api/sensors/metadata`.
- plants list: equivalent to local `/api/plants`.
- plant detail and moisture histories for A-D unless an implementation discovery proves the drawer should be split out after the strip; the Plant A-D dashboard strip itself is mandatory.
- system devices: equivalent to local `/api/system/devices`, including status values and notes.
- wiki tree, wiki files, and a search index sufficient for `/api/wiki/search`.

Milestone 3 exposes hosted API routes compatible with the local SPA contract. Add browser-authenticated cloud routes in `apps/control-plane/src/dirt_control/api/browser.py` for the local read-only endpoints above. The first acceptance target is that hosted `/api/sensors/current`, `/api/sensors/metadata`, `/api/sensors/history`, `/api/plants`, and `/api/grow/current` can drive the same dashboard code as local. Keep the existing hosted cloud routes if `live.tsx` or operational tooling still needs them, but the dashboard and wiki should be able to render from the local-compatible route set. Missing projections should return a clear empty or stale payload, not a forever-loading UI. All wiki routes must require browser auth.

Milestone 4 converges the frontend. Remove the separate hosted dashboard renderer or shrink it to a thin wrapper that uses the same components and query code as the local dashboard. Prefer one dashboard route that reads the local-compatible contract endpoints; in hosted mode those requests go to the cloud API because `VITE_DIRT_API_BASE_URL` is set. Remove hard-coded `CLOUD_METRIC_META` if `/api/sensors/metadata` is available from cloud. The hosted page should not be accepted until the six local gauges and Plant A-D cards are visible. After that, fix `wiki.tsx` loading and error states so a failed wiki projection displays an explicit authenticated error rather than hanging. Move theme initialization and persistence out of `TopBar` and into a root-level provider/hook that runs on every route, including `/login` and auth-loading states. Rename the visible theme control from `Auto` to `Light` / `Dark`, or implement real system auto mode if that is explicitly chosen and tested.

Milestone 5 validates and deploys. Run focused backend and frontend tests, deploy through `scripts/deploy-control-plane`, then use `agent-browser` to capture local and hosted dashboard/wiki screenshots at the same viewport. Update this ExecPlan with the screenshots, command results, deployment IDs, and any remaining accepted differences.


## Concrete Steps

Start with the required docs and current state:

    cd /home/akcom/code/dirt
    sed -n '1,220p' AGENTS.md
    sed -n '1,220p' docs/commands.md
    sed -n '1,260p' .agents/PLANS.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    sed -n '1,160p' docs/references/modern-idiomatic-typescript/INDEX.md
    sed -n '1,160p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,160p' docs/references/tailwind-v4/INDEX.md
    sed -n '1,180p' wiki/AGENTS.md

Create the baseline artifacts:

    mkdir -p debug/screenshots
    agent-browser --session hosted-ui-parity close || true
    agent-browser --session local-ui-parity close || true
    agent-browser --session hosted-ui-parity set viewport 1440 1000
    agent-browser --session local-ui-parity set viewport 1440 1000

Log in to hosted with the configured hosted admin password. Do not print secrets. If using `agent-browser auth save`, delete the temporary profile after capture:

    agent-browser auth delete dirt-hosted-ui-parity || true

Log in to local with `admin/changeme` unless `.env` says otherwise:

    agent-browser --session local-ui-parity open http://192.168.1.79:8001/
    agent-browser --session local-ui-parity snapshot -i -c

Capture baseline screenshots:

    agent-browser --session hosted-ui-parity screenshot debug/screenshots/hosted-ui-parity-dashboard-before.png
    agent-browser --session local-ui-parity screenshot debug/screenshots/local-ui-parity-dashboard-before.png
    agent-browser --session hosted-ui-parity click <wiki-button-ref>
    agent-browser --session hosted-ui-parity screenshot debug/screenshots/hosted-ui-parity-wiki-before.png
    agent-browser --session local-ui-parity click <wiki-button-ref>
    agent-browser --session local-ui-parity screenshot debug/screenshots/local-ui-parity-wiki-before.png

Add cloud projection schema:

    # Edit apps/control-plane/src/dirt_control/models/cloud.py.
    # Add migration through Atlas; do not write app-start DDL.
    atlas migrate diff hosted_ui_parity_projections --env cloud
    atlas migrate apply --env cloud --dry-run

Implement and test cloud/gateway backend work:

    uv run pytest apps/control-plane/tests apps/gateway/tests apps/shared/tests -q
    uv run pytest apps/tests/invariants/ -q
    uv run ruff check apps/control-plane apps/gateway apps/web
    uv run ruff format apps/control-plane apps/gateway apps/web --check

Implement and test frontend convergence:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Run browser acceptance locally after building the SPA served by `dirt-web`:

    agent-browser --session local-ui-parity open http://192.168.1.79:8001/
    agent-browser --session local-ui-parity screenshot debug/screenshots/local-ui-parity-dashboard-after.png
    agent-browser --session local-ui-parity click <wiki-button-ref>
    agent-browser --session local-ui-parity screenshot debug/screenshots/local-ui-parity-wiki-after.png

Deploy only through the supported flow:

    scripts/agent-fix
    scripts/deploy-control-plane

Capture hosted acceptance after deploy:

    agent-browser --session hosted-ui-parity open https://sirius-forge.com/
    agent-browser --session hosted-ui-parity screenshot debug/screenshots/hosted-ui-parity-dashboard-after.png
    agent-browser --session hosted-ui-parity click <wiki-button-ref>
    agent-browser --session hosted-ui-parity screenshot debug/screenshots/hosted-ui-parity-wiki-after.png
    agent-browser --session hosted-ui-parity click <theme-button-ref>
    agent-browser --session hosted-ui-parity screenshot debug/screenshots/hosted-ui-parity-dark-after.png


## Validation and Acceptance

Backend acceptance:

- Cloud Atlas migration applies cleanly with `atlas migrate apply --env cloud --dry-run` before production apply.
- `uv run pytest apps/control-plane/tests apps/gateway/tests apps/shared/tests -q` passes.
- `uv run pytest apps/tests/invariants/ -q` passes without modifying `apps/tests/invariants/**`.
- Cloud browser routes for `/api/grow/current`, `/api/sensors/current`, `/api/sensors/metadata`, `/api/plants`, and `/api/system/devices` return contract-compatible payloads.
- Cloud browser routes for `/api/sensors/current` include all six dashboard metrics: `temperature_f`, `humidity_pct`, `vpd_kpa`, `fan_pct`, `humidifier_intensity_pct`, and `reservoir_in`.
- Cloud browser routes for `/api/plants` include Plant A-D with current soil moisture values.
- Cloud browser routes for `/api/wiki/tree`, `/api/wiki/file`, and `/api/wiki/search` require auth and return non-empty projected data after gateway sync.

Frontend acceptance:

- `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `pnpm --dir web-ui test`, and `pnpm --dir web-ui build` pass.
- The dashboard route no longer has a separate hosted-only layout that omits local operator sections.
- Hosted dashboard shows the grow context line with day number, stage, week, light schedule, and cultivar/run label when that data has synced.
- Hosted dashboard shows six gauge cards in the same order as local: Temperature, Humidity, VPD, Fan, Humidifier, Reservoir. This is a must-pass criterion for this plan.
- Hosted gauge cards use target bands and status labels from the synced projection, not default `OK` for every metric.
- Hosted dashboard shows Plant A-D cards with current soil moisture. This is a must-pass criterion for this plan.
- Hosted dashboard shows the system device table with status values such as `OK`, `WARN`, `LISTENING`, or `OFFLINE`, not a catalog-only `LAST SEEN NEVER` table.
- Hosted wiki sidebar loads non-empty folders/files, file selection loads markdown, and search returns matches.
- Dark theme applies on login, dashboard, live, and wiki. The visible theme control no longer says `Auto` unless a real system-auto mode exists.
- Hosted assets remain private: unauthenticated signed-URL routes fail, authenticated routes return signed URLs.
- Remote commands remain PTZ-only and expire after 60 seconds. There must be no hosted fan, lights, or humidifier control in this plan.

Browser comparison acceptance:

- At viewport `1440x1000`, local and hosted dashboard screenshots have the same major sections: header grow context, nav, live/sync indicator, range switch, six gauges, history, plant strip, system table, and latest asset where available.
- At viewport `1440x1000`, local and hosted wiki screenshots both show a populated sidebar and an empty-state prompt or selected file content.
- Differences caused by sync timing are allowed only when they are explicitly labeled by the UI as gateway age, stale data, or missing projection.


## Idempotence and Recovery

Gateway projection sync must be safe to repeat. Use stable projection keys and idempotent upserts so rerunning `dirt-gateway` or replaying outbox rows replaces the same cloud projection document instead of duplicating rows.

Cloud migrations must be explicit Atlas migrations under `cloud/migrations/`. Do not add table creation to FastAPI startup. If a generated migration is unsafe for existing Railway rows, delete it before applying, fix the SQLModel default/nullability, regenerate, and record the discovery here.

If hosted wiki projection fails, keep local wiki untouched. The local `wiki/` filesystem remains the source. Hosted API should serve the last successful projection with stale metadata if possible, or a clear error if no projection exists.

If frontend convergence breaks local dashboard behavior, restore local parity before deploying. Local `dirt-web` remains the reference UI for this plan.

If production deploy fails, do not bypass `scripts/deploy-control-plane` with ad hoc `railway up`. Fix the script or service config and rerun the supported deploy flow. Local automation continues while the hosted UI is stale.

Do not revert unrelated dirty worktree files. At the time this plan was created, unrelated wiki files had local modifications. Leave them alone unless the user explicitly assigns them.


## Artifacts and Notes

Initial browser evidence from 2026-05-05:

- Hosted dashboard screenshot: `debug/screenshots/hosted-sirius-forge-dashboard.png`.
- Local dashboard screenshot: `debug/screenshots/local-dirt-web-dashboard.png`.
- Hosted wiki screenshot: `debug/screenshots/hosted-sirius-forge-wiki.png`.
- Local wiki screenshot: `debug/screenshots/local-dirt-web-wiki.png`.
- Hosted wiki request evidence: `GET https://api.sirius-forge.com/api/wiki/tree` returned `404`.
- Local wiki request evidence: `GET http://192.168.1.79:8001/api/wiki/tree` returned `200`.
- Dark-mode evidence: after clicking the theme button in both sessions, `document.documentElement.getAttribute("data-theme")` returned `"dark"`.

Add new screenshots, deployment IDs, and concise test transcripts here as implementation proceeds.


## Interfaces and Dependencies

New or changed cloud database interfaces:

- Add a projection storage model in `apps/control-plane/src/dirt_control/models/cloud.py`, likely `CloudUiProjection`, with keys for `site_id`, `tent_id`, `projection_type`, optional `projection_key`, JSON payload, source timestamp, received timestamp, and content hash.
- Add an Atlas migration under `cloud/migrations/` and update `cloud/migrations/atlas.sum`.

New or changed gateway interfaces:

- Add projection collection methods to `apps/gateway/src/dirt_gateway/local.py` through `GatewayLocalServiceBundle` or a narrowly named collaborator.
- Add new outbox event types in `apps/gateway/src/dirt_gateway/sync.py`, such as `ui_projection` or specific event types like `grow_projection`, `dashboard_projection`, `plants_projection`, `system_projection`, and `wiki_projection`.
- Add cloud client methods in `apps/gateway/src/dirt_gateway/cloud.py` for the new gateway projection route.
- Add gateway-authenticated route(s) in `apps/control-plane/src/dirt_control/api/gateway.py` to upsert projection payloads.

New or changed hosted browser interfaces:

- Add browser-authenticated cloud routes in `apps/control-plane/src/dirt_control/api/browser.py` for local-compatible read-only endpoints:
  - `GET /api/grow/current`
  - `GET /api/sensors/current`
  - `GET /api/sensors/metadata`
  - `GET /api/plants`
  - `GET /api/plants/{code}` if preserving plant drawer parity
  - `GET /api/plants/{code}/moisture` if preserving plant drawer parity
  - `GET /api/system/devices`
  - `GET /api/wiki/tree`
  - `GET /api/wiki/file`
  - `GET /api/wiki/search`

New or changed frontend interfaces:

- `web-ui/src/routes/index.tsx` should share dashboard route logic between local and hosted instead of rendering a divergent hosted dashboard.
- `web-ui/src/routes/wiki.tsx` should work in hosted mode against the cloud-compatible wiki routes and should show explicit errors for missing/stale projections.
- `web-ui/src/routes/__root.tsx` should initialize theme for every route.
- `web-ui/src/ui/TopBar.tsx` should render an honest theme control label and should not be the only component that applies `data-theme`.
- `web-ui/src/api-client/cloud.ts` may remain for hosted-only PTZ/live/sync APIs, but dashboard/wiki parity should not depend on a parallel dashboard data model.

External dependencies and services:

- Railway services: `control-plane-api`, `web-ui`, Railway Postgres, and private `dirt-assets` bucket.
- Local services: `dirt-web`, `dirt-gateway`, local Postgres.
- Browser validation tool: `agent-browser` CLI.
- Deployment command: `scripts/deploy-control-plane`.


## Revision Notes

- 2026-05-05 / Codex: Initial plan created after comparing hosted and local UI screenshots and confirming the hosted wiki 404.
