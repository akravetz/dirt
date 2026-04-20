"""Tests for the daily-report sensor reader.

Uses the shared ``pg_engine`` fixture (cloned from the session-wide
template) + a frozen clock passed by injection so time-window logic is
deterministic.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.daily_sensors import (
    PLANT_LOCATIONS,
    SOIL_METRIC,
    TENT_LOCATION,
    SensorReader,
    mdt_window_to_utc,
)

# Apr 19 2026: MDT is UTC-6.
TEST_NOW = datetime(2026, 4, 19, 20, 30, 0, tzinfo=UTC)  # 14:30 MDT
TEST_DATE = date(2026, 4, 19)


def _clock():
    return TEST_NOW


async def _node_ids(engine) -> dict[SensorLocation, int]:
    """Resolve every seeded sensornode (location → id)."""
    async with AsyncSession(engine) as s:
        result = await s.exec(select(SensorNode))
        return {n.location: n.id for n in result.all()}


async def _seed_readings(
    engine,
    rows: list[tuple[SensorLocation, str, float, datetime, SensorSource]],
    cals: list[tuple[SensorLocation, str, float, float]] = (),
) -> None:
    """rows: (location, metric, value, ts, source). cals: (location, metric, raw_low, raw_high)."""
    node_ids = await _node_ids(engine)
    async with AsyncSession(engine) as s:
        for loc, metric, value, ts, source in rows:
            s.add(
                SensorReading(
                    sensornode_id=node_ids[loc],
                    metric=metric,
                    value=value,
                    ts=ts,
                    source=source,
                )
            )
        for loc, metric, raw_low, raw_high in cals:
            s.add(
                SensorCalibration(
                    sensornode_id=node_ids[loc],
                    metric=metric,
                    raw_low=raw_low,
                    raw_high=raw_high,
                )
            )
        await s.commit()


def _all_tent_metrics_fresh() -> list[tuple]:
    """Build a clean set of fresh tent readings (one per METRIC)."""
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    return [
        (TENT_LOCATION, "temperature_f", 80.0, fresh_ts, SensorSource.ARDUINO),
        (TENT_LOCATION, "humidity_pct", 50.0, fresh_ts, SensorSource.ARDUINO),
        (TENT_LOCATION, "pressure_hpa", 843.0, fresh_ts, SensorSource.ARDUINO),
        (TENT_LOCATION, "vpd_kpa", 1.5, fresh_ts, SensorSource.ARDUINO),
        (TENT_LOCATION, "dew_point_f", 58.0, fresh_ts, SensorSource.ARDUINO),
    ]


def _all_plants_fresh(value: float = 2500.0) -> list[tuple]:
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    return [
        (loc, SOIL_METRIC, value, fresh_ts, SensorSource.ESP32)
        for loc in PLANT_LOCATIONS
    ]


def _plant_calibrations() -> list[tuple]:
    return [
        (loc, SOIL_METRIC, 1370.0, 3880.0) for loc in PLANT_LOCATIONS
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


async def test_validate_passes_on_clean_data(pg_engine):
    await _seed_readings(
        pg_engine,
        _all_tent_metrics_fresh() + _all_plants_fresh(value=2500.0),
        _plant_calibrations(),
    )
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300)
    assert await r.validate() == []


async def test_validate_flags_zero_tent_value(pg_engine):
    rows = _all_tent_metrics_fresh()
    rows[1] = (TENT_LOCATION, "humidity_pct", 0.0, rows[1][3], SensorSource.ARDUINO)
    await _seed_readings(pg_engine, rows + _all_plants_fresh())
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300)
    failures = await r.validate()
    assert any(f.reason == "zero" and f.metric == "humidity_pct" for f in failures)


async def test_validate_flags_pinned_plant_high(pg_engine):
    plants = _all_plants_fresh()
    plants[1] = (SensorLocation.PLANT_B, SOIL_METRIC, 4095.0, plants[1][3], SensorSource.ESP32)
    await _seed_readings(pg_engine, _all_tent_metrics_fresh() + plants)
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300, sensor_max_raw=4000.0)
    failures = await r.validate()
    assert any(
        f.reason == "raw_pinned_high" and f.location == SensorLocation.PLANT_B
        for f in failures
    )


async def test_validate_flags_pinned_plant_low(pg_engine):
    plants = _all_plants_fresh()
    plants[2] = (SensorLocation.PLANT_C, SOIL_METRIC, 5.0, plants[2][3], SensorSource.ESP32)
    await _seed_readings(pg_engine, _all_tent_metrics_fresh() + plants)
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300, sensor_min_raw=30.0)
    failures = await r.validate()
    assert any(
        f.reason == "raw_pinned_low" and f.location == SensorLocation.PLANT_C
        for f in failures
    )


async def test_validate_flags_stale(pg_engine):
    # ten minutes old -> stale at 5min threshold
    stale_ts = TEST_NOW - timedelta(minutes=10)
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    rows = [
        (TENT_LOCATION, "temperature_f", 80.0, stale_ts, SensorSource.ARDUINO),
    ]
    # other tent metrics fresh
    for m in ("humidity_pct", "pressure_hpa", "vpd_kpa", "dew_point_f"):
        rows.append((TENT_LOCATION, m, 50.0, fresh_ts, SensorSource.ARDUINO))
    await _seed_readings(pg_engine, rows + _all_plants_fresh())
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300)
    failures = await r.validate()
    assert any(f.reason == "stale" and f.metric == "temperature_f" for f in failures)


async def test_validate_flags_missing(pg_engine):
    # only humidity_pct seeded; other tent metrics missing entirely
    rows = [
        (TENT_LOCATION, "humidity_pct", 50.0,
         TEST_NOW - timedelta(seconds=5), SensorSource.ARDUINO),
    ]
    await _seed_readings(pg_engine, rows + _all_plants_fresh())
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300)
    failures = await r.validate()
    missing_metrics = {f.metric for f in failures if f.reason == "missing"}
    assert "temperature_f" in missing_metrics
    assert "vpd_kpa" in missing_metrics


async def test_snapshot_aggregates_three_windows(pg_engine):
    """Seed readings across overnight + morning + just-now and verify the
    snapshot averages match by hand."""
    rows = []
    # overnight: 02:00 MDT = 08:00 UTC. Two readings, avg should be 75.
    overnight_ts = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)
    rows.append((TENT_LOCATION, "temperature_f", 70.0, overnight_ts, SensorSource.ARDUINO))
    rows.append((TENT_LOCATION, "temperature_f", 80.0,
                 overnight_ts + timedelta(hours=1), SensorSource.ARDUINO))
    # morning: 10:00 MDT = 16:00 UTC. one reading at 90.
    morning_ts = datetime(2026, 4, 19, 16, 0, tzinfo=UTC)
    rows.append((TENT_LOCATION, "temperature_f", 90.0, morning_ts, SensorSource.ARDUINO))
    # NOW reading at 14:30 MDT = 20:30 UTC; latest = 85
    now_ts = datetime(2026, 4, 19, 20, 25, tzinfo=UTC)
    rows.append((TENT_LOCATION, "temperature_f", 85.0, now_ts, SensorSource.ARDUINO))
    # also add other tent metrics + plants so windows have *something*
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    for m in ("humidity_pct", "pressure_hpa", "vpd_kpa", "dew_point_f"):
        rows.append((TENT_LOCATION, m, 50.0, fresh_ts, SensorSource.ARDUINO))
    rows.extend(_all_plants_fresh(value=2500.0))
    await _seed_readings(pg_engine, rows, _plant_calibrations())

    r = SensorReader(pg_engine, clock=_clock)
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


async def test_snapshot_per_plant_pct_uses_calibration(pg_engine):
    rows = _all_tent_metrics_fresh()
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    # plant-a raw=2500 cal 1370/3880 -> pct = 1380/2510 = 54.98%
    rows.append((SensorLocation.PLANT_A, SOIL_METRIC, 2500.0, fresh_ts, SensorSource.ESP32))
    for loc in (SensorLocation.PLANT_B, SensorLocation.PLANT_C, SensorLocation.PLANT_D):
        rows.append((loc, SOIL_METRIC, 2000.0, fresh_ts, SensorSource.ESP32))
    await _seed_readings(pg_engine, rows, _plant_calibrations())

    r = SensorReader(pg_engine, clock=_clock)
    snap = await r.snapshot(TEST_DATE)
    pct_a = snap.plants["a"]["now_pct"]
    assert pct_a == pytest.approx(54.98, abs=0.1)


def test_to_prompt_dict_renders_window_avg():
    from dirt_shared.services.daily_sensors import (
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
