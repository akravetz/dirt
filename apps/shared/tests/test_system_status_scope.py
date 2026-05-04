from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.system_status import SystemStatusService

T0 = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)


async def test_system_status_uses_device_table_projection(
    app_engine,
) -> None:
    async with AsyncSession(app_engine) as session:
        plant_a = (
            await session.exec(select(Device).where(Device.device_id == "plant-a-node"))
        ).one()
        plant_a.name = "Renamed Plant A Node"

        node = (
            await session.exec(
                select(SensorNode).where(SensorNode.location == SensorLocation.PLANT_A)
            )
        ).one()
        node.last_seen = T0

        humidifier_cap = (
            await session.exec(
                select(Capability)
                .join(Device, Device.id == Capability.device_id)
                .where(Device.device_id == "govee-h7142-main")
                .where(Capability.capability_id == "humidifier_on")
            )
        ).one()
        assert humidifier_cap.id is not None
        tent_node = (
            await session.exec(
                select(SensorNode).where(SensorNode.location == SensorLocation.TENT)
            )
        ).one()
        assert tent_node.id is not None
        session.add(
            SensorReading(
                ts=T0 - timedelta(seconds=30),
                sensornode_id=tent_node.id,
                capability_id=humidifier_cap.id,
                metric="humidifier_on",
                value=1.0,
                source=SensorSource.GOVEE,
            )
        )
        await session.commit()

    service = SystemStatusService(
        app_engine,
        clock=lambda: T0,
        camera_rpc=lambda *_args: {"_status": "ok", "camera_connected": True},
        service_active_check=lambda _unit: True,
    )
    statuses = await service.get_device_statuses()

    assert [status.device_id for status in statuses] == [
        "fan-controller",
        "plant-a-node",
        "plant-b-node",
        "plant-c-node",
        "plant-d-node",
        "govee-h7142-main",
        "obsbot-main",
        "jabra-claudia",
    ]
    assert "reservoir-node" not in {status.device_id for status in statuses}
    assert "kasa-lights-main" not in {status.device_id for status in statuses}
    renamed = next(status for status in statuses if status.device_id == "plant-a-node")
    assert renamed.name == "Renamed Plant A Node"
    assert renamed.site_id == "homebox"
    assert renamed.tent_id == "main"
    assert renamed.zone_id == "plant-a"
    humidifier = next(
        status for status in statuses if status.device_id == "govee-h7142-main"
    )
    assert humidifier.status == "ok"
    voice = next(status for status in statuses if status.device_id == "jabra-claudia")
    assert voice.status == "listening"
    assert voice.tent_id is None
