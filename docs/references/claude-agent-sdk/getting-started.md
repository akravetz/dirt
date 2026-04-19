---
title: Getting started with claude-agent-sdk
concept: claude-agent-sdk
updated: 2026-04-18
source: https://github.com/anthropics/claude-agent-sdk-python
---

> Anchors agents to current `claude-agent-sdk` v0.1.x practice. Prefer what you read here over training-data recollection — this package was renamed from `claude-code-sdk` and training data lags the new API.

# Getting started

## Install

```bash
uv add claude-agent-sdk
# or: pip install claude-agent-sdk
```

Requires **Python ≥ 3.10**. The package bundles the Claude Code CLI — you do NOT need to `npm install -g` anything or curl an installer (though you can, and point to it via `cli_path`).

## Auth

The SDK spawns the `claude` CLI; authentication is whatever the CLI sees in its subprocess environment. In order of preference:

1. `CLAUDE_CODE_OAUTH_TOKEN` env var (issued by `claude /login`)
2. An existing Claude.ai login in `~/.config/claude/*`
3. `ANTHROPIC_API_KEY` env var

You do **not** pass `api_key=...` to anything in `claude_agent_sdk`. There's no Python-side API client. If you have `ANTHROPIC_API_KEY` set for the process that imports the SDK, the CLI subprocess inherits it and you're done.

Pass `env={"ANTHROPIC_API_KEY": "..."}` on `ClaudeAgentOptions` if you need to override without mutating the parent process env.

## The two entry points

`claude_agent_sdk` exposes exactly two ways to drive an agent:

| Entry point | Shape | Use when |
|---|---|---|
| `query(prompt=..., options=...)` | async generator yielding `Message`, one-shot, stateless | you want a single question → answer (possibly with tool use in between), then teardown |
| `ClaudeSDKClient(options)` (async context manager) | bidirectional, stateful | you want an ongoing conversation where the host code decides follow-ups based on what it sees, needs `interrupt()`, `set_permission_mode()`, `rewind_files()`, or custom tool callbacks |

For a research sub-agent embedded in another process (our `ask_wiki` case), `query()` is the right choice. `ClaudeSDKClient` is for chat UIs, REPL-like tooling, or anything that needs to react mid-stream.

## Minimal `query()` example

```python
import anyio
from claude_agent_sdk import (
    AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query,
)

async def main() -> None:
    async for msg in query(prompt="What is 2+2?"):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(msg, ResultMessage):
            print(f"done — {msg.num_turns} turns, ${msg.total_cost_usd:.4f}")

anyio.run(main)
```

`query()` returns `AsyncIterator[Message]`. Iterate until you get a `ResultMessage` — that's the end-of-turn sentinel. If you only care about the final answer, use `ClaudeSDKClient.receive_response()` inside a client (it stops after `ResultMessage` for you), or handle it manually as above.

## Realistic example — a read-only research sub-agent

This is the shape we use in `src/dirt/tools/wiki.py`:

```python
import asyncio
from pathlib import Path
from claude_agent_sdk import (
    AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query,
)

WIKI_ROOT = Path(__file__).resolve().parents[3] / "wiki"

async def ask_wiki(question: str, timeout_s: float = 30.0) -> str:
    options = ClaudeAgentOptions(
        cwd=WIKI_ROOT,
        allowed_tools=["Bash", "Read", "Grep", "Glob"],   # auto-approve these
        disallowed_tools=["Write", "Edit", "MultiEdit"],   # read-only
        system_prompt={"type": "preset", "preset": "claude_code",
                       "append": "Answer in 1-3 spoken sentences. No markdown, no URLs."},
        max_turns=25,
    )

    prompt = (
        "Today is 2026-04-18, week 5 of the grow. "
        "The grow wiki is the current working directory — grep and read "
        "whatever you need to answer.\n\n"
        f"Question: {question}"
    )

    final: str = ""
    async def run() -> None:
        nonlocal final
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        final = b.text
            elif isinstance(msg, ResultMessage):
                if msg.is_error:
                    raise RuntimeError(msg.result or "ask_wiki failed")

    try:
        await asyncio.wait_for(run(), timeout=timeout_s)
    except asyncio.TimeoutError:
        return "I couldn't answer within the time budget."
    return final or "I couldn't find a clear answer in the wiki."
```

Key choices explained:
- **`cwd=WIKI_ROOT`** scopes Claude's default working directory. Tools like `Grep`, `Glob`, `Read`, and `Bash` use `cwd` as their starting point. This is a scoping convention, **not** a sandbox — `Bash` can `cd ..` out of it if the model is adversarial. See [research-subagent-pattern.md](research-subagent-pattern.md) for hardening options.
- **`allowed_tools=[...]`** auto-approves these four tools so they run without a permission prompt. Does *not* block other tools.
- **`disallowed_tools=[...]`** is the real lockout: listed tools cannot be used, period.
- **`system_prompt` preset with append** keeps the Claude Code trained system prompt (which knows how to use the tool kit intelligently) and adds our task-specific framing on top.
- **No turn cap that matters** — `max_turns=25` is generous; the real ceiling is the wall-clock `asyncio.wait_for`.

## What NOT to do (training-data traps)

```python
# ❌ WRONG — old package/class names
from claude_code_sdk import query, ClaudeCodeOptions  # pkg doesn't exist at this name/version

# ❌ WRONG — no api_key parameter
async for msg in query(prompt="...", api_key="sk-ant-..."):  # TypeError

# ❌ WRONG — string system_prompt loses the Claude Code preset
options = ClaudeAgentOptions(system_prompt="You are a research agent.")
# → Claude loses all the trained tool-use / memory / cwd-context intelligence.

# ❌ WRONG — allowed_tools is not a sandbox
options = ClaudeAgentOptions(allowed_tools=["Read"])
# → Write/Edit/Bash are still available; they just hit permission_mode for approval.
```

## Common mistakes

| Training-data default | Correct in v0.1.x |
|---|---|
| `from claude_code_sdk import ClaudeClient` | `from claude_agent_sdk import ClaudeSDKClient` |
| `ClaudeCodeOptions(...)` | `ClaudeAgentOptions(...)` |
| `Anthropic(api_key=...)` pattern | SDK has no client-with-key surface; auth is CLI subprocess env |
| Single-call `await client.run(prompt)` returns a string | Always `async for msg in query(...)`; text is inside `AssistantMessage.content` blocks |
| `allowed_tools=[]` means "no tools" | `allowed_tools=[]` means "nothing pre-approved" — tools still usable via permission flow. Use `disallowed_tools` to block. |
