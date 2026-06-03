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
from dirt_hwd.services.kasa_schedule import (
    ScheduledKasaActuatorService,
    ScheduledKasaTarget,
)
from dirt_shared.config import ScheduledKasaConfig
from dirt_shared.models import Capability, Device, Schedule, Site, Tent
from dirt_shared.testing import create_test_capability, create_test_device

LIGHTS_ON_LOCAL_NOON = datetime(2026, 5, 4, 18, 0, tzinfo=UTC)
LIGHTS_ON_LOCAL_NOON_PLUS_ONE = datetime(2026, 5, 4, 18, 1, tzinfo=UTC)
TEST_KASA_MAC = "AA:BB:CC:DD:EE:01"
BREEDING_HEATER_DEVICE_ID = "kasa-heat-pad-breeding"
BREEDING_HEATER_CAPABILITY_ID = "power"


class _FakePlug:
    def __init__(self, stop_event: asyncio.Event, *, is_on: bool = False) -> None:
        self.is_on = is_on
        self.turn_on_calls = 0
        self.turn_off_calls = 0
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
        self.turn_off_calls += 1
        self.is_on = False
        self._stop_event.set()

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


def _config() -> ScheduledKasaConfig:
    return ScheduledKasaConfig(
        kasa_username="user",
        kasa_password="pass",
        discovery_target="255.255.255.255",
        poll_interval=30,
    )


async def _run_once(
    service: ScheduledKasaActuatorService,
    stop_event: asyncio.Event,
) -> None:
    await asyncio.wait_for(service.run(stop_event), timeout=2.0)


def _light_target(
    *,
    device_pk: int = 42,
    device_id: str | None = None,
    capability_id: str | None = None,
    schedule_id: str | None = None,
    starts_local: time,
    ends_local: time,
) -> ScheduledKasaTarget:
    return ScheduledKasaTarget(
        site_id="homebox",
        tent_id="clones",
        zone_id="lights",
        device_pk=device_pk,
        device_id=device_id or "kasa-lights-test",
        capability_id=capability_id or "lights_power",
        schedule_id=schedule_id or "lights-schedule",
        host="192.0.2.42",
        provider_uid=TEST_KASA_MAC,
        starts_local=starts_local,
        ends_local=ends_local,
        timezone="America/Denver",
    )


async def test_scheduled_kasa_service_reconciles_existing_light_schedule() -> None:
    stop_event = asyncio.Event()
    plug = _FakePlug(stop_event)
    inventory = _FakeInventory(plug)

    async def load_targets() -> list[ScheduledKasaTarget]:
        return [
            _light_target(
                device_id="kasa-lights-clones",
                capability_id="lights_power",
                schedule_id="clones-lights-photoperiod",
                starts_local=time(6, 0),
                ends_local=time(0, 0),
            )
        ]

    service = ScheduledKasaActuatorService(
        _config(),
        clock=lambda: LIGHTS_ON_LOCAL_NOON,
        target_loader=load_targets,
        inventory=inventory,
    )

    await _run_once(service, stop_event)

    assert plug.turn_on_calls == 1
    assert inventory.expected == [
        KasaExpectedDevice(
            device_id="kasa-lights-clones",
            mac=TEST_KASA_MAC,
            host="192.0.2.42",
        )
    ]


async def test_state_change_logs_schedule_kind_stream() -> None:
    stop_event = asyncio.Event()
    plug = _FakePlug(stop_event)
    inventory = _FakeInventory(plug)
    events: list[tuple[str, str, dict[str, object]]] = []

    def capture_event(stream: str, event: str, **fields: object) -> None:
        events.append((stream, event, fields))

    async def load_targets() -> list[ScheduledKasaTarget]:
        return [
            _light_target(
                device_id="kasa-lights-clones",
                capability_id="lights_power",
                schedule_id="clones-lights-photoperiod",
                starts_local=time(9, 0),
                ends_local=time(21, 0),
            )
        ]

    service = ScheduledKasaActuatorService(
        _config(),
        clock=lambda: LIGHTS_ON_LOCAL_NOON,
        target_loader=load_targets,
        inventory=inventory,
        event_logger=capture_event,
    )

    await _run_once(service, stop_event)

    assert len(events) == 1
    stream, event, fields = events[0]
    assert stream == "lights"
    assert event == "state_change"
    assert fields["site_id"] == "homebox"
    assert fields["tent_id"] == "clones"
    assert fields["zone_id"] == "lights"
    assert fields["device_id"] == "kasa-lights-clones"
    assert fields["capability_id"] == "lights_power"
    assert fields["schedule_id"] == "clones-lights-photoperiod"
    assert fields["new_state"] == "on"
    assert fields["reason"] == "scheduled_on"


async def test_default_kasa_loader_is_lights_only(app_engine) -> None:
    service = ScheduledKasaActuatorService(_config(), engine=app_engine)

    targets = await service._load_targets()

    assert targets
    assert {target.zone_id for target in targets} == {"lights"}


async def test_climate_heater_devices_keep_capabilities_without_schedules(
    app_engine,
) -> None:
    async with AsyncSession(app_engine) as session:
        rows = (
            await session.exec(
                select(Device.device_id, Capability.capability_id, Capability.enabled)
                .join(Capability, Capability.device_id == Device.id)
                .where(
                    Device.device_id.in_(
                        {
                            "ac-infinity-thermoforge-main",
                            BREEDING_HEATER_DEVICE_ID,
                        }
                    )
                )
                .order_by(Device.device_id, Capability.capability_id)
            )
        ).all()
        heater_schedules = (
            await session.exec(
                select(Schedule.schedule_id).where(Schedule.kind == "heater")
            )
        ).all()

    assert rows == [
        ("ac-infinity-thermoforge-main", "heat_level", True),
        ("ac-infinity-thermoforge-main", "power", True),
        (BREEDING_HEATER_DEVICE_ID, BREEDING_HEATER_CAPABILITY_ID, True),
    ]
    assert heater_schedules == []


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
        device.last_seen = LIGHTS_ON_LOCAL_NOON
        device_pk = device.id
        await session.commit()

    if device_pk is None:
        raise AssertionError("test device missing primary key")

    async def load_targets() -> list[ScheduledKasaTarget]:
        return [
            _light_target(
                device_pk=device_pk,
                device_id="kasa-lights-test",
                capability_id="lights_power",
                schedule_id="main-lights-photoperiod",
                starts_local=time(6, 0),
                ends_local=time(0, 0),
            )
        ]

    service = ScheduledKasaActuatorService(
        _config(),
        engine=app_engine,
        clock=lambda: LIGHTS_ON_LOCAL_NOON_PLUS_ONE,
        target_loader=load_targets,
        inventory=inventory,
    )

    await _run_once(service, stop_event)

    async with AsyncSession(app_engine) as session:
        refreshed = (
            await session.exec(
                select(Device).where(Device.device_id == "kasa-lights-test")
            )
        ).one()

    assert plug.update_calls == 1
    assert plug.turn_on_calls == 0
    assert refreshed.last_seen == LIGHTS_ON_LOCAL_NOON_PLUS_ONE


async def test_db_loader_ignores_unsuitable_schedules_and_devices(app_engine) -> None:
    async with AsyncSession(app_engine) as session:
        site_pk = (
            await session.exec(select(Site.id).where(Site.site_id == "homebox"))
        ).one()
        tent_pk = (
            await session.exec(
                select(Tent.id)
                .where(Tent.site_id == site_pk)
                .where(Tent.tent_id == "main")
            )
        ).one()

        async def add_scheduled_device(
            suffix: str,
            *,
            schedule_enabled: bool = True,
            device_enabled: bool = True,
            controller: str = "kasa",
            provider_uid_kind: str | None = "mac",
            provider_uid: str | None = "default",
            starts_local: time | None = time(0, 0),
            ends_local: time | None = time(6, 0),
            schedule_kind: str = "lights",
        ) -> None:
            device = await create_test_device(
                session,
                device_id=f"kasa-loader-{suffix}",
                tent_id="main",
                kind="actuator",
                controller=controller,
                enabled=device_enabled,
            )
            device.provider_uid_kind = provider_uid_kind
            device.provider_uid = (
                f"AA:BB:CC:DD:EE:{suffix}"
                if provider_uid == "default"
                else provider_uid
            )
            capability = await create_test_capability(
                session,
                device=device,
                capability_id=f"loader_{suffix}_power",
                kind="actuator",
                metric_name=f"loader_{suffix}_on",
                unit="bool",
                source=controller,
            )
            session.add(
                Schedule(
                    site_id=site_pk,
                    tent_id=tent_pk,
                    device_id=device.id,
                    capability_id=capability.id,
                    schedule_id=f"loader-{suffix}",
                    kind=schedule_kind,
                    starts_local=starts_local,
                    ends_local=ends_local,
                    timezone="America/Denver",
                    enabled=schedule_enabled,
                )
            )

        await add_scheduled_device("01")
        await add_scheduled_device("02", schedule_enabled=False)
        await add_scheduled_device("03", device_enabled=False)
        await add_scheduled_device("04", starts_local=None)
        await add_scheduled_device("05", ends_local=None)
        await add_scheduled_device("06", controller="manual")
        await add_scheduled_device("07", provider_uid_kind="serial")
        await add_scheduled_device("08", provider_uid=None)
        await add_scheduled_device("09", schedule_kind="heater")
        await session.commit()

    service = ScheduledKasaActuatorService(
        _config(),
        engine=app_engine,
    )

    targets = await service._load_targets()

    loader_targets = {
        target.device_id: target
        for target in targets
        if target.device_id.startswith("kasa-loader-")
    }
    assert set(loader_targets) == {"kasa-loader-01"}
    assert loader_targets["kasa-loader-01"].provider_uid == "AA:BB:CC:DD:EE:01"
