# Scoped Firmware Legacy Removal

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

Dirt now stores current telemetry, device freshness, plants, schedules, snapshots, and grow state through scoped local identities: `site`, `tent`, `zone`, `device`, and `capability`. The remaining compatibility layer exists because ESP32 firmware and a few service inventories still pretend that legacy `location` strings and `sensornode` rows are the primary model.

After this plan is complete, flashed boards post scoped identity only, the ingest API rejects legacy-only payloads, new readings no longer require `sensorreading.sensornode_id`, and production services no longer depend on `SensorLocation` or legacy metric maps for current behavior. A human can observe success by seeing firmware POST bodies without `location`, zero legacy-only ingest warnings over a soak period, fresh canonical `device.last_seen` values, current readings with non-null `capability_id`, passing daily report and voice sensor summaries, and an Atlas migration that removes `sensornode`, `sensor_location`, and `sensorreading.sensornode_id` when historical lineage has been safely handled.

This is local-controller work. The homebox remains the hardware authority. Do not add hosted/cloud command execution, public remote control, fleet management, or Vercel-specific behavior in this plan.


## Progress

- [x] (2026-05-04) Created this ExecPlan as a reviewable scope document after `LegacyCompatibilityRetirementExecPlan.md` was implemented, migrations were applied live, services restarted, and smoke checks passed.
- [ ] Milestone 1: firmware scoped-only POST support and board rollout.
- [ ] Milestone 2: soak and live compatibility telemetry gate.
- [ ] Milestone 3: tighten HWD ingest to reject legacy-only current payloads.
- [ ] Milestone 4: replace remaining service inventories that are keyed by `SensorLocation`.
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


## Decision Log

- Decision: Roll out scoped-only firmware before rejecting legacy-only ingest.
  Rationale: The homebox is actively receiving legacy-only ESP32 payloads. Server-side removal before OTA/upload would create an avoidable telemetry outage.
  Date/Author: 2026-05-04 / Codex

- Decision: Keep historical `sensorreading` lineage until a dedicated migration either preserves or deliberately drops it.
  Rationale: Some old rows intentionally remain quarantined without a safe canonical capability, such as old `pressure_hpa`, `reservoir_depth_cm`, and a one-off plant `humidity_pct`. Dropping `sensornode_id` without an explicit history decision would make old data harder to explain.
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


## Outcomes & Retrospective

Not started. Fill this section after each milestone with the actual result, operational notes, and any remaining risk.


## Context and Orientation

The previous plan, `docs/epics/multi-tent-controller/LegacyCompatibilityRetirementExecPlan.md`, completed the first compatibility-retirement phase. The live database is migrated through `20260504062816`. `Plant.sensornode_id`, `SensorCalibration.sensornode_id`, `GrowRun.location`, and duplicated grow-run photoperiod columns are gone. Current plant moisture, calibration, grow-current, and lights behavior use capability and schedule ownership.

The remaining compatibility surfaces are different: they are mostly firmware wire format, current ingest compatibility, and service inventories.

Important files:

- `firmware/common/ingest_client/ingest_client.{h,cpp}` builds ESP32 JSON POST bodies. It currently always includes `location`.
- `firmware/fan_controller/src/main.cpp` posts as `homebox/main/canopy/fan-controller` but still retains `LOCATION = "tent"`.
- `firmware/plant_node/src/main.cpp` posts as `homebox/main/plant-<id>/plant-<id>-node` but still retains `LOCATION = "plant-<id>"`.
- `firmware/reservoir_node/src/main.cpp` posts as `homebox/main/reservoir/reservoir-node` but still retains `LOCATION = "reservoir"`.
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

Before dropping columns/tables, migrate historical lineage into capability ownership. The default policy is to normalize historical rows to canonical capabilities when the old stream represents the same physical quantity. The known reservoir case should be migrated from `reservoir_depth_cm` to the canonical `reservoir_in` capability by dividing values by `2.54` and changing `metric` to `reservoir_in`. Do not round converted values in storage.

For historical streams that do not have a safe canonical equivalent, create explicit archive-only capabilities instead of dropping data or forcing a false mapping. Known examples are old tent `pressure_hpa` and the one-off plant `humidity_pct` row. Name archive capabilities so normal dashboards can ignore them unless a future historical explorer deliberately opts in.

The migration must prove that every `sensorreading` row has non-null `capability_id` before dropping `sensornode_id`. Use Atlas only for schema changes. Candidate removals:

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
- Historical rows without a safe canonical equivalent are linked to explicit archive-only capabilities rather than left dependent on `sensornode_id`.
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

    Metrics without safe equivalence, such as old pressure_hpa, should receive
    explicit archive-only capabilities so the original data remains queryable
    without appearing as a current dashboard metric.

Relevant previous plan:

    docs/epics/multi-tent-controller/LegacyCompatibilityRetirementExecPlan.md


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


## Revision Notes

- 2026-05-04: Initial scope plan created for GitHub review after live application of the previous compatibility-retirement migrations.
- 2026-05-04: Set the scoped-only firmware soak gate to 10 minutes after review.
- 2026-05-04: Chose canonical normalization for historical reservoir depth: convert `reservoir_depth_cm` rows to `reservoir_in` in storage during final schema cleanup.
