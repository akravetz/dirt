# Plant A RS485 substrate node cutover

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, Plant A can use the embedded RS485 substrate probe as its canonical moisture stream instead of the old capacitive ADC probe. The new Seeed XIAO ESP32C3 + Seeed RS485 expansion board will run normal WiFi firmware, read the DFRobot SEN0604 at Modbus address `0x02`, and post Plant A substrate moisture, pH, electrical conductivity, and temperature into Dirt through the existing `/api/ingest/sensors` boundary. Runtime operation must not require USB serial, because the board is powered from the RS485 board's 12V-to-5V path and normal USB power should not be plugged in at the same time.

The observable end state is:

- `plant-a-substrate-node.local` is reachable on the LAN and accepts OTA updates.
- `GET http://plant-a-substrate-node.local/status` returns the latest Modbus frame, decoded values, ingest counters, and last HTTP status.
- `device.device_id='plant-a-substrate-node'` has a fresh heartbeat in Postgres.
- `sensorreading` has fresh capability-owned rows for `soil_moisture_pct`, `substrate_ph`, `substrate_ec_us_cm`, and `substrate_temp_c`.
- Plant A's `plant.moisture_capability_id` points at the RS485 node's `soil_moisture_pct` capability, so Plant A pages, hosted sync, and any retained status/reporting consumers no longer depend on the capacitive `plant-a-node` stream.

## Progress

- [x] (2026-06-10) Read `.agents/PLANS.md`, `docs/commands.md`, `docs/database.md`, `docs/observability.md`, `docs/rules/simple-clean-architecture.md`, and `docs/rules/boundary-contracts.md`.
- [x] (2026-06-10) Read the RS485 wiki pages and current debug firmware: `wiki/hardware/rs485-substrate-sensors.md`, `wiki/hardware/rs485-substrate-sensor-calibration.md`, and `debug/rs485_soil_probe/src/main.cpp`.
- [x] (2026-06-10) Confirmed live USB serial from the debug firmware showed repeated `[read] no response` while the hardware was USB-powered only; the working hypothesis is that the RS485 board/sensor power topology was wrong for the current bench setup.
- [x] (2026-06-10) Confirmed from Seeed docs and schematic inspection that normal USB power should not be tied to an externally fed XIAO 5V/VBUS rail during runtime; use 12V runtime power plus OTA/HTTP/DB observability instead.
- [x] (2026-06-10) Authored this ExecPlan.
- [x] (2026-06-10) Corrected sensor power by providing 5V to the RS485 sensor path and confirmed live ID `0x02` Modbus data over the current debug firmware. The hardware communication blocker is cleared; implementation can proceed to flashing WiFi/OTA firmware and testing live ingest.
- [ ] Implement Milestone 1: add the database/device contract for the RS485 substrate node.
- [ ] Implement Milestone 2: teach plant moisture consumers to handle either calibrated raw ADC or direct percent moisture capabilities.
- [ ] Implement Milestone 3: add dedicated RS485 substrate-node firmware with OTA and HTTP status.
- [ ] Implement Milestone 4: flash, power from 12V, validate live data without USB serial, and cut Plant A over.
- [ ] Implement Milestone 5: retire or disable the old Plant A capacitive node after stable RS485 operation.

## Surprises & Discoveries

- Observation: The RS485 debug firmware in `debug/rs485_soil_probe/src/main.cpp` is already configured for Modbus address `0x02`, command `02 03 00 00 00 04 44 3A`, UART `9600 8N1`, RX GPIO 7, TX GPIO 6, and enable pin `D2`.
  Evidence: `SENSOR_ADDRESS = 0x02`, `READ_COMMAND`, and `rs485.begin(SENSOR_BAUD, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN)` in that file.

- Observation: The current raw serial capture path cannot be the runtime diagnostic path because USB power must not be present while the RS485 board is feeding the XIAO 5V rail from 12V.
  Evidence: Seeed's XIAO ESP32C3 docs describe the `5V` pin as USB VBUS input/output and require a diode when feeding external 5V; the RS485 board docs warn that the `5V OUT/IN` switch must be set correctly to avoid damage. The implementation must expose status over WiFi.

- Observation: Current Plant A moisture is capability-owned through `Plant.moisture_capability_id`, but existing consumers assume that the capability points to `soil_moisture_raw` and derive `soil_moisture_pct` through `SensorCalibration`.
  Evidence: `apps/shared/src/dirt_shared/services/daily_sensors.py` and `apps/voice/src/dirt_voice/tools/sensors.py` query `SensorReading.metric == "soil_moisture_raw"` and join `SensorCalibration` for the plant's moisture capability.

- Observation: After adding 5V power to the sensor path, the same serial-only debug firmware now reads stable Modbus frames from address `0x02`; the address diagnostic reports `value=2` and the old address check gets no response.
  Evidence: Live capture on 2026-06-10 showed repeated frames such as `02 03 08 01 0D 00 D6 00 93 00 2F 7F BC`, decoded as moisture `26.9%`, temperature `21.4C`, EC `147 us/cm`, pH `4.7`, plus `[address] value=2` and `[old-address-check] no response`.

- Observation: Official Seeed docs do not indicate a direct RS485 bus versus WiFi conflict. The RS485 expansion board documentation explicitly uses XIAO ESP32C3 `D4/GPIO6` and `D5/GPIO7` for the RS485 UART and `D2` for the enable pin, which matches this repo's debug firmware. The XIAO ESP32C3 pinout lists those pins as having JTAG alternate functions, but Seeed's own RS485 example still uses them for this expansion board.
  Evidence: Seeed RS485 Expansion Board docs say the XIAO ESP32C3 communicates with the RS485 board using `D4 (GPIO6)` and `D5 (GPIO7)`, and the sample code uses `#define enable_pin D2` plus `mySerial.begin(..., 7, 6)`. The XIAO ESP32C3 docs list `D4/GPIO6` and `D5/GPIO7` as the board's I2C-labeled pins with JTAG alternate functions.

- Observation: Intermittent WiFi is more likely to come from antenna placement, power stability, WiFi sleep behavior, or blocking firmware than from RS485 pin choice. The XIAO ESP32C3 relies on its included external antenna for stronger wireless signal, and the production firmware must not block on USB serial because runtime diagnostics are supposed to work with USB unplugged.
  Evidence: Seeed's XIAO ESP32C3 docs describe IEEE 802.11 b/g/n WiFi and say the board includes an external antenna to increase signal strength. The RS485 example code includes `while(!Serial)` patterns for demo serial workflows, but that pattern would be wrong for this no-USB runtime firmware. Espressif's ESP32-C3 WiFi low-power docs describe WiFi power-save modes that trade timing/responsiveness for reduced power; this repo's shared `wifi_client` already calls `WiFi.setSleep(false)` for always-powered sensor nodes.

- Observation: `DEVICE_METRICS` is carrying mixed responsibilities that now overlap the scoped database model.
  Evidence: `device` and `capability` rows already own hardware identity, metric names, units, sources, and enabled state. `DEVICE_METRICS` still declares emitted metrics and consumer-facing persisted metrics, and those flags are reused by ingest drift warnings, metric freshness, daily checkpoint code, and voice status code. This creates two editable sources for device/capability inventory.

## Decision Log

- Decision: Use a new device identity, `plant-a-substrate-node`, instead of reusing `plant-a-node`.
  Rationale: `plant-a-node` accurately describes the existing capacitive ADC node and its historical `soil_moisture_raw` stream. A new RS485 node has different hardware, units, health signals, and rollback behavior. Keeping a distinct device identity allows side-by-side validation and a clear Plant A moisture ownership switch through `plant.moisture_capability_id`.
  Date/Author: 2026-06-10 / Codex

- Decision: Use `soil_moisture_pct` as the RS485 moisture metric and capability ID for Plant A, not `soil_moisture_raw` and not `substrate_moisture_pct`.
  Rationale: The SEN0604 register `0x0000` reports x10 percent, not an ADC count. Storing it as raw would feed it into the existing auto-extrema calibration and produce false percentages. The product-facing plant moisture metric throughout hosted UI and reports is already `soil_moisture_pct`, so using that metric keeps Plant A's dashboard semantics direct.
  Date/Author: 2026-06-10 / Codex

- Decision: Use `substrate_temp_c`, `substrate_ec_us_cm`, and `substrate_ph` for the additional RS485 probe metrics.
  Rationale: These names avoid confusing substrate temperature with canopy air temperature, preserve EC units as reported by the sensor, and match the naming proposed in `wiki/hardware/soil-moisture-sensing-options.md`.
  Date/Author: 2026-06-10 / Codex

- Decision: Runtime firmware diagnostics must be available via LAN HTTP status and database reads, not USB serial.
  Rationale: Normal USB power and the RS485 board's externally generated 5V rail should not be tied together. OTA plus HTTP status gives enough field observability without changing the power topology.
  Date/Author: 2026-06-10 / Codex

- Decision: Initial flashing may use USB only with 12V disconnected; subsequent updates should use OTA.
  Rationale: The board currently runs serial-only debug firmware and may not have OTA enabled. USB is acceptable as a one-time programming power source if the 12V/external 5V path is disconnected. Once the WiFi firmware is installed, normal development should use `espota`.
  Date/Author: 2026-06-10 / Codex

- Decision: Move the durable RS485 metric contract toward database-owned device/capability identity plus freshness expectation, not another permanent `DEVICE_METRICS` entry.
  Rationale: The durable operational fact is that enabled capabilities for `plant-a-substrate-node` should keep producing data. That belongs with the canonical `device`/`capability` catalog, preferably through typed capability metadata such as `expected_wire_metric` and `freshness_required`, and later real columns if the policy proves stable. Code should continue to own ingest derivation and transformation behavior. Consumer-specific policies for the voice agent or daily checkpoint agent should not be promoted into schema while those agents are candidates for deprecation; retained consumers should derive from capability relationships or keep narrowly owned code.
  Date/Author: 2026-06-10 / Codex

## Outcomes & Retrospective

Not started. At completion, record the first stable no-USB runtime capture, the Plant A cutover timestamp, and whether pH/EC values are only stored for trend/reference or also shown in the dashboard.

## Context and Orientation

Dirt's local hardware service is `dirt-hwd`, a FastAPI app that exposes `POST /api/ingest/sensors` in `apps/hwd/src/dirt_hwd/api/ingest.py`. ESP32 firmware posts a Pydantic-validated JSON body with `site_id`, `tent_id`, `zone_id`, `device_id`, `metrics`, firmware version, IP, uptime, and WiFi diagnostics. The handler calls `ReadingsService.ingest_reading()` in `apps/shared/src/dirt_shared/services/readings.py`. That service updates the canonical `device.last_seen` heartbeat and inserts one `sensorreading` row per resolved `capability`.

The current hardware contract is split. Database identity is already scoped through `site`, `tent`, `zone`, `device`, and `capability`, and capability rows carry the stable `capability_id`, `metric_name`, `unit`, `source`, and `enabled` fields. `apps/shared/src/dirt_shared/sensor_contract.py` still declares `DEVICE_METRICS`, keyed by public `device_id` and `capability_id`, to describe emitted metrics and consumer-facing persisted metrics. This plan should not deepen that split. It should use the RS485 node as the cleanup point for moving durable inventory and freshness policy into database-backed capability metadata while leaving derivation behavior in code.

Current local scope is `site_id='homebox'`, `tent_id='main'`, `zone_id='plant-a'`. Device rows live in `apps/shared/src/dirt_shared/models/device.py`. The current Plant A capacitive sensor is `device.device_id='plant-a-node'`, capability `soil_moisture_raw`, and it is seeded by migrations such as `migrations/20260504000618_multi_tent_controller.sql`.

Plant rows live in `apps/shared/src/dirt_shared/models/plant.py`. `Plant.moisture_capability_id` points at the canonical capability used for that plant's moisture stream. For the current A-D capacitive nodes, consumers expect the capability to be a `soil_moisture_raw` ADC stream and convert it to `soil_moisture_pct` with `SensorCalibration`. The RS485 probe's moisture register is already a percent value, so consumers must be updated to use direct percent when the plant's moisture capability has metric `soil_moisture_pct`, while preserving calibrated raw behavior for Plants B-D.

The RS485 debug firmware lives at `debug/rs485_soil_probe/`. It successfully read the SEN0604 during earlier calibration work and then was changed to address `0x02`. Relevant settings are:

    Modbus address: 0x02
    UART: 9600 8N1
    Read command: 02 03 00 00 00 04 44 3A
    Registers:
      0x0000 moisture, x10 percent
      0x0001 temperature, x10 deg C
      0x0002 EC, us/cm
      0x0003 pH, x10
    XIAO pins:
      RS485 RX: GPIO7
      RS485 TX: GPIO6
      RS485 DE/RE enable: D2

Existing reusable firmware libraries are under `firmware/common/`: `wifi_client`, `ota`, and `ingest_client`. `firmware/fan_controller/src/main.cpp` is the best current example of an ESP32 firmware with WiFi, OTA, HTTP status/control, diagnostics counters, and ingest.

Power constraint: the RS485 board can convert 12V to 5V for the XIAO and sensor bus, but normal USB should not be connected at the same time as another 5V source. Use a data-only USB cable only if a host connection is unavoidable; otherwise rely on WiFi. Never feed 12V into the XIAO directly.

## Plan of Work

Milestone 1: Add the DB-backed RS485 substrate node contract and retire `DEVICE_METRICS` as inventory.

Create an Atlas migration that upserts the `plant-a-substrate-node` device under `homebox/main/plant-a`, upserts the four capabilities, and initially leaves `plant.moisture_capability_id` unchanged. This lets the new node run side-by-side with `plant-a-node` before Plant A's canonical moisture stream changes. The migration should be idempotent, use `ON CONFLICT`, and include metadata noting the sensor model, Modbus address `0x02`, and that pH/EC are experimental.

The four capabilities are:

    soil_moisture_pct -> soil_moisture_pct
    substrate_temp_c -> substrate_temp_c
    substrate_ec_us_cm -> substrate_ec_us_cm
    substrate_ph -> substrate_ph

Extend capability metadata through typed helpers rather than ad hoc JSON reads. The initial typed policy only needs durable operational fields:

- `expected_wire_metric=true` for capabilities the firmware is expected to emit.
- `freshness_required=true` for capabilities that should alert/log when the device is online but the metric stops arriving.

Do not add DB policy for voice status or daily checkpoint participation while those agents are candidates for deprecation. If either consumer remains, keep its presentation/reporting choices in that consumer or derive from existing relationships such as `Plant.moisture_capability_id`.

Refactor the remaining `DEVICE_METRICS` consumers so DB-backed capability identity and typed metadata own the durable contract:

- Ingest drift detection should query expected wire metrics for the posting device.
- Metric freshness should query enabled capabilities with `freshness_required=true`, gated by canonical `device.last_seen`.
- `apps/hwd/tests/test_ingest_derivation.py` should keep proving code-owned derivation behavior, but it should not be the canonical device inventory for directly emitted RS485 metrics.
- Remove `plant-a-substrate-node` from any plan to add a permanent `DEVICE_METRICS` entry. If a temporary compatibility shim is needed during the refactor, delete it in the same milestone.

Add or extend HWD ingest tests so a post from `plant-a-substrate-node` writes four capability-owned rows and updates the device heartbeat. Add focused tests for the DB-backed expected-wire and freshness-required queries. Do not add wire aliases for the RS485 node unless actual firmware emits different names.

Milestone 2: Make Plant A moisture consumers metric-aware.

Add a small shared helper in `apps/shared/src/dirt_shared/services/readings.py` or a narrowly named plant-moisture helper module that resolves a plant's `moisture_capability_id` to its `Capability.metric_name` and latest readings:

- If the capability metric is `soil_moisture_pct`, read the latest direct percent value and return it as the product-facing moisture percentage.
- If the capability metric is `soil_moisture_raw`, keep the existing calibrated path using `SensorCalibration` and `compute_calibrated_pct()`.
- For any other metric, return no plant moisture and log or raise in tests depending on the consumer boundary.

Update retained Plant A moisture consumers and gateway local sync code in `apps/gateway/src/dirt_gateway/local.py` so they use the same semantic rule rather than hard-coding `soil_moisture_raw`. If the daily checkpoint agent or voice agent is still retained at implementation time, update `apps/shared/src/dirt_shared/services/daily_sensors.py` and `apps/voice/src/dirt_voice/tools/sensors.py` to call the same helper. If either agent is being deprecated, delete its Plant A moisture dependency instead of promoting its consumer policy into the database. Preserve the existing hosted/browser product metric `soil_moisture_pct`; do not expose raw RS485 moisture as a new product metric.

Add focused tests covering both paths:

- Plant B-D style: `Plant.moisture_capability_id` points at `soil_moisture_raw`, calibration exists, consumer returns computed `soil_moisture_pct`.
- Plant A RS485 style: `Plant.moisture_capability_id` points at `soil_moisture_pct`, no calibration is required, consumer returns the direct value.
- Hosted/gateway rollups still emit `soil_moisture_pct` for plant moisture and do not sync `soil_moisture_raw` as the product-facing metric.

Milestone 3: Add dedicated RS485 substrate-node firmware.

Create `firmware/rs485_substrate_node/` with `platformio.ini`, `src/main.cpp`, `src/secrets.h.example`, and the same ignored `src/secrets.h` pattern as the existing ESP32 firmware. Reuse `firmware/common/ingest_client`, `wifi_client`, and `ota`.

Firmware requirements:

- Build target `plant-a-substrate` for one-time USB upload and `plant-a-substrate-ota` for OTA upload to `plant-a-substrate-node.local`.
- Build flags include `FIRMWARE_VERSION`, `NODE_SITE_ID="homebox"`, `NODE_TENT_ID="main"`, `NODE_ZONE_ID="plant-a"`, `NODE_DEVICE_ID="plant-a-substrate-node"`, `NODE_HOSTNAME="plant-a-substrate-node"`, `MODBUS_ADDRESS=0x02`, and `POST_INTERVAL_MS=30000`.
- RS485 serial uses `HardwareSerial(1)` on RX GPIO7 and TX GPIO6, enable pin `D2`, `9600 8N1`.
- The loop calls `ota::loop()` and `wifi_client::maintain()` frequently, polls the SEN0604 every 30 seconds, validates Modbus CRC, decodes the four registers, and posts:

    {"soil_moisture_pct":23.1,"substrate_temp_c":19.8,"substrate_ec_us_cm":130,"substrate_ph":5.3}

- The firmware should include diagnostics in the ingest payload: boot count if feasible, reset reason, Modbus success/failure counts, CRC mismatch count, short response count, no-response count, last Modbus response length, last ingest code, ingest ok/fail counts, free heap, min free heap, and max loop gap. Extend `DeviceDiagnostics` in `apps/hwd/src/dirt_hwd/api/ingest.py` only for fields that will actually be emitted.
- Add a read-only `GET /status` endpoint on port 80 returning JSON with current identity, firmware version, decoded latest sample, latest raw Modbus frame as a hex string, last Modbus status, last ingest status, WiFi snapshot, and diagnostics. Add `GET /health` returning a compact 200 response for scripts.
- Keep `Serial.print` debug lines if useful, but do not rely on them for validation.
- Keep WiFi sleep disabled through the shared `wifi_client` path. Do not introduce ESP-IDF/Arduino WiFi power-save modes for this mains-powered node until the node is stable; reduced-power modes can alter response timing and complicate OTA/status reliability.
- Do not use `while(!Serial)` or any other USB-serial wait in setup. Seeed demo code uses this pattern for interactive USB examples, but this node must boot and report over WiFi when no USB host is attached.

Firmware implementation notes:

- Prefer a small internal CRC function copied from `debug/rs485_soil_probe/src/main.cpp` rather than adding a Modbus library unless the code becomes meaningfully simpler.
- Keep status JSON hand-built with bounded buffers, following the existing firmware style. Avoid ArduinoJson unless hand-built status becomes unsafe or unreadable.
- If the sensor does not respond after flashing, first inspect `/status`, device heartbeat, and WiFi diagnostics. Then power-cycle the 12V supply and verify RS485 A/B and common ground.
- If WiFi is intermittent, inspect `/status` and device metadata for RSSI, reconnect count, last disconnect reason, and disconnected duration before changing RS485 code. Also physically verify that the U.FL antenna is snapped on and routed away from wet media, metal, the 12V wiring, and bundled RS485 cable.

Milestone 4: Flash, validate no-USB runtime, and cut Plant A over.

Before flashing, disconnect 12V/external 5V from the RS485 board. Use USB only as the temporary power/programming path:

    cd /home/akcom/code/dirt/firmware/rs485_substrate_node
    pio run -e plant-a-substrate
    pio run -e plant-a-substrate -t upload --upload-port /dev/ttyACM0

After upload, unplug USB. Set the RS485 board for the correct 12V-to-5V runtime mode, connect 12V, and wait for WiFi. Validate without USB serial:

    ping -c 3 plant-a-substrate-node.local
    curl -fsS http://plant-a-substrate-node.local/health
    curl -fsS http://plant-a-substrate-node.local/status | jq .

Then validate ingest through Postgres:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "
    SELECT d.device_id, d.last_seen, c.capability_id, sr.metric, sr.value, sr.ts
    FROM sensorreading sr
    JOIN capability c ON c.id = sr.capability_id
    JOIN device d ON d.id = c.device_id
    WHERE d.device_id = 'plant-a-substrate-node'
    ORDER BY sr.ts DESC
    LIMIT 12;"

Let the new RS485 node run side-by-side with the old capacitive Plant A node for 30 minutes. Confirm the RS485 node keeps posting all four metrics, device heartbeat stays fresh, and values are plausible and moving/stable as expected. Then create and apply a second migration or SQL seed migration that updates the current main Plant A row:

    UPDATE plant AS p
    SET moisture_capability_id = c.id,
        updated_at = now()
    FROM growrun gr
    JOIN site s ON s.id = gr.site_id
    JOIN tent t ON t.id = gr.tent_id
    JOIN device d ON d.site_id = s.id AND d.tent_id = t.id
    JOIN capability c ON c.device_id = d.id
    WHERE p.growrun_id = gr.id
      AND p.plant_id = 'a'
      AND gr.is_current IS TRUE
      AND s.site_id = 'homebox'
      AND t.tent_id = 'main'
      AND d.device_id = 'plant-a-substrate-node'
      AND c.capability_id = 'soil_moisture_pct';

The real migration must include a guard that raises if the RS485 device or capability is missing. After applying, verify Plant A's moisture reads through local services, gateway dry-run sync, hosted dev UI if necessary, and any retained voice/daily consumers.

Milestone 5: Retire the old Plant A capacitive stream after a 30-minute stable ingest window.

After 30 minutes of stable RS485 ingest, continue directly with deprecation of the old Plant A capacitive node and associated cleanup. Stable means the RS485 node has a fresh heartbeat, is posting `soil_moisture_pct`, `substrate_temp_c`, `substrate_ec_us_cm`, and `substrate_ph` at the expected cadence, and `/status` reports no persistent Modbus or WiFi failure. Disable the old Plant A capacitive node from current operations by physical unplugging, OTA firmware that stops posting, or a DB-level `device.enabled=false` depending on the desired operational behavior. Prefer source-of-truth cleanup over compatibility glue:

- Keep historical `plant-a-node` rows for history and rollback.
- Do not delete historical `sensorreading` rows.
- If the old device remains physically powered for a short side-by-side comparison, keep it distinct and do not point Plant A back to it unless RS485 validation fails.
- Update `wiki/hardware/rs485-substrate-sensors.md`, `wiki/hardware/rs485-substrate-sensor-calibration.md`, and the Plant A wiki page with the cutover timestamp and validation evidence.

## Concrete Steps

Start every implementation session from the repo root:

    cd /home/akcom/code/dirt
    sed -n '1,260p' docs/commands.md
    sed -n '1,260p' docs/epics/rs485-plant-a-substrate-node/ExecPlan.md

Read the relevant source before editing:

    sed -n '1,220p' apps/shared/src/dirt_shared/sensor_contract.py
    sed -n '1,180p' apps/shared/src/dirt_shared/models/device.py
    sed -n '1,260p' apps/hwd/src/dirt_hwd/api/ingest.py
    sed -n '1,760p' apps/shared/src/dirt_shared/services/readings.py
    sed -n '1,260p' apps/shared/src/dirt_shared/services/daily_sensors.py
    sed -n '1,260p' apps/voice/src/dirt_voice/tools/sensors.py
    sed -n '180,680p' apps/gateway/src/dirt_gateway/local.py
    sed -n '1,260p' debug/rs485_soil_probe/src/main.cpp
    sed -n '1,360p' firmware/fan_controller/src/main.cpp

Milestone 1 expected commands:

    uv run pytest apps/hwd/tests/test_ingest_derivation.py apps/hwd/tests/test_ingest_api.py -q
    uv run ruff check apps/shared/src/dirt_shared/sensor_contract.py apps/hwd/src/dirt_hwd/api/ingest.py apps/hwd/tests/test_ingest_derivation.py apps/hwd/tests/test_ingest_api.py

Atlas workflow for migrations:

    sed -n '1,260p' docs/database.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    atlas migrate hash --env local
    atlas migrate status --env local
    atlas migrate apply --env local --dry-run

If applying to the live local database, take a compressed backup first:

    set -a; source .env; set +a
    mkdir -p var/db-backups
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump -h 127.0.0.1 -U dirt -d dirt -Fc --compress=zstd:level=6 -f var/db-backups/dirt-$(date +%F-%H%M%S)-pre-rs485-plant-a.dump
    atlas migrate apply --env local

Milestone 2 expected commands:

    uv run pytest apps/shared/tests/test_daily_sensors.py apps/voice/tests/test_sensor_tools.py apps/gateway/tests/test_sync.py apps/hwd/tests/test_ingest_derivation.py -q
    uv run ruff check apps/shared/src/dirt_shared/services/readings.py apps/shared/src/dirt_shared/services/daily_sensors.py apps/voice/src/dirt_voice/tools/sensors.py apps/gateway/src/dirt_gateway/local.py

Milestone 3 expected commands:

    cd /home/akcom/code/dirt/firmware/rs485_substrate_node
    pio run -e plant-a-substrate

Milestone 4 no-USB runtime validation:

    curl -fsS http://plant-a-substrate-node.local/status | jq .
    set -a; source /home/akcom/code/dirt/.env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "
    SELECT d.device_id, d.last_seen, c.capability_id, sr.metric, sr.value, sr.ts
    FROM sensorreading sr
    JOIN capability c ON c.id = sr.capability_id
    JOIN device d ON d.id = c.device_id
    WHERE d.device_id = 'plant-a-substrate-node'
    ORDER BY sr.ts DESC
    LIMIT 12;"

Full regression before commit:

    uv run pytest apps/hwd/tests/test_ingest_derivation.py apps/hwd/tests/test_ingest_api.py apps/shared/tests/test_daily_sensors.py apps/voice/tests/test_sensor_tools.py apps/gateway/tests/test_sync.py -q
    uv run pytest apps/tests/invariants/ -q
    cd /home/akcom/code/dirt/firmware && pio test -e native
    cd /home/akcom/code/dirt/firmware/rs485_substrate_node && pio run -e plant-a-substrate

If committing:

    cd /home/akcom/code/dirt
    make fix
    git status --short
    git add ...
    git commit

Do not use `--no-verify`.

## Validation and Acceptance

Software acceptance:

- The database seed declares exactly the four RS485 capabilities, with typed metadata marking them as expected wire metrics and freshness-required runtime metrics.
- `DEVICE_METRICS` is no longer the durable source of device/capability inventory for the RS485 node; any temporary shim added during implementation is removed before milestone completion.
- A focused ingest test posts a payload from `plant-a-substrate-node` and verifies four `sensorreading` rows linked to that device's capabilities.
- Focused tests prove ingest drift detection and metric freshness derive their expected RS485 metrics from DB-backed capability policy.
- A focused plant moisture test proves direct `soil_moisture_pct` capability ownership needs no `SensorCalibration`.
- Existing calibrated raw moisture tests for `plant-a-node` or a test raw node still pass.
- Gateway or hosted-sync tests still expose product-facing `soil_moisture_pct` for plant moisture.
- Invariants pass.
- Firmware builds for `plant-a-substrate`.

Hardware acceptance:

- With USB unplugged and the board powered by 12V through the RS485 expansion board, `plant-a-substrate-node.local` resolves or is reachable by IP.
- `/status` shows `last_modbus_status` as `ok`, an ID `0x02` raw frame with a valid CRC, and decoded values in plausible ranges:
  - `soil_moisture_pct`: 0-100
  - `substrate_temp_c`: plausible tent/root-zone temperature
  - `substrate_ec_us_cm`: non-negative; treat high values and saturation as calibration evidence, not an immediate firmware bug
  - `substrate_ph`: plausible but experimental
- The HWD ingest endpoint returns HTTP 202 from firmware posts.
- Postgres shows fresh rows for all four metrics under `plant-a-substrate-node`.
- After cutover, Plant A's current moisture comes from `plant-a-substrate-node` and not `plant-a-node`.

Operational acceptance:

- A normal USB cable is not required for runtime diagnostics.
- OTA upload to `plant-a-substrate-node.local` succeeds after the initial flash.
- The old capacitive Plant A stream remains available for rollback until the RS485 path has been stable long enough to retire it deliberately.

## Idempotence and Recovery

The device/capability seed migration must use `ON CONFLICT` and be safe to run once through Atlas. Re-running the SQL manually is not the normal workflow, but the upsert shape should not create duplicate devices or capabilities.

The Plant A moisture cutover migration should be separated from initial device seeding. This gives a safe pause after the new node starts writing data. The cutover migration must fail loudly if the RS485 moisture capability is missing. If the RS485 node is bad after cutover, recover by applying a small rollback migration that points current Plant A back to `plant-a-node` / `soil_moisture_raw`.

Firmware upload recovery:

- If the initial USB flash fails, keep 12V disconnected and retry with the correct `/dev/ttyACM*` port from `pio device list`.
- If OTA fails after the first successful flash, use `/status` and device heartbeat to determine whether the board is online. Power-cycle 12V before falling back to USB.
- If USB fallback is required, disconnect 12V/external 5V before plugging in normal USB.

Runtime sensor recovery:

- If `/status` shows no Modbus response, verify 12V input, RS485 board 5V mode, sensor power, common ground, and A/B wiring. Try swapping RS485 A/B only after confirming power and ground.
- If `/status` is intermittently unreachable or device heartbeats show WiFi dropouts, first check external antenna attachment and placement. The antenna should be snapped onto the U.FL connector and placed outside dense canopy/wet media and away from metal, power wiring, and long parallel RS485 runs where practical.
- If WiFi dropouts persist with good antenna placement, use the firmware's RSSI, reconnect count, disconnect reason, disconnected duration, and reset reason fields to distinguish weak RF from power brownout/restart behavior. Keep `WiFi.setSleep(false)` enabled.
- If Modbus works but ingest fails, check `dirt-hwd` status and logs:

    systemctl --user status dirt-hwd --no-pager
    journalctl --user -u dirt-hwd -n 100 --no-pager

- If ingest writes only some metrics, check capability rows and typed capability metadata for naming drift.

Data recovery:

- Do not delete historical `plant-a-node` or `sensorreading` rows.
- Before applying live schema or cutover migrations, take a compressed backup as described in `docs/database.md`.
- If pH or EC values prove misleading, disable or hide their presentation; do not rewrite historical raw readings unless a clear unit bug is identified and documented.

## Artifacts and Notes

Relevant existing documentation:

- `wiki/hardware/rs485-substrate-sensors.md`
- `wiki/hardware/rs485-substrate-sensor-calibration.md`
- `wiki/hardware/soil-moisture-sensing-options.md`
- `docs/database.md`
- `docs/observability.md`

External references checked on 2026-06-10:

- Seeed XIAO ESP32C3 documentation: confirms 2.4 GHz WiFi support, included external antenna for stronger wireless signal, pinout, 5V/VBUS power warning, and strapping-pin notes.
- Seeed XIAO RS485 Expansion Board documentation: confirms the expansion board's intended UART pins on XIAO ESP32C3 are `D4/GPIO6` and `D5/GPIO7`, with `D2` as the RS485 enable pin, plus the `5V OUT/IN` and `120R` switch guidance.
- Espressif ESP32-C3 WiFi low-power documentation: confirms WiFi power-save modes trade timing/responsiveness for lower power; the always-powered Dirt node should keep WiFi sleep disabled for reliability unless future measurements justify changing it.

Current debug firmware details:

    debug/rs485_soil_probe/src/main.cpp
    SENSOR_ADDRESS = 0x02
    READ_COMMAND = 02 03 00 00 00 04 44 3A
    RS485_RX_PIN = 7
    RS485_TX_PIN = 6
    RS485_ENABLE_PIN = D2

Live capture before the power-topology correction:

    [read] no response
    [read] no response
    [read] no response

Live capture after providing 5V sensor power on 2026-06-10:

    [read] raw=02 03 08 01 0D 00 D6 00 93 00 2F 7F BC
    [sensor] moisture=26.9% temperature=21.4C ec=147 us/cm ph=4.7
    [read] raw=02 03 08 01 0E 00 D7 00 93 00 2F 71 7C
    [sensor] moisture=27.0% temperature=21.5C ec=147 us/cm ph=4.7
    [address] raw=02 03 02 00 02 7D 85
    [address] value=2
    [old-address-check] no response

This confirms the sensor is powered and responding at ID `0x02`. The next implementation pass can flash the WiFi/OTA firmware and test live HTTP status plus HWD ingest.

Record future evidence here as milestones complete:

- First successful `/status` response:
- First successful Postgres rows:
- Plant A cutover migration filename:
- OTA validation transcript:

## Interfaces and Dependencies

Firmware:

- New PlatformIO project: `firmware/rs485_substrate_node/`
- Environments: `plant-a-substrate`, `plant-a-substrate-ota`
- Hostname: `plant-a-substrate-node.local`
- Runtime HTTP endpoints:
  - `GET /health`
  - `GET /status`
- Firmware secrets: `WIFI_SSID`, `WIFI_PASSWORD`, `SERVER_URL`, `SENSOR_INGEST_TOKEN`, `OTA_PASSWORD`, same semantics as existing firmware `secrets.h` files.

Database:

- Device: `plant-a-substrate-node`
- Scope: `homebox/main/plant-a`
- Controller: `esp32`
- Suggested kind: `moisture_node`
- Capabilities:
  - `soil_moisture_pct`, metric `soil_moisture_pct`, unit `pct`, source `esp32`
  - `substrate_temp_c`, metric `substrate_temp_c`, unit `degC`, source `esp32`
  - `substrate_ec_us_cm`, metric `substrate_ec_us_cm`, unit `us/cm`, source `esp32`
  - `substrate_ph`, metric `substrate_ph`, unit `pH`, source `esp32`
- Plant cutover: current `plant.plant_id='a'` in `homebox/main` points `moisture_capability_id` to the RS485 `soil_moisture_pct` capability.

HWD ingest:

- Existing route: `POST /api/ingest/sensors`
- Existing request DTO: `IngestPayload` in `apps/hwd/src/dirt_hwd/api/ingest.py`
- Extend `DeviceDiagnostics` only with RS485 fields emitted by firmware.

Shared services:

- Database-backed `device`/`capability` rows and typed capability metadata declare the RS485 expected wire metrics and freshness-required metrics.
- Code-owned derivation rules remain in shared/HWD source; do not move formulas into database metadata.
- Plant moisture consumers must support both `soil_moisture_raw` plus calibration and direct `soil_moisture_pct`.

External hardware:

- Seeed Studio XIAO ESP32C3.
- Seeed XIAO RS485 expansion board, powered from 12V for runtime.
- DFRobot SEN0604 RS485 4-in-1 substrate probe at Modbus address `0x02`.
- RS485 wiring per `wiki/hardware/rs485-substrate-sensors.md`: sensor brown power, black ground, yellow A, blue B.
- XIAO ESP32C3 external antenna must be installed and placed for RF exposure; do not bury it in the pot, press it against metal, or bundle it tightly with sensor/power wiring.

## Revision Notes

- 2026-06-10: Initial ExecPlan created for Plant A RS485 substrate-node firmware, no-USB runtime diagnostics, database contract, and moisture ownership cutover.
- 2026-06-10: Updated after corrected 5V sensor power restored live Modbus reads at address `0x02`; the plan is now ready for firmware flashing and live ingest validation.
- 2026-06-10: Added official Seeed XIAO ESP32C3 and RS485 expansion board findings for WiFi stability: keep the external antenna installed and well placed, retain Seeed's RS485 pins, avoid USB-serial blocking in firmware, keep WiFi sleep disabled, and rely on WiFi telemetry before changing bus code.
- 2026-06-10: Changed the old Plant A capacitive-node retirement gate from one full light/dark or irrigation-relevant interval to a more aggressive 30-minute stable RS485 ingest window.
- 2026-06-10: Refined the architecture plan so DB-backed device/capability identity plus `expected_wire_metric`/`freshness_required` policy replaces `DEVICE_METRICS` as durable inventory; voice and daily checkpoint policy should be deleted with those agents or kept consumer-local, not promoted into schema.
