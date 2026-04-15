---
title: "Concept — Capacitive Soil Moisture Sensors (v1.2)"
type: concept
sources: []
related: [wiki/hardware/esp32-plant-nodes.md, wiki/decisions/2026-04-14-server-side-auto-calibration.md]
created: 2026-04-14
updated: 2026-04-14
---

# Capacitive Soil Moisture Sensors

The generic "Capacitive Analog Soil Moisture Sensor v1.2" sold on Amazon/AliExpress is a 555-timer-based oscillator that turns soil moisture into an analog voltage. Same PCB design, many different sellers; output behavior is broadly consistent across clones.

## How It Works

1. The probe (the forked PCB tines) forms one plate of a capacitor. The surrounding medium (soil, water, air) is the dielectric.
2. Wetter medium → higher dielectric constant → higher capacitance at the probe.
3. The 555 timer oscillates at a frequency set by that capacitance — higher C → lower frequency.
4. A comparator circuit converts the oscillator frequency into a DC voltage on AOUT.
5. **Higher moisture = lower AOUT voltage.** This is counterintuitive and catches people off guard.

## Expected Voltage Ranges (3.3V supply)

| Condition | AOUT (rough) | Raw ADC (12-bit, 11dB atten) |
|---|---|---|
| Dry air | ~2.0–2.5V | ~2500–3100 |
| Field-capacity coco | ~1.0–1.5V | ~1250–1850 |
| Submerged (probe in water, up to insertion line) | ~0.4–0.6V | ~500–750 |

These are ballpark; each unit varies ±15%. Calibrate per sensor (or use [server-side auto-calibration](../decisions/2026-04-14-server-side-auto-calibration.md)).

## Calibration

Two-point linear. Record `raw_dry` (sensor in air) and `raw_wet` (submerged). Convert raw readings to percentage:

```
pct = 100 × (raw_dry − raw) / (raw_dry − raw_wet)
```

Clamp to [0, 100]. In our stack we name these `raw_high` (dry) and `raw_low` (wet) to describe the ADC values directly rather than the physical condition. Calibration is **always per-sensor** — two different units in the same water will read differently due to manufacturing variation.

## Supply Voltage

Rated **3.3–5.5V**. The v1.2 is designed around 5V; at 3.3V the usable output range is narrower (still workable). We use **3V3 on the ESP32** because:
- Running at 5V can push AOUT above the ESP32's 3.3V-safe ADC range, which forces current through the ESP32's ESD clamp diodes every time the sensor swings high.
- The ESP32 is protected, but the sensor's output stage is stressed; suspected in some DOA sensors we accumulated during early debugging.

## Failure Modes and Diagnostics

### 1. Sensor output stuck at 0V

Most common failure. 555 oscillator dead (or unpowered); comparator output pinned near ground. Indistinguishable from "sensor unpowered" without diagnostics.

**Multimeter check (takes 30s):**
- Probe AOUT-to-GND, sensor powered, in dry air.
- Alive: ~1.5–2.5V.
- Dead: 0V (regardless of moisture).

Do this **before** wiring to the ESP32 — our current pack had a 60% DOA rate.

### 2. Sensor unpowered

VCC wire isn't making contact (bad dupont crimp, loose header). Symptom: AOUT reads near 0V because the 555 isn't oscillating.

**Check:** multimeter from sensor's VCC pad to sensor's GND pad. Should match the supply (3.3V).

### 3. Conformal coating ingress on pins

Silicone coating is deliberately non-conductive. If it creeps onto the 3-pin header (easy to happen when coating the PCB edges), dupont female sockets push onto the pins but make no electrical contact.

**Symptom:** looks identical to "unpowered" above.

**Fix:** scrape coating off pin surfaces with a fingernail or X-Acto blade, or soak in 99% IPA with a cotton swab. Mask the pins before coating in the future.

### 4. Probe not submerged to the insertion line

The white line printed across the PCB marks how deep the probe needs to go for full capacitive coupling. Dipping only the tip gives almost no reading swing — the sensor looks broken but is just under-immersed.

### 5. Slow water → air discharge

After removing from water, the sensor can take **30+ seconds** to settle at the dry value. Going air → water is fast (seconds). A forum hypothesis blames a missing R4 ground connection on some clone batches; either way, budget discharge time when calibrating.

## Design Notes for the Grow

- **Conformal-coat the PCB edges** above the insertion line to prevent moisture wicking up the FR4 and killing the board. Mask the pin header first.
- **Sanity-check with a multimeter before deployment** — our recent pack had 3/5 DOA.
- **Expect 5–15% reading differences** between sensors in the same pot. For per-plant comparisons, calibrate each sensor individually; for trending ("drying out vs yesterday") a single sensor's history is self-consistent without tuning.
