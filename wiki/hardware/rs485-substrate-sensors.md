---
title: "Hardware - RS485 Substrate Sensors"
type: hardware
sources: []
related: [wiki/hardware/soil-moisture-sensing-options.md, wiki/hardware/esp32-plant-nodes.md, wiki/hardware/project-box-enclosures.md]
created: 2026-06-09
updated: 2026-06-12
---

# RS485 Substrate Sensors

Status: Plant A production interim substrate node is live as of 2026-06-10 evening MDT. DFRobot SEN0604 is reading over RS485/Modbus at address `0x02`, and `plant-a-substrate-node` is the canonical current Plant A moisture source in Dirt. Moisture is the operational direct-percent signal, and EC/pH are current calibrated operational streams. Continue periodic cross-checks against hand measurements when troubleshooting.

## Production Cutover

Plant A now uses the dedicated RS485 substrate node:

```text
Device ID: plant-a-substrate-node
Hostname: plant-a-substrate-node.local
IP observed at cutover: 192.168.1.40
Firmware: 0.1.0-rs485-substrate
Runtime power: 12 V into the Seeed RS485 expansion board, USB unplugged
Status endpoint: http://plant-a-substrate-node.local/status
Health endpoint: http://plant-a-substrate-node.local/health
```

Post-cutover validation on 2026-06-10 evening MDT showed `/health` returning `{"ok":true,"modbus":"ok","ingest_code":202}` and `/status` reporting Modbus OK, WiFi RSSI about `-37 dBm`, zero Modbus failures, and latest sample around `26.6%`, `21.5 deg C`, `144 us/cm`, pH `4.5`.

Dirt database state after the cutover:

- Plant A's active telemetry mapping points at `plant-a-substrate-node:soil_moisture_pct`.
- Plants B-D have no current moisture capability until trustworthy replacement probes exist.
- Old capacitive devices `plant-a-node` through `plant-d-node` and their `soil_moisture_raw` capabilities are disabled/retired in active inventory.
- Historical capacitive readings and calibrations remain available for audit/history.

Operator note: it is safe to physically disconnect the old capacitive moisture nodes. The dashboard/device watchdog should not report them as offline after the retirement migration because disabled devices are filtered from system status.

## Current Bench Setup

Hardware: Seeed Studio XIAO ESP32C3 on the Seeed XIAO RS485 breakout board, DFRobot SEN0604 RS485 4-in-1 soil moisture/temperature/pH/EC sensor. Production runtime is 12 V into the RS485 expansion board's power path with normal USB unplugged. The earlier USB-powered bench/debug topology is retained here only for reference.

Set the breakout `5V OUT/IN` switch according to the actual power topology. Do not connect normal USB at the same time as an externally supplied 5 V/VBUS path.

Wiring for the DFRobot SEN0604:

```text
Sensor brown  -> breakout 5V terminal
Sensor black  -> breakout GND
Sensor yellow -> breakout RS485 A
Sensor blue   -> breakout RS485 B
```

If sensors move to 12 V power, do not feed 12 V into the breakout 5 V terminal:

```text
12V supply +  -> sensor brown
12V supply -  -> sensor black
12V supply -  -> breakout/XIAO GND
Breakout A    -> sensor yellow
Breakout B    -> sensor blue
```

Ground must be common between the sensor supply and XIAO/RS485 board. Do not connect 5 V or 12 V to any XIAO GPIO.

## Modbus Bring-Up

The debug firmware lives at `debug/rs485_soil_probe/`.

Observed board: `/dev/ttyACM0`, USB VID:PID `303A:1001`, serial `E8:F6:0A:14:A3:C8`, description `USB JTAG/serial debug unit`.

Firmware assumptions for SEN0604:

```text
Modbus address: 0x02
Serial: 9600 8N1
Read command: 02 03 00 00 00 04 44 3A
Registers:
  0x0000 moisture, x10 percent
  0x0001 temperature, x10 deg C
  0x0002 EC, us/cm
  0x0003 pH, x10
```

The firmware produced valid Modbus responses with passing CRC checks.

## First Live Readings

| Location | Moisture | Temperature | EC | pH |
|---|---:|---:|---:|---:|
| Plant A | 23.0-23.1% | 19.7-19.8 deg C | 128-130 us/cm = 0.128-0.130 mS/cm | 5.0-5.3 |
| Other plant | 36.3-36.4% | 20.2 deg C | 279-283 us/cm = 0.279-0.283 mS/cm | 5.5-5.7 |

This confirms the sensor is not stuck; moisture and EC changed materially with probe location. Cannabis feed EC is normally discussed in mS/cm, while this sensor reports us/cm:

```text
1000 us/cm = 1.0 mS/cm
```

## Bus And Enclosure Plan

No multiplexer is needed for normal RS485 use. Use one RS485 bus and give each sensor a unique Modbus slave address:

```text
XIAO RS485 board ---- sensor 1 ---- sensor 2 ---- sensor N
```

Keep the bus as a daisy chain with short stubs. Terminate only the two physical ends if communication becomes flaky; do not terminate every sensor.

For project-box quick disconnects, put female M12 A-coded 4-pin panel receptacles on the box and male M12 A-coded 4-pin field-wireable plugs on sensor cables. Use pin numbers, not pigtail colors, as the authority.

Suggested pinout:

```text
M12 pin 1 -> +12V
M12 pin 3 -> GND
M12 pin 2 -> RS485 A
M12 pin 4 -> RS485 B
```

Female receptacles belong on the powered box side because recessed contacts are harder to short and less likely to be bent when a sensor is unplugged.

## Calibration Posture

DFRobot documents writable calibration registers but does not publish a complete calibration procedure:

```text
0x0050 temperature calibration
0x0051 moisture calibration
0x0052 conductivity calibration
0x0053 pH calibration
```

Do not write these registers yet. A DFRobot forum report for SEN0604 indicates the pH calibration register behaves like a single-point offset: an offset that made pH 7 buffer read correctly made pH 4 buffer wrong. That is not enough for a real multi-point pH calibration.

Current operational status in Dirt is calibrated for moisture, EC, and pH. Store the raw sensor values and apply/maintain calibration in Dirt/software. This preserves the factory state and lets future reference checks refine slope, offset, and curve behavior without rewriting probe registers.

## Ongoing Calibration QA Plan

Use the high-precision pH/EC probe and standards as the reference instrument. Record raw SEN0604 values, reference values, temperature, media/sample description, probe depth, and stabilization time.

### Temperature

Use water baths because the probe is IP68. Test at three points: ice bath near 0 deg C, room-temperature water, and warm water around 25-30 deg C. Measure with a trusted thermometer, wait for the SEN0604 to stabilize at each point, then fit either offset-only correction or an affine correction:

```text
true_temp_c = a * sensor_temp_c + b
```

### Moisture

Calibrate in the actual coco/perlite mix, not in water solutions. Prepare a known-volume sample container with the same coco/perlite and representative packing, measure dry/baseline sample mass, add known water masses across the expected operating range, mix/seal/equilibrate each point, insert the probe fully and vertically, and calculate reference volumetric water content:

```text
VWC = water_volume_ml / sample_volume_ml
```

Fit raw moisture percent to media-specific VWC or to a practical dryback index.

### EC

Do both a solution check and a substrate validation. For the solution check, use conductivity standards near the expected range, such as 1413 us/cm plus a lower and higher point if available; measure the same solution with the reference EC probe; read SEN0604 after stabilization at the same temperature; then fit:

```text
true_ec_us_cm = a * sensor_ec_us_cm + b
```

For substrate validation, place the SEN0604 in coco and log moisture plus EC; take runoff, slurry, or saturated-paste extract from the same zone when practical; measure extract EC with the reference probe; and use the comparison as ongoing QA for drift or systematic offset under coco moisture and packing conditions.

### pH

Use external multi-point correction only. Characterize readings in fresh pH 4, pH 7, and pH 10 buffers; rinse with DI water between buffers; do not return used buffer to stock bottles; wait for stable SEN0604 readings at each point; and fit piecewise correction curves:

```text
pH 4-7 range:  true_ph = a_low * sensor_ph + b_low
pH 7-10 range: true_ph = a_high * sensor_ph + b_high
```

For cannabis/coco, pH 4 and pH 7 are the important anchors around the useful 5.5-6.5 range; pH 10 is a sanity check for slope/nonlinearity. Use runoff, slurry, or manual meter comparisons as ongoing QA when readings drive operational decisions or look inconsistent with plant behavior.

## Sources

- DFRobot SEN0604 product page: <https://www.dfrobot.com/product-2830.html>
- DFRobot SEN0604 wiki and Modbus register docs: <https://wiki.dfrobot.com/sen0604/> and <https://wiki.dfrobot.com/sen0604/docs/20297>
- DFRobot forum report on SEN0604 pH calibration behavior: <https://www.dfrobot.com/forum/topic/399211>
- Seeed XIAO RS485 Expansion Board wiki: <https://wiki.seeedstudio.com/XIAO-RS485-Expansion-Board/>
- Virginia Tech / University of Georgia soil moisture sensor overview: <https://ext.vt.edu/content/pubs_ext_vt_edu/en/BSE/BSE-338/BSE-338.html>
- NC State soil-water device calibration guide: <https://content.ces.ncsu.edu/publication/calibrating-soil-water-measuring-devices>
- Laboratory soil moisture sensor calibration study: <https://pmc.ncbi.nlm.nih.gov/articles/PMC5134571/>
- EPA pH meter calibration and maintenance SOP: <https://www.epa.gov/sites/default/files/2018-01/documents/eq-01-08.pdf>
- EPA field instrument calibration SOP, including conductivity/specific conductance: <https://19january2021snapshot.epa.gov/quality/standard-operating-procedure-calibration-field-instruments-temperature-ph-dissolved-oxygen_.html>
- YSI conductivity calibration standards note: <https://www.ysi.com/product/id-3161/conductivity-calibrator-solution>
