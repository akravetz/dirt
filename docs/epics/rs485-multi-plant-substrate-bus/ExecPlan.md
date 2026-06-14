# RS485 multi-plant substrate bus

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the existing Plant A RS485 substrate controller can run multiple DFRobot SEN0604 substrate probes on the same RS485 bus and make them appear in Dirt as current plant telemetry for Plants A, C, and D. A human operator should be able to plug in one factory-default sensor, wait for `GET http://plant-a-substrate-node.local/status` to show that it was assigned to Plant D, label that cable, then plug in a second factory-default sensor and see it assigned to Plant C. Once assigned, all three probes should post `soil_moisture_pct`, `substrate_temp_c`, `substrate_ec_us_cm`, and `substrate_ph` through the existing `POST /api/ingest/sensors` boundary and show fresh rows in Postgres, hosted sync, and plant metric views.

This matters because Plants B-D currently have no trusted moisture source after the capacitive ESP32 plant nodes were retired. The new probes should restore direct-percent substrate moisture for C and D without reopening the old raw ADC calibration path or inventing a parallel ingest API. Plant B remains intentionally probe-less until a fourth trustworthy sensor is installed or a later plan assigns one.

The observable end state is:

- `plant-a-substrate-node.local` still resolves and exposes `/health` and `/status`.
- `/status` lists at least three configured probe slots: Plant A at Modbus `0x02`, Plant D at Modbus `0x03`, and Plant C at Modbus `0x04`.
- If one new factory-default SEN0604 at address `0x01` is plugged in while Plant D is unassigned, firmware writes the sensor address register `0x07D0` to `0x03`, verifies the new address, and begins posting as `plant-d-substrate-node`.
- If another factory-default SEN0604 is plugged in after Plant D is assigned and Plant C is unassigned, firmware writes `0x07D0` to `0x04`, verifies the new address, and begins posting as `plant-c-substrate-node`.
- Postgres contains enabled `device` and `capability` rows for Plant A, Plant C, and Plant D substrate probes, with freshness-required capability metadata.
- The current plant moisture resolver returns direct `soil_moisture_pct` readings for A/C/D when fresh data exists and still omits B.

## Progress

- [x] (2026-06-12) Reviewed `.agents/PLANS.md`, `docs/commands.md`, `docs/database.md`, `docs/rules/simple-clean-architecture.md`, and `docs/rules/boundary-contracts.md`.
- [x] (2026-06-12) Reviewed the RS485 wiki pages and the completed Plant A RS485 ExecPlan.
- [x] (2026-06-12) Reviewed current firmware, ingest, scoped device/capability models, direct-percent plant moisture helpers, and existing RS485 tests.
- [x] (2026-06-12) Authored this ExecPlan.
- [x] (2026-06-12 21:11Z) Implemented Milestone 1: seeded logical Plant C and Plant D substrate devices/capabilities and active plant metric streams.
- [x] (2026-06-12 21:18Z) Implemented Milestone 2: refactored firmware from one hard-coded sensor to a fixed slot table, still read-only and no address writes.
- [x] (2026-06-12 21:26Z) Implemented Milestone 3: added guarded one-at-a-time address provisioning from factory default address `0x01`.
- [ ] Implement Milestone 4: flash, commission Plant D then Plant C, and validate HTTP status, ingest, Postgres, freshness, and plant telemetry. Completed: local DB backup, local Atlas migration apply, OTA flash, new multi-slot `/status`, fresh Plant A ingest validation, and temporary read-only scanning firmware. Remaining: make Plant D physically visible on the RS485 bus or replace the suspect probe, commission Plant D at `0x03`, then commission Plant C at `0x04`, and validate C/D Postgres/freshness/plant telemetry.
- [ ] Implement Milestone 5: update wiki/operator docs after live validation.

## Surprises & Discoveries

- Observation: The existing ingest contract already has the right shape for one logical probe at a time but not for multiple probes with repeated metric names in one payload.
  Evidence: `apps/hwd/src/dirt_hwd/api/ingest.py` defines `IngestPayload` as one `device_id` plus `metrics: dict[str, float]`, and `apps/shared/src/dirt_shared/services/readings.py` resolves capabilities by `device_id` plus metric names. A single JSON object cannot carry three separate `soil_moisture_pct` values without changing the boundary.

- Observation: The current firmware is intentionally hard-coded for one Plant A sensor.
  Evidence: `firmware/rs485_substrate_node/src/main.cpp` defines `NODE_ZONE_ID`, `NODE_DEVICE_ID`, `MODBUS_ADDRESS`, one `g_latest_sample`, and `post_latest_sample()` posts exactly one payload.

- Observation: Plant A's current SEN0604 is already assigned Modbus address `0x02`, and the DFRobot SEN0604 default address is `0x01`.
  Evidence: `wiki/hardware/rs485-substrate-sensors.md` and `docs/epics/rs485-plant-a-substrate-node/ExecPlan.md` record Plant A at `0x02`. DFRobot's SEN0604 reference documents address code factory default `0x01`, write function `0x06`, device address register `0x07D0`, and valid address range `1-254`.

- Observation: Dirt already has the plant-to-capability mapping needed for C/D without adding a new schema table.
  Evidence: `apps/shared/src/dirt_shared/models/plant.py` defines `PlantMetricStream`, and `get_supported_product_plant_moisture_capabilities()` returns active direct `soil_moisture_pct` streams joined through `PlantMetricStream`, `Capability`, and `Device`.

- Observation: After OTA flashing the provisioning firmware, the controller did not see the already-plugged Plant D probe at factory default `0x01` or target `0x03`, including after the operator adjusted wiring once.
  Evidence: `/status` at 2026-06-12 21:42Z reported Plant A `ok`, Plant D `last_modbus_status='no_response'`, Plant C `last_modbus_status='no_response'`, and provisioning `last_result='no_default_response'` for target Plant D with a cooldown active. A later retry at 2026-06-12 21:54Z still reported provisioning `attempt_count=3`, `last_result='no_default_response'`, Plant D `assigned=false`, and Plant D `last_modbus_status='no_response'`.

- Observation: A temporary read-only scan build saw only the known Plant A probe on the bus.
  Evidence: `/scan` on 2026-06-12 after flashing `plant-a-substrate-scan-ota` scanned `0x01` through `0x10` with provisioning disabled and found one valid responder at `0x02` with Plant A-like readings. The scan reported no response at `0x01`, `0x03`, `0x04`, or any other scanned address.

- Observation: With Plant A unplugged and only the new probe connected, the temporary read-only scan still saw no RS485 responses.
  Evidence: `/scan` on 2026-06-12 with only the new probe attached returned no valid responders and no non-empty responses from `0x01` through `0x10`. `/status` remained reachable with `scan_debug_enabled=true`; the Plant A slot changed to `last_modbus_status='no_response'`, proving the controller saw the unplug.

- Observation: A full-range read-only scan with only the new probe connected saw no Modbus responder at any valid SEN0604 address.
  Evidence: After the operator swapped the A/B pair on the new probe and left the known-good Plant A probe unplugged, `/scan` on 2026-06-12 scanned `0x01` through `0xFE` and reported `ok_count=0`, `no_response_count=254`, all error counters `0`, and an empty `results` array.

## Decision Log

- Decision: Model each RS485 probe as a logical Dirt device, even though all probes are read by one physical ESP32 controller.
  Rationale: The existing database and ingest boundary are device/capability-scoped. Logical per-probe devices let Plant A, C, and D have independent zones, freshness state, capabilities, hosted sync identity, and plant metric streams while preserving the current `POST /api/ingest/sensors` request shape. The shared physical controller remains visible through common hostname/IP/firmware metadata and `/status`.
  Date/Author: 2026-06-12 / Codex

- Decision: Keep `POST /api/ingest/sensors` unchanged and emit one POST per responding probe per poll cycle.
  Rationale: This is the smallest truthful boundary. Adding a multi-device ingest payload would create a second owned protocol, require new Pydantic DTOs, broaden tests, and still need to split readings into device-owned capabilities internally.
  Date/Author: 2026-06-12 / Codex

- Decision: Use fixed slot assignments for this grow: Plant A `0x02`, Plant D `0x03`, Plant C `0x04`.
  Rationale: The operator explicitly wants the first new sensor to become Plant D and the next to become Plant C. A fixed table is easier to inspect and safer than dynamic discovery names. Address `0x01` remains reserved for factory-default commissioning.
  Date/Author: 2026-06-12 / Codex

- Decision: Support one-at-a-time auto-provisioning only; do not attempt to auto-resolve multiple factory-default sensors on the bus.
  Rationale: If two factory-default sensors are connected at `0x01`, both can respond to the same request, causing bus collisions or ambiguous frames. The safe operator workflow is: plug one sensor, wait for `/status` to show assignment, label it, then plug the next.
  Date/Author: 2026-06-12 / Codex

- Decision: Do not revive `soil_moisture_raw` or server-side auto-extrema calibration for these probes.
  Rationale: The SEN0604 reports direct moisture percent. The previous Plant A RS485 plan already simplified current product moisture to direct `soil_moisture_pct` or unavailable. The new C/D streams should follow that contract.
  Date/Author: 2026-06-12 / Codex

## Outcomes & Retrospective

- Milestone 1 added an idempotent local Atlas seed migration for `plant-d-substrate-node` at Modbus `0x03` and `plant-c-substrate-node` at Modbus `0x04`, plus their four substrate capabilities and active current-grow `plant_metric_stream` rows. Focused tests now cover logical C/D ingest, metadata-driven expected wire metrics, independent freshness per logical device/capability, and direct-percent product moisture for A/C/D without synthesizing Plant B. Validation passed on 2026-06-12: `atlas migrate hash --env local`, `uv run pytest apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/shared/tests/test_daily_sensors.py apps/gateway/tests/test_sync.py -q` (`83 passed in 33.60s`), and `git diff --check` for the Milestone 1 files. The migration has not been applied to the live local database yet.

- Milestone 2 refactored `firmware/rs485_substrate_node/src/main.cpp` to poll a fixed read-only slot table for Plant A `0x02`, Plant D `0x03`, and Plant C `0x04`, posting one ingest payload per valid logical probe sample. `/status` now reports controller diagnostics plus per-slot latest sample, raw frame, Modbus status/counters, and ingest counters. `/health` reports whether any enabled slot is failing. HWD ingest diagnostics remain aggregate-only and use only existing `DeviceDiagnostics` fields. Validation passed on 2026-06-12: `cd firmware/rs485_substrate_node && pio run -e plant-a-substrate`; `git diff --check -- firmware/rs485_substrate_node/src/main.cpp firmware/rs485_substrate_node/platformio.ini`; and `rg -n "NODE_ZONE_ID|MODBUS_ADDRESS|0x06|07D0|factory|provision|putBool|putUInt|Preferences" firmware/rs485_substrate_node/src/main.cpp firmware/rs485_substrate_node/platformio.ini`, which matched only the existing boot-count `Preferences` / `putUInt("boot_count")` lines. No flash, OTA upload, or live HTTP validation was performed.

- Milestone 3 added guarded factory-default provisioning to the RS485 substrate firmware. Provisioning runs only after a normal due poll cycle, targets unassigned/non-responding slots in fixed Plant D then Plant C order, probes factory address `0x01`, writes address register `0x07D0` with function `0x06`, verifies factory default no longer responds, verifies the target address returns a valid measurement frame, and persists assignment state/address/schema with `Preferences`. `/status` now reports bounded provisioning state, last target, cooldown, counters, verification statuses, and per-slot assignment. HWD ingest diagnostics remain unchanged. Validation passed on 2026-06-12: `cd firmware/rs485_substrate_node && pio run -e plant-a-substrate`; `git diff --check -- firmware/rs485_substrate_node/src/main.cpp firmware/rs485_substrate_node/platformio.ini`; and the requested provisioning source search. No flash, OTA upload, live HTTP validation, or hardware commissioning was performed.

- Milestone 4 is partially complete. A compressed local backup was written to `var/db-backups/dirt-2026-06-12-153952-pre-rs485-cd-substrate.dump`, then `atlas migrate apply --env local` applied `20260612043000_seed_plant_c_d_substrate_nodes.sql`. OTA upload to `plant-a-substrate-node.local` succeeded. The new `/status` shape is live, and Postgres shows fresh Plant A substrate rows from the flashed firmware. Plant D commissioning is blocked because the controller did not receive any response from the already-plugged Plant D probe at `0x01` or `0x03`, including after one wiring adjustment; firmware correctly backed off instead of retrying every loop. No Plant D/C fresh rows exist yet.

## Context and Orientation

Dirt's local hardware service is `dirt-hwd`, a FastAPI app exposing `POST /api/ingest/sensors` in `apps/hwd/src/dirt_hwd/api/ingest.py`. ESP32 firmware posts a Pydantic-validated body containing `site_id`, `tent_id`, `zone_id`, `device_id`, firmware/network diagnostics, and a `metrics` object. The route calls `ReadingsService.ingest_reading()` in `apps/shared/src/dirt_shared/services/readings.py`, which updates `device.last_seen`, resolves the metric names to enabled `capability` rows for the given `device_id`, and inserts capability-owned `sensorreading` rows.

The scoped inventory model lives in `apps/shared/src/dirt_shared/models/device.py`. A `Device` row is unique by `(site_id, device_id)` and can be scoped to a `tent` and `zone`. A `Capability` row belongs to one device and has a public `capability_id`, `metric_name`, unit, source, enabled flag, and metadata. The current RS485 seed migration `migrations/20260610183000_seed_plant_a_substrate_node.sql` seeds `plant-a-substrate-node` and four capabilities:

- `soil_moisture_pct`
- `substrate_temp_c`
- `substrate_ec_us_cm`
- `substrate_ph`

Plant metric ownership lives in `apps/shared/src/dirt_shared/models/plant.py` through `PlantMetricStream`. The helper `get_supported_product_plant_moisture_capabilities()` intentionally returns only active direct-percent `soil_moisture_pct` capabilities. This is the current product moisture contract after the old capacitive ADC nodes were retired.

The current RS485 firmware is `firmware/rs485_substrate_node/src/main.cpp`. It uses shared libraries from `firmware/common/`:

- `wifi_client` for WiFi with sleep disabled and reconnect handling.
- `ota` for Arduino OTA updates.
- `ingest_client` for posting one sensor payload to HWD.

The firmware currently polls one DFRobot SEN0604 sensor at Modbus address `0x02` over the Seeed XIAO RS485 expansion board. It uses UART `9600 8N1`, RX GPIO 7, TX GPIO 6, and enable pin `D2`. It exposes `GET /health` and `GET /status` over LAN because normal USB must not be connected while the board is powered by the RS485 expansion board's 12 V runtime path.

DFRobot SEN0604 Modbus facts needed by this plan:

- Factory default address is `0x01`.
- Read function is `0x03`; write function is `0x06`.
- Measurement registers start at `0x0000` and return moisture x10 percent, temperature x10 deg C, EC in `us/cm`, and pH x10.
- Device address register is `0x07D0`, read/write, valid range `1-254`.
- Baud register is `0x07D1`; this plan keeps `9600 8N1` and does not change baud.

## Plan of Work

Milestone 1: Database contract for Plant C and Plant D substrate probes.

Add an Atlas migration under `migrations/` that upserts two logical devices under `homebox/main`:

- `plant-d-substrate-node`, zone `plant-d`, hostname `plant-a-substrate-node.local`, metadata including `sensor_model='DFRobot SEN0604'`, `bus_controller_device_id='plant-a-substrate-node'`, `bus='rs485'`, and `modbus_address='0x03'`.
- `plant-c-substrate-node`, zone `plant-c`, hostname `plant-a-substrate-node.local`, metadata including the same fields but `modbus_address='0x04'`.

For each logical device, upsert the same four capabilities as Plant A. Set capability metadata `expected_wire_metric=true`, `freshness_required=true`, `sensor_model='DFRobot SEN0604'`, `modbus_address`, and calibrated/operational pH/EC status to match the current Plant A posture. Then upsert active `plant_metric_stream` rows for current Plant D and Plant C for all four capabilities, with `soil_moisture_pct` display order first. Do not add a Plant B stream.

Add or update focused tests in `apps/hwd/tests/test_ingest_api.py`, `apps/hwd/tests/test_ingest_derivation.py`, and shared plant moisture tests so they validate behavior without pinning mutable seed values more than necessary. Good tests create or query the seeded C/D capability rows and prove that ingest writes four rows per logical device, freshness separates missing capabilities per logical device, and product plant moisture returns A/C/D only when active direct-percent readings exist.

Milestone 2: Slot-based firmware polling without address writes.

Refactor `firmware/rs485_substrate_node/src/main.cpp` from one global sensor to a fixed `ProbeSlot` array. Each slot should include:

- Plant label or zone id.
- Logical `device_id`.
- Modbus address.
- Whether the slot is enabled.
- Latest `SubstrateSample`.
- Last Modbus status and last raw frame.
- Per-slot Modbus success/failure counters.
- Per-slot ingest status counters.

Change `build_read_command()`, `read_substrate_sample()`, `build_sample_json()`, and `post_latest_sample()` to take a slot or address argument. The poll loop should iterate enabled known slots and post one payload per valid sample using `ingest.post(SITE_ID, TENT_ID, slot.zone_id, slot.device_id, metrics, diagnostics)`.

Expand `/status` to report controller-level diagnostics plus per-slot status. Keep `/health` simple but include enough aggregate state to show whether any enabled slot is failing. Do not emit new diagnostic fields to HWD until `DeviceDiagnostics` has been updated to accept them; otherwise `extra='forbid'` will reject payloads.

Milestone 3: Guarded one-at-a-time factory address provisioning.

Add provisioning logic that runs after normal slot polling. Only attempt provisioning when:

- At least one target slot is unassigned or has never responded.
- No provisioning attempt is currently pending cooldown.
- Known active slots have just been polled or skipped, reducing the chance of acting during bus noise.

The provisioning order is Plant D then Plant C. The firmware probes factory address `0x01` by reading the normal measurement block or address register. If a valid single response is received, it writes holding register `0x07D0` with function `0x06` and the next target address. Then it verifies:

- `0x01` no longer returns a valid response after a short delay or power-cycle-independent settling period.
- The target address returns a valid measurement frame with matching address and CRC.

If verification succeeds, mark the slot as assigned in non-volatile storage using `Preferences`. Store at least the target address, assignment state, and a small firmware schema version. Do not store plant identity dynamically; plant identity stays in the compiled slot table so `/status`, DB seeds, and operator labels remain aligned. If verification fails, record the failure in `/status`, increment counters, and back off without retrying every loop.

Important operator invariant: never plug two factory-default sensors in at once. The plan and wiki must say that multiple address-`0x01` sensors on the bus are ambiguous and unsupported. If it happens, unplug all new sensors, leave the already-assigned probes connected, then reconnect one new sensor at a time.

Milestone 4: Live commissioning and validation.

Build and flash the firmware by OTA if possible. Use USB only with the 12 V runtime path disconnected. Commission Plant D first:

1. Start with Plant A connected and responding at `0x02`.
2. Plug in exactly one new SEN0604.
3. Watch `/status` until it reports the factory sensor was assigned to Plant D at `0x03`.
4. Label the cable/probe as Plant D / `addr=0x03`.
5. Confirm Postgres rows and dashboard/hosted freshness.

Then commission Plant C using the same workflow, expecting assignment to `0x04`.

Milestone 5: Wiki and operator docs.

Update `wiki/hardware/rs485-substrate-sensors.md`, `wiki/hardware/rs485-substrate-sensor-calibration.md`, `wiki/hardware/soil-moisture-sensing-options.md` if still relevant, `wiki/overview.md`, and the Plant C/D pages. Document the one-at-a-time commissioning rule, current address map, status endpoint interpretation, and what to do if a factory-default collision is suspected.

## Concrete Steps

Start by inspecting the current state:

    cd /home/akcom/code/dirt
    git status --short
    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,260p' firmware/rs485_substrate_node/src/main.cpp
    sed -n '1,260p' apps/hwd/src/dirt_hwd/api/ingest.py
    sed -n '360,540p' apps/shared/src/dirt_shared/services/readings.py

Create the database migration. If SQLModel classes do not change, hand-authoring an idempotent seed migration is acceptable, following the style of `migrations/20260610183000_seed_plant_a_substrate_node.sql` and `migrations/20260612020505_add_plant_metric_stream.sql`. If model changes are required, follow the Atlas workflow in `docs/database.md`.

Run focused backend tests:

    uv run pytest apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/shared/tests/test_daily_sensors.py apps/gateway/tests/test_sync.py -q

Build the firmware:

    cd firmware
    pio run -e plant-a-substrate

If OTA credentials are available and the existing node is online, upload after confirming the board is in normal 12 V runtime power and USB is unplugged:

    cd /home/akcom/code/dirt/firmware
    PLANT_OTA_PASSWORD=<from environment> pio run -e plant-a-substrate-ota -t upload

Validate status:

    curl -fsS http://plant-a-substrate-node.local/health
    curl -fsS http://plant-a-substrate-node.local/status | jq .

Query Postgres for fresh C/D substrate rows:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "
      SELECT d.device_id, z.zone_id, c.capability_id, sr.metric, sr.value, now() - sr.ts AS age
      FROM sensorreading sr
      JOIN capability c ON c.id = sr.capability_id
      JOIN device d ON d.id = c.device_id
      LEFT JOIN zone z ON z.id = d.zone_id
      WHERE d.device_id IN ('plant-a-substrate-node', 'plant-d-substrate-node', 'plant-c-substrate-node')
      ORDER BY sr.ts DESC
      LIMIT 24;"

Before committing implementation work, run:

    make fix
    uv run pytest -q
    cd firmware && pio run -e plant-a-substrate

## Validation and Acceptance

The change is accepted when all of the following are true:

- Backend tests prove Plant C and Plant D logical substrate device ingest writes four capability-owned readings per device.
- Product plant moisture helpers return direct `soil_moisture_pct` for A/C/D when readings exist and do not synthesize any value for B.
- Metric freshness reports stale/fresh independently per logical substrate device and per capability.
- Firmware builds successfully for the USB target and, if possible, OTA target.
- `/status` shows a stable address map:
  - Plant A `device_id='plant-a-substrate-node'`, zone `plant-a`, address `0x02`.
  - Plant D `device_id='plant-d-substrate-node'`, zone `plant-d`, address `0x03`.
  - Plant C `device_id='plant-c-substrate-node'`, zone `plant-c`, address `0x04`.
- With only Plant A initially connected, adding one new factory-default sensor assigns only Plant D and does not disturb Plant A.
- Adding the second factory-default sensor after Plant D is assigned assigns Plant C and does not disturb A or D.
- Postgres shows fresh rows under all three logical device IDs.
- The hosted/local dashboard or API path that consumes plant current metrics can show A/C/D moisture when synced.
- Wiki docs explain the one-at-a-time commissioning workflow and the unsupported multi-default-sensor collision case.

## Idempotence and Recovery

Database seed migrations must use `ON CONFLICT` and be safe to apply once through Atlas and safe to reason about if manually inspected. They should not duplicate devices, capabilities, or plant metric stream rows. If a migration points C/D to the wrong capability, fix it with a new migration; do not edit already-applied migration files.

Firmware normal polling is safe to repeat. Address provisioning is intentionally not a blind repeated action. Once a sensor is assigned and verified, store assignment state in `Preferences` and report it through `/status`. Retrying a failed address write should require either a cooldown or an operator action such as unplugging/replugging the unassigned sensor.

If the wrong sensor is assigned to the wrong plant, recover operationally by unplugging the probe, labeling the mistake, and either changing the sensor address on a bench setup or adding a deliberate firmware/DB correction. Do not let production firmware randomly swap plant identities based on discovery order after assignment.

If two factory-default sensors are accidentally plugged in at once, do not try to infer which is which from bad frames. Unplug both new sensors, confirm existing A/D/C assigned probes still respond at their non-default addresses, then reconnect one default sensor at a time.

If the firmware update breaks polling, OTA back to the previous known-good firmware if OTA remains available. If OTA is unavailable, disconnect 12 V runtime power before using USB for recovery flashing.

## Artifacts and Notes

Initial code review notes from 2026-06-12:

- Existing firmware single-sensor identity and address definitions are in `firmware/rs485_substrate_node/src/main.cpp`.
- Existing ingest payload boundary is `IngestPayload` in `apps/hwd/src/dirt_hwd/api/ingest.py`.
- Existing capability resolution is `_resolve_capability_ids()` in `apps/shared/src/dirt_shared/services/readings.py`.
- Existing direct-percent product moisture selection is `get_supported_product_plant_moisture_capabilities()` in `apps/shared/src/dirt_shared/services/readings.py`.
- Existing Plant A RS485 seed/cutover migrations are `migrations/20260610183000_seed_plant_a_substrate_node.sql`, `migrations/20260611120000_plant_a_moisture_cutover.sql`, `migrations/20260612020505_add_plant_metric_stream.sql`, and `migrations/20260611143000_retire_capacitive_moisture_nodes.sql`.

Live validation artifacts should be appended here with short excerpts from `/status`, SQL fresh-row queries, and test output.

Milestone 1 artifacts from 2026-06-12:

- Added `migrations/20260612043000_seed_plant_c_d_substrate_nodes.sql` and regenerated `migrations/atlas.sum` with `atlas migrate hash --env local`.
- Updated `apps/hwd/tests/test_ingest_api.py`, `apps/hwd/tests/test_ingest_derivation.py`, and `apps/shared/tests/test_daily_sensors.py` for C/D logical substrate probes.
- Focused validation: `uv run pytest apps/hwd/tests/test_ingest_api.py apps/hwd/tests/test_ingest_derivation.py apps/shared/tests/test_daily_sensors.py apps/gateway/tests/test_sync.py -q` passed with `83 passed in 33.60s`.

Milestone 2 artifacts from 2026-06-12:

- Updated `firmware/rs485_substrate_node/src/main.cpp` and `firmware/rs485_substrate_node/platformio.ini`.
- Firmware validation: `cd firmware/rs485_substrate_node && pio run -e plant-a-substrate` succeeded; PlatformIO reported RAM `15.0%` and flash `75.3%`.
- Source guard confirmed no Milestone 3 address-write/provisioning behavior was added; only the existing boot-count `Preferences` usage matched the guard search.

Milestone 3 artifacts from 2026-06-12:

- Updated `firmware/rs485_substrate_node/src/main.cpp` and `firmware/rs485_substrate_node/platformio.ini`.
- Firmware validation: `cd firmware/rs485_substrate_node && pio run -e plant-a-substrate` succeeded; PlatformIO reported RAM `15.3%` and flash `75.5%`.
- Source guard confirmed bounded provisioning implementation with `0x06`, `0x07D0`, factory-default probing, cooldown/state reporting, and `Preferences` `getUInt`/`getBool`/`putUInt`/`putBool` assignment persistence.

Milestone 4 partial artifacts from 2026-06-12:

- Backup before live local apply: `var/db-backups/dirt-2026-06-12-153952-pre-rs485-cd-substrate.dump`.
- `atlas migrate apply --env local` applied `20260612043000_seed_plant_c_d_substrate_nodes.sql`.
- OTA upload: `cd firmware/rs485_substrate_node && pio run -e plant-a-substrate-ota -t upload` succeeded.
- `/status` after OTA showed controller slot map live with Plant A `0x02` assigned/ok, Plant D `0x03` unassigned/no_response, Plant C `0x04` unassigned/no_response, and provisioning `last_result='no_default_response'` for target Plant D.
- SQL fresh-row query showed Plant A substrate rows about 6 seconds old after OTA; no Plant D/C rows yet.
- After the operator adjusted Plant D wiring, a retry still showed Plant D invisible: provisioning `attempt_count=3`, `last_result='no_default_response'`, `last_default_probe_status='no_response'`, Plant D `assigned=false`, and Plant D `last_modbus_status='no_response'`.
- Temporary read-only scanner: added and OTA-flashed `plant-a-substrate-scan-ota`, with `scan_debug_enabled=true` and provisioning disabled. `/scan` result found only address `0x02` responding; `0x01` through `0x10` otherwise reported `no_response`.
- After unplugging Plant A and leaving only the new probe connected, `/scan` found no valid or partial responses from `0x01` through `0x10`; `/status` showed all configured slots at `last_modbus_status='no_response'`.
- The scan endpoint was compacted for full-range sweeps and `plant-a-substrate-scan-ota` was re-flashed. With only the new probe connected after an A/B swap, `/scan` across `0x01` through `0xFE` returned `ok_count=0`, `no_response_count=254`, all other counters `0`, and no result entries.
- Cleanup after scanning: removed all temporary scan firmware code and the `plant-a-substrate-scan-ota` PlatformIO env, rebuilt `plant-a-substrate`, and OTA-flashed `plant-a-substrate-ota`. Live `/status` showed Plant A at `0x02` reading successfully again; `/scan` returned `404`.

## Interfaces and Dependencies

Firmware interfaces:

- Project: `firmware/rs485_substrate_node/`
- Build envs: `plant-a-substrate`, `plant-a-substrate-ota`
- Hostname: `plant-a-substrate-node.local`
- HTTP endpoints:
  - `GET /health`
  - `GET /status`
- Ingest target: `SERVER_URL`, normally `http://homebox.local:8000/api/ingest/sensors`
- Secrets: `WIFI_SSID`, `WIFI_PASSWORD`, `SENSOR_INGEST_TOKEN`, `OTA_PASSWORD`

RS485/Modbus interfaces:

- UART: `9600 8N1`
- Factory-default SEN0604 address: `0x01`
- Plant A address: `0x02`
- Plant D target address: `0x03`
- Plant C target address: `0x04`
- Measurement read: function `0x03`, start register `0x0000`, length `0x0004`
- Address write: function `0x06`, register `0x07D0`, value target address
- Baud register `0x07D1` is out of scope and should not be written by this plan.

Backend interfaces:

- FastAPI route: `POST /api/ingest/sensors`
- Request DTO: `IngestPayload`
- Diagnostics DTO: `DeviceDiagnostics`
- Device/capability models: `Device`, `Capability`
- Plant mapping model: `PlantMetricStream`
- Shared plant moisture helpers: `get_supported_product_plant_moisture_capabilities()` and `get_latest_product_plant_moisture_readings()`

Database identities:

- Site: `homebox`
- Tent: `main`
- Zones: `plant-a`, `plant-c`, `plant-d`
- Device IDs:
  - `plant-a-substrate-node`
  - `plant-d-substrate-node`
  - `plant-c-substrate-node`
- Capability IDs per logical device:
  - `soil_moisture_pct`
  - `substrate_temp_c`
  - `substrate_ec_us_cm`
  - `substrate_ph`

External references:

- DFRobot SEN0604 reference: https://wiki.dfrobot.com/sen0604/docs/20297
- Local wiki hardware page: `wiki/hardware/rs485-substrate-sensors.md`
- Prior Plant A plan: `docs/epics/rs485-plant-a-substrate-node/ExecPlan.md`

## Revision Notes

- 2026-06-12: Initial ExecPlan created. It chooses logical per-probe devices over a multi-device ingest payload, fixes the address plan to keep Plant A at `0x02`, and records one-at-a-time factory-default provisioning as a hard operator invariant.
