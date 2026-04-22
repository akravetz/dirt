"""Lightweight OTP-style supervisor for hwd background loops.

Each background service exposes ``async def run(stop_event)`` and is
expected to live for the process's lifetime. ``supervise`` wraps such a
loop with:

- Broad-Exception restart (CancelledError still propagates — cooperative
  shutdown is never swallowed).
- A sliding-window failure budget (``max_restarts`` crashes within
  ``window_s`` seconds → give up and re-raise).
- A ``backoff_s`` pause between restarts so a tight crash loop doesn't
  spin the CPU.

When the budget is exhausted, ``supervise`` raises so the outer layer
(``_crash_watchdog`` in ``app.py`` → ``signal.raise_signal(SIGTERM)`` →
uvicorn graceful shutdown → systemd ``Restart=on-failure``) can take
over. ``StartLimitBurst`` / ``StartLimitIntervalSec`` on the unit cap
process-level restarts the same way.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable

from dirt_shared.observability import log_event

logger = logging.getLogger(__name__)

STREAM = "supervisor"


async def supervise(  # noqa: PLR0913 — 3 positional + 3 kw-only tuning knobs
    name: str,
    run: Callable[[asyncio.Event], Awaitable[None]],
    stop_event: asyncio.Event,
    *,
    max_restarts: int = 5,
    window_s: float = 60.0,
    backoff_s: float = 5.0,
) -> None:
    """Run ``run(stop_event)`` under a sliding-window restart budget.

    Re-raises the last exception if ``max_restarts`` failures occur
    within ``window_s``. A clean return from ``run`` is terminal.
    """
    crashes: collections.deque[float] = collections.deque(maxlen=max_restarts)
    while not stop_event.is_set():
        try:
            await run(stop_event)
        except asyncio.CancelledError:
            raise
        except Exception:
            now = time.monotonic()
            crashes.append(now)
            logger.exception("supervised task %s crashed", name)
            log_event(STREAM, "crash", task=name)

            if len(crashes) == max_restarts and (now - crashes[0]) < window_s:
                logger.error(
                    "supervised task %s: %d crashes in %.1fs — giving up",
                    name,
                    max_restarts,
                    window_s,
                )
                log_event(
                    STREAM,
                    "budget_exhausted",
                    task=name,
                    max_restarts=max_restarts,
                    window_s=window_s,
                )
                raise

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=backoff_s)
        else:
            logger.info("supervised task %s exited cleanly", name)
            return

    logger.info("supervised task %s stopped (stop_event set)", name)
