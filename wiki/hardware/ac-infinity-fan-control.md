---
title: Hardware — AC Infinity Fan Control + Tent Environmental Sensor (combined node)
type: hardware
sources: [debug/fan-pwm/sweep-v2.sr, debug/fan-pwm/sweep-11steps.sr, debug/fan-pwm/sweep-v3.sr]
related: [wiki/hardware/humidifier-control.md, wiki/hardware/esp32-plant-nodes.md, wiki/decisions/2026-04-22-sht45-tent-node-esp32.md]
created: 2026-04-18
updated: 2026-04-22
---

# AC Infinity Cloudline LITE 6" Fan Control + Tent Environmental Sensor

**Status (2026-04-22):** **D+ bring-up validated + SHT45 tent sensor integrated on the same ESP32.** One ESP32-C3 SuperMini now drives the fan via two 2N7000 MOSFETs (D+/B5) and reads an Adafruit SHT45 + PTFE cap over I²C (GPIO 4/5). Firmware [`firmware/fan_controller/`](../../firmware/fan_controller/) emits a combined heartbeat line every 60 s with both commanded fan state and measured tent temp/RH/VPD. **Physical placement:** board sits on the tent floor; fan reached via the 7 ft USB-C cable. **Deviation from earlier plan:** SHT45 was initially slated for a dedicated `tent_node` ESP32 per [2026-04-22 SHT45 decision](../decisions/2026-04-22-sht45-tent-node-esp32.md); merged into the fan-control board the same day since one board serving both roles is simpler than two. **Tach (D−) path remains unimplemented** — initial 10 kΩ/4.7 kΩ divider attempt 2026-04-22 registered zero edges; the fan's internal pull-up on D− is weaker than the reverse-engineering captures implied, and our divider loaded it below the ESP32 HIGH threshold. Deferred pending a redo with a higher-impedance divider or a fresh signal-analysis pass. **Also deviates from original plan:** moved from Arduino Nano to ESP32-C3 SuperMini so the driver joins the same fleet operational model as the plant nodes. The Nano-era driver schematic at `debug/fan-pwm/driver-schematic.png` and the Nano test sketch at `debug/fan-pwm/fan_drive_test/` are stale.

## Goal

Drive the Cloudline LITE 6" inline fan from an ESP32-C3 SuperMini instead of AC Infinity's stock wired speed controller, and read tent temp/RH from a colocated SHT45 on the same board. End state: programmatic fan speed, closed-loop VPD coupling with the humidifier, and retirement of the Arduino Nano BME280 tent hub.

## Protocol (confirmed 2026-04-21, sweep-v3.sr)

Three meaningful signals on the USB-C connector. All share a common GND and a ~9V VBUS rail. All three signals swing 0 ↔ ~9V.

| USB-C pin | Direction | Signal | Details |
|---|---|---|---|
| **D+** | remote → fan | **PWM speed command** | 4,969 Hz carrier, open-drain (see topology below). Duty-cycle maps to fan speed per the table below. Measured range on v3 sweep: 0.9% (dial just above OFF) → 87.6% (near top of dial). Full 100% reached at hard-max in earlier 11-step capture. |
| **D−** | fan → remote | **Tachometer output** | 50%-duty square wave whose *frequency* is proportional to RPM. ~45 Hz at lowest running speed, ~166 Hz near top of dial. Assuming 2 pulses/rev, that's ~1,350 RPM min, ~4,980 RPM max. |
| **B5** (= CC2 spec-side) | remote → fan | Clock / keep-alive | Same 4,969 Hz carrier as D+, but stuck at ~98.6% duty regardless of speed (2.5–3.0 µs LOW pulses per cycle). Likely a "remote connected" heartbeat. Drive-requirement unconfirmed — first test will leave B5 floating and see if the fan still responds to D+ alone. |
| VBUS | — | ~+9V rail | Powers the fan's control electronics and pulls the three signal lines up. Do **not** clip a 5V-only logic analyzer to this (or to any of the signal lines, which also swing to 9V). |
| D+ pin label note | | | On the minidodoca breakout, D+ is labeled `A5` on the silkscreen — that's the USB-C spec-A-side pin number for D+, not a separate signal. The B5 pin is the neighbor on the B-side row of the same connector. |

### Speed table (dial position → D+ duty cycle)

Derived from a 20-second logic-analyzer sweep stepping through all 11 dial positions; each plateau stable to ±0.005 duty.

| Dial position | D+ duty | Step |
|---:|:---:|:---:|
| OFF  | 0.0%   | — |
| 1    | 21.7%  | +21.7 (motor start threshold) |
| 2    | 29.8%  | +8.1 |
| 3    | 37.7%  | +7.9 |
| 4    | 46.8%  | +9.1 |
| 5    | 54.7%  | +7.9 |
| 6    | 62.8%  | +8.1 |
| 7    | 70.8%  | +8.0 |
| 8    | 79.7%  | +8.9 |
| 9    | 87.7%  | +8.0 |
| 10   | 100.0% | +12.3 |

- Linear PWM mapping 22%–100% for "running" speeds. 0% = OFF (line held low). Below ~22% the motor likely buzzes without spinning — avoid unless explicitly testing stall.
- The ~8% inter-click step is a remote-side UX choice, **not** a protocol limit. Underlying resolution is ≈1%, so we can command any duty we want; the 10-position dial is a coarse abstraction over a continuous range.
- Driver API: `set_fan_speed(uint8_t pct)` in `firmware/fan_controller/src/main.cpp`. `pct=0` → 0% duty (off); `pct=1..100` → linearly remapped to 22%–100% D+ wire duty; the inversion math (MCU duty = 100 − wire duty, since our MOSFET pulls D+ low when the GPIO is high) is handled inside the helper.

### Electrical topology

**D+ is open-drain with the pull-up inside the fan.** Confirmed 2026-04-20: with the stock remote unplugged, D+ floats to ~9V (the fan's internal pull-up to its ~9V VBUS) and the fan runs at max speed (reads 100% duty because nothing is pulling low). B5 behaves the same way (pulled up internally, driven LOW by the remote for 2.5–3 µs chunks at 5 kHz).

Implication: **the driver does not need to source 9V** — it only needs to pull D+ (and optionally B5) to GND at the right times. A small N-channel MOSFET (or NPN) between each signal line and GND, gate driven by the MCU's PWM output, is sufficient. If the MCU is not 5V-tolerant on its GPIO (e.g. the ESP32-C3, `Vmax = 3.6V`), the fan's 9V signals must never connect directly to a GPIO — only to the MOSFET drain.

**Failsafe behavior:** if the driver loses power, resets, or crashes, D+ floats → fan runs at 100%. For a grow tent this is the safer direction; overventilation won't kill plants, whereas a stalled fan in a sealed tent eventually will. We are intentionally leaning into this behavior rather than engineering around it.

## Driver circuit (ESP32-C3 SuperMini)

Two N-channel logic-level MOSFETs, one per driven signal. ~$1 in parts.

```
  fan D+ (via Treedix) ──────────┐                fan B5 (via Treedix) ──────────┐
                                 │ drain                                         │ drain
                         [Q1 2N7000]                                     [Q2 2N7000]
                                 │ source                                        │ source
  fan GND (via Treedix) ────── common GND ────── ESP32 GND                       │
                                 │                                               │
  ESP32 GPIO 6 ──────────────────┤ gate                        ESP32 GPIO 7 ─────┤ gate
                                 │                                               │
                              [R1 10 kΩ]                                    [R2 10 kΩ]
                                 │                                               │
                              common GND                                    common GND
```

- **Q1 drives D+** (speed command). **Q2 drives B5** (keep-alive heartbeat). Symmetric topology per signal.
- **Drain → fan signal pad** on the Treedix breakout.
- **Source → common GND.** Fan GND and ESP32 GND **must** be tied together; otherwise the MOSFETs have no reference and nothing happens.
- **Gates → ESP32 GPIO 6 (D+) / GPIO 7 (B5).** LEDC peripheral, channel 0 for D+, channel 1 for B5, both at 5 kHz / 10-bit (matches the fan's 4,969 Hz carrier).
- **10 kΩ gate pull-downs** (R1, R2). Keep each MOSFET OFF during ESP32 reset/boot (GPIO would otherwise float, causing a few ms of random pull-downs).
- **Signal is inverted in firmware.** ESP32 HIGH = MOSFET on = line pulled LOW (fan sees LOW). So `duty_mcu = 100 − duty_wire`. D+ set via the `set_fan_speed()` helper; B5 statically driven at 1.4% MCU duty → 98.6% wire duty, mimicking the stock remote's keep-alive heartbeat.
- **ESP32 USB-C powered independently** — the fan's 9V VBUS rail does not connect to the ESP32. The only electrical bridge between the two domains is common GND + the two signal wires going through the MOSFETs.
- **D− (tach) left unconnected** in this revision. Optional future add: 10 kΩ pull-up from VBUS + 4.7 kΩ divider to GND + GPIO input, for closed-loop RPM feedback.

### 2N7000 pinout (TO-92)

Flat side (with "2N7000" marking) facing you, legs pointing down → **Source, Gate, Drain from left to right**.

```
   flat side facing YOU
          ___
         /   \
        | 2N  |
        |7000 |
         \___/
          |||
          SGD
```

Sanity-check with a multimeter in diode mode before soldering: the body diode conducts ~0.6V when red probe is on the **source** and black probe is on the **drain** (anode-at-source for an N-channel body diode); open in the reverse direction; open both ways between gate and either other leg. If any other combination conducts, the part is wired backwards or dead.

### Parts used on the combined board

| Part | Qty | Notes |
|------|-----|-------|
| ESP32-C3 SuperMini | 1 | USB-C powered. Same board as the plant nodes — fleet-uniform. Serves both fan-driver and tent-sensor roles. |
| 2N7000 N-channel MOSFET (logic-level, `Vgs(th)` ≤ 2.5V) | 2 | Q1 for D+, Q2 for B5. BSS138 is interchangeable. Any logic-level N-channel FET works. |
| 10 kΩ resistor | 2 | Gate pull-downs, one per MOSFET. 5–100 kΩ is fine; 10 kΩ is unremarkable. |
| Adafruit SHT45 + PTFE cap (product 5665) | 1 | I²C temp/RH sensor, addr `0x44`. 10 kΩ I²C pull-ups on-board — no external pull-ups needed. PTFE cap press-fits over the sensor window for mist/dust protection. |

Optional belt-and-suspenders (not currently populated): 220 Ω in series on each MOSFET gate line to limit inrush current into the gate capacitance at each PWM edge. Irrelevant at 5 kHz with a 2N7000, but harmless if you want them.

Ordered separately from the reverse-engineering kit below — these were not in the original shopping list.

## Tent environmental sensor (SHT45)

The Adafruit SHT45 rides on the same ESP32-C3 as the fan driver, eating the four I²C-available pins that the fan driver isn't using.

### Wiring

| SHT45 pad | ESP32-C3 pin | Notes |
|---|---|---|
| `VIN` | `3V3` | 3.3 V matches the ESP32 I²C logic level. The breakout also accepts 5 V via an on-board regulator — we don't use that path. |
| `GND` | common GND rail | Same rail the MOSFET sources + ESP32 GND tie into. |
| `SDA` | `GPIO 4` | Not GPIO 8 — GPIO 8 is the SuperMini's onboard LED + a boot-strap pin. GPIO 4 is the documented alternate I²C path; JTAG interference only matters for ADC reads, not driven I²C. |
| `SCL` | `GPIO 5` | Not GPIO 9 — GPIO 9 is the BOOT button + a strap pin. |

Library: `adafruit/Adafruit SHT4x Library` (pulls `Adafruit Unified Sensor` transitively). Class `Adafruit_SHT4x`; bring up with `sht.begin(&Wire)`, `sht.setPrecision(SHT4X_HIGH_PRECISION)`, `sht.setHeater(SHT4X_NO_HEATER)`. Read via `sht.getEvent(&humidity, &temp)`. Heater deliberately off by default; future work to pulse it once/hour if RH pins near 100 %.

The rationale for colocating with the fan driver (rather than the separate `tent_node` ESP32 in the original plan) is in the Status section at the top. No pin contention: fan uses GPIO 6/7, SHT45 uses GPIO 4/5, GPIO 10 is reserved for a future tach revisit. The obsolete `firmware/tent_node/` PIO project still exists on disk at time of writing; slated for deletion once the combined firmware has soaked for a few days.

## Reverse-engineering hardware (ordered 2026-04-18)

Used to characterize the protocol above. Retained afterward for future RE work on other UIS devices.

| Part | ASIN | Qty | Role |
|------|------|-----|------|
| minidodoca USB 3.1 Type-C M/F test board — 24-pin, 2.54mm headers | B0FLX671VF | 2 | **Inline analysis tap.** Sits between the fan's female USB-C port and the stock remote's male plug; all 24 pins broken out to headers for probing. |
| Treedix USB Type-C vertical female breakout board | B0D31GG6WD | 2 | **Permanent install interface.** Standard USB-C M-M cable plugs fan into the Treedix receptacle; Nano wires to broken-out headers. Stock remote is removed. |
| HiLetgo USB Logic Analyzer — 24 MHz, 8 channels, Cypress FX2 | B077LSG5P2 | 1 | PWM characterization. Works with sigrok/PulseView; appears as `fx2lafw` driver. |
| ElectroCookie Prototype PCB solderable breadboards — 5 full-size + 1 mini, gold-plated | B07ZYNWJ1S | 6 | Perma-proto boards. Originally ordered for a Nano rig; reused for the ESP32-C3 build. |
| Lonely Binary 2.54mm female header assortment kit | B0FFM2RBMB | 1 kit | Socket the MCU rather than solder it directly — lets us swap if the board dies. |

## Characterization method (for reference — already complete)

Three stages, executed 2026-04-20:

1. **Multimeter pre-flight.** Minidodoca passthrough inline between fan and stock remote, fan powered. Each header pin probed vs GND. Original probe (v1/v2 captures) identified three signal pins and concluded "all signals ≤5V → safe to clip into the HiLetgo" — this was wrong; the meter was mis-ranged or misread. The real signal amplitude is ~9V (see v3 re-measurement). The HiLetgo's input protection diodes absorbed the overvoltage without damage, but future probes on unknown UIS hardware must assume the signals track VBUS, not 5V.
2. **Logic analyzer capture.** sigrok-cli at 4 MHz sample rate on D0/D1/D2, 12-second then 20-second captures while sweeping the remote's speed dial. Earlier captures (`sweep-v2.sr`, `sweep-11steps.sr`) labeled D0 as "CC1" based on the wrong side of the dongle; re-capture 2026-04-21 (`sweep-v3.sr`) with the tap on the dongle-side pins corrected the mapping: **D0 = B5, D1 = D+, D2 = D−.** Protocol numbers (4,969 Hz carrier, duty ranges, tach frequency range) match across captures — only the pin name for channel 0 changed. Analysis scripts at `debug/fan-pwm/analyze.py` (all three channels) and `debug/fan-pwm/analyze_steps.py` (plateau detection on D+) still print the legacy "CC1" label; that's cosmetic and hasn't been rewritten.
3. **Topology check.** Unplugged stock remote with fan still powered; measured D+ = ~9V and fan ran at max. Confirmed open-drain with pull-up inside the fan. B5 behaves identically (floats high, pulled low by the remote during its LOW-pulse windows).

**Sigrok-cli gotcha:** `--channels D1` *filters* which channels are shown in CLI output but the `.sr` archive still contains all probed bits in their original bit positions. When decoding in Python, D+ is at bit 1 of each output byte, not bit 0. See `debug/fan-pwm/analyze_steps.py` for the correct extraction.

## Firmware

Canonical source: [`firmware/fan_controller/`](../../firmware/fan_controller/). PlatformIO project, single `env:fan` for USB flash over `/dev/ttyACM*`. Dual-role: LEDC PWM for D+/B5 on GPIO 6/7, I²C SHT45 reads on GPIO 4/5. Same ESP32-C3 Arduino platform as the plant nodes — once WiFi/OTA/ingest are added, it'll consume the shared libs at `firmware/common/{wifi_client, ota, ingest_client}/`.

Current firmware (fw `0.1.0`) holds the fan at `HOLD_SPEED_PCT` (currently 30 %) and prints a combined heartbeat line every `HEARTBEAT_MS` (currently 60 s). Example:

```
[   60077 ms] fan=30% (D+ wire=45.4%)  |  tent: 22.70°C (72.9°F)  RH 38.9%  VPD 1.69 kPa
```

No WiFi, no ingest, no persistence yet. If the SHT45 drops mid-flight the fan keeps running unaffected — the sensor is strictly additive. Next firmware milestone: fold in `firmware/common/{wifi_client, ota, ingest_client}/` so the host can (a) command speed via ingest and (b) receive tent temp/RH/VPD into `sensorreading` under the existing `SensorLocation.TENT` enum value (source becomes `esp32` instead of the Arduino's `arduino`).

## Permanent install

- ESP32-C3 SuperMini on an ElectroCookie perma-proto board, socketed with appropriate female headers for the SuperMini footprint (not soldered directly; lets us swap if the board dies).
- Fan interface via the Treedix vertical female USB-C breakout: plain USB-C M-M cable from fan lands in the Treedix receptacle; ESP32 GPIO 6 → Q1 gate → Q1 drain to D+ pad; ESP32 GPIO 7 → Q2 gate → Q2 drain to B5 pad.
- Fan GND and ESP32 GND tied together at the perma-proto GND rail.
- **B5 driven from the start** (1.4% MCU duty → 98.6% wire duty, mimicking the stock remote's keep-alive). Open question: whether B5 is actually required — the bring-up sweep 2026-04-22 ran successfully with B5 driven; whether the fan would also accept D+ commands with B5 floating is untested. If we want to know definitively, cut power to Q2 (or command GPIO 7 static-low → B5 floats high continuously via the fan's internal pull-up) and see if the fan still responds. Not a priority.
- D− (tach) is unconnected. Adding it later is cheap: VBUS → 10 kΩ → D−, plus D− → 4.7 kΩ → GND (divider brings the 9V swing down to ~2.88V which is safely inside the ESP32's input range), feed into a GPIO with interrupt support, count rising edges → RPM.

## Bring-up validation (2026-04-22)

Initial fan bring-up (16:35–16:37 MDT): flashed smoke-test firmware, ran `fan=20%` / `fan=40%` alternation, then a full-range sweep. Later the same day: tach-divider attempt (failed — see below), then SHT45 integration on the same board (succeeded).

| Checkpoint | Observed | Notes |
|---|---|---|
| Boot failsafe (D+ floats via 9V internal pull-up) | ~2 s max-speed blast | Q1 off while firmware starts up — confirms the pull-down keeps the MOSFET dormant |
| `fan=0%` commanded | Fan silent / off | Q1 can hold D+ fully LOW — rules out a stuck-off MOSFET |
| `fan=10%` → `20%` | Audible kick-in | Wire duty 29.8% → 37.6%; above the 22% stall threshold; motor spins cleanly |
| Stepped ramp up 20% → 100% | Clean, monotonic | No dead spots, no uneven jumps — speed→RPM looks linear in the commanded range |
| `fan=100%` (in sweep) | Same as boot blast | Symmetric behavior; no asymmetry between "floating high" and "commanded high" |
| Sustained operation through full cycle | Fan keeps accepting commands | Indirect evidence B5 keep-alive is either doing its job or isn't required at all |
| D− tach divider (10 kΩ / 4.7 kΩ) | Zero edges counted, D− DC = 0.71 V | Weaker fan-side pull-up than reverse-engineering implied; divider loaded D− HIGH down to ~1.4 V on the wire (GPIO saw ~0.45 V, below HIGH threshold). Tach deferred. |
| SHT45 begin + first read | `begin()` ok; first heartbeat `22.70°C / 72.9°F / RH 38.9% / VPD 1.69 kPa` | Sensor reading plausible for room air (board not yet inside the tent). Serial returned 0x00000000 — known Adafruit library quirk; doesn't affect measurement. |

No thermal check performed yet; to verify long-term safety, touch-check each 2N7000 after 10+ minutes at mid-speed.

## Future integration (out of scope for this page)

Next firmware milestone: fold `firmware/common/{wifi_client, ota, ingest_client}/` into the fan_controller build so the host can command speed over the ingest path and we get OTA reflash via `fan-controller.local`. Once that's in, closed-loop VPD control pairs this with the humidifier — see [Humidifier Control](humidifier-control.md) for the target architecture and [multi-actuator environment control](../concepts/multi-actuator-environment-control.md) for the broader design principles (2D target zones, cascaded SISO, feedforward on lights).
