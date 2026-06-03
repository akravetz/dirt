---
title: "Hardware — Soil Moisture Sensing Options"
type: hardware
sources: []
related: [wiki/concepts/capacitive-soil-moisture.md, wiki/hardware/esp32-plant-nodes.md, wiki/hardware/reservoir-level.md, wiki/hardware/sdi-12-substrate-sensors.md]
created: 2026-05-31
updated: 2026-06-03
---

# Soil Moisture Sensing Options

Snapshot date: 2026-06-03. Prices are rough list prices found during research and should be rechecked before buying.

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
| ComWinTop / generic RS-485 soil probes | Already ordered: 2 ComWinTop THCPH-S-class probes | Moisture + temp + EC + pH for the ordered variant | RS-485/Modbus RTU | XIAO ESP32C3 + Seeed XIAO RS485 breakout | Digital bus, cheap, long cable friendly, no ESP32 ADC path | Sensor physics/calibration are opaque; pH-in-substrate behavior must be validated before trusting |
| Vegetronix VH400 | Price not published on product page | Moisture/VWC | Analog voltage | ESP32 + good ADC | Rugged blade, waterproof, salinity-insensitivity claim, simple output | No EC/temp; price must be confirmed; still analog |
| Truebner SMT50 | 69 EUR incl. VAT from OpenSprinklerShop | Moisture + temperature | Analog voltage | ESP32 + good ADC | Credible mid-tier FDR sensor; lower cost than TB-SMP03 | No EC; 0-50% VWC range; careful installation needed |
| TekBox TBSMP03 | $99 | Moisture + temperature | SDI-12 | Needs SDI-12 master/interface | Digital bus, reusable multi-sensor wiring, calibrated output | No EC; less field reputation than METER TEROS |
| METER TEROS 10 | $145 | Moisture/VWC | Analog voltage | ESP32 + ADS1115-style ADC | 70 MHz dielectric measurement, rugged, known calibration | No temp/EC; still needs analog chain |
| METER TEROS 12 | $271 | Moisture/VWC + temperature + bulk EC | SDI-12 | Needs SDI-12 master/interface | Best single diagnostic probe; includes EC and temp | Expensive to put on every plant |

Sources:

- Current system notes: [Capacitive Soil Moisture Sensors](../concepts/capacitive-soil-moisture.md), [ESP32-C3 Per-Plant Nodes](esp32-plant-nodes.md)
- ComWinTop CWT-Soil THCPH-S-class RS485 sensor: <https://store.comwintop.com/products/rs485-4-20ma-soil-temperature-humidity-moisture-conductivity-ec-ph-sensor>
- CWT-Soil-THCPH-S manual mirror: <https://www.digitalconcepts.net.au/arduino/content/support/datasheets/rs485sensors/THCPH-S%20%285pin%20probe%29%20Manual%20V1.4.pdf>
- Seeed XIAO ESP32C3 pinout: <https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/>
- Seeed RS485 Breakout Board for XIAO: <https://www.seeedstudio.com/RS485-Breakout-Board-for-XIAO-p-6306.html>
- Seeed XIAO RS485 Expansion Board wiki: <https://wiki.seeedstudio.com/XIAO-RS485-Expansion-Board/>
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

## Current RS485 Plan: ComWinTop Sensors + XIAO

Two ComWinTop RS485 soil probes have been ordered for moisture and pH exploration. The current plan is to bring them up with a Seeed Studio XIAO ESP32C3 and the Seeed RS485 Breakout Board for XIAO, then compare the signal against the existing capacitive probes, hand-weight/watering events, runoff checks, and visible plant response.

This is a validation path, not a decision to trust these probes as the long-term source of truth. The attractive part is the interface: Modbus RTU over RS485 gives a digital, multi-drop bus and avoids the ESP32-C3 ADC issues that weakened the current capacitive-probe system. The risky part is sensor physics and calibration: cheap multi-parameter soil probes often expose clean-looking digital numbers without enough transparency about how moisture and pH are actually measured in coco/perlite.

### Parts On Hand / Ordered

| Qty | Item | Source | Notes |
|---:|---|---|---|
| 2 | ComWinTop CWT-Soil THCPH-S-class RS485 soil sensors | Already ordered from ComWinTop | Ordered for moisture + pH; expected to also expose temperature and EC registers |
| 1 | Seeed Studio XIAO ESP32C3 | Already in the plant-node migration path | WiFi controller; existing firmware target already uses this board family |

### Additional BOM To Buy

| Qty | Item | Vendor | Purpose |
|---:|---|---|---|
| 1 | Seeed RS485 Breakout Board for XIAO, SKU 113991354 | Seeed Studio | XIAO-format UART-to-RS485 transceiver board |
| 1 | Reliable 5 V USB supply, 1 A minimum; 2 A preferred | Adafruit, SparkFun, or DigiKey | Powers the XIAO and, for short cable tests, both sensors |
| 1 | USB-C cable rated for power + data | Adafruit, SparkFun, or DigiKey | Flashing, serial logs, and runtime power |
| 4 | WAGO 221-413 or 221-415 lever connectors | DigiKey | Small bus bars for 5 V, GND, RS485 A, and RS485 B |
| 1 | Short Cat5e/Cat6 cable or 1-pair shielded twisted RS485 cable | DigiKey, SparkFun, or Adafruit | RS485 A/B twisted pair between controller and sensors |
| 1 optional | 120 ohm through-hole resistor | DigiKey, SparkFun, or Adafruit | Far-end RS485 termination if the short tent run is flaky |
| 1 optional | 12 V regulated supply + barrel-jack screw terminal | Adafruit, SparkFun, or DigiKey | Better sensor-power margin if 5 V over the cable proves marginal |
| 1 optional | Multimeter | Adafruit, SparkFun, or DigiKey | Verify 5 V/GND and continuity before connecting sensors |

The earlier SparkFun RS485 transceiver breakout and its screw terminal are no longer needed if using the Seeed XIAO RS485 breakout. A USB-to-RS485 adapter is also optional rather than required; the XIAO can program sensor addresses itself.

### Wiring Plan

The Seeed RS485 breakout plugs/solders directly to the XIAO. The breakout handles the UART-to-RS485 electrical conversion. The ESP32 does not drive the sensor bus directly.

Use the received sensor manual/label as the authority before applying power. The THCPH-S manual mirror lists this common CWT wiring:

```text
Sensor brown  -> power +, DC 4.5-30 V
Sensor black  -> power - / GND
Sensor yellow -> RS485 A+
Sensor blue   -> RS485 B-
```

For first bring-up from the same 5 V USB supply:

```text
USB/XIAO 5V or VBUS -> sensor 1 brown -> sensor 2 brown
USB/XIAO GND        -> sensor 1 black -> sensor 2 black
Seeed RS485 A       -> sensor 1 yellow -> sensor 2 yellow
Seeed RS485 B       -> sensor 1 blue   -> sensor 2 blue
```

Ground must be common between the XIAO/RS485 board and the sensor power supply. Do not connect sensor power to the XIAO `3V3` pin. Do not connect 5 V or 12 V to any XIAO GPIO pin.

For a short grow-tent run, start with a simple daisy-chain/bus shape and no long stubs:

```text
XIAO RS485 board ---- sensor 1 ---- sensor 2
```

The Seeed board has a 120 ohm termination switch. For short bench/tent tests, start with termination off unless communication is flaky. If the cable is longer or noisy, terminate only the two physical ends of the bus: enable the Seeed board's 120R switch if the controller is at one end, and add one 120 ohm resistor across A/B at the far sensor end. Do not add termination at every sensor.

If Modbus requests time out, first verify power and ground. Then try swapping A/B at the RS485 terminal only. Do not swap power wires.

### Address Programming Plan

Both sensors will likely arrive at Modbus slave address `1`. They cannot both keep the same address on the same RS485 bus, so configure one sensor before installing both together.

First-step procedure:

1. Connect only one sensor to the XIAO RS485 breakout.
2. Power the sensor from 5 V or 12 V and share ground with the XIAO.
3. Flash a small temporary XIAO firmware/sketch that speaks Modbus RTU.
4. Poll the sensor at the factory serial settings from the manual, expected default: address `1`, `4800` baud, `8N1`.
5. Read measurement registers first to prove RX/TX/A/B wiring works.
6. Write the documented Modbus address/config register to set the first sensor to address `2`.
7. Power-cycle that sensor.
8. Verify it responds at address `2` and no longer responds at address `1`.
9. Label the cable/probe as `addr=2`.
10. Connect the second sensor and leave it at address `1`.

Important: do not guess the address-change register. Reading measurement registers is low risk; writing configuration registers should wait until the exact register and write command are confirmed from the received ComWinTop manual or vendor support material.

### Expected Modbus Shape

The manual mirror for the THCPH-S-class sensor describes Modbus RTU over RS485. The expected first read is function code `0x03` against holding registers. For the THCPH-S-class layout, measurement registers are expected to begin at `0x0000`, with moisture/humidity, temperature, EC, and pH in the first block. Confirm scale factors from the received manual before storing values in Dirt; pH and EC are usually transmitted as scaled integers rather than native floats.

Candidate Dirt metrics after verification:

| Sensor value | Candidate metric | Notes |
|---|---|---|
| Soil moisture / humidity | `substrate_moisture_pct` or `soil_moisture_pct` | Pick one canonical name before ingest; avoid mixing with existing raw ADC metric |
| Soil temperature | `substrate_temp_c` | Convert to F only in UI/reporting if needed |
| Conductivity | `substrate_ec_us_cm` or `substrate_ec_ds_m` | Choose units before ingest; avoid silent uS/cm vs dS/m confusion |
| pH | `substrate_ph` | Treat as experimental until checked against runoff/slurry/manual meter readings |

### Bring-Up Checklist For A Future Agent

1. Re-read this section plus [ESP32-C3 Per-Plant Nodes](esp32-plant-nodes.md).
2. Verify the received sensor model and wire colors against the included manual.
3. Assemble XIAO + Seeed RS485 breakout.
4. Bench-test one sensor only at address `1`.
5. Confirm basic Modbus reads before any writes.
6. Change one sensor to address `2`, power-cycle, and verify.
7. Wire both sensors on the same A/B bus with shared ground and distinct addresses.
8. Poll both sensors for at least 15-30 minutes on the bench and log raw register responses.
9. Only then wire firmware ingest into Dirt metrics.
10. Validate pH/moisture trends against manual measurements and plant/watering events before relying on automations.

### Open Questions For Bring-Up

- What exact model/variant arrives, and does its manual match the THCPH-S V1.4 register map?
- Which Modbus register changes the slave address, and does the device require a power-cycle after writing it?
- Are the default serial settings definitely `4800 8N1`, or did this batch ship at a different baud rate?
- Does 5 V USB power remain stable with both sensors plus ESP32 WiFi active, or should sensor power move to 12 V?
- Does the pH signal track any real substrate condition in coco/perlite, or is runoff/slurry/manual meter data still the practical pH truth?

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
