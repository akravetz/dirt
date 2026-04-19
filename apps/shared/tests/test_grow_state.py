"""Tests for the GrowState singleton + stage-derived target lookup."""

from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import GROW_START
from dirt_shared.db import init_db
from dirt_shared.models.grow_state import GrowState
from dirt_shared.services import grow_state as gs


@pytest.fixture
async def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


async def _set_state(eng, *, germination: date, flower: date | None = None) -> None:
    async with AsyncSession(eng) as session:
        row = await session.get(GrowState, 1)
        if row is None:
            session.add(
                GrowState(id=1, germination_date=germination, flower_start_date=flower)
            )
        else:
            row.germination_date = germination
            row.flower_start_date = flower
            session.add(row)
        await session.commit()


# ------- current_stage -------


async def test_stage_veg_when_flower_start_is_none(db_engine):
    await _set_state(db_engine, germination=date(2026, 3, 15))
    with patch.object(gs, "engine", db_engine):
        assert await gs.current_stage(today=date(2026, 4, 18)) == "veg"


async def test_stage_veg_when_flower_start_in_future(db_engine):
    await _set_state(db_engine, germination=date(2026, 3, 15), flower=date(2026, 5, 1))
    with patch.object(gs, "engine", db_engine):
        assert await gs.current_stage(today=date(2026, 4, 18)) == "veg"


async def test_stage_early_flower_day_zero(db_engine):
    flower = date(2026, 4, 18)
    await _set_state(db_engine, germination=date(2026, 3, 15), flower=flower)
    with patch.object(gs, "engine", db_engine):
        assert await gs.current_stage(today=flower) == "flower_early"


async def test_stage_early_flower_day_20(db_engine):
    flower = date(2026, 4, 1)
    await _set_state(db_engine, germination=date(2026, 3, 15), flower=flower)
    with patch.object(gs, "engine", db_engine):
        # Day 20 = still early (21 is the crossover)
        assert await gs.current_stage(today=date(2026, 4, 21)) == "flower_early"


async def test_stage_late_flower_day_21(db_engine):
    flower = date(2026, 4, 1)
    await _set_state(db_engine, germination=date(2026, 3, 15), flower=flower)
    with patch.object(gs, "engine", db_engine):
        assert await gs.current_stage(today=date(2026, 4, 22)) == "flower_late"


# ------- grow_week -------


async def test_grow_week_day_one_is_week_one(db_engine):
    await _set_state(db_engine, germination=date(2026, 3, 15))
    with patch.object(gs, "engine", db_engine):
        assert await gs.grow_week(today=date(2026, 3, 15)) == 1


async def test_grow_week_day_seven_is_week_one(db_engine):
    await _set_state(db_engine, germination=date(2026, 3, 15))
    with patch.object(gs, "engine", db_engine):
        assert await gs.grow_week(today=date(2026, 3, 21)) == 1


async def test_grow_week_day_eight_is_week_two(db_engine):
    await _set_state(db_engine, germination=date(2026, 3, 15))
    with patch.object(gs, "engine", db_engine):
        assert await gs.grow_week(today=date(2026, 3, 22)) == 2


# ------- current_targets -------


async def test_current_targets_tracks_stage(db_engine):
    await _set_state(db_engine, germination=date(2026, 3, 15))
    with patch.object(gs, "engine", db_engine):
        veg = await gs.current_targets()
    assert veg == gs.STAGE_TARGETS["veg"]

    await _set_state(db_engine, germination=date(2026, 3, 15), flower=date(2026, 4, 1))
    with patch.object(gs, "engine", db_engine):
        early = await gs.current_targets()
    assert early == gs.STAGE_TARGETS["flower_early"]


def test_stage_targets_cover_all_stages_and_metrics():
    """Sensors.py only flags temp/humidity/VPD — every stage must carry all three."""
    expected = {"temperature_f", "humidity_pct", "vpd_kpa"}
    for stage, bands in gs.STAGE_TARGETS.items():
        assert set(bands) == expected, f"{stage} missing metrics"
        for metric, (lo, hi) in bands.items():
            assert lo < hi, f"{stage}.{metric} has inverted band"


# ------- get_state / transient fallback -------


async def test_get_state_returns_default_when_row_missing(db_engine):
    with patch.object(gs, "engine", db_engine):
        state = await gs.get_state()
    assert state.germination_date == GROW_START
    assert state.flower_start_date is None


# ------- init_db seeding -------


async def test_init_db_seeds_singleton_on_fresh_db(db_engine):
    with patch("dirt_shared.db.engine", db_engine):
        await init_db()
    async with AsyncSession(db_engine) as session:
        row = await session.get(GrowState, 1)
    assert row is not None
    assert row.germination_date == GROW_START
    assert row.flower_start_date is None


async def test_init_db_does_not_overwrite_existing_row(db_engine):
    # Simulate a user who's already flipped to flower.
    flipped = date(2026, 6, 1)
    await _set_state(db_engine, germination=date(2026, 3, 15), flower=flipped)
    with patch("dirt_shared.db.engine", db_engine):
        await init_db()
    async with AsyncSession(db_engine) as session:
        row = await session.get(GrowState, 1)
    assert row.flower_start_date == flipped
