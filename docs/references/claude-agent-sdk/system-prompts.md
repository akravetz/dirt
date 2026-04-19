---
title: system_prompt — preset, string, or file
concept: claude-agent-sdk
updated: 2026-04-18
source: src/claude_agent_sdk/types.py (SystemPromptPreset, SystemPromptFile)
---

> Anchors agents to current `claude-agent-sdk` v0.1.x. Overriding `system_prompt` with a bare string silently disables the Claude Code preset — the single most impactful mistake in SDK code.

# `system_prompt`

`ClaudeAgentOptions.system_prompt` accepts three shapes. They are **not** equivalent.

```python
# 1. None — no system prompt injected by the SDK beyond the CLI default
ClaudeAgentOptions(system_prompt=None)

# 2. str — replace the whole system prompt with your string
ClaudeAgentOptions(system_prompt="You are a research assistant.")

# 3. Preset — use the Claude Code system prompt, optionally appending
ClaudeAgentOptions(system_prompt={
    "type": "preset",
    "preset": "claude_code",
    "append": "Answer in 1-3 spoken sentences. No markdown.",
})

# 4. File — load from disk
ClaudeAgentOptions(system_prompt={"type": "file", "path": "/etc/agents/research.md"})
```

## Why the preset matters

The `"claude_code"` preset is the *actual system prompt Claude Code uses* — the one Anthropic has iterated on, A/B tested, and tuned for Claude's behavior with the built-in tool kit. It includes:

- How to use `Read`, `Grep`, `Glob`, `Bash` efficiently (parallel search, bounded outputs, when to `head` vs full-read)
- When to prefer `Task` to delegate, vs handling inline
- Working-directory awareness, git status context, memory loading
- Task-list discipline (`TodoWrite` behavior)
- Permissions etiquette — how Claude requests approvals, reacts to denials

Replacing it with a bare string drops all of this. Claude will still have access to the tools, but its tool-selection instincts degrade noticeably: more speculative reads, fewer parallel calls, worse decisions about when to search vs just guess.

**Rule of thumb:** override the preset only when you have a reason to deny Claude the Claude Code system prompt. For almost every use case you want:

```python
system_prompt={
    "type": "preset",
    "preset": "claude_code",
    "append": "<your task-specific addition>",
}
```

`append` is concatenated after the preset, so Claude sees: `[Claude Code prompt] + [your append]`.

## When a bare string is right

- You're building a fundamentally different agent (not a Claude Code-style file/research agent) and need total control.
- You've measured the preset biasing your agent in unwanted ways (rare).
- You want zero tool-kit context because you've replaced all tools via MCP and don't want the preset's built-in tool names referenced.

In every other case, prefer preset + append.

## `exclude_dynamic_sections` for cross-user caching

The preset includes per-user dynamic sections (cwd, git status, auto-memory contents). These invalidate the prompt cache across users. v0.1.57+ supports:

```python
system_prompt={
    "type": "preset",
    "preset": "claude_code",
    "append": "...",
    "exclude_dynamic_sections": True,
}
```

With this, the SDK strips cwd/git/memory out of the system prompt and re-injects them into the first user message instead — keeping the system-prompt prefix byte-identical across users so prompt caching can hit. Requires a CLI version that supports it; older CLIs silently ignore the flag.

Don't reach for this unless you're running many similar sub-agent invocations back-to-back and hitting cache misses. For a single sub-agent call per user question, it's noise.

## Per-turn context goes in the user message

For per-invocation context (the current date, a research question, a stage marker), **don't interpolate into `system_prompt`** — that invalidates the prompt cache. Put it in the user message (the `prompt` argument):

```python
# ❌ WRONG — date in system prompt invalidates cache every day
system_prompt={"type": "preset", "preset": "claude_code",
               "append": f"Today is {date.today()}."}

# ✅ RIGHT — stable preset + dynamic user message
options = ClaudeAgentOptions(
    system_prompt={"type": "preset", "preset": "claude_code",
                   "append": "Answer in 1-3 spoken sentences."},
)
prompt = f"Today is {date.today()}. Research question: {question}"
```

This pattern keeps the system prompt frozen (cacheable) while threading fresh context through the user message.

## File-backed system prompts

`SystemPromptFile` reads the prompt from disk:

```python
system_prompt={"type": "file", "path": "/etc/agents/research.md"}
```

Useful when prompts are version-controlled separately from code. Note that this **replaces** the preset entirely — there's no "preset + file append" mode. If you want both, read the file and set `append=file.read_text()` inside a `SystemPromptPreset` dict.

## Common mistakes

| Training-data default | Correct in v0.1.x |
|---|---|
| `system_prompt="You are ..."` for a Claude Code-style agent | `system_prompt={"type":"preset","preset":"claude_code","append":"..."}` to keep tool intelligence |
| Interpolating timestamps / session IDs into `system_prompt` | Put volatile context in the user message; keep `system_prompt` frozen for cache hits |
| `system_prompt` can both reference a preset and load a file | No — pick one shape. Preset + append, string, or file. |
| `system_prompt` = prepended to user message | It's a real system prompt in the Messages API sense, not a user-turn prefix |
