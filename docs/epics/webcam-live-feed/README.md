# Epic: Webcam Capture & Live Feed

Status: complete
Priority: high
Created: 2026-03-22

> **Post-completion note (2026-04-19):** the snapshot metadata DB was migrated from SQLite to Postgres 17 per [ADR-006](../../adrs/006-postgres-and-atlas.md). The ingest path + schema shape are equivalent; the `Snapshot.timestamp` column is now `Snapshot.ts` / `timestamptz`.

## Goal

Capture periodic snapshots from the Logitech C920 via OpenCV, store them to disk with metadata in SQLite, and serve a live feed page that auto-refreshes via HTMX. This is the first user-facing feature and establishes the capture pipeline, database foundation, and web UI shell.

## Scope

- OpenCV capture service (periodic snapshots from `/dev/video0`)
- Snapshot storage on disk with metadata (timestamp, path) in SQLite
- SQLite + SQLModel database initialization
- FastAPI endpoint to serve the latest snapshot
- HTMX page with auto-polling live feed
- Basic index/landing page structure

## Acceptance Criteria

- Webcam captures a snapshot on a configurable interval
- Snapshots are saved to disk and recorded in the database
- Web UI displays the latest snapshot and auto-refreshes
- Database schema is initialized on first run

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:webcam-live-feed"`
