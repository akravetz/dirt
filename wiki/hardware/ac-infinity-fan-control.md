---
title: Hardware — AC Infinity Cloudline LITE 6" Fan Control
type: hardware
sources: []
related: [wiki/hardware/humidifier-control.md]
created: 2026-04-18
updated: 2026-04-18
---

# AC Infinity Cloudline LITE 6" Fan Control

**Status (2026-04-18):** reverse-engineering phase, hardware ordered and in transit. Nothing captured or wired yet.

## Goal

Drive the Cloudline LITE 6" inline fan from an Arduino Nano (controlled by the Dirt stack) instead of AC Infinity's stock wired speed controller. End state: programmatic fan speed, scheduled ramps, closed-loop VPD coupling with the humidifier — without routing any control through AC Infinity's ecosystem.

## What we know

- **Signaling is PWM.** The stock wired speed controller's back label explicitly says "PWM signal." High-confidence working assumption: a single PWM line over the fan's USB-C connector encodes speed via duty cycle. No multi-byte protocol, no UART framing — just frequency + duty cycle on one pin relative to ground.
- **USB-C is physical convention only.** AC Infinity's "UIS" uses a standard USB-C connector body but with proprietary pin assignments — not USB at all. Prior-probability-ranked signal-pin candidates:
  1. **SBU1 / SBU2** — USB-C's explicit "sideband use" pins, designed exactly for this.
  2. **CC1 / CC2** — less likely, since CC has defined USB-C semantics.
  3. **D+ / D−** — least likely.
- **PWM voltage swing is unknown** (probably 3.3V or 5V). Multimeter pre-flight answers this.
- **Arduino Nano has native PWM** on D3/D5/D6/D9/D10/D11 via `analogWrite` (~490 Hz default). If the fan's PWM frequency is higher, direct Timer1/Timer2 register manipulation is the fallback.

## Hardware on hand (ordered 2026-04-18)

All items below were purchased for this project. Does **not** include assumed-on-hand items (multimeter, Arduino Nano with pre-soldered male pins, soldering iron, thin-gauge wire, USB-A cable for Nano programming, basic jumper wires).

| Part | ASIN | Qty | Role |
|------|------|-----|------|
| minidodoca USB 3.1 Type-C M/F test board — 24-pin, 2.54mm headers | B0FLX671VF | 2 | **Inline analysis tap.** Sits between the fan's female USB-C port and the stock remote's male plug; all 24 pins broken out to headers for probing with multimeter + logic analyzer. |
| Treedix USB Type-C vertical female breakout board | B0D31GG6WD | 2 | **Permanent install interface.** A standard USB-C M-M cable plugs the fan into the Treedix female receptacle; Nano wires to the broken-out headers. Stock remote is removed. |
| HiLetgo USB Logic Analyzer — 24 MHz, 8 channels, Cypress FX2 | B077LSG5P2 | 1 | Identifies the PWM signal pin and measures frequency + duty cycle. Works with PulseView / sigrok. 5V-tolerant inputs. |
| ElectroCookie Prototype PCB solderable breadboards — 5 full-size + 1 mini, gold-plated | B07ZYNWJ1S | 6 | Perma-proto boards for the permanent Nano rig. |
| Lonely Binary 2.54mm female header assortment kit — 160 pcs (2/3/4/6/8/10/15/19/20/22-pin) | B0FFM2RBMB | 1 kit | Female headers to socket the Nano onto the perf board (2× 1x15 per Nano; don't solder the Nano directly — lets us swap if one dies). |

## Reverse-engineering approach

Three stages. Each informs the next.

1. **Multimeter pre-flight (safety + narrow candidates).** With one minidodoca passthrough inline (fan ↔ passthrough ↔ remote), fan powered on, probe each header pin vs GND at both min- and max-knob positions. Two outcomes in one pass:
   - **Safety check:** no pin should exceed 5V. If any does, stop and assess before connecting the logic analyzer (the HiLetgo's inputs are 5V-tolerant; more than that fries it).
   - **Candidate narrowing:** the PWM-carrying pin will show a *changing* DC average between knob extremes (because the multimeter averages the PWM waveform into a duty-cycle-proportional DC reading). Other pins stay flat.

2. **Logic analyzer capture.** Clip the 7 unique candidate channels onto the header (SBU1, SBU2, CC1, CC2, D+, D−, and optionally VBUS — VBUS is power, not data, and can be skipped). Analyzer GND must connect to breakout GND. Capture a knob sweep in PulseView. One channel will show a clean PWM square wave with visibly changing duty cycle — that's the signal. Record: (a) which pin, (b) frequency, (c) duty cycle at min / max / a couple of intermediate knob positions.

3. **Cross-check for secondary signals.** Note whether any other channel is active during the capture. Some designs pair a PWM with an "enable" or direction line; if present, we'll need to drive that too.

## Permanent install (after characteristics confirmed)

- Arduino Nano on one ElectroCookie perma-proto board.
- Nano socketed with **2× 1x15 female headers** from the Lonely Binary kit (not soldered directly).
- Fan interface via the Treedix vertical female USB-C breakout: a plain USB-C M-M cable from the fan lands in the Treedix receptacle; Nano's PWM pin + common GND wire to the identified signal header pin.
- Level shifter only if the Nano's 5V PWM exceeds the fan's signal input tolerance (unknown until capture). If the fan signals at 3.3V and accepts the same, a simple resistor divider on the Nano's output is enough.

## Open questions (resolved by the capture)

- PWM frequency (Nano `analogWrite` 490 Hz vs. direct-timer higher-frequency required?).
- PWM voltage swing (3.3V? 5V?) and whether a level shifter is needed.
- Duty-cycle range from knob min → max (the mapping for our own control code).
- Whether a secondary enable/direction signal exists.

## Future integration (out of scope for this page)

Once standalone Nano control works, expose a simple HTTP or serial API from the Nano so the main Dirt host can send speed commands based on temp / humidity / VPD state — mirroring the ESP32-C3 plant nodes. Closed-loop VPD control will pair this with the humidifier (see [Humidifier Control](humidifier-control.md)).
