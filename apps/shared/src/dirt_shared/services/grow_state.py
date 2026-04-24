"""Grow identity (germination / flower dates) and stage-derived environmental targets.

Single source of truth for "what stage is the grow in right now" and "what
temp/RH/VPD should we target at this stage". Consumed by the voice status
tool (sensors.py) and the VPD-targeting humidifier loop.

Stage bands are hardcoded domain knowledge rather than DB rows: they change
rarely and via code review, not a UI toggle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import GROW_START
from dirt_shared.models.grow_state import GrowState

Stage = Literal["veg", "flower_early", "flower_late"]

# Early flower covers weeks 1-3 of 12/12 (days 0-20); late flower begins day 21.
_LATE_FLOWER_DAY = 21


def tent_tz(state: GrowState) -> ZoneInfo:
    """Resolve the grow's wall-clock timezone from the row's ``timezone`` column.

    Every grow carries its own timezone (``growstate.timezone``, IANA name)
    so a future grow in a different location doesn't require a code change.
    Callers that already have a ``GrowState`` in hand should pass it; callers
    that don't should load one via ``GrowStateService.get_state()`` first.
    """
    return ZoneInfo(state.timezone)


# Stage → metric → (low, high) target band.
STAGE_TARGETS: dict[Stage, dict[str, tuple[float, float]]] = {
    "veg": {
        "temperature_f": (70, 82),
        "humidity_pct": (45, 55),
        "vpd_kpa": (0.8, 1.2),
        # Loose operational envelope — 20% is the motor's measured stall
        # floor from the protocol sweep; 80% is an anomaly ceiling, not a
        # control-loop setpoint. Same band across all stages until the
        # closed-loop VPD service lands and can inform a tighter target.
        "fan_pct": (20, 80),
    },
    "flower_early": {
        "temperature_f": (68, 80),
        "humidity_pct": (45, 50),
        "vpd_kpa": (1.0, 1.3),
        "fan_pct": (20, 80),
    },
    "flower_late": {
        "temperature_f": (65, 78),
        "humidity_pct": (40, 45),
        "vpd_kpa": (1.2, 1.5),
        "fan_pct": (20, 80),
    },
}


@dataclass(frozen=True)
class LightsState:
    on: bool
    minutes_until_off: float  # always positive; counts to next lights-off
    minutes_until_on: float  # always positive; counts to next lights-on


@dataclass(frozen=True)
class GrowCurrentPayload:
    germination_date: date
    flower_start_date: date | None
    day_number: int  # today - germination_date + 1
    grow_week_number: int  # 1-indexed since germination_date
    flower_week_number: int | None  # 1-indexed since flower_start_date; None in veg
    stage: Stage
    strain: str
    location: str
    plant_count: int
    lights: LightsState
    lights_on_local: time
    lights_off_local: time


# ============================================================
# Pure helper used by every endpoint that returns ok|warn|crit.
# ============================================================

BandStatus = Literal["ok", "warn", "crit"]


def band_status(value: float, band: tuple[float, float] | None) -> BandStatus:
    """Classify ``value`` against a target ``band=(lo, hi)``."""
    if band is None:
        return "ok"
    lo, hi = band
    if lo <= value <= hi:
        return "ok"
    half_width = (hi - lo) / 2
    if lo - half_width <= value <= hi + half_width:
        return "warn"
    return "crit"


class GrowStateService:
    """Grow-stage queries + lights schedule. Constructor-inject the engine.

    Wired into ``app.state.grow`` by ``dirt_web.app.create_app``;
    resolved by ``get_grow`` provider in ``dirt_web.deps``.

    The clock is constructor-injected and threads through every method's
    "what time is it now" reads. Composition roots wire one shared clock
    (see ``app_wiring.build_core_services``); tests pass a frozen clock
    for deterministic stage / week / lights-state assertions.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def today(self) -> date:
        """The grow's current date in the grow's wall-clock timezone."""
        state = await self.get_state()
        return self._clock().astimezone(tent_tz(state)).date()

    async def get_state(self) -> GrowState:
        """Return the current grow (``is_current = true``)."""
        async with AsyncSession(self._engine) as session:
            result = await session.exec(
                select(GrowState).where(GrowState.is_current.is_(True)).limit(1)
            )
            state = result.first()
            return state or GrowState(germination_date=GROW_START, is_current=True)

    async def current_stage(self) -> Stage:
        """Veg vs early vs late flower, derived from flower_start_date."""
        state = await self.get_state()
        today = self._clock().astimezone(tent_tz(state)).date()
        if state.flower_start_date is None or today < state.flower_start_date:
            return "veg"
        days_in_flower = (today - state.flower_start_date).days
        if days_in_flower < _LATE_FLOWER_DAY:
            return "flower_early"
        return "flower_late"

    async def grow_week(self) -> int:
        """1-indexed week since germination. Day 1-7 = week 1."""
        state = await self.get_state()
        today = self._clock().astimezone(tent_tz(state)).date()
        return (today - state.germination_date).days // 7 + 1

    async def current_targets(self) -> dict[str, tuple[float, float]]:
        """Temp / RH / VPD band for the current stage."""
        return STAGE_TARGETS[await self.current_stage()]

    async def lights_state(self) -> LightsState:
        """Are lights on right now, and how long until the next on/off transition?"""
        state = await self.get_state()
        tz = tent_tz(state)
        now_local = self._clock().astimezone(tz)
        on_time = state.lights_on_local
        off_time = state.lights_off_local

        now_t = now_local.time()
        if on_time < off_time:
            on = on_time <= now_t < off_time
        else:
            # Lights-on crosses midnight (handled but not the current schedule).
            on = now_t >= on_time or now_t < off_time

        # Always-positive countdown to the NEXT lights-off.
        off_dt = datetime.combine(now_local.date(), off_time, tzinfo=tz)
        if off_dt <= now_local:
            off_dt = datetime.combine(
                now_local.date() + timedelta(days=1),
                off_time,
                tzinfo=tz,
            )
        minutes_until_off = (off_dt - now_local).total_seconds() / 60.0

        # Always-positive countdown to the NEXT lights-on.
        on_dt = datetime.combine(now_local.date(), on_time, tzinfo=tz)
        if on_dt <= now_local:
            on_dt = datetime.combine(
                now_local.date() + timedelta(days=1),
                on_time,
                tzinfo=tz,
            )
        minutes_until_on = (on_dt - now_local).total_seconds() / 60.0

        return LightsState(
            on=on,
            minutes_until_off=minutes_until_off,
            minutes_until_on=minutes_until_on,
        )

    async def get_grow_current_payload(self) -> GrowCurrentPayload:
        """One-shot assembler for ``GET /api/grow/current``."""
        state = await self.get_state()
        today = self._clock().astimezone(tent_tz(state)).date()

        if state.flower_start_date is None or today < state.flower_start_date:
            stage: Stage = "veg"
        else:
            days_in_flower = (today - state.flower_start_date).days
            stage = (
                "flower_early" if days_in_flower < _LATE_FLOWER_DAY else "flower_late"
            )

        grow_week_number = (today - state.germination_date).days // 7 + 1
        day_number = (today - state.germination_date).days + 1
        if state.flower_start_date is not None and today >= state.flower_start_date:
            flower_week_number: int | None = (
                today - state.flower_start_date
            ).days // 7 + 1
        else:
            flower_week_number = None
        lights = await self.lights_state()

        return GrowCurrentPayload(
            germination_date=state.germination_date,
            flower_start_date=state.flower_start_date,
            day_number=day_number,
            grow_week_number=grow_week_number,
            flower_week_number=flower_week_number,
            stage=stage,
            strain=state.strain,
            location=state.location,
            plant_count=state.plant_count,
            lights=lights,
            lights_on_local=state.lights_on_local,
            lights_off_local=state.lights_off_local,
        )
