# Backend-owned metric presentation config

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

The hosted dashboard currently sends too much rollup history to the cloud and makes the frontend decide which metrics are product-facing. After this change, the backend owns the metric presentation registry: which stored metrics are synced for history, which public metric names the browser may request, how dashboard metrics are grouped and ordered, labels, units, y-axis bounds, and value formatting. The frontend renders that contract and keeps only local visual styling such as CSS classes and chart interactions.

The user-visible result is that hosted sparkline payloads shrink because raw and diagnostic streams are not synced for dashboard history, while the dashboard keeps showing the same useful cards and history groups. A human can observe this by running the gateway rollup projection and seeing only presentation-enabled metrics, calling the browser presentation endpoint and seeing dashboard groups from the backend, then opening the hosted dashboard and seeing it render without `CURRENT_METRIC_META` or `HISTORY_METRIC_GROUPS` in `web-ui/src/routes/index.tsx`.

This is a direct cutover. Do not add frontend fallback lists, compatibility shims, or duplicate registries.

## Progress

- [x] (2026-05-31 21:35Z) Audited the hosted dashboard frontend and backend rollup/display paths.
- [x] (2026-05-31 21:50Z) Wrote the initial ExecPlan with a backend-owned registry, direct frontend cutover, and validation strategy.
- [ ] Implement the metric presentation registry in local and cloud persistence.
- [ ] Expose the browser presentation contract and regenerate hosted API types.
- [ ] Filter gateway rollup projection from the registry so raw/internal streams are not sent.
- [ ] Cut the dashboard frontend over to the backend presentation endpoint and delete the frontend domain config.
- [ ] Validate locally, update this plan with evidence, and deploy through the hosted deploy script.

## Surprises & Discoveries

- Observation: The dashboard route owns most of the metric presentation business config today.
  Evidence: `web-ui/src/routes/index.tsx` defines `CURRENT_METRIC_META`, `HISTORY_METRIC_GROUPS`, public labels, units, accents, axis bounds, grouping, ordering, and derives the `/metrics/history` query list from that local array.

- Observation: The backend already contains a partial display-metric concept, but it is too small and split from the frontend.
  Evidence: `apps/control-plane/src/dirt_control/api/browser.py` defines `DISPLAY_METRIC_BY_STORAGE` and `DISPLAY_METRIC_BY_PUBLIC` for `fan_duty_pct`, `humidifier_mist_level`, `heater_heat_level`, and `dehumidifier_on`. It does not define dashboard groups, labels, current-card eligibility, y-axis bounds, value precision, or history sync eligibility.

- Observation: The gateway rollup projection currently emits every enabled metric with a metric name, then adds calibrated `soil_moisture_pct`.
  Evidence: `_ROLLUP_SQL` in `apps/gateway/src/dirt_gateway/local.py` filters only on `c.metric_name IS NOT NULL`, so raw and diagnostic streams are eligible unless filtered after the query.

- Observation: Some frontend code is visual styling, not domain presentation config, and should stay in the frontend.
  Evidence: `web-ui/src/ui/Sparkline.tsx`, `web-ui/src/ui/Gauge.tsx`, and `web-ui/src/ui/MoistureComparisonChart.tsx` map semantic accents or sticker colors to Tailwind classes and implement chart interactions. The backend should send semantic accent names and metric config, not CSS class names.

## Decision Log

- Decision: Represent product-facing metric presentation as database rows seeded from source, not as frontend constants.
  Rationale: The gateway must filter rollups before upload, and the browser API must expose the same grouping and public names. A database-backed registry is inspectable and testable, while source-owned seed data keeps the config reviewed and repeatable instead of becoming mutable production state.
  Date/Author: 2026-05-31 / Codex

- Decision: The registry is keyed by stored metric and public metric, not only public metric.
  Rationale: Some browser metrics are transformed versions of stored streams, such as `fan_duty_pct` displayed as `fan_pct`. The gateway filters by stored metric, while the browser requests public metric names. A single row must connect both names.
  Date/Author: 2026-05-31 / Codex

- Decision: `history_enabled` is fail-closed.
  Rationale: If the registry is missing or a metric lacks a presentation row, the gateway must not send all rollups by default. The production incident was caused by excessive history payloads, so an empty or incomplete registry should surface as a test or operational failure instead of silently syncing diagnostics.
  Date/Author: 2026-05-31 / Codex

- Decision: Keep plant moisture comparison as a plant feature endpoint in the first implementation.
  Rationale: The comparison chart is product-specific, uses plant identity and sticker colors, and is already backed by dedicated moisture endpoints. The general dashboard registry should own dashboard current/history presentation first; it can later expose reusable y-axis metadata for plant moisture if that becomes useful.
  Date/Author: 2026-05-31 / Codex

- Decision: Remove the frontend metric lists in the same change that introduces the backend presentation endpoint.
  Rationale: This repo prefers direct cutover for source-owned behavior. Keeping old frontend lists as fallbacks would recreate the drift this plan is meant to remove.
  Date/Author: 2026-05-31 / Codex

## Outcomes & Retrospective

Not yet implemented. At completion, record the measured before/after rollup projection size, the tests that passed, and whether any metric presentation decisions were deferred.

## Context and Orientation

The hosted metric path has three major pieces:

The local gateway reads the local PostgreSQL database and sends projections to the Railway control plane. Rollups are collected in `apps/gateway/src/dirt_gateway/local.py` through `_ROLLUP_SQL` and delivered by `apps/gateway/src/dirt_gateway/sync.py` as `RollupsRequest` from `apps/shared/src/dirt_shared/cloud_contract.py`.

The control plane stores latest metrics and rollups in cloud tables defined in `apps/control-plane/src/dirt_control/models/cloud.py`. Browser routes live in `apps/control-plane/src/dirt_control/api/browser.py`. Current browser history uses `/api/tents/{tent_id}/metrics/history`, where `DISPLAY_METRIC_BY_PUBLIC` maps public names like `fan_pct` back to storage names like `fan_duty_pct`.

The hosted React dashboard lives in `web-ui/src/routes/index.tsx`. Today it defines the dashboard metric catalog itself:

- `CURRENT_METRIC_META` decides which current metrics become top cards.
- `HISTORY_METRIC_GROUPS` decides history sections, order, labels, units, accents, y-axis bounds, and which metric histories are fetched.
- `isIntegerMetric()` derives formatting from unit strings.
- `HISTORY_METRIC_META` is the frontend-owned query plan for `/metrics/history`.

The frontend also has local UI components. `web-ui/src/ui/Sparkline.tsx` and `web-ui/src/ui/Gauge.tsx` should continue to own CSS class mapping, geometry, hover behavior, and accessibility. They should not own the product-facing metric registry.

The desired owner is a metric presentation registry stored in both local and cloud databases. The local database copy lets the gateway filter rollups before upload. The cloud copy lets the browser API expose presentation groups and validate public metric requests. Seed rows are source-owned through migrations or an idempotent seed module, so the configuration is reviewed with code and safe to recreate.

Recommended registry fields:

- `storage_metric`: metric name stored in local readings and cloud rollups, such as `fan_duty_pct`.
- `public_metric`: browser-facing metric name, such as `fan_pct`.
- `display_name`: label such as `Fan`.
- `unit`: browser display unit after transform, such as `%`.
- `accent`: semantic visual category from `temp`, `humidity`, `vpd`, `moisture`, `reservoir`, or `neutral`.
- `value_precision`: number of decimals the frontend should display.
- `y_min` and `y_max`: optional fixed chart domain.
- `current_enabled`: whether the metric appears as a current dashboard card.
- `history_enabled`: whether rollup history is synced and exposed for dashboard history.
- `dashboard_group`: nullable group key for dashboard history.
- `dashboard_group_label`: visible group label such as `Temperature Loop`.
- `dashboard_group_order`: order of groups.
- `display_order`: order inside current cards or a group.
- `transform`: optional enum for existing display transforms, such as `identity`, `mist_level_to_pct`, `heat_level_to_pct`, and `bool_to_pct`.

The first seed set should reproduce the current dashboard's useful public metrics while excluding raw/internal diagnostics from history. It should include public history rows for `temperature_f`, `heater_intensity_pct`, `fan_pct`, `humidity_pct`, `humidifier_intensity_pct`, `dehumidifier_runtime_pct`, `vpd_kpa`, `reservoir_in`, and `reservoir_ph`. It should include `soil_moisture_pct` if and only if the dashboard should show plant/water moisture history; it must not include `soil_moisture_raw` as history-enabled.

## Plan of Work

Milestone 1: Add a backend metric presentation registry.

Add SQLModel models for local and cloud registry rows. The local model belongs under `apps/shared/src/dirt_shared/models/` because the gateway reads it from the local database. The cloud model belongs in `apps/control-plane/src/dirt_control/models/cloud.py` because browser routes query the Railway database. Add Atlas migrations in both `migrations/` and `cloud/migrations/`.

Seed the rows from source-owned SQL or an idempotent seed helper. The seed must be safe to run repeatedly and should use upserts. The registry must be small and explicit; do not infer product-facing metrics from all capabilities. Add tests proving that raw/internal diagnostic streams are not `history_enabled`, especially `soil_moisture_raw`, and that calibrated `soil_moisture_pct` is the product-facing moisture metric.

Milestone 2: Make the control plane expose presentation config.

Refactor `DISPLAY_METRIC_BY_STORAGE` and `DISPLAY_METRIC_BY_PUBLIC` into registry-backed lookup code. Keep transform functions in Python, but drive which transforms apply from registry rows. Add Pydantic browser DTOs in `apps/control-plane/src/dirt_control/api/browser.py` for a presentation endpoint, for example `GET /api/tents/{tent_id}/metrics/presentation`.

The endpoint should return ordered current metrics, ordered history groups, and supported ranges. It should include public metric names, labels, units, semantic accents, y-axis bounds, value precision, and display order. The frontend should not need to know storage metric names.

Milestone 3: Filter gateway rollup projection from the same registry.

Update `apps/gateway/src/dirt_gateway/local.py` so `_ROLLUP_SQL` or the Python projection layer includes only `history_enabled` storage metrics and derived history metrics present in the local registry. The cleanest implementation is to join the local registry in SQL for base rows and to emit derived calibrated rows such as `soil_moisture_pct` only when that derived storage/public metric is history-enabled.

The filter must fail closed. If no `history_enabled` registry rows exist, `collect_rollups()` should return no rollups or raise a clear local configuration error that prevents upload; it must not send every metric.

Milestone 4: Cut the frontend over to backend-owned presentation.

Regenerate the hosted OpenAPI types with `scripts/gen-hosted-contract`. In `web-ui/src/routes/index.tsx`, fetch the new presentation endpoint with TanStack Query, use its current metrics to build cards, and use its history groups to build `/metrics/history` queries.

Delete `MetricMeta`, `MetricGroup`, `CURRENT_METRIC_META`, `HISTORY_METRIC_GROUPS`, `HISTORY_METRIC_META`, and `isIntegerMetric()`. Replace unit-derived integer formatting with backend `value_precision`. Keep `asAccent()` or an equivalent local guard so unknown semantic accents render as `neutral`. Keep `Sparkline`, `Gauge`, and `MoistureComparisonChart` as visual components.

Milestone 5: Remove dead code and tighten contracts.

After the frontend and backend use the registry, remove obsolete display maps from `browser.py` if they were replaced by registry lookups. Search for stale metric presentation constants and old transform paths. Do not leave unused DTOs, fallback constants, or dual code paths.

Add contract and boundary tests for the new DTOs. `web-ui/src/api-client/cloud.ts` must continue to consume generated types, not handwritten hosted response interfaces.

Milestone 6: Prove the payload is smaller and deploy.

Run local tests and a local gateway projection against the dev database. Capture the rollup metric names and count before upload. The expected result is that raw/internal metrics are absent and the row count is materially smaller than the incident payload. Deploy with `scripts/deploy-control-plane`, which applies cloud Atlas migrations before deploying the Railway API and web UI.

## Concrete Steps

Work from the repository root:

    cd /home/akcom/code/dirt

Read the required docs before editing database, contracts, or frontend code:

    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md

Create the local and cloud registry models and migrations. Use Atlas commands from `docs/database.md`; do not hand-edit generated Atlas metadata incorrectly. After migrations exist, run the migration lint commands documented there.

Add backend tests. Suggested test targets:

    uv run pytest apps/shared/tests apps/gateway/tests/test_sync.py apps/control-plane/tests/test_api.py -q

Regenerate hosted browser types after adding the endpoint:

    scripts/gen-hosted-contract

Update the frontend and run:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Run the dev stack and inspect behavior:

    make dev-refresh-db
    make dev-up
    make dev-status

Open the Web URL from `make dev-status`, log in with `dev-admin` / `dev-password`, and confirm the dashboard current cards and history groups render from backend presentation config.

## Validation and Acceptance

The implementation is accepted when all of these are true:

- Gateway rollup tests prove `soil_moisture_raw` and other raw/internal diagnostic streams are not emitted for history, while product-facing rows such as `temperature_f`, `humidity_pct`, `vpd_kpa`, `reservoir_in`, `reservoir_ph`, and calibrated `soil_moisture_pct` behave according to the registry.
- Control-plane API tests prove the presentation endpoint returns ordered current metrics, ordered history groups, supported ranges, semantic accents, units, y-axis bounds, and value precision from backend data.
- Browser API tests prove public metrics such as `fan_pct`, `humidifier_intensity_pct`, `heater_intensity_pct`, and `dehumidifier_runtime_pct` still resolve to their storage metrics and transforms.
- Frontend typecheck and tests pass using generated hosted contract types.
- `rg -n "CURRENT_METRIC_META|HISTORY_METRIC_GROUPS|MetricMeta|MetricGroup|HISTORY_METRIC_META|isIntegerMetric" web-ui/src` returns no dashboard-owned metric registry.
- `rg -n "DISPLAY_METRIC_BY_STORAGE|DISPLAY_METRIC_BY_PUBLIC" apps/control-plane/src` returns no obsolete split registry after replacement, unless the names were intentionally repurposed as thin registry indexes with tests.
- A local projection or debug SQL transcript shows history-enabled rollups exclude raw/internal streams and the payload is smaller than the incident path that sent every metric.
- In the browser, the dashboard still shows current cards and the three history groups, but those groups come from the backend endpoint.

## Idempotence and Recovery

Registry seed operations must be idempotent upserts. Re-running migrations in a fresh local or cloud database should produce the same registry rows.

Gateway filtering must be fail-closed. If the local registry is missing, the gateway must not upload all rollup streams. It may upload zero rollups with a clear log event or raise a clear configuration error. Tests should protect this behavior.

The frontend cutover is intentionally not backward-compatible with an API that lacks the presentation endpoint. During deployment, use `scripts/deploy-control-plane` so the cloud migration and API deploy happen before the web UI deploy. If deployment fails after the API migration but before the web UI deploy, the old web UI can keep using existing endpoints until the new deploy is retried. If deployment fails after the new web UI deploy, roll back using the hosted deployment process in `docs/hosted-control-plane.md`.

Do not reset gateway rollup cursors as part of this plan unless validating a one-time production recovery. Normal sync should resume with smaller future projections after the gateway has the registry filter.

## Artifacts and Notes

Frontend audit evidence from 2026-05-31:

- `web-ui/src/routes/index.tsx` contains frontend-owned `CURRENT_METRIC_META`, `HISTORY_METRIC_GROUPS`, `HISTORY_METRIC_META`, `asAccent()`, and `isIntegerMetric()`.
- `web-ui/src/routes/index.tsx` maps `HISTORY_METRIC_META` into one `/api/tents/{tent_id}/metrics/history` query per metric.
- `apps/control-plane/src/dirt_control/api/browser.py` contains `DISPLAY_METRIC_BY_STORAGE` and `DISPLAY_METRIC_BY_PUBLIC`, which are partial backend display mappings.
- `apps/gateway/src/dirt_gateway/local.py` currently filters rollup base rows only by `c.metric_name IS NOT NULL` and then unions calibrated `soil_moisture_pct`.

Production incident context that motivated the plan:

- Five-minute rollup sync attempted to send a very large payload containing thousands of rows across all metrics.
- The payload included streams that are useful for diagnostics but not useful for hosted dashboard history.
- The immediate bug is payload size; the architectural smell is duplicated and misplaced ownership of "what is product-facing metric history."

## Interfaces and Dependencies

New or changed interfaces expected at completion:

- Local SQLModel registry model under `apps/shared/src/dirt_shared/models/`, backed by a migration in `migrations/`.
- Cloud SQLModel registry model in `apps/control-plane/src/dirt_control/models/cloud.py`, backed by a migration in `cloud/migrations/`.
- Registry lookup helpers used by the gateway and control-plane browser routes. The helper may live in a shared Python module if it contains source-owned seed definitions or transform identifiers, but the runtime filtering and browser presentation should read database rows.
- Browser route `GET /api/tents/{tent_id}/metrics/presentation` with generated OpenAPI types consumed by `web-ui/src/api-client/generated/hosted-schema.ts`.
- Pydantic browser DTOs for metric presentation groups, presentation metric rows, and supported ranges.
- Gateway rollup projection that filters by local registry `history_enabled`.
- Control-plane metric history route that validates public metric names against the cloud registry and maps to storage metrics and transforms.
- Frontend dashboard code that consumes generated presentation DTOs and no longer owns domain metric groups or display metadata.

No new external package dependency is expected for this plan.

## Revision Notes

- 2026-05-31: Initial ExecPlan created after auditing hosted dashboard frontend presentation smells and the gateway/control-plane rollup path.
