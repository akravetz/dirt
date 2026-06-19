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
        substrate = (
            await session.exec(
                select(Device).where(Device.device_id == "plant-a-substrate-node")
            )
        ).one()
        substrate.name = "Renamed Plant A Substrate Node"
        substrate.last_seen = T0
        substrate.wifi_rssi_dbm = -73
        substrate.wifi_reconnect_count = 5
        substrate.wifi_driver_reset_count = 1
        substrate.wifi_disconnect_reason = 200
        substrate.wifi_disconnected_for_ms = 0
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
        "plant-a-substrate-node",
        "govee-h7142-main",
        "obsbot-main",
        "jabra-claudia",
    ]
    assert not {
        "plant-a-node",
        "plant-b-node",
        "plant-c-node",
        "plant-d-node",
    } & {status.device_id for status in statuses}
    assert "reservoir-node" not in {status.device_id for status in statuses}
    assert "kasa-lights-main" not in {status.device_id for status in statuses}
    renamed = next(
        status for status in statuses if status.device_id == "plant-a-substrate-node"
    )
    assert renamed.name == "Renamed Plant A Substrate Node"
    assert renamed.source_site_id is not None
    assert renamed.source_tent_id is not None
    assert renamed.source_zone_id is not None
    assert renamed.wifi is not None
    assert renamed.wifi.rssi_dbm == -73
    assert renamed.wifi.reconnect_count == 5
    assert renamed.wifi.driver_reset_count == 1
    assert renamed.wifi.disconnect_reason == 200
    assert renamed.wifi.disconnected_for_ms == 0
    humidifier = next(
        status for status in statuses if status.device_id == "govee-h7142-main"
    )
    assert humidifier.status == "ok"
    assert humidifier.wifi is None
    voice = next(status for status in statuses if status.device_id == "jabra-claudia")
    assert voice.status == "listening"
    assert voice.source_tent_id is None
