---
title: "Hardware — Soil Moisture Sensing Options"
type: hardware
sources: []
related: [wiki/concepts/capacitive-soil-moisture.md, wiki/hardware/esp32-plant-nodes.md, wiki/hardware/reservoir-level.md, wiki/hardware/sdi-12-substrate-sensors.md]
created: 2026-05-31
updated: 2026-05-31
---

# Soil Moisture Sensing Options

Snapshot date: 2026-05-31. Prices are rough list prices found during research and should be rechecked before buying.

Goal: replace or supplement the current cheap capacitive probes with a more trustworthy root-zone signal for the current Autopot coco/perlite grow, while keeping a path toward a future 16-site drain-to-waste coco setup. The useful measurements are moisture trend/comparison first, and optional substrate EC second.

## Current Problem

The current per-plant ESP32-C3 nodes read generic capacitive soil moisture probes directly through the ESP32 ADC. That system is cheap and already integrated, but the signal has become hard to trust:

- Raw ADC values are not cross-comparable across probes.
- The current clone sensors vary by hardware generation and individual unit.
- Some readings appear pinned or implausible for long periods.
- Coco nutrient salts may affect low-end capacitive designs.
- The ESP32 ADC adds its own nonlinearity/noise near the high end.

Server-side auto-calibration makes the readings more useful than raw ADC values, but it cannot turn a physically weak sensor into a reliable substrate instrument.

## Options Considered

| Option | Approx. sensor price | Measures | Interface | Integration fit | Main upside | Main downside |
|---|---:|---|---|---|---|---|
| Generic capacitive PCB probe v1.2/v2.0 | $2-10 | Relative moisture only | Analog voltage | Already live on per-pot ESP32 nodes | Cheapest and easy to replace | Poor repeatability, clone variance, fragile packaging, questionable salt behavior |
| DFRobot SEN0308 IP65 capacitive probe | $14.90 | Relative moisture only | Analog voltage | Easy ESP32/ADC integration | Better packaging than bare PCB probes | Still basically the same class of capacitive signal; likely not enough improvement |
| Generic RS-485 soil moisture probes | ~$20-60 | Usually moisture/temp, sometimes EC/pH/NPK claims | RS-485/Modbus | Needs RS-485 transceiver + firmware | Digital bus, cheap, long cable friendly | Sensor physics are usually opaque; many are likely cheap dielectric probes with unknown calibration |
| Vegetronix VH400 | Price not published on product page | Moisture/VWC | Analog voltage | ESP32 + good ADC | Rugged blade, waterproof, salinity-insensitivity claim, simple output | No EC/temp; price must be confirmed; still analog |
| Truebner SMT50 | 69 EUR incl. VAT from OpenSprinklerShop | Moisture + temperature | Analog voltage | ESP32 + good ADC | Credible mid-tier FDR sensor; lower cost than TB-SMP03 | No EC; 0-50% VWC range; careful installation needed |
| TekBox TBSMP03 | $99 | Moisture + temperature | SDI-12 | Needs SDI-12 master/interface | Digital bus, reusable multi-sensor wiring, calibrated output | No EC; less field reputation than METER TEROS |
| METER TEROS 10 | $145 | Moisture/VWC | Analog voltage | ESP32 + ADS1115-style ADC | 70 MHz dielectric measurement, rugged, known calibration | No temp/EC; still needs analog chain |
| METER TEROS 12 | $271 | Moisture/VWC + temperature + bulk EC | SDI-12 | Needs SDI-12 master/interface | Best single diagnostic probe; includes EC and temp | Expensive to put on every plant |

Sources:

- Current system notes: [Capacitive Soil Moisture Sensors](../concepts/capacitive-soil-moisture.md), [ESP32-C3 Per-Plant Nodes](esp32-plant-nodes.md)
- DFRobot SEN0308: <https://www.dfrobot.com/search-sen0308.html>
- Vegetronix VH400: <https://www.vegetronix.com/Products/VH400/>
- Truebner SMT50: <https://opensprinklershop.de/en/product/smt50/>
- TekBox TBSMP03: <https://www.sdi-12products.com/products/sdi-12-soil-moisture-temperature-probe-tbsmp03>
- METER TEROS 10: <https://metergroup.com/products/teros-10/>
- METER TEROS 12: <https://metergroup.com/products/teros-12/>

## Shortlist Read

For a serious diagnostic probe on Plant A, TEROS 12 is the strongest option because it gives VWC, temperature, and bulk EC over SDI-12. It is expensive, but one probe can become the reference sensor for comparing cheaper sensors and understanding whether the current moisture story is real.

For scalable per-plant coverage, TEROS 12 on all 16 future DTW plants is hard to justify. The likely scale path is one or two reference-class sensors plus cheaper per-plant moisture probes. The strongest mid-price candidates are SMT50, VH400, and TBSMP03.

For the current grow, the cleanest first experiment is:

1. Put one higher-quality probe in Plant A.
2. Keep the existing capacitive node running for side-by-side comparison.
3. Compare moisture trend, irrigation events, pot hand-weight, visual stress, and runoff/root-zone checks.
4. Use that result to decide the future 16-site sensor mix.

## SDI-12 Path

SDI-12 is a slow, rugged, 3-wire environmental sensor bus: power, ground, and one bidirectional data wire. Multiple sensors can share the same bus if each has a unique address. It avoids ADC problems because the sensor does the measurement internally and returns ASCII values.

The SDI-12 candidates here are:

- **TBSMP03**: moisture + temperature, no EC, $99.
- **TEROS 12**: moisture + temperature + bulk EC, $271.

Terminology trap: **TBSMP03** is the TekBox soil moisture probe. **TBS03** is TekBox's SDI-12-to-USB converter/tester.

The SDI-12 bill-of-materials and sensor-specific details live in [SDI-12 Substrate Sensors](sdi-12-substrate-sensors.md). At a high level:

- **USB bus to Dirt computer:** fastest validation path for the current tent; TBSMP03 starter is roughly $187-190 before shipping/tax, or $359-362 with TEROS 12.
- **ESP32/WiFi SDI-12 bus node:** better long-term shape if we want the current per-pot node style; TBSMP03 starter is roughly $150-156 before shipping/tax, or $322-328 with TEROS 12.

## Analog Sketch

Analog candidates keep the existing broad shape: power a sensor near the pot, read voltage, POST values from an ESP32. The improvement comes from using a better physical sensor and a better ADC.

Recommended analog chain:

```text
sensor voltage output -> ADS1115 or equivalent ADC -> ESP32 -> Dirt ingest
```

The ADC helps most when the upstream sensor is worth preserving. For TEROS 10, SMT50, or VH400, the ADC is a sensible part of the system. For the cheapest capacitive probes, the ADC can make the reading cleaner but does not fix weak sensor physics, clone variance, or salt sensitivity.

## Deep Dive: TEROS 10

TEROS 10 is not SDI-12. It is a 70 MHz dielectric moisture sensor with analog voltage output.

Relevant engineering notes:

- Measures VWC only.
- Output is analog voltage, so it needs an ADC.
- METER lists 70 MHz dielectric measurement, intended to reduce salinity and texture effects.
- METER lists local base price at $145.
- METER specs include typical soilless media accuracy around +/-0.05 m3/m3 when solution EC is below 8 dS/m; medium-specific calibration can be better.

Pros:

- Better physical measurement system than cheap capacitive boards.
- Less expensive than TEROS 12.
- Rugged METER hardware and published specs.
- Strong candidate if only moisture is needed.

Cons:

- No temperature or EC.
- Analog chain still matters; use ADS1115 or similar.
- At $145 each, full 16-plant coverage still becomes expensive.

Best use here: a high-quality VWC-only reference or limited per-plant sensor where EC is not required. See [SDI-12 Substrate Sensors](sdi-12-substrate-sensors.md) for the TBSMP03 and TEROS 12 deep dives.

## Practical Architectures

### Current Grow: Reference Sensor First

Use one TEROS 12 or TBSMP03 in Plant A while leaving the current capacitive probe installed.

- If the goal is diagnosing Plant A and understanding salt/root-zone behavior: choose TEROS 12.
- If the goal is validating a scalable moisture-only SDI-12 path: choose TBSMP03.

### Future 16-Site DTW: Hybrid Sensor Mix

Likely shape:

- 1-2 TEROS 12 probes as reference sensors on representative/problem plants.
- Cheaper per-plant moisture sensors on all plants: TBSMP03, SMT50, VH400, or possibly TEROS 10 depending on budget.
- Use runoff EC/pH plus reservoir EC/pH as the system-level nutrient truth.

Approximate 16-plant sensor-only costs:

| Per-plant sensor choice | 16 sensor cost | EC at every plant? | Notes |
|---|---:|---|---|
| Generic capacitive | ~$32-160 | No | Too weak to trust as primary |
| DFRobot SEN0308 | ~$238 | No | Better packaging, same broad sensor class |
| SMT50 | ~1,104 EUR | No | Credible analog mid-tier, temp included |
| TBSMP03 | $1,584 | No | Digital SDI-12, moisture + temp |
| TEROS 10 | $2,320 | No | High-quality VWC-only, analog |
| TEROS 12 | $4,336 | Yes | Best data, likely overkill/costly for every plant |

This points toward a hybrid design rather than TEROS 12 everywhere.

## Open Questions

- Does TBSMP03 track coco dryback well enough to be a scalable middle tier?
- Does TEROS 12 bulk EC produce a useful enough signal in our coco/feed EC range, or is runoff/reservoir EC still the main EC truth?
- Can one reference TEROS 12 calibrate trust in cheaper per-plant probes, or does pot-to-pot placement dominate too much?
- For analog mid-tier sensors, is ADS1115 enough to make readings stable across nodes?
- In future DTW, do we need one moisture sensor per plant, or one high-quality sensor per irrigation zone plus periodic manual spot checks?
