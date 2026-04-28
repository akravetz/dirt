---
title: "Hardware — Reservoir Level: Bench Bring-up Notes (2026-04-26)"
type: hardware
sources: []
related: [wiki/hardware/reservoir-level.md, wiki/decisions/2026-04-18-reservoir-level-pressure-transducer.md]
created: 2026-04-26
updated: 2026-04-26
---

# Reservoir Level — Bench Bring-up (2026-04-26)

End-to-end signal chain validated: Probe → 4–20 mA loop → SEN0262 → ADS1115 (GAIN_FOUR, 32-sample averaging) → I²C 0x48 → ESP32-C3 SuperMini → USB serial.

See [reservoir-level.md](reservoir-level.md) for the deployment status, BOM, and current calibration constants.

## Wiring (matches the [DFRobot KIT0139 reference diagram](https://wiki.dfrobot.com/kit0139/))

- 12V brick `+` → SEN0262 top screw terminal (loop `+`)
- SEN0262 bottom screw terminal (loop `−`) → probe **brown** (V+)
- Probe **blue** (V−) → 12V brick `−`
- SEN0262 Gravity `VCC` (red) → ESP32-C3 5V pin
- SEN0262 Gravity `GND` (black) → ESP32-C3 GND
- SEN0262 Gravity `Signal` (blue) → ADS1115 A0
- ADS1115 VDD/GND/SDA/SCL/ADDR → ESP32-C3 5V/GND/GPIO4/GPIO5/GND

The brick GND and the ESP32 GND are tied through the SEN0262 Gravity GND pin (the SEN0262 is a non-isolated converter and bridges its loop-side ground to its signal-side ground internally). Don't run a separate ground wire — that one cable is the bridge.

## Provisional two-point calibration (bench)

Captured with the bench firmware (`firmware/reservoir_node/`, env `reservoir-bench`, GAIN_FOUR + 32-sample averaging):

| Cal point | Probe state | Mean voltage | Mean raw count |
|---|---|---|---|
| 0 cm head | Probe in dry air at tank-top height | 0.5793 V | 18,540 |
| 64.5 cm head | Probe suspended ~1 cm above tank floor, 25.8 in of water in tank | 0.8146 V | 26,069 |

**Provisional line:** `depth_cm = (raw_count − 18540) / 116.7` (≈ 3.65 mV per cm, ≈ 117 ADS counts per cm).

This is NOT the production cal — it skips the wiki-spec procedure (mount in final position; fill to a tape-measured reference depth; wait 30 min; verify with a third independent point). Exists to prove the math and give the firmware sane initial constants. **Superseded by the 2026-04-26 final-mount cal in [reservoir-level.md](reservoir-level.md).**

## Noise characterization

| Configuration | Per-second jitter |
|---|---|
| Single-sample reads at GAIN_TWOTHIRDS (default) | ~140 mV peak-to-peak |
| 32-sample averaging at GAIN_FOUR (current bench fw) | ~9 mV peak-to-peak (~9 mm equivalent depth) |

The 32-sample average reduces jitter ~5.7× vs single-sample. Electronics are now tighter than the probe's own ±25 mm absolute accuracy — noise floor is no longer limiting. Server-side rolling 5–10 min averages will pull reported values into sub-mm precision.

## Capacitor experiment (failed — recorded for posterity)

Tried adding a 10 µF ceramic across A0 → GND to filter brick switching noise. Result: jitter **tripled** (140 mV → 400 mV peak-to-peak) and center voltage shifted down ~100 mV. Almost certainly op-amp instability — the SEN0262's output stage doesn't tolerate a 10 µF direct capacitive load and starts ringing. A proper RC filter (small series resistor between op-amp output and cap) would isolate the cap from the feedback loop, but we didn't have a resistor on the bench. Removed the cap; firmware-side averaging does the noise reduction we need. Revisit only if production deployment shows residual brick-switching artifacts that averaging can't suppress.
