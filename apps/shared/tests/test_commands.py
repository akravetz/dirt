from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.zone import Zone
from dirt_shared.services.commands import CommandService, CommandSourceError

T0 = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)


async def test_enqueue_is_idempotent_for_local_command(app_engine) -> None:
    service = CommandService(app_engine, clock=lambda: T0)
    async with AsyncSession(app_engine) as session:
        zone_pk = (
            await session.exec(select(Zone.id).where(Zone.name == "Plant A"))
        ).one()

    first = await service.enqueue(
        command_type="ptz.preset",
        payload={"preset_id": "plant_a"},
        idempotency_key="ptz:preset:plant-a:test",
        requested_by="test",
        source="local_api",
        device_id="obsbot-main",
        capability_id="ptz_move",
        zone_pk=zone_pk,
    )
    second = await service.enqueue(
        command_type="ptz.preset",
        payload={"preset_id": "plant_a"},
        idempotency_key="ptz:preset:plant-a:test",
        requested_by="test",
        source="local_api",
        device_id="obsbot-main",
        capability_id="ptz_move",
        zone_pk=zone_pk,
    )

    assert second.command_id == first.command_id
    assert first.status == "queued"
    assert first.device_id is not None
    assert first.capability_id is not None
    assert first.zone_id is not None


async def test_enqueue_resolves_target_from_default_scope(app_engine) -> None:
    service = CommandService(app_engine, clock=lambda: T0)

    command = await service.enqueue(
        command_type="fan.set",
        payload={"fan_pct": 33},
        idempotency_key="fan:set:test",
        requested_by="test",
        source="local_api",
        device_id="fan-controller",
        capability_id="fan_pct",
    )

    async with AsyncSession(app_engine) as session:
        device = (
            await session.exec(
                select(Device).where(Device.device_id == "fan-controller")
            )
        ).one()
        capability = (
            await session.exec(
                select(Capability)
                .where(Capability.device_id == device.id)
                .where(Capability.capability_id == "fan_pct")
            )
        ).one()

    assert command.site_id == device.site_id
    assert command.tent_id == device.tent_id
    assert command.zone_id is None
    assert command.device_id == device.id
    assert command.capability_id == capability.id


async def test_lifecycle_transitions_are_idempotent(app_engine) -> None:
    now = T0

    def clock():
        return now

    service = CommandService(app_engine, clock=clock)
    command = await service.enqueue(
        command_type="ptz.zoom",
        payload={"zoom": 1.5},
        idempotency_key="ptz:zoom:test",
        requested_by="test",
        source="local_api",
        device_id="obsbot-main",
        capability_id="ptz_move",
    )

    now = T0 + timedelta(seconds=1)
    running = await service.start(command.command_id)
    running_again = await service.start(command.command_id)

    assert running.status == "running"
    assert running_again.started_at == running.started_at

    now = T0 + timedelta(seconds=2)
    succeeded = await service.succeed(command.command_id, {"ok": True})
    failed_after_terminal = await service.fail(command.command_id, {"error": "late"})

    assert succeeded.status == "succeeded"
    assert succeeded.result == {"ok": True}
    assert failed_after_terminal.status == "succeeded"
    assert failed_after_terminal.failed_at is None


async def test_remote_command_sources_are_rejected(app_engine) -> None:
    service = CommandService(app_engine, clock=lambda: T0)

    with pytest.raises(CommandSourceError):
        await service.enqueue(
            command_type="ptz.zoom",
            payload={"zoom": 1.5},
            idempotency_key="remote:test",
            requested_by="test",
            source="remote_api",
            device_id="obsbot-main",
            capability_id="ptz_move",
        )
