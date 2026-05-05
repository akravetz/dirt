---
title: "Hosted control plane: Railway web UI plus outbound local gateway"
type: decision
sources: []
related:
  - wiki/overview.md
  - wiki/hardware/ptz-camera.md
  - docs/hosted-control-plane.md
  - docs/epics/hosted-website-control-plane/ExecPlan.md
created: 2026-05-05
updated: 2026-05-05
---

# Decision: Hosted control plane with outbound local gateway

**Date:** 2026-05-05
**Status:** Implemented and deployed.

## Context

Dirt was already local-first: the grow box host runs hardware loops, local Postgres, local web/API, MCP, voice, camera, humidifier, and ESP32 ingest. That is correct for plant safety, but it limits remote inspection to being on the local network.

The new requirement is a web-based control plane that can be opened away from home without making the public cloud the hardware authority.

## Decision

Run the hosted website as two Railway services:

- `control-plane-api` — long-running FastAPI cloud API.
- `web-ui` — hosted React app.

Cloud state lives in Railway Postgres. Synced photos live in the private Railway `dirt-assets` bucket and are read through authenticated signed URLs.

The local box runs a separate `dirt-gateway.service`. It is outbound-only: it reads local Postgres and local files, pushes the cloud-visible projection, uploads selected assets, polls command intent, validates scope locally, executes only V1 PTZ commands, and reports command results back to cloud.

## Boundaries

- `dirt-hwd` remains the local hardware authority for sensors, camera capture, humidifier, fan/tent node integration, and automation loops.
- `dirt-web` remains the local LAN UI/API/MCP service.
- `dirt-gateway` is separate from hardware automation and can be stopped without stopping local grow control.
- The hosted cloud API never imports hardware modules and never talks to cameras, fans, lights, humidifiers, ESP32 nodes, or local Postgres directly.
- V1 remote commands are PTZ-only and expire after 60 seconds. Fan, light, and humidifier remote control are intentionally not exposed.

## Why this works

The cloud UI is a projection, not a raw mirror of the local database. It stores latest/current state, rollups, recent private assets, heartbeat/freshness, and a command ledger. If cloud sync fails, local automation continues. If the gateway is stopped, the hosted UI becomes stale/offline but the grow box remains safe.

The hosted UI can still be useful remotely: it shows `homebox/main` and `homebox/breeding`, freshness, current metrics, recent photos, trend rollups, and PTZ command lifecycle. Commands are intent rows until the local gateway claims and validates them.

## Operational notes

Canonical operations live in [`docs/hosted-control-plane.md`](../../docs/hosted-control-plane.md).

- Deploy through `scripts/deploy-control-plane`; do not deploy cloud code ad hoc.
- Apply cloud schema with dedicated Atlas migrations; do not add app-start DDL.
- Monitor `https://api.sirius-forge.com/api/health` for gateway heartbeat age, backlog, command failures, and asset failures.
- Monitor local gateway logs at `var/logs/cloud_gateway/YYYY-MM-DD.jsonl` and with `journalctl --user -u dirt-gateway`.
- Roll back hosted controls by disabling command creation/claiming first; read-only sync can stay active.

## See also

- Repo operations: [`docs/hosted-control-plane.md`](../../docs/hosted-control-plane.md)
- Implementation plan: [`docs/epics/hosted-website-control-plane/ExecPlan.md`](../../docs/epics/hosted-website-control-plane/ExecPlan.md)
- PTZ scope: [`hardware/ptz-camera.md`](../hardware/ptz-camera.md)
