"""Schedule-driven lights control via DB-known Kasa smart plugs."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Protocol
from zoneinfo import ZoneInfo

from kasa import Credentials
from kasa import Device as KasaDevice
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.services.kasa_inventory import (
    KasaExpectedDevice,
    KasaInventory,
    KasaObservation,
    KasaVerifiedDevice,
)
from dirt_shared.config import LightsConfig
from dirt_shared.models import (
    Capability,
    Schedule,
    Site,
    Tent,
    Zone,
)
from dirt_shared.models import (
    Device as DbDevice,
)
from dirt_shared.observability import log_event
from dirt_shared.services.grow_state import derive_lights_from_times

logger = logging.getLogger(__name__)

STREAM = "lights"


@dataclass(frozen=True)
class LightScheduleTarget:
    site_id: str
    tent_id: str
    zone_id: str | None
    device_pk: int
    device_id: str
    capability_id: str
    schedule_id: str
    host: str | None
    provider_uid: str
    starts_local: time
    ends_local: time
    timezone: str


class KasaResolver(Protocol):
    async def connect_verified(
        self,
        expected: KasaExpectedDevice,
    ) -> KasaVerifiedDevice | None: ...


TargetLoader = Callable[[], Awaitable[list[LightScheduleTarget]]]


async def _safe_disconnect(plug: KasaDevice | None) -> None:
    if plug is None:
        return
    with contextlib.suppress(Exception):
        await plug.disconnect()


class LightsLoopService:
    """Reconcile every enabled DB-known Kasa light schedule."""

    def __init__(
        self,
        config: LightsConfig,
        *,
        engine: AsyncEngine | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        target_loader: TargetLoader | None = None,
        inventory: KasaResolver | None = None,
    ) -> None:
        if engine is None and target_loader is None:
            raise ValueError("engine is required when target_loader is not provided")
        self._config = config
        self._engine = engine
        self._clock = clock
        self._target_loader = target_loader
        self._inventory = inventory

    async def run(self, stop_event: asyncio.Event) -> None:
        cfg = self._config
        if not cfg.kasa_username or not cfg.kasa_password:
            logger.warning(
                "KASA_USERNAME/KASA_PASSWORD unset - lights loop disabled",
            )
            return

        inventory = self._inventory or KasaInventory(
            credentials=Credentials(cfg.kasa_username, cfg.kasa_password),
            discovery_target=cfg.discovery_target,
        )
        interval = cfg.poll_interval

        logger.info(
            "lights loop starting: discovery_target=%s interval=%ds",
            cfg.discovery_target,
            interval,
        )

        plugs: dict[str, KasaDevice] = {}

        while not stop_event.is_set():
            try:
                targets = await self._load_targets()
                active_ids = {target.device_id for target in targets}
                for device_id in set(plugs) - active_ids:
                    await _safe_disconnect(plugs.pop(device_id))

                for target in targets:
                    try:
                        plug = plugs.get(target.device_id)
                        if plug is None:
                            verified = await inventory.connect_verified(
                                KasaExpectedDevice(
                                    device_id=target.device_id,
                                    mac=target.provider_uid,
                                    host=target.host,
                                )
                            )
                            if verified is None:
                                self._log_error(
                                    target,
                                    RuntimeError(
                                        "known Kasa plug not found by provider_uid"
                                    ),
                                )
                                continue
                            plug = verified.device
                            plugs[target.device_id] = plug
                            await self._record_observation(target, verified.observation)

                        await self._reconcile_target(target, plug)
                    except Exception:
                        await _safe_disconnect(plugs.pop(target.device_id, None))
            except Exception:
                logger.exception("lights loop error")

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=interval)

        for plug in plugs.values():
            await _safe_disconnect(plug)
        logger.info("lights loop stopped")

    async def _load_targets(self) -> list[LightScheduleTarget]:
        if self._target_loader is not None:
            return await self._target_loader()
        if self._engine is None:
            raise RuntimeError("engine missing for DB target load")

        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(
                        Schedule,
                        Site.site_id,
                        Tent.tent_id,
                        Zone.zone_id,
                        DbDevice.id,
                        DbDevice.device_id,
                        DbDevice.ip,
                        DbDevice.provider_uid,
                        Capability.capability_id,
                    )
                    .join(Site, Site.id == Schedule.site_id)
                    .join(Tent, Tent.id == Schedule.tent_id)
                    .join(DbDevice, DbDevice.id == Schedule.device_id)
                    .outerjoin(Zone, Zone.id == DbDevice.zone_id)
                    .outerjoin(Capability, Capability.id == Schedule.capability_id)
                    .where(Schedule.kind == "lights")
                    .where(Schedule.enabled.is_(True))
                    .where(col(Schedule.starts_local).is_not(None))
                    .where(col(Schedule.ends_local).is_not(None))
                    .where(DbDevice.enabled.is_(True))
                    .where(DbDevice.controller == "kasa")
                    .where(DbDevice.provider_uid_kind == "mac")
                    .where(col(DbDevice.provider_uid).is_not(None))
                    .order_by(Tent.tent_id, Schedule.schedule_id)
                )
            ).all()

        targets: list[LightScheduleTarget] = []
        for (
            schedule,
            site_id,
            tent_id,
            zone_id,
            device_pk,
            device_id,
            host,
            provider_uid,
            capability_id,
        ) in rows:
            if (
                schedule.starts_local is None
                or schedule.ends_local is None
                or provider_uid is None
                or device_pk is None
            ):
                continue
            targets.append(
                LightScheduleTarget(
                    site_id=site_id,
                    tent_id=tent_id,
                    zone_id=zone_id,
                    device_pk=device_pk,
                    device_id=device_id,
                    capability_id=capability_id or "lights_power",
                    schedule_id=schedule.schedule_id,
                    host=str(host) if host is not None else None,
                    provider_uid=provider_uid,
                    starts_local=schedule.starts_local,
                    ends_local=schedule.ends_local,
                    timezone=schedule.timezone,
                )
            )
        return targets

    async def _reconcile_target(
        self,
        target: LightScheduleTarget,
        plug: KasaDevice,
    ) -> None:
        try:
            await plug.update()
            await self._record_seen(target)
            is_on = bool(plug.is_on)
            lights = derive_lights_from_times(
                target.starts_local,
                target.ends_local,
                self._clock().astimezone(ZoneInfo(target.timezone)),
            )
            if lights.on == is_on:
                return
            if lights.on:
                await plug.turn_on()
            else:
                await plug.turn_off()
            log_event(
                STREAM,
                "state_change",
                **self._scope_fields(target),
                schedule_id=target.schedule_id,
                new_state="on" if lights.on else "off",
                reason="scheduled_on" if lights.on else "scheduled_off",
                minutes_until_off=round(lights.minutes_until_off, 1),
                minutes_until_on=round(lights.minutes_until_on, 1),
            )
            logger.info(
                "lights %s -> %s (schedule=%s)",
                target.device_id,
                "on" if lights.on else "off",
                target.schedule_id,
            )
        except Exception as exc:
            self._log_error(target, exc)
            raise

    async def _record_observation(
        self,
        target: LightScheduleTarget,
        observation: KasaObservation,
    ) -> None:
        if self._engine is None:
            return
        async with AsyncSession(self._engine) as session:
            device = await session.get(DbDevice, target.device_pk)
            if device is None:
                return
            metadata = dict(device.metadata_json)
            metadata.update(
                {
                    "kasa_alias": observation.alias,
                    "model": observation.model,
                    "hardware_version": observation.hardware_version,
                    "firmware_version": observation.firmware_version,
                    "rssi": observation.rssi,
                }
            )
            device.ip = observation.host or device.ip
            device.firmware_version = observation.firmware_version
            device.last_seen = self._clock()
            device.metadata_json = {
                key: value for key, value in metadata.items() if value is not None
            }
            device.updated_at = self._clock()
            session.add(device)
            await session.commit()

    async def _record_seen(self, target: LightScheduleTarget) -> None:
        if self._engine is None:
            return
        now = self._clock()
        async with AsyncSession(self._engine) as session:
            device = await session.get(DbDevice, target.device_pk)
            if device is None:
                return
            device.last_seen = now
            device.updated_at = now
            session.add(device)
            await session.commit()

    def _scope_fields(self, target: LightScheduleTarget) -> dict[str, str | None]:
        return {
            "site_id": target.site_id,
            "tent_id": target.tent_id,
            "zone_id": target.zone_id,
            "device_id": target.device_id,
            "capability_id": target.capability_id,
        }

    def _log_error(self, target: LightScheduleTarget, exc: Exception) -> None:
        logger.error(
            "lights target error: device_id=%s error=%r",
            target.device_id,
            exc,
        )
        log_event(
            STREAM,
            "error",
            **self._scope_fields(target),
            schedule_id=target.schedule_id,
            error_type=type(exc).__name__,
            error=repr(exc),
        )
