"""Tests for the daily-report sensor reader.

Uses an in-memory SQLite engine and a frozen clock — both passed to
SensorReader by injection so the production singletons stay untouched.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.models.sensor_calibration import SensorCalibration
from dirt.models.sensor_reading import SensorReading
from dirt.services.daily_sensors import (
    PLANT_LOCATIONS,
    SOIL_METRIC,
    TENT_LOCATION,
    SensorReader,
    mdt_window_to_utc,
)


@pytest.fixture
async def engine(tmp_path):
    db = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed(engine, rows: list[SensorReading], cals: list[SensorCalibration] = ()):
    async with AsyncSession(engine) as s:
        for r in rows:
            s.add(r)
        for c in cals:
            s.add(c)
        await s.commit()


def _ts(year, mo, d, h, m, sec=0) -> datetime:
    """Naive UTC, matching how the production code stores SensorReading.timestamp."""
    return datetime(year, mo, d, h, m, sec)


# Apr 19 2026: MDT is UTC-6.
TEST_NOW = datetime(2026, 4, 19, 20, 30, 0, tzinfo=UTC)  # 14:30 MDT
TEST_DATE = date(2026, 4, 19)


def _clock():
    return TEST_NOW


def _all_tent_metrics_fresh() -> list[SensorReading]:
    """Build a clean set of fresh tent readings (one per METRIC)."""
    fresh_ts = TEST_NOW.replace(tzinfo=None) - timedelta(seconds=10)
    return [
        SensorReading(location=TENT_LOCATION, metric="temperature_f",
                      value=80.0, timestamp=fresh_ts, source="arduino"),
        SensorReading(location=TENT_LOCATION, metric="humidity_pct",
                      value=50.0, timestamp=fresh_ts, source="arduino"),
        SensorReading(location=TENT_LOCATION, metric="pressure_hpa",
                      value=843.0, timestamp=fresh_ts, source="arduino"),
        SensorReading(location=TENT_LOCATION, metric="vpd_kpa",
                      value=1.5, timestamp=fresh_ts, source="arduino"),
        SensorReading(location=TENT_LOCATION, metric="dew_point_f",
                      value=58.0, timestamp=fresh_ts, source="arduino"),
    ]


def _all_plants_fresh(value: float = 2500.0) -> list[SensorReading]:
    fresh_ts = TEST_NOW.replace(tzinfo=None) - timedelta(seconds=10)
    return [
        SensorReading(location=loc, metric=SOIL_METRIC, value=value,
                      timestamp=fresh_ts, source="esp32")
        for loc in PLANT_LOCATIONS
    ]


def _plant_calibrations() -> list[SensorCalibration]:
    return [
        SensorCalibration(location=loc, metric=SOIL_METRIC,
                          raw_low=1370.0, raw_high=3880.0)
        for loc in PLANT_LOCATIONS
    ]


def test_mdt_window_to_utc_handles_offset():
    # 00:00 MDT Apr 19 = 06:00 UTC Apr 19
    start, end = mdt_window_to_utc(TEST_DATE, 0, 6)
    assert start == datetime(2026, 4, 19, 6, 0, tzinfo=UTC)
    assert end == datetime(2026, 4, 19, 12, 0, tzinfo=UTC)
    # 07:00-14:00 MDT = 13:00-20:00 UTC
    start, end = mdt_window_to_utc(TEST_DATE, 7, 14)
    assert start == datetime(2026, 4, 19, 13, 0, tzinfo=UTC)
    assert end == datetime(2026, 4, 19, 20, 0, tzinfo=UTC)


async def test_validate_passes_on_clean_data(engine):
    await _seed(
        engine,
        _all_tent_metrics_fresh() + _all_plants_fresh(value=2500.0),
        _plant_calibrations(),
    )
    r = SensorReader(engine, clock=_clock, max_age_s=300)
    assert await r.validate() == []


async def test_validate_flags_zero_tent_value(engine):
    rows = _all_tent_metrics_fresh()
    rows[1] = SensorReading(  # humidity_pct -> 0
        location=TENT_LOCATION, metric="humidity_pct", value=0.0,
        timestamp=rows[1].timestamp, source="arduino",
    )
    await _seed(engine, rows + _all_plants_fresh())
    r = SensorReader(engine, clock=_clock, max_age_s=300)
    failures = await r.validate()
    assert any(f.reason == "zero" and f.metric == "humidity_pct" for f in failures)


async def test_validate_flags_pinned_plant_high(engine):
    plants = _all_plants_fresh()
    plants[1] = SensorReading(  # plant-b -> 4095 (rail)
        location="plant-b", metric=SOIL_METRIC, value=4095.0,
        timestamp=plants[1].timestamp, source="esp32",
    )
    await _seed(engine, _all_tent_metrics_fresh() + plants)
    r = SensorReader(engine, clock=_clock, max_age_s=300, sensor_max_raw=4000.0)
    failures = await r.validate()
    assert any(
        f.reason == "raw_pinned_high" and f.location == "plant-b"
        for f in failures
    )


async def test_validate_flags_pinned_plant_low(engine):
    plants = _all_plants_fresh()
    plants[2] = SensorReading(  # plant-c reads 5 (out of soil)
        location="plant-c", metric=SOIL_METRIC, value=5.0,
        timestamp=plants[2].timestamp, source="esp32",
    )
    await _seed(engine, _all_tent_metrics_fresh() + plants)
    r = SensorReader(engine, clock=_clock, max_age_s=300, sensor_min_raw=30.0)
    failures = await r.validate()
    assert any(
        f.reason == "raw_pinned_low" and f.location == "plant-c"
        for f in failures
    )


async def test_validate_flags_stale(engine):
    # ten minutes old -> stale at 5min threshold
    stale_ts = TEST_NOW.replace(tzinfo=None) - timedelta(minutes=10)
    rows = [
        SensorReading(location=TENT_LOCATION, metric="temperature_f",
                      value=80.0, timestamp=stale_ts, source="arduino"),
    ]
    # other tent metrics fresh
    fresh_ts = TEST_NOW.replace(tzinfo=None) - timedelta(seconds=10)
    for m in ("humidity_pct", "pressure_hpa", "vpd_kpa", "dew_point_f"):
        rows.append(SensorReading(
            location=TENT_LOCATION, metric=m, value=50.0,
            timestamp=fresh_ts, source="arduino"))
    await _seed(engine, rows + _all_plants_fresh())
    r = SensorReader(engine, clock=_clock, max_age_s=300)
    failures = await r.validate()
    assert any(f.reason == "stale" and f.metric == "temperature_f" for f in failures)


async def test_validate_flags_missing(engine):
    # only humidity_pct seeded; other tent metrics missing entirely
    rows = [
        SensorReading(location=TENT_LOCATION, metric="humidity_pct",
                      value=50.0,
                      timestamp=TEST_NOW.replace(tzinfo=None) - timedelta(seconds=5),
                      source="arduino"),
    ]
    await _seed(engine, rows + _all_plants_fresh())
    r = SensorReader(engine, clock=_clock, max_age_s=300)
    failures = await r.validate()
    missing_metrics = {f.metric for f in failures if f.reason == "missing"}
    assert "temperature_f" in missing_metrics
    assert "vpd_kpa" in missing_metrics


async def test_snapshot_aggregates_three_windows(engine):
    """Seed readings across overnight + morning + just-now and verify the
    snapshot averages match by hand."""
    rows = []
    # overnight: 02:00 MDT = 08:00 UTC. Two readings, avg should be 75 and 50.
    overnight_ts = datetime(2026, 4, 19, 8, 0)
    rows.append(SensorReading(location=TENT_LOCATION, metric="temperature_f",
                              value=70.0, timestamp=overnight_ts, source="a"))
    rows.append(SensorReading(location=TENT_LOCATION, metric="temperature_f",
                              value=80.0,
                              timestamp=overnight_ts + timedelta(hours=1),
                              source="a"))
    # morning: 10:00 MDT = 16:00 UTC. one reading at 90.
    morning_ts = datetime(2026, 4, 19, 16, 0)
    rows.append(SensorReading(location=TENT_LOCATION, metric="temperature_f",
                              value=90.0, timestamp=morning_ts, source="a"))
    # NOW reading at 14:30 MDT = 20:30 UTC; latest = 85
    now_ts = datetime(2026, 4, 19, 20, 25)
    rows.append(SensorReading(location=TENT_LOCATION, metric="temperature_f",
                              value=85.0, timestamp=now_ts, source="a"))
    # also add other tent metrics + plants so windows have *something*
    fresh_ts = TEST_NOW.replace(tzinfo=None) - timedelta(seconds=10)
    for m in ("humidity_pct", "pressure_hpa", "vpd_kpa", "dew_point_f"):
        rows.append(SensorReading(location=TENT_LOCATION, metric=m,
                                  value=50.0, timestamp=fresh_ts, source="a"))
    rows.extend(_all_plants_fresh(value=2500.0))
    await _seed(engine, rows, _plant_calibrations())

    r = SensorReader(engine, clock=_clock)
    snap = await r.snapshot(TEST_DATE)

    temp = snap.tent["temperature_f"]
    # overnight: 70 + 80 = avg 75, n=2
    assert temp["overnight"].n == 2
    assert temp["overnight"].avg == pytest.approx(75.0)
    # morning: 90, n=1
    assert temp["morning"].n == 1
    assert temp["morning"].avg == pytest.approx(90.0)
    # now: latest reading
    assert temp["now"] == 85.0


async def test_snapshot_per_plant_pct_uses_calibration(engine):
    rows = _all_tent_metrics_fresh()
    fresh_ts = TEST_NOW.replace(tzinfo=None) - timedelta(seconds=10)
    # plant-a raw=2500 cal 1370/3880 -> pct = 1380/2510 = 54.98%
    rows.append(SensorReading(
        location="plant-a", metric=SOIL_METRIC,
        value=2500.0, timestamp=fresh_ts, source="esp32",
    ))
    for loc in ("plant-b", "plant-c", "plant-d"):
        rows.append(SensorReading(
            location=loc, metric=SOIL_METRIC, value=2000.0,
            timestamp=fresh_ts, source="esp32",
        ))
    await _seed(engine, rows, _plant_calibrations())

    r = SensorReader(engine, clock=_clock)
    snap = await r.snapshot(TEST_DATE)
    pct_a = snap.plants["a"]["now_pct"]
    assert pct_a == pytest.approx(54.98, abs=0.1)


def test_to_prompt_dict_renders_window_avg():
    from dirt.services.daily_sensors import (
        DailySensorSnapshot,
        WindowAvg,
    )
    snap = DailySensorSnapshot(
        date_mdt=TEST_DATE,
        tent={"temperature_f": {
            "overnight": WindowAvg(avg=75.123, n=2),
            "morning": WindowAvg(avg=None, n=0),
            "now": 85.0,
        }},
        plants={"a": {
            "overnight_pct": WindowAvg(avg=42.5, n=10),
            "morning_pct": WindowAvg(avg=None, n=0),
            "now_pct": 33.1,
        }},
    )
    out = snap.to_prompt_dict()
    assert out["date_mdt"] == "2026-04-19"
    assert out["tent"]["temperature_f"]["overnight"] == {"avg": 75.12, "n": 2}
    assert out["tent"]["temperature_f"]["morning"] is None
    assert out["tent"]["temperature_f"]["now"] == 85.0
    assert out["plants"]["a"]["overnight_pct"] == {"avg": 42.5, "n": 10}
    assert out["plants"]["a"]["morning_pct"] is None
    assert out["plants"]["a"]["now_pct"] == 33.1
