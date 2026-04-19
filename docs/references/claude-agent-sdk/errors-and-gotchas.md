---
title: Errors and gotchas
concept: claude-agent-sdk
updated: 2026-04-18
source: src/claude_agent_sdk/_errors.py, examples/*.py, CHANGELOG.md
---

> Anchors agents to current `claude-agent-sdk` v0.1.x. These are the traps that don't show up in training data because the SDK's subprocess-and-bundled-CLI architecture is unusual.

# Errors and gotchas

## Exception hierarchy

```python
from claude_agent_sdk import (
    ClaudeSDKError,       # base
    CLIConnectionError,   # socket / pipe issues talking to the CLI
    CLINotFoundError,     # inherits CLIConnectionError — no claude binary available
    ProcessError,         # CLI process exited non-zero; has .exit_code and .stderr
    CLIJSONDecodeError,   # malformed JSON from the CLI; has .line and .original_error
)
```

Defined in `raw/sdk-errors.py`. A typical `try/except` ladder:

```python
try:
    async for msg in query(prompt="...", options=opts):
        ...
except CLINotFoundError as e:
    # Bundled CLI missing (unusual) or cli_path wrong
    raise RuntimeError(f"Claude CLI not installed: {e}") from e
except ProcessError as e:
    # CLI crashed — often auth failure or malformed options
    logger.error("CLI exit %d: %s", e.exit_code, e.stderr)
    raise
except CLIJSONDecodeError as e:
    # CLI emitted non-JSON on the stdio channel; usually a CLI bug
    logger.error("bad CLI output: %s", e.line)
    raise
except ClaudeSDKError:
    # Anything else from the SDK
    raise
```

Note: there's also `MessageParseError` for corrupted message payloads; it's not in `__init__.py`'s public exports but it's in `_errors.py` and can escape.

## The SDK spawns a subprocess — architectural implications

The SDK is a client to the bundled `claude` CLI, not a direct HTTP client to the Messages API. That means:

- **Startup has real latency** — roughly 1-2 seconds to spawn the CLI, negotiate the control protocol, and send the initial prompt. For voice-realtime use, budget this into your TTFA.
- **Authentication is whatever the subprocess sees.** Set `ANTHROPIC_API_KEY` in the parent process (it's inherited) or pass it via `options.env={"ANTHROPIC_API_KEY": "..."}`. There is no `api_key` parameter anywhere in the SDK.
- **`cli_path`** lets you pin to a specific CLI build. Useful when you want a newer CLI than the version bundled with your SDK release, or a system-wide install with custom plugins. Path resolves through the process's `PATH` if relative.
- **Platform wheels bundle a platform-specific CLI.** The PyPI wheels include the CLI binary for Linux/macOS/Windows. A source install (`sdist`) does not — you'd need `cli_path` pointing at a manually installed CLI.

## The `setting_sources=[]` bug (fixed v0.1.60)

Before v0.1.60, passing an empty list silently fell through to defaults because the SDK treated empty lists as falsy. If you're on an older version, use `setting_sources=None` (and accept the defaults) or upgrade. The intended semantics are:

- `None` — use CLI defaults (typically loads user + project settings).
- `[]` — load nothing. Clean, isolated session.
- `["user"]` / `["project"]` / `["local"]` or combinations — load only the listed sources.

## `allowed_tools` is an approval list, not an availability filter

Said elsewhere but worth repeating in a gotcha doc: `allowed_tools=["Read"]` does **not** prevent Claude from calling `Write`. It means "auto-approve `Read`, ask via `permission_mode` or `can_use_tool` for anything else."

To actually make `Write` unavailable:

```python
disallowed_tools=["Write", "Edit", "MultiEdit", "NotebookEdit"]
# OR a denying can_use_tool callback
```

## `can_use_tool` requires streaming-mode prompt

```python
# ❌ TypeError at connect()
options = ClaudeAgentOptions(can_use_tool=gate)
async for msg in query(prompt="hello", options=options):  # str prompt → ValueError
    ...

# ✅ Use ClaudeSDKClient (always streaming)
async with ClaudeSDKClient(options=options) as client:
    await client.query("hello")
    async for msg in client.receive_response():
        ...

# ✅ Or pass an AsyncIterable prompt to query()
async def prompts():
    yield {"type": "user", "message": {"role": "user", "content": "hello"}}

async for msg in query(prompt=prompts(), options=options):
    ...
```

## Cross-runtime-context pitfall for `ClaudeSDKClient`

`ClaudeSDKClient` holds an anyio task group from `connect()` to `disconnect()`. You **cannot** hand the same client between `asyncio` and `trio`, or between separate nursery / task-group scopes. All operations on one client must be inside the same async context where it was connected. The client's own docstring calls this out (`client.py` lines 55-61).

Practically: use `async with ClaudeSDKClient(...) as client:` and do everything inside that block. Don't stash the client in a module-global and reuse across requests unless you're sure they share a runtime context.

## `AssistantMessage.content` is plural

Multiple blocks can show up in a single message — a `ThinkingBlock` followed by a `ToolUseBlock`, or several `TextBlock`s interleaved with `ToolUseBlock`s. Never assume `content[0]` is text. Always iterate and isinstance-check.

## `max_budget_usd` as a circuit breaker

Cost is hard to predict when tool results vary in size. For a sub-agent with unbounded grep/read, set `max_budget_usd` conservatively (e.g. `0.25`) as a runaway-prevention net. The session ends early with an error `ResultMessage` when exceeded — handle it like any other error result.

## `extra_args` — undocumented CLI flags

`extra_args: dict[str, str | None]` passes arbitrary flags through to the CLI. Known useful flags:

| Flag | Effect |
|---|---|
| `"replay-user-messages": None` | CLI emits `UserMessage`s with `uuid` populated — required for `rewind_files()` checkpointing. |

For unknown CLI flags, consult the installed CLI's `--help` output or `raw/sdk-CHANGELOG.md` which records "Updated bundled Claude CLI to version X.Y.Z" entries you can cross-reference.

## The "no response" failure mode

If `query()` yields no messages at all (not even an init `SystemMessage`), the CLI subprocess likely failed during startup. Common causes:

- No auth (`ANTHROPIC_API_KEY` missing and no Claude.ai session).
- `cli_path` points at a non-executable.
- `cwd` is a non-existent or unreadable directory.

Hook `options.stderr = lambda line: logger.warning("[cli] %s", line)` to surface the CLI's error output before diagnosing from Python exceptions alone.

## Common mistakes

| Training-data default | Correct in v0.1.x |
|---|---|
| `try: ... except Exception as e: ...` and hope | Use typed exceptions: `CLINotFoundError`, `ProcessError`, `CLIJSONDecodeError` |
| `api_key` parameter on client/options | No such parameter; auth via CLI subprocess env |
| Passing a client instance across task groups | One client per async context; always `async with` |
| `allowed_tools=[]` to disable tools | `[]` = "nothing pre-approved" ≠ "no tools". Use `disallowed_tools` for hard blocks. |
| `setting_sources=[]` on v < 0.1.60 expected to isolate | Silently ignored pre-v0.1.60. Upgrade or use `None`. |
| Assuming `AssistantMessage.content[0].text` works | `content[0]` might be a `ThinkingBlock` or `ToolUseBlock`. Iterate + isinstance. |
