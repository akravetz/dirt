---
title: "Hardware — Reservoir Level (Autopot, hydrostatic pressure transducer)"
type: hardware
sources: []
related: [wiki/concepts/autopot.md, wiki/decisions/2026-04-18-reservoir-level-pressure-transducer.md, wiki/decisions/2026-04-11-reservoir-stand.md, wiki/hardware/esp32-plant-nodes.md]
created: 2026-04-18
updated: 2026-04-18
---

# Reservoir Level (Autopot 25-gal FlexiTank Pro)

Continuous water-level telemetry on the Autopot reservoir, so consumption rate, refill timing, and "you're about to run dry while away" alerts are all derivable from data instead of by lifting the lid.

Method: **submerged hydrostatic pressure transducer** at the bottom of the tank. Water depth is linearly proportional to the pressure on the diaphragm — no moving parts, no float arms, no contact with surface optics. The probe sits in the nutrient solution permanently.

## Deployment Status

| Component | Status | Notes |
|-----------|--------|-------|
| DFRobot KIT0139 pressure transducer | ⏳ Planned | Submersible 316L stainless probe, 5m cable, 4–20mA loop output, 0–5m H₂O range |
| 4–20mA → 0–5V converter | ⏳ Planned | DFRobot SEN0262 ships in the KIT0139 box; alternative is a discrete precision shunt resistor (~250 Ω) — choice deferred |
| ADS1115 16-bit I²C ADC | ⏳ Planned | Reads the converter's voltage output cleanly; sidesteps the ESP32-C3's noisy/non-linear native ADC (see [ESP32-C3 ADC over-reporting note](esp32-plant-nodes.md#known-quirks)) |
| 12V DC supply for transmitter | ⏳ Planned | Transmitter needs 12–36V; ESP32-C3 USB-5V cannot drive it. Sourcing TBD |
| ESP32-C3 SuperMini node | ⏳ Planned | Same board family as the plant nodes; new dedicated node, working name `dirt-reservoir.local` (location label `reservoir`, IP TBD) |
| Firmware | ⏳ Planned | New `firmware/reservoir_node/` PIO project; mirrors `plant_node/` skeleton (WiFi, OTA, ingest POST), swaps the ADC driver for ADS1115 over I²C, drops the per-plant `PLANT_ID` flag |
| Server-side ingest | ✅ Existing path works | `POST /api/ingest/sensors` already accepts arbitrary `(location, metric, value)` triples — no schema change needed; will land as `location="reservoir"`, `metric="reservoir_depth_cm"` (and/or `reservoir_pressure_pa`) |

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

The 25-gal FlexiTank Pro is roughly **0.5 m deep when full** (21" × 21" base × ~13" tall). With a 0–5 m sensor we only ever exercise **the bottom 10%** of the probe's full scale. Implications:

- **Dynamic span on the loop:** ~1.6 mA out of the 16 mA dynamic range (4 mA = empty, 20 mA = 5 m, so 0.5 m → ~5.6 mA). Still 16-bit-readable on the ADS1115 with thousands of distinct counts across the depth range — but the absolute accuracy budget (±0.5% of full scale = ±25 mm) is fixed by full scale, not by our usable span. So the practical resolution at the tank is **±25 mm depth**, not "much better because we're using a tiny slice."
- **Trade-off accepted.** A 0–1 m or 0–0.5 m probe would give better absolute accuracy, but the KIT0139 was already on hand / in the parts roadmap, and ±25 mm on a 0.5 m tank (±5%) is fine for "how many days until refill" — well below the day-to-day noise of plant consumption rate.

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

## Firmware (planned)

- **Location:** `firmware/reservoir_node/` — new PIO project, modeled on `firmware/plant_node/`.
- **Behavior per cycle (every 30s):** read N samples from ADS1115 over I²C (averaged), convert ADC counts → mA → depth_cm using a calibration line (two-point: empty tank @ 4 mA, known fill height @ measured mA), POST as `reservoir_depth_cm` (and optionally raw `reservoir_pressure_raw` for after-the-fact recalibration).
- **Cadence rationale:** 30 s matches the plant nodes. Reservoir level changes on the order of millimeters per hour, so 30 s is wildly oversampled — but consistent cadence simplifies the ingest path, and the cost is negligible. We may downsample at the DB layer later if the row volume becomes annoying.
- **OTA:** same `mDNS`-advertised ArduinoOTA pattern as the plant nodes — `dirt-reservoir.local:3232`, password from `.env`.

## Mounting Notes

From the manufacturer's spec sheet:

- Probe must hang **vertically downward** in the tank. Don't lay it sideways.
- Keep the probe **away from the float-valve outlet** so suction transients don't show up as depth oscillations.
- **Cable seal must stay above the waterline.** The diaphragm is IP68; the cable terminations are not. Run the cable out the top of the tank, not through a side hole.
- Allow ~30 min after first power-up for the reading to settle.

## Calibration

Two-point linear:

1. Empty tank → record raw ADS1115 counts (should correspond to ~4 mA, the loop's "alive but no pressure" baseline).
2. Fill to a measured depth (use a tape measure inside the tank), record counts.

Slope and intercept from those two points convert future readings to cm. Persist the calibration in the same `sensorcalibration` table the soil probes use, with `metric="reservoir_depth_cm"`.

(Auto-extrema calibration like the soil sensors do is wrong here — the probe is absolute, not relative — so the loop in `src/dirt/services/readings.py:_update_calibration` should NOT include `reservoir_depth_cm` in `AUTO_CALIBRATED_METRICS`.)

## Open Questions

- **Current-to-voltage conversion path:** SEN0262 module (out of the box, but adds another point of failure) vs a soldered precision shunt resistor (simpler, no extra board). Decide when assembling.
- **12 V supply:** dedicated brick, or share an existing 12 V rail in the closet? TBD.
- **Node IP:** static reservation alongside the plant nodes. To be assigned.
- **Sensor housing:** cable strain relief at the tank exit. A standard cable gland through the tank lid is the obvious answer; confirm the FlexiTank lid is drillable / that we're OK modifying it.
- **Alerting thresholds:** "low reservoir" alert wiring is out of scope for this page; capture once the depth metric is flowing and we have a few weeks of consumption data to set a meaningful floor.
