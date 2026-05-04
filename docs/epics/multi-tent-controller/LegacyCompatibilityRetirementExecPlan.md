# Multi-Tent Legacy Compatibility Retirement

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

Phase 1 of the multi-tent local-controller model is live: Dirt has scoped `site`, `tent`, `zone`, `device`, `capability`, `growrun`, `schedule`, `snapshot`, and `command` records, and the existing main-tent dashboard still works. The next change retires the compatibility layers that let old code and firmware keep pretending that `SensorLocation` and `sensornode` are the primary model.

After this plan is complete, new telemetry, calibration, plant moisture, device freshness, daily sensors, API reads, and firmware payloads use canonical scoped identities directly. Legacy `location` strings remain understood only as an explicit backward-compatible ingest format for old flashed boards, not as the internal source of truth. A human can observe success by seeing current readings and heartbeats tied to `device`/`capability`, scoped API calls returning the same default-main data as the dashboard, and tests proving that no new current-path row depends on `sensornode_id` or metric-only lookups.

This plan is still local-controller work. The homebox remains the hardware authority. Do not add hosted/cloud command execution, public auth, Vercel-specific behavior, or remote-control UI in this plan.


## Progress

- [x] (2026-05-04 03:35Z) Created this ExecPlan after Phase 1 migrations were applied and operational smoke checks passed.
- [x] (2026-05-04 04:53Z) Implemented Milestone 1: audit and guard current legacy paths before changing behavior. Added executable audit coverage for production legacy references and current compatibility writers; added focused ingest/history guards before behavior changes; ran simplify fallback and focused validation.
- [x] (2026-05-04 05:09Z) Implemented Milestone 2: firmware now posts scoped identity fields alongside legacy `location`; HWD ingest accepts known scoped `device_id` payloads without `location`, warns on known legacy-only posts, and `sensor_contract.py` now derives legacy maps from canonical device/capability declarations.
- [x] (2026-05-04 05:31Z) Implemented Milestone 3: canonical heartbeat columns live on `device`; ingest updates scoped device heartbeat when `device_id` is present while legacy compatibility still updates `sensornode`; system status, device watchdog input, and metric freshness gates now read canonical device heartbeat.
- [x] (2026-05-04 05:39Z) Fixed Milestone 3 main-review blocker: legacy-only known-location ingest and rejected legacy payloads now derive the canonical device id from the legacy location mapping and refresh `device.last_seen`/metadata as well as `sensornode`.
- [x] (2026-05-04 05:51Z) Implemented Milestone 4: plant rows now have canonical `moisture_capability_id`; plant moisture summaries/history and daily-report plant sensor paths prefer capability ownership instead of `Plant.sensornode_id`; focused plant/daily report tests, invariants, and Atlas sync/status checks pass. No live migration apply was run.
- [x] (2026-05-04 06:01Z) Implemented Milestone 5: default-main sensor, plant, and latest-snapshot URLs now accept optional `site_id`/`tent_id` query params; generated TypeScript contract types expose those query params; focused scoped endpoint tests pass.
- [ ] Implement Milestone 6: backfill or quarantine historical unscoped data and tighten schema/app constraints.
- [ ] Implement Milestone 7: remove dead legacy code, docs, tests, and optional schema artifacts that no live path uses.
- [x] (2026-05-04) Recorded `growrun.location` as a cleanup-removal candidate and classified cleanup candidates as Milestone 7 work with explicit validation, not vague final-exit notes.
- [x] (2026-05-04) Recorded duplicated photoperiod storage as a cleanup-removal candidate: `schedule` should be canonical, and `growrun.lights_on_local` / `growrun.lights_off_local` should be removed after service/API reads compose lights times from schedule.


## Surprises & Discoveries

- Observation: The live rollout applied all Phase 1 migrations successfully and restarted services cleanly.
  Evidence: `atlas migrate status --env local` reported current version `20260504022916` and zero pending files after rollout.

- Observation: New live readings after the rollout are capability-linked, but historical unlinked rows remain.
  Evidence: After service restart, `sensorreading` rows after `2026-05-04 03:20:00+00` showed `49 / 49` with `capability_id IS NOT NULL`. Older rows without `capability_id` include `pressure_hpa`, old `humidifier_on`, old `humidifier_mist_level`, `reservoir_depth_cm`, and a few one-off plant rows.

- Observation: `sensornode` is still a live heartbeat table, not only historical baggage.
  Evidence: `apps/shared/src/dirt_shared/services/system_status.py` reads `SensorNode.last_seen` via `Device.metadata["legacy_location"]`; `ReadingsService.touch_node()` and `ingest_reading()` still update `sensornode`.

- Observation: Plant moisture and daily sensors still rely heavily on `SensorLocation` and `sensornode_id`.
  Evidence: `apps/shared/src/dirt_shared/services/daily_sensors.py` defines `PLANT_LOCATIONS` and queries `SensorReading.sensornode_id`; `apps/shared/src/dirt_shared/services/plants.py` still uses `Plant.sensornode_id` to find moisture readings.

- Observation: The public dashboard and generated contract still contain default-main assumptions by design.
  Evidence: Existing routes `/api/sensors/current`, `/api/sensors/history`, `/api/plants`, `/api/feed/snapshot/latest`, and `/api/system/devices` remain unscoped default-main views; scoped identity is exposed through `/api/sites`, `/api/tents`, `/api/tents/{tent_id}/grow/current`, and `/api/tents/{tent_id}/devices`.

- Observation: Firmware still bakes legacy logical locations into each image.
  Evidence: `firmware/fan_controller/src/main.cpp` uses `LOCATION = "tent"`, `firmware/plant_node/src/main.cpp` derives `LOCATION = "plant-" PLANT_ID`, and `firmware/reservoir_node/src/main.cpp` uses `LOCATION = "reservoir"`.

- Observation: The rollout surfaced unrelated archive verification failures for old camera days.
  Evidence: `dirt-hwd` logged `ArchiveVerificationError` frame-count mismatches for `2026-04-21` and `2026-04-22`; the service stayed active and JPEGs were not deleted. This is not part of this plan unless later cleanup touches archive/snapshot history.

- Observation: `growrun.location` is a free-form carryover from the old singleton grow state and duplicates relational scope.
  Evidence: `apps/shared/src/dirt_shared/models/grow_run.py` has `GrowRun.site_id`, `GrowRun.tent_id`, and a separate `location` text column. The canonical grow location is now `growrun.site_id -> site.id` and `growrun.tent_id -> tent.id`; `contracts/webapp-v1.yaml` still exposes `GrowCurrent.location` for the default-main dashboard response.

- Observation: Photoperiod is stored in both `growrun` and `schedule`.
  Evidence: `apps/shared/src/dirt_shared/models/grow_run.py` has `lights_on_local` and `lights_off_local`, while `apps/shared/src/dirt_shared/models/schedule.py` has scoped `starts_local`, `ends_local`, `timezone`, `device_id`, and `capability_id`. Phase 1 already materialized the main photoperiod as `schedule_id='main-lights-photoperiod'`, so keeping the grow-run copy creates two sources of truth.

- Observation: Milestone 1 static audit now scans every `apps/*/src` Python source root and found the active production legacy surface includes HWD ingest/humidifier/metric-freshness compatibility, shared legacy models, `sensor_contract.py`, shared readings/daily-sensors/plants/system-status services, and the voice sensor tool.
  Evidence: `apps/shared/tests/test_legacy_retirement_audit.py::test_legacy_reference_inventory_is_explicit` enumerates the exact files and fails if another production file starts using `SensorLocation`, `SensorNode`, `sensornode_id`, legacy metric maps, or `legacy_location` without updating the audit.

- Observation: Main-agent review caught that the first Milestone 1 audit was incomplete because it only scanned shared/HWD/web source roots and missed voice.
  Evidence: `apps/voice/src/dirt_voice/tools/sensors.py` imports `SensorLocation` and `SensorNode`, joins `SensorReading.sensornode_id` and `SensorCalibration.sensornode_id` through `SensorNode`, and calls `persisted_metrics(SensorLocation.TENT)`. The audit now includes this file in the explicit expected inventory.

- Observation: DB-backed app tests in this worktree share a session-scoped template database name and should not be launched as concurrent pytest processes; cross-app combined pytest commands can also expose template lifecycle races after one app's fixture teardown.
  Evidence: Running the touched shared/HWD/web tests in one command produced `template database "dirt_test_template_7ff9482e8f" does not exist` after 24 passing tests. Running DB-backed commands concurrently reproduced the same template race. Rerunning the touched suites serially passed.

- Observation: The ingest endpoint still requires `location`, but scoped `device_id` already wins for capability resolution.
  Evidence: `apps/hwd/tests/test_ingest_api.py::test_scoped_device_id_writes_capability_without_legacy_location_mapping` posts `location='tent'` with `device_id='plant-a-node'` and verifies the new reading is capability-linked to `plant-a-node` while the compatibility `sensornode_id` remains the tent node.

- Observation: A concurrent edit rewrote the new audit test file during the Milestone 1 simplify/format pass.
  Evidence: `apps/shared/tests/test_legacy_retirement_audit.py` changed from the initial five-test AST audit shape to a cleaner centralized-writer helper while still untracked; the final version keeps that helper and restores the required legacy reference inventory plus sensor-contract derivation checks.

- Observation: The fan controller's emitted wire contract includes `fan_duty_pct`, even though it is not part of the legacy consumer-facing persisted metric set.
  Evidence: After `DEVICE_METRICS` became capability keyed, `apps/hwd/tests/test_ingest_derivation.py` initially failed until `_PLAUSIBLE` and the complete fan payload included `fan_duty_pct`.

- Observation: Firmware is organized as three separate PlatformIO projects, not a single root `firmware/platformio.ini`.
  Evidence: `find firmware -maxdepth 3 \( -path '*/test/*' -o -name 'platformio.ini' \) -print` found only `firmware/fan_controller/platformio.ini`, `firmware/plant_node/platformio.ini`, and `firmware/reservoir_node/platformio.ini`; no firmware test directories were present.

- Observation: The installed Atlas CLI differs from the local Atlas reference pack for validation/lint commands.
  Evidence: `atlas migrate hash --dry-run --env local` failed with `unknown flag: --dry-run`; `atlas migrate lint --env local --latest 1` failed because this Atlas version gates migrate lint behind Atlas Pro/login. `atlas migrate diff verify_scoped_device_heartbeat_sync --env local` succeeded with `The migration directory is synced with the desired state, no changes to be made`.

- Observation: The first Milestone 3 implementation still let unflashed legacy-only boards age offline after migration backfill.
  Evidence: Main-agent review found `ReadingsService.ingest_reading(... device_id=None ...)` called `_touch_device_heartbeat()` with `device_id=None`, and rejected legacy payloads called only `touch_node()`. Because `SystemStatusService` now reads `device.last_seen`, current unflashed firmware posting only `location` would update `sensornode.last_seen` but not canonical heartbeat.

- Observation: A Milestone 4 regression test file already existed in the worktree and encoded the right cross-tent risk.
  Evidence: `apps/shared/tests/test_milestone4_scope.py` created a breeding `soil_moisture_raw` capability and proved main plant moisture/daily snapshots must choose the main capability when the same legacy node id appears in test data.

- Observation: Plant and daily report test fixtures had to become capability-scoped to match current-path reads.
  Evidence: `apps/shared/tests/test_daily_sensors.py` and web plant endpoint tests now seed `SensorReading.capability_id` and `SensorCalibration.capability_id`; legacy `sensornode_id` remains present only for compatibility rows.

- Observation: `SnapshotsService.latest()` treated historical unscoped snapshots as fallback for every resolved tent, which would make an explicit breeding-tent latest-snapshot request return a main-era unscoped archive row.
  Evidence: Milestone 5 added `apps/web/tests/test_feed_snapshot_endpoint.py::test_latest_snapshot_scoped_404_when_only_unscoped_exists` and `test_latest_snapshot_accepts_tent_scope_without_unscoped_leak`; the service now keeps the unscoped fallback only for the default `homebox/main` request.

- Observation: Main-agent review found the first Milestone 5 snapshot fix still leaked snapshots for unresolved explicit scope ids.
  Evidence: `SnapshotsService.latest(site_id=..., tent_id=...)` only filtered when `resolve_scope()` returned a scope. Unknown `site_id` or `tent_id` left the base `select(Snapshot)` unfiltered, so `/api/feed/snapshot/latest?tent_id=unknown` could return an existing unscoped/default snapshot. The service now returns `None` when scope resolution fails, and `apps/web/tests/test_feed_snapshot_endpoint.py::test_latest_snapshot_unknown_scope_404_without_unscoped_leak` covers the API behavior.


## Decision Log

- Decision: Retire compatibility in stages; do not remove `sensornode` until firmware, heartbeat, plants, and daily sensors have canonical replacements.
  Rationale: Live boards and production dashboard behavior depend on the compatibility path today. Removing it before scoped payloads and device heartbeats are proven would risk losing hardware visibility.
  Date/Author: 2026-05-04 / Codex

- Decision: Keep legacy `location` ingest accepted for at least one release cycle after scoped firmware is flashed.
  Rationale: Real ESP32 boards may be updated one at a time. The server can prefer scoped fields and log legacy usage without blocking old payloads.
  Date/Author: 2026-05-04 / Codex

- Decision: Treat old unlinked `sensorreading` rows as historical data unless a safe capability mapping is known.
  Rationale: Some old metrics do not have current canonical equivalents (`pressure_hpa`, `reservoir_depth_cm`). Backfilling them blindly would create false data lineage. Current-path enforcement should focus on new rows first.
  Date/Author: 2026-05-04 / Codex

- Decision: Move device heartbeat columns onto canonical device ownership instead of creating a new fleet/cloud heartbeat service.
  Rationale: This box remains the hardware authority and already models local devices. A local `device` heartbeat or local `deviceheartbeat` table is enough; cloud/fleet identity is out of scope.
  Date/Author: 2026-05-04 / Codex

- Decision: Track stale model fields as Milestone 7 cleanup-removal items once they are identified.
  Rationale: Cleanup removals are real schema/API work and need their own Atlas migrations, contract updates, tests, and live rollout validation. They should not be left as vague final-exit criteria, but they also should not block earlier migration milestones unless a field actively prevents canonical scoped behavior.
  Date/Author: 2026-05-04 / Codex

- Decision: Remove `growrun.location` unless a future implementation finds a distinct non-scope meaning for it and records that meaning in this plan.
  Rationale: Site and tent FKs are the source of truth for where a grow run lives. Keeping a second free-form location string creates drift risk and invites code to route or display stale location text instead of using scoped identity.
  Date/Author: 2026-05-04 / Codex

- Decision: Make `schedule` the canonical owner of recurring lights photoperiod and remove the duplicate `growrun.lights_on_local` / `growrun.lights_off_local` columns.
  Rationale: A photoperiod is recurring operational schedule data attached to a tent/device/capability. `growrun` should describe the grow cycle itself. API responses may continue to include lights times for compatibility, but those values should be composed from the scoped `schedule` row.
  Date/Author: 2026-05-04 / Codex

- Decision: Keep Milestone 1 strictly audit/test-only and preserve the currently required ingest `location` field.
  Rationale: Milestone 2 is where ingest behavior changes. Milestone 1 should make current compatibility behavior visible without changing live board payload requirements.
  Date/Author: 2026-05-04 / Codex

- Decision: In Milestone 2, accept `location`-less scoped ingest only when `device_id` can be mapped to a known legacy `SensorLocation`.
  Rationale: `sensorreading.sensornode_id` remains required until later milestones retire `sensornode`; deriving the compatibility location from canonical `device_id` preserves current main-tent behavior while letting flashed boards stop depending on the wire `location` field.
  Date/Author: 2026-05-04 / Codex

- Decision: Keep `EMITTED_METRICS`, `PERSISTED_METRICS`, and `LEGACY_LOCATION_DEVICE_IDS` exported as derived compatibility maps.
  Rationale: Existing watchdog, daily-sensor, voice, and invariant code still imports the legacy maps. Making `DEVICE_METRICS` the only editable declaration delivers scoped-first ownership without mixing Milestone 2 with broader legacy deletion.
  Date/Author: 2026-05-04 / Codex

- Decision: Store canonical device heartbeat as nullable columns on `device`: `last_seen`, `ip`, `firmware_version`, and `uptime_ms`.
  Rationale: Current consumers need latest freshness only, not heartbeat history. Nullable columns are the smallest schema change and let existing seeded non-reporting devices remain valid until they actually heartbeat.
  Date/Author: 2026-05-04 / Codex

- Decision: Keep `ReadingsService.touch_node()` as a legacy wrapper and add `ReadingsService.touch_device()` for rejected scoped payloads.
  Rationale: Rejected-payload behavior must still update compatibility `sensornode` during the transition, while scoped boards need their canonical `device` heartbeat updated even when every metric is rejected by sensor-quality filtering.
  Date/Author: 2026-05-04 / Codex

- Decision: Legacy-only known-location ingest derives canonical heartbeat ownership through `LEGACY_LOCATION_DEVICE_IDS`.
  Rationale: Firmware rollout is staged. Until every board is flashed with `device_id`, known `location` posts must keep both compatibility `sensornode` and canonical `device` heartbeat fresh so system status and watchdog behavior do not regress.
  Date/Author: 2026-05-04 / Codex

- Decision: Gate metric freshness snapshots on canonical `device.last_seen` instead of `sensornode.last_seen`.
  Rationale: Metric freshness deliberately suppresses per-metric alerts when a whole device is stale. After Milestone 3, whole-device freshness is owned by `device`, so keeping the gate on `sensornode` would preserve the retired ownership path.
  Date/Author: 2026-05-04 / Codex

- Decision: Add nullable `plant.moisture_capability_id` and keep `plant.sensornode_id` during the transition.
  Rationale: Current plants can be backfilled to canonical capability ownership immediately, while keeping the legacy FK avoids mixing Milestone 4 with the later schema cleanup/removal milestone. Current read paths prefer the capability FK and use the legacy node only as a pre-backfill fallback.
  Date/Author: 2026-05-04 / Codex

- Decision: Daily report plant moisture resolves through the current main grow's `Plant.moisture_capability_id`.
  Rationale: Daily reports are still default-main in this milestone, and plant rows are the explicit owner of each plant's moisture stream. This prevents a second tent with the same metric name from contaminating main plant moisture values.
  Date/Author: 2026-05-04 / Codex

- Decision: Add optional `site_id` and `tent_id` query parameters to `/api/sensors/current`, `/api/sensors/history`, `/api/plants`, and `/api/feed/snapshot/latest`, but do not add a visible frontend tent selector in Milestone 5.
  Rationale: These four routes are the default-main dashboard compatibility URLs called out by the milestone. Query params are the smallest coherent contract shape that proves scoped access without changing existing URLs or creating a larger multi-site UI. The current React dashboard remains default-main, so no React Query key changes are needed in this milestone.
  Date/Author: 2026-05-04 / Codex

- Decision: Keep historical unscoped snapshot fallback only for `homebox/main`.
  Rationale: Old archive rows may not carry scope and should still appear on the existing default-main latest-snapshot URL, but an explicit non-main request must not leak default-main or historical unscoped media.
  Date/Author: 2026-05-04 / Codex

- Decision: Treat unresolved snapshot scope as no match rather than a request for all snapshots.
  Rationale: Unknown explicit scope ids are not a compatibility path. Returning `None` lets the API produce 404 and prevents invalid scope parameters from bypassing scoped filtering.
  Date/Author: 2026-05-04 / Codex


## Outcomes & Retrospective

Milestone 1 is complete. The repo now has executable guardrails that show where legacy `SensorLocation`, `SensorNode`, `sensornode_id`, legacy metric maps, and `legacy_location` are still present; it also proves current writes stay centralized and carry `capability_id` through the compatibility path. Focused HWD ingest and web history tests preserve current main-tent behavior while making scoped capability writes and breeding-data exclusion observable.

No schema changes, firmware changes, hosted/cloud control, or behavior changes were made in Milestone 1.

Milestone 2 is complete. ESP32 firmware payloads now include `site_id`, `tent_id`, `zone_id`, and `device_id` while retaining legacy `location`. HWD ingest accepts scoped payloads without `location` for known devices, derives the compatibility `SensorLocation` from canonical `device_id`, logs a structured warning with `legacy_location=true` for known legacy-only boards, and keeps resolving capabilities by `device_id` plus metric name. The sensor contract's editable source is now keyed by canonical `device_id` and capability/metric identity, with legacy maps derived for compatibility. No schema changes or hosted/cloud control were added.

Milestone 3 is complete. The `device` table now owns latest heartbeat fields, with an Atlas migration that backfills ESP32-compatible devices from `sensornode` using `device.metadata->>'legacy_location'` and then backfills any still-null scoped devices, such as the Govee humidifier, from their latest capability reading. `ReadingsService.ingest_reading()` updates canonical device heartbeat whenever scoped `device_id` is present, or derives the heartbeat `device_id` from known legacy `location` when scoped identity is absent, and still updates `sensornode` for compatibility. `ReadingsService.touch_node()` remains a legacy wrapper and also refreshes canonical device heartbeat for known legacy locations. `touch_device()` handles rejected scoped payloads while also touching the compatibility node. `SystemStatusService` reads device heartbeat directly for ESP32 nodes and the Govee humidifier, and `DeviceWatchdogService` continues to persist stable `device_id` state keys through unchanged status objects. `docs/observability.md` now documents that metric freshness is gated by `device.last_seen`.

Milestone 4 is complete. `Plant` rows now carry nullable `moisture_capability_id`, backfilled for the current A-D main plants from legacy `sensornode.location` to the canonical plant-node `soil_moisture_raw` capability. `PlantsService` uses that capability for latest moisture and history queries, and `SensorReader` uses the current grow's plant capability for daily-report plant moisture. Default-main `/api/plants`, plant detail, plant moisture history, daily sensor snapshots, and daily report tests still pass. `Plant.sensornode_id` remains for legacy compatibility and later Milestone 7 removal; no hosted/cloud control was added.

Milestone 5 is complete. The existing default-main routes `/api/sensors/current`, `/api/sensors/history`, `/api/plants`, and `/api/feed/snapshot/latest` still work without query parameters, and each now accepts optional `site_id` and `tent_id` query parameters. Sensors current/history thread the scope into canonical capability reads; plants list threads scope into `PlantsService` and grow-day composition; latest snapshot returns scoped media for explicit non-main requests and no longer falls back to unscoped archives outside `homebox/main`. The OpenAPI contract and generated TypeScript schema were regenerated. No hosted/cloud control, remote execution, public multi-site UI, or visible frontend selector was added.

Post-review Milestone 5 cleanup fixed an invalid-scope snapshot leak: `SnapshotsService.latest()` now returns `None` when `resolve_scope()` cannot resolve the requested site/tent, so the API returns 404 instead of falling through to an unfiltered latest snapshot query.


## Context and Orientation

Dirt is a uv Python workspace. The relevant packages are `apps/shared/` for SQLModel models and services, `apps/hwd/` for the local hardware daemon and ingest endpoint on port 8000, `apps/web/` for the local web/API service on port 8001, `contracts/` for OpenAPI and generated Python/TypeScript clients, `web-ui/` for the React dashboard, and `firmware/` for ESP32 code.

Phase 1 introduced canonical scoped identity:

- `site`: physical installation. The live default is `site.site_id='homebox'`.
- `tent`: logical grow tent. The live default is `tent.tent_id='main'`; `breeding` exists with no active control loops.
- `zone`: logical area such as `canopy`, `plant-a`, `reservoir`, or `lights`.
- `device`: physical or service-controlled local device such as `fan-controller`, `plant-a-node`, `govee-h7142-main`, `kasa-lights-main`, `obsbot-main`, and `jabra-claudia`.
- `capability`: something a device measures or does, such as `temperature_f`, `humidity_pct`, `soil_moisture_raw`, `mist_level`, `lights_power`, or `ptz_move`.

The major remaining legacy surfaces are:

- `apps/shared/src/dirt_shared/models/enums.py`: `SensorLocation` and the Postgres enum `sensor_location`.
- `apps/shared/src/dirt_shared/models/sensor_node.py`: legacy heartbeat rows keyed by `SensorLocation`.
- `apps/shared/src/dirt_shared/models/sensor_reading.py`: still has non-null `sensornode_id` plus nullable `capability_id`.
- `apps/shared/src/dirt_shared/models/sensor_calibration.py`: still has nullable `sensornode_id`, `metric`, and capability ownership.
- `apps/shared/src/dirt_shared/models/plant.py`: still has `sensornode_id` for plant moisture.
- `apps/shared/src/dirt_shared/sensor_contract.py`: still exports legacy `EMITTED_METRICS`, `PERSISTED_METRICS`, and `LEGACY_LOCATION_DEVICE_IDS` keyed by `SensorLocation`.
- `apps/shared/src/dirt_shared/services/readings.py`: still resolves legacy location to device and writes `sensornode` rows.
- `apps/shared/src/dirt_shared/services/daily_sensors.py`: still uses `SensorLocation` constants and node-scoped reads.
- `apps/shared/src/dirt_shared/services/plants.py`: still reads plant moisture through `Plant.sensornode_id`.
- `apps/shared/src/dirt_shared/services/system_status.py`: still uses `Device.metadata["legacy_location"]` to bridge device rows to `sensornode.last_seen`.
- `apps/hwd/src/dirt_hwd/api/ingest.py`: still accepts required `location`, with optional scoped fields.
- `apps/voice/src/dirt_voice/tools/sensors.py`: still reads tent and plant sensor summaries through `SensorLocation`, `SensorNode`, `sensornode_id`, and legacy persisted metric maps.
- `firmware/*/src/main.cpp`: still sends legacy `location` payloads.
- `apps/web/src/dirt_web/api/sensors.py` and `metric_registry.py`: still assemble default-main dashboards through legacy metric/location registry concepts.

Additional cleanup-removal candidates that are not strictly `sensornode` compatibility:

- `growrun.location`: remove after API/frontend consumers stop requiring `GrowCurrent.location`. Any UI display should use `tent.name`, `site.location`, or an intentionally named grow-run note field instead of a duplicate scope label.
- `growrun.lights_on_local` and `growrun.lights_off_local`: remove after `GrowStateService`, lights loop code, flower-flip/update paths, API response mapping, tests, and frontend fixtures use the scoped `schedule` row as the only persisted photoperiod source. Keep local wall-clock `time` plus IANA `timezone` on `schedule`; do not convert recurring daily photoperiods to stored UTC.

Operational state after rollout:

- Backup before migration: `var/db-backups/dirt-before-multi-tent-rollout-2026-05-03-211914.sql`.
- Atlas live version: `20260504022916`.
- New readings after restart were all capability-linked in the live smoke check.
- A PTZ no-op zoom created a successful local command row for `obsbot-main` / `ptz_move`.


## Plan of Work

Milestone 1: Audit and guard current legacy paths.

Add tests and small diagnostic helpers that make remaining legacy use visible before behavior changes. The output of this milestone is not a refactor; it is an executable map of what still depends on `SensorLocation`, `sensornode`, `sensornode_id`, or metric-only defaults.

Add or update tests under agent-owned test directories only:

- `apps/shared/tests/test_legacy_retirement_audit.py`: assert current live code has no new unscoped writers except the explicitly allowed compatibility functions.
- `apps/hwd/tests/test_ingest_api.py`: assert scoped payloads write `sensorreading.capability_id` and do not need legacy location mapping.
- `apps/web/tests/test_sensors_history_endpoint.py`: keep proving default main history excludes breeding data.
- `apps/tests/invariants/` must not be edited.

Milestone 2: Make firmware and ingest scoped-first.

Update ESP32 firmware to send scoped identity fields in addition to legacy `location`:

- `firmware/fan_controller/src/main.cpp`: send `site_id=homebox`, `tent_id=main`, `zone_id=canopy`, `device_id=fan-controller`.
- `firmware/plant_node/src/main.cpp`: send `site_id=homebox`, `tent_id=main`, `zone_id=plant-<id>`, `device_id=plant-<id>-node`.
- `firmware/reservoir_node/src/main.cpp`: send `site_id=homebox`, `tent_id=main`, `zone_id=reservoir`, `device_id=reservoir-node`.

Update `apps/hwd/src/dirt_hwd/api/ingest.py` so `location` is optional when scoped identity is present. Keep old payloads accepted, but log a structured warning with `legacy_location=true` when a known legacy-only board posts without `device_id`. The new preferred ingest path must resolve capabilities from `device_id` plus metric name, not from `location`.

Update `apps/shared/src/dirt_shared/sensor_contract.py` to make the canonical declaration keyed by `device_id` and `capability_id`, with legacy `SensorLocation` maps derived only for firmware compatibility. Tests should fail if a new canonical device metric is added only to the legacy maps.

Milestone 3: Move device heartbeat/freshness ownership to canonical devices.

Add canonical heartbeat storage. The simplest path is adding nullable heartbeat columns to `device`: `last_seen`, `ip`, `firmware_version`, and `uptime_ms`. If the model shape suggests append-only history is more useful, add a separate `deviceheartbeat` table with latest-query helpers, but do not add any hosted/cloud fleet component.

Use Atlas for schema changes:

- edit `apps/shared/src/dirt_shared/models/device.py` or add `models/device_heartbeat.py`;
- run `atlas migrate diff scoped_device_heartbeat --env local`;
- hand-review/backfill from `sensornode`;
- run `atlas migrate hash --env local` if hand-editing the migration.

Update these services:

- `ReadingsService.ingest_reading()` updates device heartbeat from scoped `device_id`;
- `ReadingsService.touch_node()` becomes a legacy wrapper or is renamed to a device heartbeat method;
- `SystemStatusService` reads device heartbeat directly and no longer needs `Device.metadata["legacy_location"]`;
- `DeviceWatchdogService` keeps stable `device_id` state keys.

Milestone 4: Move plant moisture and daily sensors off `sensornode_id`.

Add canonical plant moisture ownership. Prefer adding `plant.moisture_capability_id` or an equivalent explicit capability FK so plants no longer need a direct `sensornode_id` to find their moisture stream.

Update:

- `apps/shared/src/dirt_shared/models/plant.py`;
- `apps/shared/src/dirt_shared/services/plants.py`;
- `apps/shared/src/dirt_shared/services/daily_sensors.py`;
- `apps/shared/src/dirt_shared/services/readings.py` calibration helpers;
- plant and daily report tests under `apps/shared/tests/` and `apps/web/tests/`.

Backfill current A-D plants from their existing legacy `sensornode_id` to canonical plant node `soil_moisture_raw` capabilities. Preserve default-main `/api/plants` and daily report output.

Milestone 5: Make scoped API/frontend access first-class without breaking default-main URLs.

Keep the existing unscoped endpoints as default-main compatibility, but add scoped query parameters or scoped frontend state where it improves real use:

- Decide whether `/api/sensors/current`, `/api/sensors/history`, `/api/plants`, and `/api/feed/snapshot/latest` should accept optional `site_id` and `tent_id`.
- If API shape changes, update `contracts/webapp-v1.yaml`, run `scripts/gen-contract`, and format generated TypeScript with `pnpm --dir web-ui exec biome check --write src/api-client/generated/schema.ts`.
- If adding a visible frontend tent selector, read `docs/references/tanstack-router-v1/INDEX.md`, `docs/references/tailwind-v4/INDEX.md`, and `docs/references/modern-idiomatic-typescript/INDEX.md` first. The selector must default to `main`; React Query keys must include `tent_id`.

Do not build hosted auth, cloud command submission, remote execution, or public multi-site UI here.

Milestone 6: Backfill/quarantine historical unscoped data and tighten current-path constraints.

Classify historical null `capability_id` rows before tightening anything:

    SELECT sr.metric, sn.location, count(*), max(sr.ts) AS latest
    FROM sensorreading sr
    JOIN sensornode sn ON sn.id = sr.sensornode_id
    WHERE sr.capability_id IS NULL
    GROUP BY sr.metric, sn.location
    ORDER BY latest DESC;

Known rollout examples were old `pressure_hpa`, `humidifier_on`, `humidifier_mist_level`, `reservoir_depth_cm`, and a few one-off plant rows. For each metric, either add a real canonical capability and backfill, or explicitly leave it as historical-unscoped data.

Then add current-path guards:

- tests proving new ingest writes `capability_id`;
- optional database constraints only if historical data has been handled safely;
- app-level rejection or warning for any new known-device reading that cannot resolve a capability.

Do not set `sensorreading.capability_id NOT NULL` while known historical rows remain null unless the migration first safely backfills or archives them.

Milestone 7: Remove dead legacy code and optional schema artifacts.

After firmware and services use canonical identity:

- remove or narrow `SensorLocation` imports from production services;
- delete legacy `LEGACY_LOCATION_DEVICE_IDS` and legacy-only metric maps if no live code uses them;
- remove `Plant.sensornode_id` if plant moisture capability ownership fully replaces it;
- remove `SensorCalibration.sensornode_id` and legacy unique constraints if no compatibility path needs them;
- consider dropping `sensornode` and the `sensor_location` enum only after all FKs and live uses are gone;
- remove `GrowRun.location` and the corresponding API/contract/frontend fixture field unless it has been deliberately redefined as something other than scope. Use an Atlas migration to drop the column, update `apps/shared/src/dirt_shared/models/grow_run.py`, remove response mapping from `apps/web/src/dirt_web/api/grow.py`, update `contracts/webapp-v1.yaml`, regenerate clients, and replace display needs with `tent.name` or `site.location`;
- remove `GrowRun.lights_on_local` and `GrowRun.lights_off_local` after confirming the scoped `schedule` row is authoritative. Before dropping columns, update `GrowStateService.current_light_schedule()`, `lights_state()`, flower-flip/write paths, `LightsLoopService`, `/api/grow/current` response mapping, tests, OpenAPI schemas, generated clients, and frontend fixtures so compatibility responses are composed from `schedule.starts_local`, `schedule.ends_local`, and `schedule.timezone`;
- update `docs/database.md`, `docs/observability.md`, and this plan.

This milestone is intentionally last. It should be mostly deletion plus schema cleanup, not mixed with behavior migration.


## Concrete Steps

Start every milestone from a clean worktree:

    cd /home/akcom/code/dirt
    git status --short

Read these documents before implementation:

    sed -n '1,260p' .agents/PLANS.md
    sed -n '1,220p' docs/commands.md
    sed -n '1,180p' docs/database.md
    sed -n '1,220p' docs/observability.md
    sed -n '1,240p' docs/references/atlas/INDEX.md
    sed -n '1,260p' docs/epics/multi-tent-controller/LegacyCompatibilityRetirementExecPlan.md

For frontend TypeScript or routes, also read:

    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/tailwind-v4/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md

For schema work, use Atlas only:

    atlas migrate diff <short_name> --env local
    atlas migrate hash --env local
    atlas migrate diff verify_<short_name>_sync --env local

Before applying to the live DB, take a backup:

    mkdir -p var/db-backups
    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump -h 127.0.0.1 -U dirt -d dirt > var/db-backups/dirt-before-legacy-retirement-$(date +%F-%H%M%S).sql
    atlas migrate apply --env local

Run focused tests after each slice. Candidate commands:

    uv run pytest apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py -q
    uv run pytest apps/shared/tests/test_readings_scope.py apps/shared/tests/test_milestone4_scope.py apps/shared/tests/test_commands.py -q
    uv run pytest apps/shared/tests/test_daily_sensors.py apps/shared/tests/test_daily_report.py -q
    uv run pytest apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py apps/web/tests/test_scope_endpoints.py -q
    uv run pytest apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py -q
    uv run pytest apps/web/tests/test_system_devices_endpoint.py apps/hwd/tests/test_device_watchdog.py apps/hwd/tests/test_humidifier_loop.py apps/hwd/tests/test_fan_controller.py apps/hwd/tests/test_lights_loop.py -q

If contracts change:

    scripts/gen-contract
    pnpm --dir web-ui exec biome check --write src/api-client/generated/schema.ts
    uv run pytest apps/tests/invariants/test_api_contract.py -q
    pnpm --dir web-ui lint
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui test

Before committing:

    scripts/agent-fix
    uv run pytest apps/tests/invariants/ -q
    uv run pytest apps/shared/tests apps/hwd/tests apps/web/tests -q
    git diff --check


## Validation and Acceptance

The work is complete when these behaviors are observable:

- Existing deployed firmware payloads using only `location` still receive `202 Accepted` during the compatibility window.
- Scoped firmware payloads with `site_id`, `tent_id`, `zone_id`, and `device_id` write readings with non-null `sensorreading.capability_id`.
- Current live sensor readings for known devices have `capability_id`; an unresolved known-device metric logs or rejects clearly instead of silently writing unscoped current data.
- Device status and watchdog freshness use canonical `device` heartbeat state, not `sensornode.last_seen`.
- Plant moisture and daily report sensor summaries read from plant/capability ownership, not `Plant.sensornode_id`.
- Scoped API calls can fetch sensors/plants/snapshots for `main` and return empty or scoped data for `breeding` without leaking main data.
- The frontend either remains default-main only with generated types passing, or has a minimal tent selector that defaults to `main` and includes `tent_id` in query keys.
- If `sensornode` or `SensorLocation` remain, this plan documents why and the remaining live dependency. If no live dependency remains, schema and code no longer expose them.
- `growrun.location` is removed from the SQLModel, Atlas schema, migration state, OpenAPI contract, generated clients, and frontend fixtures unless a distinct non-scope meaning is documented in this plan before Milestone 7.
- `growrun.lights_on_local` and `growrun.lights_off_local` are removed from the SQLModel, Atlas schema, migration state, and generated contracts after tests prove grow-current responses and lights-loop decisions read the scoped `schedule` row.
- A validation query or test proves each active tent that should have lights control has exactly one enabled photoperiod schedule, and no service writes photoperiod times to `growrun`.
- `apps/tests/invariants/` is unchanged.
- `atlas migrate diff verify_... --env local` reports no schema drift after any migration.

Operational smoke after live apply:

    systemctl --user restart dirt-hwd dirt-web
    systemctl --user --no-pager --full status dirt-hwd dirt-web
    journalctl --user -u dirt-hwd -u dirt-web --since '5 minutes ago' --no-pager -p warning..alert

API smoke with auth cookie:

    set -a; source .env; set +a
    COOKIES=$(mktemp)
    curl -sS -c "$COOKIES" -H 'Content-Type: application/json' \
      -d "{\"username\":\"${AUTH_USERNAME:-admin}\",\"password\":\"${AUTH_PASSWORD:-changeme}\"}" \
      http://127.0.0.1:8001/api/auth/login >/dev/null
    curl -sS -b "$COOKIES" http://127.0.0.1:8001/api/grow/current
    curl -sS -b "$COOKIES" http://127.0.0.1:8001/api/sites
    curl -sS -b "$COOKIES" http://127.0.0.1:8001/api/tents
    curl -sS -b "$COOKIES" http://127.0.0.1:8001/api/tents/main/devices
    rm -f "$COOKIES"


## Idempotence and Recovery

Most service and API refactors are safe to rerun under pytest. Migrations must be handled with the normal Atlas workflow and reviewed before apply.

Before any live schema apply, create a `pg_dump` backup under `var/db-backups/`. If migration fails before commit, Atlas/Postgres should leave the failed statement transaction state visible; inspect and stop. If migration applies but services fail after restart, stop services and restore the backup only after deciding the failure is unsafe for hardware operation:

    systemctl --user stop dirt-hwd dirt-web
    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt < var/db-backups/<backup-file>.sql
    systemctl --user start dirt-hwd dirt-web

Firmware rollout must be staged. Keep the server accepting legacy `location` payloads until all boards are confirmed posting scoped identity. If a board fails after flashing, revert that board firmware or rely on server legacy compatibility; do not drop the legacy ingest path in the same milestone as firmware changes.

Do not run destructive commands such as `git reset --hard`, dropping tables manually, deleting `var/`, or force-pushing without explicit user approval.


## Artifacts and Notes

Phase 1 commits already on `main`:

    2dd05fd Move current grow to scoped grow runs
    f213968 Scope telemetry and remaining local state
    4a5ce0f Add scoped control and API surfaces

Live migration rollout evidence from 2026-05-03 MDT:

    atlas migrate status --env local
    Migration Status: OK
      -- Current Version: 20260504022916
      -- Pending Files:   0

    SELECT count(*) FILTER (WHERE capability_id IS NOT NULL), count(*)
    FROM sensorreading
    WHERE ts > '2026-05-04 03:20:00+00';
    linked_after_restart = 49, total_after_restart = 49

    POST /api/ptz/zoom {"zoom": 1.0}
    recorded command row: ptz.zoom / local_api / succeeded / obsbot-main / ptz_move

Historical unlinked reading classes seen immediately after rollout:

    pressure_hpa          tent
    humidifier_on         tent
    humidifier_mist_level tent
    reservoir_depth_cm    reservoir
    one-off plant moisture rows

These should be classified before any `NOT NULL` or FK tightening on historical telemetry.

Milestone 1 audit artifacts added:

    apps/shared/tests/test_legacy_retirement_audit.py
    apps/hwd/tests/test_ingest_api.py::test_scoped_device_id_writes_capability_without_legacy_location_mapping
    apps/web/tests/test_sensors_history_endpoint.py::test_sensors_history_defaults_to_main_tent

These tests are guards only. They intentionally preserve the current required
legacy `location` field and the compatibility `sensornode_id` write while
making both visible before Milestone 2 changes ingest behavior.

Main-agent review rework expanded the static audit from the original
shared/HWD/web-only scan to every `apps/*/src` Python source root and added
`apps/voice/src/dirt_voice/tools/sensors.py` to the explicit legacy read
inventory. The centralized writer guard still allows only the compatibility
writers in `dirt_shared.services.readings`; voice adds no writer allowance
because it does not construct `SensorReading`, `SensorCalibration`, or
`SensorNode`.

Milestone 1 validation evidence from 2026-05-04:

    uv run pytest apps/shared/tests/test_legacy_retirement_audit.py -q
    4 passed in 0.39s

    uv run pytest apps/hwd/tests/test_ingest_api.py -q
    15 passed in 4.17s

    uv run pytest apps/hwd/tests/test_ingest_derivation.py -q
    9 passed in 0.34s

    uv run pytest apps/web/tests/test_sensors_history_endpoint.py -q
    12 passed in 5.00s

    uv run pytest apps/shared/tests/test_readings_scope.py -q
    1 passed in 1.45s

    uv run ruff check apps/shared/tests/test_legacy_retirement_audit.py apps/hwd/tests/test_ingest_api.py apps/web/tests/test_sensors_history_endpoint.py
    All checks passed.

    uv run ruff format --check apps/shared/tests/test_legacy_retirement_audit.py apps/hwd/tests/test_ingest_api.py apps/web/tests/test_sensors_history_endpoint.py
    3 files already formatted

The simplify pass used the local fallback because no subagent spawn tool was available. It kept the scope unchanged and applied two cleanup fixes: clearer static-inventory failure diagnostics and a stronger web history assertion that returned default-main values stay inside the seeded main range.

Milestone 2 validation evidence from 2026-05-04 before simplify:

    uv run pytest apps/hwd/tests/test_ingest_api.py -q
    18 passed in 4.70s

    uv run pytest apps/hwd/tests/test_ingest_derivation.py -q
    9 passed in 0.39s

    uv run pytest apps/shared/tests/test_legacy_retirement_audit.py -q
    5 passed in 0.45s

    uv run pytest apps/tests/invariants/test_sensor_contract.py -q
    2 passed in 0.20s

    uv run pytest apps/shared/tests/test_readings_scope.py -q
    1 passed in 1.47s

    pio run -e fan
    fan SUCCESS in 5.16s

    pio run -e plant-a
    plant-a SUCCESS in 4.18s; existing ADC_ATTEN_DB_11 deprecation warning remains unrelated to this milestone.

    pio run -e reservoir
    reservoir SUCCESS in 4.32s

    uv run ruff check apps/hwd/src/dirt_hwd/api/ingest.py apps/shared/src/dirt_shared/sensor_contract.py apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/shared/tests/test_legacy_retirement_audit.py
    All checks passed.

    uv run ruff format --check apps/hwd/src/dirt_hwd/api/ingest.py apps/shared/src/dirt_shared/sensor_contract.py apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/shared/tests/test_legacy_retirement_audit.py
    5 files already formatted

Milestone 2 simplify pass used the local fallback because no subagent spawn tool was available. The reuse/quality/efficiency review found one worthwhile cleanup around duplicated emitted/persisted metric derivation. A later invariant pass required keeping the canonical declaration as literal tuples instead of dataclass constructor calls, so the final helpers are pure functions over the tuple declaration. No firmware or behavior changes were made during the simplify pass.

Milestone 2 validation evidence from 2026-05-04 after simplify:

    uv run pytest apps/tests/invariants/ -q
    115 passed, 1 skipped in 3.97s

    uv run pytest apps/hwd/tests/test_ingest_api.py -q
    19 passed in 4.75s

    uv run pytest apps/hwd/tests/test_ingest_derivation.py -q
    9 passed in 0.34s

    uv run pytest apps/shared/tests/test_legacy_retirement_audit.py -q
    5 passed in 0.38s

    uv run pytest apps/tests/invariants/test_sensor_contract.py -q
    2 passed in 0.19s

    uv run pytest apps/shared/tests/test_readings_scope.py -q
    1 passed in 1.44s

    uv run ruff check apps/hwd/src/dirt_hwd/api/ingest.py apps/shared/src/dirt_shared/sensor_contract.py apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/shared/tests/test_legacy_retirement_audit.py
    All checks passed.

    uv run ruff format --check apps/hwd/src/dirt_hwd/api/ingest.py apps/shared/src/dirt_shared/sensor_contract.py apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/shared/tests/test_legacy_retirement_audit.py
    5 files already formatted

Post-review Milestone 2 cleanup added `apps/hwd/tests/test_ingest_api.py::test_unknown_device_id_without_location_is_rejected` to lock the narrowed compatibility behavior: scoped ingest without `location` is accepted only for device IDs that can still derive a legacy compatibility location. The stale comment in the mismatched-location capability-resolution test was updated to describe the Milestone 2 behavior.

Pre-commit invariant cleanup removed the HWD API import of `dirt_shared.models.enums` by returning and using legacy location strings at the API boundary. It also replaced module-level `DeviceContract(...)` and `MetricContract(...)` dataclass constructor calls in `dirt_shared.sensor_contract` with a literal tuple-based `DEVICE_METRICS` declaration.

    pio run -e fan
    fan SUCCESS in 1.78s

    pio run -e plant-a
    plant-a SUCCESS in 1.18s

    pio run -e plant-b -e plant-c -e plant-d
    plant-b, plant-c, and plant-d SUCCESS in 5.90s; existing ADC_ATTEN_DB_11 deprecation warnings remain unrelated to this milestone.

    pio run -e reservoir
    reservoir SUCCESS in 1.33s

Milestone 3 migration artifact:

    migrations/20260504052839_scoped_device_heartbeat.sql

The migration adds nullable heartbeat columns to `device`, backfills current
ESP32 heartbeat data from `sensornode` via `device.metadata->>'legacy_location'`,
and backfills non-legacy scoped devices from their latest capability reading
where no explicit heartbeat exists. No live `atlas migrate apply` was run for
this milestone.

Milestone 3 simplify pass used the local fallback because no subagent spawn
tool was available. Reuse/quality/efficiency review found two worthwhile
cleanup items: remove the now-unused `_ScopedDevice.pk` field after actuator
status stopped querying readings, and batch freshness device heartbeat lookups
instead of re-querying one device per legacy location.

Milestone 3 validation evidence from 2026-05-04:

    atlas migrate diff scoped_device_heartbeat --env local
    generated migrations/20260504052839_scoped_device_heartbeat.sql

    atlas migrate hash --env local
    completed after hand-editing the migration backfill

    atlas migrate diff verify_scoped_device_heartbeat_sync --env local
    The migration directory is synced with the desired state, no changes to be made

    atlas migrate hash --env local
    rerun after adding the latest-capability-reading backfill for non-legacy scoped devices

    atlas migrate diff verify_scoped_device_heartbeat_sync --env local
    rerun after the additional backfill; still synced with desired state

    uv run pytest apps/shared/tests/test_readings_scope.py -q
    rerun after the additional migration backfill; 2 passed in 1.63s

    atlas migrate hash --dry-run --env local
    failed: installed Atlas reports `unknown flag: --dry-run`

    atlas migrate lint --env local --latest 1
    failed: installed Atlas gates migrate lint behind Atlas Pro/login

    uv run pytest apps/shared/tests/test_readings_scope.py apps/shared/tests/test_system_status_scope.py apps/shared/tests/test_legacy_retirement_audit.py apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_device_watchdog.py -q
    39 passed in 7.12s

    uv run ruff check apps/shared/src/dirt_shared/models/device.py apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/system_status.py apps/hwd/src/dirt_hwd/api/ingest.py apps/hwd/src/dirt_hwd/services/metric_freshness.py apps/hwd/tests/test_ingest_api.py apps/shared/tests/test_readings_scope.py apps/shared/tests/test_system_status_scope.py apps/shared/tests/test_legacy_retirement_audit.py
    All checks passed.

    uv run ruff format apps/shared/src/dirt_shared/models/device.py apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/system_status.py apps/hwd/src/dirt_hwd/api/ingest.py apps/hwd/src/dirt_hwd/services/metric_freshness.py apps/hwd/tests/test_ingest_api.py apps/shared/tests/test_readings_scope.py apps/shared/tests/test_system_status_scope.py apps/shared/tests/test_legacy_retirement_audit.py
    completed; one file reformatted before lint/test, no further format changes after simplify

Final Milestone 3 validation after the ExecPlan update:

    uv run pytest apps/shared/tests/test_readings_scope.py apps/shared/tests/test_system_status_scope.py apps/shared/tests/test_legacy_retirement_audit.py -q
    8 passed in 2.06s

    uv run pytest apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_device_watchdog.py -q
    31 passed in 6.15s

    uv run pytest apps/web/tests/test_system_devices_endpoint.py -q
    2 passed in 0.61s

    uv run pytest apps/tests/invariants/ -q
    115 passed, 1 skipped in 3.98s

    uv run ruff check apps/shared/src/dirt_shared/models/device.py apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/system_status.py apps/hwd/src/dirt_hwd/api/ingest.py apps/hwd/src/dirt_hwd/services/metric_freshness.py apps/hwd/tests/test_ingest_api.py apps/shared/tests/test_readings_scope.py apps/shared/tests/test_system_status_scope.py apps/shared/tests/test_legacy_retirement_audit.py
    All checks passed.

    uv run ruff format --check apps/shared/src/dirt_shared/models/device.py apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/system_status.py apps/hwd/src/dirt_hwd/api/ingest.py apps/hwd/src/dirt_hwd/services/metric_freshness.py apps/hwd/tests/test_ingest_api.py apps/shared/tests/test_readings_scope.py apps/shared/tests/test_system_status_scope.py apps/shared/tests/test_legacy_retirement_audit.py
    9 files already formatted

    git diff --check
    passed with no output

Milestone 4 migration artifact:

    migrations/20260504054904_plant_moisture_capability.sql

The migration adds nullable `plant.moisture_capability_id`, backfills current
main A-D plants by joining `plant.sensornode_id -> sensornode.location` to the
canonical `plant-<letter>-node` `soil_moisture_raw` capability, and indexes the
new FK. No live `atlas migrate apply` was run for this milestone.

Milestone 4 simplify pass used the local fallback because no subagent spawn
tool was available. Reuse/quality/efficiency review found one worthwhile
cleanup: `apps/shared/tests/test_daily_sensors.py` now derives test capability
ids from seeded canonical capabilities instead of carrying a hardcoded metric
name list. Repeated web endpoint seed helpers were left local because they
match the existing per-file test style and a shared test helper would add
scope churn.

Milestone 4 validation evidence from 2026-05-04:

    atlas migrate diff plant_moisture_capability --env local
    generated migrations/20260504054904_plant_moisture_capability.sql

    atlas migrate hash --env local
    completed after hand-editing the migration backfill

    atlas migrate diff verify_plant_moisture_capability_sync --env local
    The migration directory is synced with the desired state, no changes to be made

    atlas migrate status --env local
    Migration Status: PENDING; Current Version 20260504022916; Next Version 20260504052839; Pending Files 2. This is expected because the live Milestone 3 and Milestone 4 migrations were intentionally not applied.

    uv run pytest apps/shared/tests/test_milestone4_scope.py apps/shared/tests/test_daily_sensors.py apps/shared/tests/test_daily_report.py -q
    41 passed in 7.20s

    uv run pytest apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py -q
    14 passed in 3.99s

    uv run pytest apps/shared/tests/test_legacy_retirement_audit.py apps/shared/tests/test_readings_scope.py -q
    9 passed in 2.28s

    uv run pytest apps/tests/invariants/ -q
    115 passed, 1 skipped in 4.00s

    uv run ruff format --check apps/shared/src/dirt_shared/models/plant.py apps/shared/src/dirt_shared/services/plants.py apps/shared/src/dirt_shared/services/daily_sensors.py apps/shared/tests/test_daily_sensors.py apps/shared/tests/test_milestone4_scope.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py
    8 files already formatted

    uv run ruff check apps/shared/src/dirt_shared/models/plant.py apps/shared/src/dirt_shared/services/plants.py apps/shared/src/dirt_shared/services/daily_sensors.py apps/shared/tests/test_daily_sensors.py apps/shared/tests/test_milestone4_scope.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py
    All checks passed.

    git diff --check
    passed with no output

Milestone 5 contract artifacts:

    contracts/webapp-v1.yaml
    web-ui/src/api-client/generated/schema.ts

The contract adds optional `site_id` and `tent_id` query parameters to:

    GET /api/sensors/current
    GET /api/sensors/history
    GET /api/plants
    GET /api/feed/snapshot/latest

`scripts/gen-contract` was run. The generated Pydantic models did not retain a
diff after `uv run ruff format contracts/python/src/dirt_contracts/webapp_v1/models.py`
because the API response schemas did not change; the generated TypeScript
operation types changed to expose the optional query parameters.

Milestone 5 focused validation evidence from 2026-05-04 before simplify:

    uv run pytest apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_feed_snapshot_endpoint.py -q
    27 passed in 8.67s

Milestone 5 simplify pass used the local fallback because no subagent spawn
tool was available. Reuse/quality/efficiency review found two worthwhile
cleanup items: a small `latest()` helper in `apps/web/src/dirt_web/api/sensors.py`
to avoid repeating the scope args for every dashboard metric, and a cleaner
current-endpoint test seeder that avoids opening a nested DB session while
seeding breeding-tent data. A final diff scan also removed the now-unused
private sensornode lookup helper from `apps/shared/src/dirt_shared/services/readings.py`.
No behavior changes were made during simplify.

Milestone 5 final validation evidence from 2026-05-04:

    scripts/gen-contract
    generated Pydantic models and TypeScript schema from contracts/webapp-v1.yaml

    pnpm --dir web-ui exec biome check --write src/api-client/generated/schema.ts
    Checked 1 file in 34ms. Fixed 1 file.

    uv run ruff format contracts/python/src/dirt_contracts/webapp_v1/models.py
    1 file reformatted; no generated Pydantic diff remained afterward.

    uv run pytest apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_feed_snapshot_endpoint.py -q
    27 passed in 8.64s

    uv run pytest apps/tests/invariants/test_api_contract.py -q
    6 passed, 1 skipped in 0.92s

    pnpm --dir web-ui lint
    Checked 88 files in 36ms. No fixes applied; eslint passed.

    pnpm --dir web-ui typecheck
    tsc --noEmit passed.

    pnpm --dir web-ui test
    1 passed in 761ms.

    uv run ruff check apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/snapshots.py apps/web/src/dirt_web/api/feed.py apps/web/src/dirt_web/api/plants.py apps/web/src/dirt_web/api/sensors.py apps/web/tests/test_feed_snapshot_endpoint.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py
    All checks passed.

    uv run ruff format --check apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/snapshots.py apps/web/src/dirt_web/api/feed.py apps/web/src/dirt_web/api/plants.py apps/web/src/dirt_web/api/sensors.py apps/web/tests/test_feed_snapshot_endpoint.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_sensors_current_endpoint.py apps/web/tests/test_sensors_history_endpoint.py contracts/python/src/dirt_contracts/webapp_v1/models.py
    10 files already formatted.

    git diff --check
    passed with no output.

Post-review Milestone 5 snapshot-scoping blocker fix validation:

    uv run pytest apps/web/tests/test_feed_snapshot_endpoint.py -q
    7 passed in 2.51s

    uv run ruff check apps/shared/src/dirt_shared/services/snapshots.py apps/web/tests/test_feed_snapshot_endpoint.py
    All checks passed.

    uv run ruff format --check apps/shared/src/dirt_shared/services/snapshots.py apps/web/tests/test_feed_snapshot_endpoint.py
    2 files already formatted.

    git diff --check
    passed with no output.

Earlier post-main-review Milestone 3 blocker fix validation:

    uv run pytest apps/hwd/tests/test_ingest_api.py -q
    20 passed in 5.08s

    uv run pytest apps/shared/tests/test_readings_scope.py -q
    4 passed in 2.04s

    uv run pytest apps/shared/tests/test_system_status_scope.py -q
    1 passed in 1.28s

    uv run pytest apps/tests/invariants/ -q
    115 passed, 1 skipped in 3.97s

    uv run ruff check apps/shared/src/dirt_shared/models/device.py apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/system_status.py apps/hwd/src/dirt_hwd/api/ingest.py apps/hwd/src/dirt_hwd/services/metric_freshness.py apps/hwd/tests/test_ingest_api.py apps/shared/tests/test_readings_scope.py apps/shared/tests/test_system_status_scope.py apps/shared/tests/test_legacy_retirement_audit.py
    All checks passed.

    uv run ruff format --check apps/shared/src/dirt_shared/models/device.py apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/system_status.py apps/hwd/src/dirt_hwd/api/ingest.py apps/hwd/src/dirt_hwd/services/metric_freshness.py apps/hwd/tests/test_ingest_api.py apps/shared/tests/test_readings_scope.py apps/shared/tests/test_system_status_scope.py apps/shared/tests/test_legacy_retirement_audit.py
    9 files already formatted

    git diff --check
    passed with no output


## Interfaces and Dependencies

New or changed interfaces expected by the end of this plan:

- Firmware payloads include scoped identity fields: `site_id`, `tent_id`, `zone_id`, `device_id`, and optionally `capability_id` for single-capability posts.
- `POST /api/ingest/sensors` accepts scoped payloads without requiring `location`; legacy `location` remains optional compatibility until explicitly retired.
- Canonical device heartbeat exists on `device` or a local `deviceheartbeat` table and is used by `SystemStatusService`, `DeviceWatchdogService`, and metric freshness logic.
- `Plant` rows own or reference moisture capability identity directly; plant services do not need `Plant.sensornode_id` for current reads.
- `DailySensorService` reads through capability/device/tent scope.
- `GrowRun` no longer carries a duplicate `location` string; grow placement is represented by `site_id` and `tent_id`, and human display labels come from `site`/`tent` fields unless deliberately redesigned.
- `Schedule` is the canonical persisted photoperiod interface. Grow-current APIs may expose lights times for compatibility, but they are derived from `schedule`, not duplicated on `growrun`.
- Existing default-main API routes remain compatible unless a contract revision deliberately changes them.
- If scoped query params are added to existing API routes, `contracts/webapp-v1.yaml`, generated Python models, and `web-ui/src/api-client/generated/schema.ts` are regenerated and formatted.
- Atlas remains the only schema migration mechanism.
- No new cloud provider, hosted backend, remote executor, MQTT fleet service, public auth provider, or Vercel deployment is introduced.


## Revision Notes

- 2026-05-04: Initial ExecPlan created after Phase 1 multi-tent model was committed, pushed, migrated, and smoke-tested on the local controller.
- 2026-05-04: Added `growrun.location` to the Milestone 7 cleanup-removal inventory and clarified that future stale-field removals should be tracked as explicit cleanup work with validation, not only as final exit criteria.
- 2026-05-04: Added duplicated photoperiod storage to the Milestone 7 cleanup-removal inventory. The target is schedule-canonical storage using local wall-clock times plus timezone, with grow-current API values composed from schedule during compatibility.
- 2026-05-04: Completed Milestone 2 and recorded scoped firmware ingest, canonical device/capability sensor-contract ownership, compatibility-location derivation, and focused validation evidence.
- 2026-05-04: Completed Milestone 5 and recorded the scoped query-param API decision, snapshot fallback rule, contract regeneration, and focused endpoint validation.
- 2026-05-04: Fixed main-review Milestone 5 snapshot scoping blocker: unresolved explicit snapshot scope now returns 404 instead of falling through to unfiltered latest-snapshot selection.
- 2026-05-04: Added post-review Milestone 2 ingest test coverage for unknown scoped device IDs without legacy `location` and refreshed the stale test comment.
- 2026-05-04: Reworked Milestone 2 sensor-contract and ingest API helpers to satisfy pre-commit import-boundary and no-module-level-singleton invariants.
- 2026-05-04: Completed Milestone 4 and recorded plant moisture capability ownership, daily sensor capability reads, migration/backfill artifact, simplify cleanup, and validation evidence.
