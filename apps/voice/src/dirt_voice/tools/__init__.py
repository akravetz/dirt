"""Tool registry — framework-agnostic definitions shared across channels.

Channels (voice, telegram, ...) build their tools at composition time via
``build_*_tools(...)`` factories that take the services they need as
parameters. Each factory returns a list of ``ToolSpec`` whose handlers
closure over the injected services — no module-level service access.

Design principles (voice-agent-first):
- Names and descriptions are terse — every description token taxes TTFA.
- Handlers return small dicts shaped for the LLM to paraphrase into speech.
- Slow handlers (sub-agents, vision) set ``cancel_on_interruption=False``
  so brief filler ("mhmm") from the user doesn't abort them mid-flight.
- Every tool has an explicit ``timeout_secs`` — fail loud rather than hang.
- Errors return ``{"error": "..."}`` rather than raising — lets the LLM
  adapt and explain, rather than the pipeline dropping.
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
    properties: dict[str, Any]
    required: list[str]
    handler: ToolHandler
    cancel_on_interruption: bool = True
    timeout_secs: float = 5.0
