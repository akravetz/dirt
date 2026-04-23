# Fan Controller + Tent Sensor Combined Node — Handoff

**Date:** 2026-04-22 (end-of-day)
**Author of this handoff:** Claude (context-full)
**Scope:** everything done this session to bring up the dual-role ESP32-C3 node (AC Infinity Cloudline LITE 6" fan driver + Adafruit SHT45 tent environmental sensor), plus the plan for completing the cutover from the Arduino Nano + BME280 tent hub.

---

## TL;DR

One ESP32-C3 SuperMini now drives the Cloudline LITE 6" fan (via 2× 2N7000 MOSFETs on D+/B5) **and** reads the new Adafruit SHT45 (via I²C on GPIO 4/5). Hardware was migrated from breadboard to Adafruit perma-proto today and is physically sitting on the tent floor with a 7 ft USB-C cable to the fan. Firmware `0.1.0` holds fan at 30 % and prints a combined heartbeat with tent temp/RH/VPD every 60 s — verified working.

**Firmware is standalone** (no WiFi, no OTA, no ingest yet). That is the next coherent step, and also unblocks retiring the Arduino Nano + BME280 production tent hub.

Uncommitted changes on `main` (as of this writing):
- `firmware/fan_controller/{platformio.ini, src/main.cpp}` — dual-role firmware
- `wiki/hardware/ac-infinity-fan-control.md` — renamed, SHT45 section added, bring-up table updated
- `wiki/decisions/2026-04-22-sht45-tent-node-esp32.md` — revision block added
- `wiki/index.md` — entries for hardware + decision updated
- `wiki/log.md` — two milestone entries appended

Last committed state: `4003dd2 feat: SHT45 tent node + ESP32 fan controller + fleet-wide cleanup` — that commit has the pre-SHT45-merge state of the firmware tree + wiki.

---

## Current state

### Hardware (on Adafruit perma-proto, soldered, working)

Currently on the tent floor outside the tent (7 ft USB-C cable reaches the fan). Not yet moved inside the tent.

| Element | Wiring |
|---|---|
| ESP32-C3 SuperMini | USB-C powered from its own wall brick (independent of fan power) |
| Treedix 10-pad female USB-C breakout | Plugs into the fan via 7 ft USB-C M-M cable |
| Q1 (2N7000) | gate ← GPIO 6; source → common GND; drain → Treedix `D+1`; 10 kΩ gate pull-down |
| Q2 (2N7000) | gate ← GPIO 7; source → common GND; drain → Treedix `C2` (= CC2 in USB-C spec = wiki's "B5"); 10 kΩ gate pull-down |
| Adafruit SHT45 + PTFE cap (#5665) | VIN ← 3V3; GND → common GND; SDA ← GPIO 4; SCL ← GPIO 5. On-breakout 10 kΩ I²C pull-ups (no external pull-ups needed). |

**Common GND rail ties**: ESP32 GND + both MOSFET sources + both 10 kΩ pull-down bottoms + Treedix GND + SHT45 GND. All one rail.

**Treedix pad identities** (important — this caused an hour of debugging today):
- `D+1` (= A6) and `D+2` (= B6) both carry the fan's D+ signal (fan internally ties A6=B6). Either works; use D+1 for consistency.
- `D-1` / `D-2` same story for D−, still unused.
- `C1` = CC1 (unused by this fan). `C2` = CC2 = keep-alive heartbeat. Do NOT wire Q2 to C1.

### Firmware (fw `0.1.0`, flashed and running)

Source: `firmware/fan_controller/src/main.cpp` (~155 lines).
Build: `cd firmware/fan_controller && pio run -e fan -t upload`.
Enumerates as `/dev/ttyACM4` at time of writing (MAC `38:44:BE:44:47:90`). Confirm with `ls -la /dev/serial/by-id/ | grep -i esp`.

Key constants (top of `main.cpp`):
```cpp
GPIO_D_PLUS    = 6    // Q1 gate
GPIO_B5        = 7    // Q2 gate
GPIO_I2C_SDA   = 4    // SHT45 SDA
GPIO_I2C_SCL   = 5    // SHT45 SCL
PWM_FREQ_HZ    = 5000 // matches fan's 4,969 Hz carrier
PWM_RESOLUTION = 10   // ledc 0..1023
HOLD_SPEED_PCT = 30
HEARTBEAT_MS   = 60000
B5_MCU_DUTY_PCT   = 1.4f   // → 98.6 % wire, mimics stock remote
D_PLUS_MIN_WIRE   = 22.0f  // stall-zone floor (linear remap)
D_PLUS_MAX_WIRE   = 100.0f
```

Sample heartbeat:
```
[   60077 ms] fan=30% (D+ wire=45.4%)  |  tent: 21.13°C (70.0°F)  RH 39.0%  VPD 1.53 kPa
```

If the SHT45 drops mid-flight, the fan keeps running; `bring_up_sht()` retries on every heartbeat.

**Critical mental model:** MOSFETs pull the fan signal lines LOW when the GPIO drives HIGH. So `duty_on_wire = 100% − duty_at_mcu`. At reset, gates float and pull-downs keep Qs off → D+ floats to ~9 V via the fan's internal pull-up → fan runs at max. This is the intentional failsafe.

### Other firmware projects (context for a cold agent)

| Path | State | Notes |
|---|---|---|
| `firmware/plant_node/` | Production — 4 ESP32-C3 soil-moisture nodes | Refactored earlier today to use `firmware/common/`; all four envs build clean. No further changes needed. |
| `firmware/common/{wifi_client, ota, ingest_client}/` | Ready, unused by fan_controller | Shared C++ libs. Pulled in via `lib_extra_dirs = ../common`. `IngestClient` signature after simplify pass: `(server_url, token, firmware_version)` — `source` is hardcoded to `"esp32"` internally. |
| `firmware/tent_node/` | **OBSOLETE, not yet deleted** | Standalone tent SHT45 project. Functionality moved into fan_controller. Delete after the combined firmware soaks a few days. |
| `firmware/{src, lib/sensor_protocol, platformio.ini}` | Legacy Arduino Nano BME280 firmware | Keep until the physical Arduino is retired. |

### Wiki state

| Path | Status |
|---|---|
| `wiki/hardware/ac-infinity-fan-control.md` | **Canonical page for the combined node.** 195 lines. Renamed title, Status reflects current reality. |
| `wiki/decisions/2026-04-22-sht45-tent-node-esp32.md` | Has "Revision (2026-04-22, evening)" block noting merge with fan controller. |
| `wiki/decisions/2026-04-20-bme280-sensor-swap.md` | Superseded by the 04-22 decision. |
| `wiki/index.md` | Hardware + Decisions entries current. |
| `wiki/log.md` | Two milestone entries today: fan controller D+ bring-up, and fan+SHT45 merge revision. |

Lint (`uv run scripts/lint.py`) passes 7/7.

**DO NOT create `wiki/hardware/tent-node.md`** — that was part of the original plan (dedicated tent_node ESP32) and is now superseded. The combined board lives in `ac-infinity-fan-control.md`.

---

## Pending work

### 1. Fold WiFi + OTA + ingest into fan_controller firmware ✅ DONE (2026-04-22 evening)

Firmware shipped as `0.2.0`. Build verified (`pio run -e fan` → flash 76.0 %, RAM 13.7 %) but not yet flashed to the physical board — user will do the USB re-flash + relocation inside the tent as a follow-up.

**What landed:**
- `firmware/fan_controller/platformio.ini` — `lib_extra_dirs = ../common`, Adafruit SHT4x deps, `FIRMWARE_VERSION="0.2.0"`, new `[env:fan-ota]` using `PLANT_OTA_PASSWORD`.
- `firmware/fan_controller/include/secrets.h.example` — committed template; `secrets.h` gitignored, seeded from the tent_node fleet credentials.
- `.gitignore` — `firmware/fan_controller/include/secrets.h` added.
- `firmware/fan_controller/src/main.cpp` — full rewrite. WiFi/OTA/IngestClient via shared libs; non-blocking heater-cycle state machine (1 s @ 200 mW pulse → 59 s equilibrate → read + post → chain next pulse; Sensirion AN §3); ingest metrics `{temperature_c, humidity_pct, fan_duty_pct}` at `location=tent`.
- `WebServer` on :80 with `POST /fan {"duty_pct":0..100}` and `GET /fan → {"set_duty_pct":N,"reported_duty_pct":N}`. `reported_duty_pct` is MOCKED (echoes set value) until tach lands.

**Design decisions that were open in this section:**

- *Control plane* → **separate HTTP endpoint on the fan** (the option-2 row of the old table). Chosen over ingest-response-body because it's host-initiated, low-latency, and factors cleanly into a `FanNodeClient` the same way the Kasa humidifier plug factors into `HumidifierLoopService`. ~30 KB flash cost (`<WebServer.h>`) is a non-issue at 76 % flash utilization.
- *Reading location* → **overload `SensorLocation.TENT`** (option a). `fan_duty_pct` rides on the tent rows' `metrics` JSON column alongside `temperature_c` / `humidity_pct`. No enum change, no Atlas migration, no new ingest endpoint — pure-additive.
- *Host-side SDK* → `apps/shared/src/dirt_shared/services/fan_node.py` (`FanNodeClient`, `FanNodeError`) + `apps/shared/tests/test_fan_node.py` (8/8 green, `httpx.MockTransport`-based). Lives in `shared` so dirt-hwd, dirt-web, and dirt-mcp can all call it from one module.
- *Heater schedule* → **Sensirion-matched** 1 s @ 200 mW per 60 s cycle (1.67 % duty). 5-minute cadence was considered and rejected — it lands right on the `humidifier_failsafe_stale_seconds = 300` edge; 60 s gives 5× headroom.

**Explicitly deferred:** host-side closed-loop VPD control. `FanNodeClient` is plumbing; nothing on the host calls it yet. Target shape documented in `wiki/hardware/ac-infinity-fan-control.md` "Future integration" — a `apps/hwd/src/dirt_hwd/services/fan_controller.py` analogous to `HumidifierLoopService`, reading tent VPD from `ReadingsService` and emitting a `fan_controller` observability stream.

### 2. Deploy combined board inside the tent

Currently on the floor outside. Physically move inside and verify the SHT45 starts reading tent-representative air (warmer + more humid than the ~21 °C / 39 % RH we're seeing now). Validate by comparing against Arduino/BME280 readings.

### 3. Retire Arduino Nano + BME280 tent hub

Prerequisite: combined board is reporting via ingest AND has been trusted for ≥ 24 h of parallel operation.

Order of operations:
1. Unplug Arduino's USB cable from the host.
2. `systemctl --user stop dirt-hwd`.
3. Delete `apps/hwd/src/dirt_hwd/services/serial_reader.py`.
4. Remove serial_reader wiring from `apps/hwd/src/dirt_hwd/app.py`.
5. Remove `/dev/ttyArduino` udev rule if present in `/etc/udev/rules.d/`.
6. Remove `ExecStartPre` serial-symlink assertion from `systemd/dirt-hwd.service` if present.
7. Delete `firmware/src/`, `firmware/lib/sensor_protocol/`, `firmware/platformio.ini`.
8. `systemctl --user start dirt-hwd`.
9. `journalctl --user -u dirt-hwd` — verify no errors.
10. Update `wiki/hardware/humidifier-control.md` Known Issues #1 → mark resolved-by-transition.
11. Update `wiki/overview.md` System Status row to reflect ESP32 tent sensor.
12. Optional (later, via Atlas): retire `SensorSource.ARDUINO` enum value. Historical rows keep the label; enum cleanup is cheap but not urgent.

### 4. Delete obsolete `firmware/tent_node/`

After combined firmware has soaked a few days (~2026-04-26 onward):
```bash
rm -rf firmware/tent_node/
# then remove from .gitignore:
#   firmware/tent_node/.pio/
#   firmware/tent_node/include/secrets.h
```

### 5. Tach (D−) input — deferred

First attempt today failed: 10 kΩ / 4.7 kΩ voltage divider loaded D− below the ESP32 HIGH threshold. DC measurement on D− under load was **0.71 V** — implying D− HIGH on the wire is only ~1.4 V because the fan's internal pull-up is much weaker (~170 kΩ) than the original reverse-engineering captures suggested.

Fix options when we come back:
- **Higher-impedance divider:** swap 10 k → 100 k, 4.7 k → 47 k. Same 1:3 ratio, 10× less loading. Math predicts D− HIGH ≈ 4 V, GPIO sees ≈ 1.3 V (above threshold).
- **External VBUS pull-up:** add a 10 kΩ from Treedix `V` (9 V) to D−1 to overcome the weak internal pull-up. Keep the existing 10 k / 4.7 k divider.
- **Re-characterize:** fresh logic-analyzer session if hardware fixes don't get clean edges.

**GPIO 10 is still reserved for tach.** No code for it in the current firmware.

### 6. Low-priority loose ends

- **Is B5 actually required?** Fan works with B5 driven. Untested whether it'd work with B5 floating (`ledcWrite(LEDC_CH_B5, 0)` → B5 floats high via fan's internal pull-up).
- **Thermal check on 2N7000s** — touch-check each after 10+ minutes at mid-speed. Not done.
- **SHT45 heater schedule** — deferred until we observe RH pinned at 100 % in the tent. Would be an `sht.setHeater(SHT4X_MED_HEATER_100MS)` pulse once per hour or so.

---

## Gotchas for a cold agent

### ESP32-C3 SuperMini pin rules
- **GPIO 8** = onboard LED + boot-strap pin (must be HIGH at boot). **GPIO 9** = BOOT button + strap pin. Neither is safe for general-purpose wiring at runtime.
- **GPIO 4–7** are JTAG pins on the C3. JTAG interferes with *passive ADC reads* only — actively-driven I/O (I²C, PWM out, digital in/out) is unaffected. That's why the plant_node's capacitive moisture sensor is on GPIO 3 (to avoid ADC collapse) while the fan controller happily uses GPIO 4/5/6/7.
- **GPIO 10** is a plain GPIO with no strapping role. Safe for anything.

### Arduino-ESP32 core version
This repo uses arduino-esp32 **v2.x**, not v3.x. LEDC API is the older:
```cpp
ledcSetup(channel, freq, resolution);
ledcAttachPin(pin, channel);
ledcWrite(channel, duty);
```
NOT the newer `ledcAttach(pin, freq, resolution)` + `ledcWrite(pin, duty)`.

### Fan protocol quirks
- **D+ is open-drain** with ~9 V internal pull-up inside the fan. We don't source 9 V — we just pull the line LOW via Q1. MCU HIGH → line LOW, always.
- **When D+ is "released" (MOSFET off), the line floats to ~9 V** → fan reads 100 % duty → runs at max. This is the failsafe direction. Don't engineer around it.
- **D− internal pull-up is weak** (~170 kΩ empirically). Divider attempts need to be very high-impedance or use an external VBUS pull-up.
- **B5 = CC2** in USB-C spec = Treedix `C2` pad. Easy to wire to `C1` (CC1) by mistake; the fan ignores CC1 so it'd silently "not keep-alive."

### Ingest / DB transition period
- `SensorLocation.TENT` enum value is shared between the Arduino (`source='arduino'`) and combined ESP32 (`source='esp32'`) during parallel operation. Both coexist in `sensorreading` rows.
- `sensornode` has `location` as UNIQUE. Row id 1 for `tent` currently has no ip/firmware (it's the Arduino's row, written by the serial_reader service). When the combined ESP32 starts posting, it'll upsert that row with its IP + firmware.
- `dirt-hwd` is production-critical (humidifier VPD control loop reads from `sensorreading`). Don't carelessly restart during a humidity swing. It has a burst-cap restart budget: 5 nonzero exits in 5 min → systemd leaves it failed. Reset with `systemctl --user reset-failed dirt-hwd`.

### Wiki lint
- Always run `uv run scripts/lint.py` after wiki edits. 7 checks, fails hard on frontmatter, file length, index sync.
- Hardware page file-length limit: 200 lines warning, 400 lines fail. `ac-infinity-fan-control.md` is currently at 195. Be careful what you add.
- Decision pages are append-only via revision blocks (see how `2026-04-22-sht45-tent-node-esp32.md` added its revision rather than being rewritten).

---

## Useful commands

### Read serial (no reset — catches the 60 s heartbeat)
```bash
uv run --with pyserial python3 -c "
import serial, time
s = serial.Serial('/dev/ttyACM4', 115200, timeout=1)
t_end = time.time() + 70
while time.time() < t_end:
    line = s.readline()
    if line: print(line.decode('utf-8', errors='replace').rstrip())
"
```

### Read serial with reset (full boot banner + first heartbeat)
```bash
uv run --with pyserial python3 -c "
import serial, time
s = serial.Serial('/dev/ttyACM4', 115200, timeout=1)
s.setDTR(False); s.setRTS(False); time.sleep(0.1); s.setDTR(True)
t_end = time.time() + 12
while time.time() < t_end:
    line = s.readline()
    if line: print(line.decode('utf-8', errors='replace').rstrip())
"
```

### Build + flash
```bash
cd firmware/fan_controller && pio run -e fan -t upload
```

### Find the board on USB
```bash
ls -la /dev/serial/by-id/ | grep -i esp
# fan controller is MAC 38:44:BE:44:47:90
```

### Check production ingest
```bash
journalctl --user -u dirt-hwd --since "5 minutes ago" | grep ingest
# 4 plant nodes + (eventually) 1 combined tent/fan board show up
```

### Check sensor nodes in DB
```bash
set -a; source .env; set +a
PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c \
  "SELECT id, location, ip, firmware_version, last_seen FROM sensornode ORDER BY last_seen DESC NULLS LAST;"
```

### Commit current uncommitted work (when ready)
```bash
cd /home/akcom/code/dirt
scripts/agent-fix       # formatters before commit — always run first
git add firmware/fan_controller/ wiki/
git commit -m "feat(firmware.fan_controller): merge SHT45 tent sensor into fan-controller ESP32
...
"
```
The `4003dd2` commit captured the pre-merge state; this handoff's changes are the evening SHT45-merge work.
