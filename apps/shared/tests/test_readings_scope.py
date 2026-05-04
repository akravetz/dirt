"""Scoped telemetry ownership tests."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.scope import resolve_scope


async def test_default_history_excludes_same_metric_from_breeding_tent(app_engine):
    readings = ReadingsService(app_engine)
    await readings.ingest_reading(
        SensorLocation.TENT,
        {"temperature_f": 72.0},
        source=SensorSource.MOCK,
    )

    async with AsyncSession(app_engine) as session:
        breeding = await resolve_scope(session, tent_id="breeding")
        assert breeding is not None
        node_id = (
            await session.exec(
                select(SensorNode.id).where(SensorNode.location == SensorLocation.TENT)
            )
        ).one()
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
                sensornode_id=node_id,
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
        SensorLocation.PLANT_A,
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
        node = (
            await session.exec(
                select(SensorNode).where(SensorNode.location == SensorLocation.PLANT_A)
            )
        ).one()

    assert device.last_seen == datetime(2026, 5, 4, tzinfo=UTC)
    assert str(device.ip) == "192.168.1.101"
    assert device.firmware_version == "0.2.0"
    assert device.uptime_ms == 1234
    assert node.last_seen == datetime(2026, 5, 4, tzinfo=UTC)


async def test_legacy_ingest_updates_derived_device_heartbeat(app_engine):
    readings = ReadingsService(
        app_engine, clock=lambda: datetime(2026, 5, 4, 0, 1, tzinfo=UTC)
    )

    await readings.ingest_reading(
        SensorLocation.PLANT_A,
        {"soil_moisture_raw": 1600.0},
        source=SensorSource.ESP32,
        ip="192.168.1.102",
        firmware_version="0.1.5",
        uptime_ms=4321,
    )

    async with AsyncSession(app_engine) as session:
        device = (
            await session.exec(select(Device).where(Device.device_id == "plant-a-node"))
        ).one()
        node = (
            await session.exec(
                select(SensorNode).where(SensorNode.location == SensorLocation.PLANT_A)
            )
        ).one()

    assert device.last_seen == datetime(2026, 5, 4, 0, 1, tzinfo=UTC)
    assert str(device.ip) == "192.168.1.102"
    assert device.firmware_version == "0.1.5"
    assert device.uptime_ms == 4321
    assert node.last_seen == datetime(2026, 5, 4, 0, 1, tzinfo=UTC)


async def test_touch_node_updates_derived_device_heartbeat(app_engine):
    readings = ReadingsService(
        app_engine, clock=lambda: datetime(2026, 5, 4, 0, 2, tzinfo=UTC)
    )

    await readings.touch_node(
        SensorLocation.RESERVOIR,
        ip="192.168.1.23",
        firmware_version="0.1.0",
        uptime_ms=12345,
    )

    async with AsyncSession(app_engine) as session:
        device = (
            await session.exec(
                select(Device).where(Device.device_id == "reservoir-node")
            )
        ).one()
        node = (
            await session.exec(
                select(SensorNode).where(
                    SensorNode.location == SensorLocation.RESERVOIR
                )
            )
        ).one()

    assert device.last_seen == datetime(2026, 5, 4, 0, 2, tzinfo=UTC)
    assert str(device.ip) == "192.168.1.23"
    assert device.firmware_version == "0.1.0"
    assert device.uptime_ms == 12345
    assert node.last_seen == datetime(2026, 5, 4, 0, 2, tzinfo=UTC)
