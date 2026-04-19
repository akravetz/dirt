---
title: ClaudeAgentOptions reference
concept: claude-agent-sdk
updated: 2026-04-18
source: src/claude_agent_sdk/types.py (ClaudeAgentOptions, ~line 1175)
---

> Anchors agents to current `claude-agent-sdk` v0.1.x. The option surface expanded significantly after the rename from `claude-code-sdk` — training data for the older `ClaudeCodeOptions` shape is wrong here.

# `ClaudeAgentOptions`

A frozen-ish dataclass you pass to `query()` or `ClaudeSDKClient(options=...)`. All fields have defaults; a bare `ClaudeAgentOptions()` works. Full definition: `raw/sdk-types.py` line ~1175.

This file covers the fields you'll actually touch in real code, grouped by purpose.

## Working directory + environment

| Field | Type | Default | Notes |
|---|---|---|---|
| `cwd` | `str \| Path \| None` | `None` (inherits process cwd) | Working directory for Claude's tools. Grep/Glob/Read/Bash use this as their start. Scoping convention, not a sandbox — `Bash` can `cd` elsewhere. |
| `add_dirs` | `list[str \| Path]` | `[]` | Extra directories added to Claude's filesystem roots beyond `cwd`. Use for sibling repos or data dirs the agent should see. |
| `env` | `dict[str, str]` | `{}` | Env vars injected into the CLI subprocess. Use this to set `ANTHROPIC_API_KEY` without mutating the parent process env. |
| `cli_path` | `str \| Path \| None` | `None` (bundled CLI) | Point at a specific `claude` binary (system install, pinned version, etc.). Bundled CLI is used otherwise. |
| `settings` | `str \| None` | `None` | Path to a `.claude/settings.json`-style file to load. |
| `setting_sources` | `list["user" \| "project" \| "local"] \| None` | `None` | Which filesystem settings to load. See gotcha below. |

**`setting_sources` gotcha (v0.1.60 fix):** `None` means "CLI defaults" (loads user + project). `[]` means "load nothing" (SDK-managed session only). Before v0.1.60 the SDK silently dropped `[]` and behaved like `None`. If you want a clean isolated session with no inherited settings, explicitly pass `setting_sources=[]`.

## Tools and permissions

| Field | Type | Default | Notes |
|---|---|---|---|
| `allowed_tools` | `list[str]` | `[]` | Auto-approval list. Listed tools run without prompting; **this is not an availability filter**. |
| `disallowed_tools` | `list[str]` | `[]` | Hard block. Listed tools cannot be invoked at all. |
| `permission_mode` | `"default" \| "acceptEdits" \| "plan" \| "bypassPermissions" \| "dontAsk" \| "auto" \| None` | `None` (→ `"default"`) | Fallback policy when a tool isn't on `allowed_tools` and no `can_use_tool` callback handles it. See [tools-and-permissions.md](tools-and-permissions.md). |
| `can_use_tool` | `CanUseTool \| None` | `None` | Async callback that adjudicates each tool call. Requires streaming-mode prompt (i.e., `AsyncIterable[dict]`, not `str`). Mutually exclusive with `permission_prompt_tool_name`. |
| `hooks` | `dict[HookEvent, list[HookMatcher]] \| None` | `None` | Hooks on `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, etc. Ran deterministically before/after tool calls. |
| `tools` | `list[str] \| ToolsPreset \| None` | `None` | Enable/override the tool set. `{"type":"preset","preset":"claude_code"}` loads the default Claude Code tool kit. Leave as `None` to inherit. |

## System prompt and model

| Field | Type | Default | Notes |
|---|---|---|---|
| `system_prompt` | `str \| SystemPromptPreset \| SystemPromptFile \| None` | `None` | See [system-prompts.md](system-prompts.md). TL;DR: prefer `{"type":"preset","preset":"claude_code","append":"..."}` over a bare string. |
| `model` | `str \| None` | `None` (CLI default) | Override the model. Accepts aliases (`"sonnet"`, `"opus"`, `"haiku"`) or full model IDs (`"claude-sonnet-4-5"`, `"claude-opus-4-7"`, etc.). |
| `fallback_model` | `str \| None` | `None` | Secondary model if the primary fails. |
| `thinking` | `ThinkingConfig \| None` | `None` | `{"type":"adaptive"}`, `{"type":"enabled","budget_tokens":N}`, or `{"type":"disabled"}`. |
| `effort` | `"low" \| "medium" \| "high" \| "max" \| None` | `None` | Thinking depth / token-efficiency dial. `max` is Opus-only. |
| `task_budget` | `TaskBudget \| None` | `None` | `{"total": N}` — model-visible token budget so it can pace itself. |

## Loop shape + budgets

| Field | Type | Default | Notes |
|---|---|---|---|
| `max_turns` | `int \| None` | `None` (unbounded) | Turn cap. Not a wall-clock limit — wrap `async for` in `asyncio.wait_for(...)` for that. |
| `max_budget_usd` | `float \| None` | `None` | Cost cap in USD. Session ends when exceeded. |
| `continue_conversation` | `bool` | `False` | Resume the previous local session. |
| `resume` | `str \| None` | `None` | Session ID to resume. |
| `session_id` | `str \| None` | `None` | Explicit session ID for this run. |
| `fork_session` | `bool` | `False` | When resuming, fork to a new session ID instead of continuing the old one. |

## Agents, plugins, skills, MCP

| Field | Type | Default | Notes |
|---|---|---|---|
| `agents` | `dict[str, AgentDefinition] \| None` | `None` | Inline sub-agent definitions (description, prompt, tools, model, effort, permissionMode). |
| `skills` | `list[str] \| "all" \| None` | `None` | Which skills to load. `None` = CLI defaults (still loads bundled skills). `"all"` = everything discovered. `[]` = none. Since v0.1.62, this option alone wires `setting_sources` and `allowed_tools` for skills — don't do it manually. |
| `plugins` | `list[SdkPluginConfig]` | `[]` | Local plugin configs. |
| `mcp_servers` | `dict[str, McpServerConfig] \| str \| Path` | `{}` | External MCP servers (stdio/SSE/HTTP), in-process SDK MCP servers (from `create_sdk_mcp_server(...)`), or a path to a config file. |

## Output shape

| Field | Type | Default | Notes |
|---|---|---|---|
| `include_partial_messages` | `bool` | `False` | Emit `StreamEvent`s for partial assistant output. |
| `output_format` | `dict \| None` | `None` | Structured output config, Messages-API-style (`{"type":"json_schema","schema":{...}}`). |
| `enable_file_checkpointing` | `bool` | `False` | Track file changes so `ClaudeSDKClient.rewind_files(uuid)` can undo them. |

## Debugging

| Field | Type | Default | Notes |
|---|---|---|---|
| `stderr` | `Callable[[str], None] \| None` | `None` | Callback for CLI stderr. Use for piping CLI logs into your app's logger. |
| `debug_stderr` | file-like | `sys.stderr` | Deprecated. Use `stderr` callback instead. |
| `extra_args` | `dict[str, str \| None]` | `{}` | Pass arbitrary CLI flags. `{"replay-user-messages": None}` is a common one (enables `UserMessage.uuid` for checkpointing). |
| `max_buffer_size` | `int \| None` | `None` | CLI stdout buffer cap in bytes. |
| `user` | `str \| None` | `None` | Distinguishes users in session metadata. |

## Minimal realistic config for a read-only research sub-agent

```python
ClaudeAgentOptions(
    cwd=Path("/path/to/data"),
    allowed_tools=["Bash", "Read", "Grep", "Glob"],
    disallowed_tools=["Write", "Edit", "MultiEdit"],
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "Answer in 1-3 spoken sentences. No markdown, no URLs.",
    },
    max_turns=25,           # generous; real ceiling is wall-clock
    max_budget_usd=0.25,    # cost cap as a safety net
    setting_sources=[],     # isolated — ignore host .claude/ settings
)
```

## Common mistakes

| Training-data default | Correct in v0.1.x |
|---|---|
| `ClaudeCodeOptions(api_key=...)` | `ClaudeAgentOptions(...)`; no api_key field |
| `options.cwd = "..."` after construction | Options is a dataclass; set at construction or use `dataclasses.replace(opts, cwd=...)` |
| `allowed_tools=["Read"]` to prevent writes | Use `disallowed_tools=["Write","Edit","MultiEdit"]` |
| `max_turns=5` to time-limit | Use `asyncio.wait_for(..., timeout=30)`; `max_turns` is a turn cap, not seconds |
| Passing `api_key=...` anywhere | Auth is via CLI subprocess env (`CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`) |
