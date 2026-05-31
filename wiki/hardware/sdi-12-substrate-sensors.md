---
title: "Hardware — SDI-12 Substrate Sensors"
type: hardware
sources: []
related: [wiki/hardware/soil-moisture-sensing-options.md, wiki/hardware/esp32-plant-nodes.md, wiki/hardware/reservoir-level.md]
created: 2026-05-31
updated: 2026-05-31
---

# SDI-12 Substrate Sensors

Snapshot date: 2026-05-31. Prices are rough list prices found during research and should be rechecked before buying.

This page covers the practical SDI-12 path for substrate moisture sensing in Dirt. The broader sensor comparison lives in [Soil Moisture Sensing Options](soil-moisture-sensing-options.md).

## What SDI-12 Means Here

SDI-12 is a slow, rugged, 3-wire environmental sensor bus:

- Power
- Ground
- One bidirectional data wire

Multiple sensors can share the same bus if each has a unique address. The key advantage is that the sensor performs the measurement internally and returns digital values, so Dirt does not need an ADC for these probes.

The SDI-12 candidates under consideration are:

- **TBSMP03**: moisture + temperature, no EC, $99.
- **TEROS 12**: moisture + temperature + bulk EC, $271.

Terminology trap: **TBSMP03** is the TekBox soil moisture probe. **TBS03** is TekBox's SDI-12-to-USB converter/tester.

## Option A: USB SDI-12 Bus to the Dirt Computer

This is the fastest validation path for the current tent because the farthest plant is about 8 ft from the computer including routing. The TBSMP03 default 5 m cable should cover the current layout without a custom extension.

| Item | Qty | Approx. price | Notes |
|---|---:|---:|---|
| TBSMP03 sensor | 1 | $99 | Default 5 m cable covers current tent routing |
| LiuDr SDI-12 USB adapter | 1 | $55 | USB serial interface to SDI-12 bus |
| 12 V 1 A supply | 1 | $7-9 | TBSMP03 wants 6-17 V supply |
| Barrel jack to screw terminal | 1 | $2 | Makes 12 V supply easy to land |
| Small IP65/weatherproof enclosure | 1 | ~$10 | Protect adapter/junction |
| Cable glands | 2 | ~$4 | Power and sensor/bus cable entry |
| WAGO / terminal splices | 1 pack | ~$10 | Bus junctions for power/data/ground |

Estimated TBSMP03 USB starter: **~$187-190** before shipping/tax.

With TEROS 12 instead of TBSMP03: **~$359-362** before shipping/tax.

The official TekBox TBS03 USB converter is another path, but it costs more: $184 for transfer-only mode, $349+ for auto-measurement/monitor modes. That may be useful as a lab/debug tool, but the LiuDr adapter is a cheaper first logger.

## Option B: ESP32/WiFi SDI-12 Bus Node

This keeps the current "node near the pots" deployment style but replaces analog ADC reading with a digital SDI-12 bus.

| Item | Qty | Approx. price | Notes |
|---|---:|---:|---|
| TBSMP03 sensor | 1 | $99 | Or TEROS 12 at $271 |
| RAK13010 SDI-12 interface | 1 | $6.50 | SDI-12 interface module with UART-side integration |
| RAK19007 WisBlock base | 1 | $9.99 | Base board for WisBlock modules |
| RAK11200 ESP32 WiFi core | 1 | $9.90-15.90 | ESP32/WiFi core module |
| Enclosure, glands, splices | 1 set | ~$24 | Same physical packaging problem |

Estimated TBSMP03 ESP32/WisBlock starter: **~$150-156** before shipping/tax.

With TEROS 12 instead of TBSMP03: **~$322-328** before shipping/tax.

The tradeoff: cheaper hardware than USB and a better long-term deployment shape, but more firmware work before the first data lands in Dirt.

## Deep Dive: TBSMP03

TBSMP03 is the middle SDI-12 option. It returns calibrated soil moisture and soil temperature over SDI-12. It does not report EC.

Relevant engineering notes:

- Supply: 6-17 V, typically 12 V.
- Data: SDI-12, 1200 baud, addressable bus.
- Output: moisture percent and temperature.
- Cable: default ordering information lists 5 m cable; custom lengths are possible.
- Claimed strengths: salinity-insensitive, temperature-compensated, rugged cast design.

Pros:

- Much cheaper than TEROS 12.
- Digital output avoids ESP32 ADC issues.
- SDI-12 bus is reusable for multiple sensors.
- Good fit for a future tent-level bus.

Cons:

- No substrate EC.
- Less known in cannabis/coco crop-steering circles than TEROS/Aroya-style probes.
- We would need to validate its coco behavior ourselves.

Best use here: a scalable candidate if the goal is per-plant moisture and temperature without paying for EC on every plant.

## Deep Dive: TEROS 12

TEROS 12 is the high-confidence option. It reports VWC, temperature, and bulk EC over SDI-12.

Relevant engineering notes:

- Measures moisture/VWC, substrate temperature, and bulk electrical conductivity.
- Uses SDI-12, so no ADC is needed.
- METER lists local base price at $271.
- METER lists increased volume of influence and rugged epoxy body.
- TEROS 12 is common in commercial substrate monitoring systems, including cannabis crop steering products.

Pros:

- Best single probe for Plant A diagnosis.
- EC is the major extra value over TBSMP03 and TEROS 10.
- Digital SDI-12 output simplifies long cable runs and avoids local ADC problems.
- Can act as the reference probe for validating cheaper sensors.

Cons:

- Too expensive to blindly buy for every plant in a 16-site DTW layout.
- Bulk EC is not the same as pore-water EC; interpretation in coco needs care.
- SDI-12 integration is new for Dirt.

Best use here: one Plant A/reference sensor, then possibly one sensor per irrigation zone or per representative plant instead of one per plant.

## First Integration Shape

For current validation, start with one sensor in Plant A while leaving the existing capacitive probe installed. The first Dirt metrics should probably be:

- `substrate_vwc`
- `substrate_temp_c`
- `substrate_bulk_ec_ds_m` for TEROS 12 only

The USB route gets data into the system fastest. The ESP32/WisBlock route is the better rehearsal for a future multi-plant bus.
