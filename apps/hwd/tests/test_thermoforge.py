from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, time
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.services.thermoforge import (
    ScheduledThermoForgeService,
    ScheduledThermoForgeTarget,
)
from dirt_hwd.services.thermoforge_ble import ThermoForgeUnavailable
from dirt_hwd.services.thermoforge_protocol import ThermoForgeStatus
from dirt_shared.config import ThermoForgeConfig
from dirt_shared.models import Capability, Device, Schedule, SensorReading, Site, Tent
from dirt_shared.models.enums import SensorSource
from dirt_shared.testing import create_test_capability, create_test_device

ACTIVE_LOCAL_0300 = datetime(2026, 5, 4, 9, 0, tzinfo=UTC)
INACTIVE_LOCAL_1500 = datetime(2026, 5, 4, 21, 0, tzinfo=UTC)
TEST_MAC_1 = "80:B5:4E:4D:27:01"
TEST_MAC_2 = "80:B5:4E:4D:27:02"


class FakeThermoForgeClient:
    def __init__(self, status: ThermoForgeStatus) -> None:
        self.status = status
        self.calls: list[str] = []
        self.disconnect_calls = 0
        self.fail_connect = False
        self.fail_power: bool | None = None
        self.power_statuses: list[ThermoForgeStatus] = []
        self.level_statuses: list[ThermoForgeStatus] = []
        self.read_statuses: list[ThermoForgeStatus] = []

    async def connect(self) -> ThermoForgeStatus:
        self.calls.append("connect")
        if self.fail_connect:
            raise ThermoForgeUnavailable("test connect failure")
        return self.status

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    async def read_status(self) -> ThermoForgeStatus:
        self.calls.append("read_status")
        if self.read_statuses:
            self.status = self.read_statuses.pop(0)
        return self.status

    async def set_power(self, on: bool) -> ThermoForgeStatus:
        self.calls.append(f"set_power:{on}")
        if self.fail_power is on:
            raise ThermoForgeUnavailable("test write failure")
        if self.power_statuses:
            self.status = self.power_statuses.pop(0)
        else:
            self.status = ThermoForgeStatus(running=on, level=self.status.level)
        return self.status

    async def set_level(self, level: int) -> ThermoForgeStatus:
        self.calls.append(f"set_level:{level}")
        if self.level_statuses:
            self.status = self.level_statuses.pop(0)
        else:
            self.status = ThermoForgeStatus(running=self.status.running, level=level)
        return self.status


class FakeReadings:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def ingest_reading(
        self,
        metrics: dict[str, float],
        **kwargs: object,
    ) -> int:
        self.calls.append({"metrics": metrics, **kwargs})
        return len(metrics)


def _config(tmp_path: Path) -> ThermoForgeConfig:
    return ThermoForgeConfig(
        night_level=4,
        poll_interval=30,
        connect_timeout_s=15,
        offline_alert_failures=2,
        state_path=tmp_path / "logs" / "heater" / "state.json",
        telegram_bot_token="test-token",
        telegram_chat_id="chat-1",
    )


def _target(
    *,
    device_id: str = "ac-infinity-thermoforge-test",
    provider_uid: str = TEST_MAC_1,
    starts_local: time = time(21, 0),
    ends_local: time = time(9, 0),
) -> ScheduledThermoForgeTarget:
    return ScheduledThermoForgeTarget(
        site_id="homebox",
        tent_id="main",
        zone_id="heat",
        device_id=device_id,
        capability_id="power",
        schedule_id=f"{device_id}-night",
        provider_uid=provider_uid,
        starts_local=starts_local,
        ends_local=ends_local,
        timezone="America/Denver",
    )


async def test_active_schedule_maps_to_on_level_four(tmp_path: Path) -> None:
    client = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    client.power_statuses = [ThermoForgeStatus(running=True, level=0)]
    events: list[tuple[str, str, dict[str, object]]] = []

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    def capture_event(stream: str, event: str, **fields: object) -> None:
        events.append((stream, event, fields))

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
        event_logger=capture_event,
    )

    await service._tick()

    assert client.calls == ["connect", "set_power:True", "set_level:4"]
    assert client.status == ThermoForgeStatus(running=True, level=4)
    assert [(stream, event) for stream, event, _fields in events] == [
        ("heater", "status_read"),
        ("heater", "command_sent"),
        ("heater", "command_sent"),
        ("heater", "state_change"),
    ]
    assert events[0][2] == {
        "site_id": "homebox",
        "tent_id": "main",
        "zone_id": "heat",
        "device_id": "ac-infinity-thermoforge-test",
        "capability_id": "power",
        "schedule_id": "ac-infinity-thermoforge-test-night",
        "running": False,
        "level": 0,
        "target_running": True,
        "target_level": 4,
    }
    assert events[1][2]["command"] == "on"
    assert "level" not in events[1][2]
    assert events[2][2]["command"] == "heat_level"
    assert events[2][2]["level"] == 4
    assert events[3][2] == {
        "site_id": "homebox",
        "tent_id": "main",
        "zone_id": "heat",
        "device_id": "ac-infinity-thermoforge-test",
        "capability_id": "power",
        "schedule_id": "ac-infinity-thermoforge-test-night",
        "previous_running": False,
        "previous_level": 0,
        "new_running": True,
        "new_level": 4,
        "reason": "scheduled_on",
    }


async def test_inactive_schedule_maps_to_off(tmp_path: Path) -> None:
    client = FakeThermoForgeClient(ThermoForgeStatus(running=True, level=4))
    events: list[tuple[str, str, dict[str, object]]] = []

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: INACTIVE_LOCAL_1500,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
        event_logger=lambda stream, event, **fields: events.append(
            (stream, event, fields)
        ),
    )

    await service._tick()

    assert client.calls == ["connect", "set_power:False"]
    assert client.status.running is False
    assert [(stream, event) for stream, event, _fields in events] == [
        ("heater", "status_read"),
        ("heater", "command_sent"),
        ("heater", "state_change"),
    ]
    assert events[1][2]["command"] == "off"
    assert "level" not in events[1][2]
    assert events[2][2]["new_running"] is False
    assert events[2][2]["new_level"] == 0


async def test_no_write_when_live_status_already_matches_target(tmp_path: Path) -> None:
    client = FakeThermoForgeClient(ThermoForgeStatus(running=True, level=4))
    events: list[tuple[str, str, dict[str, object]]] = []

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
        event_logger=lambda stream, event, **fields: events.append(
            (stream, event, fields)
        ),
    )

    await service._tick()

    assert client.calls == ["connect"]
    assert [(stream, event) for stream, event, _fields in events] == [
        ("heater", "status_read")
    ]


async def test_on_reconciliation_writes_power_on_before_level(tmp_path: Path) -> None:
    client = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=2))
    client.power_statuses = [ThermoForgeStatus(running=True, level=2)]
    client.level_statuses = [ThermoForgeStatus(running=True, level=4)]

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
    )

    await service._tick()

    assert client.calls == ["connect", "set_power:True", "set_level:4"]


async def test_waits_for_ramping_status_after_level_command(tmp_path: Path) -> None:
    client = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    client.power_statuses = [ThermoForgeStatus(running=True, level=0)]
    client.level_statuses = [ThermoForgeStatus(running=True, level=2)]
    client.read_statuses = [ThermoForgeStatus(running=True, level=4)]

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
    )

    await service._tick()

    assert client.calls == [
        "connect",
        "set_power:True",
        "set_level:4",
        "read_status",
    ]
    assert client.disconnect_calls == 0
    assert client.status == ThermoForgeStatus(running=True, level=4)


async def test_post_write_status_must_match_target(tmp_path: Path) -> None:
    client = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    client.power_statuses = [ThermoForgeStatus(running=True, level=0)]
    client.level_statuses = [ThermoForgeStatus(running=True, level=3)]

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    service = ScheduledThermoForgeService(
        replace(_config(tmp_path), connect_timeout_s=0),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
    )

    await service._tick()

    assert client.calls == ["connect", "set_power:True", "set_level:4"]
    assert client.disconnect_calls == 1


async def test_target_failure_does_not_shutdown_off_or_crash_whole_tick(
    tmp_path: Path,
) -> None:
    failing = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    failing.fail_power = True
    succeeding = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    succeeding.power_statuses = [ThermoForgeStatus(running=True, level=0)]
    clients = {TEST_MAC_1: failing, TEST_MAC_2: succeeding}

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [
            _target(device_id="thermoforge-failing", provider_uid=TEST_MAC_1),
            _target(device_id="thermoforge-succeeding", provider_uid=TEST_MAC_2),
        ]

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda mac: clients[mac],
    )

    await service._tick()

    assert failing.calls == ["connect", "set_power:True"]
    assert "set_power:False" not in failing.calls
    assert failing.disconnect_calls == 1
    assert succeeding.calls == ["connect", "set_power:True", "set_level:4"]


async def test_single_failure_logs_poll_failed_without_offline_alert(
    tmp_path: Path,
) -> None:
    alerts: list[str] = []
    events: list[tuple[str, str, dict[str, object]]] = []
    client = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    client.fail_connect = True

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    async def announce(text: str) -> None:
        alerts.append(text)

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
        announcer=announce,
        event_logger=lambda stream, event, **fields: events.append(
            (stream, event, fields)
        ),
    )

    await service._tick()

    assert alerts == []
    assert client.disconnect_calls == 1
    assert [(stream, event) for stream, event, _fields in events] == [
        ("heater", "poll_failed")
    ]
    assert events[0][2]["consecutive_failures"] == 1
    assert events[0][2]["offline_alert_failures"] == 2
    assert events[0][2]["will_mark_offline"] is False
    assert not _config(tmp_path).state_path.exists()


async def test_repeated_failures_send_one_offline_alert_and_persist_state(
    tmp_path: Path,
) -> None:
    clients: list[FakeThermoForgeClient] = []
    alerts: list[str] = []
    events: list[tuple[str, str, dict[str, object]]] = []

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    async def announce(text: str) -> None:
        alerts.append(text)

    def create_client(_mac: str) -> FakeThermoForgeClient:
        client = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
        client.fail_connect = True
        clients.append(client)
        return client

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=create_client,
        announcer=announce,
        event_logger=lambda stream, event, **fields: events.append(
            (stream, event, fields)
        ),
    )

    await service._tick()
    await service._tick()

    assert len(clients) == 2
    assert [client.disconnect_calls for client in clients] == [1, 1]
    assert len(alerts) == 1
    assert "offline" in alerts[0]
    assert [(stream, event) for stream, event, _fields in events] == [
        ("heater", "poll_failed"),
        ("heater", "poll_failed"),
        ("heater", "offline"),
    ]
    assert events[0][2]["will_mark_offline"] is False
    assert events[1][2]["will_mark_offline"] is True
    assert events[2][2]["error_type"] == "ThermoForgeUnavailable"
    assert events[2][2]["next_poll_interval_s"] == 30
    assert json.loads(_config(tmp_path).state_path.read_text()) == {
        "ac-infinity-thermoforge-test": "offline"
    }


async def test_recovery_sends_one_recovery_alert(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_path.write_text(json.dumps({"ac-infinity-thermoforge-test": "offline"}))
    alerts: list[str] = []
    events: list[tuple[str, str, dict[str, object]]] = []
    client = FakeThermoForgeClient(ThermoForgeStatus(running=True, level=4))

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    async def announce(text: str) -> None:
        alerts.append(text)

    service = ScheduledThermoForgeService(
        cfg,
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
        announcer=announce,
        event_logger=lambda stream, event, **fields: events.append(
            (stream, event, fields)
        ),
    )

    await service._tick()
    await service._tick()

    assert alerts == [
        "OK: <b>ac-infinity-thermoforge-test</b> ThermoForge controller back online"
    ]
    assert [(stream, event) for stream, event, _fields in events] == [
        ("heater", "status_read"),
        ("heater", "recovered"),
        ("heater", "status_read"),
    ]
    assert events[1][2]["running"] is True
    assert events[1][2]["level"] == 4
    assert json.loads(cfg.state_path.read_text()) == {
        "ac-infinity-thermoforge-test": "online"
    }


async def test_recovery_logs_verified_post_reconcile_status(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_path.write_text(json.dumps({"ac-infinity-thermoforge-test": "offline"}))
    events: list[tuple[str, str, dict[str, object]]] = []
    client = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    client.power_statuses = [ThermoForgeStatus(running=True, level=0)]

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    service = ScheduledThermoForgeService(
        cfg,
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
        announcer=lambda _text: _noop(),
        event_logger=lambda stream, event, **fields: events.append(
            (stream, event, fields)
        ),
    )

    await service._tick()

    recovered = [fields for _stream, event, fields in events if event == "recovered"]

    assert client.calls == ["connect", "set_power:True", "set_level:4"]
    assert recovered == [
        {
            "site_id": "homebox",
            "tent_id": "main",
            "zone_id": "heat",
            "device_id": "ac-infinity-thermoforge-test",
            "capability_id": "power",
            "running": True,
            "level": 4,
        }
    ]


async def test_records_actuator_readings_with_ac_infinity_source(
    tmp_path: Path,
) -> None:
    client = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    client.power_statuses = [ThermoForgeStatus(running=True, level=0)]
    readings = FakeReadings()

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
        readings=readings,
        event_logger=lambda *_args, **_kwargs: None,
    )

    await service._tick()

    assert readings.calls == [
        {
            "metrics": {"heater_on": 0.0, "heater_heat_level": 0.0},
            "device_id": "ac-infinity-thermoforge-test",
            "source": SensorSource.AC_INFINITY,
            "site_id": "homebox",
            "tent_id": "main",
            "zone_id": "heat",
        },
        {
            "metrics": {"heater_on": 1.0, "heater_heat_level": 4.0},
            "device_id": "ac-infinity-thermoforge-test",
            "source": SensorSource.AC_INFINITY,
            "site_id": "homebox",
            "tent_id": "main",
            "zone_id": "heat",
        },
    ]


async def test_records_actuator_readings_through_readings_service(
    app_engine,
    tmp_path: Path,
) -> None:
    client = FakeThermoForgeClient(ThermoForgeStatus(running=True, level=4))

    async with AsyncSession(app_engine) as session:
        device = await create_test_device(
            session,
            device_id="thermoforge-reading-test",
            tent_id="main",
            zone_id="heat",
            kind="actuator",
            controller="ac_infinity_ble",
            enabled=True,
        )
        await create_test_capability(
            session,
            device=device,
            capability_id="power",
            kind="actuator",
            metric_name="heater_on",
            unit="bool",
            source="ac_infinity",
            enabled=True,
        )
        await create_test_capability(
            session,
            device=device,
            capability_id="heat_level",
            kind="actuator",
            metric_name="heater_heat_level",
            unit="level",
            source="ac_infinity",
            enabled=True,
        )
        await session.commit()

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target(device_id="thermoforge-reading-test")]

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        engine=app_engine,
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
        event_logger=lambda *_args, **_kwargs: None,
    )

    await service._tick()

    async with AsyncSession(app_engine) as session:
        rows = (
            await session.exec(
                select(
                    Capability.metric_name, SensorReading.value, SensorReading.source
                )
                .join(SensorReading, SensorReading.capability_id == Capability.id)
                .join(Device, Device.id == Capability.device_id)
                .where(Device.device_id == "thermoforge-reading-test")
                .where(Capability.metric_name.in_({"heater_on", "heater_heat_level"}))
                .order_by(Capability.metric_name)
            )
        ).all()

    assert rows == [
        ("heater_heat_level", 4.0, SensorSource.AC_INFINITY),
        ("heater_on", 1.0, SensorSource.AC_INFINITY),
    ]


async def test_persisted_offline_state_suppresses_restart_spam(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_path.write_text(json.dumps({"ac-infinity-thermoforge-test": "offline"}))
    alerts: list[str] = []
    client = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    client.fail_connect = True

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    async def announce(text: str) -> None:
        alerts.append(text)

    service = ScheduledThermoForgeService(
        cfg,
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=lambda _mac: client,
        announcer=announce,
    )

    await service._tick()

    assert alerts == []
    assert client.disconnect_calls == 1
    assert json.loads(cfg.state_path.read_text()) == {
        "ac-infinity-thermoforge-test": "offline"
    }


async def test_failed_client_is_removed_and_recreated_on_next_tick(
    tmp_path: Path,
) -> None:
    first = FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))
    first.fail_connect = True
    second = FakeThermoForgeClient(ThermoForgeStatus(running=True, level=4))
    clients = [first, second]
    cached: dict[str, FakeThermoForgeClient] = {}

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return [_target()]

    def create_client(_mac: str) -> FakeThermoForgeClient:
        return clients.pop(0)

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        clock=lambda: ACTIVE_LOCAL_0300,
        target_loader=load_targets,
        client_factory=create_client,
        announcer=lambda _text: _noop(),
    )

    await service._tick(cached)
    await service._tick(cached)

    assert first.calls == ["connect"]
    assert first.disconnect_calls == 1
    assert second.calls == ["connect"]
    assert cached == {TEST_MAC_1: second}


async def _noop() -> None:
    return None


async def test_db_loader_loads_all_enabled_ac_infinity_ble_heater_schedules(
    app_engine,
    tmp_path: Path,
) -> None:
    async with AsyncSession(app_engine) as session:
        seeded_heaters = (
            await session.exec(select(Schedule).where(Schedule.kind == "heater"))
        ).all()
        for schedule in seeded_heaters:
            schedule.enabled = False
            session.add(schedule)

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
            controller: str = "ac_infinity_ble",
            provider_uid_kind: str | None = "mac",
            provider_uid: str | None = "default",
            starts_local: time | None = time(21, 0),
            ends_local: time | None = time(9, 0),
            capability_enabled: bool = True,
        ) -> None:
            device = await create_test_device(
                session,
                device_id=f"thermoforge-loader-{suffix}",
                tent_id="main",
                zone_id="heat",
                kind="actuator",
                controller=controller,
                enabled=device_enabled,
            )
            device.provider_uid_kind = provider_uid_kind
            device.provider_uid = (
                f"80:B5:4E:4D:27:{suffix}"
                if provider_uid == "default"
                else provider_uid
            )
            capability = await create_test_capability(
                session,
                device=device,
                capability_id="power",
                kind="actuator",
                metric_name=f"loader_{suffix}_heater_on",
                unit="bool",
                source=controller,
                enabled=capability_enabled,
            )
            session.add(
                Schedule(
                    site_id=site_pk,
                    tent_id=tent_pk,
                    device_id=device.id,
                    capability_id=capability.id,
                    schedule_id=f"thermoforge-loader-{suffix}",
                    kind="heater",
                    starts_local=starts_local,
                    ends_local=ends_local,
                    timezone="America/Denver",
                    enabled=schedule_enabled,
                )
            )

        await add_scheduled_device("01")
        await add_scheduled_device("02")
        await add_scheduled_device("03", schedule_enabled=False)
        await add_scheduled_device("04", device_enabled=False)
        await add_scheduled_device("05", controller="kasa")
        await add_scheduled_device("06", provider_uid_kind="serial")
        await add_scheduled_device("07", provider_uid=None)
        await add_scheduled_device("08", starts_local=None)
        await add_scheduled_device("09", ends_local=None)
        await add_scheduled_device("10", capability_enabled=False)
        await session.commit()

    service = ScheduledThermoForgeService(_config(tmp_path), engine=app_engine)

    targets = await service._load_targets()

    assert [target.device_id for target in targets] == [
        "thermoforge-loader-01",
        "thermoforge-loader-02",
    ]
    assert [target.provider_uid for target in targets] == [
        "80:B5:4E:4D:27:01",
        "80:B5:4E:4D:27:02",
    ]


async def test_tick_idles_cleanly_when_no_targets(tmp_path: Path) -> None:
    clients_created: list[str] = []

    async def load_targets() -> list[ScheduledThermoForgeTarget]:
        return []

    def create_client(mac: str) -> FakeThermoForgeClient:
        clients_created.append(mac)
        return FakeThermoForgeClient(ThermoForgeStatus(running=False, level=0))

    service = ScheduledThermoForgeService(
        _config(tmp_path),
        target_loader=load_targets,
        client_factory=create_client,
    )

    await service._tick()

    assert clients_created == []
