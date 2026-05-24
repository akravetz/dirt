"""Exact-MAC BLE client for AC Infinity ThermoForge controllers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakDeviceNotFoundError, BleakError

from dirt_hwd.services.thermoforge_protocol import (
    NOTIFY_CHARACTERISTIC_UUID,
    WRITE_CHARACTERISTIC_UUID,
    ThermoForgeStatus,
    build_packet,
    decode_status,
    level_body,
    off_body,
    on_body,
)

NotifyCallback = Callable[[object, bytearray], None]


class ThermoForgeError(Exception):
    """Base class for expected ThermoForge BLE failures."""


class ThermoForgeUnavailable(ThermoForgeError):
    """The configured controller cannot currently be reached or observed."""


class ThermoForgeProtocolError(ThermoForgeError):
    """The controller returned data that does not match the known protocol."""


@dataclass(frozen=True, slots=True)
class ThermoForgeBleConfig:
    mac: str
    status_timeout_s: float = 5.0


@dataclass(frozen=True, slots=True)
class ThermoForgeTarget:
    running: bool
    level: int | None = None

    def __post_init__(self) -> None:
        if self.level is not None and not 0 <= self.level <= 10:
            raise ValueError("level must be between 0 and 10")


class ThermoForgeBleBackend(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def start_notify(
        self,
        characteristic_uuid: str,
        callback: NotifyCallback,
    ) -> None: ...

    async def stop_notify(self, characteristic_uuid: str) -> None: ...

    async def write_gatt_char(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool,
    ) -> None: ...


BleakClientFactory = Callable[[str | BLEDevice], ThermoForgeBleBackend]


class _BleakBackend:
    def __init__(
        self,
        config: ThermoForgeBleConfig,
        *,
        client_factory: BleakClientFactory = BleakClient,
    ) -> None:
        self._config = config
        self._client_factory = client_factory
        self._client = client_factory(config.mac)

    async def connect(self) -> None:
        try:
            await self._client.connect()
        except BleakDeviceNotFoundError:
            self._client = self._client_factory(_bluez_cached_device(self._config.mac))
            await self._client.connect()

    async def disconnect(self) -> None:
        await self._client.disconnect()

    async def start_notify(
        self,
        characteristic_uuid: str,
        callback: NotifyCallback,
    ) -> None:
        await self._client.start_notify(characteristic_uuid, callback)

    async def stop_notify(self, characteristic_uuid: str) -> None:
        await self._client.stop_notify(characteristic_uuid)

    async def write_gatt_char(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool,
    ) -> None:
        await self._client.write_gatt_char(
            characteristic_uuid,
            data,
            response=response,
        )


def _bluez_cached_device(mac: str) -> BLEDevice:
    address = mac.upper()
    path = f"/org/bluez/hci0/dev_{address.replace(':', '_')}"
    return BLEDevice(
        address,
        address,
        details={
            "path": path,
            "props": {
                "Address": address,
                "Name": address,
            },
        },
    )


BackendFactory = Callable[[ThermoForgeBleConfig], ThermoForgeBleBackend]


class ThermoForgeBleClient:
    def __init__(
        self,
        config: ThermoForgeBleConfig,
        *,
        backend_factory: BackendFactory | None = None,
    ) -> None:
        self._config = config
        self._backend = (backend_factory or _BleakBackend)(config)
        self._sequence = 0
        self._status: ThermoForgeStatus | None = None
        self._status_received_at = 0.0
        self._status_event = asyncio.Event()
        self._notify_started = False
        self._last_protocol_error: ThermoForgeProtocolError | None = None

    async def connect(self) -> ThermoForgeStatus:
        since = monotonic()
        try:
            await self._backend.connect()
            await self._backend.start_notify(
                NOTIFY_CHARACTERISTIC_UUID,
                self._handle_notification,
            )
        except BleakError as exc:
            raise ThermoForgeUnavailable(
                f"ThermoForge controller {self._config.mac} is unavailable"
            ) from exc
        self._notify_started = True
        return await self._wait_for_status_after(since)

    async def disconnect(self) -> None:
        notify_error: BleakError | None = None
        if self._notify_started:
            try:
                await self._backend.stop_notify(NOTIFY_CHARACTERISTIC_UUID)
            except BleakError as exc:
                notify_error = exc
            finally:
                self._notify_started = False

        try:
            await self._backend.disconnect()
        except BleakError as exc:
            raise ThermoForgeUnavailable(
                f"ThermoForge controller {self._config.mac} disconnect failed"
            ) from exc
        if notify_error is not None:
            raise ThermoForgeUnavailable(
                f"ThermoForge controller {self._config.mac} notify stop failed"
            ) from notify_error

    async def read_status(self) -> ThermoForgeStatus:
        return await self._wait_for_status_after(monotonic())

    async def set_power(self, on: bool) -> ThermoForgeStatus:
        body = on_body() if on else off_body()
        return await self._write_command(body)

    async def set_level(self, level: int) -> ThermoForgeStatus:
        try:
            body = level_body(level)
        except ValueError as exc:
            raise ThermoForgeProtocolError(str(exc)) from exc
        return await self._write_command(body)

    async def reconcile(self, target: ThermoForgeTarget) -> ThermoForgeStatus:
        status = self._status or await self.read_status()

        if not target.running:
            if status.running:
                return await self.set_power(False)
            return status

        if not status.running:
            status = await self.set_power(True)
        if target.level is not None and status.level != target.level:
            status = await self.set_level(target.level)
        return status

    async def _write_command(self, body: bytes) -> ThermoForgeStatus:
        since = monotonic()
        packet = build_packet(body, self._next_sequence())
        try:
            await self._backend.write_gatt_char(
                WRITE_CHARACTERISTIC_UUID,
                packet,
                response=True,
            )
        except BleakError as exc:
            raise ThermoForgeUnavailable(
                f"ThermoForge controller {self._config.mac} write failed"
            ) from exc
        return await self._wait_for_status_after(since)

    def _handle_notification(self, _sender: object, data: bytearray) -> None:
        status = decode_status(bytes(data))
        if status is None:
            self._last_protocol_error = ThermoForgeProtocolError(
                f"unexpected ThermoForge notification length {len(data)}"
            )
            return

        self._status = status
        self._status_received_at = monotonic()
        self._last_protocol_error = None
        self._status_event.set()

    async def _wait_for_status_after(self, since: float) -> ThermoForgeStatus:
        deadline = monotonic() + self._config.status_timeout_s

        while True:
            if self._status is not None and self._status_received_at >= since:
                return self._status

            timeout = deadline - monotonic()
            if timeout <= 0:
                if self._last_protocol_error is not None:
                    raise self._last_protocol_error
                raise ThermoForgeUnavailable(
                    f"ThermoForge controller {self._config.mac} did not send status"
                )

            try:
                await asyncio.wait_for(self._status_event.wait(), timeout=timeout)
            except TimeoutError:
                continue
            finally:
                self._status_event.clear()

    def _next_sequence(self) -> int:
        sequence = self._sequence
        self._sequence = (self._sequence + 1) & 0xFFFF
        return sequence
