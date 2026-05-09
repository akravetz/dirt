"""Grow identity (germination / flower dates) and stage-derived environmental targets.

Single source of truth for "what stage is the scoped grow run in right now"
and "what temp/RH/VPD should we target at this stage". Consumed by the voice
status tool (sensors.py) and the VPD-targeting humidifier loop.

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
from dirt_shared.models.grow_run import GrowRun
from dirt_shared.models.schedule import Schedule
from dirt_shared.services.scope import (
    DEFAULT_SITE_ID,
    DEFAULT_TENT_ID,
    current_grow_run,
    resolve_scope,
)

Stage = Literal["veg", "flower_early", "flower_late"]

# Early flower covers weeks 1-3 of 12/12 (days 0-20); late flower begins day 21.
_LATE_FLOWER_DAY = 21


def tent_tz(state: GrowRun) -> ZoneInfo:
    """Resolve the grow's wall-clock timezone from the row's ``timezone`` column.

    Every grow carries its own timezone (``growrun.timezone``, IANA name)
    so a future grow in a different location doesn't require a code change.
    Callers that already have a ``GrowRun`` in hand should pass it; callers
    that don't should load one via ``GrowStateService.get_state()`` first.
    """
    return ZoneInfo(state.timezone)


# Stage → metric → (low, high) target band.
#
# Semantics by metric:
#
#   temperature_f, vpd_kpa  — primary targets. Controller setpoints; what we're
#                              actively trying to hold the tent at.
#
#   humidity_pct            — *envelope*, not a setpoint. RH and VPD are
#                              mathematically coupled at constant T (RH = 1 - VPD/SVP),
#                              so an RH "target" duplicating the VPD target is
#                              a bug. Instead, the RH band is a horticultural
#                              envelope: the lower edge protects against
#                              defensive stomatal closure (too dry); the upper
#                              edge is the mold/bud-rot threshold for the
#                              stage. The bands intentionally span more than the
#                              VPD target's RH-equivalent range so envelope
#                              guards (e.g. humidifier PI ceiling) only fire on
#                              real envelope violations, not on every VPD-in-band
#                              sample. See wiki/concepts/control-theory-primer.md
#                              §13 and wiki/concepts/vpd.md.
#
#   fan_pct                 — operational envelope, not a setpoint. The fan
#                              firmware (firmware/fan_controller/src/main.cpp:
#                              fan_speed_to_wire_duty) abstracts the motor's
#                              22% wire-duty stall threshold internally: API
#                              speed_pct=0 is off, speed_pct=1..100 maps
#                              linearly onto the full running range. So the
#                              band here is a free policy choice — currently
#                              "fairly slow but running" (20%) up to a
#                              "suspicious if sustained" ceiling (80%). Same
#                              across all stages until closed-loop fan control
#                              lands and per-stage targets become meaningful.
STAGE_TARGETS: dict[Stage, dict[str, tuple[float, float]]] = {
    "veg": {
        "temperature_f": (70, 82),
        "humidity_pct": (40, 70),  # envelope: <40 stomata close, >70 mold risk
        "vpd_kpa": (0.9, 1.1),
        "fan_pct": (20, 80),
    },
    "flower_early": {
        "temperature_f": (68, 80),
        "humidity_pct": (40, 60),  # envelope: bud rot risk climbs above 60 in flower
        "vpd_kpa": (1.0, 1.3),
        "fan_pct": (20, 80),
    },
    "flower_late": {
        "temperature_f": (65, 78),
        "humidity_pct": (35, 55),  # envelope: bud rot is the dominant late-flower risk
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
class GrowContext:
    """Snapshot of stage + lights + target bands from one ``get_state()`` fetch.

    Callers in hot paths (control loops ticking every ~30s) should prefer
    ``GrowStateService.current_context()`` over separate ``current_stage()``/
    ``lights_state()``/``current_targets()`` calls, which each round-trip to the
    DB for the same row.
    """

    stage: Stage
    lights: LightsState
    targets: dict[str, tuple[float, float]]


@dataclass(frozen=True)
class GrowCurrentPayload:
    germination_date: date
    flower_start_date: date | None
    day_number: int  # today - germination_date + 1
    grow_week_number: int  # 1-indexed since germination_date
    flower_week_number: int | None  # 1-indexed since flower_start_date; None in veg
    stage: Stage
    strain: str
    plant_count: int
    lights: LightsState
    lights_on_local: time
    lights_off_local: time


@dataclass(frozen=True)
class LightSchedule:
    site_id: str
    tent_id: str
    starts_local: time
    ends_local: time
    timezone: str
    enabled: bool
    source: str


def derive_lights_from_times(
    on_time: time,
    off_time: time,
    now_local: datetime,
) -> LightsState:
    """Derive current light state and next transitions from a local time window."""
    tz = now_local.tzinfo
    now_t = now_local.time()
    if on_time < off_time:
        on = on_time <= now_t < off_time
    else:
        # Lights-on crosses midnight.
        on = now_t >= on_time or now_t < off_time

    off_dt = datetime.combine(now_local.date(), off_time, tzinfo=tz)
    if off_dt <= now_local:
        off_dt = datetime.combine(
            now_local.date() + timedelta(days=1), off_time, tzinfo=tz
        )
    minutes_until_off = (off_dt - now_local).total_seconds() / 60.0

    on_dt = datetime.combine(now_local.date(), on_time, tzinfo=tz)
    if on_dt <= now_local:
        on_dt = datetime.combine(
            now_local.date() + timedelta(days=1), on_time, tzinfo=tz
        )
    minutes_until_on = (on_dt - now_local).total_seconds() / 60.0

    return LightsState(
        on=on,
        minutes_until_off=minutes_until_off,
        minutes_until_on=minutes_until_on,
    )


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


def in_band(value: float, band: tuple[float, float] | None) -> bool:
    """True iff ``value`` is inside ``band=(lo, hi)`` (inclusive endpoints).

    ``band=None`` means "no target defined" → always in-band (vacuously true)."""
    if band is None:
        return True
    lo, hi = band
    return lo <= value <= hi


def above_band(value: float, band: tuple[float, float] | None) -> bool:
    """True iff ``value`` is strictly above the band's upper edge.

    The one-sided comparison used by envelope guards — e.g. the humidifier
    PI controller's RH ceiling: "stop adding moisture if RH walked above
    the stage's mold-prevention upper edge regardless of what VPD says."
    ``band=None`` → never above (no envelope defined)."""
    if band is None:
        return False
    return value > band[1]


def below_band(value: float, band: tuple[float, float] | None) -> bool:
    """True iff ``value`` is strictly below the band's lower edge.

    Symmetric counterpart to ``above_band`` — used by future dehumidifier
    guards / floor-only comparisons. ``band=None`` → never below."""
    if band is None:
        return False
    return value < band[0]


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

    async def today(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> date:
        """The grow's current date in the grow's wall-clock timezone."""
        state = await self.get_state(site_id=site_id, tent_id=tent_id)
        return self._clock().astimezone(tent_tz(state)).date()

    async def get_state(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> GrowRun:
        """Return the current scoped grow run.

        The method name remains for API compatibility, but the source of truth
        is now ``growrun`` scoped by public ``site_id``/``tent_id``.
        """
        async with AsyncSession(self._engine) as session:
            state = await current_grow_run(session, site_id=site_id, tent_id=tent_id)
            return state or _fallback_grow_run(site_id=site_id, tent_id=tent_id)

    async def current_grow_run(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> GrowRun | None:
        """Return the current grow run for an explicit site/tent scope."""
        async with AsyncSession(self._engine) as session:
            return await current_grow_run(session, site_id=site_id, tent_id=tent_id)

    @staticmethod
    def _derive_stage(state: GrowRun, today: date) -> Stage:
        if state.flower_start_date is None or today < state.flower_start_date:
            return "veg"
        days_in_flower = (today - state.flower_start_date).days
        if days_in_flower < _LATE_FLOWER_DAY:
            return "flower_early"
        return "flower_late"

    @staticmethod
    def _derive_lights_from_times(
        on_time: time,
        off_time: time,
        now_local: datetime,
    ) -> LightsState:
        return derive_lights_from_times(on_time, off_time, now_local)

    @staticmethod
    def _lights_on_duration_seconds(on_time: time, off_time: time) -> float:
        on_seconds = (
            on_time.hour * 60 * 60
            + on_time.minute * 60
            + on_time.second
            + on_time.microsecond / 1_000_000
        )
        off_seconds = (
            off_time.hour * 60 * 60
            + off_time.minute * 60
            + off_time.second
            + off_time.microsecond / 1_000_000
        )
        return (off_seconds - on_seconds) % (24 * 60 * 60)

    async def current_stage(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> Stage:
        """Veg vs early vs late flower, derived from flower_start_date."""
        state = await self.get_state(site_id=site_id, tent_id=tent_id)
        today = self._clock().astimezone(tent_tz(state)).date()
        return self._derive_stage(state, today)

    async def grow_week(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> int:
        """1-indexed week since germination. Day 1-7 = week 1."""
        state = await self.get_state(site_id=site_id, tent_id=tent_id)
        today = self._clock().astimezone(tent_tz(state)).date()
        return (today - _germination_date(state)).days // 7 + 1

    async def current_targets(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> dict[str, tuple[float, float]]:
        """Temp / RH / VPD band for the current stage."""
        return STAGE_TARGETS[await self.current_stage(site_id=site_id, tent_id=tent_id)]

    async def lights_state(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> LightsState:
        """Are lights on right now, and how long until the next on/off transition?"""
        schedule = await self.current_light_schedule(site_id=site_id, tent_id=tent_id)
        now_local = self._clock().astimezone(ZoneInfo(schedule.timezone))
        return self._derive_lights_from_times(
            schedule.starts_local,
            schedule.ends_local,
            now_local,
        )

    async def current_context(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> GrowContext:
        """Stage + lights + target bands from one ``get_state()`` fetch.

        Hot-path helper for control loops — avoids three DB round-trips per tick.
        """
        state = await self.get_state(site_id=site_id, tent_id=tent_id)
        schedule = await self.current_light_schedule(site_id=site_id, tent_id=tent_id)
        now_local = self._clock().astimezone(ZoneInfo(schedule.timezone))
        stage = self._derive_stage(state, now_local.date())
        lights = self._derive_lights_from_times(
            schedule.starts_local,
            schedule.ends_local,
            now_local,
        )
        return GrowContext(stage=stage, lights=lights, targets=STAGE_TARGETS[stage])

    async def current_light_schedule(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> LightSchedule:
        """Return the scoped lights schedule, projected from ``schedule``."""
        state = await self.get_state(site_id=site_id, tent_id=tent_id)
        async with AsyncSession(self._engine) as session:
            scope = await resolve_scope(session, site_id=site_id, tent_id=tent_id)
            if scope is not None:
                schedule = (
                    await session.exec(
                        select(Schedule)
                        .where(Schedule.site_id == scope.site_pk)
                        .where(Schedule.tent_id == scope.tent_pk)
                        .where(Schedule.kind == "lights")
                        .where(Schedule.enabled.is_(True))
                        .order_by(Schedule.id.desc())
                        .limit(1)
                    )
                ).first()
                if (
                    schedule is not None
                    and schedule.starts_local is not None
                    and schedule.ends_local is not None
                ):
                    return LightSchedule(
                        site_id=site_id,
                        tent_id=tent_id,
                        starts_local=schedule.starts_local,
                        ends_local=schedule.ends_local,
                        timezone=schedule.timezone,
                        enabled=schedule.enabled,
                        source="schedule",
                    )
        return LightSchedule(
            site_id=site_id,
            tent_id=tent_id,
            starts_local=time(5, 0),
            ends_local=time(23, 0),
            timezone=state.timezone,
            enabled=True,
            source="default",
        )

    async def get_grow_current_payload(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> GrowCurrentPayload:
        """One-shot assembler for ``GET /api/grow/current``."""
        state = await self.get_state(site_id=site_id, tent_id=tent_id)
        schedule = await self.current_light_schedule(site_id=site_id, tent_id=tent_id)
        now_local = self._clock().astimezone(ZoneInfo(schedule.timezone))
        today = now_local.date()

        stage = self._derive_stage(state, today)
        lights = self._derive_lights_from_times(
            schedule.starts_local,
            schedule.ends_local,
            now_local,
        )

        germination_date = _germination_date(state)
        grow_week_number = (today - germination_date).days // 7 + 1
        day_number = (today - germination_date).days + 1
        if state.flower_start_date is not None and today >= state.flower_start_date:
            flower_week_number: int | None = (
                today - state.flower_start_date
            ).days // 7 + 1
        else:
            flower_week_number = None

        return GrowCurrentPayload(
            germination_date=germination_date,
            flower_start_date=state.flower_start_date,
            day_number=day_number,
            grow_week_number=grow_week_number,
            flower_week_number=flower_week_number,
            stage=stage,
            strain=state.strain or "Sirius Black × BS01",
            plant_count=state.plant_count,
            lights=lights,
            lights_on_local=schedule.starts_local,
            lights_off_local=schedule.ends_local,
        )

    async def flip_to_flower(
        self,
        *,
        flower_start_date: date,
        lights_on_local: time,
        lights_off_local: time,
    ) -> GrowCurrentPayload:
        """Persist the current grow's first flower day and 12/12 light schedule."""
        if (
            self._lights_on_duration_seconds(lights_on_local, lights_off_local)
            != 12 * 60 * 60
        ):
            raise ValueError("flower light schedule must be exactly 12 hours on")

        async with AsyncSession(self._engine) as session:
            scope = await resolve_scope(
                session, site_id=DEFAULT_SITE_ID, tent_id=DEFAULT_TENT_ID
            )
            if scope is None:
                raise ValueError("default site/tent scope is missing")

            state = await current_grow_run(session)
            if state is None:
                state = GrowRun(
                    site_id=scope.site_pk,
                    tent_id=scope.tent_pk,
                    grow_run_id=f"{scope.tent_id}-{GROW_START.isoformat()}",
                    name="Main grow 2026-03-15",
                    purpose="flower",
                    germination_date=GROW_START,
                    strain="Sirius Black × BS01",
                    plant_count=4,
                    is_current=True,
                )

            if flower_start_date < _germination_date(state):
                raise ValueError("flower_start_date cannot be before germination_date")

            if (
                state.flower_start_date is not None
                and state.flower_start_date != flower_start_date
            ):
                raise ValueError("flower_start_date is already set")

            state.flower_start_date = flower_start_date
            session.add(state)
            schedule = (
                await session.exec(
                    select(Schedule)
                    .where(Schedule.site_id == scope.site_pk)
                    .where(Schedule.tent_id == scope.tent_pk)
                    .where(Schedule.kind == "lights")
                    .limit(1)
                )
            ).first()
            if schedule is None:
                schedule = Schedule(
                    site_id=scope.site_pk,
                    tent_id=scope.tent_pk,
                    schedule_id=f"{scope.tent_id}-lights-photoperiod",
                    kind="lights",
                )
            schedule.starts_local = lights_on_local
            schedule.ends_local = lights_off_local
            schedule.timezone = state.timezone
            schedule.enabled = True
            session.add(schedule)
            await session.commit()

        return await self.get_grow_current_payload()


def _fallback_grow_run(
    *,
    site_id: str = DEFAULT_SITE_ID,
    tent_id: str = DEFAULT_TENT_ID,
) -> GrowRun:
    return GrowRun(
        site_id=0,
        tent_id=0,
        grow_run_id=f"{tent_id}-{GROW_START.isoformat()}",
        name=f"{tent_id} fallback grow",
        purpose="flower",
        germination_date=GROW_START,
        strain="Sirius Black × BS01",
        plant_count=4,
        is_current=True,
    )


def _germination_date(state: GrowRun) -> date:
    return state.germination_date or GROW_START
