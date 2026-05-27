# Epic: Seeed XIAO ESP32-C3 Fleet Migration

Status: planning
Priority: high
Created: 2026-05-27

## Goal

Replace the current ESP32-C3 SuperMini grow-monitoring fleet with Seeed Studio XIAO ESP32-C3 boards while preserving the existing device identities, ingest behavior, OTA workflow, and simple firmware ownership model.

## Scope

- Update firmware build targets from the generic ESP32-C3 DevKitM/SuperMini posture to the Seeed XIAO ESP32-C3 board target.
- Keep the existing chip-GPIO contract unless canary testing proves a XIAO board-level conflict.
- Produce wiring documentation for plant, reservoir, fan, and breeding environment nodes using XIAO silkscreen labels.
- Validate one XIAO canary on USB, then migrate the deployed fleet one node at a time.
- Update the wiki hardware pages after the successful cutover.

## Acceptance Criteria

- Every ESP32 firmware profile builds for `seeed_xiao_esp32c3`.
- A USB-connected XIAO canary boots, joins WiFi, advertises mDNS, accepts OTA, and posts to `/api/ingest/sensors`.
- Plant moisture, reservoir ADS1115, SHT45, and fan MOSFET pins are validated on XIAO hardware before their deployed node is swapped.
- The wiki records the XIAO pin map, migration status, and any board-specific quirks discovered during rollout.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:seeed-xiao-esp32c3-fleet-migration"`
