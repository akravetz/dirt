---
title: "Tent-Hub Temperature/Humidity Sensor Swap: DHT22 → BME280"
type: decision
sources: []
related:
  - wiki/decisions/2026-04-12-distributed-sensor-architecture.md
  - wiki/decisions/2026-04-14-humidifier-relay-control.md
  - wiki/decisions/2026-04-17-humidifier-kasa-ep10.md
  - wiki/decisions/2026-04-18-vpd-targeting.md
  - wiki/decisions/2026-04-19-lights-off-aware-humidifier.md
  - wiki/hardware/humidifier-control.md
  - wiki/environment/humidity.md
created: 2026-04-20
updated: 2026-04-20
---

# Decision: Swap Tent-Hub Temp/RH Sensor from DHT22 to BME280

**Date:** 2026-04-20 (sensor physically deployed ~2026-04-13)
**Status:** Accepted — deployed
**Supersedes:** the DHT22 sensor choice baked into [2026-04-12 distributed sensor architecture](2026-04-12-distributed-sensor-architecture.md) and referenced by every downstream humidifier-control decision. The tent-hub topology (Arduino Nano outside the tent → USB serial → host) is unchanged; only the temp/RH sensor element is replaced.

## Context

Two problems with the original DHT22:

1. **Hardware failure.** The deployed DHT22 began returning stuck / invalid readings on the Arduino Nano tent-hub. Failsafe kicked in and forced the humidifier OFF on stale-sensor reason, but the VPD control loop was unusable until a replacement sensor was in.
2. **Accuracy headroom.** Even working, DHT22 is a 1-wire consumer-grade part with noticeable cal drift over months. With VPD (not RH) as the control-loop setpoint, temperature error compounds into VPD error — a 0.5°C bias at 70°F/60% RH shifts computed VPD by ~0.03 kPa. We want the sensor noise floor to stay well under the 0.1 kPa deadband for the life of the grow, not just fresh out of the box.

## Decision

Replace the DHT22 on the Arduino Nano tent-hub with a **Bosch BME280** (I²C, address `0x76`). The tent-hub firmware (`firmware/src/main.cpp` + `firmware/src/config.h`) now reads the BME280 over I²C and publishes temp / RH / pressure over USB serial to `dirt-hwd` at the existing 10-second cadence.

Pressure is a free side effect of the BME280 and is ingested alongside temp/RH. It is not currently used by any control loop but is available for altitude-compensation and barometric-trend observation if we ever want it.

### What *didn't* change

- **Tent-hub topology.** Arduino Nano outside the tent, USB serial to the host, still the ingest path.
- **Ingest model.** `sensorreading` columns (`temperature_f`, `humidity_pct`, `vpd_kpa`) are unchanged; BME280 values land in the same columns via the same serial-reader parser.
- **Humidifier control loop.** Setpoint (`STAGE_TARGETS` upper edge), deadband (0.1 kPa), feedforward (pre-lights-off prep + lights-off offset), and failsafes (stale-sensor forced OFF) all unchanged. The loop is sensor-agnostic — it reads VPD from the DB.
- **Deadband width.** Kept at 0.1 kPa. BME280 typical accuracy is tighter than DHT22 (±0.5°C / ±3% RH typical vs DHT22's ±0.5°C / ±2% RH nameplate) and, more importantly, has much less drift — so 0.1 kPa is more conservative than it was before, which is fine. Shrinking it would trade a tiny duty-cycle improvement for more relay cycles; not worth it.

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Replace with another DHT22 | Same drift / reliability profile — we'd be back here in 6 months. |
| SHT31 / SHT35 (Sensirion I²C) | Tighter RH spec than BME280, but ~3× the BOM cost and no pressure channel; accuracy already exceeds control-loop needs with BME280. |
| AHT20 | Cheap but no pressure; BME280 is the same footprint class with one extra useful channel. |
| Keep DHT22, add a second sensor for voting | Over-engineering. Two cheap sensors ≠ one reliable sensor. |

## Consequences

- **Humidifier control-loop noise floor drops.** Tighter temp/RH → tighter derived VPD. The 0.1 kPa deadband is now a more conservative margin than before rather than exactly at the noise floor. No retuning required.
- **Failsafe behaviour unchanged.** If I²C reads fail for > `humidifier_failsafe_stale_seconds` (5 min), the humidifier forces OFF on `failsafe_stale_sensor` — same code path as before.
- **Firmware addr pinned to `0x76`.** The BME280 module ships with SDO tied low → `0x76`. Pulling SDO high selects `0x77`; if a module arrives pre-configured that way, the `BME280_ADDRESS` macro in `firmware/src/config.h` is the single knob.
- **Barometric pressure is now available** as a nice-to-have signal for future weather-correlation or altitude work. Not wired into any loop.
- **Historical decision pages keep their DHT22 references** — those decisions were real at the time and the rationale (deadband sizing, rejecting derivative control on sensor noise, etc.) is still sound under BME280. Only current-state operational pages (`hardware/humidifier-control.md`, `environment/humidity.md`, `overview.md`, `index.md`) have been updated to name BME280.

## Not in Scope

- **Second BME280 for room (makeup-air) context.** Still a future item — see [concepts/multi-actuator-environment-control.md](../concepts/multi-actuator-environment-control.md).
- **Using pressure as a control input.** Recorded only; no controller depends on it.
- **Retuning the humidifier deadband.** Possible future optimization once we have enough BME280 drift data to argue for a smaller value.
