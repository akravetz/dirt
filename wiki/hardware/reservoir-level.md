---
title: "Hardware — Reservoir Level (Autopot, hydrostatic pressure transducer)"
type: hardware
sources: []
related: [wiki/concepts/autopot.md, wiki/decisions/2026-04-18-reservoir-level-pressure-transducer.md, wiki/decisions/2026-04-11-reservoir-stand.md, wiki/hardware/esp32-plant-nodes.md]
created: 2026-04-18
updated: 2026-04-26
---

# Reservoir Level (Autopot 25-gal FlexiTank Pro)

Continuous water-level telemetry on the Autopot reservoir, so consumption rate, refill timing, and "you're about to run dry while away" alerts are all derivable from data instead of by lifting the lid.

Method: **submerged hydrostatic pressure transducer** at the bottom of the tank. Water depth is linearly proportional to the pressure on the diaphragm — no moving parts, no float arms, no contact with surface optics. The probe sits in the nutrient solution permanently.

## Deployment Status

| Component | Status | Notes |
|-----------|--------|-------|
| DFRobot KIT0139 pressure transducer | ✅ Received 2026-04-26, bench-tested | Submersible 316L stainless probe, 5m cable, 4–20mA loop output, 0–5m H₂O range. Confirmed 4 mA dry-air baseline on the multimeter. |
| 4–20mA → 0–5V converter | ✅ Bench-tested | DFRobot SEN0262 (shipped in the KIT0139 box). **Note**: this rev's actual output mapping is **not** a clean 4 mA → 0 V; measured ~0.58 V at the 4 mA loop floor and ~0.81 V at 64.5 cm head, which back-extrapolates to roughly 0 mA → 0.12 V, 20 mA → 2.4 V. Doesn't match either the "0–3 V" or "0–5 V" datasheet variants — has a built-in offset. Doesn't matter for our depth math (we calibrate the line we measure), but worth flagging so the next person doesn't predict 0 V at 4 mA like the original BOM did. Discrete precision-shunt alternative still deferred to v2. |
| ADS1115 16-bit I²C ADC | ✅ Bench-tested 2026-04-26 | Adafruit breakout, ADDR→GND → I²C address 0x48. Powered from ESP32-C3 5 V rail (no level shifters needed — the breakout handles 3.3V I²C from the C3). Reads cleanly at GAIN_FOUR (±1.024 V FS, 31.25 µV/count) — see "Bench bring-up" below. |
| 12V DC supply for transmitter | ✅ In service 2026-04-26 | Security-01 12V/1A UL-listed regulated brick, 5.5×2.1 mm barrel center-positive. Dedicated to the loop + node — not shared with the LED rail. [Amazon B01DB91P46](https://www.amazon.com/100-240V-Supply-Adapter-Barrel-Camera/dp/B01DB91P46) |
| ESP32-C3 SuperMini node | ⏳ On bench, USB-powered | Same board family as the plant nodes; new dedicated node, working name `dirt-reservoir.local` (location label `reservoir`, IP TBD). Bench bring-up complete with the test sketch in `firmware/reservoir_node/` env `reservoir-bench`. Not yet on WiFi. |
| Firmware | ⏳ Bench validated, production WIP | `firmware/reservoir_node/` PIO project exists. Bench bring-up complete on the test sketch (USB-only, no WiFi, raw counts to serial). The production env (WiFi + ingest POST every 30 s, OTA, both `reservoir_pressure_raw` and pre-converted `reservoir_depth_cm`) is in progress, mirroring the SHT45/tent pattern (firmware does the conversion in-flight, server stores values as-is). |
| Server-side ingest | ✅ Existing path works | `POST /api/ingest/sensors` already accepts arbitrary `(location, metric, value)` triples — no schema change needed; lands as `location="reservoir"`, `metric="reservoir_in"` and `metric="reservoir_pressure_raw"`. |

## Bill of Materials

| Qty | Part | Purpose | Source |
|----:|------|---------|--------|
| 1 | DFRobot KIT0139 submersible pressure transducer + SEN0262 4–20mA→V converter | Sensing element + signal conditioner | [dfrobot.com product-1863](https://www.dfrobot.com/product-1863.html) |
| 1 | Security-01 12V/1A UL-listed power adapter, 5.5×2.1 mm barrel | Powers the 4–20mA loop and feeds the node's buck | [Amazon B01DB91P46](https://www.amazon.com/100-240V-Supply-Adapter-Barrel-Camera/dp/B01DB91P46) — **purchased 2026-04-25** |
| 1 | 5.5×2.1 mm female barrel pigtail w/ screw terminals | Lands the brick's bare wires into the loop / buck without cutting the adapter cord | Amazon (any 5-pack, ~$6) |
| 1 | 12V→5V buck converter (e.g. mini-360) | Feeds 5V to the ESP32-C3 SuperMini from the same brick | Amazon (any 3-pack, ~$8) |
| 1 | ADS1115 16-bit I²C ADC breakout | Clean ADC for the 0–5 V SEN0262 output (sidesteps the C3's native ADC) | Adafruit / Amazon |
| 1 | ESP32-C3 SuperMini | WiFi MCU; new node `dirt-reservoir.local`, location label `reservoir` | On-hand (same family as plant nodes) |
| 1 | M16 cable gland (or similar) | Tank-lid pass-through for the probe cable + atmospheric vent | Amazon |
| — | Project box (small IP54 enclosure, ~80×60×40 mm) | Houses the SEN0262 + ADS1115 + ESP32 outside the tank, dry side of the cable vent | Any |
| — | Hookup wire, 22 AWG, 4-conductor (red / black / SDA / SCL) | Probe-to-enclosure I²C and power | On-hand |

Loop draw is ~20 mA + node ~150 mA peak ≈ 200 mA total — the 1 A brick has 5× headroom. Do **not** upsize to a 2 A brick; bigger supplies tend to ripple harder on a precision analog rail.

## Hardware

### DFRobot KIT0139 Submersible Pressure Transducer

| Spec | Value |
|------|-------|
| Output | 4–20 mA current loop |
| Supply | 12–36 V DC |
| Range | 0–5 m water column |
| Accuracy | ±0.5% FS |
| Cable | 5 m, sealed |
| Probe body | 316L stainless steel diaphragm, 304 stainless casing |
| Protection | IP68 (designed for permanent submersion) |
| Operating temp | -20 °C to 70 °C |

Product page: https://www.dfrobot.com/product-1863.html.

#### Range vs reservoir depth — resolution caveat

The 25-gal FlexiTank Pro turns out to be **substantially taller than the 13" estimate** in the original BOM. Hand-measured during bench bring-up on 2026-04-26: **25.8 in (65.5 cm) of water in the tank without it being filled to the brim**, so the usable depth is at least 65 cm and probably closer to 70 cm when topped off. With a 0–5 m sensor we exercise **the bottom ~13–15%** of the probe's full scale (not 10% as originally guessed). Implications:

- **Dynamic span on the loop:** ~2.1–2.2 mA out of the 16 mA dynamic range (4 mA = empty, 20 mA = 5 m, so 65 cm → ~6.1 mA). Still 16-bit-readable on the ADS1115 with thousands of distinct counts across the depth range — but the absolute accuracy budget (±0.5% of full scale = ±25 mm) is fixed by full scale, not by our usable span. So the practical resolution at the tank is **±25 mm depth**, not "much better because we're using a tiny slice."
- **Trade-off accepted.** A 0–1 m or 0–0.5 m probe would give better absolute accuracy, but the KIT0139 was already on hand / in the parts roadmap, and ±25 mm on a ~65 cm tank (±4%) is fine for "how many days until refill" — well below the day-to-day noise of plant consumption rate.
- **TODO:** measure the FlexiTank Pro's actual full water depth and update the BOM table at the top of this file (the "21" × 21" base × ~13" tall" line is wrong by roughly 2×).

### Signal Chain

```
[FlexiTank, water]
        │
        ▼
[KIT0139 probe, submerged at the bottom]   ← 12V supply on the loop
        │  4–20 mA current loop, 5 m sealed cable, exits the tank
        ▼
[4-20mA → 0-5V converter]  (DFRobot SEN0262 included with KIT0139, or discrete shunt)
        │  0–5 V analog
        ▼
[ADS1115 16-bit I²C ADC]
        │  I²C (SDA/SCL)
        ▼
[ESP32-C3 SuperMini]  (new dedicated `reservoir` node)
        │  WiFi
        ▼
[POST /api/ingest/sensors] → sensorreading rows
```

### Why ADS1115 instead of the ESP32-C3's native ADC

Two reasons, both documented elsewhere in the wiki:

1. **Non-linearity at the rail.** The ESP32-C3 ADC1 over-reports by 200–400 counts in the upper ~500 mV — fine for relative wet/dry tracking on a soil probe, **not** fine for a calibrated pressure-to-depth conversion where absolute accuracy is the whole point. See the "ESP32-C3 ADC over-reports near the rail" entry in [esp32-plant-nodes.md](esp32-plant-nodes.md#known-quirks).
2. **WiFi cross-talk.** GPIO4–GPIO7 are JTAG-multiplexed and unusable for ADC under WiFi (see [GPIO3/ADC decision](../decisions/2026-04-14-esp32-c3-gpio3-adc.md)). The ADS1115 is on I²C, so we sidestep the whole ADC-pin-availability puzzle on the C3.

The ADS1115 gives us 16 bits of resolution, programmable gain, and a clean stable reference — well-matched to the precision the pressure transducer is capable of.

### Why submerged pressure, not a float switch / ultrasonic / capacitive probe

See the [decision record](../decisions/2026-04-18-reservoir-level-pressure-transducer.md) for the full alternatives table. Short version: floats only give a discrete trip point; ultrasonic struggles with the FlexiTank's lid geometry and condensation; capacitive strip probes drift with nutrient EC. A hydrostatic transducer gives continuous, EC-independent depth and is the only IP68 option in the parts list.

## Bench bring-up (2026-04-26)

End-to-end signal chain validated on the bench. Probe → 4–20 mA loop → SEN0262 → ADS1115 (GAIN_FOUR, 32-sample averaging) → I²C 0x48 → ESP32-C3 SuperMini → USB serial.

### Wiring (matches the [DFRobot KIT0139 reference diagram](https://wiki.dfrobot.com/kit0139/))

- 12V brick `+` → SEN0262 top screw terminal (loop `+`)
- SEN0262 bottom screw terminal (loop `−`) → probe **brown** (V+)
- Probe **blue** (V−) → 12V brick `−`
- SEN0262 Gravity `VCC` (red) → ESP32-C3 5V pin
- SEN0262 Gravity `GND` (black) → ESP32-C3 GND
- SEN0262 Gravity `Signal` (blue) → ADS1115 A0
- ADS1115 VDD/GND/SDA/SCL/ADDR → ESP32-C3 5V/GND/GPIO4/GPIO5/GND

The brick GND and the ESP32 GND are tied through the SEN0262 Gravity GND pin (the SEN0262 is a non-isolated converter and bridges its loop-side ground to its signal-side ground internally). Don't run a separate ground wire — that one cable is the bridge.

### Provisional two-point calibration

Captured with the bench firmware (`firmware/reservoir_node/`, env `reservoir-bench`, GAIN_FOUR + 32-sample averaging):

| Cal point | Probe state | Mean voltage | Mean raw count |
|---|---|---|---|
| 0 cm head | Probe in dry air at tank-top height | 0.5793 V | 18,540 |
| 64.5 cm head | Probe suspended ~1 cm above tank floor, 25.8 in of water in tank | 0.8146 V | 26,069 |

**Provisional line:** `depth_cm = (raw_count − 18540) / 116.7` (≈ 3.65 mV per cm of head, ≈ 117 ADS counts per cm).

This is **not** the production cal — it skips the wiki-spec procedure (mount in final position; fill to a tape-measured reference depth; wait 30 min for the cable's atmospheric vent and the diaphragm thermals to settle; verify with a third independent point at ~½ depth and reject if it misses by >10 mm). It exists to (a) prove the math works end-to-end and (b) give the firmware sane initial constants. **Re-take and overwrite when the probe is in its final mount position with the proper 2 cm clearance.**

### Noise characterization

| Configuration | Per-second jitter |
|---|---|
| Single-sample reads at GAIN_TWOTHIRDS (default) | ~140 mV peak-to-peak |
| 32-sample averaging at GAIN_FOUR (current bench fw) | ~9 mV peak-to-peak (~9 mm equivalent depth) |

The 32-sample average is reduced by approximately √32 ≈ 5.7× from the single-sample jitter, plus an additional factor from the higher PGA setting rejecting wider-band noise. We're now electronically tighter than the probe's own ±25 mm absolute accuracy — i.e., the noise floor is no longer the limiting factor. Server-side downsampling (rolling 5–10 min averages) will pull the reported value into sub-mm precision, plenty for "days until refill" alerting.

### Capacitor experiment (failed — recorded for posterity)

Tried adding a 10 µF ceramic across A0 → GND to filter brick switching noise. Result: jitter **tripled** (140 mV → 400 mV peak-to-peak) and the center voltage shifted down ~100 mV. Almost certainly op-amp instability — the SEN0262's output stage doesn't tolerate a 10 µF direct capacitive load and starts ringing. A proper RC filter (small series resistor between op-amp output and cap, like 10–100 Ω + cap) would isolate the cap from the op-amp's feedback loop, but we didn't have a resistor on the bench. Removed the cap; firmware-side averaging does the noise reduction we need without it. Revisit only if production deployment shows residual brick-switching artifacts that averaging can't suppress.

## Firmware

- **Location:** `firmware/reservoir_node/`, two PlatformIO envs:
  - `reservoir-bench` — USB-only, no WiFi/OTA, prints `ts_ms,raw_mean,volts` to serial. Used for bring-up + calibration captures. **In service.**
  - `reservoir` — full WiFi + OTA + ingest path. **Production target.**
- **Behavior per cycle (every 30 s):** read 32 samples from the ADS1115 channel 0 (averaged), convert raw counts to depth via the compiled-in two-point calibration constants, divide by `DENSITY_REL = 1.007` to correct for nutrient solution density, divide by `CM_PER_INCH = 2.54` to publish in inches, POST `{reservoir_pressure_raw: <mean_count>, reservoir_in: <converted>}` to the existing `/api/ingest/sensors` endpoint with `location="reservoir"`.
- **Why both raw and depth?** The raw count is the recovery anchor for after-the-fact recalibration (if cal constants change, history can be re-derived from raw). The depth-in-inches is the value queries actually use. Mirrors the soil-moisture pattern (`soil_moisture_raw` + auto-cal'd `_pct`) but with **fixed cal constants in firmware** instead of auto-tracked extrema in the DB — see "Calibration" below.

- **Why inches on the wire?** The contract (`reservoir_in`) and the dashboard already speak inches; the operator measures fill depth with a tape measure in inches. Doing the cm→in conversion at the firmware publish boundary means the server stores values that match the contract 1:1 and zero unit-translation infrastructure has to live in the API layer. The internal cal math stays in cm because the cal procedure measures cm with a tape and the probe spec sheet is metric.
- **Cadence rationale:** 30 s matches the plant nodes. Reservoir level changes on the order of millimeters per hour, so 30 s is wildly oversampled — but consistent cadence simplifies the ingest path, and the cost is negligible. We may downsample at the DB layer later if the row volume becomes annoying.
- **OTA:** same `mDNS`-advertised ArduinoOTA pattern as the plant nodes — `dirt-reservoir.local:3232`, password from `.env`.

### Where the calibration lives

**Firmware, not DB.** The reservoir is the system's first absolute sensor, but extending the `sensorcalibration` table (which is built for the soil-moisture auto-extrema pattern) to also support fixed two-point calibrations would mean either a `mode` column or overloading existing columns with hidden semantics — both add ongoing complexity for a single sensor.

Instead we mirror the **tent SHT45 pattern**: the firmware contains the calibration constants (`RESERVOIR_RAW_AT_ZERO_CM`, `RESERVOIR_COUNTS_PER_CM`, `RESERVOIR_DENSITY_REL`) and converts raw → depth in-flight. The server stores the already-converted value with no special handling — exactly like it stores `temperature_c` from the tent SHT45 (factory-calibrated by the Sensirion driver) without ever needing a `sensorcalibration` row for it.

Recalibration = edit the constants in `firmware/reservoir_node/src/main.cpp`, OTA reflash. Annoying but rare (the wiki cal procedure says "once per deployment"), and OTA makes it not painful. The raw count is also persisted so we can recompute history with new constants without losing past data.

`reservoir_in` and `reservoir_pressure_raw` must NOT be added to `AUTO_CALIBRATED_METRICS` in `apps/shared/src/dirt_shared/services/readings.py`.

### Current calibration constants

Live values compiled into `firmware/reservoir_node/src/main.cpp`. Update this table on every (re)calibration in the same change as the firmware constants — the firmware ships with whatever's here, so a desync means depth values silently drift away from truth.

| Date | Source | `RAW_AT_ZERO_CM` | `COUNTS_PER_CM` | `DENSITY_REL` | Cal points used | Notes |
|---|---|---|---|---|---|---|
| 2026-04-26 | Bench bring-up | 18540 | 116.7 | 1.007 | 0 cm = 0.5793 V (raw 18540) ; 64.5 cm = 0.8146 V (raw 26069) | Provisional. Probe out of tank for the zero point, suspended ~1 cm above floor for the span point with 25.8 in (65.5 cm) of water. Skipped the 30 min settling step and the third-point verification — re-take per the cal procedure once the probe is in its permanent mount. |

## Mounting Notes

From the manufacturer's spec sheet, plus our own:

- Probe must hang **vertically downward** in the tank. Don't lay it sideways.
- **Suspend ~2 cm above the tank bottom** on the probe's own cable. Resting on the bottom puts the diaphragm into root-mat sediment and biases readings high.
- Keep the probe **away from the float-valve outlet** so suction transients don't show up as depth oscillations.
- **Cable seal must stay above the waterline.** The diaphragm is IP68; the cable terminations are not. Run the cable out the top of the tank, not through a side hole.
- **The cable contains an atmospheric vent.** The dry end of the cable must terminate in a non-condensing space so the gauge reference stays at room atmospheric pressure. House the SEN0262 / ADS1115 / ESP32 in a small enclosure with a sachet of desiccant; do not seal the cable end into a humid pocket inside the tent. A wet vent reads as fictitious depth changes that drift over hours-to-days.
- Allow ~30 min after first power-up for the reading to settle.

## Calibration

Two-point linear, run once per deployment, persisted in the `sensorcalibration` table with `metric="reservoir_depth_cm"`:

1. **Zero (dry-air)**: probe held in air at tank height. Record ADS1115 counts → that's the 0 cm anchor (should correspond to ~4 mA on the loop).
2. **Span**: fill to a tape-measured depth near the top of the usable range (e.g. ~40 cm in the FlexiTank), wait ~30 min for the reading to settle, record counts.
3. Compute slope from those two points; depth(counts) is linear between them.
4. **Verify** at a third independent depth (e.g. ~20 cm). Reject the calibration and re-do if the verification point misses by more than **10 mm**.

Auto-extrema calibration like the soil sensors do is wrong here — the probe is absolute, not relative — so the loop in `src/dirt/services/readings.py:_update_calibration` must NOT include `reservoir_depth_cm` in `AUTO_CALIBRATED_METRICS`.

### Density correction

A pressure sensor measures `ρ·g·h`, so a denser fluid reads as deeper than it is. Hydroponic nutrient solution runs ~1.005–1.010 g/mL, biasing depth high by ~0.7–1.0% (≈3–5 mm at 0.5 m full). We apply a single config constant `RESERVOIR_DENSITY_REL = 1.007` and divide depth by it before persisting. Recalibrate the slope rather than tweaking the constant if the recipe changes substantially (e.g. switching base nutrient brands).

### Volume conversion (separate calibration)

The FlexiTank's base is approximately a 21" × 21" prism, so depth → liters is roughly linear, but the corners are slightly radiused. To get an honest L number for "days until refill" estimates:

1. Empty tank.
2. Add water in 5 L increments from a measuring jug, recording depth after each addition.
3. Store the (depth_cm → liters) lookup table in config; piecewise-linear interpolate at runtime.

Publish both `reservoir_depth_cm` (raw, calibrated) and `reservoir_volume_l` (derived) so depth is recoverable if the volume table ever needs to be redone.

## Fault detection

In firmware, before publishing each reading:

- **Loop fault**: SEN0262 output below the equivalent of 2.4 mA on the loop (i.e. well under the 4 mA "alive" floor) → publish `loop_fault=true` and skip the depth value. Catches cable cut, broken probe, or lost loop power without requiring the server to infer it.
- **Refill event**: depth jumps by > 10 cm in < 5 min → emit a `reservoir_refilled` ingest event in addition to the normal sample. Anchors the daily report and prevents "rapid level change" alerting from firing on hand-fills.

These are cheap server-trustable signals — no need for the ingest path to second-guess depth values that already failed sanity at the source.

## Deferred / v2

- **Reclaiming ADC dynamic range.** With a 0–5 m sensor on a 0.5 m tank, we use only ~10% of the 4–20 mA span. Replacing the SEN0262's burden resistor with a larger value (and dividing back to ADS1115 range) would put our usable depth into the upper end of the converter's voltage span and push effective resolution from ~25 mm toward ~5 mm. **Not doing on day one** — adds a custom hardware mod and breaks the manufacturer's calibration. Re-evaluate if day-to-day evapotranspiration trends are too noisy to read.

## Open Questions

- **Node IP:** static reservation alongside the plant nodes. To be assigned.
- **Sensor housing:** cable strain relief at the tank exit. A standard cable gland through the tank lid is the obvious answer; confirm the FlexiTank lid is drillable / that we're OK modifying it.
- **Alerting thresholds:** "low reservoir" alert wiring is out of scope for this page; capture once the depth metric is flowing and we have a few weeks of consumption data to set a meaningful floor.
