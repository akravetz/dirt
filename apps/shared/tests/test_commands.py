from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dirt_shared.services.commands import CommandService, CommandSourceError

T0 = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)


async def test_enqueue_is_idempotent_for_local_command(app_engine) -> None:
    service = CommandService(app_engine, clock=lambda: T0)

    first = await service.enqueue(
        command_type="ptz.preset",
        payload={"preset_id": "plant_a"},
        idempotency_key="ptz:preset:plant-a:test",
        requested_by="test",
        source="local_api",
        device_id="obsbot-main",
        capability_id="ptz_move",
        zone_id="plant-a",
    )
    second = await service.enqueue(
        command_type="ptz.preset",
        payload={"preset_id": "plant_a"},
        idempotency_key="ptz:preset:plant-a:test",
        requested_by="test",
        source="local_api",
        device_id="obsbot-main",
        capability_id="ptz_move",
        zone_id="plant-a",
    )

    assert second.command_id == first.command_id
    assert first.status == "queued"
    assert first.device_id is not None
    assert first.capability_id is not None
    assert first.zone_id is not None


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
