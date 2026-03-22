# Epic: MCP Server

Status: planning
Priority: medium
Created: 2026-03-22

## Goal

MCP server for Claude Desktop integration. Exposes grow data — webcam snapshots, sensor readings, history — as MCP tools that Claude can call via Custom Connectors.

## Architecture Decisions

- **Transport**: Streamable HTTP (MCP spec 2025-03-26)
- **Deployment**: Mounted into the existing FastAPI app (same process, shared DB engine)
- **Endpoint**: `/mcp` on the existing web server
- **Auth**: Bearer token stored in `.env` (`MCP_BEARER_TOKEN`), checked in middleware
- **Connection**: Added as a Custom Connector in Claude.ai settings (Settings > Connectors > paste URL)
- **Image handling**: Snapshots returned as base64-encoded JPEG inline in MCP response

## Scope

### Tools

- **get_latest_snapshot** — Returns the most recent webcam snapshot as a base64 JPEG image
- **get_current_readings** — Returns latest sensor values: temperature, humidity, CO2, soil moisture, reservoir level
- **get_sensor_history** — Returns sensor readings for a time range (temperature, humidity, CO2, soil moisture, reservoir level)

### Infrastructure

- Add `mcp` SDK dependency
- Mount `FastMCP` as sub-application in FastAPI app
- Bearer token auth middleware for the `/mcp` endpoint
- Extend `SensorReading` model if needed for CO2, soil moisture, reservoir level

## Out of Scope

- Grow status summary tool (may revisit later)
- OAuth 2.1 (bearer token is sufficient for single-user)
- Separate process / standalone MCP server

## Acceptance Criteria

- MCP server is mounted at `/mcp` and starts with the FastAPI app
- Claude can connect via Custom Connector and call all three tools
- Tools return structured data that Claude can reason about
- Snapshot tool returns base64 JPEG that Claude can display
- Unauthenticated requests to `/mcp` are rejected
- MCP module does not import from `api` package (invariant boundary)

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:mcp-server"`
