from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.services.kasa_inventory import (
    KasaExpectedDevice,
    KasaObservation,
    KasaVerifiedDevice,
)
from dirt_hwd.services.lights import LightScheduleTarget, LightsLoopService
from dirt_shared.config import LightsConfig
from dirt_shared.models import Device
from dirt_shared.testing import create_test_device

T0 = datetime(2026, 5, 4, 18, 0, tzinfo=UTC)
T1 = datetime(2026, 5, 4, 18, 1, tzinfo=UTC)
TEST_KASA_MAC = "AA:BB:CC:DD:EE:01"


class _FakePlug:
    def __init__(self, stop_event: asyncio.Event, *, is_on: bool = False) -> None:
        self.is_on = is_on
        self.turn_on_calls = 0
        self.update_calls = 0
        self._stop_event = stop_event

    async def update(self) -> None:
        self.update_calls += 1
        self._stop_event.set()
        return None

    async def turn_on(self) -> None:
        self.turn_on_calls += 1
        self.is_on = True
        self._stop_event.set()

    async def turn_off(self) -> None:
        raise AssertionError("expected turn_on, got turn_off")

    async def disconnect(self) -> None:
        return None


class _FakeInventory:
    def __init__(self, plug: _FakePlug) -> None:
        self.plug = plug
        self.expected: list[KasaExpectedDevice] = []

    async def connect_verified(
        self,
        expected: KasaExpectedDevice,
    ) -> KasaVerifiedDevice | None:
        self.expected.append(expected)
        return KasaVerifiedDevice(
            device=self.plug,
            observation=KasaObservation(
                host="192.0.2.42",
                mac=expected.mac,
                alias="test-light",
                model="EP10",
                hardware_version="1.0",
                firmware_version="1.1.1",
                rssi=-50,
            ),
        )


async def test_lights_loop_reconciles_db_known_schedule() -> None:
    stop_event = asyncio.Event()
    plug = _FakePlug(stop_event)
    inventory = _FakeInventory(plug)

    async def load_targets() -> list[LightScheduleTarget]:
        return [
            LightScheduleTarget(
                site_id="homebox",
                tent_id="clones",
                zone_id="lights",
                device_pk=42,
                device_id="kasa-lights-clones",
                capability_id="lights_power",
                schedule_id="clones-lights-photoperiod",
                host="192.0.2.42",
                provider_uid="10:5A:95:8B:E8:B7",
                starts_local=time(6, 0),
                ends_local=time(0, 0),
                timezone="America/Denver",
            )
        ]

    service = LightsLoopService(
        LightsConfig(
            kasa_username="user",
            kasa_password="pass",
            discovery_target="255.255.255.255",
            poll_interval=30,
        ),
        clock=lambda: T0,
        target_loader=load_targets,
        inventory=inventory,
    )

    await asyncio.wait_for(service.run(stop_event), timeout=2.0)

    assert plug.turn_on_calls == 1
    assert inventory.expected == [
        KasaExpectedDevice(
            device_id="kasa-lights-clones",
            mac="10:5A:95:8B:E8:B7",
            host="192.0.2.42",
        )
    ]


async def test_successful_kasa_poll_refreshes_last_seen(app_engine) -> None:
    stop_event = asyncio.Event()
    plug = _FakePlug(stop_event, is_on=True)
    inventory = _FakeInventory(plug)

    async with AsyncSession(app_engine) as session:
        device = await create_test_device(
            session,
            device_id="kasa-lights-test",
            tent_id="main",
            zone_id="lights",
            kind="actuator",
            controller="kasa",
        )
        device.ip = "192.0.2.42"
        device.provider_uid_kind = "mac"
        device.provider_uid = TEST_KASA_MAC
        device.last_seen = T0
        device_pk = device.id
        await session.commit()

    if device_pk is None:
        raise AssertionError("test device missing primary key")

    async def load_targets() -> list[LightScheduleTarget]:
        return [
            LightScheduleTarget(
                site_id="homebox",
                tent_id="main",
                zone_id="lights",
                device_pk=device_pk,
                device_id="kasa-lights-test",
                capability_id="lights_power",
                schedule_id="main-lights-photoperiod",
                host="192.0.2.42",
                provider_uid=TEST_KASA_MAC,
                starts_local=time(6, 0),
                ends_local=time(0, 0),
                timezone="America/Denver",
            )
        ]

    service = LightsLoopService(
        LightsConfig(
            kasa_username="user",
            kasa_password="pass",
            discovery_target="255.255.255.255",
            poll_interval=30,
        ),
        engine=app_engine,
        clock=lambda: T1,
        target_loader=load_targets,
        inventory=inventory,
    )

    await asyncio.wait_for(service.run(stop_event), timeout=2.0)

    async with AsyncSession(app_engine) as session:
        refreshed = (
            await session.exec(
                select(Device).where(Device.device_id == "kasa-lights-test")
            )
        ).one()

    assert plug.update_calls == 1
    assert plug.turn_on_calls == 0
    assert refreshed.last_seen == T1
