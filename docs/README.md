# Dirt Documentation

Dirt is a home grow monitoring system with three components:

1. **Web UI** — Lightweight dashboard showing live webcam feed, temperature/humidity graphs over time
2. **Backend** — API serving sensor data, webcam captures, and historical readings
3. **MCP Server** — Claude Desktop integration for querying latest screenshots, sensor history, and grow status

## Documentation Map

| Directory | Purpose |
|-----------|---------|
| `adrs/` | Architecture Decision Records — why we made key technical choices |
| `epics/` | Epic and issue tracking — feature planning, tasks, and progress |
| `progress/` | Feature progress tracking between PRs |
| `rules/` | Codebase rules and conventions Claude must follow |

## ADRs

ADRs follow the [Nygard format](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions). Each records a single decision with Context, Decision, and Consequences. Numbered sequentially, never reused. See `adrs/` for the full list.

## Epics

`epics/` organizes work into epics (major features) and issues (individual tasks). Each epic is a directory with a README and an `issues/` subdirectory. See `epics/README.md` for format details and rules for Claude.

## Progress Tracking

`progress/` tracks feature progress between PRs. Lightweight status updates — see `epics/` for the full work breakdown.

## Rules

`rules/` contains codebase-specific conventions and constraints. Claude should read relevant rule files before making changes in affected areas.
