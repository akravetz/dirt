"""Scoped telemetry ownership tests."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorSource
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.scope import resolve_scope


async def test_default_history_excludes_same_metric_from_breeding_tent(app_engine):
    readings = ReadingsService(app_engine)
    await readings.ingest_reading(
        {"temperature_f": 72.0},
        source=SensorSource.MOCK,
        device_id="fan-controller",
    )

    async with AsyncSession(app_engine) as session:
        breeding = await resolve_scope(session, tent_id="breeding")
        assert breeding is not None
        device = Device(
            site_id=breeding.site_pk,
            tent_id=breeding.tent_pk,
            device_id="breeding-env-node",
            name="Breeding env node",
            kind="env_sensor",
            controller="test",
        )
        session.add(device)
        await session.flush()
        assert device.id is not None
        capability = Capability(
            device_id=device.id,
            capability_id="temperature_f",
            name="Temperature F",
            kind="measurement",
            metric_name="temperature_f",
            unit="degF",
            source="test",
        )
        session.add(capability)
        await session.flush()
        assert capability.id is not None
        session.add(
            SensorReading(
                ts=datetime.now(UTC),
                capability_id=capability.id,
                metric="temperature_f",
                value=80.0,
                source=SensorSource.MOCK,
            )
        )
        await session.commit()

    main_history = await readings.get_metric_history("temperature_f", "1h")
    breeding_history = await readings.get_metric_history(
        "temperature_f", "1h", tent_id="breeding"
    )
    main_latest = await readings.get_latest_reading("temperature_f")
    breeding_latest = await readings.get_latest_reading(
        "temperature_f", tent_id="breeding"
    )

    assert [value for _, value in main_history] == [72.0]
    assert [value for _, value in breeding_history] == [80.0]
    assert main_latest is not None
    assert main_latest.value == 72.0
    assert breeding_latest is not None
    assert breeding_latest.value == 80.0


async def test_scoped_ingest_updates_device_heartbeat(app_engine):
    readings = ReadingsService(
        app_engine, clock=lambda: datetime(2026, 5, 4, tzinfo=UTC)
    )

    await readings.ingest_reading(
        {"soil_moisture_raw": 1600.0},
        source=SensorSource.ESP32,
        ip="192.168.1.101",
        firmware_version="0.2.0",
        uptime_ms=1234,
        site_id="homebox",
        tent_id="main",
        zone_id="plant-a",
        device_id="plant-a-node",
    )

    async with AsyncSession(app_engine) as session:
        device = (
            await session.exec(select(Device).where(Device.device_id == "plant-a-node"))
        ).one()

    assert device.last_seen == datetime(2026, 5, 4, tzinfo=UTC)
    assert str(device.ip) == "192.168.1.101"
    assert device.firmware_version == "0.2.0"
    assert device.uptime_ms == 1234


async def test_touch_device_updates_device_heartbeat(app_engine):
    readings = ReadingsService(
        app_engine, clock=lambda: datetime(2026, 5, 4, 0, 1, tzinfo=UTC)
    )

    await readings.touch_device(
        device_id="plant-a-node",
        ip="192.168.1.102",
        firmware_version="0.1.5",
        uptime_ms=4321,
    )

    async with AsyncSession(app_engine) as session:
        device = (
            await session.exec(select(Device).where(Device.device_id == "plant-a-node"))
        ).one()

    assert device.last_seen == datetime(2026, 5, 4, 0, 1, tzinfo=UTC)
    assert str(device.ip) == "192.168.1.102"
    assert device.firmware_version == "0.1.5"
    assert device.uptime_ms == 4321
