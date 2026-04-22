---
title: Hardware — AC Infinity Cloudline LITE 6" Fan Control
type: hardware
sources: [debug/fan-pwm/sweep-v2.sr, debug/fan-pwm/sweep-11steps.sr]
related: [wiki/hardware/humidifier-control.md]
created: 2026-04-18
updated: 2026-04-20
---

# AC Infinity Cloudline LITE 6" Fan Control

**Status (2026-04-20):** protocol characterized end-to-end; circuit designed; test firmware written. Speed signal, pinout, voltage levels, and electrical topology all confirmed via logic-analyzer capture + multimeter. **Waiting on 2N7000 MOSFET delivery (overnight)**; 10 kΩ gate resistor on hand. Rendered schematic at `debug/fan-pwm/driver-schematic.png` (source: `debug/fan-pwm/schematic.py`). Standalone test sketch at `debug/fan-pwm/fan_drive_test/fan_drive_test.ino` — ramps fan duty 0 → 100% in 10% steps, dwells 3 s each, loops. Meant to flash on a spare Nano for the first bring-up; once validated, the logic folds into the main firmware.

## Goal

Drive the Cloudline LITE 6" inline fan from an Arduino Nano (controlled by the Dirt stack) instead of AC Infinity's stock wired speed controller. End state: programmatic fan speed, scheduled ramps, closed-loop VPD coupling with the humidifier — without routing any control through AC Infinity's ecosystem.

## Protocol (confirmed 2026-04-20)

Three meaningful signals on the USB-C connector. All share a common GND and a 10V VCC rail.

| USB-C pin | Direction | Signal | Details |
|---|---|---|---|
| **D+** | remote → fan | **PWM speed command** | 4,969 Hz carrier, open-drain (see topology below). Duty-cycle maps to fan speed per the table below. |
| **D−** | fan → remote | **Tachometer output** | 50%-duty square wave whose *frequency* is proportional to RPM. ~45 Hz at min speed, ~137 Hz at max. Assuming 2 pulses/rev, that's ~1,350 RPM min, ~4,100 RPM max. |
| **CC1** | remote → fan | Clock / keep-alive | Same 4,969 Hz carrier as D+, but stuck at 98.6% duty regardless of speed. Likely a "remote connected" heartbeat. Appears ignorable — first Nano test drives D+ only with CC1 floating. |
| VBUS | — | +10V rail | Powers the fan's control electronics. Do **not** clip a 5V-tolerant logic analyzer to this. |
| D+ pin label note | | | On the minidodoca breakout, D+ is labeled `A5` on the silkscreen — that's the USB-C spec-A-side pin number for D+, not a separate signal. |

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
- Recommended Nano API: `fan.set_speed(pct)` where `pct=0` → 0% duty (off) and `pct=1..100` → linearly remapped to 22%–100% duty (protects against the stall zone).

### Electrical topology

**D+ is open-drain with the pull-up inside the fan.** Confirmed 2026-04-20: with the stock remote unplugged, D+ floats to ~9V (the fan's internal pull-up to its ~10V VCC) and the fan runs at max speed (reads 100% duty because nothing is pulling low).

Implication: **the Nano does not need to source 9V** — it only needs to pull D+ to GND at the right times. A single small N-channel MOSFET (or NPN) between D+ and GND, gate driven by the Nano's 5V PWM pin, is sufficient.

**Failsafe behavior:** if the Nano loses power, resets, or crashes, D+ floats → fan runs at 100%. For a grow tent this is the safer direction; overventilation won't kill plants, whereas a stalled fan in a sealed tent eventually will. We are intentionally leaning into this behavior rather than engineering around it.

## Nano driver circuit

Single N-channel logic-level MOSFET. ~$0.50 in parts.

```
  D+ (fan USB-C via Treedix) ─────┐
                                  │ drain
                          [2N7000 N-ch MOSFET]
                                  │ source
  GND (fan) ─────────────── common GND ─────── GND (Nano)
                                  │
  Nano pin 9 ─────────────────────┤ gate
                                  │
                              [10 kΩ]
                                  │
                               GND (pull-down)
```

- **Drain → D+** on the Treedix breakout.
- **Source → common GND.** Fan GND and Nano GND must be tied together; otherwise the MOSFET has no reference.
- **Gate → Nano pin 9.** Timer1 fast-PWM gives a clean 5 kHz output; the default `analogWrite()` 490 Hz is ~10× too slow and will likely confuse the fan MCU.
- **10 kΩ gate-to-source pull-down.** Keeps the MOSFET OFF during Nano reset/boot (gate would otherwise float, causing a few ms of random D+ pull-downs).
- **Signal is inverted in firmware.** Nano HIGH = MOSFET on = D+ pulled LOW (fan sees LOW). So `duty_nano = 100 − duty_fan`.

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

### Parts used for the driver

| Part | Qty | Notes |
|------|-----|-------|
| 2N7000 N-channel MOSFET (logic-level, `Vgs(th)` ≤ 2.5V) | 1 | BSS138 is interchangeable. Any logic-level N-channel FET works. |
| 10 kΩ resistor | 1 | Gate pull-down. 5–100 kΩ is fine; 10 kΩ is unremarkable. |

Ordered separately from the reverse-engineering kit below — these were not in the original shopping list.

## Reverse-engineering hardware (ordered 2026-04-18)

Used to characterize the protocol above. Retained afterward for future RE work on other UIS devices.

| Part | ASIN | Qty | Role |
|------|------|-----|------|
| minidodoca USB 3.1 Type-C M/F test board — 24-pin, 2.54mm headers | B0FLX671VF | 2 | **Inline analysis tap.** Sits between the fan's female USB-C port and the stock remote's male plug; all 24 pins broken out to headers for probing. |
| Treedix USB Type-C vertical female breakout board | B0D31GG6WD | 2 | **Permanent install interface.** Standard USB-C M-M cable plugs fan into the Treedix receptacle; Nano wires to broken-out headers. Stock remote is removed. |
| HiLetgo USB Logic Analyzer — 24 MHz, 8 channels, Cypress FX2 | B077LSG5P2 | 1 | PWM characterization. Works with sigrok/PulseView; appears as `fx2lafw` driver. |
| ElectroCookie Prototype PCB solderable breadboards — 5 full-size + 1 mini, gold-plated | B07ZYNWJ1S | 6 | Perma-proto boards for the Nano rig. |
| Lonely Binary 2.54mm female header assortment kit | B0FFM2RBMB | 1 kit | 2× 1x15 to socket the Nano (don't solder the Nano directly — lets us swap if one dies). |

## Characterization method (for reference — already complete)

Three stages, executed 2026-04-20:

1. **Multimeter pre-flight.** Minidodoca passthrough inline between fan and stock remote, fan powered. Each header pin probed vs GND. VCC read 10V; three pins showed signal (labeled `A5`/D+, D+, D−). All signals confirmed ≤5V → safe to clip into the HiLetgo.
2. **Logic analyzer capture.** sigrok-cli at 4 MHz sample rate on D0=CC1, D1=D+, D2=D−, 12-second then 20-second captures while sweeping the remote's speed dial. Captures saved at `debug/fan-pwm/sweep-v2.sr` and `debug/fan-pwm/sweep-11steps.sr`. Analysis scripts at `debug/fan-pwm/analyze.py` (all three channels) and `debug/fan-pwm/analyze_steps.py` (plateau detection on D+).
3. **Topology check.** Unplugged stock remote with fan still powered; measured D+ = ~9V and fan ran at max. Confirmed open-drain with pull-up inside the fan.

**Sigrok-cli gotcha:** `--channels D1` *filters* which channels are shown in CLI output but the `.sr` archive still contains all probed bits in their original bit positions. When decoding in Python, D+ is at bit 1 of each output byte, not bit 0. See `debug/fan-pwm/analyze_steps.py` for the correct extraction.

## Permanent install

- Arduino Nano on one ElectroCookie perma-proto board, socketed with 2× 1x15 female headers (not soldered directly).
- Fan interface via the Treedix vertical female USB-C breakout: plain USB-C M-M cable from fan lands in the Treedix receptacle; Nano's pin-9 → MOSFET gate → drain to D+.
- Fan GND and Nano GND tied together at the perma-proto.
- CC1 left floating for the first test. If the fan refuses to respond to D+ alone, revisit and drive CC1 at 98.6% duty on a second Nano pin.
- D− (tach) can optionally wire to a Nano interrupt pin (D2 or D3) for closed-loop RPM feedback. Not required for basic control.

## Future integration (out of scope for this page)

Once standalone Nano control works, expose a simple HTTP or serial API from the Nano so the main Dirt host can send speed commands based on temp / humidity / VPD state — mirroring the ESP32-C3 plant nodes. Closed-loop VPD control will pair this with the humidifier (see [Humidifier Control](humidifier-control.md)).
