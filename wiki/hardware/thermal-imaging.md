---
title: "Hardware — Thermal Imaging (PureThermal Mini Pro + FLIR Lepton 3.5)"
type: hardware
sources: []
related: [wiki/concepts/vpd.md, wiki/environment/temperature.md, wiki/environment/humidity.md, wiki/hardware/ptz-camera.md, wiki/overview.md]
created: 2026-05-02
updated: 2026-05-02
---

# Thermal Imaging — PureThermal Mini Pro + FLIR Lepton 3.5

Planned fixed thermal camera for canopy temperature measurement. The goal is not a pretty thermal thumbnail by itself; the goal is to measure leaf/canopy temperature relative to tent air temperature so Dirt can estimate leaf-level VPD more accurately and identify relative canopy hot spots.

## Goal

Use a fixed thermal sensor to produce three daily/control-loop artifacts:

1. **Leaf/canopy temperature metrics** — min, median, p95, max, and per-zone stats for the SCROG canopy.
2. **Leaf-air delta** — canopy temperature minus tent SHT45 air temperature, tracked over time.
3. **Hotspot map** — false-color overlay for human inspection, backed by raw radiometric temperature data for agent decisions.

Primary use cases:

- Detect warm canopy zones caused by light intensity, poor airflow, or localized transpiration slowdown.
- Detect cool/wet zones that may indicate heavy evaporation, humidifier plume influence, or stagnant high-RH pockets.
- Replace air-temperature-only VPD estimates with leaf-temperature-aware VPD estimates.
- Give daily reports a quantitative canopy temperature summary instead of relying only on visual RGB photos.

## Selected Hardware

**SparkFun DEV-17544 — PureThermal Mini Pro JST-SR with FLIR Lepton 3.5**

What matters for Dirt:

| Component | Role |
|---|---|
| PureThermal Mini Pro JST-SR | USB UVC bridge and hackable STM32F412 carrier board for the Lepton core. |
| FLIR Lepton 3.5 | 160x120 radiometric LWIR thermal sensor. |
| JST-SR to USB cable | Required; the SparkFun kit does not include it. |

Relevant specs:

| Spec | Value |
|---|---|
| Thermal resolution | 160x120 |
| Effective frame rate | ~8.7 Hz / 9 Hz class |
| HFOV | 57 deg |
| Sensor output | User-selectable 14-bit, 8-bit AGC, or 24-bit RGB/false-color |
| Radiometry | Lepton 3.5 supports per-pixel temperature data |

## System Role

This is a **fixed canopy sensor**, not a replacement for the OBSBOT PTZ camera.

The OBSBOT Tiny 2 Lite remains the visual inspection camera: plant presets, daily RGB photos, and manual PTZ closeups. The PureThermal/Lepton should be mounted rigidly in the tent so the thermal frame maps consistently to the SCROG/canopy plane.

Proposed data path:

```text
PureThermal + Lepton
  -> stable /dev/thermal-camera symlink
  -> thermal capture service
  -> raw radiometric frame (.npy or 16-bit TIFF)
  -> thermal summary JSON
  -> false-color overlay image
  -> daily report / dashboard / wiki synthesis
```

## VPD Calculation

The existing [VPD concept page](../concepts/vpd.md) documents the air-temperature approximation. Thermal imaging lets us improve that approximation.

For leaf-level VPD:

- **SVP_leaf** should be computed from measured leaf/canopy temperature.
- **AVP_air** should come from tent air temperature and RH measured by the SHT45.
- **Leaf VPD** = `SVP_leaf - AVP_air`.

Do not compute AVP from leaf temperature and ambient RH. RH belongs to the air measurement; the leaf temperature changes the saturation vapor pressure at the leaf surface, not the measured amount of water vapor already in the tent air.

Expected interpretation:

| Pattern | Meaning |
|---|---|
| Leaf temp below air temp | Normal evaporative cooling; transpiration is active. |
| Leaf temp near or above air temp | Possible low transpiration, excessive light load, poor airflow, or root-zone stress. |
| Localized hot spot | Likely light/airflow imbalance, leaf angle, or impaired transpiration in that zone. |
| Localized cool spot | Possible humidifier plume, wet surface influence, or unusually high evaporation. |

## Raw Data vs. Colorized Output

The human overlay is only a presentation layer. Agent decisions should use raw radiometric frames.

The PureThermal can expose easy display output as a normal UVC video stream, but RGB/false-color frames are not reliable temperature data because palette and AGC mappings can change. The integration should request a raw 16-bit thermal format such as Y16/GRAY16_LE, convert those values to temperature, and then generate its own false-color overlay from the numeric frame.

Target artifacts per capture:

```text
thermal_raw.npy              # uint16 or float temperature frame
thermal_summary.json         # min/max/median/p95, leaf-air delta, zone stats
thermal_overlay.jpg          # human-readable false-color overlay
thermal_debug_color.jpg      # optional raw display-mode capture for bring-up only
```

## Mounting Plan

Preferred mount: fixed overhead or high front/top angle aimed at the SCROG plane.

Constraints:

- Keep the thermal sensor off the OBSBOT gimbal.
- Mount rigidly; avoid cable drag moving the board.
- Avoid reflective or transparent barriers in front of the Lepton lens. LWIR does not behave like visible light through common plastics/acrylic.
- Keep humidifier mist from condensing on the board or lens.
- Add physical strain relief for the JST-SR USB cable.
- Expect canopy-height drift; recalibrate zone mapping as the canopy rises through the SCROG.

Initial zone mapping can be simple quadrants for Plants A/B/C/D. Refine to polygons if parallax or canopy spread makes quadrants misleading.

## Bring-Up Checklist

1. Connect outside the tent and verify USB enumeration with `lsusb`.
2. Identify the video node with `v4l2-ctl --list-devices`.
3. Check supported formats with `v4l2-ctl --list-formats-ext`.
4. Verify colorized UVC output for basic hardware health.
5. Verify raw Y16/GRAY16_LE capture.
6. Convert raw values to deg F / deg C and validate against a known target.
7. Create a udev rule for a stable `/dev/thermal-camera` symlink.
8. Mount in tent and capture first overhead thermal frame.
9. Define A/B/C/D canopy zones.
10. Add daily-report integration only after raw radiometry is validated.

## Calibration Notes

Thermal readings are useful immediately for relative hot/cool mapping, but absolute temperatures need validation.

Minimum calibration/validation:

- Compare against tent SHT45 air temperature for a matte object that has equilibrated with tent air.
- Compare against a simple contact probe or known-temperature water target outside the tent.
- Log shutter/FFC events if exposed by the capture stack; frames around correction events may jump.
- Track median canopy temperature, not only max. A single hot pixel is less useful than sustained p95 or zone-level elevation.

Measurement caution:

- Cannabis leaves have high emissivity, so thermal measurement is usually workable.
- Wet leaves, shiny hardware, reflective labels, tent Mylar, and water surfaces can distort thermal readings.
- The Lepton's resolution is low relative to RGB; treat the output as canopy-zone telemetry, not leaf-edge diagnosis.

## Integration Plan

Phase 1 — bench validation:

- Prove raw radiometric capture on Linux.
- Write a throwaway capture script under `debug/`.
- Save one raw frame, one converted temperature array, and one false-color image.

Phase 2 — stable device:

- Add udev symlink and a small thermal capture service.
- Store raw frames under `var/thermal/` or a dated `var/raw/thermal/` path.
- Emit summary metrics suitable for daily synthesis.

Phase 3 — daily report:

- Capture thermal frame near the RGB daily photo set.
- Include leaf-air delta, canopy p95, max, and per-plant zone stats in the synthesis context.
- Attach overlay image only if it adds human value; raw metrics are the primary signal.

Phase 4 — control feedback:

- Use leaf-level VPD as an advisory signal for humidifier/fan/light decisions.
- Do not directly close the loop on thermal data until several days of baseline behavior exist.

## Open Questions

- Exact Linux capture path: V4L2 `Y16` directly, GroupGets/libuvc radiometry example, or a small dedicated helper around the UVC extension controls.
- Storage format: `.npy` is easiest for agents/Python; 16-bit TIFF is more portable; both may be worth keeping initially.
- Zone model: quadrants first, then calibrated polygons if RGB/thermal overlay proves stable.
- Whether to add a fixed RGB companion camera for overlay alignment, or use the OBSBOT overview frame as a loose visual reference.

## References

- SparkFun product page: https://www.sparkfun.com/purethermal-mini-pro-jst-sr-with-flir-lepton-3-5.html
- GroupGets PureThermal Mini Pro: https://groupgets.com/products/purethermal-mini-pro-jst-sr
- GroupGets PureThermal UVC capture examples: https://github.com/groupgets/purethermal1-uvc-capture
- FLIR Lepton 3.5 listing: https://groupgets.com/collections/frontpage/products/flir-lepton-3-5
