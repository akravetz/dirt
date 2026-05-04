# Phase 1 Multi-Tent Local Controller Model

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt can model one physical local controller site with more than one logical grow tent. The current production grow remains the default `site_id=homebox` and `tent_id=main`; a second `tent_id=breeding` can exist in the database, API, and service model without running a second backend, duplicating hardware daemons, or making any cloud service the hardware authority.

The visible result is that the existing dashboard, ingest endpoint, control loops, daily report, and local API still behave exactly as they do for the current tent when no scope is specified, while tests and new scoped service/API reads can prove that telemetry, devices, grow runs, plants, schedules, photos, alerts, and command intent records can be associated with either the default main tent or the new breeding tent.

This is not the hosted website phase. The local `dirt-hwd` service remains the only process that executes hardware actions. Future hosted frontend/backend work may read cloud-visible state or submit command intent, but command execution and reconciliation stay local.


## Progress

- [x] (2026-05-03 23:45Z) Read required operating documents: `AGENTS.md`, `.agents/PLANS.md`, `docs/commands.md`, `docs/database.md`, `docs/grow-state.md`, and `docs/observability.md`.
- [x] (2026-05-03 23:45Z) Investigated current models, migrations, services, API routes, generated contracts, frontend routes/components, hardware loops, daily report paths, PTZ/camera code, firmware ingest identity, and read-only live schema shape.
- [x] (2026-05-03 23:45Z) Created this de novo ExecPlan at `docs/epics/multi-tent-controller/ExecPlan.md` without opening or relying on prior planning files.
- [x] (2026-05-04 00:09Z) Implemented Milestone 1: added canonical scoped identity SQLModel classes, generated/reviewed the Atlas migration, seeded `homebox/main/breeding` identity rows plus current main-tent zones/devices/capabilities, and validated schema replay.
- [x] (2026-05-04 01:31Z) Implemented Milestone 2: moved current grow semantics from `growstate` to scoped `growrun`, migrated `plant` from `growstate_id` to `growrun_id` plus `site_id`/`tent_id`/`plant_id`, added default scope helpers, preserved unscoped main-tent API behavior, and validated migration replay.
- [x] (2026-05-04 01:44Z) Implemented Milestone 3: moved telemetry ingest and read paths to scoped device/capability ownership, with default main-tent compatibility preserved.
- [x] (2026-05-04 02:34Z) Implemented a coherent Milestone 4 checkpoint: scoped grow/schedule service methods, empty breeding plant reads, capability-owned sensor calibrations, scoped periodic snapshots, and stable alert state keys for device/metric watchdogs.
- [x] (2026-05-04 02:40Z) Completed the Milestone 4 daily-report photo follow-up: daily captures now write scoped `snapshot.kind='daily_report'` rows for `overview` and `plant_a` through `plant_d`, and `scripts/daily_report` wires the production recorder.
- [x] (2026-05-04 03:01Z) Implemented Milestone 5: hardware-control loops now explicitly target `homebox/main`, PTZ user commands record local command lifecycle rows, and system status is backed by canonical `device` rows while preserving the current dashboard device set.
- [x] (2026-05-04 03:09Z) Implemented Milestone 6: added minimal scoped site/tent/device read APIs, regenerated contract clients, preserved unscoped default-main API behavior, and validated frontend compatibility without adding visible hosted/cloud UI.


## Surprises & Discoveries

- Observation: The current telemetry identity is a fixed Postgres enum, not a general device model. `SensorNode.location` is unique over the `sensor_location` enum values `tent`, `plant-a`, `plant-b`, `plant-c`, `plant-d`, and `reservoir`.
  Evidence: `apps/shared/src/dirt_shared/models/enums.py`, `apps/shared/src/dirt_shared/models/sensor_node.py`, and read-only `psql \d sensornode` show `location sensor_location NOT NULL UNIQUE`.

- Observation: `growstate` is already multi-row capable but still has global singleton semantics because only one row can be `is_current=true`.
  Evidence: `apps/shared/src/dirt_shared/models/grow_state.py` defines partial unique index `ux_growstate_is_current` on `is_current = true`, and `GrowStateService.get_state()` always selects the first current row without a tent scope.

- Observation: Plants are current-grow scoped but still assume a single current grow in every service/API call, and the public contract only allows `PlantCode` values `a`, `b`, `c`, and `d`.
  Evidence: `apps/shared/src/dirt_shared/services/plants.py` selects `GrowState.is_current == true`; `contracts/webapp-v1.yaml` defines `PlantCode: [a, b, c, d]`; `web-ui/src/ui/plant-types.ts` mirrors that exact union.

- Observation: Sensor history is unsafe for multi-tent metric names because `ReadingsService.get_metric_history()` filters only by metric name, not by location/device/scope.
  Evidence: `apps/shared/src/dirt_shared/services/readings.py` says the assumption is that each emitted metric comes from exactly one node; this fails once two tents both emit `temperature_f`, `humidity_pct`, or `soil_moisture_raw`.

- Observation: The hardware execution boundary is already local and should be preserved. `dirt-hwd` owns ingest plus background loops for capture, archive, humidifier, lights, fan trim, device watchdog, and metric freshness.
  Evidence: `apps/hwd/src/dirt_hwd/app.py:_default_background_services()` wires all hardware-touching services; `apps/web/src/dirt_web/app.py` only serves API/UI/MCP and PTZ facade calls.

- Observation: Firmware currently bakes logical location strings into each device image.
  Evidence: `firmware/fan_controller/src/main.cpp` uses `LOCATION = "tent"`, `firmware/plant_node/src/main.cpp` uses `LOCATION = "plant-" PLANT_ID`, and `firmware/reservoir_node/src/main.cpp` uses `LOCATION = "reservoir"`.

- Observation: Photos are split between database-backed periodic `snapshot` rows and filesystem-only daily report photos.
  Evidence: `apps/shared/src/dirt_shared/models/snapshot.py` only has `ts` and `file_path`; `apps/shared/src/dirt_shared/services/daily_report.py` writes daily photos under `raw/photos/<DATE>/` without DB rows.

- Observation: Device status and alert state keys are human display names or legacy location strings, not stable device identifiers.
  Evidence: `apps/shared/src/dirt_shared/services/system_status.py` hardcodes the eight-row device list; `apps/hwd/src/dirt_hwd/services/device_watchdog.py` persists `state.json` keyed by `DeviceStatus.name`; `metric_freshness.py` persists keys like `<location>:<metric>`.

- Observation: The installed Atlas CLI reports that `atlas migrate lint` is now Atlas Pro-only, despite the local reference pack describing it as available in the community CLI.
  Evidence: `atlas migrate lint --env local --latest 1` exited 1 with `Starting with v0.38, 'atlas migrate lint' is available only to Atlas Pro users.` Validation used `atlas migrate diff verify_multi_tent_sync --env local` plus pytest migration replay instead.

- Observation: Atlas generated the Milestone 2 diff as an unsafe single `ALTER TABLE plant DROP COLUMN growstate_id, ADD COLUMN ... NOT NULL` statement.
  Evidence: Generated `20260504012912_scoped_growrun_plants.sql` would have added non-null `site_id`, `tent_id`, `growrun_id`, and `plant_id` to a table with existing rows before backfill. The migration was hand-authored as a forward Atlas migration: add nullable columns, backfill from `growstate`/`growrun`, set `NOT NULL`, add constraints/indexes, then drop `growstate`.

- Observation: Atlas generated the Milestone 3 structural change, but the operational migration still needed hand-authored seed and backfill SQL.
  Evidence: `20260504013944_scoped_sensorreading_capabilities.sql` adds `sensorreading.capability_id`, seeds transitional `soil_moisture_pct` capabilities for plant nodes, backfills existing readings from legacy `sensornode.location` plus `metric`, and creates the capability history index.

- Observation: Async raw SQL with optional scoped filters needs explicit parameter casts for PostgreSQL/asyncpg.
  Evidence: Raw bucket queries using `:tent_id IS NULL` produced ambiguous-parameter errors until the optional filters used `CAST(:tent_id AS text)` style predicates.

- Observation: `sensorcalibration` was originally keyed by legacy `sensornode_id`/`metric`, and the plan had listed that as pending without assigning it to a milestone.
  Evidence: Milestone 4 moved calibration reads to `capability_id`; the later legacy cleanup retired `SensorCalibration.sensornode_id` entirely.

- Observation: Capability-only calibration rows required a transition period before the legacy FK could be removed.
  Evidence: A breeding-tent moisture capability cannot have a distinct legacy `sensornode` because `SensorLocation` is a fixed enum. Milestone 4 made `sensornode_id` nullable while preserving the legacy lookup; the later legacy cleanup removed it after capability ownership replaced the compatibility path.

- Observation: PostgreSQL `UPDATE ... FROM` cannot reference the target alias inside a joined table's `ON` predicate.
  Evidence: The first test migration replay failed with `pq: invalid reference to FROM-clause entry for table "sc"` until the calibration backfill moved `c.metric_name = sc.metric` into the `WHERE` clause.

- Observation: Once a scoped `schedule` row exists, tests and write paths that only update grow-run photoperiod columns can leave lights reads stale.
  Evidence: `GrowStateService.lights_state()` now reads the scoped schedule projection. The later legacy cleanup removed the grow-run photoperiod columns and makes `flip_to_flower()` write the schedule row directly.

- Observation: Daily-report photos reuse deterministic file paths for a target date, so DB recording must be idempotent for forced reruns.
  Evidence: `DailyReportSnapshotRecorder.record_daily_report_photo()` selects by `snapshot.file_path` and updates the existing row instead of blindly inserting, preserving the unique `snapshot.file_path` constraint.

- Observation: Daily-report DB metadata can be added without changing existing orchestrator tests by making the recorder an optional dependency.
  Evidence: `DailyReport.__init__()` now accepts `snapshot_recorder=None`; existing filesystem/Telegram tests still construct the orchestrator without DB access, while production `scripts/daily_report` passes `DailyReportSnapshotRecorder(engine)`.

- Observation: Milestone 5 did not require a schema migration because the `command` table already existed from Milestone 1.
  Evidence: `apps/shared/src/dirt_shared/models/command.py` already matched the required command lifecycle columns, and `atlas migrate diff verify_scoped_milestone5_sync --env local` reported the migration directory synced.

- Observation: Running two pytest commands in parallel from the same worktree can break the shared Postgres template fixture.
  Evidence: A parallel validation run failed with `atlas migrate apply failed for template ... driver: bad connection`; rerunning the same failing pytest command serially passed with `16 passed`.

- Observation: New tests for system status and lights initially used `monkeypatch.setattr()` against `dirt_*` modules, which violates repository invariants.
  Evidence: `uv run pytest apps/tests/invariants/ -q` failed in `test_no_patching_production_code`; the production services were refactored to accept injected `camera_rpc`, `service_active_check`, and `discover_single` seams, then invariants passed.

- Observation: The canonical `device` table contains hardware not historically displayed in `/api/system/devices`, including `reservoir-node` and `kasa-lights-main`.
  Evidence: Milestone 5 keeps the current eight-row dashboard status projection while sourcing row identity/name/scope from `device`, so `reservoir-node` and `kasa-lights-main` remain modeled but not newly surfaced by the existing endpoint.

- Observation: Milestone 6 did not require schema changes; the missing piece was API/contract exposure for identity rows already created by earlier milestones.
  Evidence: `atlas migrate diff verify_scoped_milestone6_sync --env local` reported the migration directory synced.

- Observation: Scoped current-grow responses can violate the existing `GrowCurrent` contract if test or future seed data creates a current grow with a germination date after the service clock's local date.
  Evidence: The first Milestone 6 test fixture used `germination_date=2026-05-04` while the test clock could still resolve to 2026-05-03 local, producing `day_number=0`; the fixture was changed to `2026-05-01`.

- Observation: `scripts/gen-contract` regenerates `web-ui/src/api-client/generated/schema.ts` but does not apply the frontend formatter.
  Evidence: `pnpm --dir web-ui lint` failed on Biome formatting for the generated schema until `pnpm --dir web-ui exec biome check --write src/api-client/generated/schema.ts` was run.

- Observation: The new scoped tent device endpoint intentionally exposes all canonical devices assigned to `homebox/main`, including `reservoir-node` and `kasa-lights-main`, while the existing dashboard endpoint remains the historic eight-row projection.
  Evidence: `apps/web/tests/test_scope_endpoints.py` asserts `/api/tents/main/devices` includes those canonical devices and excludes site-level `jabra-claudia`; existing `/api/system/devices` tests still pass unchanged.


## Decision Log

- Decision: Use `tent_id`, not `tenant_id`, and model this as one local site controller managing multiple logical tents.
  Rationale: This is not SaaS tenancy or a fleet architecture. The user explicitly called out one physical box and one physical installation for now.
  Date/Author: 2026-05-03 / Codex

- Decision: Introduce canonical scoped identity tables for `site`, `tent`, `zone`, `device`, `capability`, and `growrun` instead of widening the existing `SensorLocation` enum.
  Rationale: The enum encodes the current grow layout and cannot safely represent multiple tents with duplicate metric names. Canonical tables let new tents and devices be data, not code or enum migrations.
  Date/Author: 2026-05-03 / Codex

- Decision: Preserve current unscoped API and service behavior as default-main-tent compatibility during Phase 1.
  Rationale: The production system controls real hardware. Existing local behavior must continue working while internals gain scope. Compatibility is implemented at boundaries by resolving missing scope to the default `homebox/main` records.
  Date/Author: 2026-05-03 / Codex

- Decision: Do not make cloud, Vercel, or remote execution part of this phase.
  Rationale: The remodel is prerequisite local architecture work. Remote command submission requires auth, public exposure, replay protection, audit policy, and network design that should not be mixed into the local data-model change.
  Date/Author: 2026-05-03 / Codex

- Decision: Add a local command-intent ledger now, but only execute commands from local code paths.
  Rationale: Dirt already has actuator APIs and loops: PTZ movement, fan `/fan`, Govee humidifier control, and Kasa lights. A command ledger with idempotency and lifecycle states prevents future remote control from being bolted on without replay/audit semantics.
  Date/Author: 2026-05-03 / Codex

- Decision: Drop the legacy `growstate` table in Milestone 2 after backfilling `growrun`.
  Rationale: Keeping both tables would preserve two possible sources of truth for stage, photoperiod, strain, location, and plant count. The cleaner Phase 1 target is `growrun` with per-tent current semantics; compatibility remains in the `GrowStateService` class name and unscoped API defaults, not in a duplicate table.
  Date/Author: 2026-05-04 / Codex

- Decision: Complete daily-report photo DB rows as a focused Milestone 4 follow-up after the first checkpoint.
  Rationale: Periodic snapshots carried scope and were backfilled in the first checkpoint. Adding daily-report DB rows required widening `DailyReport` construction to accept a database writer in addition to its existing injected camera/sensor/synthesis/telegram collaborators, so it was implemented as a focused follow-up with daily-report tests rather than mixed into the larger calibration/schedule/alert change.
  Date/Author: 2026-05-04 / Codex

- Decision: Keep `/api/system/devices` on the current eight visible rows for Milestone 5 while backing those rows from canonical `device` records.
  Rationale: `reservoir-node` and `kasa-lights-main` are now modeled devices, but surfacing extra dashboard rows is a UI/API behavior change better handled with Milestone 6 compatibility work. Milestone 5 proves the stable identity path without changing the visible system table shape.
  Date/Author: 2026-05-04 / Codex

- Decision: Add new scoped read endpoints instead of adding scope query parameters to the existing dashboard endpoints.
  Rationale: Phase 1 requires current unscoped dashboard workflows to stay default-main compatible. New read-only endpoints prove the multi-tent model without changing existing React Query keys, dashboard payloads, or user-visible UI.
  Date/Author: 2026-05-04 / Codex


## Outcomes & Retrospective

Milestone 1 completed on 2026-05-04. The repository now has canonical scoped identity tables for site, tent, zone, device, capability, grow run, schedule, and command intent. The migration seeds `site.site_id='homebox'`, `tent.tent_id='main'`, `tent.tent_id='breeding'`, main-tent zones, and current local hardware/capability mappings without changing existing singleton service behavior.

Milestone 2 completed on 2026-05-04. The current main grow is now represented as `growrun.grow_run_id='main-2026-03-15'` under `homebox/main`, and current plants A-D are linked by `plant.growrun_id` with stable `plant_id` values. Existing unscoped grow and plant endpoints still resolve to the default main tent. A test also proves a current breeding grow run can be inserted without changing the default main grow payload.

Milestone 3 completed on 2026-05-04. Sensor readings now carry a nullable `capability_id` FK while retaining `sensornode_id` for legacy firmware and calibration compatibility. Readings ingest accepts optional scoped identity fields, legacy `location` payloads still resolve to default-main devices, and history/latest/freshness reads use capability/device/tent joins so a breeding-tent `temperature_f` reading does not leak into default main dashboard history.

Milestone 4 checkpoint completed on 2026-05-04. Grow stage/target/light-schedule methods accept default-main or explicit scope, and the main photoperiod is materialized in `schedule`. Plant reads remain default-main compatible and an empty breeding tent returns no plants. Sensor calibrations now have nullable canonical `capability_id` ownership and can represent a capability-only breeding calibration without contaminating main plant moisture or daily sensor summaries. Periodic snapshots now write/backfill default-main camera/grow scope. `device_watchdog` state keys by stable `device_id`, and `metric_freshness` keys by stable `capability_id`. Residual humidifier/fan/lights control-loop event scoping is folded into Milestone 5 with the rest of hardware-control-loop scoping.

Milestone 4 daily-report follow-up completed on 2026-05-04. The daily-report capture phase now optionally records each saved photo as a scoped `snapshot` row with `kind='daily_report'`, `view_id` equal to the existing preset (`overview`, `plant_a`, `plant_b`, `plant_c`, `plant_d`), default `homebox/main` scope, `device_id='obsbot-main'`, the current main `growrun`, and zone mapping `overview -> canopy`, `plant_a -> plant-a`, `plant_b -> plant-b`, `plant_c -> plant-c`, and `plant_d -> plant-d`. The production `scripts/daily_report` entrypoint wires the recorder. Broader humidifier/fan/lights control-loop `log_event()` scoping remains Milestone 5 because that milestone owns hardware-control loops.

Milestone 5 completed on 2026-05-04. `HumidifierLoopService`, `FanTrimLoopService`, and `LightsLoopService` now carry explicit default `homebox/main` scope, use scoped grow/sensor reads, and emit scoped control-loop log fields. `SystemStatusService` now projects the existing dashboard rows from canonical `device` records and scoped freshness/probe sources. `CommandService` provides idempotent local command enqueue/start/succeed/fail lifecycle, rejects non-local command sources, and PTZ preset/look/zoom calls record scoped local command rows against `obsbot-main`/`ptz_move` while preserving the existing PTZ endpoint responses.

Milestone 6 completed on 2026-05-04. The local web API now exposes read-only scoped catalog endpoints: `GET /api/sites`, `GET /api/tents`, `GET /api/tents/{tent_id}/grow/current`, and `GET /api/tents/{tent_id}/devices`. Existing unscoped endpoints remain default-main views, including `/api/grow/current` and `/api/system/devices`. The OpenAPI contract and generated Python/TypeScript clients include the new schemas. The frontend remains visually unchanged and default-main compatible; generated TypeScript typecheck, lint, and tests pass.


## Context and Orientation

Dirt is a uv Python workspace with shared SQLModel models and services under `apps/shared/src/dirt_shared/`, a hardware daemon under `apps/hwd/`, a local web/API service under `apps/web/`, generated OpenAPI clients under `contracts/` and `web-ui/src/api-client/`, a Vite/React frontend under `web-ui/`, and ESP32 firmware under `firmware/`.

The current database shape is centered on these tables:

- `sensornode`: one row per `SensorLocation` enum value. It currently acts like a device table but only knows `location`, IP/firmware/uptime, and `last_seen`.
- `sensorreading`: append-only fact table keyed by `sensornode_id`, `metric`, `value`, and `source`.
- `growrun`: scoped grow identity, photoperiod, timezone, strain/location text, plant count, and per-tent current flag.
- `plant`: one row per A-D plant in the current main grow, linked to `growrun`, explicit `site`/`tent` scope, a stable `plant_id`, and a moisture `sensornode`.
- `sensorcalibration`: capability-owned calibration rows with nullable legacy `sensornode_id` for firmware compatibility.
- `snapshot`: periodic and daily-report camera image metadata with nullable site/tent/zone/device/growrun/view/kind scope fields.

The current service ownership is:

- Grow stage, lights schedule, and target bands: `apps/shared/src/dirt_shared/services/grow_state.py`.
- Sensor ingest/query/calibration: `apps/shared/src/dirt_shared/services/readings.py` and `apps/hwd/src/dirt_hwd/api/ingest.py`.
- Sensor contract: `apps/shared/src/dirt_shared/sensor_contract.py`.
- Plant listing/detail/moisture: `apps/shared/src/dirt_shared/services/plants.py` and `plant_detail.py`.
- Periodic snapshots and daily photos: `capture.py`, `snapshots.py`, `photos.py`, and `daily_report.py`.
- Device status and alerts: `system_status.py`, `device_watchdog.py`, `metric_freshness.py`, `sensor_quality.py`, and structured JSONL via `dirt_shared.observability.log_event()`.
- Actuators and hardware loops: `humidifier.py`, `lights.py`, `fan_controller.py`, `fan_node.py`, and PTZ service/API.
- API routes: `apps/web/src/dirt_web/api/{grow,sensors,plants,system,feed,ptz}.py`.
- Contract source: `contracts/webapp-v1.yaml`, regenerated via `scripts/gen-contract`.
- Frontend singleton assumptions: `web-ui/src/routes/index.tsx`, `web-ui/src/routes/live.tsx`, `web-ui/src/ui/plant-types.ts`, `PlantsStrip.tsx`, `PlantDetail.tsx`, `SystemTable.tsx`, and MSW fixtures under `web-ui/src/mocks/fixtures/`.
- Firmware identity: location literals in `firmware/fan_controller/src/main.cpp`, `firmware/plant_node/src/main.cpp`, and `firmware/reservoir_node/src/main.cpp`.

Definitions used in this plan:

`site_id` is the stable string identity of the physical installation controlled by this machine. Phase 1 seeds one site, `homebox`.

`tent_id` is the stable string identity of a logical grow tent at the site. Phase 1 seeds at least `main` and `breeding`.

`zone_id` is a logical area within a tent or site, such as `canopy`, `reservoir`, `plant-a`, `intake`, or `exhaust`.

`device_id` is the stable string identity of a physical or service-controlled device, such as `fan-controller`, `govee-h7142-main`, `kasa-lights-main`, `plant-a-node`, `reservoir-node`, `obsbot-main`, or `jabra-claudia`.

`capability_id` is the stable string identity of something a device measures or does, such as `temperature_f`, `humidity_pct`, `vpd_kpa`, `fan_duty_pct`, `mist_level`, `lights_power`, `camera_capture`, or `ptz_move`.

`grow_run` is one grow cycle or breeding run associated with one tent.


## Plan of Work

Milestone 1: Add canonical scoped identity schema.

Create SQLModel classes under `apps/shared/src/dirt_shared/models/` for `Site`, `Tent`, `Zone`, `Device`, `Capability`, `GrowRun`, `Schedule`, `Command`, and scoped photo/alert records if they are separate tables. Prefer small files such as `site.py`, `tent.py`, `zone.py`, `device.py`, `grow_run.py`, `schedule.py`, `command.py`, `photo.py`, and `alert.py`, with exports in `models/__init__.py`.

Use stable string identifiers for public identity and surrogate bigint primary keys for joins. Recommended table names and core fields:

- `site`: `id`, `site_id`, `name`, `location`, `timezone`, `is_default`, timestamps.
- `tent`: `id`, `site_id` FK, `tent_id`, `name`, `role`, `is_default`, `active`, timestamps, unique `(site_id, tent_id)`.
- `zone`: `id`, `site_id` FK, nullable `tent_id` FK, `zone_id`, `name`, `zone_type`, `active`, unique within `(site_id, tent_id, zone_id)`.
- `device`: `id`, `site_id` FK, nullable `tent_id` FK, nullable `zone_id` FK, `device_id`, `name`, `kind`, `controller`, `enabled`, `metadata` JSONB, timestamps, unique `(site_id, device_id)`.
- `capability`: `id`, `device_id` FK, `capability_id`, `name`, `kind`, `metric_name`, `unit`, `source`, `enabled`, `metadata` JSONB, unique `(device_id, capability_id)`.
- `growrun`: `id`, `site_id` FK, `tent_id` FK, `grow_run_id`, `name`, `purpose`, germination/flower dates, strain, timezone, plant count, current flag, timestamps, unique `(tent_id, grow_run_id)` and partial unique current index per tent.
- `schedule`: `id`, `site_id` FK, `tent_id` FK, nullable `device_id`/`capability_id`, `schedule_id`, `kind`, local times, timezone, enabled flag, timestamps, unique `(tent_id, schedule_id)`.
- `command`: `id`, `command_id`, `idempotency_key`, `site_id`, `tent_id`, nullable `zone_id`, `device_id`, `capability_id`, `command_type`, `payload` JSONB, `requested_by`, `source`, `status`, timestamps for queued/started/succeeded/failed/cancelled, result/error JSONB, unique `idempotency_key`.

The first Atlas migration for this plan seeds:

- `site_id=homebox`, default true, timezone `America/Denver`.
- `tent_id=main`, default true, role `flower`, linked to `homebox`.
- `tent_id=breeding`, default false, role `breeding`, linked to `homebox`, with no active hardware loops unless explicitly enabled later.
- Main tent zones for `canopy`, `reservoir`, `plant-a`, `plant-b`, `plant-c`, `plant-d`, `exhaust`, and `lights`.
- Device/capability rows mapping the current hardware and service-controlled devices to the new identity model.

Milestone 2: Migrate current singleton data into scoped default records.

Move `growstate` semantics to `growrun`. The clean target is a `GrowRun` SQLModel/table named `growrun`; if the implementation chooses to preserve the physical `growstate` table name for migration risk, it must still expose `grow_run_id`, `site_id`, and `tent_id` semantics and record the reason in this plan's Decision Log.

Backfill the current grow row into `homebox/main`, with `grow_run_id` derived from the current germination date, such as `main-2026-03-15`. Preserve `germination_date=2026-03-15`, `flower_start_date=2026-05-03`, `lights_on_local=09:00:00`, `lights_off_local=21:00:00`, `timezone=America/Denver`, current strain, location text, and plant count.

Move `plant.growstate_id` to `plant.growrun_id`, add explicit `site_id`/`tent_id` if useful for query speed, and add a stable `plant_id` string. For current compatibility, seed `plant_id` and `code` as `a`, `b`, `c`, and `d` under `main-2026-03-15`. Keep old route behavior `/api/plants/a` by resolving it to the current main grow run.

Do not leave global current-grow queries in service code. Replace them with a scope resolver such as `ScopeService.default_scope()` and service methods like `current_grow_run(site_id="homebox", tent_id="main")`. The existing `GrowStateService` name may remain as a compatibility facade only if it delegates to scoped grow-run methods.

Milestone 3: Move telemetry to scoped device/capability ownership.

Add `capability_id` or `capability_pk` to `sensorreading` and backfill every existing row by joining its `sensornode_id` and `metric` to the seeded device/capability mapping. Keep `sensornode_id` during the transition so existing tests and calibration rows can be migrated incrementally, but make the canonical read path use `capability`.

Update `ReadingsService` so every public read method accepts a scope:

- `get_latest_reading(metric, site_id="homebox", tent_id="main", zone_id=None, device_id=None, capability_id=None)`.
- `get_metric_history(metric, range_key, site_id="homebox", tent_id="main", zone_id=None, device_id=None, capability_id=None)`.
- `get_sensor_history(range_key, site_id="homebox", tent_id="main")`.
- `get_metric_freshness_snapshot(stale_cutoff, site_id="homebox", tent_id=None)` for watchdog use.

Fix the unsafe metric-only history query by joining through capability/device/tent. A second tent emitting `temperature_f` must not appear in the default main dashboard history.

Update `apps/hwd/src/dirt_hwd/api/ingest.py` to accept optional `site_id`, `tent_id`, `zone_id`, `device_id`, and `capability_id` fields in the payload. Existing firmware payloads that only send `location` must continue to work by resolving legacy locations as follows:

- `tent` maps to `homebox/main/canopy`, device `fan-controller`, capabilities for `temperature_c`, `temperature_f`, `humidity_pct`, `vpd_kpa`, `dew_point_f`, and `fan_duty_pct`.
- `reservoir` maps to `homebox/main/reservoir`, device `reservoir-node`, capabilities for `reservoir_pressure_raw` and `reservoir_in`.
- `plant-a` through `plant-d` map to the matching main plant zone and moisture node.

Update `sensor_contract.py` so the canonical declaration is keyed by device/capability or by scoped device identity, not by the fixed `SensorLocation` enum. Keep a small legacy mapping for firmware until the firmware payload is upgraded. Update agent-owned tests; do not modify `apps/tests/invariants/`.

Milestone 4: Scope grow state, plants, schedules, sensor calibrations, snapshots/photos, and alerts.

Grow state: update `GrowStateService` or the new grow-run service so current stage, week, day, and target bands are derived per tent. The default no-argument methods should resolve to `homebox/main`. Add tests showing `homebox/main` can be in `flower_early` while `homebox/breeding` has no current grow or a separate breeding run.

Schedules: move the lights schedule out of global singleton semantics. At minimum, the main tent photoperiod schedule must be scoped to `homebox/main` and read by `LightsLoopService`. If `growrun` keeps photoperiod columns, add a `schedule` projection or service method that still returns a schedule scoped by tent.

Plants: update `PlantsService` to list plants for a specific `site_id`, `tent_id`, and current `grow_run_id`. Existing `/api/plants` remains default main. Add tests showing an empty breeding run returns an empty plant list without disturbing main A-D.

Sensor calibrations: move calibration ownership from `sensornode_id`/`metric` to canonical capability/device scope while preserving existing plant moisture behavior. Add nullable `capability_id` during the transition, backfill from the legacy sensornode and metric mapping, keep legacy lookup compatibility until all callers are migrated, and add tests for `ReadingsService`, `PlantsService`, and `DailySensorService` so calibrated main plant moisture remains unchanged and scoped reads cannot pick up another tent's calibration.

Snapshots/photos: add scope fields to `snapshot`, including at least `site_id`, `tent_id`, nullable `zone_id`, nullable `device_id`, nullable `growrun_id`, and `preset_id` or `view_id`. Backfill old periodic snapshots to `homebox/main` and a camera device; use a neutral preset such as `periodic` when no PTZ preset is known. Add DB-backed records for daily report photos, or extend `snapshot` with `kind=daily_report` so `overview`, `plant_a`, `plant_b`, `plant_c`, and `plant_d` daily photos can be scoped to main tent zones.

Alerts: introduce stable scoped alert/event records or, at minimum for Phase 1, add standard scope fields to every structured `log_event()` emitted by watchdog/control services. `device_watchdog` state should key by `device_id`, not display name. `metric_freshness` state should key by `capability_id`, not `<legacy-location>:<metric>`. Preserve existing stream names and retention from `docs/observability.md`.

Milestone 5: Scope local hardware control and add command lifecycle.

Make every hardware-control loop explicitly target `homebox/main` unless configured otherwise. Do not start a breeding-tent loop just because a breeding tent row exists.

Update these services:

- `HumidifierLoopService`: read VPD/RH from main canopy capabilities; record actuator state against the humidifier device/capabilities, not the tent sensor node.
- `FanTrimLoopService`: read main canopy VPD/RH and control `device_id=fan-controller`; log scoped events.
- `LightsLoopService`: read the main tent light schedule and control `device_id=kasa-lights-main`.
- `SystemStatusService`: build device rows from the `device` table plus capability freshness, camera socket, and voice state instead of hardcoding the eight rows.
- `PTZService`: attach camera device and preset/zone scope to state and command records while preserving current PTZ endpoints.

Add `CommandService` in `apps/shared/src/dirt_shared/services/commands.py`. It should provide a local command lifecycle without remote execution:

- `enqueue(command_type, target capability/device, payload, idempotency_key, requested_by, source)` creates or returns an existing command for the same idempotency key.
- `start(command_id)`, `succeed(command_id, result)`, and `fail(command_id, error)` are idempotent state transitions with timestamps.
- Local actuator APIs and loops may record commands as `source=local_api` or `source=local_loop`. Remote/cloud sources are rejected or not exposed in this phase.

For existing actuator APIs, start with PTZ endpoints because they are user-triggered and already synchronous. Recording humidifier/fan/lights loop decisions can be added as command records only if it does not obscure the control-loop logs; otherwise log the scope now and leave command records for explicit user/API commands.

Milestone 6: API, contract, frontend, and fixture compatibility.

Keep current unscoped endpoints working as default-main views:

- `GET /api/grow/current`
- `POST /api/grow/flower-flip`
- `GET /api/sensors/current`
- `GET /api/sensors/history`
- `GET /api/sensors/metadata`
- `GET /api/plants`
- `GET /api/plants/{code}`
- `GET /api/plants/{code}/moisture`
- `GET /api/system/devices`
- `GET /api/feed/snapshot/latest`
- PTZ endpoints under `/api/ptz/*`

Add scoped read endpoints only where needed to prove the model without changing the dashboard workflow. Recommended minimal API additions:

- `GET /api/sites`
- `GET /api/tents`
- `GET /api/tents/{tent_id}/grow/current`
- `GET /api/tents/{tent_id}/devices`

If optional `site_id`/`tent_id` query parameters are added to existing endpoints, update `contracts/webapp-v1.yaml`, run `scripts/gen-contract`, and update `contracts/python/src/dirt_contracts/webapp_v1/models.py` plus `web-ui/src/api-client/generated/schema.ts`. Respect `apps/tests/invariants/test_api_contract.py`: do not edit the invariant test; update the OpenAPI contract and generated clients so the app and spec agree.

Frontend Phase 1 should stay minimal. The current dashboard may continue showing the default main tent only. If a visible tent selector is added, it must default to `main`, include `breeding` from the API, and use `tent_id` in React Query keys. Do not build hosted/Vercel-specific auth, account, or command UI in this phase.


## Concrete Steps

Start in the repository root:

    cd /home/akcom/code/dirt

Before schema work, read the Atlas reference because this plan edits SQLModel models and migrations:

    sed -n '1,240p' docs/references/atlas/INDEX.md

Create models and services in the shared package. Use `apply_patch` for manual edits. Do not edit `apps/tests/invariants/`.

Run the focused Python tests around the current model before changing behavior:

    uv run pytest apps/shared/tests/test_pg_fixture.py apps/shared/tests/test_grow_state.py apps/web/tests/test_grow_endpoint.py apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_system_devices_endpoint.py -q

Expected result before implementation: the existing tests pass on the current singleton model. If they fail for unrelated local state, record the failure in `Artifacts and Notes` before proceeding.

Generate the schema migration after editing SQLModel classes:

    atlas migrate diff multi_tent_controller --env local

Review the generated SQL in `migrations/`. It should create the scoped identity tables, add the new FKs/columns/indexes, seed default `homebox/main/breeding` rows, and backfill existing data. It must not contain application-runtime DDL.

Apply migrations only in the intended database environment. Before applying to the live local database that controls the real grow, take a backup:

    mkdir -p var/db-backups
    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump -h 127.0.0.1 -U dirt -d dirt > var/db-backups/dirt-before-multi-tent-$(date +%F-%H%M%S).sql
    atlas migrate apply --env local

Update services and APIs in small slices. After each slice, run the nearest tests:

    uv run pytest apps/shared/tests/test_grow_state.py -q
    uv run pytest apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py -q
    uv run pytest apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py -q
    uv run pytest apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py -q
    uv run pytest apps/web/tests/test_system_devices_endpoint.py apps/hwd/tests/test_device_watchdog.py apps/hwd/tests/test_fan_controller.py apps/hwd/tests/test_humidifier_loop.py -q
    uv run pytest apps/shared/tests/test_daily_sensors.py apps/shared/tests/test_daily_report.py apps/shared/tests/test_capture.py apps/web/tests/test_feed_snapshot_endpoint.py -q

If the OpenAPI contract changes, regenerate clients:

    scripts/gen-contract
    uv run pytest apps/tests/invariants/test_api_contract.py -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui test

Run broader verification before completion:

    uv run pytest apps/tests/invariants/ -q
    uv run pytest apps/shared/tests apps/hwd/tests apps/web/tests -q
    pnpm --dir web-ui lint
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui test

If frontend behavior changes visibly, run the web UI build:

    pnpm --dir web-ui build


## Validation and Acceptance

The phase is complete when these observable behaviors are true:

Existing main-tent compatibility:

- Existing firmware payloads that only include `location` still receive `202 Accepted` from `POST /api/ingest/sensors` and write readings scoped to `homebox/main`.
- `GET /api/grow/current` returns the current grow with germination date `2026-03-15`, flower start date `2026-05-03`, 12/12 lights `09:00:00` to `21:00:00`, and the same stage/day semantics as before.
- `GET /api/sensors/current` returns current main-tent values and does not include breeding-tent readings.
- `GET /api/sensors/history?range=24h&metric=temperature_f` returns only default main-tent history.
- `GET /api/plants` returns current main A-D plants.
- Main plant moisture calibration and daily sensor summaries remain unchanged for existing plants, but calibration records are owned by canonical capability/device scope internally.
- `GET /api/system/devices` still shows the current real devices, but rows are backed by stable `device_id` internally.
- HWD control-loop tests show humidifier, fan trim, and lights still target only the main tent unless configured otherwise.

Second-tent representation:

- The database has `site.site_id='homebox'`, `tent.tent_id='main'`, and `tent.tent_id='breeding'`.
- A test can insert a breeding-tent device and `temperature_f` reading, then prove default main sensor history excludes it while a scoped breeding query includes it.
- A test can create a breeding `growrun` without changing the current main grow.
- A test can list devices for `tent_id=breeding` separately from `tent_id=main`.
- A test can create a calibration for one tent's capability without affecting another tent's same metric.
- A test can create a local command-intent row for a target capability with an idempotency key and re-enqueue the same key without creating a duplicate.

Schema and contract:

- Atlas migrations apply cleanly from an empty test database and against the current local database backup path.
- `apps/tests/invariants/test_schema_managed_by_atlas.py` passes.
- `apps/tests/invariants/test_api_contract.py` passes after any API additions.
- No human-owned invariant test under `apps/tests/invariants/` is modified.

Frontend compatibility:

- `pnpm --dir web-ui typecheck` passes with generated types.
- If the dashboard remains default-main only, no user-visible frontend selector is required.
- If a selector is added, it defaults to main and does not make the breeding tent appear as an active hardware controller.

Operational observability:

- New or changed `log_event()` calls include scope fields where applicable: `site_id`, `tent_id`, `zone_id`, `device_id`, and `capability_id`.
- Watchdog state files use stable IDs for new records. Existing old state files can be ignored or migrated without replaying every offline alert.


## Idempotence and Recovery

Atlas migration generation is repeatable, but generated SQL must be reviewed before applying. The seed statements should use unique constraints and `ON CONFLICT` or equivalent idempotent patterns so re-running test setup does not duplicate `homebox`, `main`, `breeding`, zones, devices, or capabilities.

Live database migration is the riskiest step because this machine controls real hardware. Take a `pg_dump` backup immediately before `atlas migrate apply --env local`. If migration fails before commit, Atlas/Postgres should leave the schema unchanged. If a migration applies but behavior fails, stop `dirt-hwd` only if needed to prevent unsafe control behavior, restore from the backup, and restart services:

    systemctl --user stop dirt-hwd dirt-web
    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt < var/db-backups/<backup-file>.sql
    systemctl --user start dirt-hwd dirt-web

Do not run destructive commands such as `git reset --hard`, dropping the database, or removing `var/` data without explicit user approval.

Boundary compatibility is intentional and safe to repeat: legacy ingest `location` mapping can remain until firmware is updated to send scoped identity fields. When firmware is eventually upgraded, keep the server accepting legacy payloads for at least one release cycle because real boards may be flashed at different times.

Command idempotency is mandatory. `CommandService.enqueue()` must return the existing command for an existing idempotency key and must not execute twice. Failed commands should retain payload, target, timestamps, and error for audit.

Watchdog state migration should be forgiving. If old display-name keys exist, the new code should seed stable-device keys from current state without sending first-seen alerts. This mirrors the current cold-start behavior described in `docs/observability.md`.


## Artifacts and Notes

Required docs read before plan creation:

    AGENTS.md
    .agents/PLANS.md
    docs/commands.md
    docs/database.md
    docs/grow-state.md
    docs/observability.md

Read-only schema confirmation on 2026-05-03 showed:

    sensornode.location sensor_location NOT NULL UNIQUE
    sensorreading.sensornode_id bigint NOT NULL REFERENCES sensornode(id)
    growstate has global partial unique index ux_growstate_is_current WHERE is_current = true
    plant has UNIQUE (growstate_id, code) and UNIQUE (sensornode_id)
    snapshot has only id, ts, file_path

Key current singleton files found during investigation:

    apps/shared/src/dirt_shared/models/enums.py
    apps/shared/src/dirt_shared/models/sensor_node.py
    apps/shared/src/dirt_shared/models/sensor_reading.py
    apps/shared/src/dirt_shared/models/grow_state.py
    apps/shared/src/dirt_shared/models/plant.py
    apps/shared/src/dirt_shared/models/snapshot.py
    apps/shared/src/dirt_shared/sensor_contract.py
    apps/shared/src/dirt_shared/services/readings.py
    apps/shared/src/dirt_shared/services/grow_state.py
    apps/shared/src/dirt_shared/services/plants.py
    apps/shared/src/dirt_shared/services/daily_sensors.py
    apps/shared/src/dirt_shared/services/daily_report.py
    apps/shared/src/dirt_shared/services/system_status.py
    apps/hwd/src/dirt_hwd/api/ingest.py
    apps/hwd/src/dirt_hwd/services/humidifier.py
    apps/hwd/src/dirt_hwd/services/fan_controller.py
    apps/hwd/src/dirt_hwd/services/lights.py
    apps/hwd/src/dirt_hwd/services/device_watchdog.py
    apps/hwd/src/dirt_hwd/services/metric_freshness.py
    apps/web/src/dirt_web/api/grow.py
    apps/web/src/dirt_web/api/sensors.py
    apps/web/src/dirt_web/api/plants.py
    apps/web/src/dirt_web/api/system.py
    apps/web/src/dirt_web/api/feed.py
    apps/web/src/dirt_web/api/ptz.py
    contracts/webapp-v1.yaml
    web-ui/src/routes/index.tsx
    web-ui/src/routes/live.tsx
    web-ui/src/ui/plant-types.ts
    web-ui/src/ui/PlantsStrip.tsx
    web-ui/src/ui/PlantDetail.tsx
    web-ui/src/ui/SystemTable.tsx
    web-ui/src/mocks/handlers.ts
    firmware/fan_controller/src/main.cpp
    firmware/plant_node/src/main.cpp
    firmware/reservoir_node/src/main.cpp
    config/camera.json.example

Existing git status at plan creation included unrelated changes and deleted old planning files. This plan intentionally did not open or rely on those old planning files.

Milestone 1 changed these files:

    apps/shared/src/dirt_shared/models/__init__.py
    apps/shared/src/dirt_shared/models/site.py
    apps/shared/src/dirt_shared/models/tent.py
    apps/shared/src/dirt_shared/models/zone.py
    apps/shared/src/dirt_shared/models/device.py
    apps/shared/src/dirt_shared/models/grow_run.py
    apps/shared/src/dirt_shared/models/schedule.py
    apps/shared/src/dirt_shared/models/command.py
    apps/shared/tests/test_scoped_identity_models.py
    migrations/20260504000618_multi_tent_controller.sql
    migrations/atlas.sum

Milestone 1 validation evidence:

    uv run pytest apps/shared/tests/test_pg_fixture.py apps/shared/tests/test_grow_state.py apps/web/tests/test_grow_endpoint.py apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_system_devices_endpoint.py apps/shared/tests/test_scoped_identity_models.py -q
    52 passed in 10.78s

    uv run pytest apps/tests/invariants/test_schema_managed_by_atlas.py -q
    4 passed in 0.07s

    atlas migrate diff verify_multi_tent_sync --env local
    The migration directory is synced with the desired state, no changes to be made

    uv run ruff check apps/shared/src/dirt_shared/models apps/shared/tests/test_scoped_identity_models.py
    All checks passed!

Milestone 2 changed these files:

    apps/shared/src/dirt_shared/models/__init__.py
    apps/shared/src/dirt_shared/models/grow_run.py
    apps/shared/src/dirt_shared/models/grow_state.py (deleted)
    apps/shared/src/dirt_shared/models/plant.py
    apps/shared/src/dirt_shared/services/scope.py
    apps/shared/src/dirt_shared/services/grow_state.py
    apps/shared/src/dirt_shared/services/plants.py
    apps/shared/tests/test_grow_state.py
    apps/shared/tests/test_scoped_identity_models.py
    apps/web/tests/test_grow_endpoint.py
    apps/shared/src/dirt_shared/config.py
    apps/hwd/src/dirt_hwd/services/lights.py
    docs/database.md
    docs/grow-state.md
    docs/observability.md
    migrations/20260504012912_scoped_growrun_plants.sql
    migrations/atlas.sum

Milestone 2 validation evidence:

    uv run pytest apps/shared/tests/test_pg_fixture.py apps/shared/tests/test_scoped_identity_models.py apps/shared/tests/test_grow_state.py apps/web/tests/test_grow_endpoint.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py -q
    49 passed in 9.82s

    uv run pytest apps/tests/invariants/test_schema_managed_by_atlas.py -q
    4 passed in 0.07s

    atlas migrate diff verify_scoped_growrun_sync --env local
    The migration directory is synced with the desired state, no changes to be made

    uv run ruff check apps/shared/src/dirt_shared/models apps/shared/src/dirt_shared/services apps/shared/tests/test_grow_state.py apps/web/tests/test_grow_endpoint.py
    All checks passed!

    git diff --check
    passed

Milestone 3 changed these files:

    apps/hwd/src/dirt_hwd/api/ingest.py
    apps/shared/src/dirt_shared/models/sensor_reading.py
    apps/shared/src/dirt_shared/sensor_contract.py
    apps/shared/src/dirt_shared/services/readings.py
    apps/shared/tests/test_readings_scope.py
    apps/web/tests/test_sensors_current_endpoint.py
    apps/web/tests/test_sensors_history_endpoint.py
    docs/database.md
    migrations/20260504013944_scoped_sensorreading_capabilities.sql
    migrations/atlas.sum

Milestone 3 validation evidence:

    uv run pytest apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/shared/tests/test_pg_fixture.py -q
    27 passed in 4.49s

    uv run pytest apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py -q
    14 passed in 5.49s

    uv run pytest apps/shared/tests/test_readings_scope.py -q
    1 passed in 1.35s

    uv run pytest apps/shared/tests/test_pg_fixture.py apps/shared/tests/test_readings_scope.py apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py -q
    42 passed in 9.09s

    uv run pytest apps/tests/invariants/test_sensor_contract.py apps/tests/invariants/test_schema_managed_by_atlas.py -q
    6 passed in 0.18s

    uv run ruff check apps/shared/src/dirt_shared/models/sensor_reading.py apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/sensor_contract.py apps/hwd/src/dirt_hwd/api/ingest.py apps/shared/tests/test_readings_scope.py apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py
    All checks passed!

    atlas migrate diff verify_scoped_sensorreading_sync --env local
    The migration directory is synced with the desired state, no changes to be made

Milestone 4 checkpoint changed these files:

    apps/hwd/src/dirt_hwd/services/device_watchdog.py
    apps/hwd/src/dirt_hwd/services/metric_freshness.py
    apps/hwd/tests/test_device_watchdog.py
    apps/shared/src/dirt_shared/models/sensor_calibration.py
    apps/shared/src/dirt_shared/models/snapshot.py
    apps/shared/src/dirt_shared/services/capture.py
    apps/shared/src/dirt_shared/services/daily_sensors.py
    apps/shared/src/dirt_shared/services/grow_state.py
    apps/shared/src/dirt_shared/services/plants.py
    apps/shared/src/dirt_shared/services/readings.py
    apps/shared/src/dirt_shared/services/snapshots.py
    apps/shared/src/dirt_shared/services/system_status.py
    apps/shared/tests/test_capture.py
    apps/shared/tests/test_grow_state.py
    apps/shared/tests/test_milestone4_scope.py
    docs/database.md
    migrations/20260504022916_scoped_milestone4.sql
    migrations/atlas.sum

Milestone 4 checkpoint validation evidence:

    uv run pytest apps/shared/tests/test_grow_state.py apps/shared/tests/test_milestone4_scope.py apps/shared/tests/test_capture.py apps/shared/tests/test_daily_sensors.py apps/hwd/tests/test_device_watchdog.py -q
    50 passed in 12.36s

    uv run pytest apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py apps/web/tests/test_feed_snapshot_endpoint.py apps/web/tests/test_system_devices_endpoint.py apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py apps/tests/invariants/test_schema_managed_by_atlas.py -q
    38 passed in 8.34s

    uv run pytest apps/shared/tests/test_pg_fixture.py apps/shared/tests/test_readings_scope.py apps/shared/tests/test_milestone4_scope.py apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/hwd/tests/test_device_watchdog.py apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py -q
    56 passed in 11.52s

    uv run pytest apps/tests/invariants/test_sensor_contract.py apps/tests/invariants/test_schema_managed_by_atlas.py -q
    6 passed in 0.18s

    uv run ruff check apps/shared/src/dirt_shared/models/sensor_calibration.py apps/shared/src/dirt_shared/models/snapshot.py apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/plants.py apps/shared/src/dirt_shared/services/daily_sensors.py apps/shared/src/dirt_shared/services/grow_state.py apps/shared/src/dirt_shared/services/capture.py apps/shared/src/dirt_shared/services/snapshots.py apps/shared/src/dirt_shared/services/system_status.py apps/hwd/src/dirt_hwd/services/device_watchdog.py apps/hwd/src/dirt_hwd/services/metric_freshness.py apps/shared/tests/test_milestone4_scope.py apps/shared/tests/test_capture.py apps/shared/tests/test_grow_state.py apps/hwd/tests/test_device_watchdog.py
    All checks passed!

    atlas migrate diff verify_scoped_milestone4_sync --env local
    The migration directory is synced with the desired state, no changes to be made

    git diff --check
    passed

The first Milestone 4 validation attempt failed during Atlas replay before tests ran:

    pq: invalid reference to FROM-clause entry for table "sc"

The calibration backfill was corrected by moving the target-table predicate from a `JOIN ... ON` clause into the `WHERE` clause, then `atlas migrate hash --env local` was rerun.

Milestone 4 daily-report follow-up changed these files:

    apps/shared/src/dirt_shared/services/daily_report.py
    apps/shared/tests/test_daily_report.py
    scripts/daily_report
    docs/epics/multi-tent-controller/ExecPlan.md

Milestone 4 daily-report follow-up validation evidence:

    uv run pytest apps/shared/tests/test_daily_report.py -q
    28 passed in 1.71s

    uv run pytest apps/shared/tests/test_daily_report.py apps/shared/tests/test_grow_state.py apps/shared/tests/test_milestone4_scope.py apps/shared/tests/test_capture.py apps/shared/tests/test_daily_sensors.py apps/hwd/tests/test_device_watchdog.py -q
    78 passed in 12.86s

    uv run pytest apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py apps/web/tests/test_feed_snapshot_endpoint.py apps/web/tests/test_system_devices_endpoint.py apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py apps/tests/invariants/test_sensor_contract.py apps/tests/invariants/test_schema_managed_by_atlas.py -q
    40 passed in 8.39s

    uv run ruff check apps/shared/src/dirt_shared/services/daily_report.py apps/shared/tests/test_daily_report.py scripts/daily_report apps/hwd/src/dirt_hwd/services/device_watchdog.py apps/hwd/src/dirt_hwd/services/metric_freshness.py
    All checks passed!

    atlas migrate diff verify_scoped_milestone4_daily_report_sync --env local
    The migration directory is synced with the desired state, no changes to be made

    git diff --check
    passed

Milestone 5 changed these files:

    apps/hwd/src/dirt_hwd/services/fan_controller.py
    apps/hwd/src/dirt_hwd/services/humidifier.py
    apps/hwd/src/dirt_hwd/services/lights.py
    apps/hwd/tests/test_fan_controller.py
    apps/hwd/tests/test_humidifier_loop.py
    apps/hwd/tests/test_lights_loop.py
    apps/shared/src/dirt_shared/app_wiring.py
    apps/shared/src/dirt_shared/services/commands.py
    apps/shared/src/dirt_shared/services/ptz.py
    apps/shared/src/dirt_shared/services/system_status.py
    apps/shared/tests/test_commands.py
    apps/shared/tests/test_system_status_scope.py
    apps/web/src/dirt_web/app.py
    apps/web/src/dirt_web/deps.py
    apps/web/tests/test_ptz_preset_endpoint.py
    docs/epics/multi-tent-controller/ExecPlan.md

Milestone 5 validation evidence:

    uv run pytest apps/shared/tests/test_commands.py apps/shared/tests/test_system_status_scope.py apps/hwd/tests/test_humidifier_loop.py apps/hwd/tests/test_fan_controller.py apps/hwd/tests/test_lights_loop.py apps/web/tests/test_ptz_preset_endpoint.py -q
    23 passed in 3.79s

    uv run pytest apps/web/tests/test_system_devices_endpoint.py apps/hwd/tests/test_device_watchdog.py apps/shared/tests/test_milestone4_scope.py -q
    16 passed in 3.84s

    uv run pytest apps/web/tests/test_ptz_state_endpoint.py apps/web/tests/test_ptz_preset_endpoint.py apps/web/tests/test_ptz_look_endpoint.py apps/web/tests/test_ptz_zoom_endpoint.py -q
    21 passed in 2.22s

    uv run pytest apps/shared/tests/test_commands.py apps/shared/tests/test_system_status_scope.py apps/hwd/tests/test_humidifier_loop.py apps/hwd/tests/test_fan_controller.py apps/hwd/tests/test_lights_loop.py apps/hwd/tests/test_device_watchdog.py apps/web/tests/test_ptz_state_endpoint.py apps/web/tests/test_ptz_preset_endpoint.py apps/web/tests/test_ptz_look_endpoint.py apps/web/tests/test_ptz_zoom_endpoint.py apps/web/tests/test_system_devices_endpoint.py -q
    53 passed in 4.61s

    uv run pytest apps/tests/invariants/ -q
    107 passed, 1 skipped in 3.91s

    uv run ruff check apps/shared/src/dirt_shared/services/commands.py apps/shared/src/dirt_shared/app_wiring.py apps/web/src/dirt_web/app.py apps/web/src/dirt_web/deps.py apps/hwd/src/dirt_hwd/services/humidifier.py apps/hwd/src/dirt_hwd/services/fan_controller.py apps/hwd/src/dirt_hwd/services/lights.py apps/shared/src/dirt_shared/services/system_status.py apps/shared/src/dirt_shared/services/ptz.py apps/shared/tests/test_commands.py apps/shared/tests/test_system_status_scope.py apps/hwd/tests/test_humidifier_loop.py apps/hwd/tests/test_fan_controller.py apps/hwd/tests/test_lights_loop.py apps/web/tests/test_ptz_preset_endpoint.py
    All checks passed!

    atlas migrate diff verify_scoped_milestone5_sync --env local
    The migration directory is synced with the desired state, no changes to be made

Milestone 6 changed these files:

    apps/shared/src/dirt_shared/app_wiring.py
    apps/shared/src/dirt_shared/services/scope_catalog.py
    apps/web/src/dirt_web/api/scope.py
    apps/web/src/dirt_web/app.py
    apps/web/src/dirt_web/deps.py
    apps/web/tests/test_scope_endpoints.py
    contracts/webapp-v1.yaml
    contracts/python/src/dirt_contracts/webapp_v1/models.py
    web-ui/src/api-client/generated/schema.ts
    docs/epics/multi-tent-controller/ExecPlan.md

Milestone 6 validation evidence:

    scripts/gen-contract
    generated Pydantic models and TypeScript schema

    uv run pytest apps/web/tests/test_scope_endpoints.py apps/web/tests/test_grow_endpoint.py apps/web/tests/test_system_devices_endpoint.py apps/tests/invariants/test_api_contract.py -q
    17 passed, 1 skipped in 2.87s

    uv run pytest apps/tests/invariants/ -q
    115 passed, 1 skipped in 4.09s

    uv run pytest apps/web/tests -q
    103 passed in 11.26s

    uv run ruff check apps/shared/src/dirt_shared/services/scope_catalog.py apps/shared/src/dirt_shared/app_wiring.py apps/web/src/dirt_web/api/scope.py apps/web/src/dirt_web/app.py apps/web/src/dirt_web/deps.py apps/web/tests/test_scope_endpoints.py
    All checks passed!

    atlas migrate diff verify_scoped_milestone6_sync --env local
    The migration directory is synced with the desired state, no changes to be made

    pnpm --dir web-ui lint
    passed

    pnpm --dir web-ui typecheck
    passed

    pnpm --dir web-ui test
    1 passed


## Interfaces and Dependencies

New or changed database interfaces:

- Tables: `site`, `tent`, `zone`, `device`, `capability`, `growrun`, `schedule`, `command`, and scoped photo/alert storage if implemented as tables.
- Existing table changes: `growstate` has been retired in favor of `growrun`; `plant` now links to `growrun`, `site`, and `tent` with stable `plant_id`; `sensorreading` now has nullable canonical `capability_id` linkage; `sensorcalibration` has nullable canonical `capability_id` ownership and nullable legacy `sensornode_id`; `snapshot` has nullable site/tent/zone/device/growrun plus `view_id`/`kind` scope for periodic snapshots.
- Indexes: unique external IDs, per-tent current grow partial unique index, sensor history indexes that support `(capability_id, ts DESC)` and scoped dashboard queries.

New or changed service interfaces:

- `apps/shared/src/dirt_shared/services/scope.py` resolves default `homebox/main` and explicit site/tent scopes.
- `apps/shared/src/dirt_shared/services/scope_catalog.py` lists read-only site, tent, and tent-device catalog rows for API use.
- `ReadingsService` scoped read/write methods.
- `GrowStateService` remains as a compatibility facade over scoped `growrun` rows, exposes `current_grow_run(site_id="homebox", tent_id="main")`, and reads `current_light_schedule()` from the scoped `schedule` row with a growrun fallback.
- `PlantsService` methods accept `site_id`/`tent_id` and default to main.
- `PlantsService` and `DailySensorService` resolve calibration by scoped capability before falling back to legacy sensornode/metric rows.
- `SystemStatusService` rows carry stable `device_id` and default site/tent/zone metadata for watchdog state.
- `CommandService` with idempotent enqueue and lifecycle transitions rejects non-local sources in Phase 1; PTZ endpoints record `source=local_api` command rows for `obsbot-main`/`ptz_move`.
- `CaptureService` and `SnapshotsService` write/read default-main periodic snapshot scope metadata.
- `DailyReportSnapshotRecorder` writes default-main `snapshot.kind='daily_report'` rows for daily-report photo presets, and `scripts/daily_report` wires it in production.
- `HumidifierLoopService`, `FanTrimLoopService`, and `LightsLoopService` accept explicit site/tent/device scope constructor arguments and default to `homebox/main`.

New or changed API interfaces:

- Current unscoped endpoints remain default-main compatible.
- `GET /api/sites` returns the physical controller site catalog, currently `homebox`.
- `GET /api/tents?site_id=homebox` returns logical tents for the local site, currently `main` and `breeding`.
- `GET /api/tents/{tent_id}/grow/current?site_id=homebox` returns the scoped current grow or 404 when that tent has no current grow.
- `GET /api/tents/{tent_id}/devices?site_id=homebox` returns canonical devices assigned to that tent.
- `contracts/webapp-v1.yaml`, `contracts/python/src/dirt_contracts/webapp_v1/models.py`, and `web-ui/src/api-client/generated/schema.ts` include the new scope endpoint schemas and operations.

Firmware/interface compatibility:

- Existing firmware payload fields remain accepted: `location`, `metrics`, `source`, `ip`, `firmware_version`, and `uptime_ms`.
- New optional ingest fields may be accepted: `site_id`, `tent_id`, `zone_id`, `device_id`, and `capability_id`.
- No firmware update is required to complete Phase 1.

Operational dependencies:

- PostgreSQL 17 and Atlas remain the schema-management path.
- `dirt-hwd` remains the only hardware execution authority.
- `dirt-web` remains the local web/API service.
- No new cloud provider, IoT platform, Vercel deployment, public auth provider, or remote command execution dependency is introduced.

Out of scope until hosted website phase:

- Vercel or any hosted frontend deployment.
- Hosted backend/API, public DNS, TLS, OAuth, account management, or internet-facing auth redesign.
- Remote/cloud command execution.
- Multi-site fleet agents, AWS IoT Core, Greengrass, MQTT fleet architecture, or per-site cloud agents.
- Moving source of truth for hardware state to the cloud.
- Building a public command UI or mobile remote-control workflow.
- Starting real breeding-tent control loops before hardware is installed and explicitly configured.


## Revision Notes

- 2026-05-03: Initial de novo ExecPlan created from repository investigation and the user's multi-tent local-controller context.
- 2026-05-04: Milestone 1 completed. Added scoped identity models and the `20260504000618_multi_tent_controller.sql` Atlas migration with seed data. Recorded that local Atlas lint is blocked by the installed CLI's Pro-only gate and substituted schema-sync plus pytest replay validation.
- 2026-05-04: Milestone 2 completed. Retired `growstate`, backfilled current main grow into `growrun`, moved `plant` to scoped grow-run ownership, added scope helpers, and preserved default-main API behavior.
- 2026-05-04: Milestone 3 completed. Added `sensorreading.capability_id`, migrated telemetry ingest/read paths to scoped capability/device ownership, retained legacy firmware `location` compatibility, and proved duplicate metric names in another tent do not leak into default main history.
- 2026-05-04: Assigned `sensorcalibration` capability/device ownership to Milestone 4 after Milestone 3 showed it was still pending but not explicitly scheduled.
- 2026-05-04: Milestone 4 checkpoint completed for scoped grow/schedule service reads, empty breeding plant reads, capability-owned sensor calibrations, scoped periodic snapshots, and watchdog stable IDs. Daily-report photo DB rows were split into a focused follow-up.
- 2026-05-04: Milestone 4 daily-report follow-up completed. Added optional `DailyReportSnapshotRecorder`, wired `scripts/daily_report`, and proved daily-report captures create scoped `snapshot.kind='daily_report'` rows while preserving filesystem and Telegram flow.
- 2026-05-04: Milestone 5 completed. Scoped local hardware-control loops to default main tent, added `CommandService`, recorded PTZ command lifecycle rows, and moved system status identity to canonical `device` rows without changing the current visible dashboard device set.
- 2026-05-04: Milestone 6 completed. Added read-only scoped site/tent/grow/device APIs, regenerated contract clients, kept the frontend dashboard default-main only, and recorded that generated TypeScript requires Biome formatting after `scripts/gen-contract`.
