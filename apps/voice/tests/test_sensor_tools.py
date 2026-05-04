from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import ReadingsService
from dirt_voice.tools.sensors import build_sensor_tools


class _FakeGrow:
    async def current_targets(self) -> dict[str, tuple[float, float]]:
        return {
            "temperature_f": (70.0, 85.0),
            "humidity_pct": (40.0, 65.0),
            "vpd_kpa": (0.8, 1.4),
        }


async def _node_id(session: AsyncSession, location: SensorLocation) -> int:
    node_id = (
        await session.exec(select(SensorNode.id).where(SensorNode.location == location))
    ).one()
    return node_id


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


async def test_current_status_reads_scoped_tent_and_plant_capabilities(
    app_engine,
) -> None:
    now = datetime(2026, 5, 4, 20, 0, tzinfo=UTC)
    async with AsyncSession(app_engine) as session:
        tent_node = await _node_id(session, SensorLocation.TENT)
        plant_node = await _node_id(session, SensorLocation.PLANT_A)
        tent_caps = {
            metric: await _capability_id(
                session, device_id="fan-controller", capability_id=metric
            )
            for metric in ("temperature_f", "humidity_pct", "vpd_kpa", "dew_point_f")
        }
        plant_cap = await _capability_id(
            session, device_id="plant-a-node", capability_id="soil_moisture_raw"
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
                    sensornode_id=tent_node,
                    capability_id=tent_caps[metric],
                    metric=metric,
                    value=value,
                    source=SensorSource.MOCK,
                )
            )
        session.add(
            SensorCalibration(
                capability_id=plant_cap,
                metric="soil_moisture_raw",
                raw_low=0,
                raw_high=1000,
            )
        )
        session.add(
            SensorReading(
                ts=now - timedelta(seconds=5),
                sensornode_id=plant_node,
                capability_id=plant_cap,
                metric="soil_moisture_raw",
                value=400,
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
