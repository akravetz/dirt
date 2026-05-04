# Epic: Sensor Monitoring

Status: complete
Priority: high
Created: 2026-03-22

> **Post-completion note (2026-04-19):** sensor storage was migrated from SQLite to Postgres 17 per [ADR-006](../../adrs/006-postgres-and-atlas.md). `SensorReading.location` (free-form text) became `sensornode_id` (FK to the enum-typed `sensornode` table); timestamps are `timestamptz` with `LAG()` window functions replacing the SQLite datetime workarounds. Service surface unchanged: `get_latest_reading` / `get_sensor_history` / `ingest_reading`.

> **Current schema note (2026-05-04):** the later scoped device/capability
> cleanup retired `sensornode`, `sensor_location`, and
> `sensorreading.sensornode_id`. Current readings are capability-owned via
> `sensorreading.capability_id`; see [`../../database.md`](../../database.md).

## Goal

Ingest temperature and humidity readings from physical sensors, store them in SQLite, and expose via API endpoints. The sensor service interface will be designed ahead of hardware arrival so the dashboard can be built against mock data.

## Scope

- Sensor service interface (abstract, hardware-agnostic)
- Concrete implementation once hardware is identified
- Ingestion loop storing readings to SQLite
- SQLModel models for sensor readings
- API endpoints: latest reading, historical data with time range

## Acceptance Criteria

- Sensor readings are captured at a configurable interval
- Readings are stored in SQLite with timestamps
- API returns latest reading and historical data for a given time range
- Service gracefully handles sensor disconnection

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:sensor-monitoring"`
