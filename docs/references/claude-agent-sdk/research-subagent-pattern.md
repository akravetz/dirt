---
title: Read-only research sub-agent pattern
concept: claude-agent-sdk
updated: 2026-04-18
source: derived from src/claude_agent_sdk/{client,query,types}.py + examples/
---

> Anchors agents to current `claude-agent-sdk` v0.1.x. This is the concrete pattern for `src/dirt/tools/wiki.py` and any future sub-agent of the same shape.

# Research sub-agent pattern

**Goal:** embed a local Claude-Code-style agent inside a larger app as a single async function. Input: one natural-language question + a scoped filesystem. Output: one short spoken-style answer + a structured trace for logging.

This is the `ask_wiki` shape — the function is called from a voice pipeline, has a wall-clock budget, is read-only, and can't fail-stop the caller.

## Minimal template

```python
import asyncio
import contextvars
import json
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    CLINotFoundError,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

# Per-caller correlation ID, threaded through to the sub-agent log.
_CONVERSATION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_conversation_id", default=None
)


async def ask_wiki(
    question: str,
    *,
    wiki_root: Path,
    sessions_dir: Path,
    timeout_s: float = 30.0,
    model: str | None = None,
) -> dict:
    """Run a read-only Claude Code sub-agent against `wiki_root` to answer `question`."""
    if not question.strip():
        return {"error": "empty question", "answer": ""}

    options = ClaudeAgentOptions(
        cwd=wiki_root,
        allowed_tools=["Bash", "Read", "Grep", "Glob"],
        disallowed_tools=["Write", "Edit", "MultiEdit", "NotebookEdit"],
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": (
                "Answer in 1-3 sentences suitable for speaking aloud. "
                "No markdown, no bullets, no URLs. Cite files by name "
                "only when essential."
            ),
        },
        max_turns=25,
        max_budget_usd=0.25,
        setting_sources=[],   # isolated — ignore host .claude/ config
        model=model,          # let the caller pass "claude-sonnet-4-5" etc. or None
    )

    prompt = (
        f"Today is {date.today()}. "
        "The grow wiki is the current working directory — grep and read "
        "whatever you need to answer the question below.\n\n"
        f"Question: {question}"
    )

    trace: list[dict] = []
    final_text: str = ""
    result_msg: ResultMessage | None = None
    started = time.monotonic()

    async def run() -> None:
        nonlocal final_text, result_msg
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                turn: dict = {"role": "assistant", "blocks": []}
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        turn["blocks"].append({"type": "text", "text": b.text})
                        final_text = b.text
                    elif isinstance(b, ToolUseBlock):
                        turn["blocks"].append({
                            "type": "tool_use",
                            "id": b.id,
                            "name": b.name,
                            "input": b.input,
                        })
                if turn["blocks"]:
                    trace.append(turn)
            elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
                results = [
                    {"tool_use_id": b.tool_use_id,
                     "is_error": b.is_error,
                     "content": b.content}
                    for b in msg.content if isinstance(b, ToolResultBlock)
                ]
                if results:
                    trace.append({"role": "tool_results", "results": results})
            elif isinstance(msg, ResultMessage):
                result_msg = msg

    try:
        await asyncio.wait_for(run(), timeout=timeout_s)
    except asyncio.TimeoutError:
        _log_subagent_event(sessions_dir, "ask_wiki", question, trace,
                            answer=None, error="timeout",
                            duration_ms=int((time.monotonic() - started) * 1000))
        return {"error": "timeout", "answer": "I couldn't answer in time."}
    except CLINotFoundError as e:
        return {"error": f"cli_not_found: {e}", "answer": ""}
    except ClaudeSDKError as e:
        _log_subagent_event(sessions_dir, "ask_wiki", question, trace,
                            answer=None, error=str(e),
                            duration_ms=int((time.monotonic() - started) * 1000))
        return {"error": str(e), "answer": ""}

    answer = (result_msg.result if result_msg and result_msg.result else final_text)
    _log_subagent_event(
        sessions_dir, "ask_wiki", question, trace,
        answer=answer,
        error=(result_msg.result if result_msg and result_msg.is_error else None),
        duration_ms=int((time.monotonic() - started) * 1000),
        usage=(result_msg.usage if result_msg else None),
        cost_usd=(result_msg.total_cost_usd if result_msg else None),
        stop_reason=(result_msg.stop_reason if result_msg else None),
    )
    return {"answer": answer or "I couldn't find a clear answer in the wiki."}


def _log_subagent_event(
    sessions_dir: Path,
    name: str,
    question: str,
    trace: list[dict],
    *,
    answer: str | None,
    duration_ms: int,
    error: str | None = None,
    usage: dict | None = None,
    cost_usd: float | None = None,
    stop_reason: str | None = None,
) -> None:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = sessions_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    event = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "conversation_id": _CONVERSATION_ID.get(),
        "name": name,
        "question": question,
        "trace": trace,
        "answer": answer,
        "error": error,
        "duration_ms": duration_ms,
        "usage": usage,
        "cost_usd": cost_usd,
        "stop_reason": stop_reason,
    }
    with path.open("a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
```

## Design choices worth calling out

**Tool kit.** `Bash + Read + Grep + Glob` covers every research move Claude has been trained on. `Bash` is the generality escape hatch (`wc -l`, `find ... -mtime`, `head`, `tail`) for things the dedicated tools don't cover cleanly. Adding `Task` would let Claude spawn its own sub-sub-agents — powerful but expensive and usually unnecessary for a one-question research call.

**`cwd` is scoping, not sandboxing.** `cwd=wiki/` ensures Grep/Glob/Read default to the right tree and that `Bash` starts there, but the process can `cd ..`. For a grow wiki on a trusted machine this is fine. For adversarial or multi-tenant input, run under a namespace with `wiki/` bind-mounted read-only, or add a `can_use_tool` gate that rejects any `Bash` command containing `cd ` / `..` / absolute paths outside `cwd`.

**Wall clock, not turn count.** `max_turns=25` is a sanity ceiling, but the real budget is `asyncio.wait_for(..., timeout=30)`. If the agent gets stuck in a loop the turn count will climb slowly; if it makes one slow tool call the wall clock will catch it.

**Budget cap as a safety net.** `max_budget_usd=0.25` is a hard $ ceiling. For a 1-3 sentence research answer, typical spend is a few cents; 25¢ is the "something's gone wrong" threshold.

**Isolated settings.** `setting_sources=[]` explicitly opts out of loading the host's `.claude/settings.json`. Without this, a user-level permission rule (say, `acceptEdits`) could accidentally lift the safety net. The v0.1.60 bug fix made `[]` actually mean "none" — older versions silently treated it as "defaults."

**Trace capture is explicit.** The SDK doesn't hand you a structured trace — you build one by walking `AssistantMessage.content` for tool-use blocks and `UserMessage.content` for tool results. The trace is what makes post-hoc debugging ("why didn't it find the plant-C page") possible.

**`ResultMessage.result` vs final `TextBlock`.** On success, `result_msg.result` is typically the clean final answer. On failure (budget exceeded, refusal, etc.) it carries the error text and `is_error=True`. Falling back to the last `TextBlock` handles edge cases where `result` is `None` but Claude did produce text.

**`conversation_id` via `contextvars`.** The caller (a voice turn in `run_conversation`) sets the context var at the top of its scope; `ask_wiki` reads it. No plumbing through function signatures, and it works across the `asyncio.wait_for` boundary because `contextvars` propagate into tasks spawned inside the same event loop.

## Wiring `conversation_id` at the caller

```python
# In the voice channel's run_conversation():
from dirt.tools.wiki_subagent import _CONVERSATION_ID  # or expose a helper

token = _CONVERSATION_ID.set(str(uuid.uuid4()))
try:
    # The tool handler that calls ask_wiki runs inside this scope,
    # even when it's awaited several layers deep.
    await run_pipecat_loop()
finally:
    _CONVERSATION_ID.reset(token)
```

The same `conversation_id` should also be stamped on the voice channel's `wake` / `conversation_end` events. Then `jq` across both JSONL files joins a voice conversation to its sub-agent traces.

## Cancellation propagates

When `asyncio.wait_for` fires, it cancels the inner coroutine, which cancels the `async for msg in query(...)` iteration, which tells the SDK to tear down the subprocess cleanly. You don't need to explicitly kill anything — but you do need to catch `asyncio.TimeoutError` to turn it into a user-visible answer instead of propagating as an exception.

If the pipeline has already moved on (e.g. the user interrupted the voice turn), wrap the outer tool handler in its own try-finally to ensure the log event is written even when the caller is cancelled mid-flight.

## Common mistakes

| Training-data default | Correct in v0.1.x |
|---|---|
| `max_turns=5` as the timeout mechanism | `asyncio.wait_for(..., timeout=N)` for wall clock; `max_turns` is a turn ceiling |
| Parsing `response.output_text` | Walk `AssistantMessage.content` + check `ResultMessage.result` |
| Relying on `allowed_tools` to block writes | Use `disallowed_tools=["Write","Edit","MultiEdit"]` |
| Overriding `system_prompt` with a bare string | `{"type":"preset","preset":"claude_code","append":"..."}` to keep tool intelligence |
| Interpolating the date into `system_prompt` each call | Put it in the user message; keep system prompt frozen for cache hits |
| Dropping `ResultMessage` when you get `end_turn` on the last `AssistantMessage` | Always iterate to `ResultMessage`; that's when the session is actually done |
