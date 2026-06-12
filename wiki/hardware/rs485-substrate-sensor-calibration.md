---
title: "Hardware - RS485 Substrate Sensor Calibration"
type: hardware
sources: []
related: [wiki/hardware/rs485-substrate-sensors.md, wiki/hardware/soil-moisture-sensing-options.md]
created: 2026-06-10
updated: 2026-06-12
---

# RS485 Substrate Sensor Calibration

Calibration log for the DFRobot SEN0604 RS485 substrate probe on the Seeed Studio XIAO ESP32C3 + Seeed XIAO RS485 breakout. The probe has been changed to Modbus address `0x02`.

Keep probe-register calibration read-only for now. Current Dirt operational status for Plant A EC/pH is calibrated; maintain that calibration in Dirt/software and use new standards/reference captures as QA evidence before changing correction behavior.

## Current Firmware And Serial Capture

Production Plant A firmware now lives at:

```text
firmware/rs485_substrate_node/
```

Use the LAN status endpoints for normal operations:

```bash
curl -fsS http://plant-a-substrate-node.local/health
curl -fsS http://plant-a-substrate-node.local/status | jq .
```

Do not plug in normal USB while the board is powered through the RS485 board's 12 V runtime path. USB serial capture is for bench/debug work only, with 12 V disconnected.

Temporary debug firmware:

```text
debug/rs485_soil_probe/
```

Current posture:

- Serial-only debug firmware remains useful for bench calibration captures.
- Production WiFi/OTA/WebServer firmware is now live for Plant A runtime.
- Read-only Modbus polling at address `0x02`.
- Sensor serial settings: `9600 8N1`.
- Read command: `02 03 00 00 00 04 44 3A`.
- Register interpretation:
  - `0x0000` moisture, x10 percent
  - `0x0001` temperature, x10 deg C
  - `0x0002` EC, us/cm
  - `0x0003` pH, x10

Find the connected XIAO:

```bash
pio device list
```

Raw serial capture is preferred over `pio device monitor` for calibration because it avoids monitor buffering and gives cleaner complete lines:

```bash
stty -F /dev/ttyACM1 115200 raw -echo
timeout 45s cat /dev/ttyACM1 | tee /tmp/rs485_<label>.log
```

Replace `/dev/ttyACM1` with the port from `pio device list`; the board has appeared as both `/dev/ttyACM0` and `/dev/ttyACM1` after resets.

Useful parser for captured logs:

```bash
perl -ne 'if (/\[sensor\] moisture=([0-9.]+)% temperature=([0-9.]+)C ec=([0-9]+) us\/cm ph=([0-9.]+)/) { push @m,$1; push @t,$2; push @e,$3; push @p,$4; } END { sub mm { my @x=@_; return "n/a" unless @x; my ($min,$max)=($x[0],$x[0]); my $sum=0; for (@x){$min=$_ if $_<$min; $max=$_ if $_>$max; $sum+=$_} return sprintf("n=%d min=%.2f max=%.2f avg=%.2f first=%.2f last=%.2f", scalar(@x), $min, $max, $sum/@x, $x[0], $x[-1]); } print "moisture ", mm(@m), "\n"; print "temp_c ", mm(@t), "\n"; print "ec_us_cm ", mm(@e), "\n"; print "ph ", mm(@p), "\n"; }' /tmp/rs485_<label>.log
```

## Results

### pH 4 Buffer

Capture file: `/tmp/rs485_ph4_stabilization.log`

The probe was inserted into pH 4 buffer. Capture was still using the WiFi-enabled firmware and only produced two complete samples, but the raw frame repeated exactly.

| Metric | Result |
|---|---:|
| Samples | 2 |
| Moisture | 100.0% |
| Temperature | 24.8 deg C |
| EC | 20000 us/cm |
| pH | 3.0 |

Repeated raw frame:

```text
02 03 08 03 E8 00 F8 4E 20 00 1E 85 B6
```

Interpretation: in pH 4 buffer, this unit reported pH `3.0`, not `4.0`. EC saturated at `20000 us/cm`, so EC should not be interpreted from pH buffer solution.

### Air After pH 4 Buffer

Capture file: `/tmp/rs485_air_after_ph4_retry.log`

The probe was removed from the pH 4 buffer and placed in air.

| Metric | Result |
|---|---:|
| Samples | 1 |
| Moisture | 0.0% |
| Temperature | 22.4 deg C |
| EC | 0 us/cm |
| pH | 7.2 |

Interpretation: the probe clearly changed state after removal and no longer reported the pH 4 buffer values. More samples would be needed for a real dry-air stabilization curve.

### 1413 us/cm EC Standard

Capture file: `/tmp/rs485_ec1413_raw_serial.log`

The probe was inserted into a `1413 us/cm` EC calibration solution. Capture used the serial-only firmware and raw `cat` workflow.

| Metric | Result |
|---|---:|
| Samples | 22 |
| Moisture | 100.0% |
| Temperature | 24.6-24.7 deg C, avg 24.66 deg C |
| EC | 2533-2543 us/cm, avg 2535.05 us/cm |
| pH | 5.2-5.3, avg 5.25 |

Interpretation: against a `1413 us/cm` standard, this unit reported about `1.79x` high at roughly `24.6 deg C`.

### 84 us/cm EC Standard

Capture file: `/tmp/rs485_ec84_raw_serial.log`

The probe was inserted into an `84 us/cm` EC calibration solution. Capture used the serial-only firmware and raw `cat` workflow.

| Metric | Result |
|---|---:|
| Samples | 22 |
| Moisture | 100.0% |
| Temperature | 24.4-24.5 deg C, avg 24.45 deg C |
| EC | 106 us/cm |
| pH | 6.1-6.5, avg 6.28 |

Interpretation: against an `84 us/cm` standard, this unit reported `106 us/cm`, about `1.26x` high. EC was perfectly stable across the 22-sample window; pH drifted downward from `6.5` to `6.1` in the EC standard solution, so pH QA should use pH buffers or substrate/reference comparisons.

### 12.88 mS/cm EC Standard

Capture file: `/tmp/rs485_ec12880_raw_serial.log`

The probe was inserted into a `12.88 mS/cm` (`12880 us/cm`) EC calibration solution. Capture used the serial-only firmware and raw `cat` workflow.

| Metric | Result |
|---|---:|
| Samples | 23 |
| Moisture | 100.0% |
| Temperature | 24.5 deg C |
| EC | 20000 us/cm |
| pH | 5.6-5.8, avg 5.69 |

Interpretation: the sensor saturated at `20000 us/cm` for every sample. This point is useful as an upper-range failure/saturation check, but it cannot be used as a normal calibration anchor for the `12.88 mS/cm` standard.

## Next QA Points

- Repeat pH 4 with the serial-only firmware and capture at least 30 complete samples after stabilization.
- Capture pH 7 buffer, then pH 10 buffer if available.
- Capture an EC standard between `1413 us/cm` and `12880 us/cm` if available; `12880 us/cm` saturates the sensor at `20000 us/cm`.
- Rinse with DI water between standards and discard used buffer/standard aliquots.
- Record container, immersion depth, stabilization time, solution temperature, and reference meter reading for each run.
