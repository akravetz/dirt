from __future__ import annotations

from typing import Any

import pytest
from bleak.backends.device import BLEDevice
from bleak.exc import BleakDeviceNotFoundError

from dirt_hwd.services import thermoforge_ble
from dirt_hwd.services.thermoforge_ble import ThermoForgeBleConfig


@pytest.mark.asyncio
async def test_bleak_backend_falls_back_to_bluez_cached_device() -> None:
    clients: list[FakeBleakClient] = []

    def create_client(address_or_device: str | BLEDevice) -> FakeBleakClient:
        client = FakeBleakClient(address_or_device)
        clients.append(client)
        return client

    backend = thermoforge_ble._BleakBackend(
        ThermoForgeBleConfig(mac="80:B5:4E:4D:27:CA"),
        client_factory=create_client,
    )

    await backend.connect()

    assert clients[0].address_or_device == "80:B5:4E:4D:27:CA"
    cached = clients[1].address_or_device
    assert isinstance(cached, BLEDevice)
    assert cached.address == "80:B5:4E:4D:27:CA"
    assert cached.details["path"] == "/org/bluez/hci0/dev_80_B5_4E_4D_27_CA"
    assert clients[1].connected is True


class FakeBleakClient:
    def __init__(self, address_or_device: str | BLEDevice) -> None:
        self.address_or_device = address_or_device
        self.connected = False

    async def connect(self) -> None:
        if isinstance(self.address_or_device, str):
            raise BleakDeviceNotFoundError(
                self.address_or_device,
                f"Device with address {self.address_or_device} was not found.",
            )
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def start_notify(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def stop_notify(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def write_gatt_char(self, *_args: Any, **_kwargs: Any) -> None:
        return None
