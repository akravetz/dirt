"""Daily-report synthesis runner — wraps the Claude Agent SDK to spawn a
sub-agent that follows the wiki Daily Update Workflow.

Exposes a :class:`SynthesisRunner` protocol (run a synthesis, return a
:class:`SynthesisResult`) so the orchestrator can be tested against a
fake runner without the real claude binary on PATH.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKError,
    CLINotFoundError,
)

from dirt_shared.agent_trace import AgentTraceState, collect_agent_trace
from dirt_shared.observability import log_event
from dirt_shared.services.telegram import (
    TELEGRAM_HTML_WHITELIST,
    TELEGRAM_MAX_MESSAGE_CHARS,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SynthesisResult:
    success: bool
    daily_file: Path | None
    error: str | None
    duration_s: float
    cost_usd: float | None
    final_text: str | None
    # Expected location of the Telegram sidecar the sub-agent writes; the
    # orchestrator reads this path and handles the missing-file case itself.
    telegram_html_path: Path | None = None


class SynthesisRunner(Protocol):
    async def run(
        self,
        target_date: date,
        photo_paths: Sequence[Path],
        sensor_payload: dict[str, Any],
    ) -> SynthesisResult: ...


_SYSTEM_PROMPT_APPEND = (
    "You are the dirt daily-report sub-agent. Your job: produce today's "
    "daily entry, propagate updates per the wiki Daily Update Workflow, "
    "and emit a Telegram-ready summary. "
    "STEP 1: Read `AGENTS.md` (the operating manual) before doing anything "
    "else. STEP 2: Follow the Daily Update Workflow there exactly — write "
    "`wiki/daily/<DATE>.md` with photo observations and sensor readings, "
    "update each plant's Timeline + Current State (one-liner each, no "
    "duplication of observation detail), update environment pages where "
    "trends/anomalies are visible, append to `wiki/log.md`, refresh "
    "`wiki/overview.md` and `wiki/index.md`. STEP 3: Run `uv run scripts/"
    "lint.py` from the repo root and fix anything it flags. STEP 4: Write "
    "the Telegram summary file at the absolute path given in the user "
    "prompt (ignore the wiki directory for this file — it is a Telegram "
    "artifact, not a wiki page). Re-running for the same date is safe — "
    "overwrite freely. The wiki paths are relative to your current "
    "working directory."
)


_TELEGRAM_WHITELIST_PROMPT_STRING = ", ".join(f"<{t}>" for t in TELEGRAM_HTML_WHITELIST)


class ClaudeSynthesisRunner:
    """Production runner — spawns claude-agent-sdk sub-agent."""

    def __init__(  # noqa: PLR0913 — wiki_root+log_dir are required paths; the four trailing kwargs are sub-agent budget knobs kept flat so a single call site can tune one without constructing a budget struct.
        self,
        wiki_root: Path,
        log_dir: Path,
        *,
        model: str = "claude-sonnet-4-6",
        timeout_s: float = 1500.0,
        max_turns: int = 80,
        max_budget_usd: float = 5.0,
    ) -> None:
        self._wiki_root = wiki_root
        self._log_dir = log_dir
        self._model = model
        self._timeout_s = timeout_s
        self._max_turns = max_turns
        self._budget = max_budget_usd

    def _telegram_sidecar_path(self, target_date: date) -> Path:
        return self._log_dir / f"{target_date.isoformat()}.telegram.html"

    def _build_prompt(
        self,
        target_date: date,
        photo_paths: Sequence[Path],
        sensor_payload: dict[str, Any],
    ) -> str:
        photo_lines = "\n".join(f"  - {p}" for p in photo_paths)
        sensor_json = json.dumps(sensor_payload, indent=2, default=str)
        telegram_path = self._telegram_sidecar_path(target_date).resolve()
        return (
            f"Today is {target_date.isoformat()} (MDT). Generate today's "
            "daily entry per the workflow.\n\n"
            "INPUTS\n"
            f"Photos (5 presets, captured at 14:00 MDT today):\n{photo_lines}\n\n"
            "Use the Read tool to view each image — describe what you see "
            "for each plant (color, structure, canopy, any issues).\n\n"
            f"Sensor windows (overnight = 00-06 MDT, morning = 07-14 MDT, "
            f"now = at time of run; values where available, null otherwise):\n"
            f"```json\n{sensor_json}\n```\n\n"
            "WHAT TO PRODUCE\n"
            f"- `wiki/daily/{target_date.isoformat()}.md` with: per-plant "
            "photo observations, a sensor table covering the three windows, "
            "stage-appropriate recommendations, any flagged issues.\n"
            "- One-line Timeline entry on each `wiki/plants/plant-X.md` + a "
            "1-2 sentence rewrite of Current State.\n"
            "- Trend updates on relevant `wiki/environment/*.md` pages "
            "(only if the day's data shows a trend or anomaly worth noting).\n"
            "- Append to `wiki/log.md`.\n"
            "- Refresh `wiki/overview.md` (Plant Status table, Environment "
            "Last Reading, Active Action Items) and `wiki/index.md` (add "
            "today's daily link).\n"
            "- Run `uv run scripts/lint.py` from the repo root and fix any "
            "deterministic issues it flags. The repo root is the parent of "
            "your current directory.\n"
            "\n"
            "TELEGRAM SUMMARY (required, last step)\n"
            f"Write a Telegram-ready HTML summary to the absolute path:\n"
            f"  {telegram_path}\n"
            "Use the Write tool with this exact absolute path — this file "
            "lives outside the wiki tree on purpose.\n"
            "\n"
            "Contract:\n"
            f"- MAX {TELEGRAM_MAX_MESSAGE_CHARS} characters. Count, "
            "don't guess.\n"
            f"- ONLY these HTML tags allowed: "
            f"{_TELEGRAM_WHITELIST_PROMPT_STRING} "
            '(use the `<a href="url">text</a>` form for links). No '
            "headers, no `<p>`, `<ul>`, `<li>`, `<div>`, `<span>`, `<br>`. "
            "Use literal newlines for line breaks and `• ` for bullets.\n"
            "- HTML-escape every literal `<`, `>`, `&` in text content "
            "(write `&lt;`, `&gt;`, `&amp;`).\n"
            "- No markdown syntax — this is HTML, not markdown. `**bold**` "
            "must become `<b>bold</b>`, etc.\n"
            "- No frontmatter, no blank leading/trailing lines.\n"
            "\n"
            "Content: the 30-second read. Top 2-3 actionable items, key "
            "environment readings with any out-of-band flags, anything "
            "urgent. The full wiki entry is the long-form record — this "
            "summary is for a human glancing at a phone. Lead with a bold "
            "title line, then short sections. If everything is nominal, "
            "say so briefly.\n"
        )

    async def run(
        self,
        target_date: date,
        photo_paths: Sequence[Path],
        sensor_payload: dict[str, Any],
    ) -> SynthesisResult:
        options = ClaudeAgentOptions(
            cwd=self._wiki_root,
            model=self._model,
            allowed_tools=["Read", "Edit", "Write", "Glob", "Grep", "Bash"],
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": _SYSTEM_PROMPT_APPEND,
            },
            max_turns=self._max_turns,
            max_budget_usd=self._budget,
            setting_sources=[],
        )

        prompt = self._build_prompt(target_date, photo_paths, sensor_payload)

        state = AgentTraceState()
        started = time.monotonic()

        error: str | None = None
        try:
            await asyncio.wait_for(
                collect_agent_trace(
                    prompt=prompt,
                    options=options,
                    started=started,
                    state=state,
                ),
                timeout=self._timeout_s,
            )
        except TimeoutError:
            error = "timeout"
        except CLINotFoundError as e:
            error = f"cli_not_found: {e}"
        except ClaudeSDKError as e:
            error = f"sdk_error: {e}"

        trace = state.trace
        final_text = state.final_text
        result_msg = state.result
        duration_s = time.monotonic() - started
        daily_file = self._wiki_root / "daily" / f"{target_date.isoformat()}.md"
        telegram_html_path = self._telegram_sidecar_path(target_date)

        # Persist the trace regardless of success.
        self._log_dir.mkdir(parents=True, exist_ok=True)
        trace_path = self._log_dir / f"{target_date.isoformat()}.synthesis.json"
        try:
            trace_path.write_text(
                json.dumps(
                    {
                        "date": target_date.isoformat(),
                        "model": self._model,
                        "duration_s": round(duration_s, 2),
                        "error": error,
                        "trace": trace,
                        "final_text": final_text,
                        "usage": (result_msg.usage if result_msg else None),
                        "cost_usd": (result_msg.total_cost_usd if result_msg else None),
                        "stop_reason": (result_msg.stop_reason if result_msg else None),
                    },
                    indent=2,
                    default=str,
                )
            )
        except OSError as e:
            logger.warning("could not write synthesis trace %s: %s", trace_path, e)

        log_event(
            "daily_report",
            "synthesis_finished",
            date=target_date.isoformat(),
            duration_s=round(duration_s, 2),
            error=error,
            cost_usd=(result_msg.total_cost_usd if result_msg else None),
            daily_file_exists=daily_file.exists(),
        )

        if error is not None:
            return SynthesisResult(
                success=False,
                daily_file=None,
                error=error,
                duration_s=duration_s,
                cost_usd=(result_msg.total_cost_usd if result_msg else None),
                final_text=final_text,
                telegram_html_path=telegram_html_path,
            )

        if not daily_file.exists():
            return SynthesisResult(
                success=False,
                daily_file=None,
                error=f"daily file not created at {daily_file}",
                duration_s=duration_s,
                cost_usd=(result_msg.total_cost_usd if result_msg else None),
                final_text=final_text,
                telegram_html_path=telegram_html_path,
            )

        return SynthesisResult(
            success=True,
            daily_file=daily_file,
            error=None,
            duration_s=duration_s,
            cost_usd=(result_msg.total_cost_usd if result_msg else None),
            final_text=final_text,
            telegram_html_path=telegram_html_path,
        )
