---
title: "Server-Side Auto-Calibration for Soil Moisture"
type: decision
sources: []
related: [wiki/hardware/esp32-plant-nodes.md, wiki/concepts/capacitive-soil-moisture.md, wiki/decisions/2026-04-12-distributed-sensor-architecture.md]
created: 2026-04-14
updated: 2026-04-14
---

# Decision: Server-Side Auto-Calibration for Soil Moisture

**Date:** 2026-04-14
**Status:** Accepted

## Context

Capacitive soil moisture sensors produce different raw ADC values for the same physical moisture depending on the unit (per-sensor manufacturing variation) and the growing medium (different dielectric constants). To turn a raw ADC reading into a useful 0–100% figure, we need calibration anchors for each sensor.

Two questions: where do calibration constants live, and how are they maintained?

## Decision

Calibration lives in the database, one row per `(location, metric)`, with extrema updated automatically at ingest. Percentage is derived on read via JOIN with `sensorreading` — **never stored** — so recalibration is retroactive.

### Schema

```python
class SensorCalibration(SQLModel, table=True):
    location: str = Field(primary_key=True)   # e.g., "plant-a"
    metric: str   = Field(primary_key=True)   # e.g., "soil_moisture_raw"
    raw_low: float   # wettest ADC seen (→ 100%)
    raw_high: float  # driest ADC seen  (→ 0%)
```

### Auto-update rule

On each `POST /api/ingest/sensors` for a metric in `AUTO_CALIBRATED_METRICS` (currently `{"soil_moisture_raw"}`):

- If raw value is outside the `[100, 3900]` clamp range → ignore (noise spike)
- If no row exists for `(location, metric)` → create with `raw_low = raw_high = value`
- Else widen: `raw_low = min(raw_low, value)`, `raw_high = max(raw_high, value)`

### Derivation (read-time)

```python
def compute_calibrated_pct(raw, raw_low, raw_high):
    if raw_high <= raw_low:
        return None   # degenerate — only one reading seen
    pct = 100.0 * (raw_high - raw) / (raw_high - raw_low)
    return max(0.0, min(100.0, pct))
```

Clamps to [0, 100] for readings outside the observed range.

## Why Server-Side, Not Firmware

| Aspect | Server-side (chosen) | Firmware-baked |
|---|---|---|
| Recalibration | Update a DB row | Reflash every board |
| Firmware uniformity | All boards run identical binary (plant ID is build-time) | Each board needs per-unit constants |
| Historical re-interpretation | Retroactive — past raw values re-pct on query | Past readings frozen at original cal |
| Source of truth | Raw ADC (preserved forever) | Pct (rewritten on every cal change) |
| Complexity per node | Minimal | Per-node constants table or NVS storage |

## Why Auto-Widening Extrema, Not Manual Anchors

We considered seeding calibration rows with bench-measured anchors (air = dry anchor, water = wet anchor) during deployment. Rejected in favor of passive auto-widening because:

- Real-world extremes differ from bench: bone-dry soil isn't the same dielectric as ambient air; saturated coco isn't the same as distilled water. Bench anchors under-utilize the actual sensor range.
- Self-calibrates with no manual step — deploy the node, let it run, and after it's seen one dry and one wet cycle the pct is meaningful.
- The `[100, 3900]` clamp discards glitches (ADC at 0 or 4095 from a disconnected sensor, noise spikes, etc.) before they corrupt the anchors.
- If a sensor or pot is swapped, you can clear the row and let it rebuild — or leave it and it'll widen toward the new extremes naturally.

Trade-off: reported pct values shift slightly as the range widens during the first few cycles. They shift *toward truth*, which is fine.

## Consequences

- Firmware stays identical across all four plant nodes — only the `PLANT_ID` build flag differs.
- The readings service can expose `soil_moisture_pct` as a virtual metric at read time by joining `sensorreading` + `sensorcalibration` on `(location, metric)`. (Dashboard wiring for this is still pending.)
- Adding a new auto-calibrated metric is one line: add to `AUTO_CALIBRATED_METRICS` in `services/readings.py`.
- No migration is needed when we add more plant nodes — the first POST creates their calibration row.

## See Also

- [ESP32-C3 Per-Plant Nodes — hardware page](../hardware/esp32-plant-nodes.md)
- [Capacitive Soil Moisture — concept](../concepts/capacitive-soil-moisture.md)
- [Distributed Sensor Architecture (2026-04-12)](2026-04-12-distributed-sensor-architecture.md)
