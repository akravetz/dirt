---
title: Messages and content blocks
concept: claude-agent-sdk
updated: 2026-04-18
source: src/claude_agent_sdk/types.py (message/block dataclasses, ~line 855)
---

> Anchors agents to current `claude-agent-sdk` v0.1.x. The message surface is richer than the Anthropic Messages API — training data rarely covers `SystemMessage`, task sub-types, or `ResultMessage`.

# Messages and content blocks

Both `query()` and `ClaudeSDKClient.receive_messages()` yield `Message` objects. `Message` is a union of `UserMessage | AssistantMessage | SystemMessage | ResultMessage` (plus task subclasses of `SystemMessage`). You always get at least one `SystemMessage` (the init), then a stream of `AssistantMessage` / `UserMessage` / task notifications, and exactly one terminal `ResultMessage`.

## The loop shape

Idiomatic pattern — iterate until `ResultMessage`:

```python
from claude_agent_sdk import (
    AssistantMessage, ResultMessage, SystemMessage, TextBlock,
    ThinkingBlock, ToolUseBlock, ToolResultBlock, UserMessage, query,
)

async for msg in query(prompt="..."):
    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                print(block.text)
            elif isinstance(block, ToolUseBlock):
                print(f"tool use: {block.name}({block.input})")
    elif isinstance(msg, UserMessage):
        # Tool results the CLI generated — usually not what you print,
        # but useful for trace logging.
        pass
    elif isinstance(msg, SystemMessage):
        # Init, task notifications, etc. Filter on msg.subtype if needed.
        pass
    elif isinstance(msg, ResultMessage):
        # Terminal. Loop will end naturally after this iteration for query();
        # for ClaudeSDKClient use receive_response() which stops for you.
        if msg.is_error:
            raise RuntimeError(msg.result or "agent error")
        print(f"cost=${msg.total_cost_usd:.4f}, turns={msg.num_turns}")
```

## `AssistantMessage`

What Claude actually emits. Content is a list of blocks.

```python
@dataclass
class AssistantMessage:
    content: list[ContentBlock]        # TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock
    model: str                          # actual model used (after any fallback)
    parent_tool_use_id: str | None      # set if this is a sub-agent's message
    error: AssistantMessageError | None # "rate_limit", "server_error", etc. — usually None
    usage: dict | None                  # {"input_tokens":..., "output_tokens":..., "cache_read_input_tokens":...}
    message_id: str | None
    stop_reason: str | None             # "end_turn", "tool_use", "max_tokens", ...
    session_id: str | None
    uuid: str | None
```

A single turn typically produces multiple `AssistantMessage`s — one with a `ToolUseBlock`, then another after the tool result comes back. The text you want to display to a user is usually the `TextBlock` on the *last* `AssistantMessage` before the `ResultMessage`.

## `UserMessage`

What the CLI feeds back to Claude — includes your initial prompt and any `ToolResultBlock`s from tool executions. You usually don't render these; they're useful for trace logs.

```python
@dataclass
class UserMessage:
    content: str | list[ContentBlock]
    uuid: str | None                     # set when extra_args={"replay-user-messages": None}
    parent_tool_use_id: str | None
    tool_use_result: dict | None
```

## `SystemMessage` and task sub-types

`SystemMessage` carries subtyped metadata. `.subtype` is a string — the common ones are `"init"` (session start), `"tool_permission_request"`, `"task_started"`, `"task_progress"`, `"task_notification"`, `"context_compacted"`.

Task-related system messages are **subclasses** of `SystemMessage` with typed fields — `isinstance(msg, SystemMessage)` matches them all, so a broad branch works, but you can also downcast:

```python
@dataclass
class TaskStartedMessage(SystemMessage):
    task_id: str
    description: str
    uuid: str
    session_id: str
    tool_use_id: str | None
    task_type: str | None

@dataclass
class TaskProgressMessage(SystemMessage):
    task_id: str
    description: str
    usage: TaskUsage          # {"total_tokens": int, "tool_uses": int, "duration_ms": int}
    uuid: str
    session_id: str
    tool_use_id: str | None
    last_tool_name: str | None

@dataclass
class TaskNotificationMessage(SystemMessage):
    task_id: str
    status: Literal["completed", "failed", "stopped"]
    output_file: str
    summary: str
    uuid: str
    session_id: str
    tool_use_id: str | None
    usage: TaskUsage | None
```

Use these when you spawn sub-agents via the `Task` tool and want to stream progress to your UI.

## `ResultMessage` — the terminal

Exactly one per invocation. This is how you know the agent is done.

```python
@dataclass
class ResultMessage:
    subtype: str                    # "success" | "error" | "aborted"
    duration_ms: int                # wall clock
    duration_api_ms: int            # time spent in API calls
    is_error: bool
    num_turns: int
    session_id: str
    stop_reason: str | None
    total_cost_usd: float | None    # set when not 0
    usage: dict | None              # aggregated input/output/cache tokens
    result: str | None              # final text answer on success; error msg on failure
    structured_output: Any          # populated when options.output_format was set
```

`ResultMessage.result` often contains the clean final answer when Claude finishes normally. Check `is_error` first and fall back to mining `AssistantMessage.content` text blocks if `result` is `None`.

## Content blocks

```python
@dataclass
class TextBlock:
    text: str

@dataclass
class ThinkingBlock:
    thinking: str
    signature: str

@dataclass
class ToolUseBlock:
    id: str
    name: str              # e.g., "Bash", "Read", "Grep"
    input: dict[str, Any]  # tool arguments

@dataclass
class ToolResultBlock:
    tool_use_id: str       # matches a ToolUseBlock.id
    content: str | list[dict] | None
    is_error: bool | None
```

`ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock`. Always `isinstance`-check before touching fields — `.text` doesn't exist on a `ToolUseBlock`.

## Capturing a trace for logging

```python
trace: list[dict] = []
final_text: str = ""

async for msg in query(prompt=prompt, options=opts):
    if isinstance(msg, AssistantMessage):
        turn = {"role": "assistant", "blocks": []}
        for b in msg.content:
            if isinstance(b, TextBlock):
                turn["blocks"].append({"type": "text", "text": b.text})
                final_text = b.text
            elif isinstance(b, ToolUseBlock):
                turn["blocks"].append({"type": "tool_use", "name": b.name,
                                       "input": b.input, "id": b.id})
        trace.append(turn)
    elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
        results = []
        for b in msg.content:
            if isinstance(b, ToolResultBlock):
                results.append({"tool_use_id": b.tool_use_id,
                                "content": b.content, "is_error": b.is_error})
        if results:
            trace.append({"role": "tool_results", "results": results})
    elif isinstance(msg, ResultMessage):
        final_text = msg.result or final_text
        break
```

The trace is appendable JSONL input — one event per dict — suitable for `sessions/subagents/YYYY-MM-DD.jsonl` style logging.

## Common mistakes

| Training-data default | Correct in v0.1.x |
|---|---|
| `msg.content` is always a string | `AssistantMessage.content` is `list[ContentBlock]`; iterate and isinstance-check |
| Only `AssistantMessage` and `UserMessage` exist | Also `SystemMessage`, `ResultMessage`, plus task subclasses |
| `response.output_text` / `response.final_answer` | Scan `AssistantMessage.content` blocks, or read `ResultMessage.result` |
| Exit the loop on `stop_reason == "end_turn"` | Wait for `ResultMessage` — multiple `AssistantMessage`s can intervene with tool calls |
| `ThinkingBlock` is optional and never shows up | It does when `thinking` is enabled — always handle it in the block loop |
