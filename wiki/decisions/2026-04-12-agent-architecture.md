---
title: "Agent Architecture: Ephemeral Loops via Claude Agent SDK"
type: decision
sources: []
related: [wiki/decisions/2026-04-12-telegram-mobile-interface.md, wiki/decisions/2026-04-12-distributed-sensor-architecture.md]
created: 2026-04-12
updated: 2026-04-12
---

# Decision: Agent Architecture — Ephemeral Loops via Claude Agent SDK

**Date:** 2026-04-12
**Status:** Accepted

## Context

The dirt project is expanding from a monitoring dashboard into an autonomous grow assistant with multiple input channels (Telegram, voice), hardware control (PTZ camera, sensors), and proactive capabilities (alerts, daily reports). Need to decide how the agent runtime works.

## Decision

**Ephemeral agent loops using the Claude Agent SDK, running inside the existing FastAPI process.** Following the OpenClaw pattern: persistent gateway (FastAPI), ephemeral per-request agent loops.

Each incoming message triggers a fresh `query()` call. Context is assembled from the wiki, sensor DB, and recent session history. The agent loop runs tools, responds, and exits. Session transcripts are appended to JSONL files in `sessions/`.

## Why This Works

The wiki is the real memory, not conversation history. If an agent loop crashes, the next request reads the wiki and is immediately current. No session recovery, no durable event logs, no container orchestration needed.

## Alternatives Rejected

- **Managed Agents** — cloud-hosted, can't access local USB hardware directly
- **Long-lived persistent agent** — context window fills up, needs compaction/recovery infrastructure, crashes lose state
- **Raw Messages API** — would reimplement what the Agent SDK provides for free

## See Also

Full ADR: `docs/adrs/005-agent-architecture.md`
