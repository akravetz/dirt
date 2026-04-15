---
title: "Hardware — ESP32-C3 Per-Plant Nodes"
type: hardware
sources: []
related: [wiki/decisions/2026-04-12-distributed-sensor-architecture.md, wiki/decisions/2026-04-14-esp32-c3-gpio3-adc.md, wiki/decisions/2026-04-14-server-side-auto-calibration.md, wiki/concepts/capacitive-soil-moisture.md]
created: 2026-04-14
updated: 2026-04-14
---

# ESP32-C3 Per-Plant Nodes

One wireless sensor node per plant (A/B/C/D) inside the tent, each reading a capacitive soil moisture sensor and POSTing JSON to the dirt backend over WiFi.

## Deployment Status

| Node | Board | Sensor | Status |
|------|-------|--------|--------|
| plant-a | ESP32-C3 SuperMini | Capacitive v1.2 | ✅ **Live 2026-04-14** |
| plant-b | (spare available) | — | ⏳ Waiting on more working sensors |
| plant-c | (spare available) | — | ⏳ Waiting on more working sensors |
| plant-d | (spare available) | — | ⏳ Waiting on more working sensors |

**Sensor supply issue:** 2 of 5 sensors from the current Amazon pack (B0BTHL6M19) survived; 3 are dead (AOUT stuck at 0V despite VCC being good). Need a second pack before plants b/c/d can deploy.

## Hardware

- **Board:** ESP32-C3 SuperMini (clone, via Amazon). RISC-V single-core, WiFi, BLE 5.0, native USB-CDC on GPIO18/19 (enumerates as `/dev/ttyACM*`).
- **Sensor:** Capacitive Analog Soil Moisture Sensor v1.2 (555-timer based). See [capacitive soil moisture concept](../concepts/capacitive-soil-moisture.md).
- **Power:** USB-C wall power (not battery — decision stands from the distributed sensor architecture; see also the 2026-04-14 discussion on why battery was re-evaluated and declined).

## Wiring

```
Sensor VCC  →  board "3V3"   (NOT 5V — v1.2 at 5V can output >3.3V on AOUT, outside the ESP32 ADC range)
Sensor GND  →  board "GND"
Sensor AOUT →  board "3"  (chip GPIO3 / ADC1_CH3)
```

### Do NOT use GPIO4

GPIO4–GPIO7 on the ESP32-C3 are JTAG pins (MTMS/MTDI/MTCK/MTDO). When WiFi or BT is active the JTAG peripheral drives these pins, crushing any ADC reading on them to ~0. Empirically confirmed 2026-04-14: GPIO4 worked cleanly with no-WiFi firmware (raw ~2750 in air), then collapsed to raw=2–4 the moment WiFi came up. GPIO3 is the safe neighbor. See [GPIO3/ADC decision](../decisions/2026-04-14-esp32-c3-gpio3-adc.md).

### Silkscreen note

Pin silkscreens on this clone match the chip's GPIO numbering (verified empirically by wet/dry response testing). Other SuperMini clones may have labeling discrepancies — always verify before wiring.

## Firmware

- **Location:** `firmware/plant_node/`
- **Build tool:** PlatformIO with two envs per plant: `plant-{id}` for USB flash, `plant-{id}-ota` for subsequent wireless pushes
- **Plant ID baked in at build time** via `-D PLANT_ID=\"a\"` build flag
- **Firmware version** tracked via `-D FIRMWARE_VERSION=\"x.y.z\"` build flag; sent with every POST and upserted into `sensornode.firmware_version`
- **ADC driver:** ESP-IDF native `adc1_get_raw()` (Arduino `analogRead()` has documented WiFi-interaction issues on ESP32-C3)
- **Behavior per cycle (every 30s):** average 16 ADC samples on GPIO3, POST raw value as `soil_moisture_raw` metric, include node metadata (ip, firmware_version, uptime_ms) for upsert

## OTA Reflashing

The board advertises mDNS as `plant-{id}.local:3232` with password-protected ArduinoOTA. After the initial USB flash:

```bash
source /home/akcom/code/dirt/.env  # loads PLANT_OTA_PASSWORD
cd firmware/plant_node
pio run -e plant-a-ota -t upload
```

Takes ~20s over WiFi. No need to open the tent.

## Ingest Path

- **Endpoint:** `POST http://homebox.local:8000/api/ingest/sensors`
- **Auth:** bearer token (`SENSOR_INGEST_TOKEN` in `.env`, baked into firmware via `secrets.h`)
- **Payload:**
  ```json
  {
    "location": "plant-a",
    "metrics": {"soil_moisture_raw": 1234},
    "source": "esp32",
    "firmware_version": "0.1.0",
    "ip": "192.168.1.250",
    "uptime_ms": 30000
  }
  ```
- Server inserts one `sensorreading` row per metric, upserts `sensornode`, and auto-widens `sensorcalibration` extrema (see [server-side auto-calibration decision](../decisions/2026-04-14-server-side-auto-calibration.md)).

## Pre-flight Sensor Health Check

Given the 40%+ DOA rate on the current sensor pack, always validate a sensor with a multimeter **before** wiring it to the ESP32:

1. Connect sensor VCC/GND to any 3.3V source (including the ESP32 board).
2. Multimeter in DCV mode, probe the sensor's AOUT pin vs GND.
3. In dry air: should read **~1.5–2.5V**.
4. In water (dip to the insertion line): should drop to **~0.5–1V**.
5. If AOUT reads 0V in air: sensor is dead (555 oscillator not running). Discard.

## Secrets (gitignored)

`firmware/plant_node/src/secrets.h` contains WiFi creds, server URL, ingest token, and OTA password. A `secrets.h.example` template is committed; the real file is not. Values sourced from the repo-root `.env`.

## Known Quirks

- **Conformal coating risk:** silicone coating can creep onto the sensor's 3-pin header and insulate the dupont contacts. Mask the pins before coating, or scrape/IPA-clean afterward. Covered in the 2026-04-14 debugging session — multiple coated sensors appeared to fail power checks until pins were cleaned.
- **5V supply degrades sensor longevity:** running the v1.2 at 5V can push AOUT above 3.3V; if the ESP32 ADC pin is already connected, current flows through the ESP32's ESD clamp diodes. Protects the ESP32 but can stress the sensor's output stage over time. Use 3V3.
- **Dupont wire crimps** from cheap jumper packs fail silently more often than expected. When debugging a node, consider the wires as a hypothesis before swapping boards or sensors.
