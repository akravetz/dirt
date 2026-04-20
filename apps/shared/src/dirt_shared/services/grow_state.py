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

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import GROW_START
from dirt_shared.db import engine
from dirt_shared.models.grow_state import GrowState

Stage = Literal["veg", "flower_early", "flower_late"]

# Early flower covers weeks 1-3 of 12/12 (days 0-20); late flower begins day 21.
_LATE_FLOWER_DAY = 21

# Tent clock for lights schedule. Kept here (not DB) because it's a physical
# property of the grow space's location, not a per-grow decision.
TENT_TZ = ZoneInfo("America/Denver")

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
    """Return the current grow (``is_current = true``).

    The partial unique index in the schema enforces "at most one"; the
    initial Atlas migration seeds exactly one. A transient default
    (germination_date from config.GROW_START) is returned if nothing is
    found, so tool callsites stay robust against an un-seeded DB (fresh
    dev env, test without seed).
    """
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(GrowState).where(GrowState.is_current.is_(True)).limit(1)
        )
        state = result.first()
        return state or GrowState(germination_date=GROW_START, is_current=True)


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


@dataclass(frozen=True)
class LightsState:
    on: bool
    # Minutes until the next scheduled lights-off event (always positive,
    # measured from `now`). When lights are off, counts down to the *next*
    # lights-off (i.e. tomorrow's), so this field is primarily useful while
    # lights are on — callers should guard with `state.on`.
    minutes_until_off: float


async def lights_state(now_utc: datetime | None = None) -> LightsState:
    """Are lights on right now, and how long until the next lights-off?

    Reads `lights_on_local` / `lights_off_local` from the `growstate`
    singleton so the schedule is user-editable without a code deploy
    (future UI; for now `psql -U dirt -d dirt -c "UPDATE growstate SET ..."`).
    """
    now_utc = now_utc or datetime.now(UTC)
    now_local = now_utc.astimezone(TENT_TZ)
    state = await get_state()
    on_time = state.lights_on_local
    off_time = state.lights_off_local

    now_t = now_local.time()
    if on_time < off_time:
        on = on_time <= now_t < off_time
    else:
        # Lights-on crosses midnight (not our current schedule, but handled).
        on = now_t >= on_time or now_t < off_time

    off_dt = datetime.combine(now_local.date(), off_time, tzinfo=TENT_TZ)
    if off_dt <= now_local:
        next_day = now_local.date() + timedelta(days=1)
        off_dt = datetime.combine(next_day, off_time, tzinfo=TENT_TZ)
    minutes_until_off = (off_dt - now_local).total_seconds() / 60.0

    return LightsState(on=on, minutes_until_off=minutes_until_off)


# ============================================================
# Shared band-status helper — used by every endpoint that returns
# an "ok | warn | crit" classification against a target band.
# ============================================================

BandStatus = Literal["ok", "warn", "crit"]


def band_status(
    value: float, band: tuple[float, float] | None
) -> BandStatus:
    """Classify ``value`` against a target ``band=(lo, hi)``.

    - ``ok``   — value within [lo, hi]
    - ``warn`` — outside the band but within half a band-width of an edge
    - ``crit`` — further out than that

    ``None`` band (no target defined for this metric, e.g. fan_pct) is
    treated as "always ok" — the UI renders those without status colouring.
    Used by ``/api/sensors/current``, ``/api/plants/{code}.moisture.status``,
    and anywhere else the API returns a status field.
    """
    if band is None:
        return "ok"
    lo, hi = band
    if lo <= value <= hi:
        return "ok"
    half_width = (hi - lo) / 2
    if lo - half_width <= value <= hi + half_width:
        return "warn"
    return "crit"


# ============================================================
# /api/grow/current composite — collects everything the endpoint needs
# into one dataclass so the endpoint layer doesn't chain 5 service calls.
# ============================================================


@dataclass(frozen=True)
class GrowCurrentPayload:
    germination_date: date
    flower_start_date: date | None
    day_number: int          # today - germination_date + 1
    week_number: int
    stage: Stage
    strain: str
    location: str
    plant_count: int
    lights: LightsState
    lights_on_local: time
    lights_off_local: time


async def get_grow_current_payload(
    today: date | None = None, now_utc: datetime | None = None
) -> GrowCurrentPayload:
    """One-shot assembler for ``GET /api/grow/current``.

    Does a single ``get_state`` read + the three derived calculations
    (stage, week, lights). ``today`` / ``now_utc`` are passed through so
    tests can pin time.
    """
    today = today or date.today()
    now_utc = now_utc or datetime.now(UTC)
    state = await get_state()

    if state.flower_start_date is None or today < state.flower_start_date:
        stage: Stage = "veg"
    else:
        days_in_flower = (today - state.flower_start_date).days
        stage = "flower_early" if days_in_flower < _LATE_FLOWER_DAY else "flower_late"

    week_number = (today - state.germination_date).days // 7 + 1
    day_number = (today - state.germination_date).days + 1
    lights = await lights_state(now_utc)

    return GrowCurrentPayload(
        germination_date=state.germination_date,
        flower_start_date=state.flower_start_date,
        day_number=day_number,
        week_number=week_number,
        stage=stage,
        strain=state.strain,
        location=state.location,
        plant_count=state.plant_count,
        lights=lights,
        lights_on_local=state.lights_on_local,
        lights_off_local=state.lights_off_local,
    )
