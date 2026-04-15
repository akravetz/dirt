# ADR 005: Agent Architecture

## Status

Accepted

## Context

The dirt project is expanding from a monitoring dashboard into an autonomous grow assistant. The agent needs to:

- Respond to user messages from Telegram and voice (Jabra speakerphone)
- Autonomously monitor sensors and send proactive alerts
- Control a PTZ camera (OBSBOT Tiny 2 Lite) to inspect plants
- Read and update the grow wiki
- Generate daily progress reports
- All hardware is local (USB devices on a single monitoring host)

Three options were evaluated for the agent runtime:

1. **Claude Managed Agents** — Anthropic-hosted harness with sandboxed containers, durable sessions, automatic compaction and recovery.
2. **Claude Agent SDK** — Embed Claude Code's agent loop in our own process. Ephemeral per-request loops with tool dispatch, running locally.
3. **Raw Messages API** — Build the agent loop from scratch. Full control, most code to write.

We also evaluated the OpenClaw framework's architecture as a reference pattern.

## Decision

**Claude Agent SDK with ephemeral agent loops, running inside the existing FastAPI process.**

### Why not Managed Agents

All hardware (camera, sensors, audio, serial ports) is local USB. A cloud-hosted agent would need every action to be an API callback to the home server — more complexity, not less. Managed Agents is designed for long-running code tasks in sandboxed containers. Our interactions are short (2-15 tool-call turns) and need direct hardware access.

### Why Agent SDK over raw Messages API

The Agent SDK provides the agent loop, tool dispatch, context management, and compaction for free. Building this from the Messages API would mean reimplementing what the SDK already does. The SDK also supports custom tools, permission control, and budget limits out of the box.

### Runtime Update (2026-04-14): Shell-Out to Claude Code CLI

The Agent SDK explicitly **prohibits** using Pro/Max subscription credentials — it requires a separate `ANTHROPIC_API_KEY`. The user has a Max subscription; to use it, we shell out to the Claude Code CLI (`claude -p`) from Python rather than using the SDK directly. See `wiki/decisions/2026-04-14-agent-runtime-shell-out.md` for full rationale.

The architecture is unchanged — it's still ephemeral agent loops invoked per-request, with the wiki as memory. Only the invocation mechanism differs: `subprocess.exec("claude", "-p", message)` instead of `await query(prompt=message)`. Migration back to the SDK is ~30 lines if needed.

### Why ephemeral loops, not a persistent agent

Following the OpenClaw pattern: the **gateway process is persistent** (our FastAPI app), but **agent loops are ephemeral per-request**. When a Telegram message arrives, a fresh `query()` call assembles context from the wiki + sensor DB, runs the tool loop, and exits.

This works because the wiki is the real memory, not conversation history. If an agent loop crashes, the next request reads the wiki and is immediately current. No session recovery needed.

Conversational continuity (so "what about Plant D?" flows naturally after discussing Plant C) is handled by injecting the last N turns from the session log into each request — lightweight history, not a persistent agent.

### Session logs

Interaction transcripts are stored as append-only JSONL files in `sessions/{channel}/YYYY-MM-DD.jsonl`. Written by the harness, readable by the agent on demand. NOT loaded into context by default — the agent reaches for them when relevant (e.g., "what did we discuss yesterday?").

## Architecture

```
User (Telegram / Voice)
    ↓
FastAPI app (persistent gateway) — runs as dirt-harness
    ↓
channels/telegram.py  or  channels/voice.py
    ↓
agent/core.py — ephemeral query() call, tools run as dirt-agent
    ├── context.py assembles: wiki overview + recent sensors + last N turns
    ├── tools: Bash, Read, Write, Edit, Grep, Glob + custom hardware tools
    └── Agent SDK handles: tool dispatch loop, compaction, budget
    ↓
Response sent back through originating channel
Session log appended by harness (as dirt-harness) to sessions/{channel}/YYYY-MM-DD.jsonl
```

### Agent tools

The agent gets full filesystem tools — `Bash`, `Read`, `Write`, `Edit`, `Grep`, `Glob` — the same tools agents are most effective with. It can create wiki pages, reorganize files, grep across session logs for context, and run shell commands. Access control is enforced at the OS level via Linux user groups (see below), not by restricting the tool set.

Custom tools are added for hardware interaction: `move_camera`, `capture_photo`, `query_sensors`, `send_notification`.

### Access control: Linux user groups

The agent needs broad filesystem access (read/write wiki, create files, grep across everything) but must not be able to modify session transcripts (its own audit trail). This is enforced at the OS level with Linux users and groups:

```
Users:
  dirt-harness  — runs the FastAPI gateway process, writes session logs
  dirt-agent    — runs agent tool subprocesses (Bash, file ops, etc.)

Group:
  dirt          — shared group, both users are members

Directory permissions:
  sessions/     owner=dirt-harness  group=dirt  mode=755  (agent: read-only, harness: read-write)
  wiki/         owner=dirt-harness  group=dirt  mode=775  (both: read-write)
  raw/          owner=dirt-harness  group=dirt  mode=775  (both: read-write)
  outputs/      owner=dirt-harness  group=dirt  mode=775  (both: read-write)

Hardware:
  /dev/ttyUSB*  group=dirt (udev rule) — both users access serial devices
  Camera, audio — accessible via dirt group
```

**Why OS-level enforcement:** The agent has full `Bash` and filesystem tools — it needs them to be effective (grep, create files, reorganize wiki). Application-level restrictions (custom tools only, no Bash) would cripple the agent. Linux permissions enforce the one boundary that matters (session log integrity) without restricting the agent's capabilities elsewhere.

**Setup (one-time):**
```bash
sudo groupadd dirt
sudo useradd -r -G dirt dirt-harness
sudo useradd -r -G dirt dirt-agent
sudo chown -R dirt-harness:dirt sessions/
sudo chmod 755 sessions/ sessions/telegram/ sessions/voice/
sudo chown -R dirt-harness:dirt wiki/ raw/ outputs/
sudo chmod 775 wiki/ raw/ outputs/
# udev rule for USB devices:
# SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", GROUP="dirt", MODE="0660"
```

**Implementation note:** The Agent SDK `query()` call needs to run tool subprocesses as `dirt-agent`. How this works depends on the SDK's process model — either the entire agent loop runs as `dirt-agent` (harness does `setuid` before invoking `query()`), or individual tool processes are spawned as `dirt-agent`. This is an implementation detail to validate when building the agent integration.

### Autonomous monitoring

A FastAPI background task periodically checks sensor thresholds. When triggered, it either:
- Sends a direct Telegram notification (simple threshold alert), or
- Invokes an ephemeral agent loop for nuanced analysis ("VPD trending up for 3 hours, recommend action")

### Daily reports

A scheduled task (cron or FastAPI scheduler) invokes an ephemeral agent loop with a synthetic prompt: "Generate today's daily report." The agent captures PTZ photos at presets, reads sensors, writes the wiki daily entry, and updates plant/environment pages.

## Data Hierarchy

| Layer | Purpose | Who writes | Who reads | Permissions |
|-------|---------|-----------|-----------|-------------|
| `sessions/` | Raw interaction transcripts | Harness (append-only) | Agent (on demand) | `755` — agent read-only |
| `raw/` | Source material (photos, sensor logs) | User / hardware | Agent (during ingestion) | `775` — both read-write |
| `wiki/` | Curated knowledge | Agent | Agent + user | `775` — both read-write |
| `outputs/` | Generated reports | Agent | User | `775` — both read-write |

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Managed Agents | Hosted harness, durable sessions, recovery | Cloud-hosted, can't access local hardware directly |
| Raw Messages API | Full control, no SDK dependency | Reimplements agent loop, tool dispatch, compaction |
| OpenClaw framework | Proven patterns, multi-channel | Node.js (project is Python), heavyweight for single-user |
| Long-lived persistent agent | No context assembly per request | Context window fills up, needs compaction/recovery, crashes lose state |

### Access control alternatives considered

| Option | Pros | Cons |
|--------|------|------|
| **Linux user groups** (chosen) | Real OS enforcement, agent keeps full Bash/filesystem tools | One-time setup, need to validate SDK process model |
| Tool-level enforcement (no Bash/Write) | Simple, no OS config | Cripples the agent — can't grep, create files, reorganize wiki |
| Filesystem permissions only (same user) | Zero setup | Doesn't actually enforce anything — same user, same permissions |
| `chattr +a` (append-only flag) | Kernel-level append-only | Requires root, prevents log rotation, still allows appending garbage |

## Consequences

- The FastAPI app becomes the "gateway" — it already runs for the web UI, now also handles Telegram, voice, and scheduled agent tasks
- All agent interactions are stateless at the API level — state lives in wiki + sensor DB + session logs
- Adding a new channel (e.g., Signal in the future) means writing one adapter file, not changing the agent
- The agent can be tested by invoking `query()` directly with mock tools — no infrastructure needed
- Session log integrity is enforced by OS permissions — the agent cannot tamper with its own audit trail
- Agent retains full filesystem capabilities (Bash, Grep, Read, Write, Edit, Glob) for maximum effectiveness
