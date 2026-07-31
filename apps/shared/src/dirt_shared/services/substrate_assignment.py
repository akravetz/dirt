"""Transactional plant assignment for logical RS485 substrate probes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models import (
    Capability,
    Device,
    Plant,
    PlantLocationHistory,
    PlantMetricStream,
)

SUBSTRATE_METRIC_DISPLAY_ORDER: dict[str, int] = {
    "soil_moisture_pct": 1,
    "substrate_temp_c": 2,
    "substrate_ec_us_cm": 3,
    "substrate_ph": 4,
}


class SubstrateAssignmentError(ValueError):
    """Raised when a requested probe assignment is invalid or ambiguous."""


@dataclass(frozen=True)
class SubstrateAssignment:
    bus_id: str
    device_id: str
    plant_key: str
    tent_id: int
    metrics: tuple[str, ...]
    previous_plant_keys: tuple[str, ...]


@dataclass(frozen=True)
class SubstrateAssignmentRow:
    bus_id: str
    device_id: str
    plant_keys: tuple[str, ...]


def normalize_modbus_address(value: str) -> str:
    raw = value.strip()
    try:
        address = int(raw, 0)
    except ValueError as exc:
        raise SubstrateAssignmentError(
            f"invalid Modbus address {value!r}; use 0x02 or decimal 2"
        ) from exc
    if not 1 <= address <= 247:
        raise SubstrateAssignmentError("Modbus address must be between 1 and 247")
    return f"0x{address:02X}"


def _device_bus_id(device: Device) -> str | None:
    metadata = device.metadata_json
    if metadata.get("bus") != "rs485":
        return None
    value = metadata.get("modbus_address")
    return value if isinstance(value, str) else None


async def _substrate_devices(session: AsyncSession) -> list[Device]:
    devices = (
        await session.exec(
            select(Device).where(Device.enabled.is_(True)).order_by(Device.device_id)
        )
    ).all()
    return [device for device in devices if _device_bus_id(device) is not None]


async def _require_substrate_device(
    session: AsyncSession, canonical_bus_id: str
) -> Device:
    matching_devices = [
        device
        for device in await _substrate_devices(session)
        if _device_bus_id(device) == canonical_bus_id
    ]
    if not matching_devices:
        raise SubstrateAssignmentError(
            f"no enabled RS485 substrate probe found at {canonical_bus_id}"
        )
    if len(matching_devices) > 1:
        raise SubstrateAssignmentError(
            f"multiple enabled RS485 substrate probes found at {canonical_bus_id}"
        )
    return matching_devices[0]


async def _require_current_plant_location(
    session: AsyncSession,
    *,
    requested_plant_key: str,
    site_id: int,
) -> tuple[Plant, PlantLocationHistory]:
    plant_locations = (
        await session.exec(
            select(Plant, PlantLocationHistory)
            .join(
                PlantLocationHistory,
                PlantLocationHistory.plant_id == Plant.id,
            )
            .where(func.lower(Plant.key) == requested_plant_key.lower())
            .where(PlantLocationHistory.end_at.is_(None))
            .where(PlantLocationHistory.site_id == site_id)
            .where(Plant.culled_at.is_(None))
            .where(Plant.harvested_at.is_(None))
        )
    ).all()
    if not plant_locations:
        raise SubstrateAssignmentError(
            f"no current plant found with key {requested_plant_key!r}"
        )
    if len(plant_locations) > 1:
        raise SubstrateAssignmentError(
            f"multiple current plants found with key {requested_plant_key!r}"
        )
    plant, plant_location = plant_locations[0]
    if plant.id is None:
        raise SubstrateAssignmentError("target plant has no database identity")
    return plant, plant_location


async def _require_substrate_capabilities(
    session: AsyncSession,
    *,
    device_id: int,
    canonical_bus_id: str,
) -> tuple[dict[str, Capability], list[int]]:
    capabilities = (
        await session.exec(
            select(Capability)
            .where(Capability.device_id == device_id)
            .where(Capability.enabled.is_(True))
            .where(
                col(Capability.metric_name).in_(tuple(SUBSTRATE_METRIC_DISPLAY_ORDER))
            )
            .order_by(Capability.metric_name)
        )
    ).all()
    capability_by_metric = {
        capability.metric_name: capability
        for capability in capabilities
        if capability.metric_name is not None
    }
    missing_metrics = set(SUBSTRATE_METRIC_DISPLAY_ORDER) - set(capability_by_metric)
    if missing_metrics:
        missing = ", ".join(sorted(missing_metrics))
        raise SubstrateAssignmentError(
            f"probe {canonical_bus_id} is missing enabled capabilities: {missing}"
        )
    if len(capabilities) != len(SUBSTRATE_METRIC_DISPLAY_ORDER):
        raise SubstrateAssignmentError(
            f"probe {canonical_bus_id} has duplicate product metric capabilities"
        )
    capability_ids = [
        capability.id for capability in capabilities if capability.id is not None
    ]
    return capability_by_metric, capability_ids


async def assign_substrate_probe(
    engine: AsyncEngine,
    *,
    bus_id: str,
    plant_key: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> SubstrateAssignment:
    canonical_bus_id = normalize_modbus_address(bus_id)
    requested_plant_key = plant_key.strip()
    if not requested_plant_key:
        raise SubstrateAssignmentError("plant key must not be blank")

    async with AsyncSession(engine) as session:
        device = await _require_substrate_device(session, canonical_bus_id)
        if device.id is None:
            raise SubstrateAssignmentError("substrate probe has no database identity")

        plant, plant_location = await _require_current_plant_location(
            session,
            requested_plant_key=requested_plant_key,
            site_id=device.site_id,
        )
        capability_by_metric, capability_ids = await _require_substrate_capabilities(
            session,
            device_id=device.id,
            canonical_bus_id=canonical_bus_id,
        )
        active_streams = (
            await session.exec(
                select(PlantMetricStream)
                .where(col(PlantMetricStream.capability_id).in_(capability_ids))
                .where(PlantMetricStream.is_active.is_(True))
            )
        ).all()
        previous_plant_ids = {
            stream.plant_id for stream in active_streams if stream.plant_id != plant.id
        }
        previous_plants = (
            await session.exec(
                select(Plant)
                .where(col(Plant.id).in_(previous_plant_ids))
                .order_by(Plant.key)
            )
        ).all()

        now = clock()
        device.site_id = plant_location.site_id
        device.tent_id = plant_location.tent_id
        device.zone_id = None
        device.updated_at = now
        for stream in active_streams:
            stream.is_active = False
            stream.updated_at = now

        target_streams = (
            await session.exec(
                select(PlantMetricStream)
                .where(PlantMetricStream.plant_id == plant.id)
                .where(col(PlantMetricStream.capability_id).in_(capability_ids))
            )
        ).all()
        target_by_capability = {
            stream.capability_id: stream for stream in target_streams
        }
        for metric, display_order in SUBSTRATE_METRIC_DISPLAY_ORDER.items():
            capability = capability_by_metric[metric]
            if capability.id is None:
                raise SubstrateAssignmentError(
                    f"capability {capability.capability_id!r} has no database identity"
                )
            stream = target_by_capability.get(capability.id)
            if stream is None:
                session.add(
                    PlantMetricStream(
                        plant_id=plant.id,
                        capability_id=capability.id,
                        display_order=display_order,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                stream.display_order = display_order
                stream.is_active = True
                stream.updated_at = now

        device_id = device.device_id
        canonical_plant_key = plant.key
        target_tent_id = plant_location.tent_id
        previous_plant_keys = tuple(item.key for item in previous_plants)
        await session.commit()
        return SubstrateAssignment(
            bus_id=canonical_bus_id,
            device_id=device_id,
            plant_key=canonical_plant_key,
            tent_id=target_tent_id,
            metrics=tuple(SUBSTRATE_METRIC_DISPLAY_ORDER),
            previous_plant_keys=previous_plant_keys,
        )


async def list_substrate_assignments(
    engine: AsyncEngine,
) -> tuple[SubstrateAssignmentRow, ...]:
    async with AsyncSession(engine) as session:
        devices = await _substrate_devices(session)
        rows: list[SubstrateAssignmentRow] = []
        for device in devices:
            if device.id is None:
                continue
            plant_keys = (
                await session.exec(
                    select(Plant.key)
                    .join(
                        PlantMetricStream,
                        PlantMetricStream.plant_id == Plant.id,
                    )
                    .join(
                        Capability,
                        Capability.id == PlantMetricStream.capability_id,
                    )
                    .where(Capability.device_id == device.id)
                    .where(PlantMetricStream.is_active.is_(True))
                    .distinct()
                    .order_by(Plant.key)
                )
            ).all()
            bus_id = _device_bus_id(device)
            if bus_id is None:
                continue
            rows.append(
                SubstrateAssignmentRow(
                    bus_id=bus_id,
                    device_id=device.device_id,
                    plant_keys=tuple(plant_keys),
                )
            )
        return tuple(sorted(rows, key=lambda row: row.bus_id))
