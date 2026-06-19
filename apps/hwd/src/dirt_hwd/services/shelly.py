"""Shelly Gen2/Gen4 plug control with DB-owned identity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models import Capability
from dirt_shared.models import Device as DbDevice


@dataclass(frozen=True)
class ShellyPlugTarget:
    source_site_id: int
    source_tent_id: int | None
    source_zone_id: int | None
    device_pk: int
    device_id: str
    capability_pk: int
    capability_id: str
    hostname: str | None
    ip: str | None
    provider_uid_kind: str
    provider_uid: str
    switch_id: int = 0
    shelly_id: str | None = None

    @property
    def endpoints(self) -> tuple[str, ...]:
        ordered = [self.hostname, self.ip]
        seen: set[str] = set()
        endpoints: list[str] = []
        for endpoint in ordered:
            if not endpoint:
                continue
            normalized = endpoint.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            endpoints.append(normalized)
        return tuple(endpoints)


class ShellyIdentityMismatch(RuntimeError):
    """Raised when a reachable Shelly does not match the DB-owned identity."""


class ShellyConnectionError(RuntimeError):
    """Raised when no configured endpoint can be reached."""


async def load_shelly_plug_target(
    session: AsyncSession,
    *,
    device_pk: int,
    capability_pk: int,
) -> ShellyPlugTarget | None:
    row = (
        await session.exec(
            select(
                DbDevice,
                Capability,
            )
            .join(Capability, Capability.device_id == DbDevice.id)
            .where(DbDevice.id == device_pk)
            .where(Capability.id == capability_pk)
            .where(DbDevice.enabled.is_(True))
            .where(DbDevice.controller == "shelly")
            .where(DbDevice.provider_uid_kind == "mac")
            .where(col(DbDevice.provider_uid).is_not(None))
            .where(Capability.enabled.is_(True))
        )
    ).one_or_none()
    if row is None:
        return None
    device, capability = row
    return shelly_target_from_db_rows(device, capability)


def shelly_target_from_db_rows(
    device: DbDevice,
    capability: Capability,
) -> ShellyPlugTarget:
    if device.id is None or capability.id is None:
        raise ValueError("Shelly target rows must be flushed before control")
    if device.provider_uid is None or device.provider_uid_kind is None:
        raise ValueError("Shelly target is missing provider identity")

    switch_id = _metadata_int(capability.metadata_json, "switch_id")
    if switch_id is None:
        switch_id = _metadata_int(device.metadata_json, "switch_id") or 0

    shelly_id = _metadata_str(device.metadata_json, "shelly_id")
    return ShellyPlugTarget(
        source_site_id=device.site_id,
        source_tent_id=device.tent_id,
        source_zone_id=device.zone_id,
        device_pk=device.id,
        device_id=device.device_id,
        capability_pk=capability.id,
        capability_id=capability.capability_id,
        hostname=device.hostname,
        ip=str(device.ip) if device.ip is not None else None,
        provider_uid_kind=device.provider_uid_kind,
        provider_uid=device.provider_uid,
        switch_id=switch_id,
        shelly_id=shelly_id,
    )


class ShellyPlugClient:
    def __init__(
        self,
        *,
        http: httpx.AsyncClient | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._http = http
        self._timeout = timeout

    async def timed_pulse(
        self,
        target: ShellyPlugTarget,
        *,
        duration_s: int,
    ) -> str:
        if duration_s <= 0:
            raise ValueError("duration_s must be positive")

        if self._http is not None:
            return await self._timed_pulse(self._http, target, duration_s=duration_s)

        async with httpx.AsyncClient(timeout=self._timeout) as http:
            return await self._timed_pulse(http, target, duration_s=duration_s)

    async def _timed_pulse(
        self,
        http: httpx.AsyncClient,
        target: ShellyPlugTarget,
        *,
        duration_s: int,
    ) -> str:
        endpoints = target.endpoints
        if not endpoints:
            raise ShellyConnectionError(f"{target.device_id} has no Shelly endpoint")

        last_error: Exception | None = None
        for endpoint in endpoints:
            try:
                await self._verify_identity(http, endpoint, target)
                await self._switch_set(
                    http,
                    endpoint,
                    switch_id=target.switch_id,
                    duration_s=duration_s,
                )
                return endpoint
            except ShellyIdentityMismatch:
                raise
            except httpx.HTTPError as exc:
                last_error = exc

        raise ShellyConnectionError(
            f"{target.device_id} was unreachable at configured Shelly endpoints"
        ) from last_error

    async def _verify_identity(
        self,
        http: httpx.AsyncClient,
        endpoint: str,
        target: ShellyPlugTarget,
    ) -> None:
        response = await http.get(f"{_base_url(endpoint)}/rpc/Shelly.GetDeviceInfo")
        response.raise_for_status()
        payload = response.json()
        observed_mac = _normalize_mac(str(payload.get("mac") or ""))
        expected_mac = _normalize_mac(target.provider_uid)
        if target.provider_uid_kind != "mac" or observed_mac != expected_mac:
            raise ShellyIdentityMismatch(
                f"Shelly identity mismatch for {target.device_id}: "
                f"expected mac {target.provider_uid}, observed {payload.get('mac')!r}"
            )

        if target.shelly_id is not None:
            observed_id = str(payload.get("id") or "")
            if observed_id.lower() != target.shelly_id.lower():
                raise ShellyIdentityMismatch(
                    f"Shelly id mismatch for {target.device_id}: "
                    f"expected {target.shelly_id}, observed {observed_id!r}"
                )

    async def _switch_set(
        self,
        http: httpx.AsyncClient,
        endpoint: str,
        *,
        switch_id: int,
        duration_s: int,
    ) -> None:
        response = await http.post(
            f"{_base_url(endpoint)}/rpc/Switch.Set",
            json={"id": switch_id, "on": True, "toggle_after": duration_s},
        )
        response.raise_for_status()


def _base_url(endpoint: str) -> str:
    if endpoint.startswith(("http://", "https://")):
        return endpoint.rstrip("/")
    return f"http://{endpoint.rstrip('/')}"


def _normalize_mac(value: str) -> str:
    return "".join(char for char in value if char.isalnum()).upper()


def _metadata_int(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    return value if isinstance(value, int) else None


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None
