"""Scoped telemetry ownership tests."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import ReadingsService
from dirt_shared.testing import create_test_capability, create_test_device


async def test_default_history_excludes_same_metric_from_breeding_tent(app_engine):
    readings = ReadingsService(app_engine)
    await readings.ingest_reading(
        {"temperature_f": 72.0},
        source=SensorSource.MOCK,
        device_id="fan-controller",
    )

    async with AsyncSession(app_engine) as session:
        device = await create_test_device(
            session,
            tent_id="breeding",
            zone_id="canopy",
            device_id="test-breeding-reading-node",
            name="Test breeding reading node",
        )
        capability = await create_test_capability(
            session,
            device=device,
            capability_id="temperature_f",
            name="Temperature F",
            unit="degF",
        )
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
        wifi_rssi_dbm=-74,
        wifi_reconnect_count=4,
        wifi_driver_reset_count=1,
        wifi_disconnect_reason=200,
        wifi_disconnected_for_ms=0,
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
    assert device.wifi_rssi_dbm == -74
    assert device.wifi_reconnect_count == 4
    assert device.wifi_driver_reset_count == 1
    assert device.wifi_disconnect_reason == 200
    assert device.wifi_disconnected_for_ms == 0


async def test_auto_calibration_updated_at_tracks_extrema_changes(app_engine):
    timestamps = [
        datetime(2026, 5, 4, 0, 0, tzinfo=UTC),
        datetime(2026, 5, 4, 0, 1, tzinfo=UTC),
        datetime(2026, 5, 4, 0, 2, tzinfo=UTC),
        datetime(2026, 5, 4, 0, 3, tzinfo=UTC),
    ]
    clock_index = 0

    def clock() -> datetime:
        return timestamps[clock_index]

    readings = ReadingsService(app_engine, clock=clock)

    async def ingest(value: float) -> SensorCalibration:
        await readings.ingest_reading(
            {"soil_moisture_raw": value},
            source=SensorSource.ESP32,
            site_id="homebox",
            tent_id="main",
            zone_id="plant-a",
            device_id="plant-a-node",
        )
        async with AsyncSession(app_engine) as session:
            return (
                await session.exec(
                    select(SensorCalibration)
                    .join(
                        Capability,
                        Capability.id == SensorCalibration.capability_id,
                    )
                    .join(Device, Device.id == Capability.device_id)
                    .where(Device.device_id == "plant-a-node")
                    .where(SensorCalibration.metric == "soil_moisture_raw")
                )
            ).one()

    cal = await ingest(2500.0)
    assert cal.raw_low == 2500.0
    assert cal.raw_high == 2500.0
    assert cal.updated_at == timestamps[0]

    clock_index = 1
    cal = await ingest(2400.0)
    assert cal.raw_low == 2400.0
    assert cal.raw_high == 2500.0
    assert cal.updated_at == timestamps[1]

    clock_index = 2
    cal = await ingest(2450.0)
    assert cal.raw_low == 2400.0
    assert cal.raw_high == 2500.0
    assert cal.updated_at == timestamps[1]

    clock_index = 3
    cal = await ingest(2600.0)
    assert cal.raw_low == 2400.0
    assert cal.raw_high == 2600.0
    assert cal.updated_at == timestamps[3]


async def test_touch_device_updates_device_heartbeat(app_engine):
    readings = ReadingsService(
        app_engine, clock=lambda: datetime(2026, 5, 4, 0, 1, tzinfo=UTC)
    )

    await readings.touch_device(
        device_id="plant-a-node",
        ip="192.168.1.102",
        firmware_version="0.1.5",
        uptime_ms=4321,
        wifi_rssi_dbm=-81,
        wifi_reconnect_count=9,
        wifi_driver_reset_count=2,
        wifi_disconnect_reason=201,
        wifi_disconnected_for_ms=30000,
    )

    async with AsyncSession(app_engine) as session:
        device = (
            await session.exec(select(Device).where(Device.device_id == "plant-a-node"))
        ).one()

    assert device.last_seen == datetime(2026, 5, 4, 0, 1, tzinfo=UTC)
    assert str(device.ip) == "192.168.1.102"
    assert device.firmware_version == "0.1.5"
    assert device.uptime_ms == 4321
    assert device.wifi_rssi_dbm == -81
    assert device.wifi_reconnect_count == 9
    assert device.wifi_driver_reset_count == 2
    assert device.wifi_disconnect_reason == 201
    assert device.wifi_disconnected_for_ms == 30000


async def test_touch_device_without_wifi_telemetry_clears_stale_values(app_engine):
    readings = ReadingsService(
        app_engine, clock=lambda: datetime(2026, 5, 4, 0, 2, tzinfo=UTC)
    )

    await readings.touch_device(
        device_id="plant-a-node",
        wifi_rssi_dbm=-81,
        wifi_reconnect_count=9,
        wifi_driver_reset_count=2,
        wifi_disconnect_reason=201,
        wifi_disconnected_for_ms=30000,
    )
    await readings.touch_device(device_id="plant-a-node", uptime_ms=5000)

    async with AsyncSession(app_engine) as session:
        device = (
            await session.exec(select(Device).where(Device.device_id == "plant-a-node"))
        ).one()

    assert device.uptime_ms == 5000
    assert device.wifi_rssi_dbm is None
    assert device.wifi_reconnect_count is None
    assert device.wifi_driver_reset_count is None
    assert device.wifi_disconnect_reason is None
    assert device.wifi_disconnected_for_ms is None
