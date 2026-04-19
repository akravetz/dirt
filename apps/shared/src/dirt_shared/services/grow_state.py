"""Grow identity (germination / flower dates) and stage-derived environmental targets.

Single source of truth for "what stage is the grow in right now" and "what
temp/RH/VPD should we target at this stage". Consumed by the voice status
tool (sensors.py) and — soon — the VPD-targeting humidifier loop.

Stage bands are hardcoded domain knowledge rather than DB rows: they change
rarely and via code review, not a UI toggle. See commit history for the
sources that informed the numbers (converging cannabis cultivation guidance,
Apr 2026).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.config import GROW_START
from dirt.db import engine
from dirt.models.grow_state import GrowState

Stage = Literal["veg", "flower_early", "flower_late"]

# Early flower covers weeks 1-3 of 12/12 (days 0-20); late flower begins day 21.
_LATE_FLOWER_DAY = 21

# Stage → metric → (low, high) target band. Metric names match MetricReading
# so sensors.py can key by metric name directly.
STAGE_TARGETS: dict[Stage, dict[str, tuple[float, float]]] = {
    "veg": {
        "temperature_f": (70, 82),
        "humidity_pct": (45, 55),
        "vpd_kpa": (0.8, 1.2),
    },
    "flower_early": {
        "temperature_f": (68, 80),
        "humidity_pct": (45, 50),
        "vpd_kpa": (1.0, 1.3),
    },
    "flower_late": {
        "temperature_f": (65, 78),
        "humidity_pct": (40, 45),
        "vpd_kpa": (1.2, 1.5),
    },
}


async def get_state() -> GrowState:
    """Read the singleton. Returns a transient default if the row is missing.

    The transient fallback keeps tool callsites robust against an un-seeded
    DB (fresh dev env, test without explicit seed). init_db() writes the
    real row on app startup so production reads always see it.
    """
    async with AsyncSession(engine) as session:
        state = await session.get(GrowState, 1)
        return state or GrowState(id=1, germination_date=GROW_START)


async def current_stage(today: date | None = None) -> Stage:
    """Veg vs early vs late flower, derived from flower_start_date."""
    today = today or date.today()
    state = await get_state()
    if state.flower_start_date is None or today < state.flower_start_date:
        return "veg"
    days_in_flower = (today - state.flower_start_date).days
    if days_in_flower < _LATE_FLOWER_DAY:
        return "flower_early"
    return "flower_late"


async def grow_week(today: date | None = None) -> int:
    """1-indexed week since germination. Day 1-7 = week 1."""
    today = today or date.today()
    state = await get_state()
    return (today - state.germination_date).days // 7 + 1


async def current_targets() -> dict[str, tuple[float, float]]:
    """Temp / RH / VPD band for the current stage."""
    return STAGE_TARGETS[await current_stage()]
