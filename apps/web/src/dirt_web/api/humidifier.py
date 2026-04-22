"""Humidifier endpoints — current state + transition history.

Thin wrappers over :class:`HumidifierStateService`.
"""

from __future__ import annotations

from dirt_contracts.webapp_v1.models import (
    HumidifierHistory,
    HumidifierState,
    HumidifierTransition,
    Range,
)
from fastapi import APIRouter, Depends, Query

from dirt_shared.services.humidifier_state import HumidifierStateService
from dirt_shared.services.readings import RANGE_DELTAS
from dirt_web.deps import get_humidifier_state

router = APIRouter(tags=["humidifier"])


@router.get("/api/humidifier/state", response_model=HumidifierState)
async def humidifier_state(
    service: HumidifierStateService = Depends(get_humidifier_state),
) -> HumidifierState:
    """Return the current humidifier on/off envelope.

    Drives the dashboard humidifier tile header: on/off, seconds since
    the last transition, and off→on cycle count over the last 24h.
    """
    state = await service.get_state()
    # Cold cluster (no humidifier_on rows yet): the service returns
    # ``since=None`` / ``duration_s=None``. The contract requires both
    # as non-null, so anchor them at ``ts`` / 0 — the SPA treats
    # duration_s=0 as "just transitioned / unknown", which matches the
    # semantic "we have no history to show yet."
    since = state.since if state.since is not None else state.ts
    duration_s = int(state.duration_s) if state.duration_s is not None else 0
    return HumidifierState(
        on=state.on,
        since=since,
        duration_s=duration_s,
        cycles_24h=state.cycles_24h,
        ts=state.ts,
    )


@router.get("/api/humidifier/history", response_model=HumidifierHistory)
async def humidifier_history(
    range: Range = Query(...),
    service: HumidifierStateService = Depends(get_humidifier_state),
) -> HumidifierHistory:
    """Return on/off transitions for the requested range.

    FastAPI rejects out-of-enum ``range`` values at the query layer with
    422 before the handler runs — the contract's 400 response covers the
    same intent. The cutoff is derived from the injected clock (via
    ``service.now()``) so tests can drive the window deterministically
    without reaching into ``_clock`` — mirrors the pattern used by the
    sensors history route.
    """
    cutoff = service.now() - RANGE_DELTAS[range.value]
    transitions = await service.get_history(cutoff)
    points = [HumidifierTransition(ts=t.ts, on=t.on) for t in transitions]
    return HumidifierHistory(range=range, points=points)
