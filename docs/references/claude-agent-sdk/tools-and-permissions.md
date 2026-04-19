---
title: Tools and permissions
concept: claude-agent-sdk
updated: 2026-04-18
source: https://platform.claude.com/docs/en/agent-sdk/permissions, src/claude_agent_sdk/types.py (PermissionMode, CanUseTool)
---

> Anchors agents to current `claude-agent-sdk` v0.1.x. The permission model has three interacting knobs (`allowed_tools`, `permission_mode`, `can_use_tool`) and most training-data examples flatten them incorrectly.

# Tools and permissions

## The built-in tool kit

The Claude Code preset ships these tools (exact case-sensitive names — the allowlist / denylist / callback sees these):

| Tool | Effect |
|---|---|
| `Bash` | Run a shell command. Input: `{command, timeout?, description?}`. |
| `Read` | Read a file. Input: `{file_path, offset?, limit?}`. |
| `Write` | Create / overwrite a file. |
| `Edit` | String-replace in a file. |
| `MultiEdit` | Multiple edits in one call. |
| `Grep` | Ripgrep. Input: `{pattern, path?, glob?, -i?, -n?, output_mode?, ...}`. |
| `Glob` | File pattern match. Input: `{pattern, path?}`. |
| `WebFetch` | Fetch a URL. |
| `WebSearch` | Search the web. |
| `Task` | Spawn a sub-agent. |
| `Skill` | Invoke a configured skill by name. |
| `TodoWrite` | Update the agent's task list. |
| `NotebookEdit` | Edit a Jupyter notebook. |

There are also MCP tools exposed as `mcp__<server>__<tool>` (e.g., `mcp__my-tools__greet`) and the permission-prompt tool (usually `stdio` when `can_use_tool` is wired). For an authoritative list consult `https://code.claude.com/docs/en/settings#tools-available-to-claude`.

## Three interacting knobs

Tool access is governed by three fields on `ClaudeAgentOptions`, resolved in this order:

1. **`disallowed_tools`** — hard block. If the tool is on this list, it cannot be invoked.
2. **`allowed_tools`** — auto-approval list. If the tool is on this list and not on `disallowed_tools`, it runs without asking.
3. Otherwise, the call falls through to **`can_use_tool`** (if set) or **`permission_mode`**.

`allowed_tools` is **not** an availability filter. Leaving `Write` off `allowed_tools` does not prevent Claude from calling `Write`; it just means the call hits the permission-mode fallback. This is the single most common source of bugs in SDK code — if you want to *block* writes, use `disallowed_tools=["Write","Edit","MultiEdit"]` (or a denying `can_use_tool` callback).

## `permission_mode`

Fallback policy for tools not on `allowed_tools` and not handled by `can_use_tool`:

| Mode | Behavior |
|---|---|
| `"default"` | Ask before running dangerous tools (Write/Edit/Bash). Read-only tools auto-approve. |
| `"acceptEdits"` | Auto-accept file edits (Write, Edit, MultiEdit). Still prompts for Bash. |
| `"plan"` | No tool execution at all — Claude plans but doesn't act. Use for dry-runs. |
| `"bypassPermissions"` | Allow everything. Dangerous; prefer this only in trusted, isolated sandboxes. |
| `"dontAsk"` | Like `bypassPermissions` but phrased as a user preference. Same effect. |
| `"auto"` | CLI picks mode based on heuristics (v2.1.90+). |

If `permission_mode` is `None`, the CLI applies its own default.

## `can_use_tool` — the callback

For fine-grained control (per-path policies, input rewriting, logging), pass a callback:

```python
from claude_agent_sdk import (
    ClaudeAgentOptions, ClaudeSDKClient, PermissionResultAllow,
    PermissionResultDeny, ToolPermissionContext,
)

async def gate(
    tool_name: str,
    input_data: dict,
    context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    if tool_name in {"Read", "Grep", "Glob"}:
        return PermissionResultAllow()

    if tool_name == "Bash":
        cmd = input_data.get("command", "")
        if any(bad in cmd for bad in ("rm -rf", "sudo", "curl | sh")):
            return PermissionResultDeny(message=f"blocked: {cmd!r}")
        return PermissionResultAllow()

    if tool_name in {"Write", "Edit", "MultiEdit"}:
        # Example: redirect writes to a safe dir
        new_input = {**input_data, "file_path": "/tmp/agent-out/" + input_data["file_path"].split("/")[-1]}
        return PermissionResultAllow(updated_input=new_input)

    return PermissionResultDeny(message=f"no policy for {tool_name}")

options = ClaudeAgentOptions(
    can_use_tool=gate,
    permission_mode="default",  # required — callback runs under default mode
)

async with ClaudeSDKClient(options) as client:
    await client.query("do the thing")
    async for msg in client.receive_response():
        ...
```

**Requirements and quirks:**

- `can_use_tool` **requires streaming-mode prompt** — you can't pass a `str` prompt alongside it. Use `ClaudeSDKClient` (which is always streaming) or pass an `AsyncIterable[dict]` prompt to `query()`. If you try to use a string prompt with `can_use_tool`, the SDK raises `ValueError("can_use_tool callback requires streaming mode...")`.
- `can_use_tool` is mutually exclusive with `permission_prompt_tool_name`.
- Return `PermissionResultAllow(updated_input=...)` to rewrite the tool input before execution. Useful for redirecting paths, sanitizing commands, adding default flags.
- `PermissionResultDeny(message="...")` — the `message` is surfaced back to Claude so it can adapt its plan.

## Hooks

Hooks are **before/after** callbacks around tool calls (and other lifecycle events), distinct from permission gating. Use them for deterministic, non-decisional processing — logging, input sanitization that always applies, metric emission.

```python
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

async def log_bash(input_data, tool_use_id, context):
    print(f"[bash] {input_data['tool_input'].get('command')}")
    return {}  # empty = continue, no override

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [HookMatcher(matcher="Bash", hooks=[log_bash])],
    }
)
```

Hook events include: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `UserPromptSubmit`, `Stop`, `SubagentStart`, `SubagentStop`, `PreCompact`, `Notification`, `PermissionRequest`.

A hook can deny a tool call by returning `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}` — this is a shortcut for gating without a full `can_use_tool` callback.

## Recipe: read-only research agent

```python
ClaudeAgentOptions(
    cwd=Path("/path/to/data"),
    allowed_tools=["Bash", "Read", "Grep", "Glob"],
    disallowed_tools=["Write", "Edit", "MultiEdit", "NotebookEdit"],
    permission_mode="default",
)
```

This gives Claude the four read/navigation tools with zero prompting, hard-blocks all writes, and relies on `permission_mode` to gate anything else (WebFetch, Task, etc.) as a safety net.

If you need `Bash` but want to block mutating commands, add a `can_use_tool` callback that inspects `input_data["command"]` and denies `rm`, `>`, `dd`, `sudo`, etc. The Bash tool itself can't distinguish read vs write — only your gate can.

## Common mistakes

| Training-data default | Correct in v0.1.x |
|---|---|
| `allowed_tools=["Read"]` blocks Write | It doesn't. Add `disallowed_tools=["Write"]` or a denying `can_use_tool`. |
| `tools=["Read","Grep"]` is the allowlist | `tools` is a preset selector (`ToolsPreset`), not a list of tool names. Use `allowed_tools`. |
| `permission_mode="bypassPermissions"` as a default | Only in trusted sandboxes. For most code, `"default"` + `allowed_tools` is the right combination. |
| `can_use_tool` with a `str` prompt | `ValueError`. Use streaming-mode prompt or `ClaudeSDKClient`. |
| Returning `True`/`False` from `can_use_tool` | Return `PermissionResultAllow()` / `PermissionResultDeny(message=...)`. |
| Hook return value is ignored | Non-empty `{"hookSpecificOutput": {...}}` controls permission and input. |
