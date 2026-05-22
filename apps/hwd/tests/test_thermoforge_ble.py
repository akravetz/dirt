from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from dirt_hwd.services.thermoforge_ble import (
    ThermoForgeBleClient,
    ThermoForgeBleConfig,
    ThermoForgeProtocolError,
    ThermoForgeTarget,
    ThermoForgeUnavailable,
)
from dirt_hwd.services.thermoforge_protocol import (
    NOTIFY_CHARACTERISTIC_UUID,
    WRITE_CHARACTERISTIC_UUID,
    build_packet,
    level_body,
    off_body,
    on_body,
)

OFF_FRAME = bytes.fromhex(
    "1eff02090730004080008000800000000001f0000000ffff000100000000ffff"
    "000100000000ffff0001000000004650000100000000"
)
LEVEL_4_FRAME = bytes.fromhex(
    "1eff02090730004080008000800000001202f0000000ffff000100000000ffff"
    "000100000000ffff0001000000004650100100000000"
)


def status_frame(*, running: bool, level: int) -> bytes:
    frame = bytearray(OFF_FRAME)
    frame[16] = 0x02 if running else 0x00
    frame[17] = 0x02 if running else 0x01
    frame[48] = (frame[48] & ~0x3C) | (level << 2)
    return bytes(frame)


class FakeBackend:
    def __init__(self) -> None:
        self.connected = False
        self.notify_uuid: str | None = None
        self.notify_callback: Callable[[object, bytearray], None] | None = None
        self.stopped_notify_uuids: list[str] = []
        self.writes: list[tuple[str, bytes, bool]] = []
        self.next_write_status: bytes = LEVEL_4_FRAME
        self.write_statuses: list[bytes] = []
        self.fail_connect = False

    async def connect(self) -> None:
        if self.fail_connect:
            from bleak.exc import BleakError

            raise BleakError("not reachable")
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def start_notify(
        self,
        characteristic_uuid: str,
        callback: Callable[[object, bytearray], None],
    ) -> None:
        self.notify_uuid = characteristic_uuid
        self.notify_callback = callback
        self.emit(OFF_FRAME)

    async def stop_notify(self, characteristic_uuid: str) -> None:
        assert characteristic_uuid == NOTIFY_CHARACTERISTIC_UUID
        self.stopped_notify_uuids.append(characteristic_uuid)
        self.notify_uuid = None

    async def write_gatt_char(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool,
    ) -> None:
        self.writes.append((characteristic_uuid, data, response))
        await asyncio.sleep(0)
        if self.write_statuses:
            self.emit(self.write_statuses.pop(0))
        else:
            self.emit(self.next_write_status)

    def emit(self, data: bytes) -> None:
        assert self.notify_callback is not None
        self.notify_callback("sender", bytearray(data))


def make_client(
    backend: FakeBackend,
    *,
    status_timeout_s: float = 0.01,
) -> ThermoForgeBleClient:
    return ThermoForgeBleClient(
        ThermoForgeBleConfig(
            mac="80:B5:4E:4D:27:CA",
            status_timeout_s=status_timeout_s,
        ),
        backend_factory=lambda _config: backend,
    )


async def test_connect_subscribes_to_notify_and_waits_for_status() -> None:
    backend = FakeBackend()
    client = make_client(backend)

    status = await client.connect()

    assert backend.connected is True
    assert backend.notify_uuid == NOTIFY_CHARACTERISTIC_UUID
    assert status.running is False
    assert status.level == 0


async def test_set_power_writes_packet_and_waits_for_status() -> None:
    backend = FakeBackend()
    client = make_client(backend)
    await client.connect()

    status = await client.set_power(True)

    assert backend.writes == [
        (WRITE_CHARACTERISTIC_UUID, build_packet(on_body(), 0), True)
    ]
    assert status.running is True
    assert status.level == 4


async def test_disconnect_stops_notify_and_disconnects() -> None:
    backend = FakeBackend()
    client = make_client(backend)
    await client.connect()

    await client.disconnect()

    assert backend.stopped_notify_uuids == [NOTIFY_CHARACTERISTIC_UUID]
    assert backend.connected is False


async def test_set_level_writes_level_packet_with_next_sequence() -> None:
    backend = FakeBackend()
    client = make_client(backend)
    await client.connect()

    await client.set_power(True)
    await client.set_level(4)

    assert backend.writes[1] == (
        WRITE_CHARACTERISTIC_UUID,
        build_packet(level_body(4), 1),
        True,
    )


async def test_reconcile_turns_running_target_on_and_sets_level() -> None:
    backend = FakeBackend()
    backend.write_statuses = [status_frame(running=True, level=0), LEVEL_4_FRAME]
    client = make_client(backend)
    await client.connect()

    status = await client.reconcile(ThermoForgeTarget(running=True, level=4))

    assert [write[1] for write in backend.writes] == [
        build_packet(on_body(), 0),
        build_packet(level_body(4), 1),
    ]
    assert status.running is True
    assert status.level == 4


async def test_reconcile_turns_off_when_target_is_not_running() -> None:
    backend = FakeBackend()
    backend.next_write_status = OFF_FRAME
    client = make_client(backend)
    await client.connect()
    backend.emit(LEVEL_4_FRAME)

    status = await client.reconcile(ThermoForgeTarget(running=False))

    assert [write[1] for write in backend.writes] == [build_packet(off_body(), 0)]
    assert status.running is False
    assert status.level == 0


async def test_connect_failure_raises_unavailable() -> None:
    backend = FakeBackend()
    backend.fail_connect = True
    client = make_client(backend)

    try:
        await client.connect()
    except ThermoForgeUnavailable:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ThermoForgeUnavailable")


async def test_invalid_notification_raises_protocol_error() -> None:
    class InvalidStatusBackend(FakeBackend):
        async def start_notify(
            self,
            characteristic_uuid: str,
            callback: Callable[[object, bytearray], None],
        ) -> None:
            self.notify_uuid = characteristic_uuid
            self.notify_callback = callback
            self.emit(bytes.fromhex("a51700048b94172800031200ff0015f2"))

    client = make_client(InvalidStatusBackend())

    try:
        await client.connect()
    except ThermoForgeProtocolError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ThermoForgeProtocolError")


def test_production_backend_constructs_bleak_client_with_exact_mac(monkeypatch) -> None:
    created_with: list[str] = []

    class FakeBleakClient:
        def __init__(self, address: str) -> None:
            created_with.append(address)

    from dirt_hwd.services import thermoforge_ble

    monkeypatch.setattr(thermoforge_ble, "BleakClient", FakeBleakClient)

    ThermoForgeBleClient(ThermoForgeBleConfig(mac="AA:BB:CC:DD:EE:FF"))

    assert created_with == ["AA:BB:CC:DD:EE:FF"]


def test_production_code_does_not_import_bleak_scanner() -> None:
    source = Path("apps/hwd/src/dirt_hwd/services/thermoforge_ble.py").read_text()

    assert "BleakScanner" not in source
