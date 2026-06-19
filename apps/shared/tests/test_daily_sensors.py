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

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorSource
from dirt_shared.models.plant import Plant, PlantLocationHistory, PlantMetricStream
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.daily_sensors import (
    SOIL_METRIC,
    SensorReader,
    mdt_window_to_utc,
)
from dirt_shared.services.readings import get_latest_product_plant_moisture_readings
from dirt_shared.services.scope import require_default_site_pk

# Apr 19 2026: MDT is UTC-6.
TEST_NOW = datetime(2026, 4, 19, 20, 30, 0, tzinfo=UTC)  # 14:30 MDT
TEST_DATE = date(2026, 4, 19)
TENT_DEVICE = "fan-controller"
BREEDING_TENT_DEVICE = "breeding-env-node"
PLANT_A_KEY = "SBBS-R1-001"
PLANT_B_KEY = "SBBS-R1-002"
PLANT_C_KEY = "SBBS-R1-003"
PLANT_D_KEY = "SBBS-R1-004"


def _clock():
    return TEST_NOW


async def _capability_ids(engine) -> dict[tuple[str, str], int]:
    async with AsyncSession(engine) as s:
        result = await s.exec(
            select(Device.device_id, Capability.metric_name, Capability.id).join(
                Capability, Capability.device_id == Device.id
            )
        )
        by_device_metric = {
            (device_id, metric): cap_id
            for device_id, metric, cap_id in result.all()
            if metric is not None
        }
        return {
            (device_id, metric): cap_id
            for (row_device_id, metric), cap_id in by_device_metric.items()
            for device_id in (row_device_id,)
        }


async def _seed_readings(
    engine,
    rows: list[tuple[str, str, float, datetime, SensorSource]],
) -> None:
    """rows: (device_id, metric, value, ts, source)."""
    cap_ids = await _capability_ids(engine)
    async with AsyncSession(engine) as s:
        for device_id, metric, value, ts, source in rows:
            s.add(
                SensorReading(
                    capability_id=cap_ids[(device_id, metric)],
                    metric=metric,
                    value=value,
                    ts=ts,
                    source=source,
                )
            )
        await s.commit()


async def _map_plant_moisture_stream(
    engine,
    *,
    plant_key: str,
    device_id: str,
    capability_id: str,
    metric_name: str,
    unit: str,
) -> int:
    async with AsyncSession(engine) as s:
        site_pk = await require_default_site_pk(s)
        plant, location = (
            await s.exec(
                select(Plant, PlantLocationHistory)
                .join(PlantLocationHistory, PlantLocationHistory.plant_id == Plant.id)
                .where(Plant.key == plant_key)
                .where(PlantLocationHistory.site_id == site_pk)
                .where(PlantLocationHistory.end_at.is_(None))
            )
        ).one()
        device = Device(
            site_id=site_pk,
            tent_id=location.tent_id,
            device_id=device_id,
            name=device_id,
            kind="moisture_node",
            controller="test",
        )
        s.add(device)
        await s.flush()
        capability = Capability(
            device_id=device.id,
            capability_id=capability_id,
            name=capability_id,
            kind="measurement",
            metric_name=metric_name,
            unit=unit,
            source="test",
        )
        s.add(capability)
        await s.flush()
        assert capability.id is not None
        capability_pk = capability.id
        s.add(PlantMetricStream(plant_id=plant.id, capability_id=capability.id))
        await s.commit()
        return capability_pk


async def _deactivate_plant_moisture_stream(engine, *, plant_key: str) -> None:
    async with AsyncSession(engine) as s:
        site_pk = await require_default_site_pk(s)
        plant = (
            await s.exec(
                select(Plant)
                .join(PlantLocationHistory, PlantLocationHistory.plant_id == Plant.id)
                .where(Plant.key == plant_key)
                .where(PlantLocationHistory.site_id == site_pk)
                .where(PlantLocationHistory.end_at.is_(None))
            )
        ).one()
        streams = (
            await s.exec(
                select(PlantMetricStream)
                .where(PlantMetricStream.plant_id == plant.id)
                .where(PlantMetricStream.is_active.is_(True))
            )
        ).all()
        for stream in streams:
            stream.is_active = False
            s.add(stream)
        await s.commit()


def _all_tent_metrics_fresh() -> list[tuple]:
    """Build a clean set of fresh tent readings (one per METRIC)."""
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    return [
        (TENT_DEVICE, "temperature_f", 80.0, fresh_ts, SensorSource.ARDUINO),
        (TENT_DEVICE, "humidity_pct", 50.0, fresh_ts, SensorSource.ARDUINO),
        (TENT_DEVICE, "vpd_kpa", 1.5, fresh_ts, SensorSource.ARDUINO),
        (TENT_DEVICE, "dew_point_f", 58.0, fresh_ts, SensorSource.ARDUINO),
        (TENT_DEVICE, "fan_pct", 35.0, fresh_ts, SensorSource.ARDUINO),
    ]


def _plant_moisture_fresh(
    device_id: str,
    value: float,
    *,
    ts: datetime | None = None,
) -> tuple:
    return (
        device_id,
        SOIL_METRIC,
        value,
        ts or TEST_NOW - timedelta(seconds=10),
        SensorSource.ESP32,
    )


def _current_seeded_plant_moisture_fresh() -> list[tuple]:
    return [
        _plant_moisture_fresh("plant-a-substrate-node", 26.6),
        _plant_moisture_fresh("plant-c-substrate-node", 35.1),
        _plant_moisture_fresh("plant-d-substrate-node", 31.4),
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
        [*_all_tent_metrics_fresh(), *_current_seeded_plant_moisture_fresh()],
    )
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300)
    assert await r.validate() == []


async def test_validate_flags_zero_tent_value(pg_engine):
    rows = _all_tent_metrics_fresh()
    rows[1] = (TENT_DEVICE, "humidity_pct", 0.0, rows[1][3], SensorSource.ARDUINO)
    await _seed_readings(pg_engine, rows)
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300)
    failures = await r.validate()
    assert any(f.reason == "zero" and f.metric == "humidity_pct" for f in failures)


async def test_validate_flags_stale_direct_plant_moisture(pg_engine):
    device_id = "test-plant-b-direct-moisture"
    await _map_plant_moisture_stream(
        pg_engine,
        plant_key=PLANT_B_KEY,
        device_id=device_id,
        capability_id="soil_moisture_pct",
        metric_name=SOIL_METRIC,
        unit="%",
    )
    await _seed_readings(
        pg_engine,
        [
            *_all_tent_metrics_fresh(),
            (
                device_id,
                SOIL_METRIC,
                41.0,
                TEST_NOW - timedelta(minutes=10),
                SensorSource.ESP32,
            ),
        ],
    )
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300)
    failures = await r.validate()
    assert any(
        f.reason == "stale"
        and f.subject == f"plant-{PLANT_B_KEY}"
        and f.metric == SOIL_METRIC
        for f in failures
    )


async def test_validate_ignores_unsupported_raw_plant_moisture(pg_engine):
    raw_device_id = "test-plant-c-raw-moisture"
    await _map_plant_moisture_stream(
        pg_engine,
        plant_key=PLANT_C_KEY,
        device_id=raw_device_id,
        capability_id="soil_moisture_raw",
        metric_name="soil_moisture_raw",
        unit="raw",
    )
    await _seed_readings(
        pg_engine,
        [
            *_all_tent_metrics_fresh(),
            *_current_seeded_plant_moisture_fresh(),
            (
                raw_device_id,
                "soil_moisture_raw",
                4095.0,
                TEST_NOW - timedelta(seconds=10),
                SensorSource.ESP32,
            ),
        ],
    )
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300)
    assert await r.validate() == []


async def test_current_product_plant_moisture_uses_active_direct_streams_only(
    pg_engine,
):
    await _seed_readings(
        pg_engine,
        [
            *_current_seeded_plant_moisture_fresh(),
            (
                "plant-b-node",
                "soil_moisture_raw",
                1500.0,
                TEST_NOW - timedelta(seconds=10),
                SensorSource.ESP32,
            ),
        ],
    )

    async with AsyncSession(pg_engine) as s:
        readings = await get_latest_product_plant_moisture_readings(s, now=TEST_NOW)

    by_plant = {reading.plant_key: reading for reading in readings}
    assert set(by_plant) == {PLANT_A_KEY, PLANT_C_KEY, PLANT_D_KEY}
    assert by_plant[PLANT_A_KEY].device_id == "plant-a-substrate-node"
    assert by_plant[PLANT_C_KEY].device_id == "plant-c-substrate-node"
    assert by_plant[PLANT_D_KEY].device_id == "plant-d-substrate-node"
    assert {reading.capability_id for reading in readings} == {"soil_moisture_pct"}


async def test_validate_flags_stale(pg_engine):
    # ten minutes old -> stale at 5min threshold
    stale_ts = TEST_NOW - timedelta(minutes=10)
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    rows = [
        (TENT_DEVICE, "temperature_f", 80.0, stale_ts, SensorSource.ARDUINO),
    ]
    # other tent metrics fresh
    for m in ("humidity_pct", "vpd_kpa", "dew_point_f"):
        rows.append((TENT_DEVICE, m, 50.0, fresh_ts, SensorSource.ARDUINO))
    await _seed_readings(pg_engine, rows)
    r = SensorReader(pg_engine, clock=_clock, max_age_s=300)
    failures = await r.validate()
    assert any(f.reason == "stale" and f.metric == "temperature_f" for f in failures)


async def test_validate_flags_missing(pg_engine):
    # only humidity_pct seeded; other tent metrics missing entirely
    rows = [
        (
            TENT_DEVICE,
            "humidity_pct",
            50.0,
            TEST_NOW - timedelta(seconds=5),
            SensorSource.ARDUINO,
        ),
    ]
    await _seed_readings(pg_engine, rows)
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
    rows.append(
        (TENT_DEVICE, "temperature_f", 70.0, overnight_ts, SensorSource.ARDUINO)
    )
    rows.append(
        (
            TENT_DEVICE,
            "temperature_f",
            80.0,
            overnight_ts + timedelta(hours=1),
            SensorSource.ARDUINO,
        )
    )
    # morning: 10:00 MDT = 16:00 UTC. one reading at 90.
    morning_ts = datetime(2026, 4, 19, 16, 0, tzinfo=UTC)
    rows.append((TENT_DEVICE, "temperature_f", 90.0, morning_ts, SensorSource.ARDUINO))
    # NOW reading at 14:30 MDT = 20:30 UTC; latest = 85
    now_ts = datetime(2026, 4, 19, 20, 25, tzinfo=UTC)
    rows.append((TENT_DEVICE, "temperature_f", 85.0, now_ts, SensorSource.ARDUINO))
    # also add other tent metrics so windows have *something*
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    for m in ("humidity_pct", "vpd_kpa", "dew_point_f"):
        rows.append((TENT_DEVICE, m, 50.0, fresh_ts, SensorSource.ARDUINO))
    await _seed_readings(pg_engine, rows)

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


async def test_snapshot_includes_scoped_breeding_tent(pg_engine):
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    await _seed_readings(
        pg_engine,
        [
            *_all_tent_metrics_fresh(),
            (
                BREEDING_TENT_DEVICE,
                "temperature_f",
                79.0,
                fresh_ts,
                SensorSource.ESP32,
            ),
            (
                BREEDING_TENT_DEVICE,
                "humidity_pct",
                61.0,
                fresh_ts,
                SensorSource.ESP32,
            ),
            (
                BREEDING_TENT_DEVICE,
                "vpd_kpa",
                1.0,
                fresh_ts,
                SensorSource.ESP32,
            ),
            (
                BREEDING_TENT_DEVICE,
                "dew_point_f",
                64.0,
                fresh_ts,
                SensorSource.ESP32,
            ),
        ],
    )

    r = SensorReader(pg_engine, clock=_clock)
    snap = await r.snapshot(TEST_DATE)
    out = snap.to_prompt_dict()

    assert set(out["tents"]) == {1, 2}
    assert out["tents"][2]["temperature_f"]["now"] == 79.0
    assert out["tents"][1]["temperature_f"]["now"] == 80.0


async def test_snapshot_per_plant_pct_uses_direct_percent(pg_engine):
    device_id = "test-plant-a-direct-moisture"
    await _map_plant_moisture_stream(
        pg_engine,
        plant_key=PLANT_A_KEY,
        device_id=device_id,
        capability_id="soil_moisture_pct",
        metric_name=SOIL_METRIC,
        unit="%",
    )
    rows = _all_tent_metrics_fresh()
    fresh_ts = TEST_NOW - timedelta(seconds=10)
    rows.append((device_id, SOIL_METRIC, 54.9, fresh_ts, SensorSource.ESP32))
    await _seed_readings(pg_engine, rows)

    r = SensorReader(pg_engine, clock=_clock)
    snap = await r.snapshot(TEST_DATE)
    assert snap.plants[PLANT_A_KEY]["now_pct"] == 54.9


async def test_snapshot_omits_inactive_plant_moisture_stream(pg_engine):
    await _deactivate_plant_moisture_stream(pg_engine, plant_key=PLANT_A_KEY)
    await _seed_readings(pg_engine, _all_tent_metrics_fresh())

    r = SensorReader(pg_engine, clock=_clock)
    snap = await r.snapshot(TEST_DATE)

    assert PLANT_A_KEY not in snap.plants


def test_to_prompt_dict_renders_window_avg():
    from dirt_shared.services.daily_sensors import (
        DailySensorSnapshot,
        WindowAvg,
    )

    snap = DailySensorSnapshot(
        date_mdt=TEST_DATE,
        tent={
            "temperature_f": {
                "overnight": WindowAvg(avg=75.123, n=2),
                "morning": WindowAvg(avg=None, n=0),
                "now": 85.0,
            }
        },
        plants={
            PLANT_A_KEY: {
                "overnight_pct": WindowAvg(avg=42.5, n=10),
                "morning_pct": WindowAvg(avg=None, n=0),
                "now_pct": 33.1,
                "pct_delta_morning_to_now": None,
            }
        },
        tents={
            1: {
                "temperature_f": {
                    "overnight": WindowAvg(avg=75.123, n=2),
                    "morning": WindowAvg(avg=None, n=0),
                    "now": 85.0,
                }
            },
            2: {},
        },
    )
    out = snap.to_prompt_dict()
    assert out["date_mdt"] == "2026-04-19"
    assert out["tent"]["temperature_f"]["overnight"] == {"avg": 75.12, "n": 2}
    assert out["tent"]["temperature_f"]["morning"] is None
    assert out["tent"]["temperature_f"]["now"] == 85.0
    assert out["plants"][PLANT_A_KEY]["overnight_pct"] == {"avg": 42.5, "n": 10}
    assert out["plants"][PLANT_A_KEY]["morning_pct"] is None
    assert out["plants"][PLANT_A_KEY]["now_pct"] == 33.1
    assert "raw_delta_morning_to_now" not in out["plants"][PLANT_A_KEY]
    assert out["soil_moisture_note"].startswith("Soil moisture is reported")
    assert set(out["tents"]) == {1, 2}
