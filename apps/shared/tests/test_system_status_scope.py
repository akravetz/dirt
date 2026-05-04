from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Device
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
        plant_a.last_seen = T0
        humidifier = (
            await session.exec(
                select(Device).where(Device.device_id == "govee-h7142-main")
            )
        ).one()
        humidifier.last_seen = T0
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
