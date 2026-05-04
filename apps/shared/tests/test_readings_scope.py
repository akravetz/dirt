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
