# Rich plant telemetry detail page

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the hosted plant detail page is a general plant profile instead of a moisture-only page. An operator can open any current plant, read its projected wiki history, and see whatever telemetry streams are explicitly mapped to that plant. Plant A will show current readings and history for substrate moisture, substrate temperature, substrate EC, and substrate pH. Plants B-D will still have detail pages even when they have no current telemetry; those pages will show identity/wiki content and an empty telemetry state instead of returning 404.

This matters because Plant A now has rich substrate data from `plant-a-substrate-node`, and the old page model is too tightly coupled to `plant.moisture_capability_id`. The durable model is a plant-to-metric-stream mapping. The mapping replaces the one-off moisture FK, supports future per-plant sensors without adding new plant columns, and lets the browser API render plant detail from explicit source-owned data.

The work is complete when `plant.moisture_capability_id`, `cloud_plant.moisture_device_id`, `cloud_plant.moisture_capability_id`, moisture-specific browser fields such as `has_moisture_stream` and `latest_moisture`, and the moisture-only plant detail/comparison paths are removed; Plant A's four substrate streams are mapped through a canonical `plant_metric_stream` source table and projected to cloud; the hosted plant detail page renders latest readings and history charts using metric presentation rows; temperature is displayed in deg F; EC is displayed in mS/cm; pH and EC are no longer marked experimental in DB/wiki content; and the obsolete moisture comparison chart/component is deleted if no longer used.


## Progress

- [x] (2026-06-11) Reviewed current hosted plant detail frontend, browser API, gateway projection, cloud contracts, metric presentation seeds, and Plant A RS485 substrate-node seed data.
- [x] (2026-06-11) Resolved product decisions with the operator: all plants get detail pages, mapped telemetry gets readings plus history, temperature displays as deg F, EC displays as mS/cm, pH/EC are considered calibrated, `moisture_capability_id` should be deprecated and removed, and the moisture comparison chart should be deleted.
- [x] (2026-06-11) Wrote this ExecPlan for the direct cutover.
- [x] (2026-06-11) Revised the plan to explicitly deprecate `has_moisture_stream`, `latest_moisture`, and all other moisture-specific plant API/UI affordances after `plant_metric_stream` becomes canonical.
- [x] (2026-06-12) Implement Milestone 1: add canonical local/cloud plant metric stream mapping and seed Plant A streams.
- [x] (2026-06-12) Implement Milestone 2: remove `moisture_capability_id` from local/cloud models, migrations, contracts, API responses, tests, and consumers.
- [x] (2026-06-12) Implement Milestone 3: add substrate metric presentation rows and rollup sync coverage for Plant A metrics.
- [x] (2026-06-12) Implement Milestone 4: expose generalized plant detail telemetry APIs.
- [x] (2026-06-12) Implement Milestone 5: rebuild the hosted plant detail UI around mapped metrics and remove moisture comparison code.
- [x] (2026-06-12) Implement Milestone 6: clean pH/EC experimental metadata/wiki notes and validate locally.
- [x] (2026-06-12) Run Milestone 7 local backend/frontend/migration/browser validation.
- [x] (2026-06-12) Deploy through the supported hosted deploy script and capture hosted acceptance evidence.


## Surprises & Discoveries

- Observation: The current plant detail route 404s when a plant lacks a moisture stream.
  Evidence: `apps/control-plane/src/dirt_control/api/browser.py` uses `_get_moisture_backed_plant()` for `GET /api/tents/{tent_id}/plants/{plant_id}`, and that helper raises 404 if `moisture_device_id` or `moisture_capability_id` is missing.

- Observation: The hosted dashboard only links plant rows when `has_moisture_stream` is true.
  Evidence: `web-ui/src/routes/index.tsx` renders a `Link` only when `plant.has_moisture_stream`; otherwise it renders an inactive row labeled "No moisture stream".

- Observation: Latest cloud metrics carry `zone_id`, but rollups do not.
  Evidence: `CloudLatestMetric` in `apps/control-plane/src/dirt_control/models/cloud.py` has `zone_id`; `CloudMetricRollup` has `site_id`, `tent_id`, `device_id`, `capability_id`, `metric`, and bucket fields but no `zone_id`. A durable plant history implementation should not rely on zone naming.

- Observation: Plant A's pH, EC, and substrate temperature latest metrics should already be eligible for generic latest sync, but their histories are not enabled by the current presentation registry.
  Evidence: `apps/gateway/src/dirt_gateway/local.py` excludes `soil_moisture_raw` and `soil_moisture_pct` from generic latest sync but not `substrate_temp_c`, `substrate_ec_us_cm`, or `substrate_ph`. The canonical rollup query joins `metric_presentation` on `history_enabled=true`, and the local/cloud metric presentation seed migrations currently do not include the substrate metrics.

- Observation: The existing `MoistureComparisonChart` is not reusable for rich substrate telemetry.
  Evidence: `web-ui/src/ui/MoistureComparisonChart.tsx` clamps values to 0-100%, renders fixed 0/50/100% axis labels, and organizes series by plant/sticker instead of by metric stream.

- Observation: Reusing `metric_presentation.current_enabled` as the plant detail display gate would leak plant-specific substrate metrics into the tent dashboard current-card model.
  Evidence: `GET /api/tents/{tent_id}/metrics/presentation` returns `current_metrics` from rows where `CloudMetricPresentation.current_enabled` is true, and `web-ui/src/routes/index.tsx` uses that list to build tent-level current cards. Plant detail should use stream mapping for inclusion and metric presentation for formatting/history metadata.

- Observation: Plant A's pH/EC capability metadata and wiki content still say pH/EC are experimental.
  Evidence: `migrations/20260610183000_seed_plant_a_substrate_node.sql` seeds `substrate_ec_us_cm` and `substrate_ph` with `experimental=true` and an experimental note. Wiki pages under `wiki/hardware/rs485-substrate-sensors.md` and `wiki/grows/main-2026-03-15/plants/plant-a.md` mention pH/EC as experimental or trend/reference data.

- Observation: After Milestone 2 and before Milestone 4/5, hosted plant detail was temporarily an identity/wiki page with a neutral active stream count, not a telemetry reading/history page.
  Evidence: `PlantDetailResponse` exposed `telemetry_stream_count` and no `latest_moisture`/freshness fields; the old moisture history endpoints were removed. Milestones 4 and 5 replaced that temporary state with mapped telemetry latest/history API responses and UI.


## Decision Log

- Decision: Introduce `plant_metric_stream` as the canonical local plant telemetry mapping.
  Rationale: Plants can have multiple telemetry streams, and future plants may gain pH/EC/temp sensors on devices that should not be inferred from moisture stream columns or zone naming. A mapping table is the simplest truthful model for a many-stream plant detail page.
  Date/Author: 2026-06-11 / Operator + Codex

- Decision: Remove `plant.moisture_capability_id` and cloud moisture stream columns in the same direct cutover.
  Rationale: The operator explicitly wants `moisture_capability_id` deprecated and removed. Keeping it as a compatibility path would preserve parallel sources of truth for plant telemetry.
  Date/Author: 2026-06-11 / Operator

- Decision: Remove moisture-specific browser affordances such as `has_moisture_stream`, `latest_moisture`, `moisture_device_id`, and `moisture_capability_id`.
  Rationale: Once `plant_metric_stream` is canonical, moisture is one mapped metric stream, not plant identity. The browser list may expose a telemetry-neutral derived field such as `has_telemetry` or `telemetry_stream_count`, but it must not preserve a metric-specific boolean or latest-reading field.
  Date/Author: 2026-06-11 / Operator + Codex

- Decision: All plants should have hosted detail pages, regardless of telemetry.
  Rationale: Plant detail is also an identity and wiki/history page. Telemetry availability should affect the telemetry section, not route existence.
  Date/Author: 2026-06-11 / Operator

- Decision: Plant detail telemetry inclusion is controlled by plant stream mapping; metric presentation rows control formatting, chart bounds, grouping/order, and history eligibility.
  Rationale: This reuses the existing backend-owned presentation registry without making tent-level `current_enabled` carry plant-specific inclusion semantics.
  Date/Author: 2026-06-11 / Codex

- Decision: Convert `substrate_temp_c` to deg F and `substrate_ec_us_cm` to mS/cm at the browser API response boundary.
  Rationale: Storage remains source-unit and canonical, while the hosted UI receives display-ready values consistently for latest and history points.
  Date/Author: 2026-06-11 / Operator + Codex

- Decision: pH and EC are calibrated and should no longer be labeled experimental.
  Rationale: The operator has calibrated the probe and is confident in the readings. DB metadata and wiki/operator notes should match the operational truth.
  Date/Author: 2026-06-11 / Operator

- Decision: Delete the moisture comparison chart and unused moisture comparison endpoints/components.
  Rationale: B-D no longer have current moisture telemetry, and the plant detail page is shifting from cross-plant moisture comparison to per-plant mapped telemetry.
  Date/Author: 2026-06-11 / Operator


## Outcomes & Retrospective

Milestone 1 added the canonical mapping foundation. Local `PlantMetricStream`
and cloud `CloudPlantMetricStream` SQLModel tables now exist, with Atlas
migrations `migrations/20260612020505_add_plant_metric_stream.sql` and
`cloud/migrations/20260612020519_add_cloud_plant_metric_stream.sql`. The local
migration seeds Plant A's four active substrate streams from
`plant-a-substrate-node` and raises if the expected current Plant A row or
required capabilities are missing. The gateway catalog contract now carries
`CatalogPlantMetricStream`, local catalog collection emits public stream
identifiers, and the control-plane catalog route upserts cloud stream rows by
their natural identity.

Validation passed for Milestone 1:

- `uv run pytest apps/shared/tests/test_cloud_contract.py -q` — 13 passed.
- `uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q` — 28 passed.
- `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` — 46 passed.
- `uv run ruff check` on touched Python files — passed.
- `atlas migrate hash --env local` and `atlas migrate hash --env cloud` — passed.
- `git diff --check` — passed.

`atlas migrate lint --env local --latest 1` and
`atlas migrate lint --env cloud --latest 1` were attempted but are unavailable
in the installed Atlas community CLI because migrate lint is gated behind Atlas
Pro login.

Milestone 2 completed the direct moisture-FK cutover. Local `Plant` no longer
has `moisture_capability_id`, and cloud `CloudPlant` no longer has
`moisture_device_id` or `moisture_capability_id`. Atlas migrations
`migrations/20260612022035_remove_plant_moisture_capability.sql` and
`cloud/migrations/20260612022044_remove_cloud_plant_moisture_columns.sql`
remove those columns. `CatalogPlant` now carries plant identity/targets/wiki
only; mapped streams remain in `CatalogPlantMetricStream`.

Local plant moisture consumers now resolve active `PlantMetricStream` rows
whose capability metric is `soil_moisture_pct`. Browser plant list/detail
responses no longer include `has_moisture_stream`, `latest_moisture`,
`moisture_device_id`, or `moisture_capability_id`; they expose
`telemetry_stream_count` derived from active cloud stream rows. The hosted
dashboard links every plant row, and plant detail returns 200 for plants without
telemetry. The moisture-specific browser history endpoints were removed because
they cannot be coherent once the cloud plant moisture columns are gone; the
general mapped telemetry API remains Milestone 4 scope. The old
`MoistureComparisonChart` file remains for Milestone 5 cleanup, but its unused
exported types were made internal so invariants do not report dead exports.

Validation passed for Milestone 2:

- `uv run pytest apps/shared/tests/test_cloud_contract.py -q` — 13 passed.
- `uv run pytest apps/shared/tests/test_daily_sensors.py -q` — 12 passed.
- `uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q` — 28 passed on rerun; the first attempt passed assertions but hit a transient PostgreSQL test database teardown privilege error.
- `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` — 44 passed.
- `uv run pytest apps/voice/tests/test_sensor_tools.py -q` — 2 passed.
- `uv run pytest apps/tests/invariants -q` — 41 passed.
- `scripts/gen-hosted-contract` — regenerated `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts`.
- `pnpm --dir web-ui typecheck` — passed.
- `pnpm --dir web-ui lint` — passed.
- `pnpm --dir web-ui test` — 3 files / 4 tests passed.
- `uv run ruff check` on touched Python files — passed.
- `atlas migrate hash --env local` and `atlas migrate hash --env cloud` — passed.
- `git diff --check` — passed.

`atlas migrate lint --env local --latest 1` and
`atlas migrate lint --env cloud --latest 1` were attempted again for Milestone 2
and remain unavailable in the installed Atlas community CLI because migrate lint
is gated behind Atlas Pro login.

Milestone 3 added idempotent local/cloud metric presentation seed migrations:
`migrations/20260612024000_seed_substrate_metric_presentation.sql` and
`cloud/migrations/20260612024000_seed_substrate_metric_presentation.sql`.
The rows enable history for soil moisture, substrate temperature, substrate EC,
and substrate pH while leaving `current_enabled=false` for plant-detail-only
substrate telemetry. The presentation registry exposes display units `%`, `°F`,
`mS/cm`, and `pH`; gateway rollup payloads continue to carry the source
capability units such as `degC` and `us/cm`.

Validation passed for Milestone 3:

- `uv run pytest apps/shared/tests/test_metric_presentation_registry.py -q` — 2 passed.
- `uv run pytest apps/control-plane/tests/test_cloud_metric_presentation_registry.py -q` — 2 passed.
- `uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q` — 29 passed.
- `uv run ruff check` on touched Milestone 3 Python test files — passed.
- `atlas migrate hash --env local` and `atlas migrate hash --env cloud` — passed.
- `git diff --check` — passed.

Milestone 4 added generalized mapped plant telemetry to the hosted browser API.
Plant detail now includes active mapped stream metadata plus latest readings,
and plants without streams still return 200 with `telemetry=[]`. The new
`GET /api/tents/{tent_id}/plants/{plant_id}/metrics/history` endpoint returns
history for mapped, `history_enabled` streams only. Latest and history queries
are scoped by mapped `(device_id, capability_id, metric)` and do not infer from
`zone_id`. Display conversion happens at the browser API boundary:
`substrate_temp_c` is returned in degrees F and `substrate_ec_us_cm` in
`mS/cm`, while source values and units remain visible in the response.

Validation passed for Milestone 4:

- `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` — 46 passed.
- `scripts/gen-hosted-contract` — regenerated `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts`.
- `pnpm --dir web-ui typecheck` — passed after contract regeneration.
- `uv run ruff check` on touched Milestone 4 Python files — passed.
- `git diff --check` — passed.

Milestone 5 rebuilt the hosted plant detail route around mapped telemetry.
`web-ui/src/routes/tents.$tentId.plants.$plantId.tsx` now renders identity/wiki
content independently of telemetry, current metric cards from `detail.telemetry`,
and per-metric history charts from
`GET /api/tents/{tent_id}/plants/{plant_id}/metrics/history`. Dashboard plant
rows remain linked for every plant and use telemetry-neutral labels. The unused
`MoistureComparisonChart` component and test were deleted.

Validation passed for Milestone 5:

- `pnpm --dir web-ui typecheck` — passed.
- `pnpm --dir web-ui lint` — passed.
- `pnpm --dir web-ui test` — 2 files / 3 tests passed.
- `pnpm --dir web-ui build` — passed.
- `git diff --check` — passed.
- A stale-reference scan found no old moisture comparison/history/API UI terms under `web-ui/src`.

Milestone 6 cleaned Plant A pH/EC calibration metadata and operator notes.
`migrations/20260612033000_calibrate_plant_a_ph_ec_metadata.sql` updates the
Plant A substrate-node `substrate_ec_us_cm` and `substrate_ph` capability
metadata by removing `experimental` / `experimental_note`, setting
`calibration_status=calibrated`, and raising if the expected capability rows
are missing. It also updates the device-level `ph_ec_status` marker to
`calibrated` so DB metadata no longer labels pH/EC experimental. Wiki/operator
notes in the RS485 substrate sensor pages, Plant A page, overview, and soil
moisture sensing notes now state current pH/EC operational status as calibrated
without inventing an exact calibration date.

Validation passed for Milestone 6:

- `atlas migrate hash --env local` — passed.
- `uv run pytest apps/hwd/tests/test_ingest_api.py -q` — 26 passed.
- `uv run pytest apps/tests/invariants/test_schema_managed_by_atlas.py -q` — 4 passed.
- `uv run scripts/lint.py` — passed with existing file-length warnings only.
- `git diff --check` — passed.
- A stale-reference scan found only expected historical ExecPlan context and old migrations.

Milestone 7 local validation passed before hosted deployment. The local
hosted stack started with `make dev-up` at API `http://192.168.1.79:8021` and
Web `http://192.168.1.79:5171`. `agent-browser` logged in through the real
local auth form as `dev-admin`, captured the dashboard, Plant A detail, and
Plant B detail, and confirmed:

- Dashboard plant rows render as links for all four plants; Plant A shows
  `4 streams`, while B-D show `No telemetry`.
- Plant A detail renders the `Telemetry` section with Soil Moisture,
  Substrate Temp, Substrate EC, and Substrate pH history charts.
- Plant B detail returns 200 and renders identity/wiki content plus a
  professional `No telemetry` state.
- Browser-facing API calls for plant list, Plant A detail, Plant A history,
  and Plant B detail returned 200.
- Agent-browser console output contained Vite/React dev informational logs and
  no application errors.

Local browser evidence:

- `debug/screenshots/rich-telemetry-local-dashboard.png`
- `debug/screenshots/rich-telemetry-local-plant-a.png`
- `debug/screenshots/rich-telemetry-local-plant-b.png`

Validation passed for Milestone 7 local checks:

- `uv run pytest apps/shared/tests/test_metric_presentation_registry.py -q` — 2 passed.
- `uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q` — 29 passed.
- `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_cloud_metric_presentation_registry.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` — 48 passed.
- `uv run pytest apps/hwd/tests/test_ingest_api.py -q` — 26 passed.
- `uv run pytest apps/voice/tests/test_sensor_tools.py apps/shared/tests/test_daily_sensors.py -q` — 14 passed on sequential rerun after a parallel test-database race.
- `uv run pytest apps/tests/invariants -q` — 41 passed.
- `atlas migrate hash --env local` and `atlas migrate hash --env cloud` — passed.
- `scripts/gen-hosted-contract` — regenerated hosted browser OpenAPI and TypeScript schema.
- `pnpm --dir web-ui typecheck` — passed.
- `pnpm --dir web-ui lint` — passed.
- `pnpm --dir web-ui test` — 2 files / 3 tests passed.
- `pnpm --dir web-ui build` — passed.
- `uv run ruff check` — passed.
- `uv run scripts/lint.py` — passed with existing file-length warnings only.
- `git diff --check` — passed.

Hosted deployment completed after operator authorization. The first
`scripts/deploy-control-plane` run applied cloud migrations, deployed
control-plane API deployment `9708c210-408c-4edd-93ce-36ecd8c3e8c4`, deployed
web UI deployment `eec9d4c6-0e08-45bd-8e06-ce7364c45661`, and passed the
script's cloud API and hosted UI smoke checks. After deployment, the local
gateway was restarted and cloud health reported `status=live`; the gateway
backlog drained to 0 after subsequent sync cycles.

After hosted review, the plant detail telemetry card UI was simplified to show
only converted/display values and received time; the duplicate `Source` row was
removed entirely. Focused validation for that UI cleanup passed:

- `pnpm --dir web-ui typecheck` — passed.
- `pnpm --dir web-ui lint` — passed.
- `pnpm --dir web-ui test` — 2 files / 3 tests passed.
- `pnpm --dir web-ui build` — passed.
- Authenticated local `agent-browser` text check on Plant A detail showed the
  four telemetry labels and no `Source` text.

The second `scripts/deploy-control-plane` run found no pending cloud
migrations, redeployed control-plane API deployment
`013aa516-4b58-4f71-bd61-6fb71805f60c`, deployed web UI deployment
`88842506-28e8-41e3-9dae-f67532b422cb`, and passed the script's cloud API and
hosted UI smoke checks. A hosted bundle check against `https://sirius-forge.com/`
found no remaining `Source` label in deployed JavaScript.


## Context and Orientation

Local source data lives in PostgreSQL and SQLModel models under `apps/shared/src/dirt_shared/models/`. The current local `Plant` model is in `apps/shared/src/dirt_shared/models/plant.py`; it has identity fields such as `plant_id`, `name`, `display_order`, `status`, moisture target bounds, wiki path projection via gateway, and the old `moisture_capability_id` FK. Devices and capabilities live in `apps/shared/src/dirt_shared/models/device.py`; a `Capability` belongs to a `Device` and carries public identifiers such as `capability_id`, `metric_name`, and `unit`.

Gateway catalog sync is the outward projection path. `apps/gateway/src/dirt_gateway/local.py` builds catalog, latest metric, rollup, asset, and wiki projection payloads. `apps/shared/src/dirt_shared/cloud_contract.py` defines the Pydantic DTOs for those payloads. `apps/control-plane/src/dirt_control/api/gateway.py` receives those payloads and upserts cloud tables from `apps/control-plane/src/dirt_control/models/cloud.py`.

Browser API routes live in `apps/control-plane/src/dirt_control/api/browser.py`. The current plant APIs are moisture-specific: `PlantDetailResponse` includes `moisture_device_id`, `moisture_capability_id`, `latest_moisture`, and `freshness`; `GET /api/tents/{tent_id}/plants/{plant_id}` uses `_get_moisture_backed_plant()`; `GET /api/tents/{tent_id}/plants/moisture/history` powers the comparison chart; and `GET /api/tents/{tent_id}/plants/{plant_id}/moisture/history` is a moisture-only history endpoint.

The hosted React app is under `web-ui/`. The plant detail route is `web-ui/src/routes/tents.$tentId.plants.$plantId.tsx`. The hosted dashboard route is `web-ui/src/routes/index.tsx`. Browser API types are generated by `scripts/gen-hosted-contract` into `web-ui/src/api-client/generated/hosted-schema.ts`; do not hand-write hosted response interfaces.

Metric presentation rows are source-owned seed data in local and cloud migrations. The local seed is `migrations/20260531233500_metric_presentation_registry.sql`; the cloud seed is `cloud/migrations/20260531233500_metric_presentation_registry.sql`. Gateway rollups only sync metrics whose local `metric_presentation.history_enabled` is true. The browser presentation endpoint exposes display labels, units, precision, accents, y-axis bounds, grouping, and supported ranges.

Before implementation, read the docs required by `AGENTS.md` for this work:

    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/hosted-control-plane.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md
    sed -n '1,220p' docs/references/tailwind-v4/INDEX.md
    sed -n '1,220p' wiki/AGENTS.md


## Plan of Work

Milestone 1 adds the canonical mapping. Add a local SQLModel, likely `PlantMetricStream`, under `apps/shared/src/dirt_shared/models/` or a plant-adjacent module. The table should have a surrogate id, `plant_id` FK to local `plant.id`, `capability_id` FK to local `capability.id`, `display_order`, `is_active`, timestamps if consistent with nearby models, and a uniqueness constraint on `(plant_id, capability_id)`. Add a local Atlas migration that creates the table and seeds Plant A's four active streams for the current grow run:

- `soil_moisture_pct`
- `substrate_temp_c`
- `substrate_ec_us_cm`
- `substrate_ph`

Add the cloud counterpart, likely `CloudPlantMetricStream`, with `site_id`, `tent_id`, `grow_run_id`, `plant_id`, `device_id`, `capability_id`, `metric`, `display_order`, `is_active`, `synced_at`, `created_at`, and `updated_at`. Key it by `site_id + tent_id + grow_run_id + plant_id + device_id + capability_id + metric`. Add a cloud Atlas migration for this table.

Extend `apps/shared/src/dirt_shared/cloud_contract.py` with a `CatalogPlantMetricStream` DTO and add `plant_metric_streams` to `CatalogRequest` and `CatalogResponse`. Extend `GatewayLocalServiceBundle.collect_catalog()` and `apps/control-plane/src/dirt_control/api/gateway.py` to project/upsert mapped streams. Use joins through `PlantMetricStream -> Plant -> GrowRun -> Tent` and `Capability -> Device` so the cloud table stores public stream identifiers, not local numeric ids.

Milestone 2 removes the old moisture FK and moisture-specific plant API shape. Remove `Plant.moisture_capability_id` and associated index/FK from local models and migrations through a direct Atlas migration. Remove `moisture_device_id` and `moisture_capability_id` from `CatalogPlant`, `CloudPlant`, gateway plant projection, browser plant summary/detail response models, and frontend generated-type consumers. Remove browser fields and frontend model assumptions named around moisture, including `has_moisture_stream` and `latest_moisture`. If the plant list needs a compact affordance, replace `has_moisture_stream` with telemetry-neutral derived data such as `has_telemetry` or `telemetry_stream_count`, computed from active mapped streams. Update local consumers that currently join `Plant.moisture_capability_id`, including `apps/shared/src/dirt_shared/services/readings.py`, `apps/shared/src/dirt_shared/services/daily_sensors.py`, `apps/gateway/src/dirt_gateway/local.py`, `apps/voice/src/dirt_voice/tools/sensors.py`, and any tests. These consumers should query the mapped stream for metric `soil_moisture_pct` when they need canonical plant moisture.

This is a direct cutover. Do not leave helper wrappers named around `moisture_capability_id`, cloud compatibility columns, moisture-specific browser fields, or fallback branches that preserve the removed FK. If a service needs plant moisture, give it a plainly named query over `PlantMetricStream` such as `get_latest_product_plant_moisture_readings()`, backed by the mapping table.

Milestone 3 enables substrate histories. Add idempotent local and cloud migrations that insert/update metric presentation rows for Plant A substrate detail:

- `soil_moisture_pct`: keep as `%`, history enabled.
- `substrate_temp_c`: display name like `Substrate Temp`, stored unit `degC`, display unit exposed to plant detail as `°F`, precision 1, history enabled.
- `substrate_ec_us_cm`: display name like `Substrate EC`, stored unit `us/cm`, display unit exposed to plant detail as `mS/cm`, precision 2 or 3, history enabled.
- `substrate_ph`: display name like `Substrate pH`, unit `pH`, precision 1, history enabled.

Keep `current_enabled` semantics focused on the tent dashboard. If substrate rows should not appear as tent dashboard current cards, leave `current_enabled=false` and let plant detail use stream mapping for inclusion. Add tests in `apps/shared/tests/test_metric_presentation_registry.py`, `apps/control-plane/tests/test_cloud_metric_presentation_registry.py`, and `apps/gateway/tests/test_sync.py` proving substrate rollups are emitted only when presentation history is enabled.

Milestone 4 generalizes the browser plant API. Replace `_get_moisture_backed_plant()` with a plant lookup that returns the newest synced row for the tent/plant regardless of stream availability. Add response DTOs for mapped telemetry, for example:

- `PlantMetricStreamResponse`: metric identity, display name, display unit, precision, accent, y bounds, latest reading, freshness, and optional history points.
- `PlantMetricReadingResponse`: value already converted for display, source/stored value if useful for debugging, source unit, display unit, device id, capability id, source/received timestamps, stale window.
- `PlantMetricHistoryResponse`: range and points for one stream, with values converted at the API boundary.

The detail route can either return latest telemetry and a separate `GET /api/tents/{tent_id}/plants/{plant_id}/metrics/history?range=...` endpoint, or return history in one detail payload. Prefer a separate history endpoint if it follows existing dashboard query patterns and keeps live refresh cheaper. The plant detail route must return 200 for B-D even with no streams, with `telemetry=[]` or equivalent.

Implement conversion helpers in the browser API layer:

- `substrate_temp_c`: `degF = degC * 9 / 5 + 32`
- `substrate_ec_us_cm`: `mS/cm = us/cm / 1000`
- `substrate_ph`: unchanged
- `soil_moisture_pct`: unchanged

Use the mapped stream's `(device_id, capability_id, metric)` to query `CloudLatestMetric` and `CloudMetricRollup`. Do not infer plant history from `zone_id`.

Remove the moisture comparison browser endpoint if no remaining consumer uses it. Keep or delete the individual moisture history endpoint based on whether it is replaced by the generalized plant metric history endpoint in the same change; prefer deletion to avoid duplicate product paths.

Milestone 5 rebuilds the frontend route. Update `web-ui/src/routes/tents.$tentId.plants.$plantId.tsx` to render plant identity/wiki content independent of telemetry. Replace the moisture fact row with a metric card grid driven by mapped telemetry. Render per-metric history charts with reusable chart primitives. If `Sparkline` is sufficient for individual metric histories, reuse it. If a richer multi-metric panel is needed, make a generic metric chart component with y-axis bounds from presentation metadata; do not adapt `MoistureComparisonChart`.

Update `web-ui/src/routes/index.tsx` so every plant row links to detail. Replace moisture-specific headings/labels in the plant panel with plant or telemetry-neutral text. Rows without telemetry should render a neutral "No telemetry" status but still navigate. Do not carry over `has_moisture_stream` naming into the route model; use generated telemetry-neutral fields from the API.

Delete `web-ui/src/ui/MoistureComparisonChart.tsx` and associated tests/imports if no route uses it after the redesign. Regenerate TanStack route tree and hosted OpenAPI client types through the normal toolchain.

Milestone 6 cleans calibration metadata and wiki/operator notes. Add a local migration to update Plant A substrate capability metadata so `substrate_ec_us_cm` and `substrate_ph` no longer have `experimental=true` or the old experimental note. Update `wiki/hardware/rs485-substrate-sensors.md`, `wiki/hardware/rs485-substrate-sensor-calibration.md`, `wiki/grows/main-2026-03-15/plants/plant-a.md`, `wiki/overview.md`, and any operator notes found by searching for `experimental trend/reference`, `until field-calibrated`, `substrate_ec_us_cm`, and `substrate_ph`. The wiki should state that pH/EC are calibrated as of the current calibration date if known from local notes; if the exact calibration date is not discoverable, state only that the current operational status is calibrated.

Milestone 7 validates and deploys. Run focused backend, frontend, migration, and invariant checks; then run local hosted stack browser validation. Deploy only through `scripts/deploy-control-plane` when ready.


## Concrete Steps

Start from the repository root:

    cd /home/akcom/code/dirt

Read the required docs:

    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/hosted-control-plane.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md
    sed -n '1,220p' docs/references/tailwind-v4/INDEX.md
    sed -n '1,220p' wiki/AGENTS.md

Find all old moisture-FK usage before editing:

    rg -n "moisture_capability_id|moisture_device_id|has_moisture_stream|latest_moisture|PlantMoisture|moisture/history|MoistureComparison" apps web-ui migrations cloud/migrations docs wiki

Inspect the source schema and stream rows:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -P pager=off \
      -c "\d plant" \
      -c "\d capability" \
      -c "SELECT p.plant_id, d.device_id, c.capability_id, c.metric_name, c.unit FROM plant p JOIN capability c ON c.id = p.moisture_capability_id JOIN device d ON d.id = c.device_id ORDER BY p.plant_id;" \
      -c "SELECT d.device_id, c.capability_id, c.metric_name, c.unit, c.metadata FROM capability c JOIN device d ON d.id = c.device_id WHERE d.device_id = 'plant-a-substrate-node' ORDER BY c.capability_id;"

Create local and cloud migrations using the repository's Atlas workflow. Follow the exact commands in `docs/database.md` and `docs/references/atlas/INDEX.md`; do not hand-edit `atlas.sum` except through Atlas hash commands.

After API changes, regenerate hosted contracts:

    scripts/gen-hosted-contract

After frontend route changes, run the web checks:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Run focused backend checks, adding or narrowing targets as implementation touches files:

    uv run pytest apps/shared/tests/test_metric_presentation_registry.py -q
    uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q
    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_cloud_metric_presentation_registry.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    uv run pytest apps/voice/tests/test_sensor_tools.py apps/shared/tests/test_daily_sensors.py -q
    uv run pytest apps/tests/invariants -q

Run the standard pre-commit fix path before committing:

    make fix

Validate browser behavior locally:

    make dev-up
    make dev-status

Use the Web URL from `make dev-status`, log in with `dev-admin` / `dev-password`, then verify:

- The dashboard plant panel links all current plants.
- Plant A detail shows moisture, substrate temp in deg F, EC in mS/cm, and pH latest readings.
- Plant A detail shows history charts for each mapped metric when synced rollups exist.
- Plants B-D detail pages render identity/wiki content and an empty telemetry state instead of 404.
- No moisture comparison chart remains.


## Validation and Acceptance

Database acceptance:

- Local `plant_metric_stream` exists and maps Plant A to exactly four active stream capabilities.
- Local `plant.moisture_capability_id` no longer exists.
- Cloud `cloud_plant_metric_stream` exists and receives mapped stream rows from catalog sync.
- Cloud `cloud_plant.moisture_device_id` and `cloud_plant.moisture_capability_id` no longer exist.
- Browser plant list/detail responses no longer include `has_moisture_stream`, `latest_moisture`, `moisture_device_id`, or `moisture_capability_id`.
- Any plant-list telemetry affordance is telemetry-neutral and derived from active mapped streams, such as `has_telemetry` or `telemetry_stream_count`.
- Metric presentation rows exist locally and in cloud for `substrate_temp_c`, `substrate_ec_us_cm`, and `substrate_ph` with `history_enabled=true`.
- Plant A pH/EC capability metadata no longer says experimental.

API acceptance:

- `GET /api/tents/main/plants/a` returns 200 with plant identity/wiki fields and mapped telemetry metadata.
- `GET /api/tents/main/plants/b` returns 200 even if telemetry is empty.
- Plant telemetry latest responses are scoped by mapped `(device_id, capability_id, metric)`.
- Plant telemetry history responses are scoped by mapped `(device_id, capability_id, metric)` and do not rely on `zone_id`.
- Temperature values returned to the browser are deg F; EC values are mS/cm.
- Moisture comparison endpoints are removed or have no generated frontend consumer.

Frontend acceptance:

- The dashboard plant panel links every plant, not only moisture-backed plants.
- Plant A detail shows current cards and history charts for moisture, temp, EC, and pH.
- B-D detail pages show identity/wiki and a professional empty telemetry state.
- UI labels say "Plants", "Telemetry", or "No telemetry" rather than "Plant Moisture" or "No moisture stream".
- `MoistureComparisonChart` is deleted if no longer used.
- No generated hosted schema files are hand-edited.

Operational acceptance:

- `make dev-up` starts the local hosted stack.
- Browser login and the Plant A/B-D detail flows pass locally.
- `scripts/deploy-control-plane` completes when the operator authorizes deployment.
- Hosted acceptance confirms Plant A rich telemetry appears after gateway sync.


## Idempotence and Recovery

The seed migrations for `plant_metric_stream`, metric presentation rows, and pH/EC metadata must be idempotent where practical. Use `INSERT ... ON CONFLICT DO UPDATE` for seed data and explicit checks for required Plant A substrate capabilities. If the Plant A substrate capabilities are missing, the migration should fail loudly rather than silently creating unmapped streams.

Catalog sync is safe to repeat. Gateway upserts for `CloudPlantMetricStream` should update rows by their natural stream key and leave no duplicate rows. If a stream is deactivated locally, cloud projection should either update `is_active=false` or have an explicit deletion/pruning behavior documented during implementation.

Removing `moisture_capability_id` is a direct cutover and should be implemented only after all source consumers have been updated to `PlantMetricStream`. If migration validation fails, fix the code/schema and rerun in a disposable/local database before touching hosted state. Do not recover by reintroducing compatibility columns unless the operator explicitly changes the decision.

If hosted deployment fails, use the normal rollback procedure in `docs/hosted-control-plane.md`. Do not run ad hoc Railway commands. Re-running `scripts/deploy-control-plane` is the supported retry path after code or migration fixes.


## Artifacts and Notes

Initial review evidence:

- `CloudLatestMetric` has `zone_id`; `CloudMetricRollup` does not.
- `collect_canonical_history_rollups()` only emits rows joined to `metric_presentation.history_enabled=true`.
- Existing local/cloud metric presentation seeds lack `substrate_temp_c`, `substrate_ec_us_cm`, and `substrate_ph`.
- Existing plant detail and dashboard links are gated by moisture stream presence.
- `MoistureComparisonChart` is 0-100% moisture-specific.

Implementation artifacts to add here as work proceeds:

- Migration filenames and Atlas validation output.
- Contract generation output.
- Focused pytest/pnpm results.
- Local browser URLs and screenshot paths.
- Deployment command output and hosted smoke-test notes.


## Interfaces and Dependencies

New or changed persistence interfaces:

- Local table/model: `plant_metric_stream`.
- Cloud table/model: `cloud_plant_metric_stream`.
- Removed local column/model field: `plant.moisture_capability_id`.
- Removed cloud columns/model fields: `cloud_plant.moisture_device_id`, `cloud_plant.moisture_capability_id`.
- Removed browser response fields: `has_moisture_stream`, `latest_moisture`, `moisture_device_id`, `moisture_capability_id`.
- Optional replacement browser response fields, if needed: `has_telemetry` or `telemetry_stream_count`, derived from active mapped streams.
- Local/cloud metric presentation rows for `substrate_temp_c`, `substrate_ec_us_cm`, `substrate_ph`.

New or changed gateway contract interfaces:

- `CatalogPlantMetricStream` in `apps/shared/src/dirt_shared/cloud_contract.py`.
- `CatalogRequest.plant_metric_streams`.
- `CatalogResponse.plant_metric_streams`.
- Gateway catalog collection and control-plane catalog upsert for mapped streams.

New or changed browser API interfaces:

- General plant detail response with mapped telemetry, not `latest_moisture`.
- General plant telemetry history endpoint scoped by mapped streams.
- Removed moisture comparison endpoint if no longer consumed.
- Generated OpenAPI contract regenerated by `scripts/gen-hosted-contract`.

Frontend interfaces:

- `web-ui/src/routes/tents.$tentId.plants.$plantId.tsx` renders mapped telemetry.
- `web-ui/src/routes/index.tsx` links every plant row.
- `web-ui/src/ui/MoistureComparisonChart.tsx` removed if unused.
- Shared chart/card helpers may be added only if they are genuinely reusable and simpler than route-local rendering.

External dependencies:

- PostgreSQL/Atlas migrations for local and cloud schemas.
- Existing TanStack Router, TanStack Query, Tailwind v4, and generated OpenAPI client.
- Local hosted dev stack via `make dev-up`.
- Hosted deployment via `scripts/deploy-control-plane`.


## Revision Notes

- 2026-06-11: Initial ExecPlan written after code review and operator clarification. This plan supersedes the moisture-only assumptions in `docs/epics/hosted-plant-detail/ExecPlan.md` but does not overwrite that file's historical implementation record.
- 2026-06-11: Added explicit deprecation of `has_moisture_stream`, `latest_moisture`, and other moisture-specific browser API/UI fields. Plant list affordances must be telemetry-neutral and derived from mapped streams.
