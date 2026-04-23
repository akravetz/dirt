# Dirt

Home grow monitoring and tracking system. Webcam live feed, temperature/humidity sensors graphed over time, an MCP server for Claude Desktop, and an agent-maintained wiki that synthesizes daily photos + sensor readings + chat notes into a structured knowledge base.

<!--
LoC badges use codetabs.com. Shields.io's JSONPath doesn't support filter
predicates, so each badge indexes into the response array (sorted by file
count desc). Current order: [0]=Markdown, [1]=Python, [3]=TypeScript,
[4]=C++. If a language overtakes another by file count the indices shift —
re-check https://api.codetabs.com/v1/loc/?github=akravetz/dirt and adjust.
-->
[![Python](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.codetabs.com%2Fv1%2Floc%2F%3Fgithub%3Dakravetz%2Fdirt&query=%24%5B1%5D.linesOfCode&label=Python&color=3776ab&logo=python&logoColor=white&suffix=%20LoC&cacheSeconds=86400)](https://api.codetabs.com/v1/loc/?github=akravetz/dirt)
[![TypeScript](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.codetabs.com%2Fv1%2Floc%2F%3Fgithub%3Dakravetz%2Fdirt&query=%24%5B3%5D.linesOfCode&label=TypeScript&color=3178c6&logo=typescript&logoColor=white&suffix=%20LoC&cacheSeconds=86400)](https://api.codetabs.com/v1/loc/?github=akravetz/dirt)
[![C++](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.codetabs.com%2Fv1%2Floc%2F%3Fgithub%3Dakravetz%2Fdirt&query=%24%5B4%5D.linesOfCode&label=C%2B%2B&color=00599c&logo=cplusplus&logoColor=white&suffix=%20LoC&cacheSeconds=86400)](https://api.codetabs.com/v1/loc/?github=akravetz/dirt)
[![Markdown](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.codetabs.com%2Fv1%2Floc%2F%3Fgithub%3Dakravetz%2Fdirt&query=%24%5B0%5D.linesOfCode&label=Markdown&color=083fa1&logo=markdown&logoColor=white&suffix=%20LoC&cacheSeconds=86400)](https://api.codetabs.com/v1/loc/?github=akravetz/dirt)

## Layout

- `apps/hwd/` — hardware daemon (serial, humidifier loop, capture, ESP32 ingest) on :8000
- `apps/web/` — UI + JSON API + MCP mount on :8001
- `apps/shared/` — models, db, services shared across apps
- `apps/mcp/` — MCP server mounted inside `dirt-web`
- `apps/voice/` — Claudia wake-word → Pipecat voice channel
- `web-ui/` — Vite + React + TanStack Router frontend
- `firmware/` — ESP32 / Arduino nodes (fan controller, tent SHT45)
- `wiki/` — agent-maintained grow knowledge base

## Docs

- [`CLAUDE.md`](CLAUDE.md) — operating manual for agents (commands, invariants, observability)
- [`docs/README.md`](docs/README.md) — full documentation map, ADRs, epics, references
- [`wiki/CLAUDE.md`](wiki/CLAUDE.md) — wiki conventions and daily update workflow

## Project

- Board: https://github.com/users/akravetz/projects/1/views/1
- Issues: https://github.com/akravetz/dirt/issues
