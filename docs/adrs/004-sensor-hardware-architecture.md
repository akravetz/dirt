# ADR 004: Sensor Hardware Architecture

## Status

Accepted

## Context

We need real sensor data for temperature, humidity, CO2, soil moisture, and reservoir level. Two approaches were evaluated:

1. **USB plug-and-play sensors** — Individual USB devices (TEMPerHUM, AirCO2ntrol, MaxBotix, Tinovi). Each has its own protocol, Python library, and USB port. Total cost ~$150+. Simpler software, more complex hardware (multiple USB devices).

2. **Arduino Nano sensor hub** — One microcontroller reading all sensors, outputting JSON over a single USB serial connection. Total cost ~$29-50. More complex firmware, simpler software integration.

We also evaluated the reservoir level sensor. The JSN-SR04T ultrasonic sensor has a 20cm minimum distance, which is too much for a small autopot reservoir. Non-contact capacitive sensors (XKC-Y25-T12V) mounted on the outside of the reservoir wall provide binary level detection with no minimum distance constraint.

## Decision

**Microcontroller approach with Arduino Nano clone (CH340).**

### Hardware
- **Board:** Arduino Nano clone (ELEGOO, CH340 USB-serial, ~$6)
- **Temp/Humidity:** DHT22 / AM2302 — digital single-wire on D6, 10kΩ pull-up (±0.5°C, ±2% RH)
- **CO2:** MH-Z19B NDIR — UART via SoftwareSerial on D2/D3 (0-5000 ppm)
- **Soil Moisture:** Capacitive v2.0 — analog on A0 (edges coated with conformal coating)
- **Reservoir Level:** 3× XKC-Y25-T12V — non-contact capacitive, digital on D7/D8/D9, mounted at low/half/full on outside of reservoir wall

### Data Protocol
JSON lines over USB serial at 9600 baud, one reading every 10 seconds:
```json
{"temperature_f": 78.2, "humidity_pct": 52.1, "co2_ppm": 812, "soil_moisture_pct": 62.3, "reservoir_level": "half", "vpd": 1.23}
```

### Derived Metrics
VPD (Vapor Pressure Deficit) calculated on the Arduino from temp + humidity. Formula: `SVP × (1 - RH/100)` where `SVP = 0.6108 × exp(17.27 × T / (T + 237.3))`.

### Development Tooling
PlatformIO over arduino-cli for firmware development. PlatformIO provides:
- Declarative config (`platformio.ini` checked into repo)
- Built-in test runner with `native` environment (tests run on Linux, no hardware needed)
- Library dependency management
- CLI compile and upload

### Code Structure
Firmware lives in `firmware/` at the repo root. Logic (JSON encoding, VPD calculation, validation) separated into pure C++ libraries testable without hardware. The `.ino`/`main.cpp` is a thin orchestrator calling into testable library code.

### Integration
Python backend reads serial via `pyserial`, stores readings in the existing `SensorReading` model. The `source` field distinguishes mock data from real sensor data.

## Consequences

- Single USB connection for all sensors simplifies the software — one serial reader, one data format.
- Arduino firmware adds a second language (C++) to the project, but PlatformIO's native test environment means the agent can develop and test without hardware connected.
- CH340 driver is built into modern Linux kernels — no driver installation needed.
- XKC-Y25-T12V sensors provide discrete level thresholds (low/half/full) rather than continuous measurement. Sufficient for "time to refill" alerting but not precise volume tracking.
- MH-Z19B needs 3 minutes warmup on power-on before readings are accurate — firmware must handle this gracefully.
- Capacitive soil moisture sensor readings drift over time in wet media — periodic recalibration needed.
