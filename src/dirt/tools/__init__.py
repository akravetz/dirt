"""Tool registry — framework-agnostic definitions shared across channels.

Channels (voice, telegram, ...) import `SHARED_TOOLS` and adapt each spec to
their LLM service's calling convention. Business logic lives in `handler`;
the rest is metadata.

Design principles (voice-agent-first):
- Names and descriptions are terse — every description token taxes TTFA.
- Handlers return small dicts shaped for the LLM to paraphrase into speech.
- Slow handlers (sub-agents, vision) set `cancel_on_interruption=False` so
  brief filler ("mhmm") from the user doesn't abort them mid-flight.
- Every tool has an explicit `timeout_secs` — fail loud rather than hang.
- Errors return `{"error": "..."}` rather than raising — lets the LLM adapt
  and explain, rather than the pipeline dropping.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    properties: dict[str, Any]   # JSON-schema style, e.g. {"sensor": {"type": "string", ...}}
    required: list[str]
    handler: ToolHandler
    cancel_on_interruption: bool = True
    timeout_secs: float = 5.0


# Populated at import time by each tool module.
from dirt.tools.sensors import GET_CURRENT_STATUS, GET_SENSOR_TREND  # noqa: E402
from dirt.tools.wiki import ASK_WIKI  # noqa: E402

SHARED_TOOLS: list[ToolSpec] = [
    GET_CURRENT_STATUS,
    GET_SENSOR_TREND,
    ASK_WIKI,
]
