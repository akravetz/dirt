# Epic: Sensor Monitoring

Status: blocked
Priority: high
Created: 2026-03-22
Blocked: Waiting on sensor hardware (~April 1, 2026)

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
