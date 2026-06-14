"""Tests for current plant lifecycle context + stage-derived target lookup.

The default no-argument service path resolves to ``homebox/main``. Current
plant rows are selected through ``plant_location_history.end_at IS NULL`` so a
breeding-tent plant set can exist without changing the main dashboard.

Each test uses the shared ``pg_engine`` fixture, which yields an engine
pointing at a fresh per-test Postgres clone (the template already has
the singleton row seeded). Helpers below mutate that seeded row.

Determinism: the clock is constructor-injected on ``GrowStateService``,
so tests build the service with a frozen UTC datetime via the ``_svc``
helper instead of patching the datetime module.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import GROW_START
from dirt_shared.models.plant import Plant, PlantLocationHistory
from dirt_shared.models.schedule import Schedule
from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent
from dirt_shared.services import grow_state as gs
from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.scope import resolve_scope

# Tests seed the default `America/Denver` timezone row; use the same IANA
# zone locally when assembling a MDT wall-clock UTC instant.
_TEST_TZ = ZoneInfo("America/Denver")


def _svc(
    engine: AsyncEngine,
    *,
    today: date | None = None,
    now_utc: datetime | None = None,
) -> GrowStateService:
    """Construct a GrowStateService with a frozen clock.

    Pass ``today`` for date-only tests (anchored at noon MDT so the UTC
    conversion lands on the same calendar day) or ``now_utc`` directly
    for lights-state tests that need a specific UTC timestamp.
    """
    if now_utc is None:
        if today is None:
            now_utc = datetime.now(UTC)
        else:
            # noon MDT → unambiguous calendar-day for grow_state.today()
            now_local = datetime.combine(today, time(12, 0), tzinfo=_TEST_TZ)
            now_utc = now_local.astimezone(UTC)
    frozen = now_utc
    return GrowStateService(engine, clock=lambda: frozen)


async def _set_state(engine, *, germination: date, flower: date | None = None) -> None:
    """Overwrite current main plant lifecycle dates with the given dates."""
    async with AsyncSession(engine) as session:
        scope = await resolve_scope(session)
        assert scope is not None
        plants = (
            await session.exec(
                select(Plant)
                .join(PlantLocationHistory, PlantLocationHistory.plant_id == Plant.id)
                .where(PlantLocationHistory.site_id == scope.site_pk)
                .where(PlantLocationHistory.tent_id == scope.tent_pk)
                .where(PlantLocationHistory.end_at.is_(None))
            )
        ).all()
        for plant in plants:
            plant.germinated_at = _local_midnight(germination)
            plant.flower_started_at = (
                None if flower is None else _local_midnight(flower)
            )
            session.add(plant)
        await session.commit()


async def _set_lights(engine, on: time, off: time) -> None:
    async with AsyncSession(engine) as session:
        scope = await resolve_scope(session)
        assert scope is not None
        schedule = (
            await session.exec(
                select(Schedule)
                .where(Schedule.site_id == scope.site_pk)
                .where(Schedule.tent_id == scope.tent_pk)
                .where(Schedule.kind == "lights")
                .limit(1)
            )
        ).first()
        assert schedule is not None
        schedule.starts_local = on
        schedule.ends_local = off
        session.add(schedule)
        await session.commit()


async def _clear_state(engine) -> None:
    """Close main current plant locations to exercise fallback behavior."""
    async with AsyncSession(engine) as session:
        scope = await resolve_scope(session)
        assert scope is not None
        rows = (
            await session.exec(
                select(PlantLocationHistory)
                .where(PlantLocationHistory.site_id == scope.site_pk)
                .where(PlantLocationHistory.tent_id == scope.tent_pk)
                .where(PlantLocationHistory.end_at.is_(None))
            )
        ).all()
        for row in rows:
            row.end_at = datetime(2030, 1, 1, tzinfo=UTC)
            session.add(row)
        await session.commit()


def _local_midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=_TEST_TZ)


async def _site_tent_ids(engine, tent_id: str) -> tuple[int, int]:
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(Site.id, Tent.id)
            .join(Tent, Tent.site_id == Site.id)
            .where(Site.site_id == "homebox")
            .where(Tent.tent_id == tent_id)
        )
        row = result.one()
        return row


# ------- current_stage -------


async def test_stage_veg_when_flower_start_is_none(pg_engine):
    await _set_state(pg_engine, germination=date(2026, 3, 15))
    assert await _svc(pg_engine, today=date(2026, 4, 18)).current_stage() == "veg"


async def test_stage_veg_when_flower_start_in_future(pg_engine):
    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=date(2026, 5, 1))
    assert await _svc(pg_engine, today=date(2026, 4, 18)).current_stage() == "veg"


async def test_stage_early_flower_day_zero(pg_engine):
    flower = date(2026, 4, 18)
    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=flower)
    assert await _svc(pg_engine, today=flower).current_stage() == "flower_early"


async def test_stage_early_flower_day_20(pg_engine):
    flower = date(2026, 4, 1)
    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=flower)
    # Day 20 = still early (21 is the crossover)
    svc = _svc(pg_engine, today=date(2026, 4, 21))
    assert await svc.current_stage() == "flower_early"


async def test_stage_late_flower_day_21(pg_engine):
    flower = date(2026, 4, 1)
    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=flower)
    svc = _svc(pg_engine, today=date(2026, 4, 22))
    assert await svc.current_stage() == "flower_late"


# ------- grow_week -------


async def test_grow_week_day_one_is_week_one(pg_engine):
    await _set_state(pg_engine, germination=date(2026, 3, 15))
    assert await _svc(pg_engine, today=date(2026, 3, 15)).grow_week() == 1


async def test_grow_week_day_seven_is_week_one(pg_engine):
    await _set_state(pg_engine, germination=date(2026, 3, 15))
    assert await _svc(pg_engine, today=date(2026, 3, 21)).grow_week() == 1


async def test_grow_week_day_eight_is_week_two(pg_engine):
    await _set_state(pg_engine, germination=date(2026, 3, 15))
    assert await _svc(pg_engine, today=date(2026, 3, 22)).grow_week() == 2


# ------- current_targets -------


async def test_current_targets_tracks_stage(pg_engine):
    # Freeze "today" so the stage derivation is deterministic regardless
    # of when the suite runs — without this, a day-21+ wall clock would
    # push the second assertion into flower_late.
    await _set_state(pg_engine, germination=date(2026, 3, 15))
    veg = await _svc(pg_engine, today=date(2026, 3, 20)).current_targets()
    assert veg == gs.STAGE_TARGETS["veg"]

    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=date(2026, 4, 1))
    early = await _svc(pg_engine, today=date(2026, 4, 10)).current_targets()
    assert early == gs.STAGE_TARGETS["flower_early"]


def test_stage_targets_cover_all_stages_and_metrics():
    """Every stage must carry a full band for every dashboard metric."""
    expected = {"temperature_f", "humidity_pct", "vpd_kpa", "fan_pct"}
    for stage, bands in gs.STAGE_TARGETS.items():
        assert set(bands) == expected, f"{stage} missing metrics"
        for metric, (lo, hi) in bands.items():
            assert lo < hi, f"{stage}.{metric} has inverted band"


# ------- transient fallback -------


async def test_get_tent_context_returns_default_when_current_locations_missing(
    pg_engine,
):
    await _clear_state(pg_engine)
    context = await GrowStateService(pg_engine).get_tent_context()
    assert context.germination_date == GROW_START
    assert context.flower_start_date is None
    assert context.plant_count == 0


async def test_current_plant_context_is_scoped_per_tent(pg_engine):
    main_site_id, main_tent_id = await _site_tent_ids(pg_engine, "main")
    breeding_site_id, breeding_tent_id = await _site_tent_ids(pg_engine, "breeding")

    async with AsyncSession(pg_engine) as session:
        for tent_id, germination, flower in (
            ("main", date(2026, 3, 15), date(2026, 5, 3)),
            ("breeding", date(2026, 5, 4), None),
        ):
            scope = await resolve_scope(session, tent_id=tent_id)
            assert scope is not None
            plants = (
                await session.exec(
                    select(Plant)
                    .join(
                        PlantLocationHistory,
                        PlantLocationHistory.plant_id == Plant.id,
                    )
                    .where(PlantLocationHistory.site_id == scope.site_pk)
                    .where(PlantLocationHistory.tent_id == scope.tent_pk)
                    .where(PlantLocationHistory.end_at.is_(None))
                )
            ).all()
            for plant in plants:
                plant.germinated_at = _local_midnight(germination)
                plant.flower_started_at = (
                    None if flower is None else _local_midnight(flower)
                )
                session.add(plant)
        await session.commit()

    svc = _svc(pg_engine, today=date(2026, 5, 4))
    default_payload = await svc.get_grow_current_payload()
    breeding = await svc.get_tent_context(tent_id="breeding")

    assert main_site_id == breeding_site_id
    assert main_tent_id != breeding_tent_id
    assert default_payload.flower_start_date == date(2026, 5, 3)
    assert default_payload.stage == "flower_early"
    assert breeding.germination_date == date(2026, 5, 4)
    assert breeding.plant_count == 5
    assert await svc.current_stage(tent_id="breeding") == "veg"


# ------- lights_state (feedforward inputs for the humidifier loop) -------


def _utc(y: int, mo: int, d: int, h: int, mi: int = 0) -> datetime:
    # 12:00 MDT == 18:00 UTC; build the UTC equivalent for a MDT wall-clock time.
    local = datetime(y, mo, d, h, mi, tzinfo=_TEST_TZ)
    return local.astimezone(UTC)


async def test_lights_on_midday(pg_engine):
    await _set_lights(pg_engine, time(5, 0), time(23, 0))
    state = await _svc(pg_engine, now_utc=_utc(2026, 4, 19, 14, 0)).lights_state()
    assert state.on is True
    assert state.minutes_until_off == pytest.approx(9 * 60, abs=0.1)


async def test_lights_off_after_schedule(pg_engine):
    await _set_lights(pg_engine, time(5, 0), time(23, 0))
    state = await _svc(pg_engine, now_utc=_utc(2026, 4, 20, 2, 0)).lights_state()
    assert state.on is False


async def test_lights_off_before_schedule(pg_engine):
    await _set_lights(pg_engine, time(5, 0), time(23, 0))
    state = await _svc(pg_engine, now_utc=_utc(2026, 4, 19, 4, 30)).lights_state()
    assert state.on is False


async def test_prep_window_boundary(pg_engine):
    """22:35 MDT — 25 min before 23:00 lights-off, inside a 30-min prep."""
    await _set_lights(pg_engine, time(5, 0), time(23, 0))
    state = await _svc(pg_engine, now_utc=_utc(2026, 4, 19, 22, 35)).lights_state()
    assert state.on is True
    assert state.minutes_until_off == pytest.approx(25, abs=0.1)


async def test_flower_schedule_overridable_via_db(pg_engine):
    """Flipping lights_on to 11:00 (flower 12/12) takes effect on next read."""
    await _set_lights(pg_engine, time(11, 0), time(23, 0))
    # 10:00 MDT — lights should still be OFF (before the 11:00 flower on-time).
    state = await _svc(pg_engine, now_utc=_utc(2026, 4, 19, 10, 0)).lights_state()
    assert state.on is False


async def test_current_light_schedule_is_scoped_projection(pg_engine):
    await _set_lights(pg_engine, time(9, 0), time(21, 0))

    schedule = await GrowStateService(pg_engine).current_light_schedule()

    assert schedule.site_id == "homebox"
    assert schedule.tent_id == "main"
    assert schedule.starts_local == time(9, 0)
    assert schedule.ends_local == time(21, 0)
    assert schedule.source == "schedule"


async def test_flip_to_flower_sets_date_and_12_12_schedule(pg_engine):
    await _set_state(pg_engine, germination=date(2026, 3, 15))
    svc = _svc(pg_engine, today=date(2026, 5, 3))

    payload = await svc.flip_to_flower(
        flower_start_date=date(2026, 5, 3),
        lights_on_local=time(9, 0),
        lights_off_local=time(21, 0),
    )

    assert payload.flower_start_date == date(2026, 5, 3)
    assert payload.flower_week_number == 1
    assert payload.stage == "flower_early"
    assert payload.lights_on_local == time(9, 0)
    assert payload.lights_off_local == time(21, 0)


async def test_flip_to_flower_rejects_non_12_12_schedule(pg_engine):
    await _set_state(pg_engine, germination=date(2026, 3, 15))

    with pytest.raises(ValueError, match="exactly 12 hours"):
        await _svc(pg_engine, today=date(2026, 5, 3)).flip_to_flower(
            flower_start_date=date(2026, 5, 3),
            lights_on_local=time(9, 0),
            lights_off_local=time(22, 0),
        )

    context = await GrowStateService(pg_engine).get_tent_context()
    assert context.flower_start_date is None
    schedule = await GrowStateService(pg_engine).current_light_schedule()
    assert schedule.starts_local == time(9, 0)
    assert schedule.ends_local == time(21, 0)


# ------- get_grow_current_payload -------


async def test_payload_in_veg_has_null_flower_week(pg_engine):
    await _set_state(pg_engine, germination=date(2026, 3, 15))
    payload = await _svc(pg_engine, today=date(2026, 4, 18)).get_grow_current_payload()
    assert payload.day_number == 35
    assert payload.grow_week_number == 5
    assert payload.flower_week_number is None
    assert payload.stage == "veg"


async def test_payload_with_future_flower_date_still_in_veg(pg_engine):
    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=date(2026, 5, 1))
    payload = await _svc(pg_engine, today=date(2026, 4, 18)).get_grow_current_payload()
    assert payload.flower_week_number is None
    assert payload.stage == "veg"


async def test_payload_on_flower_day_zero_is_week_one(pg_engine):
    flower = date(2026, 4, 18)
    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=flower)
    payload = await _svc(pg_engine, today=flower).get_grow_current_payload()
    assert payload.flower_week_number == 1
    assert payload.stage == "flower_early"


async def test_payload_on_flower_day_seven_is_still_week_one(pg_engine):
    flower = date(2026, 4, 1)
    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=flower)
    payload = await _svc(pg_engine, today=date(2026, 4, 7)).get_grow_current_payload()
    assert payload.flower_week_number == 1


async def test_payload_on_flower_day_eight_is_week_two(pg_engine):
    flower = date(2026, 4, 1)
    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=flower)
    payload = await _svc(pg_engine, today=date(2026, 4, 9)).get_grow_current_payload()
    assert payload.flower_week_number == 2


# ------- init_db is no longer a DDL entrypoint (ADR-006) -------
# The old test_init_db_* tests are intentionally dropped:
#   - init_db now only runs `SELECT 1` (Atlas owns DDL).
#   - seeding of the current grow row lives in the initial Atlas migration,
#     not in init_db. The pg_engine fixture's template already has it.
