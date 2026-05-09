"""Verified Kasa device resolution.

The database owns device identity. Kasa discovery is only an observation layer:
we may use it to find the current IP for a known MAC, but callers must not
control an unrecognized plug just because it responds on the LAN.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from kasa import Credentials, Discover
from kasa import Device as KasaDevice

DiscoverSingle = Callable[..., Awaitable[KasaDevice | None]]
DiscoverMany = Callable[..., Awaitable[dict[str, KasaDevice]]]


@dataclass(frozen=True)
class KasaExpectedDevice:
    device_id: str
    mac: str
    host: str | None = None


@dataclass(frozen=True)
class KasaObservation:
    host: str
    mac: str
    alias: str | None
    model: str | None
    hardware_version: str | None
    firmware_version: str | None
    rssi: int | None


@dataclass(frozen=True)
class KasaVerifiedDevice:
    device: KasaDevice
    observation: KasaObservation


class KasaInventory:
    def __init__(
        self,
        *,
        credentials: Credentials,
        discovery_target: str = "255.255.255.255",
        discovery_timeout: int = 5,
        discover_single: DiscoverSingle | None = None,
        discover: DiscoverMany | None = None,
    ) -> None:
        self._credentials = credentials
        self._discovery_target = discovery_target
        self._discovery_timeout = discovery_timeout
        self._discover_single = discover_single or Discover.discover_single
        self._discover = discover or Discover.discover

    async def connect_verified(
        self,
        expected: KasaExpectedDevice,
    ) -> KasaVerifiedDevice | None:
        expected_mac = _normalize_mac(expected.mac)
        if expected.host:
            device = await self._try_host(expected.host)
            verified = await self._verify(device, expected_mac=expected_mac)
            if verified is not None:
                return verified

        devices = await self._discover(
            target=self._discovery_target,
            discovery_timeout=self._discovery_timeout,
            credentials=self._credentials,
        )
        for device in devices.values():
            verified = await self._verify(device, expected_mac=expected_mac)
            if verified is not None:
                return verified
            await _safe_disconnect(device)
        return None

    async def _try_host(self, host: str) -> KasaDevice | None:
        with contextlib.suppress(Exception):
            return await self._discover_single(
                host,
                discovery_timeout=self._discovery_timeout,
                credentials=self._credentials,
            )
        return None

    async def _verify(
        self,
        device: KasaDevice | None,
        *,
        expected_mac: str,
    ) -> KasaVerifiedDevice | None:
        if device is None:
            return None
        with contextlib.suppress(Exception):
            await device.update()
            observation = _observe(device)
            if _normalize_mac(observation.mac) == expected_mac:
                return KasaVerifiedDevice(device=device, observation=observation)
        await _safe_disconnect(device)
        return None


def _observe(device: KasaDevice) -> KasaObservation:
    hw_info = getattr(device, "hw_info", {}) or {}
    firmware = _optional_str(hw_info.get("sw_ver"))
    hardware = _optional_str(hw_info.get("hw_ver"))
    host = _optional_str(getattr(device, "host", None)) or ""
    return KasaObservation(
        host=host,
        mac=_optional_str(getattr(device, "mac", None))
        or _optional_str(hw_info.get("mac"))
        or "",
        alias=_optional_str(getattr(device, "alias", None)),
        model=_optional_str(getattr(device, "model", None)),
        hardware_version=hardware,
        firmware_version=firmware,
        rssi=_optional_int(getattr(device, "rssi", None)),
    )


async def _safe_disconnect(device: KasaDevice | None) -> None:
    if device is None:
        return
    with contextlib.suppress(Exception):
        await device.disconnect()


def _normalize_mac(value: str) -> str:
    return value.strip().upper()


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
