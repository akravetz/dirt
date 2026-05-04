# Multi-Tent Legacy Compatibility Retirement

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

Phase 1 of the multi-tent local-controller model is live: Dirt has scoped `site`, `tent`, `zone`, `device`, `capability`, `growrun`, `schedule`, `snapshot`, and `command` records, and the existing main-tent dashboard still works. The next change retires the compatibility layers that let old code and firmware keep pretending that `SensorLocation` and `sensornode` are the primary model.

After this plan is complete, new telemetry, calibration, plant moisture, device freshness, daily sensors, API reads, and firmware payloads use canonical scoped identities directly. Legacy `location` strings remain understood only as an explicit backward-compatible ingest format for old flashed boards, not as the internal source of truth. A human can observe success by seeing current readings and heartbeats tied to `device`/`capability`, scoped API calls returning the same default-main data as the dashboard, and tests proving that no new current-path row depends on `sensornode_id` or metric-only lookups.

This plan is still local-controller work. The homebox remains the hardware authority. Do not add hosted/cloud command execution, public auth, Vercel-specific behavior, or remote-control UI in this plan.


## Progress

- [x] (2026-05-04 03:35Z) Created this ExecPlan after Phase 1 migrations were applied and operational smoke checks passed.
- [ ] Implement Milestone 1: audit and guard current legacy paths before changing behavior.
- [ ] Implement Milestone 2: make firmware and ingest scoped-first while preserving explicit legacy ingest compatibility.
- [ ] Implement Milestone 3: move device heartbeat/freshness ownership from `sensornode` to `device`.
- [ ] Implement Milestone 4: move plant moisture and daily sensor paths off `sensornode_id`.
- [ ] Implement Milestone 5: make scoped API/frontend access first-class while keeping default-main URLs compatible.
- [ ] Implement Milestone 6: backfill or quarantine historical unscoped data and tighten schema/app constraints.
- [ ] Implement Milestone 7: remove dead legacy code, docs, tests, and optional schema artifacts that no live path uses.


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


## Outcomes & Retrospective

No implementation milestones have been completed yet. This plan starts after Phase 1 was committed, pushed, migrated, and smoke-tested on the live local database.


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
- `firmware/*/src/main.cpp`: still sends legacy `location` payloads.
- `apps/web/src/dirt_web/api/sensors.py` and `metric_registry.py`: still assemble default-main dashboards through legacy metric/location registry concepts.

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


## Interfaces and Dependencies

New or changed interfaces expected by the end of this plan:

- Firmware payloads include scoped identity fields: `site_id`, `tent_id`, `zone_id`, `device_id`, and optionally `capability_id` for single-capability posts.
- `POST /api/ingest/sensors` accepts scoped payloads without requiring `location`; legacy `location` remains optional compatibility until explicitly retired.
- Canonical device heartbeat exists on `device` or a local `deviceheartbeat` table and is used by `SystemStatusService`, `DeviceWatchdogService`, and metric freshness logic.
- `Plant` rows own or reference moisture capability identity directly; plant services do not need `Plant.sensornode_id` for current reads.
- `DailySensorService` reads through capability/device/tent scope.
- Existing default-main API routes remain compatible unless a contract revision deliberately changes them.
- If scoped query params are added to existing API routes, `contracts/webapp-v1.yaml`, generated Python models, and `web-ui/src/api-client/generated/schema.ts` are regenerated and formatted.
- Atlas remains the only schema migration mechanism.
- No new cloud provider, hosted backend, remote executor, MQTT fleet service, public auth provider, or Vercel deployment is introduced.


## Revision Notes

- 2026-05-04: Initial ExecPlan created after Phase 1 multi-tent model was committed, pushed, migrated, and smoke-tested on the local controller.
