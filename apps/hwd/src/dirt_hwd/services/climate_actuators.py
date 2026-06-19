"""Explicit actuator command boundaries for climate control."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from kasa import Credentials
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.services.humidifier import (
    H7142_BOOT_TICK_INTERLEAVE_S,
    plan_dispatch,
)
from dirt_hwd.services.humidifier_dispatch import (
    DispatchConfig,
    DispatchOutput,
    DispatchState,
    level_to_intensity_pct,
    quantize,
)
from dirt_hwd.services.kasa_inventory import (
    KasaExpectedDevice,
    KasaInventory,
    KasaVerifiedDevice,
)
from dirt_hwd.services.thermoforge_ble import ThermoForgeTarget
from dirt_hwd.services.thermoforge_protocol import ThermoForgeStatus
from dirt_shared.config import HumidifierConfig, ScheduledKasaConfig
from dirt_shared.models import Capability
from dirt_shared.models import Device as DbDevice
from dirt_shared.models.enums import SensorSource
from dirt_shared.services.fan_node import FanNodeClient, FanState
from dirt_shared.services.govee import WORKMODE_MANUAL, DeviceInfo, StateSnapshot

DEFAULT_DEHUMIDIFIER_DEVICE_ID = "kasa-dehumidifier-main"
DEHUMIDIFIER_METRIC = "dehumidifier_on"
DEFAULT_THERMOFORGE_DEVICE_ID = "ac-infinity-thermoforge-main"
HEATER_INTENSITY_METRIC = "heater_intensity_pct"
DEFAULT_HUMIDIFIER_DEVICE_ID = "govee-h7142-main"


class FanActuator(Protocol):
    async def read_duty(self) -> int: ...

    async def set_duty(self, duty_pct: int) -> int: ...


class HumidifierActuator(Protocol):
    async def set_intensity(self, intensity_pct: float) -> DispatchOutput: ...


class DehumidifierActuator(Protocol):
    async def set_power(self, on: bool) -> bool: ...


class HeaterActuator(Protocol):
    async def set_target(
        self,
        target: ThermoForgeHeaterTarget,
    ) -> ThermoForgeStatus: ...


@dataclass(frozen=True, slots=True)
class ClimateActuators:
    fan: FanActuator
    humidifier: HumidifierActuator
    dehumidifier: DehumidifierActuator
    heater: HeaterActuator


class FanNodeActuator:
    def __init__(self, client: FanNodeClient) -> None:
        self._client = client

    async def read_state(self) -> FanState:
        return await self._client.get_state()

    async def read_duty(self) -> int:
        state = await self.read_state()
        return int(state["set_duty_pct"])

    async def set_duty(self, duty_pct: int) -> int:
        return await self._client.set_duty(duty_pct)


class H7142Client(Protocol):
    async def discover(self) -> list[DeviceInfo]: ...

    async def get_state(self, sku: str, mac: str) -> StateSnapshot: ...

    async def set_power(self, sku: str, mac: str, *, on: bool) -> None: ...

    async def set_manual_level(self, sku: str, mac: str, level: int) -> None: ...


class H7142HumidifierActuator:
    def __init__(  # noqa: PLR0913 - explicit provider boundary dependencies.
        self,
        config: HumidifierConfig,
        client: H7142Client,
        *,
        mac: str | None = None,
        dispatch_config: DispatchConfig | None = None,
        dispatch_state: DispatchState | None = None,
        readings: ClimateReadingsRecorder | None = None,
        device_id: str = DEFAULT_HUMIDIFIER_DEVICE_ID,
        interleave_s: float = H7142_BOOT_TICK_INTERLEAVE_S,
    ) -> None:
        self._config = config
        self._client = client
        self._mac = mac or config.govee_mac or None
        self._dispatch_config = dispatch_config or DispatchConfig(
            levels=config.mist_levels
        )
        self._dispatch_state = dispatch_state or DispatchState()
        self._readings = readings
        self._device_id = device_id
        self._interleave_s = interleave_s

    async def set_intensity(self, intensity_pct: float) -> DispatchOutput:
        mac = await self._resolve_mac()
        plug_on = intensity_pct > 0.0
        dispatch = quantize(
            self._dispatch_config,
            self._dispatch_state,
            max(0.0, min(100.0, intensity_pct)),
            plug_on,
        )
        snapshot = await self._client.get_state(self._config.govee_sku, mac)
        current_level = (
            snapshot.mode_value if snapshot.work_mode == WORKMODE_MANUAL else None
        )
        diff = plan_dispatch(
            current_power=snapshot.power_on,
            current_level=current_level,
            target_level=dispatch.target_level,
        )
        if diff.set_power_on is not None:
            await self._client.set_power(
                self._config.govee_sku,
                mac,
                on=diff.set_power_on,
            )
        if diff.interleave and diff.set_level is not None and self._interleave_s > 0:
            await asyncio.sleep(self._interleave_s)
        if diff.set_level is not None:
            await self._client.set_manual_level(
                self._config.govee_sku,
                mac,
                diff.set_level,
            )
        self._dispatch_state = dispatch.new_state
        await self._record_actuator(dispatch.target_level)
        return dispatch

    async def _resolve_mac(self) -> str:
        if self._mac:
            return self._mac
        for device in await self._client.discover():
            if device.sku == self._config.govee_sku:
                self._mac = device.device
                return device.device
        raise RuntimeError(f"no Govee device found for sku={self._config.govee_sku}")

    async def _record_actuator(self, target_level: int | None) -> None:
        if self._readings is None:
            return
        intensity_pct = level_to_intensity_pct(
            target_level,
            self._dispatch_config.levels,
        )
        await self._readings.ingest_reading(
            {
                "humidifier_on": 0.0 if target_level is None else 1.0,
                "humidifier_intensity_pct": intensity_pct,
            },
            source=SensorSource.GOVEE,
            device_id=self._device_id,
        )


@dataclass(frozen=True, slots=True)
class ClimateKasaPlugTarget:
    source_site_id: int
    source_tent_id: int | None
    source_zone_id: int | None
    device_id: str
    capability_id: str
    host: str | None
    provider_uid: str


KasaPlugTargetLoader = Callable[[], Awaitable[ClimateKasaPlugTarget | None]]


class KasaResolver(Protocol):
    async def connect_verified(
        self,
        expected: KasaExpectedDevice,
    ) -> KasaVerifiedDevice | None: ...


class ClimateReadingsRecorder(Protocol):
    async def ingest_reading(
        self,
        metrics: dict[str, float],
        **kwargs: object,
    ) -> int: ...


class KasaDehumidifierActuator:
    def __init__(  # noqa: PLR0913 - explicit provider boundary dependencies.
        self,
        config: ScheduledKasaConfig,
        *,
        engine: AsyncEngine | None = None,
        readings: ClimateReadingsRecorder | None = None,
        inventory: KasaResolver | None = None,
        target_loader: KasaPlugTargetLoader | None = None,
        device_id: str = DEFAULT_DEHUMIDIFIER_DEVICE_ID,
    ) -> None:
        if engine is None and target_loader is None:
            raise ValueError("engine is required when target_loader is not provided")
        if readings is None:
            raise ValueError("readings recorder is required")
        self._config = config
        self._engine = engine
        self._readings = readings
        self._inventory = inventory
        self._target_loader = target_loader
        self._device_id = device_id

    async def set_power(self, on: bool) -> bool:
        target = await self._load_target()
        if target is None:
            raise RuntimeError(f"DB-known Kasa device not found: {self._device_id}")
        verified = await self._connect(target)
        if verified is None:
            raise RuntimeError(f"known Kasa plug not found: {target.device_id}")

        plug = verified.device
        try:
            await plug.update()
            if bool(plug.is_on) != on:
                if on:
                    await plug.turn_on()
                else:
                    await plug.turn_off()
            await self._readings.ingest_reading(
                {DEHUMIDIFIER_METRIC: 1.0 if on else 0.0},
                device_id=target.device_id,
                source=SensorSource.KASA,
                capability_id=target.capability_id,
            )
            return on
        finally:
            with contextlib.suppress(Exception):
                await plug.disconnect()

    async def _connect(
        self,
        target: ClimateKasaPlugTarget,
    ) -> KasaVerifiedDevice | None:
        inventory = self._inventory
        if inventory is None:
            if not self._config.kasa_username or not self._config.kasa_password:
                raise RuntimeError("Kasa credentials are required")
            inventory = KasaInventory(
                credentials=Credentials(
                    self._config.kasa_username,
                    self._config.kasa_password,
                ),
                discovery_target=self._config.discovery_target,
            )
        return await inventory.connect_verified(
            KasaExpectedDevice(
                device_id=target.device_id,
                mac=target.provider_uid,
                host=target.host,
            )
        )

    async def _load_target(self) -> ClimateKasaPlugTarget | None:
        if self._target_loader is not None:
            return await self._target_loader()
        if self._engine is None:
            raise RuntimeError("engine missing for DB target load")
        return await load_dehumidifier_target(
            self._engine,
            device_id=self._device_id,
        )


async def load_dehumidifier_target(
    engine: AsyncEngine,
    *,
    device_id: str = DEFAULT_DEHUMIDIFIER_DEVICE_ID,
) -> ClimateKasaPlugTarget | None:
    async with AsyncSession(engine) as session:
        row = (
            await session.exec(
                select(
                    DbDevice.site_id,
                    DbDevice.tent_id,
                    DbDevice.zone_id,
                    DbDevice.device_id,
                    DbDevice.ip,
                    DbDevice.provider_uid,
                    Capability.capability_id,
                )
                .select_from(DbDevice)
                .join(Capability, Capability.device_id == DbDevice.id)
                .where(DbDevice.device_id == device_id)
                .where(DbDevice.enabled.is_(True))
                .where(DbDevice.controller == "kasa")
                .where(DbDevice.provider_uid_kind == "mac")
                .where(col(DbDevice.provider_uid).is_not(None))
                .where(Capability.metric_name == DEHUMIDIFIER_METRIC)
                .where(Capability.enabled.is_(True))
                .limit(1)
            )
        ).first()

    if row is None:
        return None
    site_id, tent_id, zone_id, public_device_id, host, provider_uid, capability_id = row
    if provider_uid is None:
        return None
    return ClimateKasaPlugTarget(
        source_site_id=site_id,
        source_tent_id=tent_id,
        source_zone_id=zone_id,
        device_id=public_device_id,
        capability_id=capability_id,
        host=str(host) if host is not None else None,
        provider_uid=provider_uid,
    )


@dataclass(frozen=True, slots=True)
class ThermoForgeActuatorDevice:
    source_site_id: int
    source_tent_id: int | None
    source_zone_id: int | None
    device_id: str
    capability_id: str
    provider_uid: str


@dataclass(frozen=True, slots=True)
class ThermoForgeHeaterTarget:
    level: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.level <= 10:
            raise ValueError("ThermoForge heater target must be off or level 1..10")

    @classmethod
    def off(cls) -> ThermoForgeHeaterTarget:
        return cls(level=0)

    @classmethod
    def heat_level(cls, level: int) -> ThermoForgeHeaterTarget:
        if level == 0:
            raise ValueError("active ThermoForge heat level must be 1..10")
        return cls(level=level)

    @property
    def running(self) -> bool:
        return self.level > 0

    def to_ble_target(self) -> ThermoForgeTarget:
        if not self.running:
            return ThermoForgeTarget(running=False)
        return ThermoForgeTarget(running=True, level=self.level)


class ThermoForgeReconcileClient(Protocol):
    async def connect(self) -> ThermoForgeStatus: ...

    async def disconnect(self) -> None: ...

    async def reconcile(self, target: ThermoForgeTarget) -> ThermoForgeStatus: ...


ThermoForgeReconcileClientFactory = Callable[[str], ThermoForgeReconcileClient]


class ThermoForgeHeaterActuator:
    def __init__(
        self,
        device: ThermoForgeActuatorDevice,
        *,
        client_factory: ThermoForgeReconcileClientFactory,
        readings: ClimateReadingsRecorder | None = None,
    ) -> None:
        self._device = device
        self._client_factory = client_factory
        self._readings = readings

    async def set_target(self, target: ThermoForgeHeaterTarget) -> ThermoForgeStatus:
        client = self._client_factory(self._device.provider_uid)
        try:
            await client.connect()
            status = await client.reconcile(target.to_ble_target())
            await self._record_readings(status)
            return status
        finally:
            with contextlib.suppress(Exception):
                await client.disconnect()

    async def _record_readings(self, status: ThermoForgeStatus) -> None:
        if self._readings is None:
            return
        await self._readings.ingest_reading(
            {
                "heater_on": 1.0 if status.running else 0.0,
                "heater_intensity_pct": float(
                    (status.level if status.running else 0) * 10
                ),
            },
            device_id=self._device.device_id,
            source=SensorSource.AC_INFINITY,
            capability_id=self._device.capability_id,
        )


async def load_thermoforge_actuator_device(
    engine: AsyncEngine,
    *,
    device_id: str = DEFAULT_THERMOFORGE_DEVICE_ID,
) -> ThermoForgeActuatorDevice | None:
    async with AsyncSession(engine) as session:
        row = (
            await session.exec(
                select(
                    DbDevice.site_id,
                    DbDevice.tent_id,
                    DbDevice.zone_id,
                    DbDevice.device_id,
                    DbDevice.provider_uid,
                    Capability.capability_id,
                )
                .select_from(DbDevice)
                .join(Capability, Capability.device_id == DbDevice.id)
                .where(DbDevice.device_id == device_id)
                .where(DbDevice.enabled.is_(True))
                .where(DbDevice.controller == "ac_infinity_ble")
                .where(DbDevice.provider_uid_kind == "mac")
                .where(col(DbDevice.provider_uid).is_not(None))
                .where(Capability.metric_name == HEATER_INTENSITY_METRIC)
                .where(Capability.enabled.is_(True))
                .limit(1)
            )
        ).first()

    if row is None:
        return None
    site_id, tent_id, zone_id, public_device_id, provider_uid, capability_id = row
    if provider_uid is None:
        return None
    return ThermoForgeActuatorDevice(
        source_site_id=site_id,
        source_tent_id=tent_id,
        source_zone_id=zone_id,
        device_id=public_device_id,
        capability_id=capability_id,
        provider_uid=provider_uid,
    )


class DatabaseThermoForgeHeaterActuator:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        client_factory: ThermoForgeReconcileClientFactory,
        readings: ClimateReadingsRecorder | None = None,
        device_id: str = DEFAULT_THERMOFORGE_DEVICE_ID,
    ) -> None:
        self._engine = engine
        self._client_factory = client_factory
        self._readings = readings
        self._device_id = device_id
        self._device: ThermoForgeActuatorDevice | None = None

    async def set_target(self, target: ThermoForgeHeaterTarget) -> ThermoForgeStatus:
        device = await self._load_device()
        if device is None:
            raise RuntimeError(
                f"DB-known ThermoForge device not found: {self._device_id}"
            )
        actuator = ThermoForgeHeaterActuator(
            device,
            client_factory=self._client_factory,
            readings=self._readings,
        )
        return await actuator.set_target(target)

    async def _load_device(self) -> ThermoForgeActuatorDevice | None:
        if self._device is None:
            self._device = await load_thermoforge_actuator_device(
                self._engine,
                device_id=self._device_id,
            )
        return self._device
