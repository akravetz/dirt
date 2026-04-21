"""Tests for the GrowState current-row + stage-derived target lookup.

Post-pg-cutover (ADR-006): growstate is no longer a pinned-id=1 singleton.
Instead, a partial unique index on ``is_current = true`` enforces
at-most-one-current-grow. The Atlas init migration seeds one row with
``is_current=true`` and the germination date from config.GROW_START.

Each test uses the shared ``pg_engine`` fixture, which yields an engine
pointing at a fresh per-test Postgres clone (the template already has
the singleton row seeded). Helpers below mutate that seeded row.

Determinism: the clock is constructor-injected on ``GrowStateService``,
so tests build the service with a frozen UTC datetime via the ``_svc``
helper instead of patching the datetime module.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import GROW_START
from dirt_shared.models.grow_state import GrowState
from dirt_shared.services import grow_state as gs
from dirt_shared.services.grow_state import GrowStateService


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
            now_local = datetime.combine(today, time(12, 0), tzinfo=gs.TENT_TZ)
            now_utc = now_local.astimezone(UTC)
    frozen = now_utc
    return GrowStateService(engine, clock=lambda: frozen)


async def _set_state(engine, *, germination: date, flower: date | None = None) -> None:
    """Overwrite the seeded is_current row with the given dates."""
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(GrowState).where(GrowState.is_current.is_(True))
        )
        row = result.first()
        if row is None:
            session.add(
                GrowState(
                    germination_date=germination,
                    flower_start_date=flower,
                    is_current=True,
                )
            )
        else:
            row.germination_date = germination
            row.flower_start_date = flower
            session.add(row)
        await session.commit()


async def _set_lights(engine, on: time, off: time) -> None:
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(GrowState).where(GrowState.is_current.is_(True))
        )
        row = result.first()
        assert row is not None, "migration should have seeded an is_current row"
        row.lights_on_local = on
        row.lights_off_local = off
        session.add(row)
        await session.commit()


async def _clear_state(engine) -> None:
    """Flip is_current off on the seeded row — exercises the transient-default
    path. Can't DELETE the row because plant.growstate_id references it."""
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(GrowState).where(GrowState.is_current.is_(True))
        )
        row = result.first()
        if row is not None:
            row.is_current = False
            session.add(row)
            await session.commit()


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
    await _set_state(pg_engine, germination=date(2026, 3, 15))
    veg = await GrowStateService(pg_engine).current_targets()
    assert veg == gs.STAGE_TARGETS["veg"]

    await _set_state(pg_engine, germination=date(2026, 3, 15), flower=date(2026, 4, 1))
    early = await GrowStateService(pg_engine).current_targets()
    assert early == gs.STAGE_TARGETS["flower_early"]


def test_stage_targets_cover_all_stages_and_metrics():
    """Sensors.py only flags temp/humidity/VPD — every stage must carry all three."""
    expected = {"temperature_f", "humidity_pct", "vpd_kpa"}
    for stage, bands in gs.STAGE_TARGETS.items():
        assert set(bands) == expected, f"{stage} missing metrics"
        for metric, (lo, hi) in bands.items():
            assert lo < hi, f"{stage}.{metric} has inverted band"


# ------- get_state / transient fallback -------


async def test_get_state_returns_default_when_row_missing(pg_engine):
    await _clear_state(pg_engine)
    state = await GrowStateService(pg_engine).get_state()
    assert state.germination_date == GROW_START
    assert state.flower_start_date is None


# ------- lights_state (feedforward inputs for the humidifier loop) -------


def _utc(y: int, mo: int, d: int, h: int, mi: int = 0) -> datetime:
    # 12:00 MDT == 18:00 UTC; build the UTC equivalent for a MDT wall-clock time.
    local = datetime(y, mo, d, h, mi, tzinfo=gs.TENT_TZ)
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
