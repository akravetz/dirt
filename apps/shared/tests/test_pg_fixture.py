"""Smoke tests for the root pg_engine fixture — verifies per-test DB
isolation + engine monkeypatching across service modules."""

from __future__ import annotations

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Device
from dirt_shared.models.enums import SensorSource
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import ReadingsService


async def test_fixture_yields_engine_with_seeded_rows(app_engine):
    async with AsyncSession(app_engine) as session:
        result = await session.exec(select(Device.device_id))
        devices = set(result.all())
    # topology-contract-ok: fixture smoke test intentionally checks seed rows.
    assert {
        "fan-controller",
        "plant-a-node",
        "plant-b-node",
        "plant-c-node",
        "plant-d-node",
        "reservoir-node",
    } <= devices


async def test_readings_service_round_trip(app_engine):
    """Constructor-injected service writes + reads through the test engine."""
    readings = ReadingsService(app_engine)
    await readings.ingest_reading(
        {"temperature_f": 72.4},
        source=SensorSource.ARDUINO,
        device_id="fan-controller",
    )
    r = await readings.get_latest_reading("temperature_f")
    assert r is not None
    assert r.value == pytest.approx(72.4)


async def test_per_test_isolation_one(app_engine):
    """Writes in this test should NOT appear in test_per_test_isolation_two."""
    readings = ReadingsService(app_engine)
    await readings.ingest_reading(
        {"temperature_f": 99.9},
        source=SensorSource.ARDUINO,
        device_id="fan-controller",
    )


async def test_per_test_isolation_two(app_engine):
    """Should see zero readings even though test_one wrote one."""
    async with AsyncSession(app_engine) as session:
        result = await session.exec(
            select(SensorReading).where(SensorReading.metric == "temperature_f")
        )
        rows = result.all()
    assert len(rows) == 0, f"got {len(rows)} rows, expected 0 — isolation broken"
