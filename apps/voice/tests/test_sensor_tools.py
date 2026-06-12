from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorSource
from dirt_shared.models.grow_run import GrowRun
from dirt_shared.models.plant import Plant, PlantMetricStream
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.models.site import Site
from dirt_shared.services.readings import ReadingsService
from dirt_voice.tools.sensors import build_sensor_tools


class _FakeGrow:
    async def current_targets(self) -> dict[str, tuple[float, float]]:
        return {
            "temperature_f": (70.0, 85.0),
            "humidity_pct": (40.0, 65.0),
            "vpd_kpa": (0.8, 1.4),
        }


async def _capability_id(
    session: AsyncSession, *, device_id: str, capability_id: str
) -> int:
    cap_id = (
        await session.exec(
            select(Capability.id)
            .join(Device, Device.id == Capability.device_id)
            .where(Device.device_id == device_id)
            .where(Capability.capability_id == capability_id)
        )
    ).one()
    return cap_id


async def _map_plant_moisture_stream(
    session: AsyncSession,
    *,
    plant_id: str,
    device_id: str,
    capability_id: str,
    metric_name: str,
    unit: str,
) -> int:
    site_pk = (
        await session.exec(select(Site.id).where(Site.site_id == "homebox"))
    ).one()
    grow = (
        await session.exec(
            select(GrowRun)
            .where(GrowRun.site_id == site_pk)
            .where(GrowRun.is_current.is_(True))
            .limit(1)
        )
    ).one()
    device = Device(
        site_id=site_pk,
        tent_id=grow.tent_id,
        device_id=device_id,
        name=device_id,
        kind="moisture_node",
        controller="test",
    )
    session.add(device)
    await session.flush()
    capability = Capability(
        device_id=device.id,
        capability_id=capability_id,
        name=capability_id,
        kind="measurement",
        metric_name=metric_name,
        unit=unit,
        source="test",
    )
    session.add(capability)
    await session.flush()
    plant = (
        await session.exec(
            select(Plant)
            .where(Plant.growrun_id == grow.id)
            .where(Plant.plant_id == plant_id)
        )
    ).one()
    session.add(PlantMetricStream(plant_id=plant.id, capability_id=capability.id))
    await session.flush()
    assert capability.id is not None
    return capability.id


async def test_current_status_reads_scoped_tent_and_plant_capabilities(
    app_engine,
) -> None:
    now = datetime(2026, 5, 4, 20, 0, tzinfo=UTC)
    async with AsyncSession(app_engine) as session:
        tent_caps = {
            metric: await _capability_id(
                session, device_id="fan-controller", capability_id=metric
            )
            for metric in ("temperature_f", "humidity_pct", "vpd_kpa", "dew_point_f")
        }
        plant_cap = await _map_plant_moisture_stream(
            session,
            plant_id="a",
            device_id="test-plant-a-direct-moisture",
            capability_id="soil_moisture_pct",
            metric_name="soil_moisture_pct",
            unit="%",
        )
        for metric, value in {
            "temperature_f": 78.0,
            "humidity_pct": 52.0,
            "vpd_kpa": 1.1,
            "dew_point_f": 58.0,
        }.items():
            session.add(
                SensorReading(
                    ts=now,
                    capability_id=tent_caps[metric],
                    metric=metric,
                    value=value,
                    source=SensorSource.MOCK,
                )
            )
        session.add(
            SensorReading(
                ts=now - timedelta(seconds=5),
                capability_id=plant_cap,
                metric="soil_moisture_pct",
                value=60.0,
                source=SensorSource.MOCK,
            )
        )
        await session.commit()

    tools = build_sensor_tools(
        engine=app_engine,
        readings=ReadingsService(app_engine, clock=lambda: now),
        grow=_FakeGrow(),
        clock=lambda: now,
    )
    current_status = next(tool for tool in tools if tool.name == "get_current_status")

    result = await current_status.handler()

    assert result["readings"]["temperature_f"] == 78.0
    assert result["readings"]["humidity_pct"] == 52.0
    assert result["soil_moisture_pct"]["a"] == 60.0
    assert result["out_of_range"] == []


async def test_current_status_omits_raw_plant_moisture(
    app_engine,
) -> None:
    now = datetime(2026, 5, 4, 20, 0, tzinfo=UTC)
    async with AsyncSession(app_engine) as session:
        plant_cap = await _map_plant_moisture_stream(
            session,
            plant_id="a",
            device_id="test-plant-a-raw-moisture",
            capability_id="soil_moisture_raw",
            metric_name="soil_moisture_raw",
            unit="raw",
        )
        session.add(
            SensorReading(
                ts=now - timedelta(seconds=5),
                capability_id=plant_cap,
                metric="soil_moisture_raw",
                value=400.0,
                source=SensorSource.MOCK,
            )
        )
        await session.commit()

    tools = build_sensor_tools(
        engine=app_engine,
        readings=ReadingsService(app_engine, clock=lambda: now),
        grow=_FakeGrow(),
        clock=lambda: now,
    )
    current_status = next(tool for tool in tools if tool.name == "get_current_status")

    result = await current_status.handler()

    assert result["soil_moisture_pct"] == {}
