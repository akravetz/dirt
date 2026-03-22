# ADR 002: Technology Stack

## Status

Accepted

## Context

Dirt is a home grow monitoring system running on a single home box. It needs to serve a web UI with live webcam feed and sensor graphs, expose an API for data access, and provide an MCP server for Claude Desktop integration. The project prioritizes simplicity, modern idiomatic Python, and minimal operational overhead.

## Decision

**Web Framework:** FastAPI — async-native, Pydantic validation built-in, automatic OpenAPI docs.

**Database:** SQLite via aiosqlite — single-box deployment, zero ops burden, sufficient for sensor time-series at this scale. DB is a single file, trivially backed up.

**ORM:** SQLModel — Pydantic models that double as ORM models, consistent with FastAPI's Pydantic-everywhere philosophy.

**Frontend:** Jinja2 templates + HTMX — server-rendered, no JS build toolchain. HTMX handles live updates (webcam polling, sensor refresh) with HTML responses from FastAPI.

**Graphing:** Chart.js (loaded via CDN) for temperature/humidity time-series charts.

**MCP Server:** Official `mcp` Python SDK for Claude Desktop integration.

**Tooling:**
- `ruff` — linting and formatting
- `pytest` + `pytest-asyncio` — testing
- `uv` — package and project management

**Project layout:** `src/` layout (`src/dirt/`) with subpackages for `api/`, `models/`, `services/`, `mcp/`, and `templates/`.

**Explicitly excluded:**
- PostgreSQL — unnecessary complexity for single-box deployment
- Celery/task queues — asyncio tasks or cron suffice
- Alembic — simple migration functions in code are enough for a small schema
- Docker — direct install on the home box is simpler
- npm/JS build toolchain — HTMX + CDN-loaded Chart.js avoids this entirely

## Consequences

- The entire system runs as a single process with an embedded database, making deployment and debugging straightforward.
- SQLite limits concurrent write throughput, but sensor ingestion rates are far below this threshold.
- No JS build step means frontend interactivity is limited to what HTMX and Chart.js provide — sufficient for dashboards, but a richer UI would require revisiting this.
- SQLModel is younger than SQLAlchemy; some advanced query patterns may require dropping down to SQLAlchemy Core (which SQLModel wraps).
