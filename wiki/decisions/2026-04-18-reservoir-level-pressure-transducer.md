---
title: "Decision: Reservoir Level via Submerged Pressure Transducer + ADS1115"
type: decision
sources: []
related: [wiki/hardware/reservoir-level.md, wiki/concepts/autopot.md, wiki/hardware/esp32-plant-nodes.md, wiki/decisions/2026-04-14-esp32-c3-gpio3-adc.md]
created: 2026-04-18
updated: 2026-05-04
---

# Decision: Reservoir Level via Submerged Pressure Transducer + ADS1115

**Date:** 2026-04-18
**Status:** Accepted (parts on roadmap; implementation pending — see [hardware page](../hardware/reservoir-level.md))

**Revision 2026-05-04:** implementation is live under scoped identity
`device_id='reservoir-node'`. Current persisted depth metric is canonical
`reservoir_in`; historical `reservoir_depth_cm` rows were converted to
`reservoir_in` during the scoped firmware legacy cleanup.

## Context

The Autopot 25-gallon FlexiTank Pro is the grow's water reservoir. Today, the only way to know its level is to lift the lid and look — fine while we hand-water daily, but useless once the float valves are open and the system is supposed to run unattended for 7–10 days at a time. We need continuous, agent-readable depth telemetry so consumption rate, refill timing, and "running dry while we're away" alerts can come from data instead of memory.

The ESP32-C3 plant-node infrastructure (per-plant nodes, ingest endpoint, OTA flow, auto-restarting service) already exists, so adding a fifth wireless node is the cheap path. The open question was sensor topology.

## Decision

Use a **submerged hydrostatic pressure transducer** at the bottom of the tank, read through a **16-bit ADS1115 I²C ADC** wired to a new dedicated **ESP32-C3 SuperMini reservoir node**. Specific part: **DFRobot KIT0139** (4–20 mA, 12–36 V, 0–5 m H₂O, IP68, 316L stainless probe).

The 4–20 mA loop is converted to a 0–5 V signal (either the SEN0262 module that ships with KIT0139, or a discrete precision shunt — choice deferred to assembly time) and sampled by the ADS1115. The ESP32-C3 reads the ADS1115 over I²C, converts counts to depth via a two-point linear calibration, and POSTs canonical `reservoir_in` plus raw `reservoir_pressure_raw` every 30 s through the scoped `/api/ingest/sensors` endpoint as `device_id='reservoir-node'`.

## Alternatives Considered

| Option | Resolution | Why rejected |
|--------|-----------|--------------|
| **Float switch (single trip point)** | Discrete only | Tells us "below X" but no consumption rate, no refill ETA. Useless for "you have ~3 days of water at current rate" analytics |
| **Multi-stage float ladder** (4 switches at 25/50/75/100%) | 4-step | Coarse, mechanical, more failure modes (4 contacts vs 1 sealed diaphragm), still doesn't give a smooth time-series for trend extraction |
| **Ultrasonic (HC-SR04 / JSN-SR04T from above)** | ~1 cm | FlexiTank lid geometry is awkward for top-down beam (curved, condensation-prone underside catches the return). Ultrasonic also drifts with tank temperature and humidity |
| **Capacitive water-level strip (e.g. resistive ladder)** | ~1 cm/segment | Output drifts with nutrient EC — and EC is precisely what we change every refill. Coupling level readings to nutrient strength is a usability disaster |
| **eTape resistive level sensor** | ~1 cm | Similar EC sensitivity; also rated only for water, not nutrient solution; long-term drift in the salt environment is unproven |
| **Submerged hydrostatic transducer (chosen)** | ±5% (limited by full-scale range vs our usable depth, see below) | Continuous depth, EC-independent, IP68 for permanent submersion, no moving parts, no surface optics |

## Why ADS1115, not the ESP32-C3 ADC

Two reasons, both already paid for in prior decisions:

1. **The C3's ADC over-reports near the rail by 200–400 counts** (documented quirk in [esp32-plant-nodes.md](../hardware/esp32-plant-nodes.md#known-quirks)). For the soil-moisture probes that's harmless because we read the wet/dry range relatively. For an absolute pressure-to-depth conversion the non-linearity becomes a systematic accuracy error we'd have to characterize per-board.
2. **GPIO availability is constrained.** GPIO4–GPIO7 are JTAG-multiplexed and useless for ADC under WiFi (see [GPIO3/ADC decision](2026-04-14-esp32-c3-gpio3-adc.md)). Adding a second high-precision analog channel on the C3 means fighting that pin map again.

The ADS1115 (~$3, I²C, well-supported) gives us 16-bit resolution, a stable internal reference, and dodges both problems for the price of two pins (SDA/SCL) instead of one ADC pin.

## Why a 0–5 m sensor for a 0.5 m tank

The 25-gal FlexiTank is ~0.5 m deep when full, so a 0–5 m probe only ever exercises the bottom 10% of its range. The accuracy budget is fixed by full scale (±0.5% × 5 m = ±25 mm), so practical resolution at the tank is ±25 mm — about ±5% of the tank depth. That's well below the daily noise of plant consumption rate, so it doesn't constrain anything we want to do with the data. A 0–1 m probe would buy us tighter accuracy but the KIT0139 is the part already in the parts roadmap, and the trade-off isn't worth a second order.

## What This Establishes for the Future

- A dedicated scoped **`reservoir-node`** device with `reservoir_in` and `reservoir_pressure_raw` capabilities.
- A new pattern of **dedicated single-purpose ESP32-C3 nodes** beyond the per-plant template — the firmware skeleton (`firmware/plant_node/`) is reusable but the location-specific logic (sensors, calibration) gets its own folder.
- The first **absolute** sensor reading in the system. All prior sensors were either inherently calibrated (BME280 temp/RH/pressure on the Arduino Nano — see [2026-04-20 sensor swap](2026-04-20-bme280-sensor-swap.md)) or auto-calibrated relatively (capacitive soil probes). This one needs a one-time **two-point manual calibration** and must stay out of the soil-moisture auto-extrema widening path.

## Acceptance Criteria

- `reservoir_in` shows up in `sensorreading` rows attached to the `reservoir-node/reservoir_in` capability at ~30 s cadence.
- A two-point empty-tank / known-fill calibration is recorded and the resulting line produces depth values that match a tape-measure check to within ±25 mm.
- The depth time-series is monotonically decreasing between refills (no EC- or temperature-driven drift artifacts) and shows a clear step on each top-off.
- The web UI's sensor-history graphs render `reservoir_in` alongside the existing tent metrics without code changes — proving the ingest path didn't need bespoke handling.

## Open Items (from the hardware page)

- 4–20 mA → 0–5 V conversion path: SEN0262 module vs discrete precision shunt.
- 12 V supply source for the transmitter loop.
- Static IP / mDNS reservation for the new node.
- Cable strain relief / lid grommet on the FlexiTank.
- Low-reservoir alert thresholds — defer until we have a few weeks of consumption data.
