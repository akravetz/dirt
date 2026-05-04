"""Milestone 4 scope regression tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.daily_sensors import SensorReader
from dirt_shared.services.plant_detail import PlantDetailService
from dirt_shared.services.plants import PlantsService
from dirt_shared.services.scope import resolve_scope


async def _sensor_node_id(session: AsyncSession, location: SensorLocation) -> int:
    node_id = (
        await session.exec(select(SensorNode.id).where(SensorNode.location == location))
    ).one()
    return node_id


async def _capability_pk(
    session: AsyncSession,
    *,
    device_id: str,
    capability_id: str,
) -> int:
    cap_pk = (
        await session.exec(
            select(Capability.id)
            .join(Device, Device.id == Capability.device_id)
            .where(Device.device_id == device_id)
            .where(Capability.capability_id == capability_id)
        )
    ).one()
    return cap_pk


async def _insert_breeding_soil_capability(session: AsyncSession) -> int:
    breeding = await resolve_scope(session, tent_id="breeding")
    assert breeding is not None
    device = Device(
        site_id=breeding.site_pk,
        tent_id=breeding.tent_pk,
        device_id="breeding-plant-a-node",
        name="Breeding plant A node",
        kind="moisture_node",
        controller="test",
    )
    session.add(device)
    await session.flush()
    assert device.id is not None
    cap = Capability(
        device_id=device.id,
        capability_id="soil_moisture_raw",
        name="Soil Moisture Raw",
        kind="measurement",
        metric_name="soil_moisture_raw",
        unit="raw",
        source="test",
    )
    session.add(cap)
    await session.flush()
    assert cap.id is not None
    return cap.id


async def test_breeding_without_current_grow_returns_empty_plants(
    app_engine,
    tmp_path,
) -> None:
    plants = PlantsService(app_engine, PlantDetailService(tmp_path))

    assert await plants.list_plants(tent_id="breeding") == []


async def test_main_plant_moisture_ignores_other_tent_calibration(
    app_engine,
    tmp_path,
) -> None:
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    async with AsyncSession(app_engine) as session:
        node_id = await _sensor_node_id(session, SensorLocation.PLANT_A)
        main_cap = await _capability_pk(
            session,
            device_id="plant-a-node",
            capability_id="soil_moisture_raw",
        )
        breeding_cap = await _insert_breeding_soil_capability(session)
        session.add(
            SensorCalibration(
                capability_id=main_cap,
                metric="soil_moisture_raw",
                raw_low=0,
                raw_high=1000,
            )
        )
        session.add(
            SensorCalibration(
                capability_id=breeding_cap,
                metric="soil_moisture_raw",
                raw_low=0,
                raw_high=500,
            )
        )
        session.add(
            SensorReading(
                ts=now,
                sensornode_id=node_id,
                capability_id=main_cap,
                metric="soil_moisture_raw",
                value=400,
                source=SensorSource.MOCK,
            )
        )
        session.add(
            SensorReading(
                ts=now + timedelta(seconds=1),
                sensornode_id=node_id,
                capability_id=breeding_cap,
                metric="soil_moisture_raw",
                value=400,
                source=SensorSource.MOCK,
            )
        )
        await session.commit()

    plants = PlantsService(app_engine, PlantDetailService(tmp_path))
    plant_a = next(p for p in await plants.list_plants() if p.code == "a")

    assert plant_a.moisture_pct == 60.0


async def test_daily_sensor_snapshot_uses_main_capability_calibration(
    app_engine,
) -> None:
    now = datetime(2026, 5, 4, 20, 0, tzinfo=UTC)
    async with AsyncSession(app_engine) as session:
        node_id = await _sensor_node_id(session, SensorLocation.PLANT_A)
        main_cap = await _capability_pk(
            session,
            device_id="plant-a-node",
            capability_id="soil_moisture_raw",
        )
        breeding_cap = await _insert_breeding_soil_capability(session)
        session.add(
            SensorCalibration(
                capability_id=main_cap,
                metric="soil_moisture_raw",
                raw_low=0,
                raw_high=1000,
            )
        )
        session.add(
            SensorCalibration(
                capability_id=breeding_cap,
                metric="soil_moisture_raw",
                raw_low=0,
                raw_high=500,
            )
        )
        session.add(
            SensorReading(
                ts=now,
                sensornode_id=node_id,
                capability_id=main_cap,
                metric="soil_moisture_raw",
                value=400,
                source=SensorSource.MOCK,
            )
        )
        session.add(
            SensorReading(
                ts=now + timedelta(seconds=1),
                sensornode_id=node_id,
                capability_id=breeding_cap,
                metric="soil_moisture_raw",
                value=400,
                source=SensorSource.MOCK,
            )
        )
        await session.commit()

    reader = SensorReader(app_engine, clock=lambda: now + timedelta(seconds=2))
    snap = await reader.snapshot(date(2026, 5, 4))

    assert snap.plants["a"]["now_pct"] == 60.0
