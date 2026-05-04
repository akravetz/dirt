# Scoped Firmware Legacy Removal

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

Dirt now stores current telemetry, device freshness, plants, schedules, snapshots, and grow state through scoped local identities: `site`, `tent`, `zone`, `device`, and `capability`. The remaining compatibility layer exists because ESP32 firmware and a few service inventories still pretend that legacy `location` strings and `sensornode` rows are the primary model.

After this plan is complete, flashed boards post scoped identity only, the ingest API rejects legacy-only payloads, new readings no longer require `sensorreading.sensornode_id`, and production services no longer depend on `SensorLocation` or legacy metric maps for current behavior. A human can observe success by seeing firmware POST bodies without `location`, zero legacy-only ingest warnings over a soak period, fresh canonical `device.last_seen` values, current readings with non-null `capability_id`, passing daily report and voice sensor summaries, and an Atlas migration that removes `sensornode`, `sensor_location`, and `sensorreading.sensornode_id` when historical lineage has been safely handled.

This is local-controller work. The homebox remains the hardware authority. Do not add hosted/cloud command execution, public remote control, fleet management, or Vercel-specific behavior in this plan.


## Progress

- [x] (2026-05-04) Created this ExecPlan as a reviewable scope document after `LegacyCompatibilityRetirementExecPlan.md` was implemented, migrations were applied live, services restarted, and smoke checks passed.
- [x] (2026-05-04) Milestone 1: firmware scoped-only POST support and board rollout. `firmware/common/ingest_client/ingest_client.{h,cpp}` now builds scoped-only POST bodies without `location`; fan, plant, and reservoir sketches call the scoped-only API; retained legacy-location comments/constants were removed; firmware versions were bumped; build validation passed for fan, reservoir, and plant A-D environments; OTA upload succeeded for fan, plant A-D, and reservoir; live DB confirmed the expected firmware versions fan `0.2.1`, plant `0.1.2`, and reservoir `0.1.1` with fresh `device.last_seen`.
- [x] (2026-05-04) Milestone 2: soak and live compatibility telemetry gate. A 10-minute live `dirt-hwd` journal check after scoped firmware rollout found zero `accepted legacy location-only sensor ingest` messages; all six current hardware devices reported expected firmware versions with fresh `device.last_seen`; recent live readings remained capability-linked with `0` null `capability_id` rows out of `644`.
- [x] (2026-05-04) Milestone 3: tighten HWD ingest to reject legacy-only current payloads. `apps/hwd/src/dirt_hwd/api/ingest.py` now rejects known current `location`-only posts with a clear 422 requiring `device_id`; the legacy-only warning helper was removed; scoped fault/heartbeat posts update canonical `device` state through `touch_device()` without also updating `sensornode`; agent-owned ingest/readings/audit tests were updated and focused validation passed.
- [x] (2026-05-04) Milestone 4: replace remaining service inventories that are keyed by `SensorLocation`. Daily report sensor validation/snapshot now discovers default-main tent requirements from `fan-controller` persisted capability contracts plus live capability rows, and plant moisture requirements from current `plant.moisture_capability_id` rows. Metric freshness state/logging now keys by `device_id:capability_id` and emits scoped fields without `location`. Voice sensor tools read default-main tent metrics with `device_id='fan-controller'` and plant moisture through current scoped plant capabilities. Production service code no longer imports legacy `SensorLocation` maps; `EMITTED_METRICS` and `PERSISTED_METRICS` remain only as derived compatibility exports for the human-owned invariant suite.
- [ ] Milestone 5: remove legacy `sensornode` storage and maps after current and historical paths no longer need them.


## Surprises & Discoveries

- Observation: Live boards are still using the legacy-only ingest path even though code supports scoped identity.
  Evidence: After the 2026-05-04 rollout, `systemctl --user status dirt-hwd` showed repeated `accepted legacy location-only sensor ingest` messages from ESP32 IPs, each followed by `POST /api/ingest/sensors ... 202 Accepted`.

- Observation: Current live readings are already capability-linked.
  Evidence: After applying migrations through `20260504062816`, a live query over the last 20 minutes returned `431` recent readings and `0` with null `capability_id`.

- Observation: The firmware common ingest client always serializes a `location` field.
  Evidence: `firmware/common/ingest_client/ingest_client.cpp` begins every request body with `{"location":"...` and the scoped overload still takes `location` as the first required argument.

- Observation: The remaining production legacy reference inventory is explicit and guarded.
  Evidence: `apps/shared/tests/test_legacy_retirement_audit.py` lists current files containing `SensorLocation`, `SensorNode`, `sensornode_id`, `legacy_location`, and legacy sensor-contract maps.

- Observation: The normal firmware POST helper no longer has a retained legacy-location overload.
  Evidence: `firmware/common/ingest_client/ingest_client.h` exposes `post(site_id, tent_id, zone_id, device_id, metrics_json)`, and `rg -n '"location"|location=|legacy|LOCATION|post\([^\n]*LOCATION' firmware/common firmware/fan_controller firmware/plant_node firmware/reservoir_node` returned no matches after Milestone 1 edits.

- Observation: `plant_node` has one default PlatformIO environment even though rollout has four plant boards.
  Evidence: `pio run` in `firmware/plant_node` built only `plant-a`; a separate `pio run -e plant-b -e plant-c -e plant-d` was run to validate the other board identities.

- Observation: No firmware test directories were found for this milestone.
  Evidence: `find firmware -maxdepth 3 \( -path '*/test/*' -o -path '*/tests/*' -o -name 'test_*' \) -print` produced no output.

- Observation: Plant firmware still emits an existing PlatformIO deprecation warning for `ADC_ATTEN_DB_11`.
  Evidence: Plant A-D builds succeeded, but each printed `warning: 'ADC_ATTEN_DB_11' is deprecated`; this predates the scoped-ingest change and behaves the same as `ADC_ATTEN_DB_12` per the SDK note.

- Observation: Two cheap ESP32-C plant boards were unreliable over OTA even after authenticating.
  Evidence: `pio run -e fan-ota -t upload`, `pio run -e plant-a-ota -t upload`, `pio run -e plant-c-ota -t upload`, and a direct-IP reservoir `espota.py` retry succeeded. `plant-b-ota` and `plant-d-ota` repeatedly failed during transfer after authentication, including one plant B attempt that reached 98% before failing. Later direct-IP OTA retries eventually succeeded for both boards, and a live `device` query showed `plant-b-node` and `plant-d-node` reporting firmware `0.1.2`.

- Observation: Reservoir OTA config was pointed at an unset password env var even though this repo uses one shared node OTA password.
  Evidence: The first `reservoir-ota` attempt passed an empty auth value from `RESERVOIR_OTA_PASSWORD` and failed authentication; `firmware/fan_controller/platformio.ini` already documents that `PLANT_OTA_PASSWORD` is shared across every dirt node. `firmware/reservoir_node/platformio.ini` now uses `PLANT_OTA_PASSWORD`; after that correction, a later direct-IP reservoir OTA retry completed and live heartbeat reported firmware `0.1.1`.

- Observation: The scoped-only firmware passed the configured 10-minute live soak.
  Evidence: At `2026-05-04 07:54:07 MDT`, `journalctl --user -u dirt-hwd --since '10 minutes ago' --no-pager | rg 'accepted legacy location-only sensor ingest' || true` returned no matches. The same validation pass showed fresh expected firmware versions for `fan-controller`, `plant-a-node`, `plant-b-node`, `plant-c-node`, `plant-d-node`, and `reservoir-node`; a recent readings query returned `0` null `capability_id` rows out of `644`.

- Observation: HWD test fixtures are not safe to run as parallel pytest processes.
  Evidence: A first validation attempt used two concurrent `uv run pytest ...` commands against database-backed suites. One process dropped the shared test template database while the other was still cloning from it, producing `InvalidCatalogNameError: template database ... does not exist`. Rerunning the same suites sequentially passed.

- Observation: Current fault/heartbeat-only scoped ingest no longer updates `sensornode`.
  Evidence: `ReadingsService.touch_device()` now updates only canonical `device` heartbeat fields. Rejected reservoir payload tests were updated to assert canonical device freshness and no readings, not legacy node metadata updates.

- Observation: The metric freshness state key needed both device and capability identity.
  Evidence: Every plant node has a public `capability_id='soil_moisture_raw'`. Keying by capability alone would collapse plant A-D into one alert state, so `ReadingsService.get_capability_freshness_snapshot()` now returns keys like `plant-a-node:soil_moisture_raw`.

- Observation: Daily report and voice plant moisture were already close to scoped reads.
  Evidence: Both paths resolved current grow `Plant.moisture_capability_id` before reading plant moisture. Milestone 4 removed the remaining `SensorLocation` loop from those paths and made current `Plant` rows the inventory.

- Observation: Human-owned invariants still import the legacy sensor-contract maps.
  Evidence: `uv run pytest apps/tests/invariants/ -q` initially failed during collection because `apps/tests/invariants/test_sensor_contract.py` imports `EMITTED_METRICS` and `PERSISTED_METRICS`. The maps remain as compatibility exports derived from `DEVICE_METRICS`, but production service code no longer imports them.

- Observation: Some web endpoint tests still imported the removed legacy location-to-device map.
  Evidence: Main-agent commit-hook review found `apps/web/tests/test_plants_{detail,list,moisture}_endpoint.py` importing `LEGACY_LOCATION_DEVICE_IDS`. Those agent-owned tests now use `device_id_for_legacy_location()` and the targeted web test trio passed.


## Decision Log

- Decision: Roll out scoped-only firmware before rejecting legacy-only ingest.
  Rationale: The homebox is actively receiving legacy-only ESP32 payloads. Server-side removal before OTA/upload would create an avoidable telemetry outage.
  Date/Author: 2026-05-04 / Codex

- Decision: Keep historical `sensorreading` lineage until a dedicated migration either preserves or deliberately drops it.
  Rationale: Some old rows intentionally remain quarantined without a safe canonical capability, such as old `pressure_hpa`, `reservoir_depth_cm`, and a one-off plant `humidity_pct`. Dropping `sensornode_id` without an explicit history decision would make old data harder to explain.
  Date/Author: 2026-05-04 / Codex

- Decision: Do not migrate old `pressure_hpa` or the stray `plant-a` `humidity_pct` row into the current app schema.
  Rationale: These values were never used by the product and are considered trash historical readings. The normal pre-migration `pg_dump` is enough retention; no targeted extract or archive-only capability is needed. The cleanup migration may delete exactly these known rows after the backup, then fail if any unexpected null-capability rows remain.
  Date/Author: 2026-05-04 / Codex

- Decision: Normalize historical reservoir depth rows to the canonical inches stream instead of preserving a separate centimetre display metric.
  Rationale: The product should continue to show one reservoir-depth chart without frontend unit-conversion business logic. Old `reservoir_depth_cm` rows are the same physical quantity as current `reservoir_in`, so the migration should convert `value = value / 2.54`, set `metric = 'reservoir_in'`, and attach the canonical `reservoir-node` `reservoir_in` capability. Preserve the conversion in migration comments, validation counts, and this plan rather than storing a second UI-facing metric.
  Date/Author: 2026-05-04 / Codex

- Decision: Use capability/device inventories rather than adding a new replacement enum for `SensorLocation`.
  Rationale: The canonical model already has `device` and `capability`; a new enum would preserve the same drift risk under a different name.
  Date/Author: 2026-05-04 / Codex

- Decision: Treat voice and daily-report compatibility cleanup as first-class acceptance criteria, not incidental refactors.
  Rationale: Both paths produce user-visible summaries. Removing legacy telemetry storage while leaving those services keyed by `SensorLocation` would preserve hidden default-main assumptions.
  Date/Author: 2026-05-04 / Codex

- Decision: Use a 10-minute soak window after scoped-only firmware rollout.
  Rationale: The ESP32 ingest cadence is roughly 30 seconds, so 10 minutes covers many fan, plant, and reservoir posts without unnecessarily delaying the next server-side tightening step. Longer monitoring can continue after the gate, but it should not block the milestone.
  Date/Author: 2026-05-04 / Codex

- Decision: Reject only known current legacy locations at the HWD API boundary during Milestone 3.
  Rationale: Current boards are covered by `sensor_contract.DEVICE_METRICS` and must send `device_id` after the soak gate. Unknown `location`-only payloads remain as an explicit legacy/test-only path until the final `sensornode` removal milestone, so this step does not accidentally turn a compatibility cleanup into a broader schema/data decision.
  Date/Author: 2026-05-04 / Codex


## Outcomes & Retrospective

Milestone 1 is complete. Scoped firmware POST bodies no longer serialize `location`, all current fan/plant/reservoir sketches use the scoped-only helper, stale retained-legacy-location comments/constants were removed, and firmware versions were bumped to fan `0.2.1`, plant `0.1.2`, and reservoir `0.1.1`.

The physical rollout completed after explicit OTA confirmation. Standard OTA succeeded for fan, plant A, and plant C. Reservoir, plant D, and plant B required direct-IP OTA retries after transfer failures, but all six hardware targets later checked in with the expected firmware versions and fresh heartbeats. The next milestone is the 10-minute scoped-only soak and live compatibility telemetry gate.

Milestone 2 is complete. The scoped-only firmware soaked for the configured 10-minute window with no legacy-only ingest warnings in `dirt-hwd`, fresh expected firmware versions for every current ESP32 device, and recent live readings fully linked to capabilities. The next milestone can tighten current HWD ingest so known current payloads must include `device_id`.

Milestone 3 is complete. Known current legacy-only HWD ingest posts now return HTTP 422 with `device_id is required for current sensor ingest`; the old `accepted legacy location-only sensor ingest` warning path has been removed because those payloads are no longer accepted. Current scoped posts still derive a temporary compatibility location for sensor-quality checks and `sensornode_id` writes while the legacy table remains, but `device_id` is the canonical heartbeat identity and `touch_device()` no longer writes `SensorNode`.

Milestone 4 is complete. Daily report, metric freshness, and voice sensor summaries no longer use service inventories keyed by `SensorLocation`. The remaining `SensorLocation` references are compatibility/model surfaces for the still-live `sensornode` and `sensorreading.sensornode_id` schema, the HWD ingest compatibility bridge, the humidifier's legacy internal recording path, centralized readings compatibility helpers, and human-owned invariant compatibility. `sensor_contract.py` stopped exporting `LEGACY_LOCATION_DEVICE_IDS`, `emitted_metrics()`, and `persisted_metrics()`; `EMITTED_METRICS` and `PERSISTED_METRICS` remain as derived compatibility exports solely because the human-owned invariant suite imports them until Milestone 5 removes `SensorLocation`.


## Context and Orientation

The previous plan, `docs/epics/multi-tent-controller/LegacyCompatibilityRetirementExecPlan.md`, completed the first compatibility-retirement phase. The live database is migrated through `20260504062816`. `Plant.sensornode_id`, `SensorCalibration.sensornode_id`, `GrowRun.location`, and duplicated grow-run photoperiod columns are gone. Current plant moisture, calibration, grow-current, and lights behavior use capability and schedule ownership.

The remaining compatibility surfaces are different: they are mostly firmware wire format, current ingest compatibility, and service inventories.

Important files:

- `firmware/common/ingest_client/ingest_client.{h,cpp}` builds ESP32 JSON POST bodies. As of Milestone 1, the normal helper serializes scoped identity only and no longer includes `location`.
- `firmware/fan_controller/src/main.cpp` posts as `homebox/main/canopy/fan-controller` through the scoped-only helper.
- `firmware/plant_node/src/main.cpp` posts as `homebox/main/plant-<id>/plant-<id>-node` through the scoped-only helper.
- `firmware/reservoir_node/src/main.cpp` posts as `homebox/main/reservoir/reservoir-node` through the scoped-only helper.
- `apps/hwd/src/dirt_hwd/api/ingest.py` accepts either legacy `location` or scoped `device_id`, logs legacy-only posts, and derives compatibility location when needed.
- `apps/shared/src/dirt_shared/services/readings.py` still writes `SensorNode` and non-null `SensorReading.sensornode_id` through centralized compatibility choke points.
- `apps/shared/src/dirt_shared/sensor_contract.py` declares canonical `DEVICE_METRICS` but still exports derived legacy maps for compatibility.
- `apps/shared/src/dirt_shared/services/daily_sensors.py`, `apps/hwd/src/dirt_hwd/services/metric_freshness.py`, and `apps/voice/src/dirt_voice/tools/sensors.py` still use legacy location or metric inventory concepts.
- `apps/shared/tests/test_legacy_retirement_audit.py` is the executable inventory of remaining legacy references. It must be updated deliberately as each reference disappears.

Terms:

- Scoped identity means `site_id`, `tent_id`, optional `zone_id`, `device_id`, and `capability_id`, backed by the relational tables with the same concepts.
- Legacy-only ingest means an ESP32 payload that supplies `location` but no `device_id`.
- Scoped-only firmware means an ESP32 payload with `site_id`, `tent_id`, `zone_id`, and `device_id`, and no `location`.
- Historical lineage means old `sensorreading` rows that are useful to interpret by original `sensornode_id` even if their metric cannot safely map to a canonical capability.


## Plan of Work

Milestone 1: Firmware scoped-only POST support and board rollout.

Change `firmware/common/ingest_client/ingest_client.h` and `.cpp` so callers can post without `location`. Keep a transitional overload only if tests or sketches still need it before rollout; prefer an explicit scoped method whose arguments are `site_id`, `tent_id`, `zone_id`, `device_id`, and metrics. Update all three firmware sketches to call the scoped-only method and remove comments saying legacy `location` is retained. Bump firmware versions in the relevant PlatformIO configs. Build each firmware project. Then OTA/upload the physical boards using the repo's firmware commands and confirm live logs stop reporting legacy-only posts.

Milestone 2: Soak and live compatibility telemetry gate.

Add or use existing structured log checks to prove no legacy-only ingest occurred over a 10-minute soak window after the scoped-only firmware rollout. Ten minutes is intentionally brief because the ESP32 ingest cadence is about 30 seconds; it should include many fan, plant, and reservoir post cycles. Add a small operational script under `debug/` if needed, not under app code. The acceptance gate is a live query/log check showing fresh device heartbeats and zero recent legacy-only warnings.

Milestone 3: Tighten HWD ingest.

Update `apps/hwd/src/dirt_hwd/api/ingest.py` so known current payloads must include `device_id`; legacy-only payloads should return a clear 422 once the soak gate is satisfied. Remove or narrow `_compat_location()` and `_warn_on_legacy_only_payload()`. Update `ReadingsService.ingest_reading()` and `touch_device()` call patterns so `device_id` is the canonical current identity. Keep compatibility only if there is an explicit historical or test-only path, and document it in the audit.

Milestone 4: Replace service inventories.

Replace remaining `SensorLocation`-keyed current inventories with capability/device queries:

- `daily_sensors.py` should discover default-main required metrics from `device`/`capability` or an explicit capability contract, not `PLANT_LOCATIONS` and `persisted_metrics(SensorLocation.TENT)`.
- `metric_freshness.py` should track freshness by `device_id` and `capability_id` or `metric_name`, not `(location, metric)`.
- `voice/tools/sensors.py` should read default-main summaries through scoped capabilities, not `SensorNode` or `sensornode_id`.
- `sensor_contract.py` should stop exporting legacy maps once no production code imports them.

Update tests around daily reports, metric freshness, voice sensor tools, and legacy audit inventory.

Milestone 5: Final schema and code deletion.

Before dropping columns/tables, migrate useful historical lineage into capability ownership and delete known trash rows after the standard pre-migration backup. The default policy is to normalize historical rows to canonical capabilities when the old stream represents the same physical quantity. The known reservoir case should be migrated from `reservoir_depth_cm` to the canonical `reservoir_in` capability by dividing values by `2.54` and changing `metric` to `reservoir_in`. Do not round converted values in storage.

Do not create archive-only capabilities for old tent `pressure_hpa` or the one-off `plant-a` `humidity_pct` row. Those rows are not product history worth preserving in the app schema. The migration may delete exactly those rows, with comments naming the decision, after the normal `pg_dump` backup has been taken.

The migration must prove that every remaining `sensorreading` row has non-null `capability_id` before dropping `sensornode_id`. Use Atlas only for schema changes. Candidate removals:

- `sensorreading.sensornode_id`
- `sensornode`
- Postgres enum `sensor_location`
- Python `SensorLocation`
- `LEGACY_LOCATION_DEVICE_IDS`
- `EMITTED_METRICS` and `PERSISTED_METRICS`
- compatibility writer guards for `SensorNode`

Update `docs/database.md`, `docs/observability.md`, this plan, and any multi-tent ERD docs after the migration.


## Concrete Steps

Start from the repo root and confirm unrelated dirty files before editing:

    cd /home/akcom/code/dirt
    git status --short

Read required context before implementation:

    sed -n '1,260p' .agents/PLANS.md
    sed -n '1,240p' docs/commands.md
    sed -n '1,220p' docs/database.md
    sed -n '1,180p' docs/observability.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    sed -n '1,220p' docs/epics/multi-tent-controller/LegacyCompatibilityRetirementExecPlan.md
    sed -n '1,260p' docs/epics/multi-tent-controller/ScopedFirmwareLegacyRemovalExecPlan.md

Inspect current legacy surfaces:

    rg -n "SensorLocation|SensorNode|sensornode_id|legacy_location|LEGACY_LOCATION|PERSISTED_METRICS|EMITTED_METRICS" apps firmware
    rg -n "accepted legacy location-only sensor ingest" var/logs || true
    journalctl --user -u dirt-hwd --since '1 hour ago' --no-pager | rg "accepted legacy location-only sensor ingest" || true

Build firmware after scoped-only edits:

    cd /home/akcom/code/dirt/firmware/fan_controller
    pio run

    cd /home/akcom/code/dirt/firmware/plant_node
    pio run

    cd /home/akcom/code/dirt/firmware/reservoir_node
    pio run

Upload or OTA using the existing PlatformIO targets for each project after a human confirms the intended board and environment. Do not mass-flash unfamiliar devices without confirmation.

For schema changes, use Atlas only:

    cd /home/akcom/code/dirt
    atlas migrate diff <short_name> --env local
    atlas migrate hash --env local
    atlas migrate diff verify_<short_name>_sync --env local

Before applying live schema changes:

    mkdir -p var/db-backups
    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump -h 127.0.0.1 -U dirt -d dirt > var/db-backups/dirt-before-scoped-firmware-removal-$(date +%F-%H%M%S).sql
    atlas migrate apply --env local

Before committing any milestone:

    scripts/agent-fix
    uv run pytest apps/tests/invariants/ -q
    uv run pytest apps/shared/tests apps/hwd/tests apps/web/tests -q
    git diff --check


## Validation and Acceptance

The work is accepted only when all of these are true:

- Firmware source for fan, plant, and reservoir boards no longer sends `location` in normal ingest payloads.
- All physical ESP32 boards have been flashed or OTA-updated and are posting scoped-only payloads.
- `dirt-hwd` logs show no `accepted legacy location-only sensor ingest` events over the soak window.
- Recent live readings have non-null `capability_id`.
- Key devices have fresh canonical `device.last_seen`: at least `fan-controller`, `plant-a-node`, `plant-b-node`, `plant-c-node`, `plant-d-node`, and `reservoir-node`.
- `apps/hwd/src/dirt_hwd/api/ingest.py` rejects known current payloads missing `device_id` with a clear 422 response.
- Daily report sensor validation and summaries still work.
- Voice sensor tool summaries still work or have a deliberate replacement if the voice service is separately offline.
- `apps/shared/tests/test_legacy_retirement_audit.py` shows the remaining legacy inventory shrinking milestone by milestone.
- If `sensornode`, `sensor_location`, or `sensorreading.sensornode_id` remain at any stopping point, this plan documents exactly why.
- If they are removed, Atlas status reports no pending files after apply and `docs/database.md` no longer documents them as live tables/columns.
- Historical `reservoir_depth_cm` rows are converted to `reservoir_in` in storage and linked to the canonical reservoir capability; frontend/API history does not need a special centimetre conversion path.
- Old `pressure_hpa` and the one-off `plant-a` `humidity_pct` rows are deleted by the cleanup migration after the standard backup; no targeted extract or archive-only capability is created for them.
- The migration has a guard that fails if any null-capability `sensorreading` rows remain after reservoir conversion and known-trash deletion.
- `apps/tests/invariants/` remains unchanged.

Useful live checks:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "
    SELECT count(*) FILTER (WHERE capability_id IS NULL) AS null_capability_recent,
           count(*) AS recent_readings
    FROM sensorreading
    WHERE ts > now() - interval '30 minutes';"

    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "
    SELECT device_id, last_seen, now() - last_seen AS age
    FROM device
    WHERE device_id IN ('fan-controller','plant-a-node','plant-b-node','plant-c-node','plant-d-node','reservoir-node')
    ORDER BY device_id;"

    journalctl --user -u dirt-hwd --since '10 minutes ago' --no-pager | rg "accepted legacy location-only sensor ingest" || true

Historical migration checks:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "
    SELECT count(*) AS remaining_cm_rows
    FROM sensorreading
    WHERE metric = 'reservoir_depth_cm';"

    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "
    SELECT count(*) FILTER (WHERE capability_id IS NULL) AS null_capability_rows,
           count(*) AS total_rows
    FROM sensorreading;"

    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "
    SELECT sr.metric, sn.location, count(*) AS rows
    FROM sensorreading sr
    JOIN sensornode sn ON sn.id = sr.sensornode_id
    WHERE sr.capability_id IS NULL
    GROUP BY sr.metric, sn.location
    ORDER BY sr.metric, sn.location;"


## Idempotence and Recovery

Firmware builds are safe to repeat. Firmware upload/OTA is visible to hardware and should be done board by board with a known target. If a board fails after scoped-only firmware, either reflash the last known-good firmware or temporarily re-enable the transitional firmware overload while server compatibility remains available.

The soak milestone is observational and safe to repeat. The planned gate is 10 minutes; record the exact wall-clock start and end used for log checks.

Ingest tightening should happen only after the soak gate passes. If it causes telemetry loss, revert the ingest-tightening commit or redeploy compatibility firmware while preserving the database backup.

Atlas migration generation, hash, and sync verification are safe to repeat. Live `atlas migrate apply --env local` is not a dry run. Always take a backup first. If a migration guard fails, stop and inspect the data rather than editing the live database manually.

Do not use destructive git commands to clean unrelated dirty files. At the time this plan was created, unrelated dirty files existed under `apps/wake-word/` and `wiki/`; leave them out of commits for this plan unless the user explicitly asks otherwise.


## Artifacts and Notes

Live rollout state before this plan:

    atlas migrate status --env local
    Migration Status: OK
      -- Current Version: 20260504062816
      -- Pending Files:   0

Post-rollout smoke showed recent readings were capability-linked:

    null_capability_recent | recent_readings
    ------------------------+-----------------
                          0 |             431

Post-rollout service status showed legacy-only firmware still active:

    accepted legacy location-only sensor ingest
    POST /api/ingest/sensors HTTP/1.1" 202 Accepted

Historical data policy:

    reservoir_depth_cm is a legacy unit spelling of the current reservoir depth stream.
    During final schema cleanup, convert those rows to reservoir_in with value / 2.54
    and link them to the canonical reservoir-node reservoir_in capability.

    pressure_hpa and the one-off plant-a humidity_pct row are trash historical
    values. They were never used by the product and should not get archive-only
    capabilities. The standard pre-migration pg_dump is enough retention.

Relevant previous plan:

    docs/epics/multi-tent-controller/LegacyCompatibilityRetirementExecPlan.md

Milestone 1 build validation before hardware upload:

    cd firmware/fan_controller && pio run
    fan SUCCESS

    cd firmware/plant_node && pio run
    plant-a SUCCESS

    cd firmware/plant_node && pio run -e plant-b -e plant-c -e plant-d
    plant-b SUCCESS
    plant-c SUCCESS
    plant-d SUCCESS

    cd firmware/reservoir_node && pio run
    reservoir SUCCESS

Milestone 1 OTA rollout:

    cd firmware/fan_controller && pio run -e fan-ota -t upload
    fan-ota SUCCESS

    cd firmware/plant_node && pio run -e plant-a-ota -t upload
    plant-a-ota SUCCESS

    cd firmware/plant_node && pio run -e plant-c-ota -t upload
    plant-c-ota SUCCESS

    cd firmware/plant_node && pio run -e plant-b-ota -t upload
    plant-b-ota FAILED during OTA transfer after authentication

    cd firmware/plant_node && pio run -e plant-d-ota -t upload
    plant-d-ota FAILED during OTA transfer after authentication

    cd firmware/reservoir_node && pio run -e reservoir-ota -t upload
    reservoir-ota FAILED during OTA transfer after authentication

    cd firmware/reservoir_node
    python3 ~/.platformio/packages/framework-arduinoespressif32/tools/espota.py \
      -i 192.168.1.23 -p 3232 -a "$PLANT_OTA_PASSWORD" \
      -f .pio/build/reservoir-ota/firmware.bin -r -t 60
    reservoir direct-IP OTA SUCCESS

    cd firmware/plant_node
    python3 ~/.platformio/packages/framework-arduinoespressif32/tools/espota.py \
      -i 192.168.1.74 -p 3232 -a "$PLANT_OTA_PASSWORD" \
      -f .pio/build/plant-d-ota/firmware.bin -r -t 60
    plant D direct-IP OTA SUCCESS after retries

    cd firmware/plant_node
    python3 ~/.platformio/packages/framework-arduinoespressif32/tools/espota.py \
      -i 192.168.1.243 -p 3232 -a "$PLANT_OTA_PASSWORD" \
      -f .pio/build/plant-b-ota/firmware.bin -r -t 60
    plant B direct-IP OTA SUCCESS after retries

Live verification after rollout:

    fan-controller | 0.2.1
    plant-a-node   | 0.1.2
    plant-b-node   | 0.1.2
    plant-c-node   | 0.1.2
    plant-d-node   | 0.1.2
    reservoir-node | 0.1.1

Recent readings remained capability-linked:

    null_capability_recent | recent_readings
    -----------------------+----------------
                         0 |            644

Hardware upload completed. Milestone 2 should start from the completed rollout and use the configured 10-minute soak window.

Milestone 2 soak validation:

    date '+%Y-%m-%d %H:%M:%S %Z'
    2026-05-04 07:54:07 MDT

    journalctl --user -u dirt-hwd --since '10 minutes ago' --no-pager \
      | rg 'accepted legacy location-only sensor ingest' || true
    no matches

    fan-controller | 0.2.1 | age 00:00:59.164495
    plant-a-node   | 0.1.2 | age 00:00:10.015673
    plant-b-node   | 0.1.2 | age 00:00:09.368190
    plant-c-node   | 0.1.2 | age 00:00:06.061040
    plant-d-node   | 0.1.2 | age 00:00:18.343696
    reservoir-node | 0.1.1 | age 00:00:23.252279

    null_capability_recent | recent_readings | oldest_recent                  | newest_recent
    ------------------------+-----------------+--------------------------------+-------------------------------
                         0 |             644 | 2026-05-04 07:24:14.569552-06 | 2026-05-04 07:54:01.928402-06


## Interfaces and Dependencies

End-state firmware interface:

- POST `/api/ingest/sensors`
- Required current payload fields: `site_id`, `tent_id`, `device_id`, `metrics`, `source`, `firmware_version`, `ip`, `uptime_ms`
- Optional current payload fields: `zone_id`, `capability_id`
- Removed current payload field: `location`

End-state database interfaces:

- `sensorreading.capability_id` is the current telemetry owner.
- `device.last_seen`, `device.ip`, `device.firmware_version`, and `device.uptime_ms` are the current heartbeat owner.
- `sensornode`, `sensor_location`, and `sensorreading.sensornode_id` are absent, archived, or explicitly documented as historical-only with no current writes.

End-state service interfaces:

- `ReadingsService.ingest_reading()` accepts scoped identity and writes capability-owned readings.
- HWD ingest rejects current payloads missing `device_id`.
- Daily sensor, metric freshness, and voice sensor summaries use scoped device/capability inventories.
- `sensor_contract.py` is canonical-device/capability oriented and no longer exports legacy location maps unless a documented historical path still imports them.

Milestone 3 validation:

    uv run pytest apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/hwd/tests/test_ingest_properties.py apps/shared/tests/test_readings_scope.py apps/shared/tests/test_legacy_retirement_audit.py -q
    42 passed

    first attempt only:
    concurrent database-backed pytest commands failed with asyncpg InvalidCatalogNameError because the shared test template database was dropped by the other pytest process; rerunning sequentially passed.

Milestone 4 validation:

    uv run pytest apps/shared/tests/test_daily_sensors.py apps/shared/tests/test_daily_report.py apps/shared/tests/test_milestone4_scope.py apps/hwd/tests/test_metric_freshness.py apps/voice/tests/test_sensor_tools.py apps/shared/tests/test_legacy_retirement_audit.py -q
    49 passed

    uv run pytest apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py -q
    15 passed

    uv run pytest apps/tests/invariants -q
    115 passed, 1 skipped

    uv run pytest apps/shared/tests apps/hwd/tests apps/voice/tests -q
    311 passed

    uv run pytest apps/shared/tests apps/hwd/tests apps/voice/tests apps/web/tests -q
    421 passed


## Revision Notes

- 2026-05-04: Initial scope plan created for GitHub review after live application of the previous compatibility-retirement migrations.
- 2026-05-04: Set the scoped-only firmware soak gate to 10 minutes after review.
- 2026-05-04: Chose canonical normalization for historical reservoir depth: convert `reservoir_depth_cm` rows to `reservoir_in` in storage during final schema cleanup.
- 2026-05-04: Classified old `pressure_hpa` and one-off `plant-a` `humidity_pct` rows as discardable trash values retained only by the standard pre-migration `pg_dump`.
- 2026-05-04: Milestone 1 source/build work completed for scoped-only firmware POST support.
- 2026-05-04: Milestone 1 OTA rollout completed for fan, plant A-D, and reservoir after direct-IP retries for reservoir, plant D, and plant B. Plant B and plant D transfer reliability remains a hardware/network risk, but both report the scoped-only firmware version.
- 2026-05-04: Milestone 2 soak gate completed with zero legacy-only ingest warnings over the 10-minute live window and current readings still capability-linked.
- 2026-05-04: Milestone 3 HWD ingest tightening completed. Known current location-only payloads now fail with clear 422, the legacy-only warning helper was removed, `touch_device()` is canonical device-only, and the remaining location-only compatibility path is explicitly legacy/test-only until final `sensornode` removal.
- 2026-05-04: Milestone 4 service inventory cleanup completed. Daily report, metric freshness, and voice sensor summaries use scoped device/capability inventories; remaining legacy maps are compatibility-only until Milestone 5.
