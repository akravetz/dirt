---
title: "Concept — Capacitive Soil Moisture Sensors (v1.2 + v2.0)"
type: concept
sources: []
related: [wiki/hardware/esp32-plant-nodes.md, wiki/decisions/2026-04-14-server-side-auto-calibration.md]
created: 2026-04-14
updated: 2026-04-16
---

# Capacitive Soil Moisture Sensors

The generic "Capacitive Analog Soil Moisture Sensor" sold on Amazon/AliExpress is a 555-timer-based oscillator that turns soil moisture into an analog voltage. Same PCB shape across many different sellers; output behavior is broadly consistent across clones but varies by generation (v1.2 vs v2.0).

## How It Works

1. The probe (the forked PCB tines) forms one plate of a capacitor. The surrounding medium (soil, water, air) is the dielectric.
2. Wetter medium → higher dielectric constant → higher capacitance at the probe.
3. The 555 timer oscillates at a frequency set by that capacitance — higher C → lower frequency.
4. A comparator circuit converts the oscillator frequency into a DC voltage on AOUT.
5. **Higher moisture = lower AOUT voltage.** This is counterintuitive and catches people off guard.

## v1.2 vs v2.0

Both versions use the same 555-timer principle, but the onboard electronics differ:

| Aspect | v1.2 | v2.0 |
|---|---|---|
| Voltage regulation | No onboard regulator — runs directly off VCC. Switching 3.3V/5V needs a solder-jumper swap. | LDO regulator (662K / XC6206 family) auto-adapts to **3.3–5.5V** input. |
| AOUT range (claimed) | ~0–3.0 V | ~0–2.3 V (per some resellers) |
| AOUT range (measured, this grow) | ~0.4–2.5 V | **~0.9–2.76 V** (confirmed with multimeter 2026-04-16) |
| PCB coating | Typically uncoated | Typically ships with water-resistant coating |
| Oscillator | TLC555 variant at ~1.5 MHz, 34% duty | Similar, sometimes cheaper 555 clones |

**The "v2.0 caps at 2.3 V" claim in some reseller docs doesn't match our hardware.** Our v2.0 sensors output up to 2.76 V in dry air. Amazon/AliExpress clone "v2.0" boards vary — don't trust the reseller datasheet; confirm with a multimeter.

**For this grow:** plant-a and plant-d are on v1.2; plant-b and plant-c are on v2.0. The server-side auto-calibration normalizes over the voltage-range differences, so cross-plant wet% comparisons work correctly even with mixed hardware. Raw ADC values are **not** cross-comparable.

## Expected Voltage Ranges (3.3V supply, measured on this grow)

| Condition | v1.2 AOUT | v1.2 raw ADC | v2.0 AOUT | v2.0 raw ADC |
|---|---|---|---|---|
| Dry air | ~2.0–2.5 V | ~2500–2850 | ~2.7–2.8 V | **~3800–3900** (see ADC quirk below) |
| Field-capacity coco | ~1.0–1.5 V | ~1250–1850 | ~1.4–1.8 V | ~1500–2100 |
| Submerged to insertion line | ~0.1–0.5 V | ~150–650 | ~0.9–1.1 V | ~1380–1400 |

**ESP32-C3 ADC non-linearity note:** the C3's ADC1 at 11 dB attenuation over-reports by 200–400 counts above ~2.5 V input. A v2.0 sensor outputting a real 2.76 V (multimeter-verified) reads as raw **~3800** (not the linear-math ~3425). This is expected and documented — do not interpret raw 3800 on a v2.0 sensor as a floating-pin fault. Floating pins usually rail at 4095 and are persistent; real 3800 readings drop cleanly when the sensor hits water.

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
