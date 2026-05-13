# Hosted Multi-Tent Web UI Migration

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the hosted site at `https://sirius-forge.com/` should be the primary operator UI for all modeled tents, not only a remote clone of the local main-tent dashboard. A user should be able to open the hosted UI away from the local network, choose a site and tent such as `homebox/main` or `homebox/breeding`, and see the best available state for that selected tent: grow context when a grow exists, current metrics when sensors exist, light schedule state, device health, recent private assets, sync freshness, and safe camera/PTZ affordances.

The old local dashboard remains a valuable reference for `homebox/main` because it has the clearest main-tent operator semantics: the six established gauges, stage-aware target/status bands, Plant A-D cards, plant detail drawers, system health, wiki navigation, and theme behavior. Those main-tent behaviors are now an acceptance fixture, not the whole product target. Hosted should match them for the main tent where the underlying data exists, while other tents must render their own scoped catalog, camera assets, schedules, and metrics without pretending they have Plant A-D or the exact main-tent gauge set.

This plan also keeps the good engineering pattern from the local SPA: typed API boundaries, generated or schema-derived frontend types where practical, Pydantic response/request DTOs, and contract tests for process/network/persistence boundaries. The exact contract mechanism for hosted browser routes is intentionally a design checkpoint in this revised plan. Since `docs/epics/typed-boundary-contracts/ExecPlan.md` has already added Pydantic DTOs and guardrails to hosted control-plane routes, the next step is to decide whether hosted browser types should be generated from the control-plane OpenAPI output, folded into `contracts/webapp-v1.yaml`, or split into a new hosted web contract. Do not force hosted multi-tent routes to mimic singleton local paths solely for parity.

This plan exists because the first hosted-control-plane implementation proved the Railway deployment, cloud API, gateway, private assets, tent-scoped catalog/metric/device/asset routes, and PTZ command loop, but the hosted dashboard still diverges from the richer local main-tent UX and the hosted wiki route still has no cloud implementation. The hosted implementation currently has a separate `HostedDashboardPage`, hand-written cloud TypeScript interfaces, cloud-specific endpoints, no hosted wiki API, hard-coded metric metadata, and limited target/status semantics. Meanwhile, later epics made multi-tent support real: the local model has scoped `site`/`tent`/`device`/`capability`/`schedule` records, `dirt2` uploads breeding-tent private assets, and capture policy is derived from tent-scoped catalog and schedule data.

The final observable result is a hosted multi-tent dashboard comparison plus boundary verification: log in to hosted, switch between `main` and `breeding`, capture dashboard/wiki screenshots with `agent-browser`, confirm the main tent retains the important local operator information, confirm non-main tents show their scoped assets and devices without leaking main-tent data, and confirm every frontend-visible hosted API route is covered by the chosen typed contract approach. Exact data timestamps may differ by gateway sync delay, but tent selection, scoped data boundaries, status semantics, private assets, and error states must be clear.


## Progress

- [x] (2026-05-05T13:20:00-06:00) Created this ExecPlan from the hosted/local UI parity review and the captured `agent-browser` evidence.
- [x] (2026-05-05T13:55:00-06:00) Reframed the plan as a migration to hosted web as the canonical UI, with local UI as the temporary UX reference/fallback and OpenAPI-generated contracts as a core implementation requirement.
- [x] (2026-05-13T10:25:00-06:00) Rewrote the early milestones around hosted multi-tent visibility. Main-tent parity is now a regression fixture, not a requirement that every tent mimic `homebox/main`. Contract strategy is explicitly deferred to a design checkpoint before implementation.
- [ ] Milestone 1: establish a repeatable hosted multi-tent baseline and API matrix.
- [ ] Milestone 2: decide and document the hosted browser contract strategy before changing route shapes or frontend clients.
- [ ] Milestone 3: fill only the missing cloud projection gaps needed for tent-scoped dashboard envelopes, main-tent plant summaries, and wiki.
- [ ] Milestone 4: expose hosted API routes that satisfy the chosen typed contract and preserve scoped site/tent boundaries.
- [ ] Milestone 5: converge the frontend onto tent-scoped hosted components, keep main-tent parity where applicable, and fix theme ownership.
- [ ] Milestone 6: deploy through `scripts/deploy-control-plane` and capture multi-tent acceptance evidence.
- [ ] Milestone 7: after hosted parity is accepted, deprecate and remove or shrink the local browser-facing UI/API surface.


## Surprises & Discoveries

- Observation: Hosted wiki currently calls the cloud API for local wiki routes and gets `404`.
  Evidence: `agent-browser` network output showed `GET https://api.sirius-forge.com/api/wiki/tree` returning `404`, while `GET http://192.168.1.79:8001/api/wiki/tree` returned `200` and rendered the wiki sidebar.

- Observation: The hosted dashboard is not a renderer of the local dashboard contract; it is a separate cloud-specific dashboard.
  Evidence: `web-ui/src/routes/index.tsx` chooses `HostedDashboardPage` when `isHostedApiMode` is true. The hosted path reads `/api/tents/{tent_id}/metrics/current`, `/api/tents/{tent_id}/devices`, and cloud-specific TypeScript interfaces from `web-ui/src/api-client/cloud.ts`, while the local path reads `/api/grow/current`, `/api/sensors/current`, `/api/sensors/metadata`, `/api/plants`, and `/api/system/devices`.

- Observation: The hosted dashboard and sync APIs are not currently described by the OpenAPI contract used by the SPA.
  Evidence: Local SPA routes use `contracts/webapp-v1.yaml`, generated schema files under `web-ui/src/api-client/generated/`, and `createDirtApiClient()`. Hosted dashboard code imports hand-written interfaces from `web-ui/src/api-client/cloud.ts` instead of generated OpenAPI types.

- Observation: The cloud schema stores raw-ish latest metrics and rollups, but not the local UI envelopes that encode grow-stage target bands and status labels.
  Evidence: `apps/control-plane/src/dirt_control/models/cloud.py` has `CloudLatestMetric` and `CloudMetricRollup`, but no table for the contract-shaped `SensorsCurrent`, grow context, plants response, or system device status response.

- Observation: Device catalog sync does not currently populate the local status table semantics.
  Evidence: The hosted screenshot showed devices with `LAST SEEN` as `NEVER`, while the local screenshot showed `OK` and `OFFLINE` status values from `/api/system/devices`.

- Observation: Dark mode works after login when the `TopBar` button is clicked, but theme application is not owned by the root app shell.
  Evidence: `agent-browser` click on the theme button made `document.documentElement.getAttribute("data-theme")` return `"dark"` in both local and hosted sessions. Login and auth-loading screens do not mount `TopBar`, and the visible button label is `Auto` even though the behavior is a manual light/dark toggle.

- Observation: Hosted admin auth now uses only `DIRT_CLOUD_ADMIN_USERNAME` plus `DIRT_CLOUD_ADMIN_PASSWORD_HASH`.
  Evidence: The deploy script no longer derives hosted credentials from local `AUTH_USERNAME` / `AUTH_PASSWORD`. Do not reintroduce plaintext hosted password variables while implementing this plan.

- Observation: Multi-tent support is no longer a future prerequisite; it is already part of the production model.
  Evidence: `docs/epics/multi-tent-controller/ExecPlan.md` records scoped `site`, `tent`, `device`, `capability`, `growrun`, `schedule`, `snapshot`, and `command` records. `docs/epics/multi-tent-controller/LegacyCompatibilityRetirementExecPlan.md` records that current sensor, plant, snapshot, and schedule reads accept explicit `site_id` / `tent_id` scope and guard against cross-tent leakage.

- Observation: The hosted UI already contains a tent selector and cloud-specific tent-scoped routes.
  Evidence: `web-ui/src/routes/index.tsx` initializes `selectedSiteId` and `selectedTentId`, calls `/api/sites`, `/api/tents?site_id=...`, `/api/tents/{tent_id}/metrics/current`, `/api/tents/{tent_id}/devices`, `/api/tents/{tent_id}/lights/schedules`, and `/api/tents/{tent_id}/assets/latest`, and renders a hosted-only dashboard when `isHostedApiMode` is true.

- Observation: Breeding-tent imagery now arrives through a camera-edge path, not the main gateway's default-tent asset projection.
  Evidence: `docs/epics/camera-edge/ExecPlan.md` records that `dirt2` runs `dirt-camera-agent`, uploads private assets under `homebox/breeding`, and verified `/api/tents/breeding/assets/latest` with a signed hosted asset. `docs/epics/unified-ptz-capture-execplan.md` records that both mainbox and camera-only hosts use `CameraCapturePublisher` and that `dirt2` capture policy is derived from hosted camera/schedule catalog.

- Observation: Typed boundary work partially superseded the old "add everything to `contracts/webapp-v1.yaml` first" milestone.
  Evidence: `docs/epics/typed-boundary-contracts/ExecPlan.md` added shared Pydantic DTOs for gateway/control-plane protocols and local Pydantic response models for hosted browser API routes, while also recording the decision that hosted browser response DTOs may stay local to `apps/control-plane` unless the shape is also a shared gateway/control-plane wire contract.


## Decision Log

- Decision: Implement hosted visibility through outbound sync and cloud-owned read models, not by exposing the local `dirt-web` process or mirroring the local database.
  Rationale: The original hosted-control-plane boundary remains correct: the local box owns hardware and the local database; the cloud API serves selected operator state. Hosted multi-tent visibility needs scoped cloud data and a few richer display envelopes, not inbound access to the local network.
  Date/Author: 2026-05-05 / Codex

- Decision: Treat the hosted web app as the canonical future UI and the local UI as a temporary reference/fallback during migration.
  Rationale: The user clarified that the long-term goal is web-based operation and eventual removal of the local UI once hosted reaches UX parity. The implementation should preserve the local UX, not preserve a permanent dual-stack local/hosted architecture.
  Date/Author: 2026-05-05 / Codex

- Decision: Migrate the local typed-boundary discipline to the hosted web API.
  Rationale: The important pattern is schema-backed contracts, generated or schema-derived frontend/backend types, Pydantic DTOs, and contract tests. The hosted API should not continue with unchecked hand-written TypeScript interfaces and undocumented cloud-only shapes, but the exact hosted browser contract mechanism must be chosen after the typed-boundary work already completed.
  Date/Author: 2026-05-05 / Codex

- Decision: Make the hosted cloud API provide typed read-only routes for tent-scoped dashboard and wiki data.
  Rationale: The local SPA already has tested components and OpenAPI-generated types for main-tent dashboard/wiki behavior. The hosted successor can reuse components and evolve shapes, but multi-tent hosted routes should stay explicitly scoped and should be covered by the chosen typed contract/client path before the React app depends on them.
  Date/Author: 2026-05-05 / Codex

- Decision: Keep V1 hosted remote commands PTZ-only.
  Rationale: UI parity means display parity, not adding remote fan, light, or humidifier control. The existing safety decision from `docs/epics/hosted-website-control-plane/ExecPlan.md` still applies.
  Date/Author: 2026-05-05 / Codex

- Decision: Use JSONB projection rows selectively for display-shaped payloads that are not naturally represented by existing cloud tables.
  Rationale: UI display envelopes are read by primary key and replaced wholesale by the gateway. They are snapshots, not analytical records. Keeping only genuinely display-specific envelopes as named projection documents avoids duplicating every local contract model into cloud SQL columns, while normalized catalog/metric/schedule/asset tables remain the primary source for tent-scoped hosted views.
  Date/Author: 2026-05-05 / Codex

- Decision: Sync wiki as an authenticated read-only cloud projection.
  Rationale: The hosted UI should not hide Wiki if the local operator experience includes it. Wiki contents are operational notes, so hosted wiki routes must require browser auth and must not become static public files.
  Date/Author: 2026-05-05 / Codex

- Decision: Move theme application to the root app shell and keep the visible control honest.
  Rationale: Theme should apply on login, auth-loading, dashboard, live, and wiki. The current `Auto` label is misleading because there is no system-preference auto mode.
  Date/Author: 2026-05-05 / Codex

- Decision: Prioritize the main-tent dashboard fixture and multi-tent scoping over less central polish.
  Rationale: The user explicitly identified the local dashboard information density and plants strip as important, but later clarified that hosted should also let operators look at other tents. The implementation should first make `homebox/main` preserve the six gauge cards, target/status semantics, sparklines, and Plant A-D strip, while ensuring `homebox/breeding` and future tents render scoped state without main-tent leakage.
  Date/Author: 2026-05-05 / Codex

- Decision: Include local UI deprecation as a final milestone, not as part of the initial parity implementation.
  Rationale: Hosted parity should be proven before removing the working local UI. Once proven, local browser routes and static serving can be retired deliberately while preserving local services needed by hardware loops, gateway projection, PTZ execution, and observability.
  Date/Author: 2026-05-05 / Codex

- Decision: Treat `homebox/main` local-dashboard parity as a regression fixture, not as the target shape for every hosted tent.
  Rationale: `homebox/main` still needs the six local gauges, target/status semantics, Plant A-D strip, plant details, and system health because those are useful operator affordances. Other tents may have different sensors, assets, plants, or no active grow run. Exact parity across all tents would hide the multi-tent model rather than serving it.
  Date/Author: 2026-05-13 / Codex

- Decision: Make tent-scoped hosted routes the primary implementation direction unless the contract design checkpoint proves a better shape.
  Rationale: The hosted control plane and frontend already expose `/api/tents/{tent_id}/...` routes, which map naturally to the scoped catalog and avoid singleton local route assumptions. The contract discussion should decide how to type these routes, not whether hosted should regress to default-main singleton URLs.
  Date/Author: 2026-05-13 / Codex

- Decision: Add UI projection storage only for display envelopes that cannot be derived cleanly from the existing cloud tables and typed gateway sync.
  Rationale: Since the cloud schema already stores sites, tents, catalog devices, latest metrics, rollups, schedules, assets, commands, and typed gateway payloads, a broad `CloudUiProjection` table would duplicate storage. Projection documents remain appropriate for UI-specific envelopes such as stage-aware metric targets/statuses, main-tent plant summaries, and wiki tree/file/search data.
  Date/Author: 2026-05-13 / Codex

- Decision: Hold the hosted browser contract shape for a follow-up design conversation before implementation.
  Rationale: Three viable paths now exist: generate a hosted browser client from control-plane FastAPI OpenAPI, extend `contracts/webapp-v1.yaml` with hosted tent-scoped routes, or create a separate hosted web contract. Choosing this affects route naming, generated artifacts, and long-term local UI deprecation, so it should be explicit before code work.
  Date/Author: 2026-05-13 / Codex


## Outcomes & Retrospective

Not yet implemented. Update this section after each milestone with what changed, what remained different between local and hosted, and any follow-up work that should be split out of this parity plan.


## Outstanding Questions

- Question: Should hosted browser frontend types be generated from the control-plane FastAPI OpenAPI output, folded into `contracts/webapp-v1.yaml`, or described by a new hosted web contract?
  Current thesis: Decide this before implementation. The old thesis, "put every hosted route into `contracts/webapp-v1.yaml` and mimic local singleton routes," is no longer obviously correct after typed-boundary work and the hosted tent-scoped route shape.

- Question: Which hosted dashboard routes should be canonical for multi-tent operation?
  Current thesis: Prefer explicit tent-scoped hosted routes such as `/api/tents/{tent_id}/metrics/current`, `/api/tents/{tent_id}/devices`, `/api/tents/{tent_id}/lights/schedules`, and `/api/tents/{tent_id}/assets/latest`. Add or adapt routes for missing UI envelopes instead of forcing every hosted view through default-main local paths such as `/api/sensors/current`.

- Question: How much plant detail parity belongs in the first pass?
  Current thesis: Plant A-D dashboard cards and plant detail/moisture history are mandatory for `homebox/main` if the local data has synced. Non-main tents should render plants only when scoped plant/run data exists; a breeding or clones tent must not be forced into the A-D shape.

- Question: When can the local browser UI be removed?
  Current thesis: Only after hosted browser screenshots, typed-boundary tests, gateway sync evidence, private-asset checks, multi-tent scope checks, and at least one real operator review confirm that hosted is a satisfactory replacement. The local hardware and gateway services remain; only the local browser-facing SPA/API surface is retired.

- Question: Should the hosted wiki projection include all wiki files or only an allowlist?
  Current thesis: Sync the authenticated read-only wiki needed by the operator UI, but keep it behind hosted browser auth and private cloud storage/API routes. If sensitive local-only notes are identified, add an explicit exclusion mechanism before deployment.

- Question: Should hosted PTZ controls target only `obsbot-main`, or should the UI grow a per-tent camera control model?
  Current thesis: Keep remote commands PTZ-only, but do not hard-code every hosted command UI to `obsbot-main` indefinitely. For tents with camera assets but no safe command target, show read-only imagery and an explicit disabled/control-unavailable state.


## Context and Orientation

The repository currently has a local Python web service and a hosted cloud control plane. During this migration, the local UI is the UX reference and fallback, while the hosted cloud control plane becomes the canonical backend for the React app.

Local `dirt-web` runs on the homebox and serves the local SPA plus local API routes. Important local API files are:

- `apps/web/src/dirt_web/api/grow.py`: serves `/api/grow/current`.
- `apps/web/src/dirt_web/api/sensors.py`: serves `/api/sensors/current`, `/api/sensors/history`, and `/api/sensors/metadata`.
- `apps/web/src/dirt_web/api/plants.py`: serves `/api/plants`, `/api/plants/{code}`, and `/api/plants/{code}/moisture`.
- `apps/web/src/dirt_web/api/system.py`: serves `/api/system/devices`.
- `apps/web/src/dirt_web/api/wiki.py`: serves `/api/wiki/tree`, `/api/wiki/file`, and `/api/wiki/search`.
- `contracts/webapp-v1.yaml`: currently defines the local SPA API contract and generated TypeScript/Pydantic shapes. It may become the hosted web contract too, but this revised plan requires an explicit contract strategy checkpoint before deciding whether hosted tent-scoped routes live here, in generated control-plane OpenAPI artifacts, or in a separate hosted web contract.

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

- `web-ui/src/routes/index.tsx`: currently contains both `HostedDashboardPage` and `LocalDashboardPage`. Hosted mode already has a site/tent selector and calls cloud-specific tent-scoped routes. This is the right product direction, but the current implementation still hard-codes metric metadata, omits main-tent plant parity, and uses hand-written cloud TypeScript interfaces.
- `web-ui/src/routes/wiki.tsx`: currently uses the typed API client for `/api/wiki/*`; in hosted mode that client points at `https://api.sirius-forge.com`, where the wiki routes do not exist.
- `web-ui/src/routes/__root.tsx`: owns auth bootstrap and suppresses `TopBar` on login.
- `web-ui/src/ui/TopBar.tsx`: currently owns theme application and the visible `Auto` theme label.
- `web-ui/src/api-client/client.ts`: switches API base URL with `VITE_DIRT_API_BASE_URL`.
- `web-ui/src/api-client/cloud.ts`: cloud-only TypeScript interfaces and fetch helpers used by the hosted dashboard/live routes. Dashboard, plants, wiki, sync status, signed assets, and hosted command intent should migrate away from unverified hand-written frontend types and toward the chosen contract strategy. This file may remain temporarily for live/PTZ work until generated or schema-derived hosted browser types exist.

Recent epics changed the baseline:

- `docs/epics/multi-tent-controller/ExecPlan.md` and `docs/epics/multi-tent-controller/LegacyCompatibilityRetirementExecPlan.md`: scoped site/tent/device/capability/schedule/growrun ownership exists, and current read paths have explicit scope guardrails.
- `docs/epics/camera-edge/ExecPlan.md`: `dirt2` captures and uploads breeding-tent camera assets directly to hosted storage as `homebox/breeding`.
- `docs/epics/unified-ptz-capture-execplan.md`: mainbox and `dirt2` capture use shared publisher infrastructure, and camera capture policy is derived from synced camera and lights catalog.
- `docs/epics/typed-boundary-contracts/ExecPlan.md`: hosted gateway/control-plane protocols and hosted browser API responses now have Pydantic DTO coverage and guardrails. This does not yet give the React app generated hosted browser types.

Before editing TypeScript or TSX, read `docs/references/modern-idiomatic-typescript/INDEX.md`, `docs/references/tanstack-router-v1/INDEX.md`, and, for Tailwind utility work, `docs/references/tailwind-v4/INDEX.md`. Before editing cloud migrations, read `docs/database.md` and `docs/references/atlas/INDEX.md`. Before changing wiki projection behavior, read `wiki/AGENTS.md` and `apps/web/src/dirt_web/api/wiki.py`.

Do not modify `apps/tests/invariants/**`. If an invariant fails, fix the implementation.


## Plan of Work

Milestone 1 creates a reproducible hosted multi-tent baseline. Capture current hosted screenshots and route behavior for at least `homebox/main` and `homebox/breeding` with `agent-browser`, then record the API matrix for each selected tent. For `main`, also capture the local dashboard as the parity fixture. The baseline must record: selected site/tent, visible gauges, target/status semantics, plant cards or explicit no-plant state, lights schedule panel, device rows, latest asset panel, sync freshness, PTZ controls or disabled state, and wiki behavior. Also record which frontend calls use generated types and which still use `web-ui/src/api-client/cloud.ts`.

Milestone 2 is a contract strategy checkpoint. Before changing route shapes or frontend clients, choose one hosted browser typing path and record it in this ExecPlan:

- generate a hosted browser client from `apps/control-plane` FastAPI OpenAPI output;
- extend `contracts/webapp-v1.yaml` with hosted tent-scoped routes;
- create a separate hosted web contract and generated client; or
- keep a short-lived hand-written cloud client only behind explicit guardrail tests while a generated path is built.

The decision must preserve the boundary-contract rule from `docs/rules/boundary-contracts.md`, respect the typed-boundary work already completed, and avoid forcing multi-tent hosted routes into singleton local names just to reuse the local client. This milestone should end with a small API/client matrix, not a broad implementation.

Milestone 3 fills missing cloud display envelopes. Prefer deriving hosted UI responses from existing typed cloud tables and gateway sync: `CloudSite`, `CloudTent`, `CloudDevice`, `CloudLatestMetric`, `CloudMetricRollup`, `CloudSchedule`, `CloudAsset`, and `CloudCommand`. Add projection storage only where a display envelope cannot be derived cleanly. Likely projection candidates are:

- main-tent dashboard metric metadata and stage-aware target/status bands;
- main-tent Plant A-D strip/detail/moisture summaries;
- current grow/run context for each tent that has a grow;
- read-only wiki tree, file, and search data.

Do not build a broad local-database mirror in cloud. Do not require non-main tents to have Plant A-D data or all six main-tent metrics.

Milestone 4 exposes hosted API routes that satisfy the chosen typed contract and scoped boundary. Existing tent-scoped routes may remain canonical if the contract checkpoint confirms them. Add missing browser-authenticated cloud routes only where needed for dashboard envelopes, main-tent plant summaries, wiki, sync status, assets, and safe PTZ command intent. Missing projections should return a clear empty, stale, unavailable, or not-applicable payload, not a forever-loading UI. Wiki routes must require browser auth.

Milestone 5 converges the frontend onto tent-scoped hosted components. Preserve the site/tent selector, and make the selected tent drive all dashboard queries and visible sections. For `homebox/main`, the hosted dashboard should show the six established local gauges, target/status semantics, Plant A-D cards, plant detail where implemented, grow context, system/device health, latest asset, and sync freshness. For non-main tents, the dashboard should show scoped metrics/assets/devices/schedules that exist and render professional empty states for missing plants, missing metrics, or unavailable controls. Remove or replace hard-coded `CLOUD_METRIC_META` once hosted metric metadata is available through the chosen contract. Fix `wiki.tsx` loading/error states and move theme initialization/persistence out of `TopBar` into a root-level provider/hook that runs on every route, including `/login` and auth-loading states. Rename the visible theme control from `Auto` to `Light` / `Dark`, or implement real system auto mode if that is explicitly chosen and tested.

Milestone 6 validates and deploys. Run focused backend and frontend tests, deploy through `scripts/deploy-control-plane`, then use `agent-browser` to capture local and hosted dashboard/wiki screenshots at the same viewport. Update this ExecPlan with the screenshots, command results, deployment IDs, and any remaining accepted differences.

Milestone 7 deprecates the local browser UI after hosted acceptance. Identify which `apps/web/src/dirt_web/api/*` routes and local static-serving paths exist only for the browser SPA, which local APIs are still needed by hardware services or gateway projection, and which frontend dev/test fixtures should remain. Remove or disable only the browser-facing local UI surface after the hosted UI is accepted. Keep local services needed by `dirt-hwd`, `dirt-gateway`, camera/PTZ execution, observability, and tests.


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
    agent-browser --session hosted-multitent close || true
    agent-browser --session local-main-fixture close || true
    agent-browser --session hosted-multitent set viewport 1440 1000
    agent-browser --session local-main-fixture set viewport 1440 1000

Log in to hosted with the configured hosted admin password. Do not print secrets. If using `agent-browser auth save`, delete the temporary profile after capture:

    agent-browser auth delete dirt-hosted-multitent || true

Log in to local with `admin/changeme` unless `.env` says otherwise:

    agent-browser --session local-main-fixture open http://192.168.1.79:8001/
    agent-browser --session local-main-fixture snapshot -i -c

Capture baseline screenshots:

    agent-browser --session hosted-multitent open https://sirius-forge.com/
    agent-browser --session hosted-multitent screenshot debug/screenshots/hosted-main-dashboard-before.png
    # Switch the hosted tent selector to breeding.
    agent-browser --session hosted-multitent screenshot debug/screenshots/hosted-breeding-dashboard-before.png
    agent-browser --session local-main-fixture screenshot debug/screenshots/local-main-dashboard-before.png
    agent-browser --session hosted-multitent click <wiki-button-ref>
    agent-browser --session hosted-multitent screenshot debug/screenshots/hosted-wiki-before.png
    agent-browser --session local-main-fixture click <wiki-button-ref>
    agent-browser --session local-main-fixture screenshot debug/screenshots/local-wiki-before.png

Decide the hosted browser contract strategy before consuming new hosted API shapes from the frontend:

    rg -n "response_model=|/tents/|/sync/status|/assets/.*/signed-url|/commands|/wiki/tree" apps/control-plane/src/dirt_control/api contracts web-ui/src/api-client web-ui/src/routes
    rg -n "cloudGet<|CloudMetric|CloudAsset|CloudCommand|CLOUD_METRIC_META" web-ui/src

Expected result:

    # A short matrix recorded in this ExecPlan that says which hosted browser
    # routes are already Pydantic response-model backed, which are consumed by
    # hand-written frontend types, and which generated contract path will own
    # each route before implementation proceeds.

Add cloud display projections only if the contract strategy and API matrix prove they are needed:

    # Edit apps/control-plane/src/dirt_control/models/cloud.py.
    # Add Atlas migrations only for missing display envelopes that cannot be
    # derived from existing cloud tables. Do not write app-start DDL.
    atlas migrate diff hosted_multitent_display_envelopes --env cloud
    atlas migrate apply --env cloud --dry-run

Implement and test cloud/gateway backend work:

    uv run pytest apps/control-plane/tests apps/web/tests apps/gateway/tests apps/shared/tests -q
    uv run pytest apps/tests/invariants/ -q
    uv run ruff check apps/control-plane apps/gateway apps/web
    uv run ruff format apps/control-plane apps/gateway apps/web --check

Implement and test frontend convergence:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Run browser acceptance locally after building the SPA served by `dirt-web`:

    agent-browser --session local-main-fixture open http://192.168.1.79:8001/
    agent-browser --session local-main-fixture screenshot debug/screenshots/local-main-dashboard-after.png
    agent-browser --session local-main-fixture click <wiki-button-ref>
    agent-browser --session local-main-fixture screenshot debug/screenshots/local-wiki-after.png

Deploy only through the supported flow:

    scripts/agent-fix
    scripts/deploy-control-plane

Capture hosted acceptance after deploy:

    agent-browser --session hosted-multitent open https://sirius-forge.com/
    agent-browser --session hosted-multitent screenshot debug/screenshots/hosted-main-dashboard-after.png
    # Switch the hosted tent selector to breeding.
    agent-browser --session hosted-multitent screenshot debug/screenshots/hosted-breeding-dashboard-after.png
    agent-browser --session hosted-multitent click <wiki-button-ref>
    agent-browser --session hosted-multitent screenshot debug/screenshots/hosted-wiki-after.png
    agent-browser --session hosted-multitent click <theme-button-ref>
    agent-browser --session hosted-multitent screenshot debug/screenshots/hosted-dark-after.png


## Validation and Acceptance

Backend acceptance:

- Cloud Atlas migration applies cleanly with `atlas migrate apply --env cloud --dry-run` before production apply.
- The chosen hosted browser contract strategy is recorded in this ExecPlan before route/client implementation. If `contracts/webapp-v1.yaml` is the chosen path, generated TypeScript and Pydantic contract artifacts are refreshed through `scripts/gen-contract`. If control-plane OpenAPI generation or a separate hosted contract is chosen, the exact generation command and artifacts are recorded here before frontend migration.
- `uv run pytest apps/control-plane/tests apps/web/tests apps/gateway/tests apps/shared/tests -q` passes.
- Focused boundary or contract tests prove hosted frontend-visible routes satisfy typed schemas for tent catalog, current metrics, metric history, light schedules, devices, assets, sync status, wiki, main-tent plants where applicable, and PTZ command intent.
- `uv run pytest apps/tests/invariants/ -q` passes without modifying `apps/tests/invariants/**`.
- Hosted browser routes preserve scoped isolation: requesting `homebox/breeding` does not leak main-tent plants, snapshots, or metric history.
- Hosted main-tent routes or display envelopes include the six established dashboard metrics when data has synced: `temperature_f`, `humidity_pct`, `vpd_kpa`, `fan_pct`, `humidifier_intensity_pct`, and `reservoir_in`.
- Hosted main-tent routes or display envelopes include Plant A-D with current soil moisture values when data has synced. Non-main tent routes return scoped plant data only if it exists, or an explicit no-plants/not-applicable payload.
- Hosted tent asset routes return recent private assets for both main and breeding when those assets have synced or uploaded.
- Cloud browser routes for `/api/wiki/tree`, `/api/wiki/file`, and `/api/wiki/search` require auth and return non-empty projected data after gateway sync.

Frontend acceptance:

- `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `pnpm --dir web-ui test`, and `pnpm --dir web-ui build` pass.
- The hosted dashboard is tent-scoped end to end: changing the tent selector changes metrics, assets, devices, schedules, and control affordances without stale main-tent sections.
- Hosted dashboard, plants, wiki, sync status, signed assets, and hosted PTZ command intent use the chosen typed contract/client path rather than unchecked hand-written cloud TypeScript interfaces, except for any explicitly documented temporary compatibility shim guarded by tests.
- Hosted main-tent dashboard shows the grow context line with day number, stage, week, light schedule, and cultivar/run label when that data has synced.
- Hosted main-tent dashboard shows six gauge cards in the same order as local: Temperature, Humidity, VPD, Fan, Humidifier, Reservoir. This is a must-pass criterion for the main-tent parity fixture, not for every tent.
- Hosted gauge cards use target bands and status labels from synced or derived display envelopes when available, not default `OK` for every metric.
- Hosted main-tent dashboard shows Plant A-D cards with current soil moisture. This is a must-pass criterion for the main-tent parity fixture. Non-main tents show scoped plant data when present or a clear empty/not-applicable state.
- Hosted dashboard shows scoped device health with useful status/freshness semantics, not a catalog-only `LAST SEEN NEVER` table.
- Hosted breeding dashboard shows recent private breeding-tent imagery from `/api/tents/breeding/assets/latest` when available.
- Hosted wiki sidebar loads non-empty folders/files, file selection loads markdown, and search returns matches.
- Dark theme applies on login, dashboard, live, and wiki. The visible theme control no longer says `Auto` unless a real system-auto mode exists.
- Hosted assets remain private: unauthenticated signed-URL routes fail, authenticated routes return signed URLs.
- Remote commands remain PTZ-only and expire after 60 seconds. There must be no hosted fan, lights, or humidifier control in this plan.

Browser comparison acceptance:

- At viewport `1440x1000`, local main-tent and hosted main-tent dashboard screenshots have the same major operator sections where data has synced: header grow context, nav, live/sync indicator, range switch, six gauges, history, plant strip, system table/device health, and latest asset where available.
- At viewport `1440x1000`, hosted breeding dashboard screenshot shows the selected breeding tent, sync status, light schedule, scoped devices, recent breeding asset if available, and professional empty states for missing metrics/plants/controls.
- At viewport `1440x1000`, local and hosted wiki screenshots both show a populated sidebar and an empty-state prompt or selected file content.
- Differences caused by sync timing are allowed only when they are explicitly labeled by the UI as gateway age, stale data, or missing projection.
- The local UI remains usable until hosted parity is accepted. Local UI deprecation happens only after the hosted screenshots and contract tests pass.


## Idempotence and Recovery

Gateway projection sync must be safe to repeat. Use stable projection keys and idempotent upserts so rerunning `dirt-gateway` or replaying outbox rows replaces the same cloud projection document instead of duplicating rows.

Cloud migrations must be explicit Atlas migrations under `cloud/migrations/`. Do not add table creation to FastAPI startup. If a generated migration is unsafe for existing Railway rows, delete it before applying, fix the SQLModel default/nullability, regenerate, and record the discovery here.

If hosted wiki projection fails, keep local wiki untouched. The local `wiki/` filesystem remains the source. Hosted API should serve the last successful projection with stale metadata if possible, or a clear error if no projection exists.

If frontend convergence breaks local dashboard behavior before hosted is accepted, restore local parity before deploying. Local `dirt-web` remains the reference UI and fallback during this plan. After hosted is accepted, local browser UI removal should be done in a dedicated milestone with its own validation, not as an incidental cleanup.

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

- Prefer existing normalized cloud tables for hosted dashboard data: `CloudSite`, `CloudTent`, `CloudDevice`, `CloudLatestMetric`, `CloudMetricRollup`, `CloudSchedule`, `CloudAsset`, `CloudCommand`, and `CloudAuditEvent`.
- Add a projection storage model in `apps/control-plane/src/dirt_control/models/cloud.py` only for missing display envelopes that cannot be derived cleanly from existing cloud state. Likely candidates are `dashboard_metric_metadata`, `metric_status_bands`, `main_plant_summaries`, and `wiki` projections. If added, key rows by `site_id`, optional `tent_id`, `projection_type`, optional `projection_key`, JSON payload, source timestamp, received timestamp, and content hash.
- Add Atlas migrations under `cloud/migrations/` and update `cloud/migrations/atlas.sum` only for actual schema additions. Do not create app-start DDL.

New or changed gateway interfaces:

- Reuse existing typed gateway sync for catalog/latest metrics/rollups/assets/commands where it already supplies hosted state.
- Add projection collection methods to `apps/gateway/src/dirt_gateway/local.py` through `GatewayLocalServiceBundle` or a narrowly named collaborator only for the display envelopes identified in Milestone 3.
- Add new typed outbox event types in `apps/gateway/src/dirt_gateway/sync.py` only for those envelopes, such as `display_projection` or specific event types like `dashboard_metadata_projection`, `plants_projection`, and `wiki_projection`.
- Add cloud client methods in `apps/gateway/src/dirt_gateway/cloud.py` and gateway-authenticated routes in `apps/control-plane/src/dirt_control/api/gateway.py` for any new projection payloads. These must use Pydantic DTOs per `docs/rules/boundary-contracts.md`.

New or changed hosted browser interfaces:

- First decide the hosted browser contract strategy: control-plane OpenAPI client generation, `contracts/webapp-v1.yaml`, a separate hosted web contract, or a short-lived tested shim. Record exact generation commands and artifact paths in this plan before implementation.
- The typed browser surface must cover tent catalog, tent state, current metrics, metric history, light schedules, devices, assets, sync status, wiki, main-tent plant data where applicable, and PTZ command intent.
- Add browser-authenticated cloud routes in `apps/control-plane/src/dirt_control/api/browser.py` for contract-backed read-only endpoints:
  - `GET /api/sites`
  - `GET /api/tents`
  - `GET /api/tents/{tent_id}/state` or the chosen grow/state replacement
  - `GET /api/tents/{tent_id}/metrics/current`
  - `GET /api/tents/{tent_id}/metrics/history`
  - `GET /api/tents/{tent_id}/metrics/metadata` or equivalent display metadata route if needed
  - `GET /api/tents/{tent_id}/lights/schedules`
  - `GET /api/tents/{tent_id}/devices`
  - `GET /api/tents/{tent_id}/assets/latest`
  - main-tent or scoped plant routes if preserving plant strip/drawer parity
  - `GET /api/wiki/tree`
  - `GET /api/wiki/file`
  - `GET /api/wiki/search`
  - hosted sync status and asset signed-URL routes consumed by the SPA
  - hosted PTZ-only command creation/list/fetch routes consumed by the SPA

New or changed frontend interfaces:

- `web-ui/src/routes/index.tsx` should keep hosted site/tent selection as a first-class control and make every hosted dashboard section depend on the selected scope.
- `web-ui/src/routes/index.tsx` should share reusable dashboard components between local and hosted where useful, but it should not force non-main hosted tents into the local main-tent shape.
- `web-ui/src/routes/wiki.tsx` should work in hosted mode against cloud-compatible authenticated wiki routes and should show explicit errors for missing/stale projections.
- `web-ui/src/routes/__root.tsx` should initialize theme for every route.
- `web-ui/src/ui/TopBar.tsx` should render an honest theme control label and should not be the only component that applies `data-theme`.
- `web-ui/src/api-client/cloud.ts` should shrink or disappear as hosted routes move into the chosen typed contract/client path. Any remaining hand-written cloud client code must be documented as temporary and covered by guardrail tests.

External dependencies and services:

- Railway services: `control-plane-api`, `web-ui`, Railway Postgres, and private `dirt-assets` bucket.
- Local services: `dirt-web`, `dirt-gateway`, local Postgres.
- Browser validation tool: `agent-browser` CLI.
- Deployment command: `scripts/deploy-control-plane`.

Local UI deprecation interfaces:

- Inventory `apps/web/src/dirt_web/api/*` and separate browser-only routes from routes still needed by local services, gateway projection, tests, or operator emergency fallback.
- Remove local static SPA serving only after hosted acceptance. Do not remove local hardware services, gateway projection code, PTZ execution code, observability, or shared service APIs needed outside the browser UI.


## Revision Notes

- 2026-05-05 / Codex: Initial plan created after comparing hosted and local UI screenshots and confirming the hosted wiki 404.
- 2026-05-05 / Codex: Reframed the plan around hosted web as the canonical future UI, OpenAPI-generated contracts as a core requirement, and local UI removal as a post-parity milestone.
- 2026-05-13 / Codex: Rewrote the early milestones around hosted multi-tent operation. `homebox/main` local parity is now a regression fixture, `homebox/breeding` hosted visibility is first-class, broad UI projection storage is no longer assumed, and hosted browser contract strategy is deferred to an explicit design checkpoint before implementation.
