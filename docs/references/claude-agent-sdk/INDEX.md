---
title: Claude Agent SDK (Python) Reference Pack
concept: claude-agent-sdk
mode: framework
version: 0.1.63
updated: 2026-04-18
---

# Claude Agent SDK (Python)

`claude-agent-sdk` is Anthropic's Python package for embedding the Claude Code agent loop in your own app. It spawns the bundled `claude` CLI as a subprocess and drives it over stdio JSON — you don't call the Anthropic Messages API directly. You get Claude's trained tool kit (`Bash`, `Read`, `Write`, `Edit`, `Grep`, `Glob`, `WebFetch`, `WebSearch`, `Task`, `Skill`, etc.) for free, plus a permission model, hooks, sub-agent machinery, and the whole "Claude Code system prompt" behind one preset.

This pack targets **v0.1.63** with CLI **2.1.114**. Anything referencing `claude-code-sdk`, `ClaudeCodeOptions`, or `ClaudeClient` is pre-0.1.0 and wrong for this version.

## When to consult this pack

Read this INDEX first (and the relevant topic files below) before writing any code that:

- imports from `claude_agent_sdk`,
- calls `query(...)` or instantiates `ClaudeSDKClient`,
- builds a local Claude-Code-style sub-agent that needs filesystem + bash access,
- configures `ClaudeAgentOptions` (system_prompt, allowed_tools, permission_mode, cwd, hooks, can_use_tool),
- or threads messages/content blocks out of an `AsyncIterator[Message]`.

Prefer what's written here over recollection — this SDK has been through a rename and several API changes, and training data for it is thin and often wrong.

## Topics

- **[getting-started.md](getting-started.md)** — install, the two entry points (`query()` vs `ClaudeSDKClient`), a minimal end-to-end example. Read this first.
- **[options.md](options.md)** — every `ClaudeAgentOptions` field that matters in real code: `cwd`, `allowed_tools`, `disallowed_tools`, `permission_mode`, `system_prompt`, `max_turns`, `max_budget_usd`, `model`, `setting_sources`, `can_use_tool`, `hooks`, `cli_path`, `env`.
- **[messages.md](messages.md)** — the `Message` hierarchy (`UserMessage` / `AssistantMessage` / `SystemMessage` / `ResultMessage`, plus task sub-types), content blocks (`TextBlock` / `ThinkingBlock` / `ToolUseBlock` / `ToolResultBlock`), and the idiomatic consume-until-`ResultMessage` loop.
- **[tools-and-permissions.md](tools-and-permissions.md)** — built-in tool names, how `allowed_tools`/`disallowed_tools`/`permission_mode`/`can_use_tool` interact, PermissionResultAllow/Deny, and the hook surface.
- **[system-prompts.md](system-prompts.md)** — string vs preset vs file; why you almost always want the `"claude_code"` preset (keeps tool intelligence) and how to append to it instead of overriding.
- **[research-subagent-pattern.md](research-subagent-pattern.md)** — the concrete pattern for a read-only research sub-agent: `cwd` pointed at a data directory, read-only tool allowlist, wall-clock timeout with `asyncio.wait_for`, trace capture for logging.
- **[errors-and-gotchas.md](errors-and-gotchas.md)** — exception hierarchy, the bundled-CLI / `cli_path` escape hatch, `allowed_tools` is an approval list not a sandbox, `setting_sources=[]` vs `None`, cross-runtime-context limitations.

## Version-specific warnings

- **Package is `claude-agent-sdk`, not `claude-code-sdk`.** The rename happened at v0.1.0. `pip install claude-code-sdk` either fails or installs an obsolete pre-rename package. Use `pip install claude-agent-sdk`.
- **`ClaudeAgentOptions`, not `ClaudeCodeOptions`.** The old name is gone. See [options.md](options.md).
- **No direct Anthropic API key usage.** The SDK runs the `claude` CLI, which reads auth from its own subprocess environment (`ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, or a Claude.ai login). You do not pass `api_key=...` anywhere in the SDK. See [getting-started.md](getting-started.md).
- **`allowed_tools` is an approval list, not an availability list.** Listed tools auto-approve; unlisted tools still exist and fall through to `permission_mode` / `can_use_tool`. To make a tool unavailable, use `disallowed_tools` or a denying `can_use_tool` callback. Training data frequently gets this backwards. See [tools-and-permissions.md](tools-and-permissions.md).
- **Overriding `system_prompt` with a bare string turns off the Claude Code preset** — you lose the trained tool-use prompts, memory-loading behavior, working-directory context injection, etc. Prefer `{"type": "preset", "preset": "claude_code", "append": "..."}` or leave `system_prompt=None` and steer via the user message. See [system-prompts.md](system-prompts.md).
- **`max_turns` counts turns, not wall-clock seconds.** For a hard time ceiling wrap the `async for` in `asyncio.wait_for(..., timeout=N)`. `max_budget_usd` is the cost ceiling. See [options.md](options.md).
- **`SystemMessage` has task sub-types.** `TaskStartedMessage`, `TaskProgressMessage`, `TaskNotificationMessage` subclass `SystemMessage`, so `isinstance(msg, SystemMessage)` matches all four. Don't assume only one shape. See [messages.md](messages.md).
- **`setting_sources=[]` ≠ `setting_sources=None`.** `None` means "use CLI defaults" (which loads `.claude/settings.json`, etc.); `[]` means "load nothing." A v0.1.60 bug fix made `[]` actually do what it says. See [options.md](options.md).
- **`can_use_tool` requires streaming-mode prompt.** You cannot pass a `str` prompt and a `can_use_tool` callback together; the SDK raises `ValueError`. See [tools-and-permissions.md](tools-and-permissions.md).

## Sources

- Repo: https://github.com/anthropics/claude-agent-sdk-python (v0.1.63)
- Docs: https://docs.anthropic.com/en/docs/claude-code/sdk
- Platform docs: https://platform.claude.com/docs/en/agent-sdk/python
- CHANGELOG: `raw/sdk-CHANGELOG.md`
- Type definitions: `raw/sdk-types.py`
- Public API surface: `raw/sdk-__init__.py`
