# Epic: Sensor Hardware Integration

Status: planning
Priority: high
Created: 2026-03-22

## Goal

Replace mock sensor data with real hardware readings from an Arduino Nano sensor hub connected via USB serial. Support temperature, humidity, CO2, soil moisture, and reservoir level — all feeding into the existing dashboard and database.

## Hardware

### Microcontroller
- **Arduino Nano clone** (ELEGOO, CH340 USB-serial) — shows up as `/dev/ttyUSB0` on Linux

### Sensors

| Sensor | Model | Interface | Nano Pin | Measurement |
|--------|-------|-----------|----------|-------------|
| Temp + Humidity | DHT22 / AM2302 | Digital (single-wire) | D6 + 10kΩ pull-up | -40–80°C (±0.5°C), 0–100% RH (±2%) |
| CO2 | MH-Z19B NDIR | UART (SoftwareSerial) | D2 (RX), D3 (TX) | 0–5000 ppm (±50ppm +5%) |
| Soil Moisture | Capacitive v2.0 | Analog | A0 | Relative moisture % (calibrated) |
| Reservoir Level | XKC-Y25-T12V (×3) | Digital (binary) | D7, D8, D9 | Non-contact, mounted at low/half/full |

### Pin Allocation

```
D0/D1  — Hardware serial (USB)
D2/D3  — MH-Z19B UART (SoftwareSerial)
D4/D5  — Free
D6     — DHT22 data (+ 10kΩ pull-up to 5V)
D7     — XKC-Y25-T12V #1 (low)
D8     — XKC-Y25-T12V #2 (half)
D9     — XKC-Y25-T12V #3 (full)
D10-D13 — Free
A0     — Soil moisture analog
A1-A7  — Free
```

## Data Path

```
Arduino Nano (reads all sensors every 10s)
  → JSON line over USB serial at 9600 baud
  → /dev/ttyUSB0
  → Python backend reads with pyserial
  → Stores in SensorReading model
  → Dashboard displays via existing Chart.js UI
```

### JSON Line Format

```json
{
  "temperature_f": 78.2,
  "humidity_pct": 52.1,
  "co2_ppm": 812,
  "soil_moisture_pct": 62.3,
  "reservoir_level": "half",
  "vpd": 1.23
}
```

## Derived Metrics

- **VPD (Vapor Pressure Deficit)** — calculated from temperature + humidity, not a sensor. Formula: `VPD = SVP(temp) × (1 - RH/100)` where `SVP = 0.6108 × exp(17.27 × T / (T + 237.3))`. Critical for grow optimization.

## Scope

### Arduino Side
- Arduino sketch reading all sensors, outputting JSONL over serial
- Soil moisture calibration (dry air = 0%, submerged = 100%)
- MH-Z19B warmup handling (2s between reads)

### Python Backend
- Serial reader service (`src/dirt/services/serial_reader.py`)
- Extended SensorReading model with new fields (co2_ppm, soil_moisture_pct, reservoir_level, vpd)
- VPD calculation service
- Background task reading serial port and storing readings

### Dashboard
- CO2 graph (separate chart, same pattern as temp/humidity)
- Soil moisture indicator
- Reservoir level indicator (3-tier: low/half/full)
- VPD display with optimal range highlighting (0.8–1.2 kPa for veg, 1.0–1.5 for flower)

### Hardware Notes
- XKC-Y25-T12V sensors mount on outside of reservoir with double-sided tape — no contact with nutrient solution
- Capacitive soil moisture sensor edges need conformal coating or clear nail polish to prevent moisture wicking
- MH-Z19B needs 3 minutes warmup on power-on before readings are accurate
- DHT22 needs a 10kΩ pull-up resistor between VCC and data pin

## Acceptance Criteria

- All sensors read and display on dashboard with real data
- Mock data seed is bypassed when real sensor data exists (source field distinguishes)
- VPD calculated and displayed with optimal range indicator
- Reservoir level shows visual indicator (low=red, half=yellow, full=green)
- Serial reader handles disconnection gracefully (log error, retry)
- Existing tests still pass, new tests for serial reader and VPD calculation

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:sensor-hardware"`
