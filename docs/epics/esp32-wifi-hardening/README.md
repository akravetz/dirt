# Epic: ESP32 WiFi Hardening

Status: planning
Priority: high
Created: 2026-05-22

## Goal

Make the ESP32-C3 sensor fleet resilient to WiFi drops and observable enough to decide whether the SuperMini hardware is the real failure point. The first goal is not a board replacement; it is firmware that reconnects predictably, escalates from reconnect to WiFi-driver reset to MCU restart, and reports RSSI and disconnect reasons so hardware decisions are based on evidence.

## Scope

- Shared firmware WiFi state machine for all current ESP32 nodes.
- Disconnect reason, reconnect, driver-reset, uptime, and RSSI telemetry.
- Optional first-class backend persistence for current WiFi health fields on `device`.
- Focused watchdog/logging updates so offline events can be correlated with firmware WiFi state.
- PlatformIO build validation for plant, reservoir, fan, and breeding-env firmware profiles.
- OTA rollout procedure and post-rollout soak criteria.

## Acceptance Criteria

- A node that loses WiFi attempts reconnect promptly, backs off, resets the WiFi driver after a bounded offline window, and restarts the MCU after a longer stuck-offline window.
- Every ESP32 ingest payload includes enough WiFi telemetry to diagnose weak RF, beacon loss, handshake/auth failures, and reconnect churn.
- The local database or logs expose per-device RSSI, reconnect count, last disconnect reason, and driver reset count.
- Existing plant, reservoir, fan, and breeding-env firmware still build.
- A controlled AP restart or SSID outage produces a visible reconnect sequence and the node returns to fresh status without manual power cycling.
- A multi-day soak shows whether offline transitions drop enough to keep the SuperMini fleet, or whether remaining failures point to board/antenna replacement.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:esp32-wifi-hardening"`

## ExecPlan

Implementation plan: `docs/epics/esp32-wifi-hardening/ExecPlan.md`
