"""`ask_wiki` — delegated Sonnet sub-agent that searches and reads the wiki."""

from __future__ import annotations

import re
from pathlib import Path

from anthropic import AsyncAnthropic

from dirt.config import settings
from dirt.tools import ToolSpec

_WIKI_ROOT = Path(__file__).resolve().parents[3] / "wiki"
_MAX_TURNS = 5
_MAX_RESULT_CHARS = 4000
_MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = (
    "You are a research sub-agent that answers questions about an ongoing "
    "indoor cannabis grow by reading the project's wiki. Your answer will be "
    "spoken aloud by a voice assistant, so:\n"
    "- Be direct and concise — 1 to 3 spoken sentences.\n"
    "- No bullet points, no markdown, no URLs.\n"
    "- If the wiki doesn't have the answer, say so plainly.\n"
    "Cite the wiki file you used by calling it by name (e.g. 'plant C's page')."
)


def _safe_wiki_path(rel: str) -> Path | None:
    """Resolve rel under wiki/, rejecting traversal and symlink escapes."""
    try:
        p = (_WIKI_ROOT / rel).resolve()
    except (OSError, ValueError):
        return None
    if _WIKI_ROOT not in p.parents and p != _WIKI_ROOT:
        return None
    return p


def _tool_read_wiki(path: str) -> str:
    p = _safe_wiki_path(path)
    if p is None or not p.is_file():
        return f"error: {path!r} not found in wiki/"
    text = p.read_text()
    if len(text) > _MAX_RESULT_CHARS:
        text = text[:_MAX_RESULT_CHARS] + f"\n...[truncated at {_MAX_RESULT_CHARS} chars]"
    return text


def _tool_grep_wiki(pattern: str, max_matches: int = 30) -> str:
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"error: invalid regex: {e}"

    matches: list[str] = []
    for md in sorted(_WIKI_ROOT.rglob("*.md")):
        rel = md.relative_to(_WIKI_ROOT)
        for i, line in enumerate(md.read_text().splitlines(), 1):
            if rx.search(line):
                matches.append(f"{rel}:{i}: {line.strip()[:200]}")
                if len(matches) >= max_matches:
                    matches.append(f"...[capped at {max_matches} matches]")
                    return "\n".join(matches)
    return "\n".join(matches) or "(no matches)"


_TOOLS_SCHEMA = [
    {
        "name": "read_wiki",
        "description": "Read a wiki file by path relative to the wiki/ root (e.g. 'plants/plant-a.md').",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "grep_wiki",
        "description": "Search the wiki tree with a case-insensitive regex. Returns path:line: match results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "max_matches": {"type": "integer", "default": 30},
            },
            "required": ["pattern"],
        },
    },
]


def _execute_tool(name: str, args: dict) -> str:
    if name == "read_wiki":
        return _tool_read_wiki(args["path"])
    if name == "grep_wiki":
        return _tool_grep_wiki(args["pattern"], args.get("max_matches", 30))
    return f"error: unknown tool {name!r}"


async def _ask_wiki(question: str) -> dict:
    question = (question or "").strip()
    if not question:
        return {"error": "empty question"}
    if not settings.anthropic_api_key:
        return {"error": "ANTHROPIC_API_KEY not configured"}

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages: list[dict] = [{"role": "user", "content": question}]
    sources: list[str] = []

    for _ in range(_MAX_TURNS):
        resp = await client.messages.create(
            model=_MODEL,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            tools=_TOOLS_SCHEMA,
            messages=messages,
        )

        if resp.stop_reason != "tool_use":
            answer = "".join(b.text for b in resp.content if b.type == "text").strip()
            return {"answer": answer or "No answer.", "sources": sources}

        # Run tools, feed results back.
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if block.name == "read_wiki":
                sources.append(block.input.get("path", ""))
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": _execute_tool(block.name, block.input),
            })
        messages.append({"role": "user", "content": tool_results})

    return {"answer": "I couldn't find a clear answer in the wiki.", "sources": sources}


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
    cancel_on_interruption=False,  # don't abort a 2s lookup on a 'mhmm'
    timeout_secs=15.0,
)
