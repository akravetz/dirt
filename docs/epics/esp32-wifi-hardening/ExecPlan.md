# ESP32 WiFi Hardening

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

The ESP32-C3 SuperMini plant sensor fleet is repeatedly going offline long enough for Dirt to mark nodes stale or offline. After this change, each ESP32 node should recover from common WiFi failures without a manual power cycle, and Dirt should show enough WiFi health data to decide whether the remaining problem is firmware, RF placement, router behavior, or the SuperMini board design.

The user-visible result is a fleet that posts readings reliably through router hiccups and weak-signal periods. When a node does drop, the operator can inspect the database-backed device row, the dashboard system table, logs, or serial output and see RSSI, reconnect count, driver reset count, disconnected duration, and the last ESP32 disconnect reason. That evidence then drives the hardware decision: keep hardened SuperMinis, replace only bad nodes, standardize on SparkFun Pro Micro ESP32-C3, or test ESP32-C6 boards for a future migration.


## Progress

- [x] (2026-05-22) Read `.agents/PLANS.md`, `docs/commands.md`, `docs/database.md`, `docs/observability.md`, `docs/rules/simple-clean-architecture.md`, and `docs/rules/boundary-contracts.md`.
- [x] (2026-05-22) Inspected current plant, reservoir, fan/env, shared WiFi, shared ingest, and HWD ingest code.
- [x] (2026-05-22) Queried local device freshness and watchdog history to confirm recurring offline transitions, especially on `plant-b-node`.
- [x] (2026-05-22) Reviewed current ESP32-C3 WiFi guidance and SuperMini antenna notes.
- [x] (2026-05-22) Wrote this epic and ExecPlan.
- [x] (2026-05-22 02:56Z) Implemented shared firmware WiFi state machine, direct `begin()` call-site cutover, and ingest envelope WiFi telemetry.
- [x] (2026-05-22 02:56Z) Added server-side WiFi telemetry fields to the typed ingest boundary, nullable `device` columns, Atlas migration `migrations/20260522024624_esp32_wifi_telemetry.sql`, local API projection, generated contracts, and dashboard table columns.
- [x] (2026-05-22 02:56Z) Built all current firmware profiles and ran focused backend, frontend, e2e, invariant, and fixer validation. Hosted dashboard exposure is deferred until after local canary proof because the immediate rollout workflow is local `device` persistence plus the local dashboard, and adding cloud schema/catalog changes would expand the blast radius before the firmware behavior is proven.
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

- Observation: The documented root firmware test command does not match the current PlatformIO layout.
  Evidence: There is no root `firmware/platformio.ini`; validation used per-project builds in `firmware/plant_node`, `firmware/reservoir_node`, and `firmware/fan_controller`.

- Observation: The plant-node builds still emit the pre-existing ESP-IDF ADC attenuation deprecation warning.
  Evidence: `pio run -e plant-a` through `plant-d` all succeeded, with warnings that `ADC_ATTEN_DB_11` is deprecated and behaves as `ADC_ATTEN_DB_12`.

- Observation: Local Atlas migration lint is unavailable with the installed Atlas CLI license level.
  Evidence: `atlas migrate lint --env local --latest 1` exited with an Atlas Pro requirement message, so the generated nullable-column SQL was reviewed directly instead.


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

- Decision: Persist ESP32 WiFi telemetry as nullable `device` columns, not as a log-only projection.
  Rationale: The operator needs the current WiFi health in normal database queries, API responses, and the web UI. Logs remain useful supporting evidence, but they are not the source of truth for the latest device health.
  Date/Author: 2026-05-22 / Codex

- Decision: Surface WiFi telemetry through the existing device-status/device-catalog paths rather than inventing a separate WiFi diagnostics screen first.
  Rationale: The current operator workflow already checks device rows in the dashboard. Extending `device`, `SystemStatusService`, `/api/system/devices`, and the existing React device tables keeps the change direct and makes the data visible where stale/offline status is already evaluated.
  Date/Author: 2026-05-22 / Codex

- Decision: Use source-owned direct cutover for firmware call sites.
  Rationale: The firmware projects are all in this repo. If the helper API changes, update plant, reservoir, fan, and breeding-env call sites directly rather than preserving thin compatibility wrappers.
  Date/Author: 2026-05-22 / Codex

- Decision: Represent local API WiFi diagnostics as a nested nullable `wifi` object.
  Rationale: The generated Python and TypeScript models support a nested object cleanly, and grouping RSSI, reconnect count, driver reset count, disconnect reason, and disconnected duration keeps WiFi-specific data out of the main device-status namespace.
  Date/Author: 2026-05-22 / Codex

- Decision: Defer hosted dashboard WiFi telemetry for this implementation slice.
  Rationale: The local canary rollout can be proven with firmware serial logs, local `device` columns, `/api/system/devices`, and the local dashboard. Carrying the fields through gateway catalog sync, cloud persistence, and hosted browser contracts is still valuable, but it should follow local proof so cloud migrations and hosted UI changes are not coupled to an unproven firmware policy.
  Date/Author: 2026-05-22 / Codex

- Decision: Use a short canary gate before fleet rollout instead of an overnight soak.
  Rationale: The user prefers moving quickly once the first node proves it can reconnect and keep posting for about ten minutes. Roll out the remaining fleet one at a time after that short gate, while continuing to watch telemetry and device-status logs during the rollout.
  Date/Author: 2026-05-22 / Codex/User


## Outcomes & Retrospective

Code milestones 2 through 7 are implemented and validated locally. Firmware now uses a shared nonblocking WiFi state machine with event-captured disconnect reasons, exponential reconnect backoff, driver reset escalation after 5 minutes offline, MCU restart escalation after 15 minutes offline, and a `Snapshot` telemetry API. All current firmware profiles build after the direct `wifi_client::begin()` cutover.

Local ingest accepts and persists numeric WiFi telemetry on `device`, including quality-rejected heartbeat-only payloads. `/api/system/devices` returns a typed nested `wifi` object, and the local dashboard system table renders RSSI, reconnects, driver resets, and disconnect reason with `--` placeholders for non-ESP32 or missing values. Hosted dashboard exposure is intentionally deferred; do not treat hosted device rows as complete for WiFi diagnostics until a follow-up carries these fields through gateway catalog sync and cloud browser contracts.

The remaining retrospective question still depends on canary and fleet rollout: whether offline transitions decline after firmware hardening. If they do, the SuperMini fleet can likely stay until boards fail physically. If they do not, the persisted RSSI/reason-code evidence should identify weak RF, router behavior, or board-specific failures that justify replacement.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before implementation:

- `docs/commands.md` before running firmware, test, lint, or service commands.
- `docs/database.md` before editing `apps/shared/src/dirt_shared/models/` or running Atlas migrations.
- `docs/observability.md` before adding or changing log streams.
- `docs/rules/simple-clean-architecture.md` before changing architecture or preserving compatibility paths.
- `docs/rules/boundary-contracts.md` before changing the sensor ingest payload or any persisted boundary shape.
- `docs/references/atlas/INDEX.md` before running Atlas migration commands.
- `docs/references/modern-idiomatic-typescript/INDEX.md` and `docs/references/tailwind-v4/INDEX.md` before editing `web-ui/src/`.

Current firmware profiles:

- `firmware/plant_node/src/main.cpp` reads one capacitive soil moisture ADC channel on GPIO3 / ADC1_CH3 and posts `soil_moisture_raw` every 30 seconds. It uses ESP-IDF `adc1_get_raw()` because Arduino `analogRead()` and WiFi were previously unreliable on ESP32-C3.
- `firmware/reservoir_node/src/main.cpp` reads a DFRobot pressure transducer through ADS1115 over I2C on GPIO4/GPIO5 and posts `reservoir_pressure_raw` plus `reservoir_in` every 30 seconds.
- `firmware/fan_controller/src/main.cpp` reads SHT45 over I2C on GPIO4/GPIO5, drives AC Infinity fan PWM on GPIO6/GPIO7, exposes `GET /fan` and `POST /fan` on port 80, uses NVS for fan duty persistence, and posts environment/fan metrics.
- `firmware/common/wifi_client/wifi_client.cpp` is the shared WiFi helper used by all current ESP32 firmware.
- `firmware/common/ingest_client/ingest_client.cpp` builds the JSON ingest envelope with `site_id`, `tent_id`, `zone_id`, `device_id`, `source`, `firmware_version`, `ip`, `uptime_ms`, and `metrics`.
- `apps/hwd/src/dirt_hwd/api/ingest.py` defines the `IngestPayload` Pydantic model for the `/api/ingest/sensors` boundary.
- `apps/shared/src/dirt_shared/services/readings.py` updates `device.last_seen`, `device.ip`, `device.firmware_version`, and `device.uptime_ms` during ingest.
- `apps/shared/src/dirt_shared/services/system_status.py` builds the local `/api/system/devices` rows from `device.last_seen` and device identity rows.
- `apps/web/src/dirt_web/api/system.py` maps `SystemStatusService` rows into the `dirt-contracts` Pydantic `DeviceStatus` response.
- `contracts/webapp-v1.yaml`, `contracts/python/src/dirt_contracts/webapp_v1/models.py`, and `web-ui/src/api-client/generated/schema.ts` define the local SPA device-status contract consumed by `web-ui/src/ui/SystemTable.tsx`.
- Hosted dashboard device rows flow through `apps/gateway/src/dirt_gateway/local.py` -> `dirt_shared.cloud_contract.CatalogDevice` -> `apps/control-plane/src/dirt_control/models/cloud.py:CloudDevice` -> `apps/control-plane/src/dirt_control/api/browser.py:DeviceResponse` -> `web-ui/src/routes/index.tsx:HostedDevicesPanel`. If this epic's rollout must expose WiFi diagnostics on the hosted dashboard too, carry the same nullable fields through that catalog path and regenerate hosted browser types with `scripts/gen-hosted-contract`.
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

Persist the fields as nullable database columns. Do not use a log-only projection for the accepted implementation.

Add nullable columns to `apps/shared/src/dirt_shared/models/device.py` and an Atlas migration. Update `ReadingsService.touch_device()` and `ReadingsService.ingest_reading()` plumbing so every accepted heartbeat can update the current device row, including payloads whose sensor metrics were rejected by quality filters.

Use these column names:

- `wifi_rssi_dbm`
- `wifi_reconnect_count`
- `wifi_driver_reset_count`
- `wifi_disconnect_reason`
- `wifi_disconnected_for_ms`

Add focused tests in `apps/hwd/tests/` and `apps/shared/tests/` proving the ingest boundary accepts the new fields and writes them to the `device` row. Update any test fixture device rows that need the new nullable attributes, but do not edit `apps/tests/invariants/`.

Milestone 6: Add database-backed operator diagnostics to the web UI.

Expose WiFi health from the persisted `device` columns in the existing operator surfaces. This milestone is not complete if the values are only present in firmware serial output, JSON logs, or ignored request fields.

First, keep the database inspection path obvious. This query should work after the migration and after any ESP32 has posted a payload with WiFi telemetry:

    SELECT device_id, last_seen, now() - last_seen AS staleness,
           wifi_rssi_dbm, wifi_reconnect_count, wifi_driver_reset_count,
           wifi_disconnect_reason, wifi_disconnected_for_ms
    FROM device
    WHERE controller = 'esp32'
    ORDER BY device_id;

Then expose the same current values through the local web API and dashboard:

- Extend the internal `DeviceStatus` dataclass in `apps/shared/src/dirt_shared/services/system_status.py` with nullable `wifi_rssi_dbm`, `wifi_reconnect_count`, `wifi_driver_reset_count`, `wifi_disconnect_reason`, and `wifi_disconnected_for_ms`.
- Extend `_ScopedDevice` and `_status_devices()` in `SystemStatusService` to select those columns from `Device` and copy them into heartbeat statuses for ESP32-backed rows. Leave non-ESP32 camera, voice, and Govee rows with `None` values.
- Extend `contracts/webapp-v1.yaml` `DeviceStatus` with a nullable `wifi` object, or with the five nullable top-level fields if that is simpler for generated-model compatibility. Prefer a nested object if the generator cleanly supports it because it keeps WiFi-specific diagnostics grouped.
- Regenerate `contracts/python/src/dirt_contracts/webapp_v1/models.py` and `web-ui/src/api-client/generated/schema.ts` from `contracts/webapp-v1.yaml`; do not hand-author a divergent TypeScript interface in `web-ui`.
- Update `apps/web/src/dirt_web/api/system.py` to populate the Pydantic response model from the service result.
- Update `web-ui/src/ui/SystemTable.tsx` to add compact WiFi columns for RSSI, reconnects, driver resets, and reason code. Render a restrained placeholder such as `--` when the value is `null`, and keep status as the primary quick-scan column.
- Update `web-ui/tests/e2e/dashboard-system-table.spec.ts` so the dashboard test asserts the WiFi columns render from `/api/system/devices` when present and do not break rows without WiFi data.

If hosted web UI exposure is in scope for the implementation PR, carry the same fields through the hosted catalog path instead of adding a local-only special case:

- Extend `dirt_shared.cloud_contract.CatalogDevice` with the same nullable WiFi fields.
- Extend `apps/gateway/src/dirt_gateway/local.py` to copy local `Device` WiFi columns into catalog payloads.
- Add nullable columns to `apps/control-plane/src/dirt_control/models/cloud.py:CloudDevice` with a cloud Atlas migration.
- Extend `apps/control-plane/src/dirt_control/api/gateway.py` catalog upsert and `apps/control-plane/src/dirt_control/api/browser.py:DeviceResponse`.
- Run `scripts/gen-hosted-contract` and update `web-ui/src/routes/index.tsx:HostedDevicesPanel` to show the same compact diagnostics for hosted device rows.

If hosted exposure is deferred, record that explicitly in `Progress` and `Outcomes & Retrospective` with the reason. Do not silently leave the hosted dashboard looking complete while only the local dashboard has WiFi diagnostics.

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

Run focused backend and frontend checks for touched modules, plus invariants:

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests/test_ingest*.py apps/shared/tests/test_readings_scope.py -q
    uv run pytest apps/web/tests/test_system_devices_endpoint.py -q
    uv run pytest apps/tests/invariants/ -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui test

Before committing implementation work, run:

    make fix

Milestone 8: Canary OTA rollout.

Start with the most problematic plant node, likely `plant-b-node`, unless the current baseline points elsewhere. Flash only one canary first.

    cd /home/akcom/code/dirt/firmware/plant_node
    set -a; source ../../.env; set +a
    pio run -e plant-b-ota -t upload

Observe for about ten minutes:

- Serial output if the node is connected by USB.
- `device.last_seen`, `uptime_ms`, and WiFi telemetry fields.
- `var/logs/device_status/YYYY-MM-DD.jsonl`.
- `var/logs/metric_freshness/YYYY-MM-DD.jsonl`.

Acceptance for canary: after the flash, the node should stay fresh and continue posting for about ten minutes, with populated WiFi telemetry fields. If a router/AP restart or intentional short outage is practical, the node should return to fresh status without manual power cycling. If the ten-minute gate looks good, proceed to the remaining fleet one node at a time rather than waiting overnight.

Milestone 9: Fleet rollout and hardware decision.

After the ten-minute canary gate passes, OTA the rest of the fleet one node at a time. At minimum:

- `plant-a-node`
- `plant-b-node`
- `plant-c-node`
- `plant-d-node`
- `reservoir-node`
- `fan-controller`
- `breeding-env-node`

After rollout, keep watching device telemetry during the session, then compare offline transitions, gap counts, RSSI, and reason-code patterns against the baseline over the next 3-7 days.

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

Add persisted DB columns:

    $EDITOR apps/shared/src/dirt_shared/models/device.py
    $EDITOR apps/shared/src/dirt_shared/services/readings.py
    $EDITOR apps/hwd/src/dirt_hwd/api/ingest.py
    atlas migrate diff esp32_wifi_telemetry --env local

Add local dashboard projection:

    $EDITOR apps/shared/src/dirt_shared/services/system_status.py
    $EDITOR apps/web/src/dirt_web/api/system.py
    $EDITOR contracts/webapp-v1.yaml
    uv run datamodel-codegen --input contracts/webapp-v1.yaml --input-file-type openapi --output contracts/python/src/dirt_contracts/webapp_v1/models.py
    pnpm --dir web-ui exec openapi-typescript ../contracts/webapp-v1.yaml -o src/api-client/generated/schema.ts
    pnpm --dir web-ui exec biome check --write src/api-client/generated/schema.ts
    $EDITOR web-ui/src/ui/SystemTable.tsx
    $EDITOR web-ui/tests/e2e/dashboard-system-table.spec.ts

If hosted dashboard exposure is included:

    $EDITOR apps/shared/src/dirt_shared/cloud_contract.py
    $EDITOR apps/gateway/src/dirt_gateway/local.py
    $EDITOR apps/control-plane/src/dirt_control/models/cloud.py
    $EDITOR apps/control-plane/src/dirt_control/api/gateway.py
    $EDITOR apps/control-plane/src/dirt_control/api/browser.py
    atlas migrate diff cloud_esp32_wifi_telemetry --env cloud
    scripts/gen-hosted-contract
    $EDITOR web-ui/src/routes/index.tsx

Validate:

    cd /home/akcom/code/dirt/firmware/plant_node
    pio run -e plant-a

    cd /home/akcom/code/dirt/firmware/reservoir_node
    pio run -e reservoir

    cd /home/akcom/code/dirt/firmware/fan_controller
    pio run -e fan
    pio run -e breeding-env

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests apps/shared/tests apps/web/tests/test_system_devices_endpoint.py apps/tests/invariants -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui test

Run formatting/fixes before commit:

    cd /home/akcom/code/dirt
    make fix

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
- The `device` table has nullable WiFi telemetry columns, and ingest updates them on both normal sensor inserts and heartbeat-only accepted payloads.
- `/api/system/devices` returns the current WiFi values for ESP32 rows through a typed Pydantic response model.
- Existing ingest tests and invariants pass.

Web UI acceptance:

- The local dashboard system table renders RSSI, reconnect count, driver reset count, and last disconnect reason for ESP32 rows using the generated local API type.
- Rows with `null` WiFi values still render cleanly with placeholders and no layout jump.
- If hosted exposure is included, the hosted dashboard device table renders the same diagnostics after one gateway catalog sync and the hosted browser types are regenerated from `scripts/gen-hosted-contract`.

Operational acceptance:

- A canary node stays fresh and posts WiFi telemetry for about ten minutes after OTA.
- If a controlled AP/router restart is practical, the canary returns to fresh status without manual power cycling.
- During and after one-at-a-time fleet rollout, nodes keep posting current WiFi telemetry.
- Over the next 3-7 days, offline transition count and reading gap count are lower than the pre-change baseline, or the remaining failures have actionable RSSI/reason-code evidence.


## Idempotence and Recovery

Firmware builds are safe to repeat. OTA uploads are safe to repeat with the same firmware image.

Atlas migration generation is not idempotent if repeated with different local model state; inspect generated SQL before applying. Take a normal database backup before applying any live schema migration:

    pg_dump dirt > var/db-backups/dirt-$(date +%F)-pre-esp32-wifi-telemetry.sql

If a canary OTA makes a node unreachable, recover by USB flashing the previous known-good environment from the same PlatformIO project. If the fan controller canary fails, prioritize USB recovery because it also owns the fan HTTP control surface and tent SHT45 ingest.

If the new WiFi policy causes rapid reboot loops, increase `MCU_RESTART_AFTER_MS`, disable the restart path temporarily, and rebuild. Do not remove event/reason logging while debugging.

If backend telemetry fields are added but firmware is not rolled out yet, all local and hosted database/API/UI fields must remain nullable so old firmware keeps ingesting and dashboard rows without WiFi diagnostics still render.


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

Validation evidence from 2026-05-22 implementation:

- `pio run -e plant-a`, `plant-b`, `plant-c`, and `plant-d` passed from `firmware/plant_node`.
- `pio run -e reservoir` passed from `firmware/reservoir_node`.
- `pio run -e fan` and `pio run -e breeding-env` passed from `firmware/fan_controller`.
- `uv run pytest apps/hwd/tests/test_ingest*.py apps/shared/tests/test_readings_scope.py apps/shared/tests/test_system_status_scope.py apps/web/tests/test_system_devices_endpoint.py apps/tests/invariants/ -q` passed: 152 tests.
- `pnpm --dir web-ui typecheck` passed.
- `pnpm --dir web-ui test` passed with the current project state of no Vitest files.
- `pnpm --dir web-ui test:e2e -- tests/e2e/dashboard-system-table.spec.ts` passed once the expected Vite dev server was running on the worktree port.
- `make fix` passed after implementation.
- `atlas migrate diff esp32_wifi_telemetry --env local` generated `migrations/20260522024624_esp32_wifi_telemetry.sql`; the migration has not been applied to the live local database in this coding pass.


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

Persistence:

- `apps/shared/src/dirt_shared/models/device.py` nullable WiFi telemetry columns, plus an Atlas migration under `migrations/`.
- `apps/shared/src/dirt_shared/services/readings.py` updates those columns during `touch_device()` and sensor ingest.

Local web UI interfaces:

- `apps/shared/src/dirt_shared/services/system_status.py` `DeviceStatus` includes `wifi: WifiTelemetry | None`, and `WifiTelemetry` groups nullable RSSI, reconnect count, driver reset count, disconnect reason, and disconnected duration.
- `apps/web/src/dirt_web/api/system.py` maps the diagnostics into the typed `/api/system/devices` response.
- `contracts/webapp-v1.yaml`, `contracts/python/src/dirt_contracts/webapp_v1/models.py`, and `web-ui/src/api-client/generated/schema.ts` include the WiFi diagnostics shape.
- `web-ui/src/ui/SystemTable.tsx` renders compact WiFi diagnostics for the existing dashboard system table.

Optional hosted web UI interfaces, deferred from this implementation slice:

- `dirt_shared.cloud_contract.CatalogDevice` carries nullable WiFi diagnostics.
- `apps/control-plane/src/dirt_control/models/cloud.py:CloudDevice` persists nullable WiFi diagnostics in the cloud database.
- `apps/control-plane/src/dirt_control/api/browser.py:DeviceResponse` and generated `web-ui/src/api-client/generated/hosted-schema.ts` expose those diagnostics.

Validation dependencies:

- PlatformIO for firmware builds.
- `uv run pytest` for Python tests.
- Atlas for schema migration generation and apply.
- `.env` for database credentials and `PLANT_OTA_PASSWORD` during OTA.

External behavior:

- Nodes continue posting to `POST http://homebox.local:8000/api/ingest/sensors`.
- Nodes continue using mDNS hostnames and ArduinoOTA on port 3232.
- Fan controller continues serving `GET /fan` and `POST /fan` on port 80.


## Revision Notes

- 2026-05-22: Initial ExecPlan created from observed ESP32 offline behavior, firmware inspection, and ESP32-C3/SuperMini WiFi guidance.
- 2026-05-22: Solidified Milestone 6 so WiFi telemetry must persist in `device` database columns and flow into the web UI device tables; log-only diagnostics are no longer an acceptable endpoint.
- 2026-05-22: Implemented and validated local firmware/backend/dashboard code milestones; recorded hosted dashboard telemetry as deferred until after local canary proof.
