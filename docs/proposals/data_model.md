# data_model.md — first-pass proposal

**Status**: draft 1 for review. Companion to `API.md`. Every new/changed table below is driven by a concrete UI need. Items marked **MOCK** are UI-visible fields we are not collecting today — the proposal is to ship the API shape now and backfill storage + ingestion later.

Principles:
- **Don't touch `SensorReading`/`SensorCalibration`/`SensorNode`/`Snapshot`** — they are working and hot-path. New data lives in new tables.
- **Wiki stays authoritative for narrative content** (timelines, quotes, daily logs). SQL only gets structured/queryable data.
- **Mock before ingest** — synthesize plausible values for fields the UI shows but sensors don't report, so the UI doesn't have to change when real data arrives.

---

## Summary table

| Proposal | Kind | UI driver | Status |
|---|---|---|---|
| New: `Plant` | table | dashboard strip, plant drawer | ADD |
| New: `PlantVitalReading` | table | plant drawer (pH, distance, nodes) | ADD (mock data to start) |
| New: `StageTarget` | table | gauge target bands, editability later | ADD (seed from `grow_state.STAGE_TARGETS`) |
| New: `DeviceHeartbeat` | table | system-devices status table | ADD |
| New: `HumidifierEvent` | table | humidifier history + "last reason" | ADD |
| Update: `SensorReading` | column | track `reservoir_in` + `fan_pct` when hardware arrives | NO SCHEMA CHANGE — just new `metric` values |
| No change: `SensorCalibration` | — | calibrated plant % (unchanged) | — |
| No change: `SensorNode` | — | sensor device online/last_seen (unchanged) | — |
| No change: `Snapshot` | — | latest-snapshot endpoint (unchanged) | — |
| No change: `GrowState` | — | stage derivation + lights (unchanged) | — |
| **MOCK**: `fan_pct` metric | sensor data | gauge + sparkline | backend returns synthesized series until hardware lands |
| **MOCK**: `reservoir_in` metric | sensor data | gauge + sparkline | same |
| **MOCK**: `runoff_ph` / `distance_from_light_in` / `node_count` | plant vitals | drawer | served from `PlantVitalReading` with `source="mock"` rows seeded at startup |
| **MOCK**: `timeline` / `quote` on `/api/plants/{id}` | narrative | drawer | parsed from wiki page for v1 — no SQL |
| **MOCK**: `irrigation_events` on `/api/plants/{id}/history` | derived | drawer chart | detected from soil-% jumps; empty array acceptable |

---

## New: `Plant` table

The UI needs a structured source for plant identity (name, strain, primary/secondary, purple flag). Today this lives only in wiki markdown, which is not queryable.

```python
# apps/shared/src/dirt_shared/models/plant.py
class Plant(SQLModel, table=True):
    id: str = Field(primary_key=True)                 # "a" | "b" | "c" | "d"
    name: str                                         # "Plant A"
    label: str | None = None                          # "Purple Keeper Candidate"
    strain: str | None = None                         # "Sirius Black × BS01"
    sensor_location: str                              # "plant-a" — links to SensorReading.location
    status: str = "secondary"                         # "primary" | "secondary"
    purple: bool = False                              # genetic anthocyanin confirmed
    transplanted_on: date | None = None               # for day-count in drawer
    topped_on: date | None = None                     # cosmetic flag on timeline
    notes: str | None = None                          # short, shown in drawer frontmatter
    wiki_path: str | None = None                      # "plants/plant-a.md"
    ptz_preset_id: str | None = None                  # "plant_a"
```

- Seed migration writes the current 4 plants (a/b/c/d) with hard-coded values matching the mockup.
- `sensor_location` bridges to `SensorReading.location` — no FK because sensor locations are strings, not normalized.
- `soil_moisture_pct`, `day` are derived on read, not stored.
- The wiki page remains the source of truth for prose; this table is the queryable slice the UI needs.

---

## New: `PlantVitalReading` table

Three drawer fields are not sensor-driven today: **runoff pH**, **distance from light**, and **node count**. Rather than inlining them as columns on `Plant` (which would lose history), give them their own reading stream parallel to `SensorReading`.

```python
# apps/shared/src/dirt_shared/models/plant_vital_reading.py
class PlantVitalReading(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    plant_id: str = Field(index=True, foreign_key="plant.id")
    metric: str = Field(index=True)                    # "runoff_ph" | "distance_from_light_in" | "node_count"
    value: float
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    source: str = "manual"                             # "manual" | "mock" | "sensor" (future)
    note: str | None = None                            # free-form ("topped at 4", etc.)
```

- Seed migration inserts one mock row per (plant, metric) so the drawer has data to render immediately.
- When we wire up a UI form or a pH meter later, rows carry `source="manual"` or `source="sensor"` — no schema change.
- UI reads "latest per (plant, metric)" to fill the drawer vitals table.

---

## New: `StageTarget` table

Today `STAGE_TARGETS` is a Python dict in `grow_state.py`. The gauges need the current band, and we eventually want users to edit bands without a code deploy.

```python
# apps/shared/src/dirt_shared/models/stage_target.py
class StageTarget(SQLModel, table=True):
    stage: str = Field(primary_key=True)               # "veg" | "flower_early" | "flower_late"
    metric: str = Field(primary_key=True)              # "temperature_f" | "humidity_pct" | "vpd_kpa"
    lo: float
    hi: float
    unit: str                                          # "°F" | "%" | "kPa"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

- Seed the 9 rows (3 stages × 3 metrics) from the current `STAGE_TARGETS` dict at migration time.
- `grow_state.current_targets()` becomes a DB read with an in-process cache. The humidifier loop, the daily-report validator, and the new `/api/sensors/current` all consume through this same function.
- **Out of scope v1**: an edit UI. Just making the values queryable + editable via SQL for now.

---

## New: `DeviceHeartbeat` table

The system-devices table on the dashboard lists 8 devices, but only 5 (Arduino + 4 ESP32s) have a natural "last seen" from `SensorNode`. Camera, Jabra, and humidifier-plug status are not tracked anywhere queryable.

Options:
- **A**: have `dirt-web` shell out to `systemctl --user is-active` per request — simple, but couples web to systemd and adds latency.
- **B** (proposed): every long-running daemon writes a tiny heartbeat row every N seconds. Web reads the latest per device.

```python
# apps/shared/src/dirt_shared/models/device_heartbeat.py
class DeviceHeartbeat(SQLModel, table=True):
    device_id: str = Field(primary_key=True)           # "obsbot" | "jabra" | "humidifier" | ...
    label: str                                         # "OBSBOT Tiny 2 Lite"
    status: str                                        # "online" | "listening" | "offline" | "error"
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    detail: str | None = None                          # free text (error cause, mode)
```

- Upsert pattern: each daemon writes `{device_id, status, last_seen=now, detail}` on every loop tick.
- `dirt-web` reads all rows once per `/api/system/devices` call + combines with `SensorNode.last_seen` for sensor nodes.
- Writers required:
  - `dirt-camera` — writes `obsbot` heartbeat on every successful frame capture.
  - `dirt-voice` — writes `jabra` heartbeat on every wake-listen tick.
  - `dirt-hwd` humidifier loop — writes `humidifier` heartbeat on every control tick (already runs every 30s).
- Thresholds: `online` if last_seen < 2× the writer's tick interval, else `offline`.

This is strictly additive. Existing services keep working if they don't write yet — `dirt-web` just reports `offline` for the missing rows.

---

## New: `HumidifierEvent` table

The humidifier tile needs "last reason" + 24h cycle count, and the duty-cycle strip needs on/off history. We have both inside `var/logs/humidifier/<DATE>.jsonl` today, but log files rotate (30-day retention) and aren't SQL-queryable.

We **already** record the on/off state as `SensorReading(metric="humidifier_on")` rows — that's enough for cycle count + duty cycle. What's missing is the **reason** field, the **stage**, and the **target band** at each transition.

Proposal: add a dedicated event table for state transitions only (not every tick). This lets us answer "why was the humidifier on at 14:20?" without log spelunking.

```python
# apps/shared/src/dirt_shared/models/humidifier_event.py
class HumidifierEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    new_state: str                                     # "on" | "off"
    reason: str                                        # "vpd_above_upper_band" | "vpd_below_upper_band" | "failsafe_stale_sensor" | "lights_off_prep"
    vpd_kpa: float | None = None                       # reading at decision time
    vpd_age_s: float | None = None
    stage: str | None = None                           # "veg" | "flower_early" | "flower_late"
    upper_band_kpa: float | None = None                # effective band at decision time
    lower_band_kpa: float | None = None
    lights_on: bool | None = None
    minutes_until_off: float | None = None
```

- Written by `humidifier_loop` on every state transition only (not every poll). Today those transitions land in the JSON log; we add a parallel DB insert.
- The existing log stream continues — the DB table is a **queryable projection** of the same events. Retention in SQL is indefinite (small: maybe 30 rows/day).
- `/api/humidifier/state` reads the most-recent row for `last_reason` + `target_band_kpa`.
- `/api/humidifier/history` keeps using `SensorReading(metric="humidifier_on")` (no change).

---

## Fields we are NOT collecting today (MOCK flags)

These are UI fields with no real source of truth yet. Proposal: backend returns plausible synthetic values with `_mock: true` flags, so the UI ships verbatim and gets real data when the sensors do.

| UI field | Shape | Today's source | When real | Mock strategy |
|---|---|---|---|---|
| `fan_pct` | 0–100 int | nothing | after fan PWM sensor wired via Arduino | linear random walk around 48%, range 40–60; stored as `SensorReading(metric="fan_pct", location="tent")` so the sparkline query path is identical |
| `reservoir_in` | float, inches | nothing | after water-level sensor arrives | slow-decay sawtooth (refill = +4in events on daily_report runs); stored as `SensorReading(metric="reservoir_in", location="tent")` |
| `runoff_ph` | float 5.0–7.0 | manual wiki notes | user types into drawer (future) | one `PlantVitalReading(source="mock", metric="runoff_ph", value=5.9)` seeded per plant |
| `distance_from_light_in` | int, inches | manual wiki | user types into drawer | seeded mock per plant |
| `node_count` | int | wiki narrative | manual field | seeded mock per plant |
| Plant `timeline` | list of events | wiki markdown parse | — | parse wiki `plants/plant-*.md` bullet list; v1 stub if parse fails |
| Plant `quote` | string | wiki daily page | — | parse wiki daily page for the most recent blockquote mentioning the plant; v1 stub |
| `irrigation_events` | list of deltas | derived | — | detect >10% jumps across 2 buckets in soil-% series; empty array is fine |

Rule: **every mocked metric uses the same storage path as the real one**. Mock generators write into `SensorReading` or `PlantVitalReading` on a timer during dev; in production, once hardware is attached, those generators turn off and real rows flow in. No API contract change.

---

## Migration order

1. `StageTarget` + seed from `STAGE_TARGETS` dict.
2. `Plant` + seed 4 rows matching the mockup.
3. `PlantVitalReading` + seed 3 mock rows per plant (pH, distance, nodes).
4. `DeviceHeartbeat` (empty; writers land later).
5. `HumidifierEvent` (empty; humidifier loop starts writing on next deploy).
6. Mock-value writer for `fan_pct` / `reservoir_in` — optional hwd-side loop that synthesizes rows every 30s while `settings.mocks_enabled=True`. Default True until hardware exists.

---

## What stays untouched

- `SensorReading` — already has the right shape for any new metric. We just add new `metric` string values; no schema change.
- `SensorCalibration` — continues to auto-widen for `soil_moisture_raw`.
- `SensorNode` — continues to capture last-seen / ip / firmware / uptime for the 5 upstream nodes.
- `Snapshot` — latest-snapshot endpoint reads it as-is.
- `GrowState` — stage derivation + lights schedule stay exactly where they are. `current_targets()` starts reading from `StageTarget` but the *caller* API (`grow_state.current_targets()`) is unchanged.

---

## Open questions for this review pass

1. **Plant as a table vs hard-coded**: v1 could live with a hardcoded `PLANTS = [...]` module constant and skip the `Plant` table entirely. Adding a table costs a migration but unlocks per-plant settings, edit UI, and keeps wiki paths out of Python. Table wins IMO — but cheap to defer.
2. **`PlantVitalReading` granularity**: one table with `(plant_id, metric, value)` is maximally flexible. Alternative: three columns on `Plant` (`last_ph`, `last_distance_in`, `last_node_count`). Alt is simpler but loses history. Prefer the reading table.
3. **`DeviceHeartbeat` writers**: cross-daemon write pattern is new. Acceptable cost? The alternative (dirt-web shelling out to systemctl per request) is simpler but uglier and slower.
4. **`HumidifierEvent` vs JSON logs**: duplication is fine since the SQL version is the long-lived queryable projection. Confirm you're OK with the dual write.
5. **Mock metric strategy**: writing synthesized `fan_pct`/`reservoir_in` rows into `SensorReading` means the DB has fake data in it. Acceptable for a pre-production system? Alternative: compute mocks on-the-fly in the API handler and skip DB writes. I lean DB writes because it exercises the same code path real data will — no surprises when we swap ingest sources.
6. **Stage target editability**: this proposal adds the table but no edit UI. OK to defer edit-UI to a later feature, or bundle it now? Current thinking: defer; the table-ification alone is the win.
7. **Heartbeat granularity**: one row per device (upsert) vs append-only history. Proposed upsert — history-over-time is not in any v1 UI. Flag for later if we want an uptime chart.
