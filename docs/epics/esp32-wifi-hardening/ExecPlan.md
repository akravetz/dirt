# ESP32 WiFi Hardening

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

The ESP32-C3 SuperMini plant sensor fleet is repeatedly going offline long enough for Dirt to mark nodes stale or offline. After this change, each ESP32 node should recover from common WiFi failures without a manual power cycle, and Dirt should show enough WiFi health data to decide whether the remaining problem is firmware, RF placement, router behavior, or the SuperMini board design.

The user-visible result is a fleet that posts readings reliably through router hiccups and weak-signal periods. When a node does drop, the operator can inspect the device row, logs, or serial output and see RSSI, reconnect count, driver reset count, and the last ESP32 disconnect reason. That evidence then drives the hardware decision: keep hardened SuperMinis, replace only bad nodes, standardize on SparkFun Pro Micro ESP32-C3, or test ESP32-C6 boards for a future migration.


## Progress

- [x] (2026-05-22) Read `.agents/PLANS.md`, `docs/commands.md`, `docs/database.md`, `docs/observability.md`, `docs/rules/simple-clean-architecture.md`, and `docs/rules/boundary-contracts.md`.
- [x] (2026-05-22) Inspected current plant, reservoir, fan/env, shared WiFi, shared ingest, and HWD ingest code.
- [x] (2026-05-22) Queried local device freshness and watchdog history to confirm recurring offline transitions, especially on `plant-b-node`.
- [x] (2026-05-22) Reviewed current ESP32-C3 WiFi guidance and SuperMini antenna notes.
- [x] (2026-05-22) Wrote this epic and ExecPlan.
- [ ] Implement firmware WiFi state machine and serial diagnostics.
- [ ] Add server-side WiFi telemetry contract and persistence or log projection.
- [ ] Build all firmware profiles and run focused backend tests.
- [ ] OTA rollout to one canary node, then the rest of the fleet after soak.


## Surprises & Discoveries

- Observation: The live nodes look intermittently disconnected, not permanently dead.
  Evidence: A local `device` query on 2026-05-21 around 20:02 MDT showed most ESP32 devices fresh, while `plant-b-node` was stale by about 21 minutes. Several nodes reported multi-day `uptime_ms`, which argues against constant power loss.

- Observation: The watchdog history shows repeated short offline cycles.
  Evidence: `var/logs/device_status/*.jsonl` included repeated `warn -> offline -> ok` transitions on 2026-05-21 and 2026-05-22 UTC for `plant-a-node`, `plant-b-node`, and `plant-c-node`. Fourteen-day reading-gap queries showed max gaps around 18-19 minutes for several ESP32 devices.

- Observation: Current firmware recovery is minimal.
  Evidence: `firmware/common/wifi_client/wifi_client.cpp` calls `WiFi.reconnect()` every 5 seconds when disconnected. It does not register WiFi event callbacks, capture disconnect reason codes, reset the WiFi driver, restart a stuck node, or report RSSI/reconnect counters to the backend.

- Observation: The ESP32-C3 WiFi driver expects application-level disconnect handling.
  Evidence: Espressif's ESP32-C3 WiFi guide says robust WiFi applications need explicit handling for `WIFI_EVENT_STA_DISCONNECTED` and recommends calling `esp_wifi_connect()` on disconnect. It also documents beacon timeout, no-AP-found, auth failure, handshake timeout, and connection failure reason codes.

- Observation: The SuperMini board can make marginal RF worse.
  Evidence: SuperMini hardware notes call out weak WiFi/BLE range from the tiny integrated antenna. CNX Software documented materially improved range after an antenna modification on cheap ESP32-C3 USB-C boards, which supports treating RF quality as a first-class diagnostic input.


## Decision Log

- Decision: Harden firmware before replacing the fleet.
  Rationale: The current evidence shows reconnect gaps and long uptime, not obvious board death. A board swap may reduce RF problems, but every future ESP32-class node still needs robust reconnect, escalation, and telemetry.
  Date/Author: 2026-05-22 / Codex

- Decision: Keep the shared WiFi helper as the single source of firmware WiFi behavior.
  Rationale: Plant, reservoir, fan, and breeding-env firmware already use `firmware/common/wifi_client`. Fixing the shared helper improves the fleet without duplicated per-node reconnect logic.
  Date/Author: 2026-05-22 / Codex

- Decision: Add explicit telemetry fields rather than burying diagnostic state in opaque strings.
  Rationale: The operator needs to compare devices and time windows. Numeric RSSI, reason, reconnect count, and reset count are queryable and can later drive UI or alert thresholds.
  Date/Author: 2026-05-22 / Codex

- Decision: Use source-owned direct cutover for firmware call sites.
  Rationale: The firmware projects are all in this repo. If the helper API changes, update plant, reservoir, fan, and breeding-env call sites directly rather than preserving thin compatibility wrappers.
  Date/Author: 2026-05-22 / Codex


## Outcomes & Retrospective

This plan is not implemented yet. Record rollout evidence here after the canary and fleet soak. The important retrospective question is whether offline transitions decline after firmware hardening. If they do, the SuperMini fleet can likely stay until boards fail physically. If they do not, the remaining evidence should identify weak RSSI, disconnect reason patterns, or hardware-specific failures that justify replacement.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before implementation:

- `docs/commands.md` before running firmware, test, lint, or service commands.
- `docs/database.md` before editing `apps/shared/src/dirt_shared/models/` or running Atlas migrations.
- `docs/observability.md` before adding or changing log streams.
- `docs/rules/simple-clean-architecture.md` before changing architecture or preserving compatibility paths.
- `docs/rules/boundary-contracts.md` before changing the sensor ingest payload or any persisted boundary shape.
- `docs/references/atlas/INDEX.md` before running Atlas migration commands.

Current firmware profiles:

- `firmware/plant_node/src/main.cpp` reads one capacitive soil moisture ADC channel on GPIO3 / ADC1_CH3 and posts `soil_moisture_raw` every 30 seconds. It uses ESP-IDF `adc1_get_raw()` because Arduino `analogRead()` and WiFi were previously unreliable on ESP32-C3.
- `firmware/reservoir_node/src/main.cpp` reads a DFRobot pressure transducer through ADS1115 over I2C on GPIO4/GPIO5 and posts `reservoir_pressure_raw` plus `reservoir_in` every 30 seconds.
- `firmware/fan_controller/src/main.cpp` reads SHT45 over I2C on GPIO4/GPIO5, drives AC Infinity fan PWM on GPIO6/GPIO7, exposes `GET /fan` and `POST /fan` on port 80, uses NVS for fan duty persistence, and posts environment/fan metrics.
- `firmware/common/wifi_client/wifi_client.cpp` is the shared WiFi helper used by all current ESP32 firmware.
- `firmware/common/ingest_client/ingest_client.cpp` builds the JSON ingest envelope with `site_id`, `tent_id`, `zone_id`, `device_id`, `source`, `firmware_version`, `ip`, `uptime_ms`, and `metrics`.
- `apps/hwd/src/dirt_hwd/api/ingest.py` defines the `IngestPayload` Pydantic model for the `/api/ingest/sensors` boundary.
- `apps/shared/src/dirt_shared/services/readings.py` updates `device.last_seen`, `device.ip`, `device.firmware_version`, and `device.uptime_ms` during ingest.
- `apps/hwd/src/dirt_hwd/services/device_watchdog.py` and `apps/hwd/src/dirt_hwd/services/metric_freshness.py` emit offline/stale transitions.

External references that motivate the design:

- Espressif ESP32-C3 WiFi guide: `https://docs.espressif.com/projects/esp-idf/en/v4.3.3/esp32c3/api-guides/wifi.html`
- Espressif ESP32-C3 reason-code guide: `https://docs.espressif.com/projects/esp-idf/en/v4.3.5/esp32c3/api-guides/wifi.html`
- SuperMini board notes: `https://homeding.github.io/boards/esp32c3/super-mini-c3.htm`
- SuperMini antenna range report: `https://www.cnx-software.com/2025/04/09/antenna-hack-more-than-doubles-the-range-of-cheap-esp32-c3-usb-c-boards/`


## Plan of Work

Milestone 1: Capture the current failure baseline.

Run read-only queries and log summaries before editing firmware. Record current per-device `last_seen`, `uptime_ms`, recent offline transition counts, and recent reading gaps. This gives the post-rollout soak a comparison target.

Useful evidence:

    SELECT device_id, ip, firmware_version, last_seen, now() - last_seen AS staleness, uptime_ms
    FROM device
    WHERE controller = 'esp32'
    ORDER BY device_id;

    WITH points AS (
      SELECT d.device_id, sr.ts,
             lag(sr.ts) OVER (PARTITION BY d.device_id ORDER BY sr.ts) AS prev_ts
      FROM sensorreading sr
      JOIN capability c ON c.id = sr.capability_id
      JOIN device d ON d.id = c.device_id
      WHERE d.controller = 'esp32'
        AND sr.ts > now() - interval '14 days'
    )
    SELECT device_id, count(*) AS gaps_over_2m, max(ts - prev_ts) AS max_gap
    FROM points
    WHERE prev_ts IS NOT NULL AND ts - prev_ts > interval '2 minutes'
    GROUP BY device_id
    ORDER BY device_id;

Milestone 2: Replace the shared WiFi helper with a stateful reconnect policy.

Edit `firmware/common/wifi_client/wifi_client.h` and `firmware/common/wifi_client/wifi_client.cpp`.

The helper should own:

- STA mode setup and hostname setup.
- `WiFi.setSleep(false)` for wall-powered nodes.
- WiFi event registration.
- Last disconnect reason.
- Connected timestamp and disconnected-since timestamp.
- Reconnect attempt count.
- Driver reset count.
- Exponential reconnect backoff with a maximum delay.
- WiFi driver reset after a bounded offline window.
- MCU restart after a longer stuck-offline window.
- A read-only snapshot API for telemetry.

Target API shape:

    namespace wifi_client {

    struct Snapshot {
        bool connected;
        int rssi_dbm;
        uint32_t reconnect_count;
        uint32_t driver_reset_count;
        uint8_t last_disconnect_reason;
        uint32_t disconnected_for_ms;
    };

    void begin(const char* ssid, const char* password, const char* hostname);
    void maintain();
    Snapshot snapshot();

    }

Implementation outline:

    void on_wifi_event(WiFiEvent_t event, WiFiEventInfo_t info) {
        if (event == ARDUINO_EVENT_WIFI_STA_GOT_IP) {
            g_last_connected_ms = millis();
            g_disconnected_since_ms = 0;
            g_reconnect_delay_ms = RECONNECT_BASE_MS;
        }

        if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
            g_last_disconnect_reason = info.wifi_sta_disconnected.reason;
            if (g_disconnected_since_ms == 0) {
                g_disconnected_since_ms = millis();
            }
            g_next_reconnect_ms = millis();
        }
    }

    void maintain() {
        if (WiFi.status() == WL_CONNECTED) return;
        if (millis() < g_next_reconnect_ms) return;

        uint32_t offline_for = disconnected_for_ms();
        if (offline_for > WIFI_DRIVER_RESET_AFTER_MS) {
            reset_driver();
        }
        if (offline_for > MCU_RESTART_AFTER_MS) {
            ESP.restart();
        }

        g_reconnect_count++;
        WiFi.begin(g_ssid, g_password);
        g_next_reconnect_ms = millis() + g_reconnect_delay_ms;
        g_reconnect_delay_ms = min(g_reconnect_delay_ms * 2, RECONNECT_MAX_MS);
    }

Use conservative defaults first:

- `RECONNECT_BASE_MS = 5 seconds`
- `RECONNECT_MAX_MS = 60 seconds`
- `WIFI_DRIVER_RESET_AFTER_MS = 5 minutes`
- `MCU_RESTART_AFTER_MS = 15 minutes`

The helper must avoid blocking normal loop work for long periods after setup. OTA and the fan HTTP server should continue to run whenever WiFi is up.

Milestone 3: Directly update firmware call sites.

Update these files to use the new helper API:

- `firmware/plant_node/src/main.cpp`
- `firmware/reservoir_node/src/main.cpp`
- `firmware/fan_controller/src/main.cpp`

For each firmware profile, replace setup-time `wifi_client::connect(...)` with `wifi_client::begin(...)`. Keep per-loop `wifi_client::maintain()`.

Do not leave a compatibility wrapper unless a build constraint proves it is necessary. If the helper keeps the old `connect()` name instead, update this plan's decision log with the reason.

Milestone 4: Add WiFi telemetry to ingest.

Edit `firmware/common/ingest_client.h` and `firmware/common/ingest_client.cpp` so the ingest envelope includes WiFi diagnostics from `wifi_client::snapshot()`.

Proposed payload additions:

- `wifi_rssi_dbm`
- `wifi_reconnect_count`
- `wifi_driver_reset_count`
- `wifi_disconnect_reason`
- `wifi_disconnected_for_ms`

Example JSON shape:

    {
      "site_id": "homebox",
      "tent_id": "main",
      "zone_id": "plant-b",
      "device_id": "plant-b-node",
      "source": "esp32",
      "firmware_version": "0.1.3",
      "ip": "192.168.1.243",
      "uptime_ms": 123456,
      "wifi_rssi_dbm": -78,
      "wifi_reconnect_count": 14,
      "wifi_driver_reset_count": 1,
      "wifi_disconnect_reason": 200,
      "wifi_disconnected_for_ms": 0,
      "metrics": {"soil_moisture_raw": 2711}
    }

If flash/RAM pressure appears, keep numeric fields and skip strings. The server can map reason codes later.

Milestone 5: Update the typed backend ingest boundary.

Because `/api/ingest/sensors` is a process/network boundary, update the Pydantic DTO in `apps/hwd/src/dirt_hwd/api/ingest.py` rather than accepting raw extra fields.

Add optional fields matching the firmware payload:

- `wifi_rssi_dbm: int | None = None`
- `wifi_reconnect_count: int | None = None`
- `wifi_driver_reset_count: int | None = None`
- `wifi_disconnect_reason: int | None = None`
- `wifi_disconnected_for_ms: int | None = None`

Choose the simplest persistence model after inspecting current consumers:

1. Preferred direct model: add nullable columns to `apps/shared/src/dirt_shared/models/device.py` and an Atlas migration. Update `ReadingsService.touch_device()` and `ReadingsService.ingest_reading()` plumbing so the current device row exposes current WiFi health.
2. If first-class columns are too broad for the initial PR, add an `esp32_wifi` observability stream that logs the accepted telemetry on every meaningful transition or count change. Do not silently rely on ignored extra fields.

If using columns, suggested names:

- `wifi_rssi_dbm`
- `wifi_reconnect_count`
- `wifi_driver_reset_count`
- `wifi_disconnect_reason`
- `wifi_disconnected_for_ms`

Add focused tests in `apps/hwd/tests/` and `apps/shared/tests/` proving the ingest boundary accepts the new fields and writes them to the chosen projection.

Milestone 6: Add operator diagnostics.

Expose the WiFi health somewhere easy to inspect. The minimum acceptable implementation is a documented SQL query and log stream. A better implementation extends the existing system/device status API if it already has a device row projection.

Minimum read-only SQL:

    SELECT device_id, last_seen, now() - last_seen AS staleness,
           wifi_rssi_dbm, wifi_reconnect_count, wifi_driver_reset_count,
           wifi_disconnect_reason, wifi_disconnected_for_ms
    FROM device
    WHERE controller = 'esp32'
    ORDER BY device_id;

If adding an API response, read `docs/rules/boundary-contracts.md` first and update a Pydantic response model, not a handwritten raw dictionary.

Milestone 7: Validate firmware builds and backend tests.

Build all firmware profiles that consume the shared WiFi helper:

    cd /home/akcom/code/dirt/firmware/plant_node
    pio run -e plant-a
    pio run -e plant-b
    pio run -e plant-c
    pio run -e plant-d

    cd /home/akcom/code/dirt/firmware/reservoir_node
    pio run -e reservoir

    cd /home/akcom/code/dirt/firmware/fan_controller
    pio run -e fan
    pio run -e breeding-env

Run focused backend tests for any touched Python modules, plus invariants:

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests/test_ingest*.py apps/shared/tests/test_readings_scope.py -q
    uv run pytest apps/tests/invariants/ -q

Before committing implementation work, run:

    scripts/agent-fix

Milestone 8: Canary OTA rollout.

Start with the most problematic plant node, likely `plant-b-node`, unless the current baseline points elsewhere. Flash only one canary first.

    cd /home/akcom/code/dirt/firmware/plant_node
    set -a; source ../../.env; set +a
    pio run -e plant-b-ota -t upload

Observe:

- Serial output if the node is connected by USB.
- `device.last_seen`, `uptime_ms`, and WiFi telemetry fields.
- `var/logs/device_status/YYYY-MM-DD.jsonl`.
- `var/logs/metric_freshness/YYYY-MM-DD.jsonl`.

Acceptance for canary: after a router/AP restart or intentional short outage, the node should return to fresh status without manual power cycling. During a normal overnight soak, offline transitions should decrease compared with the baseline.

Milestone 9: Fleet rollout and hardware decision.

After the canary soaks, OTA the rest of the fleet. At minimum:

- `plant-a-node`
- `plant-b-node`
- `plant-c-node`
- `plant-d-node`
- `reservoir-node`
- `fan-controller`
- `breeding-env-node`

After 3-7 days, compare offline transitions, gap counts, RSSI, and reason-code patterns against the baseline.

Decision criteria:

- If offline transitions largely disappear, keep the SuperMini fleet and treat the previous issue as firmware recovery weakness.
- If only one or two nodes remain bad with poor RSSI or high beacon-timeout counts, replace or reposition those nodes first.
- If many nodes show poor RSSI despite good AP coverage, replace the fleet with a better-vendor ESP32-C3 board such as SparkFun Pro Micro ESP32-C3.
- If future Thread/Zigbee/Matter or battery operation becomes a near-term requirement, prototype one ESP32-C6 node separately before standardizing on it.


## Concrete Steps

Start from the repo root:

    cd /home/akcom/code/dirt

Capture baseline:

    set -a; source .env; set +a
    PGPASSWORD="$DIRT_PG_PASSWORD" psql -h 127.0.0.1 -U dirt -d dirt -P pager=off -c "SELECT device_id, ip, firmware_version, last_seen, now() - last_seen AS staleness, uptime_ms FROM device WHERE controller = 'esp32' ORDER BY device_id;"

Edit firmware:

    $EDITOR firmware/common/wifi_client/wifi_client.h
    $EDITOR firmware/common/wifi_client/wifi_client.cpp
    $EDITOR firmware/common/ingest_client/ingest_client.h
    $EDITOR firmware/common/ingest_client/ingest_client.cpp
    $EDITOR firmware/plant_node/src/main.cpp
    $EDITOR firmware/reservoir_node/src/main.cpp
    $EDITOR firmware/fan_controller/src/main.cpp

If adding persisted DB columns:

    $EDITOR apps/shared/src/dirt_shared/models/device.py
    $EDITOR apps/shared/src/dirt_shared/services/readings.py
    $EDITOR apps/hwd/src/dirt_hwd/api/ingest.py
    atlas migrate diff esp32_wifi_telemetry --env local

Validate:

    cd /home/akcom/code/dirt/firmware/plant_node
    pio run -e plant-a

    cd /home/akcom/code/dirt/firmware/reservoir_node
    pio run -e reservoir

    cd /home/akcom/code/dirt/firmware/fan_controller
    pio run -e fan
    pio run -e breeding-env

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests apps/shared/tests apps/tests/invariants -q

Run formatting/fixes before commit:

    cd /home/akcom/code/dirt
    scripts/agent-fix

Canary upload:

    cd /home/akcom/code/dirt/firmware/plant_node
    set -a; source ../../.env; set +a
    pio run -e plant-b-ota -t upload


## Validation and Acceptance

Firmware acceptance:

- All current firmware profiles build.
- A disconnected node logs a disconnect reason, reconnect attempts, and backoff progression.
- A node offline for more than the configured driver-reset window resets the WiFi driver.
- A node offline for more than the configured MCU-restart window restarts the MCU.
- OTA still works after the changes.
- The fan controller HTTP surface still responds after the changes.

Backend acceptance:

- `POST /api/ingest/sensors` accepts the new WiFi telemetry fields through the Pydantic `IngestPayload`.
- The chosen projection, either `device` columns or `esp32_wifi` logs, shows current RSSI, reconnect count, driver reset count, and last disconnect reason.
- Existing ingest tests and invariants pass.

Operational acceptance:

- A canary node returns to fresh status after a controlled AP/router restart without manual power cycling.
- During a 3-7 day soak, offline transition count and reading gap count are lower than the pre-change baseline, or the remaining failures have actionable RSSI/reason-code evidence.


## Idempotence and Recovery

Firmware builds are safe to repeat. OTA uploads are safe to repeat with the same firmware image.

Atlas migration generation is not idempotent if repeated with different local model state; inspect generated SQL before applying. Take a normal database backup before applying any live schema migration:

    pg_dump dirt > var/db-backups/dirt-$(date +%F)-pre-esp32-wifi-telemetry.sql

If a canary OTA makes a node unreachable, recover by USB flashing the previous known-good environment from the same PlatformIO project. If the fan controller canary fails, prioritize USB recovery because it also owns the fan HTTP control surface and tent SHT45 ingest.

If the new WiFi policy causes rapid reboot loops, increase `MCU_RESTART_AFTER_MS`, disable the restart path temporarily, and rebuild. Do not remove event/reason logging while debugging.

If backend telemetry fields are added but firmware is not rolled out yet, all fields must remain nullable so old firmware keeps ingesting.


## Artifacts and Notes

Current failure evidence from local inspection:

- `plant-b-node` was stale by about 21 minutes in a local query while most peer ESP32 nodes were fresh.
- Recent watchdog logs showed repeated plant-node `warn -> offline -> ok` cycles.
- Fourteen-day gap analysis showed max ESP32 reading gaps around 18-19 minutes for multiple nodes.
- Existing firmware uptime values were multi-day, which makes repeated board power loss less likely than reconnect/RF problems.

Current code excerpts that motivate the change:

    void maintain() {
        uint32_t now = millis();
        if (now - last_maintain_ms < MAINTAIN_INTERVAL_MS) return;
        last_maintain_ms = now;
        if (WiFi.status() == WL_CONNECTED) return;

        Serial.println("[wifi] disconnected - reconnecting");
        WiFi.reconnect();
    }

The hardened behavior should look more like a state machine:

    disconnect event -> record reason -> reconnect now
    reconnect failures -> exponential backoff
    offline too long -> reset WiFi driver
    still offline too long -> restart MCU
    successful ingest -> persist RSSI and counters


## Interfaces and Dependencies

Firmware interfaces:

- `firmware/common/wifi_client/wifi_client.h`
  - `wifi_client::begin(const char*, const char*, const char*)`
  - `wifi_client::maintain()`
  - `wifi_client::snapshot() -> wifi_client::Snapshot`
- `firmware/common/ingest_client/ingest_client.cpp`
  - JSON envelope includes WiFi telemetry fields.

Backend boundary:

- `apps/hwd/src/dirt_hwd/api/ingest.py`
  - `IngestPayload` has optional WiFi telemetry fields.

Persistence or observability:

- Preferred: `apps/shared/src/dirt_shared/models/device.py` nullable WiFi telemetry columns, plus an Atlas migration under `migrations/`.
- Acceptable initial alternative: `apps/shared/src/dirt_shared/observability.py` retention entry for an `esp32_wifi` stream and explicit log events from ingest.

Validation dependencies:

- PlatformIO for firmware builds.
- `uv run pytest` for Python tests.
- Atlas for schema migration generation and apply if persistence columns are used.
- `.env` for database credentials and `PLANT_OTA_PASSWORD` during OTA.

External behavior:

- Nodes continue posting to `POST http://homebox.local:8000/api/ingest/sensors`.
- Nodes continue using mDNS hostnames and ArduinoOTA on port 3232.
- Fan controller continues serving `GET /fan` and `POST /fan` on port 80.


## Revision Notes

- 2026-05-22: Initial ExecPlan created from observed ESP32 offline behavior, firmware inspection, and ESP32-C3/SuperMini WiFi guidance.
