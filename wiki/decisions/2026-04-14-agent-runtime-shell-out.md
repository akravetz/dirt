---
title: "Agent Runtime: Shell-Out to Claude Code CLI (Uses Max Subscription)"
type: decision
sources: []
related: [wiki/decisions/2026-04-12-agent-architecture.md, wiki/decisions/2026-04-12-telegram-mobile-interface.md]
created: 2026-04-14
updated: 2026-04-14
---

# Decision: Agent Runtime — Shell-Out to Claude Code CLI

**Date:** 2026-04-14
**Status:** Accepted

## Context

ADR 005 originally proposed the Claude Agent SDK for the agent runtime. On 2026-04-14 we discovered that the Agent SDK explicitly **prohibits** using Pro/Max subscription credentials — it requires a separate `ANTHROPIC_API_KEY` with pay-per-token billing. The user has a Max subscription that would go unused if we went the SDK route.

## Decision

**Shell out to the Claude Code CLI (`claude -p`) from our Python code.** Each incoming message triggers a subprocess call:

```python
result = await asyncio.create_subprocess_exec(
    "claude", "-p", user_message,
    "--output-format", "json",
    "--add-dir", "/home/akcom/code/dirt",
    cwd="/home/akcom/code/dirt",
    stdout=asyncio.subprocess.PIPE,
)
```

The CLI uses the user's Max subscription (already authenticated locally). It provides the same agent loop as the SDK — full tool access (Read, Write, Edit, Bash, Grep, Glob), CLAUDE.md awareness, skills, and settings.

## Why This Over the Agent SDK

| | Claude Code CLI (chosen) | Claude Agent SDK (rejected) |
|---|---|---|
| Billing | Uses Max subscription | Per-token API billing (~$0.30/interaction on Opus) |
| Setup | Zero (already authenticated) | Requires ANTHROPIC_API_KEY |
| Tools | Full Claude Code toolset | Same, via SDK options |
| CLAUDE.md | Automatic | Automatic with `setting_sources=["project"]` |
| Streaming | JSON output mode | Native async iterator |
| Hooks | Not exposed via CLI | Full hook API |
| Rate limits | Max plan rate limits | Per-minute API limits |

## Alternatives Considered

- **Agent SDK with API key** — costs ~$90-$450/month for reasonable use (Sonnet to Opus); Max subscription would sit unused
- **Haiku 4.5 via API** — cheapest option at ~$15/month, but limits agent capability
- **Hybrid** — CLI for heavy workflows, API for simple queries — unnecessary complexity for a personal project

## Migration Path

If Anthropic restricts programmatic use of Claude Code CLI in the future, we swap the subprocess call for an SDK `query()` call. Same architectural shape, different process model. Our application code is thin (~30 lines for the wrapper), so migration cost is minimal.

## Consequences

- **No API costs** for agent interactions — subscription covers everything
- Subject to Max plan rate limits (request-based, not token-based)
- Application code is slightly "clunkier" — subprocess + JSON parse vs native async iterator
- SDK-specific features (fine-grained hooks, custom tool handlers) not available — acceptable for this use case
- The CLI's setup sources (CLAUDE.md, skills, permissions) are honored automatically

## See Also

- [ADR 005: Agent Architecture](../../docs/adrs/005-agent-architecture.md) — overall agent design (ephemeral loops, channel adapters, wiki as memory)
- Agent SDK billing policy: [GitHub issue #559](https://github.com/anthropics/claude-agent-sdk-python/issues/559) — confirms subscription credentials are not supported
