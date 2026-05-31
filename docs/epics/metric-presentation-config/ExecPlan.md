# Backend-owned metric presentation config

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

The hosted dashboard currently sends too much rollup history to the cloud and makes the frontend decide which metrics are product-facing. It also carries a second architectural smell: some cloud/browser metrics are aliases or transforms of differently named stored metrics. After this change, product telemetry uses canonical metric names at the producer/storage boundary, and the backend owns the metric presentation registry: which canonical metrics are synced for history, how dashboard metrics are grouped and ordered, labels, units, y-axis bounds, and value formatting. The frontend renders that contract and keeps only local visual styling such as CSS classes and chart interactions.

The user-visible result is that hosted sparkline payloads shrink because raw and diagnostic streams are not synced for dashboard history, while the dashboard keeps showing the same useful cards and history groups. A human can observe this by running the gateway rollup projection and seeing only presentation-enabled metrics, calling the browser presentation endpoint and seeing dashboard groups from the backend, then opening the hosted dashboard and seeing it render without `CURRENT_METRIC_META` or `HISTORY_METRIC_GROUPS` in `web-ui/src/routes/index.tsx`.

This is a direct cutover. Do not add frontend fallback lists, metric alias compatibility shims, or duplicate registries.

## Progress

- [x] (2026-05-31 21:35Z) Audited the hosted dashboard frontend and backend rollup/display paths.
- [x] (2026-05-31 21:50Z) Wrote the initial ExecPlan with a backend-owned registry, direct frontend cutover, and validation strategy.
- [x] (2026-05-31 22:15Z) Revised the plan to canonicalize product metric names before adding the registry. Native hardware levels remain controller details or logs, not cloud/browser metric aliases.
- [x] (2026-05-31 22:30Z) Revised the plan to delete persisted native humidifier/heater level streams instead of keeping them as diagnostic readings.
- [x] (2026-05-31 22:40Z) Clarified that canonical intensity readings must represent effective quantized actuator output, not raw requested control demand.
- [x] (2026-05-31 22:55Z) Quarantined calibrated soil moisture as a disposable legacy projection and clarified that rollup SQL should live inside named functions rather than module-level SQL constants.
- [ ] Canonicalize product metric names at the producer/storage boundary and directly migrate owned local/cloud data.
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

- Observation: The stored/public metric split is itself a smell for most actuator metrics.
  Evidence: `fan_duty_pct` is stored locally and in cloud rollups but the browser requests `fan_pct`; `humidifier_mist_level` is stored as a native 0..9 Govee level but the browser wants `humidifier_intensity_pct`; `heater_heat_level` is stored as a native 0..10 ThermoForge level but the browser wants `heater_intensity_pct`. These transforms belong at telemetry production time, where hardware semantics are known, not in the browser API.

- Observation: Native actuator levels are still real hardware concepts.
  Evidence: HWD services command or observe native levels such as Govee mist level and ThermoForge heat level. Those native values should remain inside hardware/controller code and structured logs. They should not remain persisted `sensorreading` streams unless a future product need requires queryable native-level history.

- Observation: Current HWD code reads native persisted levels back into the climate controller.
  Evidence: `apps/hwd/src/dirt_hwd/services/climate_controller.py` reads latest `humidifier_mist_level` and `heater_heat_level` to reconstruct current actuator state. The cleanup must update those reads to canonical percent metrics: `humidifier_intensity_pct` directly, and `heater_intensity_pct` converted back to a native level inside HWD when dispatch logic needs a ThermoForge level.

- Observation: Control-loop feedback must use effective actuator output, not requested continuous demand.
  Evidence: HWD quantizes humidifier demand to Govee levels and heater demand to ThermoForge levels before dispatch. Persisting the requested demand as current state would make the next loop believe the actuator delivered values it physically cannot deliver, weakening hysteresis, rate limiting, and anti-chatter behavior.

- Observation: `dehumidifier_on` is different from the level-to-percent cases.
  Evidence: A latest `dehumidifier_runtime_pct` value is not a hardware state; it is the bucket average of binary `dehumidifier_on` readings. The canonical latest metric should stay `dehumidifier_on` unless the product explicitly wants latest state represented as 0/100 percent. Runtime percent should be a rollup presentation of the binary canonical stream.

- Observation: The gateway rollup projection currently emits every enabled metric with a metric name, then adds calibrated `soil_moisture_pct`.
  Evidence: `_ROLLUP_SQL` in `apps/gateway/src/dirt_gateway/local.py` filters only on `c.metric_name IS NOT NULL`, so raw and diagnostic streams are eligible unless filtered after the query.

- Observation: Soil moisture calibration is the only current metric path that depends on `sensorcalibration`.
  Evidence: `apps/shared/src/dirt_shared/services/readings.py` defines `AUTO_CALIBRATED_METRICS = {"soil_moisture_raw"}`. Gateway latest/rollup SQL, daily sensors, and voice sensor tools all special-case `soil_moisture_raw + sensorcalibration -> soil_moisture_pct`.

- Observation: Dynamic soil moisture calibration is current hardware tech debt, not the desired long-term metric architecture.
  Evidence: Plant-node firmware emits raw ADC `soil_moisture_raw`, and the local database auto-widens `sensorcalibration` rows. Future soil moisture sensors are expected to behave more like reservoir sensors by producing normalized/calibrated product values at hardware or producer level.

- Observation: `_ROLLUP_SQL` is a mixed-responsibility implementation detail.
  Evidence: The constant currently combines canonical bucket aggregation, metric eligibility, calibration joins, derived soil moisture math, and cloud payload shape. The implementation should use named functions for projection behavior, with any SQL scoped inside those functions.

- Observation: Some frontend code is visual styling, not domain presentation config, and should stay in the frontend.
  Evidence: `web-ui/src/ui/Sparkline.tsx`, `web-ui/src/ui/Gauge.tsx`, and `web-ui/src/ui/MoistureComparisonChart.tsx` map semantic accents or sticker colors to Tailwind classes and implement chart interactions. The backend should send semantic accent names and metric config, not CSS class names.

## Decision Log

- Decision: Represent product-facing metric presentation as database rows seeded from source, not as frontend constants.
  Rationale: The gateway must filter rollups before upload, and the browser API must expose the same grouping and canonical metric names. A database-backed registry is inspectable and testable, while source-owned seed data keeps the config reviewed and repeatable instead of becoming mutable production state.
  Date/Author: 2026-05-31 / Codex

- Decision: Collapse stored/public metric aliases before adding the presentation registry.
  Rationale: A registry row that says "store `fan_duty_pct`, display `fan_pct`" preserves the architectural smell instead of removing it. The canonical product metric should be stored, synced, and requested by the same name. Use direct migrations and owned producer updates; do not add durable alias or compatibility layers.
  Date/Author: 2026-05-31 / Codex

- Decision: Normalize native actuator levels at the telemetry boundary, while keeping native hardware concepts inside controller code.
  Rationale: Hardware drivers need native values such as Govee mist level `0..9` and ThermoForge heat level `0..10`. The hosted product dashboard needs device-independent product telemetry such as `humidifier_intensity_pct` and `heater_intensity_pct`. The transform belongs near the producer that understands the native scale, not in the cloud browser API.
  Date/Author: 2026-05-31 / Codex

- Decision: Delete persisted native humidifier/heater level metric streams.
  Rationale: `humidifier_mist_level` and `heater_heat_level` are hardware-native implementation details, not product telemetry. Keeping them in `sensorreading` as diagnostic/internal rows would preserve parallel truths in the database. Structured HWD logs can retain native level details for debugging, while persisted readings use canonical product metrics.
  Date/Author: 2026-05-31 / Codex

- Decision: Canonical intensity metrics represent effective quantized output.
  Rationale: `humidifier_intensity_pct` and `heater_intensity_pct` are persisted readings and later control-loop feedback. They must be derived from the actual dispatched or observed native level, such as `target_level / 9 * 100` for Govee or `level * 10` for ThermoForge, not from raw requested PI/controller demand. Requested continuous demand belongs in logs.
  Date/Author: 2026-05-31 / Codex

- Decision: Treat `dehumidifier_on` as the canonical binary metric and `dehumidifier_runtime_pct` as a rollup presentation, unless implementation discovers the product truly wants latest state as 0/100 percent.
  Rationale: `dehumidifier_runtime_pct` is not a native latest state; it is an aggregation over time. Collapsing it into the latest metric would make the model less truthful.
  Date/Author: 2026-05-31 / Codex

- Decision: Quarantine soil moisture calibration as a legacy projection, not a general transform system.
  Rationale: `soil_moisture_raw + sensorcalibration -> soil_moisture_pct` is the only current calibration-table metric path and is likely to disappear when better soil moisture hardware emits normalized values. Keep it working today, but isolate it behind named projection functions so deleting it later does not disturb the canonical metric rollup path.
  Date/Author: 2026-05-31 / Codex

- Decision: Replace module-level rollup SQL blobs with named projection functions.
  Rationale: A constant named `_ROLLUP_SQL` hides domain policy and mixed responsibilities. SQL is fine for efficient bucket aggregation, but it should live inside functions with names like `collect_canonical_history_rollups()` and `collect_legacy_calibrated_soil_moisture_rollups()` so the architecture exposes what each projection does.
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

The control plane stores latest metrics and rollups in cloud tables defined in `apps/control-plane/src/dirt_control/models/cloud.py`. Browser routes live in `apps/control-plane/src/dirt_control/api/browser.py`. Current browser history uses `/api/tents/{tent_id}/metrics/history`, where `DISPLAY_METRIC_BY_PUBLIC` maps public names like `fan_pct` back to storage names like `fan_duty_pct`. This plan removes that alias layer by making product telemetry canonical before it reaches the cloud.

The hosted React dashboard lives in `web-ui/src/routes/index.tsx`. Today it defines the dashboard metric catalog itself:

- `CURRENT_METRIC_META` decides which current metrics become top cards.
- `HISTORY_METRIC_GROUPS` decides history sections, order, labels, units, accents, y-axis bounds, and which metric histories are fetched.
- `isIntegerMetric()` derives formatting from unit strings.
- `HISTORY_METRIC_META` is the frontend-owned query plan for `/metrics/history`.

The frontend also has local UI components. `web-ui/src/ui/Sparkline.tsx` and `web-ui/src/ui/Gauge.tsx` should continue to own CSS class mapping, geometry, hover behavior, and accessibility. They should not own the product-facing metric registry.

The metric model has three layers:

- Hardware command/state: device-native values that drivers and controllers need, such as ThermoForge heat level `0..10` or Govee mist level `0..9`.
- Local diagnostics: structured logs that preserve native details for debugging, such as commanded Govee target level or observed ThermoForge level. Do not persist native humidifier/heater levels as `sensorreading` rows in this plan.
- Product telemetry: canonical metric streams stored for dashboard/current/history use, such as `fan_pct`, `heater_intensity_pct`, `humidifier_intensity_pct`, `temperature_f`, `humidity_pct`, and `soil_moisture_pct`.

Transforms from native hardware state to product telemetry belong at the producer/storage boundary. Product intensity telemetry must represent effective quantized output, not raw requested demand. For example, if the humidifier controller requests `47%` but Govee dispatch quantizes that to level `4` of `9`, persist `humidifier_intensity_pct=44.4` and log the requested demand separately. If the ThermoForge controller requests about `36%` but dispatches heat level `4` of `10`, persist `heater_intensity_pct=40`. Native levels remain available in controller variables and structured logs, not as separate persisted readings.

The desired owner of dashboard presentation is a metric presentation registry stored in both local and cloud databases. The local database copy lets the gateway filter rollups before upload. The cloud copy lets the browser API expose presentation groups and validate canonical metric requests. Seed rows are source-owned through migrations or an idempotent seed module, so the configuration is reviewed with code and safe to recreate.

Soil moisture calibration is the one accepted derived-metric exception in this plan. Treat it as a quarantined legacy adapter for current plant nodes, not as a pattern for other metrics. The adapter derives `soil_moisture_pct` from local `soil_moisture_raw` readings and `sensorcalibration` rows. It should be the only gateway/control-plane place that knows about the calibration table. The general rollup path should not know calibration exists.

When future soil moisture sensors emit calibrated moisture directly, deleting the legacy adapter should be the only gateway projection cleanup required. At that point `soil_moisture_pct` should flow through the canonical metric path like reservoir or climate metrics.

Recommended registry fields:

- `metric`: canonical product metric name stored locally, synced to cloud, and requested by the browser, such as `fan_pct`.
- `display_name`: label such as `Fan`.
- `unit`: display unit, such as `%`.
- `accent`: semantic visual category from `temp`, `humidity`, `vpd`, `moisture`, `reservoir`, or `neutral`.
- `value_precision`: number of decimals the frontend should display.
- `y_min` and `y_max`: optional fixed chart domain.
- `current_enabled`: whether the metric appears as a current dashboard card.
- `history_enabled`: whether rollup history is synced and exposed for dashboard history.
- `dashboard_group`: nullable group key for dashboard history.
- `dashboard_group_label`: visible group label such as `Temperature Loop`.
- `dashboard_group_order`: order of groups.
- `display_order`: order inside current cards or a group.

The first seed set should reproduce the current dashboard's useful metrics while excluding raw/internal diagnostics from history. It should include history rows for `temperature_f`, `heater_intensity_pct`, `fan_pct`, `humidity_pct`, `humidifier_intensity_pct`, `vpd_kpa`, `reservoir_in`, and `reservoir_ph`. It should include `soil_moisture_pct` if and only if the dashboard should show plant/water moisture history; it must not include `soil_moisture_raw` as history-enabled. For the dehumidifier, store the canonical binary stream as `dehumidifier_on`; the browser history DTO may label the rollup aggregate as `dehumidifier_runtime_pct` because bucket average of a binary state is runtime percentage.

## Plan of Work

Milestone 1: Canonicalize product metric names at the producer/storage boundary.

Update source-owned producers, capability seeds, local data, cloud data, tests, and docs so product telemetry uses one canonical metric name across storage, sync, API, and frontend. Do this before adding the registry so the registry does not encode alias pairs.

Rename `fan_duty_pct` to `fan_pct` as the canonical product fan metric. This includes firmware in `firmware/fan_controller/`, ingest capability mappings such as `apps/shared/src/dirt_shared/sensor_contract.py`, local capability seed migrations or new direct migration updates, tests, docs, local `sensorreading` rows, `cloud_latest_metric`, and `cloud_metric_rollup`.

Normalize humidifier and heater product telemetry at the HWD producer boundary. Controller/driver code may keep native command/state values, but persisted product telemetry should be `humidifier_intensity_pct` and `heater_intensity_pct`. Those persisted intensity values must be computed from the effective quantized target or observed level, not from raw requested demand. Delete persisted `humidifier_mist_level` and `heater_heat_level` streams from producer code, capability seeds, tests, local data, and cloud data. Preserve native level observability and requested continuous demand in structured logs, such as Govee `requested_u_pct` plus `target_level`, and ThermoForge requested heat percent plus dispatched or observed level.

Update climate-controller state reconstruction so it no longer reads native persisted levels. Read `humidifier_intensity_pct` directly for `current_humidifier_pct`. Read `heater_intensity_pct` and convert to the native ThermoForge level inside HWD when the allocator needs `current_heater_level`, for example `round(intensity_pct / 10)` with the same clamping rules used when dispatching levels.

Keep `dehumidifier_on` as the canonical stored latest/state metric. Add explicit rollup/presentation handling so history can show runtime percentage from bucket averages without pretending `dehumidifier_runtime_pct` is a native latest metric.

Directly migrate owned historical local and cloud data. Do not add compatibility reads from old metric names. After this milestone, searches for the old product aliases should show only migration history, intentionally diagnostic code, or historical docs.

Milestone 2: Add a backend metric presentation registry.

Add SQLModel models for local and cloud registry rows. The local model belongs under `apps/shared/src/dirt_shared/models/` because the gateway reads it from the local database. The cloud model belongs in `apps/control-plane/src/dirt_control/models/cloud.py` because browser routes query the Railway database. Add Atlas migrations in both `migrations/` and `cloud/migrations/`.

Seed the rows from source-owned SQL or an idempotent seed helper. The seed must be safe to run repeatedly and should use upserts. The registry must be small and explicit; do not infer product-facing metrics from all capabilities. Add tests proving that raw/internal diagnostic streams are not `history_enabled`, especially `soil_moisture_raw`, and that calibrated `soil_moisture_pct` is the product-facing moisture metric.

Milestone 3: Make the control plane expose presentation config.

Remove `DISPLAY_METRIC_BY_STORAGE` and `DISPLAY_METRIC_BY_PUBLIC` after canonical metric names are migrated. Add Pydantic browser DTOs in `apps/control-plane/src/dirt_control/api/browser.py` for a presentation endpoint, for example `GET /api/tents/{tent_id}/metrics/presentation`.

The endpoint should return ordered current metrics, ordered history groups, and supported ranges. It should include canonical metric names, labels, units, semantic accents, y-axis bounds, value precision, and display order. The frontend should not need to know old storage aliases or hardware-native metric names.

Milestone 4: Filter gateway rollup projection from the same registry.

Update `apps/gateway/src/dirt_gateway/local.py` so the general rollup projection includes only `history_enabled` canonical metrics from the local registry. Replace the module-level `_ROLLUP_SQL` constant with named projection functions. The general function should aggregate canonical readings only; it should not contain calibration joins, `UNION ALL`, or soil moisture exceptions.

Add a separate, plainly named legacy projection function for current calibrated plant moisture, for example `collect_legacy_calibrated_soil_moisture_rollups()`. That function may use SQL internally, but it owns the whole temporary exception: read `soil_moisture_raw`, join `sensorcalibration`, derive `soil_moisture_pct`, and emit rows only when the registry has `soil_moisture_pct` history-enabled. Do not add a generic metric transform framework for this one case.

The filter must fail closed. If no `history_enabled` registry rows exist, `collect_rollups()` should return no rollups or raise a clear local configuration error that prevents upload; it must not send every metric.

Milestone 5: Cut the frontend over to backend-owned presentation.

Regenerate the hosted OpenAPI types with `scripts/gen-hosted-contract`. In `web-ui/src/routes/index.tsx`, fetch the new presentation endpoint with TanStack Query, use its current metrics to build cards, and use its history groups to build `/metrics/history` queries.

Delete `MetricMeta`, `MetricGroup`, `CURRENT_METRIC_META`, `HISTORY_METRIC_GROUPS`, `HISTORY_METRIC_META`, and `isIntegerMetric()`. Replace unit-derived integer formatting with backend `value_precision`. Keep `asAccent()` or an equivalent local guard so unknown semantic accents render as `neutral`. Keep `Sparkline`, `Gauge`, and `MoistureComparisonChart` as visual components.

Milestone 6: Remove dead code and tighten contracts.

After the frontend and backend use the registry, remove obsolete display maps from `browser.py` if they were replaced by registry lookups. Search for stale metric presentation constants and old transform paths. Do not leave unused DTOs, fallback constants, or dual code paths.

Add contract and boundary tests for the new DTOs. `web-ui/src/api-client/cloud.ts` must continue to consume generated types, not handwritten hosted response interfaces.

Milestone 7: Prove the payload is smaller and deploy.

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

Update product metric producers before relying on the registry. This includes the fan controller firmware payload, HWD telemetry writes for humidifier and heater intensity, sensor contract mappings, capability seed data, and direct data migrations for local and cloud metric tables. Search before and after the migration work:

    rg -n "fan_duty_pct|humidifier_mist_level|heater_heat_level|DISPLAY_METRIC_BY_STORAGE|DISPLAY_METRIC_BY_PUBLIC" apps web-ui firmware docs migrations cloud -S

Expected result after implementation: old product names remain only in historical migrations/docs or comments explaining the direct migration. `humidifier_mist_level` and `heater_heat_level` must not remain as active persisted reading streams, cloud/browser alias maps, or gateway rollup inputs. Native level values may remain as local variable names, driver command concepts, and structured log fields.

Create the local and cloud registry models and migrations after the canonical metric cutover is defined. Use Atlas commands from `docs/database.md`; do not hand-edit generated Atlas metadata incorrectly. After migrations exist, run the migration lint commands documented there.

Refactor gateway rollup collection into named functions. Keep SQL where it is the right tool for bucket aggregation, but keep each SQL query scoped inside the function that names its domain responsibility. The expected shape is:

    async def collect_canonical_history_rollups(...): ...
    async def collect_legacy_calibrated_soil_moisture_rollups(...): ...

`collect_rollups()` should compose those functions into the `RollupsRequest`. It should not execute a single broad `_ROLLUP_SQL` constant that combines canonical aggregation and legacy calibration.

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
- Browser API tests prove canonical metrics such as `fan_pct`, `humidifier_intensity_pct`, and `heater_intensity_pct` are stored, synced, requested, and returned by the same name. They also prove dehumidifier history can present bucketed `dehumidifier_on` averages as runtime percentage without making `dehumidifier_runtime_pct` a latest/state metric.
- Frontend typecheck and tests pass using generated hosted contract types.
- `rg -n "CURRENT_METRIC_META|HISTORY_METRIC_GROUPS|MetricMeta|MetricGroup|HISTORY_METRIC_META|isIntegerMetric" web-ui/src` returns no dashboard-owned metric registry.
- `rg -n "DISPLAY_METRIC_BY_STORAGE|DISPLAY_METRIC_BY_PUBLIC" apps/control-plane/src` returns no obsolete split registry.
- `rg -n "fan_duty_pct|humidifier_mist_level|heater_heat_level" apps/control-plane apps/gateway web-ui firmware apps/shared/src/dirt_shared/sensor_contract.py` returns no product telemetry dependency on the old names.
- HWD tests prove humidifier and heater producers persist `humidifier_intensity_pct` and `heater_intensity_pct`, not `humidifier_mist_level` or `heater_heat_level`.
- HWD tests prove persisted intensity readings are effective quantized output. For humidifier, a request that quantizes to level `4` of `9` persists approximately `44.4`, not the raw requested percent. For heater, a dispatched or observed level `4` persists `40`.
- Climate-controller tests prove actuator state reconstruction reads canonical percent metrics and converts heater intensity back to native ThermoForge level only inside HWD decision/dispatch code.
- Gateway tests prove canonical rollup collection uses registry-enabled canonical metrics without calibration joins or soil moisture-specific `UNION ALL`.
- Gateway tests prove calibrated soil moisture rollups are produced only by the legacy projection, only as `soil_moisture_pct`, and only when `soil_moisture_pct` is history-enabled. `soil_moisture_raw` is not synced to hosted rollups.
- `rg -n "_ROLLUP_SQL|_LATEST_METRICS_SQL" apps/gateway/src/dirt_gateway/local.py` returns no broad module-level projection SQL constants. Small SQL strings scoped inside named functions are acceptable.
- A local projection or debug SQL transcript shows history-enabled rollups exclude raw/internal streams and the payload is smaller than the incident path that sent every metric.
- In the browser, the dashboard still shows current cards and the three history groups, but those groups come from the backend endpoint.

## Idempotence and Recovery

Registry seed operations must be idempotent upserts. Re-running migrations in a fresh local or cloud database should produce the same registry rows.

Metric canonicalization migrations are direct cutovers. They should update owned local and cloud rows in place and update capability seeds so new readings use the canonical names. They should be safe to reapply only through normal Atlas migration guarantees, not through runtime compatibility code.

Deleting native level persistence means removing active capability rows and historical local/cloud metric rows for `humidifier_mist_level` and `heater_heat_level`, after the canonical percent streams exist. Keep native level information in logs. Do not add a diagnostic metric table or hidden persistence path in this plan.

Gateway filtering must be fail-closed. If the local registry is missing, the gateway must not upload all rollup streams. It may upload zero rollups with a clear log event or raise a clear configuration error. Tests should protect this behavior.

The legacy soil moisture projection must also fail closed. If `soil_moisture_pct` is missing from the registry or disabled for history, it emits no rows. If calibration is missing or degenerate for a plant node, it skips that derived stream and should not emit raw moisture as a fallback.

The frontend cutover is intentionally not backward-compatible with an API that lacks the presentation endpoint. During deployment, use `scripts/deploy-control-plane` so the cloud migration and API deploy happen before the web UI deploy. If deployment fails after the API migration but before the web UI deploy, the old web UI can keep using existing endpoints until the new deploy is retried. If deployment fails after the new web UI deploy, roll back using the hosted deployment process in `docs/hosted-control-plane.md`.

The fan firmware update is part of the cutover. If the firmware cannot be updated at the same time as the ingest contract, pause implementation rather than adding an ingest compatibility shim. This is source-owned hardware in this repo, so keeping the house tidy is more important than preserving old payload names.

Do not reset gateway rollup cursors as part of this plan unless validating a one-time production recovery. Normal sync should resume with smaller future projections after the gateway has canonical metrics and the registry filter.

## Artifacts and Notes

Frontend audit evidence from 2026-05-31:

- `web-ui/src/routes/index.tsx` contains frontend-owned `CURRENT_METRIC_META`, `HISTORY_METRIC_GROUPS`, `HISTORY_METRIC_META`, `asAccent()`, and `isIntegerMetric()`.
- `web-ui/src/routes/index.tsx` maps `HISTORY_METRIC_META` into one `/api/tents/{tent_id}/metrics/history` query per metric.
- `apps/control-plane/src/dirt_control/api/browser.py` contains `DISPLAY_METRIC_BY_STORAGE` and `DISPLAY_METRIC_BY_PUBLIC`, which are partial backend display mappings.
- `apps/gateway/src/dirt_gateway/local.py` currently filters rollup base rows only by `c.metric_name IS NOT NULL` and then unions calibrated `soil_moisture_pct`.
- `sensorcalibration` is only part of the current soil moisture path. It should be quarantined behind the legacy calibrated soil moisture projection rather than shaping the general rollup architecture.
- `firmware/fan_controller/src/main.cpp` currently emits `fan_duty_pct`; this should become `fan_pct` during the canonical metric cutover.
- HWD currently records native actuator metrics such as `humidifier_mist_level` and `heater_heat_level`, and the climate controller reads those persisted streams back. The plan deletes those persisted native streams, records percent intensity product telemetry instead, and keeps native level details in structured logs and controller variables.
- The persisted percent intensity must be the quantized effective output. Raw requested control demand remains observable through logs, not through current-state readings.

Production incident context that motivated the plan:

- Five-minute rollup sync attempted to send a very large payload containing thousands of rows across all metrics.
- The payload included streams that are useful for diagnostics but not useful for hosted dashboard history.
- The immediate bug is payload size; the architectural smell is duplicated and misplaced ownership of "what is product-facing metric history."

## Interfaces and Dependencies

New or changed interfaces expected at completion:

- Local SQLModel registry model under `apps/shared/src/dirt_shared/models/`, backed by a migration in `migrations/`.
- Cloud SQLModel registry model in `apps/control-plane/src/dirt_control/models/cloud.py`, backed by a migration in `cloud/migrations/`.
- Registry lookup helpers used by the gateway and control-plane browser routes. The helper may live in a shared Python module if it contains source-owned seed definitions, but the runtime filtering and browser presentation should read database rows.
- Browser route `GET /api/tents/{tent_id}/metrics/presentation` with generated OpenAPI types consumed by `web-ui/src/api-client/generated/hosted-schema.ts`.
- Pydantic browser DTOs for metric presentation groups, presentation metric rows, and supported ranges.
- Gateway rollup projection that filters by local registry `history_enabled`.
- Legacy calibrated soil moisture projection function that derives `soil_moisture_pct` from `soil_moisture_raw` plus `sensorcalibration`, isolated from the canonical rollup path and documented as removable tech debt.
- Control-plane metric history route that validates canonical metric names against the cloud registry. It should not map browser aliases to different stored metric names.
- Frontend dashboard code that consumes generated presentation DTOs and no longer owns domain metric groups or display metadata.

No new external package dependency is expected for this plan.

## Revision Notes

- 2026-05-31: Initial ExecPlan created after auditing hosted dashboard frontend presentation smells and the gateway/control-plane rollup path.
- 2026-05-31: Revised the design to collapse stored/public metric aliases before adding the presentation registry. Native actuator levels remain hardware/controller details or log fields; product telemetry is normalized at the producer/storage boundary.
- 2026-05-31: Revised the native actuator decision to delete persisted `humidifier_mist_level` and `heater_heat_level` streams. Native levels remain in HWD controller/driver logic and structured logs; persisted readings use percent intensity.
- 2026-05-31: Clarified that persisted `humidifier_intensity_pct` and `heater_intensity_pct` are effective quantized output, not raw requested demand, so the climate loop's feedback model remains truthful.
- 2026-05-31: Quarantined calibrated soil moisture as a disposable legacy projection and directed implementation away from broad module-level rollup SQL constants toward named projection functions.
