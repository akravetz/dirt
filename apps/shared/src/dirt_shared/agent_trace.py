"""Stream a Claude Agent SDK run into a structured trace.

Shared by:
  - ``dirt_shared.services.daily_synthesis`` (daily-report orchestrator)
  - ``dirt_voice.tools.wiki`` (``ask_wiki`` sub-agent)

Both places build ``ClaudeAgentOptions``, call ``query(prompt, options)``,
and fold the streamed ``AssistantMessage`` / ``UserMessage`` /
``ResultMessage`` events into the trace dict that ``log_event`` persists.
Keeping one loop here stops the two callers from drifting on trace
shape and keeps the retention-policy-sensitive trace fields identical.

Partial-state semantics: callers wrap this in ``asyncio.wait_for`` so a
slow model run gets cancelled at the caller's timeout. Mutations land
on the caller's ``AgentTraceState`` as they happen, so on ``TimeoutError``
the caller still has every event that arrived before cancellation —
that's the "don't lose diagnostic data when it takes too long" contract
the daily report and voice sub-agent both depend on.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)


@dataclass
class AgentTraceState:
    """Accumulated output of a streamed Claude Agent SDK run."""

    trace: list[dict[str, Any]] = field(default_factory=list)
    final_text: str | None = None
    result: ResultMessage | None = None


async def collect_agent_trace(
    *,
    prompt: str,
    options: ClaudeAgentOptions,
    started: float,
    state: AgentTraceState,
    on_tool_use: Callable[[ToolUseBlock], None] | None = None,
) -> None:
    """Stream ``query(prompt, options)`` into ``state`` in place.

    Each ``AssistantMessage`` becomes one trace entry with its TextBlocks,
    ThinkingBlocks, and ToolUseBlocks recorded. ``UserMessage``s with
    ``ToolResultBlock``s become their own trace entries. The terminal
    ``ResultMessage`` lands in ``state.result``.

    ``started`` is the caller's ``time.monotonic()`` reference — passed
    in so ``ts_ms`` on each entry matches the caller's duration accounting
    (log_event's ``duration_ms`` field, etc.).

    ``on_tool_use`` is an optional observer fired AFTER each ToolUseBlock
    is appended to the trace. Used for ``ask_wiki`` to extract Read
    file_paths into a "sources" list for the spoken answer.
    """
    async for msg in query(prompt=prompt, options=options):
        ts_ms = int((time.monotonic() - started) * 1000)
        if isinstance(msg, AssistantMessage):
            turn: dict[str, Any] = {
                "role": "assistant",
                "ts_ms": ts_ms,
                "blocks": [],
            }
            for b in msg.content:
                if isinstance(b, TextBlock):
                    turn["blocks"].append({"type": "text", "text": b.text})
                    state.final_text = b.text
                elif isinstance(b, ThinkingBlock):
                    # Full thinking text — diagnostic record of why the
                    # run took the time it did. Do not truncate;
                    # storage is cheap, replaying a slow run is not.
                    turn["blocks"].append(
                        {
                            "type": "thinking",
                            "thinking": b.thinking,
                            "signature": b.signature,
                        }
                    )
                elif isinstance(b, ToolUseBlock):
                    turn["blocks"].append(
                        {
                            "type": "tool_use",
                            "id": b.id,
                            "name": b.name,
                            "input": b.input,
                        }
                    )
                    if on_tool_use is not None:
                        on_tool_use(b)
            if turn["blocks"]:
                state.trace.append(turn)
        elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
            results = [
                {
                    "tool_use_id": b.tool_use_id,
                    "is_error": b.is_error,
                    "content": b.content,
                }
                for b in msg.content
                if isinstance(b, ToolResultBlock)
            ]
            if results:
                state.trace.append(
                    {
                        "role": "tool_results",
                        "ts_ms": ts_ms,
                        "results": results,
                    }
                )
        elif isinstance(msg, ResultMessage):
            state.result = msg
