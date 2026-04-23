---
title: "Tent Sensor + Transport Swap: BME280 on Arduino Nano → SHT45 on ESP32-C3"
type: decision
sources: []
related:
  - wiki/decisions/2026-04-20-bme280-sensor-swap.md
  - wiki/decisions/2026-04-12-distributed-sensor-architecture.md
  - wiki/decisions/2026-04-18-vpd-targeting.md
  - wiki/decisions/2026-04-19-lights-off-aware-humidifier.md
  - wiki/hardware/esp32-plant-nodes.md
  - wiki/hardware/humidifier-control.md
  - wiki/environment/humidity.md
created: 2026-04-22
updated: 2026-04-22
---

# Decision: Replace Tent-Hub BME280/Arduino with SHT45/ESP32-C3

**Date:** 2026-04-22
**Status:** Accepted — hardware bring-up complete (via revision below). SHT45 integrated onto the ESP32-C3 fan-controller board rather than a dedicated tent_node ESP32; SHT45 begin + first read validated on the combined board the same day.
**Revision (2026-04-22, evening):** the original plan of a standalone `tent_node` ESP32 inside the tent is superseded by the **combined fan-controller + tent-sensor board** (see [`hardware/ac-infinity-fan-control.md`](../hardware/ac-infinity-fan-control.md)). Rationale: the 7 ft USB-C cable from the Cloudline fan lets the ESP32 sit on the tent floor, putting it in the same physical domain a tent sensor would want anyway; combining saves one board, one power feed, one WiFi association, one OTA target. No pin contention (fan driver: GPIO 6/7; SHT45: GPIO 4/5). Wiring specifics and combined firmware now live in the fan-control hardware page. The standalone `firmware/tent_node/` PIO project is obsolete on disk and slated for deletion after the combined firmware has soaked.
**Supersedes:** the Arduino Nano + USB-serial tent-hub topology from [2026-04-12 distributed sensor architecture](2026-04-12-distributed-sensor-architecture.md) and the BME280 sensor choice from [2026-04-20 BME280 swap](2026-04-20-bme280-sensor-swap.md). Two days ago we swapped the *sensor element* on the Arduino hub. Today we are swapping *both the sensor and the host board* — the Arduino goes away entirely.

## Context

Two overlapping problems led here:

1. **BME280 stuck-state, recurring.** First instance logged 2026-04-20 17:36 MDT (`humidifier-control.md` Known Issues). The sensor returns the same values for long stretches and only recovers after a `dirt-hwd` restart. This is a software/driver-level lockup rather than a hardware fault, but it makes the humidifier failsafe (stale-sensor forced OFF) fire on a working sensor — defeating the control loop without any user-visible signal beyond overnight VPD regression.
2. **Transport asymmetry.** The four per-plant nodes all post to `/api/ingest/sensors` over WiFi (see [ESP32-C3 plant nodes](../hardware/esp32-plant-nodes.md)). The tent hub is the last sensor still riding a USB-serial tether to the host, parsed by `apps/hwd/src/dirt_hwd/services/serial_reader.py`, with a udev rule pinning `/dev/ttyArduino` by hardware ID. Two ingest paths means two failure modes, two parsers, two pieces of hardware to track. The Arduino also can't be OTA-reflashed.

The SHT45 breakout (Adafruit 5665) arrived with a PTFE cap, which is the differentiator over SHT31/SHT35 for this specific environment: the sensor sits inside a humidified tent where direct mist exposure from the Raydrop happens. The PTFE cap is a hydrophobic filter that passes water vapor but blocks droplets — directly relevant to the failure mode we've already seen with the DHT22 and suspect with the BME280.

## Decision

Two entangled changes, committed as one transition:

1. **Sensor: BME280 → Sensirion SHT45 + PTFE cap** (Adafruit product 5665, I²C addr `0x44`). High-precision mode (~10 ms per read, ±0.1°C / ±1.0% RH). On-die heater available but left off by default; future work to pulse it once/hour against condensation if RH pins near 100%.
2. **Host board: Arduino Nano (USB serial) → ESP32-C3 SuperMini (WiFi + HTTP ingest)**, same firmware posture as the four plant nodes. mDNS hostname `tent-node.local`, `source=esp32` in `sensorreading`, location remains `tent`, metrics `{temperature_c, humidity_pct}`.

Wiring: SHT45 VIN/GND to 3V3/GND; SDA on **GPIO4**, SCL on **GPIO5**. GPIO8/9 is the C3's nominal I²C default but collides with the SuperMini's onboard LED + BOOT button strapping pins — GPIO4/5 is the documented alternate path. The JTAG-vs-ADC warning that shaped the plant-node pinout does not apply to I²C (JTAG only crushes passive reads; actively-driven digital I/O is fine).

Firmware restructure: three peer PlatformIO projects (`firmware/plant_node/`, `firmware/tent_node/`, and a new `firmware/common/` shared lib tree with `wifi_client`, `ota`, `ingest_client`). Each node project consumes `common/` via `lib_extra_dirs = ../common`. Both `main.cpp`s are now thin sensor-specific orchestrators.

### What *doesn't* change

- **Ingest schema.** `sensorreading` columns and metric names are identical; the only diff is `source` = `esp32` instead of `arduino` for new tent rows.
- **Humidifier control loop.** Setpoint (`STAGE_TARGETS` upper edge), 0.1 kPa deadband, lights-off feedforward, failsafe (stale-sensor forced OFF). The loop reads VPD from the DB and is sensor-agnostic.
- **Location label.** Still `tent` — same `SensorLocation` enum value. No schema migration.
- **Plant-node firmware behavior.** Plant nodes were refactored to use the new shared libs but function identically; verified by clean compile of all four envs.

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Keep Arduino + swap sensor only (BME280→SHT45) | Addresses the sensor but leaves the transport asymmetry and the serial-reader/udev/Nano-flash toolchain. Half the win for most of the work. |
| Keep BME280, harden the stuck-state recovery (aggressive reinit, watchdog) | Treats a symptom; doesn't close the transport-asymmetry gap or unlock OTA. The SHT45 is already in hand. |
| SHT31 / SHT35 (no PTFE cap) | Same Sensirion accuracy class, cheaper, but no cap. The cap is the specific reason we picked the 5665 — this sensor lives in a mist-exposed environment where past sensor failures correlate with moisture ingress. |
| AHT20 | No pressure channel, no PTFE-capped variant available. |
| Replace tent hub but keep Arduino Nano with a new sensor | The Nano + serial + udev machinery is the cruft we're removing; keeping it would defeat the transport half of the decision. |

## Consequences

- **One fewer ingest path.** After cutover, `dirt-hwd` drops `serial_reader.py`, the `/dev/ttyArduino` udev rule, and the `dirt-hwd.service` `ExecStartPre` that asserts the symlink. `SensorSource.ARDUINO` stays in the enum for historical rows; may be retired in a later Atlas migration.
- **OTA reflash on the tent node.** Future firmware changes to the tent sensor no longer require physically removing a USB cable. mDNS: `tent-node.local:3232`.
- **Barometric pressure channel goes away.** BME280 emitted pressure as a free side effect; SHT45 is temp+RH only. Nothing in any controller uses pressure, so the loss is cosmetic — if we ever want it back, add a BMP280/BMP390 on the same I²C bus of the tent ESP32.
- **Fleet is now 5× ESP32-C3 SuperMinis.** Same board, same toolchain, same OTA model. Uniform operational surface.
- **Firmware tree loses the legacy Arduino project.** `firmware/src/`, `firmware/lib/sensor_protocol/`, and `firmware/platformio.ini` are kept during cutover and deleted once the tent node is proven. They are no longer the canonical tent-hub firmware as of this decision.
- **Recurring BME280 stuck-state issue moots itself.** Different sensor, different driver path — the specific failure mode documented in `hardware/humidifier-control.md` Known Issues #1 cannot recur. If SHT45 develops its own stuck-state pattern we'll catch it with the same detection cue (flatline RH against lights cycle).

## Rollout

1. ✅ Firmware written + compile-verified (2026-04-22). `firmware/tent_node/` + `firmware/common/`; plant-node refactored to shared libs, all four envs still build.
2. ⏳ User solders SHT45 + PTFE cap to a spare ESP32-C3 SuperMini, USB-flashes with `pio run -e tent -t upload`.
3. ⏳ Place tent node inside the tent alongside the Arduino Nano + BME280. Run both for ≥24h; cross-check `sensorreading.source = 'arduino'` vs `'esp32'` rows at the `tent` location.
4. ⏳ Cut over: unplug Arduino, stop+disable the serial-reader code path, remove udev rule + `ExecStartPre`, delete `firmware/src/` + `firmware/lib/sensor_protocol/` + `firmware/platformio.ini`.
5. ⏳ Update `hardware/humidifier-control.md` Known Issues #1 → resolved-by-transition; create `hardware/tent-node.md` at same level as `hardware/esp32-plant-nodes.md`; flip this decision's status to "Deployed".

## Not in Scope

- **Resurrecting barometric pressure.** Separate BMP-family sensor decision if/when it becomes useful.
- **Adding a room-context (outside-tent) temp/RH sensor.** Still a future item, tracked in [multi-actuator-environment-control](../concepts/multi-actuator-environment-control.md).
- **Retiring `SensorSource.ARDUINO`.** Historical rows keep that source label; enum cleanup is cheap but deferred until we have a reason to touch the schema.
- **SHT45 heater schedule.** Deferred until we observe actual condensation-pinned readings; noted as a TODO in `firmware/tent_node/src/main.cpp`.
