# Epic: Dashboard & Visualization

Status: planning
Priority: medium
Created: 2026-03-22

## Goal

Unified dashboard page combining the live webcam feed with Chart.js time-series graphs for temperature and humidity. The "log in and see everything" experience.

## Scope

- Dashboard page layout (Jinja2 + HTMX)
- Chart.js integration for temp/humidity graphs
- Time range selection for historical data
- Live webcam feed embed (from webcam epic)
- Summary stats (min/max/average)

## Acceptance Criteria

- Single page shows live webcam feed and sensor graphs
- Graphs update with new readings without full page reload
- User can select time ranges for historical data
- Dashboard loads quickly with reasonable data volumes

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:dashboard"`
