"""Smoke tests for the root pg_engine fixture — verifies per-test DB
isolation + engine monkeypatching across service modules."""

from __future__ import annotations

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import ReadingsService


async def test_fixture_yields_engine_with_seeded_rows(app_engine):
    async with AsyncSession(app_engine) as session:
        result = await session.exec(select(SensorNode))
        nodes = result.all()
    # The Atlas init migration seeds one sensornode row per enum value.
    assert {n.location for n in nodes} == {
        SensorLocation.TENT,
        SensorLocation.PLANT_A,
        SensorLocation.PLANT_B,
        SensorLocation.PLANT_C,
        SensorLocation.PLANT_D,
        SensorLocation.RESERVOIR,
    }


async def test_readings_service_round_trip(app_engine):
    """Constructor-injected service writes + reads through the test engine."""
    readings = ReadingsService(app_engine)
    await readings.ingest_reading(
        SensorLocation.TENT,
        {"temperature_f": 72.4},
        source=SensorSource.ARDUINO,
    )
    r = await readings.get_latest_reading("temperature_f")
    assert r is not None
    assert r.value == pytest.approx(72.4)


async def test_per_test_isolation_one(app_engine):
    """Writes in this test should NOT appear in test_per_test_isolation_two."""
    readings = ReadingsService(app_engine)
    await readings.ingest_reading(
        SensorLocation.TENT,
        {"temperature_f": 99.9},
        source=SensorSource.ARDUINO,
    )


async def test_per_test_isolation_two(app_engine):
    """Should see zero readings even though test_one wrote one."""
    async with AsyncSession(app_engine) as session:
        result = await session.exec(
            select(SensorReading).where(SensorReading.metric == "temperature_f")
        )
        rows = result.all()
    assert len(rows) == 0, f"got {len(rows)} rows, expected 0 — isolation broken"
