# Epic: Telegram Bot (Mobile Chat Interface)

Status: planning
Priority: high
Created: 2026-04-12

## Goal

Provide a mobile chat interface via Telegram so the user can interact with the grow agent from anywhere — ask questions, get status updates, receive proactive alerts, and view camera snapshots. The agent has full access to the wiki, sensor data, and PTZ camera.

## Why Telegram

- Lowest friction setup: create bot via BotFather, get token, write handler
- No business verification, no webhook SSL ceremony, no message template approval
- Rich messages: markdown, inline photos, buttons, formatted tables
- Proactive messaging works natively (push alerts without user asking)
- Great mobile app, likely already installed
- Free for personal use
- `python-telegram-bot` library is mature, async, fits into existing FastAPI app

Alternatives considered: WhatsApp (Meta Business account + Twilio required, message template approval for proactive sends), SMS (no rich messages, per-message cost), Signal (no official bot API, requires signal-cli Docker container).

## Architecture

See ADR 005 (`docs/adrs/005-agent-architecture.md`) for full agent architecture.

The Telegram bot is a **channel adapter** — it receives messages, invokes an ephemeral agent loop by shelling out to the Claude Code CLI (`claude -p`), and sends back the response. The agent loop assembles context from the wiki + sensor DB + recent session history on each request. Using the CLI (not the Agent SDK) lets us bill against the user's Max subscription instead of per-token API charges.

```
User sends Telegram message
    → channels/telegram.py receives it
    → loads last N turns from sessions/telegram/YYYY-MM-DD.jsonl
    → invokes agent/core.py query() with context + tools
    → agent loop runs (reads wiki, queries sensors, moves camera, etc.)
    → response sent back to Telegram
    → interaction appended to sessions/telegram/YYYY-MM-DD.jsonl
```

### Session Logging

All interactions are logged as append-only JSONL in `sessions/telegram/YYYY-MM-DD.jsonl`. The agent can read past sessions on demand but they are not loaded into context by default.

## Scope

### Channel Adapter (`channels/telegram.py`)
- Telegram bot running within the dirt FastAPI app
- Receives messages, invokes ephemeral agent loop
- Sends responses (text, photos, formatted messages)
- Appends interactions to session JSONL
- Restricted to a single authorized Telegram user ID

### Agent Capabilities (via tools)
- **Q&A** — "How's Plant C doing?" → reads wiki + recent sensors, responds
- **Status** — "Give me a status update" → summarizes overview + current readings
- **Camera** — "Show me Plant A" → moves PTZ to preset, captures photo, sends inline
- **Wiki search** — "What's our training plan?" → reads relevant wiki pages, responds
- **Sensor data** — "What's the VPD right now?" → queries latest readings
- **Wiki update** — files important interactions into wiki (filing-worthy workflow)

### Proactive Alerts
- `services/alerts.py` monitors sensor thresholds in a background task
- Simple threshold alerts sent directly to Telegram (no agent loop needed)
- Complex alerts invoke an ephemeral agent loop for nuanced analysis
- Daily summary message at lights-on with overnight sensor trends + action items

### Security
- Bot restricted to a single Telegram user ID (the owner)
- No public access, no group chat support needed
- Agent loop has budget limits per invocation (`max_budget_usd`)

## Acceptance Criteria

- User can send messages to bot and receive Claude-powered responses
- Bot can send inline photos from PTZ camera on request
- Proactive alerts fire when sensor thresholds are crossed
- Daily summary message sent automatically
- Bot restricted to authorized user only
- All interactions logged to `sessions/telegram/`
- Response latency < 10s for text queries, < 15s for camera captures

## References

### Telegram Bot API
- [python-telegram-bot (GitHub)](https://github.com/python-telegram-bot/python-telegram-bot) — mature async Python library for Telegram bots
- [Telegram BotFather](https://core.telegram.org/bots#botfather) — bot creation and token management

### Agent Architecture
- [ADR 005: Agent Architecture](../../adrs/005-agent-architecture.md) — ephemeral agent loops, session logging, channel adapter pattern
- [Claude Agent SDK: How the agent loop works](https://code.claude.com/docs/en/agent-sdk/agent-loop) — SDK loop lifecycle, tool execution, context management
- [OpenClaw Architecture (Substack)](https://ppaolo.substack.com/p/openclaw-system-architecture-overview) — reference architecture for gateway + ephemeral agent pattern
- [OpenClaw Reference Architecture (RobotPaper)](https://robotpaper.ai/reference-architecture-openclaw-early-feb-2026-edition-opus-4-6/) — directory layout, skill system, memory patterns

### Alternatives Evaluated
- [signal-cli-rest-api (GitHub)](https://github.com/bbernhard/signal-cli-rest-api) — Signal alternative (rejected: no official bot API, Docker container dependency)

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:telegram-bot"`
