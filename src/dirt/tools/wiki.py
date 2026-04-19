"""`ask_wiki` — delegated Claude Code sub-agent that reads the grow wiki.

The sub-agent runs via the Claude Agent SDK with the Claude Code tool kit
(Bash/Read/Grep/Glob) scoped to `wiki/`. It's read-only by policy — Write/Edit
are on the disallowed list so the research agent can't mutate the wiki by
accident. Trace and result are persisted to `sessions/subagents/YYYY-MM-DD.jsonl`.

Reference for the SDK surface: `docs/references/claude-agent-sdk/INDEX.md`.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date
from pathlib import Path
from typing import Any

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

from dirt.config import grow_week
from dirt.observability import log_event
from dirt.tools import ToolSpec

_WIKI_ROOT = Path(__file__).resolve().parents[3] / "wiki"

# Haiku 4.5 is the right fit for this sub-agent: the work is "read 1-3 wiki
# files, synthesize 1-3 spoken sentences", not open-ended reasoning. Haiku
# is ~3x cheaper than Sonnet and ~2-3x faster for straight extraction, which
# matters because this call blocks a voice turn. Pinning to a concrete model
# ID rather than the "haiku" alias to keep behavior reproducible across
# Claude Code CLI versions. See docs/references/claude-agent-sdk/options.md.
_MODEL = "claude-haiku-4-5"

_BUDGET_USD = 0.25
_TIMEOUT_S = 30.0
_MAX_TURNS = 25

_PROMPT_APPEND = (
    "Answer in 1-3 sentences suitable for speaking aloud. "
    "No markdown, no bullets, no URLs. If you truly can't find the answer "
    "in the wiki, say so plainly."
)


async def _ask_wiki(question: str) -> dict[str, Any]:
    question = (question or "").strip()
    if not question:
        return {"error": "empty question", "answer": ""}

    options = ClaudeAgentOptions(
        cwd=_WIKI_ROOT,
        model=_MODEL,
        allowed_tools=["Bash", "Read", "Grep", "Glob"],
        disallowed_tools=["Write", "Edit", "MultiEdit", "NotebookEdit"],
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": _PROMPT_APPEND,
        },
        max_turns=_MAX_TURNS,
        max_budget_usd=_BUDGET_USD,
        setting_sources=[],  # isolated — do not inherit host .claude/ settings
    )

    prompt = (
        f"Today is {date.today()}, week {grow_week()} of the grow. "
        "You're in the grow wiki (this directory). Start by reading "
        "`CLAUDE.md` — it's the wiki's operating manual and has a routing "
        "table that tells you which file to read for each question shape. "
        "Most questions are answered by one section of `overview.md`; read "
        "there before greping or reading `log.md`.\n\n"
        f"Question: {question}"
    )

    trace: list[dict[str, Any]] = []
    final_text = ""
    result_msg: ResultMessage | None = None
    read_paths: list[str] = []
    started = time.monotonic()

    async def run() -> None:
        nonlocal final_text, result_msg
        async for msg in query(prompt=prompt, options=options):
            # ms since _ask_wiki started — tells us where the wall clock
            # went (SDK spawn vs first LLM call vs tool exec vs next LLM).
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
                        final_text = b.text
                    elif isinstance(b, ToolUseBlock):
                        turn["blocks"].append({
                            "type": "tool_use",
                            "id": b.id,
                            "name": b.name,
                            "input": b.input,
                        })
                        if b.name == "Read":
                            fp = b.input.get("file_path")
                            if isinstance(fp, str) and fp not in read_paths:
                                read_paths.append(fp)
                if turn["blocks"]:
                    trace.append(turn)
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
                    trace.append({
                        "role": "tool_results",
                        "ts_ms": ts_ms,
                        "results": results,
                    })
            elif isinstance(msg, ResultMessage):
                result_msg = msg

    try:
        await asyncio.wait_for(run(), timeout=_TIMEOUT_S)
    except TimeoutError:
        log_event(
            "subagent_calls", "ask_wiki",
            question=question,
            trace=trace,
            error="timeout",
            duration_ms=int((time.monotonic() - started) * 1000),
            sources=read_paths,
        )
        return {"error": "timeout", "answer": "I couldn't answer in time."}
    except CLINotFoundError as e:
        return {"error": f"cli_not_found: {e}", "answer": ""}
    except ClaudeSDKError as e:
        log_event(
            "subagent_calls", "ask_wiki",
            question=question,
            trace=trace,
            error=str(e),
            duration_ms=int((time.monotonic() - started) * 1000),
            sources=read_paths,
        )
        return {"error": str(e), "answer": ""}

    # Prefer ResultMessage.result (the CLI's canonical final answer) over the
    # last TextBlock, which can include trailing tool-use explanation.
    answer = (
        result_msg.result
        if result_msg and result_msg.result
        else final_text or ""
    )
    error_text = result_msg.result if (result_msg and result_msg.is_error) else None

    log_event(
        "subagent_calls", "ask_wiki",
        question=question,
        trace=trace,
        answer=answer if not error_text else None,
        error=error_text,
        duration_ms=int((time.monotonic() - started) * 1000),
        usage=(result_msg.usage if result_msg else None),
        cost_usd=(result_msg.total_cost_usd if result_msg else None),
        stop_reason=(result_msg.stop_reason if result_msg else None),
        sources=read_paths,
    )

    return {
        "answer": answer or "I couldn't find a clear answer in the wiki.",
        "sources": read_paths,
    }


ASK_WIKI = ToolSpec(
    name="ask_wiki",
    description=(
        "Delegate a question to a research sub-agent that searches and reads "
        "the grow wiki. Use for anything referencing plants, schedules, past "
        "decisions, technique, or 'what's next' questions. Returns a short "
        "spoken-ready answer."
    ),
    properties={
        "question": {
            "type": "string",
            "description": "The question to research, in natural language.",
        },
    },
    required=["question"],
    handler=_ask_wiki,
    cancel_on_interruption=False,  # don't abort a 20s lookup on a filler "mhmm"
    timeout_secs=_TIMEOUT_S,
)
