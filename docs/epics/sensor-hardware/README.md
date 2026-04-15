# Epic: Sensor Hardware Integration

Status: planning
Priority: high
Created: 2026-03-22
Updated: 2026-04-12

## Goal

Build a distributed sensor network for the grow tent with two tiers: a centralized Arduino Nano hub for tent-level environment readings, and per-plant ESP32-C3 wireless nodes for soil moisture monitoring. All data feeds into the dirt web app's dashboard and database.

## Architecture

```
Per-plant (inside tent, USB-C powered, always-on, WiFi):
  ESP32-C3 SuperMini × 4 + capacitive soil moisture sensor
  → always-on loop: reads sensor every 5 min, POSTs JSON to FastAPI
  → mDNS: advertises as plant-{a,b,c,d}.local
  → OTA: firmware updates pushed over WiFi via PlatformIO

Tent-level (outside tent, USB serial):
  Arduino Nano → DHT22 (temp/humidity) + MH-Z19B (CO2) + XKC-Y25-T12V ×3 (reservoir level)
  → JSON lines over USB serial at 9600 baud
  → dirt app reads via pyserial

Service discovery (mDNS):
  ESP32 nodes → resolve dirt-server.local to find FastAPI server
  FastAPI server → resolve plant-{id}.local for OTA pushes
  No hardcoded IPs in firmware or server config

All USB power via:
  RSHTECH 10-Port Powered USB Hub (60W)
  → monitoring host
```

### Data Flow: Push Model (ESP32 → FastAPI)

The ESP32 nodes push readings to the FastAPI server via HTTP POST. The server does NOT poll the ESP32s. This is the simplest architecture because:

- ESP32 only needs to know the server (resolved via mDNS)
- Server does NOT need to discover ESP32s for data collection — nodes self-identify in POST payloads
- No message broker infrastructure (MQTT) needed for a single-consumer setup
- Node health monitoring is free: if a node hasn't POSTed in 10 minutes, it's offline

### Service Discovery: mDNS (Both Directions)

**ESP32 → Server:** Each ESP32 resolves `dirt-server.local` via mDNS to find the FastAPI server. The server's hostname is set once on the Linux host (`hostnamectl set-hostname dirt-server`); Avahi advertises it automatically. No IP addresses hardcoded in firmware — survives DHCP lease changes.

**Server → ESP32 (for OTA):** Each ESP32 advertises itself as `plant-{id}.local` via mDNS. PlatformIO uses this for OTA uploads: `pio run -e esp32 -t upload --upload-port plant-a.local`. The FastAPI app can also use these hostnames for health checks or future pull-based features.

### OTA Firmware Updates

ESP32 nodes are always-on (USB-C powered, no deep sleep), so ArduinoOTA runs continuously in the main loop. Firmware can be pushed at any time from the development machine without physical access to the boards.

- Initial flash: USB-C (one time per board)
- All subsequent updates: WiFi OTA via `pio run -t upload --upload-port plant-{id}.local`
- **Critical:** Every firmware version MUST include `ArduinoOTA.begin()` + `ArduinoOTA.handle()`. Omitting these loses OTA capability and requires USB reflash.

### Why Always-On (No Deep Sleep)

The ESP32s are USB-C powered, not battery powered. Deep sleep would save ~25mA but:
- Kills WiFi → no mDNS advertisement → no OTA capability while sleeping
- Adds complexity: boot/WiFi reconnect cycle on each wake, sleep state management
- The ~25mA active-idle draw is irrelevant on USB-C wall power

Always-on gives: instant OTA anytime, continuous mDNS discovery, simpler firmware, no reconnection logic.

## Hardware

### Tent-Level Controller (Arduino Nano)

- **Arduino Nano clone** (ELEGOO, CH340 USB-serial) — `/dev/ttyUSB0` on Linux
- Reads tent-wide environment sensors: temperature, humidity, CO2, reservoir level

| Sensor | Model | Interface | Nano Pin | Measurement |
|--------|-------|-----------|----------|-------------|
| Temp + Humidity | DHT22 / AM2302 | Digital (single-wire) | D6 + 10k pull-up | -40-80C (+/-0.5C), 0-100% RH (+/-2%) |
| CO2 | MH-Z19B NDIR | UART (SoftwareSerial) | D2 (RX), D3 (TX) | 0-5000 ppm (+/-50ppm +5%) |
| Reservoir Level | XKC-Y25-T12V x3 | Digital (binary) | D7, D8, D9 | Non-contact, mounted at low/half/full |

### Per-Plant Nodes (ESP32-C3 SuperMini)

- **ESP32-C3 SuperMini** (RISC-V, WiFi, BLE 5.0, USB-C) — 5-pack, 4 deployed + 1 spare
- Each node reads one capacitive soil moisture sensor
- Powered via USB-C from RSHTECH hub or USB power strip inside tent
- Always-on: reads sensor every 5 min, OTA-ready, mDNS-discoverable

| Sensor | Model | Interface | ESP32 Pin | Measurement |
|--------|-------|-----------|-----------|-------------|
| Soil Moisture | Capacitive v1.2 x4 | Analog | GPIO3 (ADC1_CH3) | Relative moisture % (calibrated) |

**Soil moisture sensor details:**
- Generic "Capacitive Analog Soil Moisture Sensor v1.2" (555-timer based, 3.3–5.5V supply, analog output).
- Source: [Amazon B0BTHL6M19](https://www.amazon.com/dp/B0BTHL6M19) — 5-pack, corrosion-resistant PCB.
- Output: analog voltage inversely proportional to moisture (higher voltage = drier). Calibrate per-pot: record raw ADC values for dry air and submerged-in-water to derive the 0–100% range.
- Power from ESP32-C3 3.3V rail. v1.2 was designed around 5V so the usable ADC range on 3.3V is narrower than v2.0 — still workable; just tighter calibration.
- Conformal-coat the PCB edges above the insertion line before deployment (moisture wicks up unprotected FR4 and kills the board).
- Power sensor VCC from the board's 5V/VBUS pin (the 3.3V rail droops under WiFi TX current draw on the SuperMini).
- **Do NOT wire AOUT to GPIO4.** GPIO4–GPIO7 are JTAG pins (MTMS/MTDI/MTCK/MTDO) on the ESP32-C3; when WiFi is active the JTAG peripheral drives these pins and the ADC reading collapses to ~0. Confirmed empirically 2026-04-14. Use GPIO3 (ADC1_CH3) — nearest safe ADC1 channel.

### Infrastructure

| Component | Model | Purpose |
|-----------|-------|---------|
| USB Hub | RSHTECH 10-Port (60W) | Central hub for all USB devices on monitoring host |
| Conformal Coating | Silicone (120ml) | Board protection for flower phase (high RH) |

### Pin Allocation (Arduino Nano)

```
D0/D1  — Hardware serial (USB)
D2/D3  — MH-Z19B UART (SoftwareSerial)
D4/D5  — Free
D6     — DHT22 data (+ 10k pull-up to 5V)
D7     — XKC-Y25-T12V #1 (low)
D8     — XKC-Y25-T12V #2 (half)
D9     — XKC-Y25-T12V #3 (full)
D10-D13 — Free
A0-A7  — Free (soil moisture moved to ESP32 nodes)
```

## Data Path

### Tent-Level (Arduino Nano → USB Serial)

```json
{
  "temperature_f": 78.2,
  "humidity_pct": 52.1,
  "co2_ppm": 812,
  "reservoir_level": "half",
  "vpd": 1.23
}
```

### Per-Plant (ESP32-C3 → WiFi HTTP POST)

```json
{
  "plant_id": "a",
  "soil_moisture_pct": 62.3,
  "firmware_version": "1.0.0",
  "ip": "192.168.1.103",
  "uptime_ms": 3600000
}
```

## ESP32-C3 Reference Firmware

```cpp
#include <WiFi.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include <HTTPClient.h>

const char* SSID = "...";
const char* PASSWORD = "...";
const char* SERVER = "http://dirt-server.local/api/sensors/reading";
const char* PLANT_ID = "a";  // unique per board
const int SENSOR_PIN = 0;
const unsigned long INTERVAL_MS = 300000;  // 5 minutes

unsigned long lastReading = 0;

void setup() {
    WiFi.begin(SSID, PASSWORD);
    while (WiFi.status() != WL_CONNECTED) delay(100);

    MDNS.begin("plant-a");  // advertise as plant-a.local
    ArduinoOTA.begin();
}

void loop() {
    ArduinoOTA.handle();

    if (millis() - lastReading > INTERVAL_MS) {
        int raw = analogRead(SENSOR_PIN);
        float pct = map(raw, DRY_VALUE, WET_VALUE, 0, 100);

        HTTPClient http;
        http.begin(SERVER);
        http.addHeader("Content-Type", "application/json");
        http.POST("{\"plant_id\":\"" + String(PLANT_ID) +
                  "\",\"soil_moisture_pct\":" + String(pct) + "}");
        http.end();

        lastReading = millis();
    }
}
```

## Derived Metrics

- **VPD (Vapor Pressure Deficit)** — calculated from temperature + humidity, not a sensor. Formula: `VPD = SVP(temp) * (1 - RH/100)` where `SVP = 0.6108 * exp(17.27 * T / (T + 237.3))`. Critical for grow optimization.

## Scope

### ESP32-C3 Firmware
- Arduino sketch: read capacitive soil moisture sensor, connect WiFi, POST JSON on interval
- Always-on loop with ArduinoOTA for over-the-air updates
- mDNS advertisement as `plant-{id}.local`
- mDNS resolution of `dirt-server.local` for server discovery
- Soil moisture calibration (dry air = 0%, submerged = 100%)
- WiFi reconnection handling on disconnect

### Arduino Nano Firmware
- Existing sketch extended for CO2 and reservoir level sensors
- MH-Z19B warmup handling (3 min on power-on, 2s between reads)

### Python Backend
- HTTP endpoint (`POST /api/sensors/reading`) to receive ESP32 soil moisture POSTs
- Node health tracking: flag nodes that haven't reported in 10+ minutes
- Serial reader service for Arduino Nano (existing)
- Extended SensorReading model with new fields (co2_ppm, soil_moisture_pct per plant, reservoir_level, vpd)
- VPD calculation service

### Dashboard
- Per-plant soil moisture indicators
- CO2 graph (separate chart)
- Reservoir level indicator (3-tier: low/half/full with color coding)
- VPD display with optimal range highlighting (0.8-1.2 kPa veg, 1.0-1.5 flower)
- Node health status (online/offline per ESP32)

### Hardware Notes
- Capacitive soil moisture sensor PCB edges need conformal coating above insertion line to prevent moisture wicking
- ESP32-C3 boards should be mounted above splash zone (pot rim or tent pole, not floor)
- Conformal coat all boards before flowering phase (RH will climb)
- XKC-Y25-T12V sensors mount on outside of reservoir with double-sided tape
- MH-Z19B needs 3 minutes warmup on power-on before readings are accurate
- DHT22 needs a 10k pull-up resistor between VCC and data pin

## Acceptance Criteria

- All sensors read and display on dashboard with real data
- Per-plant soil moisture displayed individually (Plants A, B, C, D)
- ESP32 nodes reliably connect to WiFi and POST readings every 5 minutes
- ESP32 nodes discoverable via mDNS (`plant-{id}.local`)
- OTA firmware updates work via `pio run -t upload --upload-port plant-{id}.local`
- Server discoverable by ESP32s via mDNS (`dirt-server.local`)
- VPD calculated and displayed with optimal range indicator
- Reservoir level shows visual indicator (low=red, half=yellow, full=green)
- Serial reader and HTTP endpoint handle disconnection/failure gracefully
- Node health monitoring: offline nodes flagged within 10 minutes
- Existing tests still pass, new tests for HTTP endpoint, serial reader, and VPD calculation

## References

### ESP32 & Soil Moisture
- [ESP32 Soil Moisture Sensor project (Maakbaas)](https://maakbaas.com/esp32-soil-moisture-sensor/) — full build guide for ESP32 + capacitive sensor
- [ESP32 Deep Sleep Battery Sensors Guide](https://esp32.co.uk/esp32-battery-powered-sensors-deep-sleep-low-power-design-guide/) — power analysis (informed our decision to skip deep sleep on USB-C power)
- [ESP32-C3 vs ESP32-S3 comparison](https://www.agentangiehomes.com/esp32-c3-vs-esp32-s3-deep-sleep-current/) — why we chose C3 (cheaper, lower power, sufficient for single-sensor nodes)
- [XIAO ESP32 S3/C3/C6 comparison (Seeed Studio)](https://www.seeedstudio.com/blog/2026/01/14/xiao-esp32-s3-c3-c6-comparison/)

### mDNS & Service Discovery
- [Understanding mDNS on ESP32 (Medium)](https://medium.com/engineering-iot/understanding-mdns-on-esp32-local-network-device-discovery-made-easy-9aab590f0eea) — mDNS basics, hostname resolution, service advertisement
- [ESP32 mDNS Tutorial (Last Minute Engineers)](https://lastminuteengineers.com/esp32-mdns-tutorial/) — setup guide with code examples
- [ESP-IDF mDNS Service Documentation (Espressif)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/protocols/mdns.html) — official mDNS API reference
- [ESP32 mDNS Service Advertisement (DFRobot)](https://www.dfrobot.com/blog-1526.html) — service discovery patterns

### OTA Firmware Updates
- [ESP32 Basic OTA Programming (Last Minute Engineers)](https://lastminuteengineers.com/esp32-ota-updates-arduino-ide/) — ArduinoOTA setup guide
- [ESP32 OTA with PlatformIO / VS Code (Random Nerd Tutorials)](https://randomnerdtutorials.com/esp32-ota-over-the-air-vs-code/) — PlatformIO-specific OTA config
- [ESP32 OTA using PlatformIO (PlatformIO Community)](https://community.platformio.org/t/esp32-ota-using-platformio/15057) — community discussion on PlatformIO OTA setup
- [OTA and Deep Sleep conflict (PlatformIO Community)](https://community.platformio.org/t/ota-and-deepsleep-mode/7235) — why OTA and deep sleep don't mix (informed our always-on decision)

### Data Flow Architecture
- [MQTT vs HTTP for IoT (ESP32 Tutorials)](https://esp32tutorials.com/mqtt-vs-http-iot/) — comparison that informed our HTTP POST push model decision

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:sensor-hardware"`
