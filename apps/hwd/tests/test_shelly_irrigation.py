from __future__ import annotations

from datetime import UTC, datetime, time

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.services.shelly import ShellyPlugTarget
from dirt_hwd.services.shelly_irrigation import ShellyIrrigationScheduleService
from dirt_shared.models import IrrigationRun, IrrigationScheduleItem, Schedule
from dirt_shared.testing import create_test_capability, create_test_device

DUE_AT = datetime(2026, 5, 25, 17, 0, tzinfo=UTC)


class _FakeShellyClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[ShellyPlugTarget, int]] = []

    async def timed_pulse(
        self,
        target: ShellyPlugTarget,
        *,
        duration_s: int,
    ) -> str:
        self.calls.append((target, duration_s))
        if self.fail:
            raise RuntimeError("simulated Shelly failure")
        return target.hostname or target.ip or "unknown"


async def _add_irrigation_schedule(
    session: AsyncSession,
    *,
    suffix: str,
    schedule_enabled: bool = True,
    item_enabled: bool = True,
    starts_local: time = time(11, 0),
    duration_s: int = 5,
):
    mac_suffix = sum(ord(char) for char in suffix) % 100
    device = await create_test_device(
        session,
        device_id=f"test-shelly-irrigation-{suffix}",
        tent_id="main",
        kind="actuator",
        controller="shelly",
    )
    device.hostname = f"pump-{suffix}.local"
    device.ip = f"192.0.2.{20 + len(suffix)}"
    device.provider_uid_kind = "mac"
    device.provider_uid = f"AA:BB:CC:DD:EE:{mac_suffix:02d}"
    capability = await create_test_capability(
        session,
        device=device,
        capability_id=f"pump_power_{suffix}",
        kind="actuator",
        metric_name=f"pump_on_{suffix}",
        unit="bool",
        source="shelly",
    )
    capability.metadata_json = {"switch_id": 0}
    schedule = Schedule(
        site_id=device.site_id,
        tent_id=device.tent_id,
        device_id=device.id,
        capability_id=capability.id,
        schedule_id=f"test-irrigation-{suffix}",
        kind="irrigation",
        timezone="America/Denver",
        enabled=schedule_enabled,
    )
    session.add(schedule)
    await session.flush()
    item = IrrigationScheduleItem(
        schedule_id=schedule.id,
        starts_local=starts_local,
        duration_s=duration_s,
        enabled=item_enabled,
    )
    session.add(item)
    await session.flush()
    return schedule, item, device, capability


async def _runs(session: AsyncSession) -> list[IrrigationRun]:
    return (
        await session.exec(
            select(IrrigationRun).order_by(IrrigationRun.schedule_item_id)
        )
    ).all()


async def test_due_irrigation_pulse_dispatches_once_and_suppresses_duplicate_tick(
    app_engine,
) -> None:
    async with AsyncSession(app_engine) as session:
        await _add_irrigation_schedule(session, suffix="due", duration_s=6)
        await session.commit()

    client = _FakeShellyClient()
    service = ShellyIrrigationScheduleService(
        app_engine,
        client=client,
        clock=lambda: DUE_AT,
    )

    first = await service.run_once()
    second = await service.run_once()

    async with AsyncSession(app_engine) as session:
        runs = await _runs(session)

    assert [result.status for result in first] == ["dispatched"]
    assert second == []
    assert [(target.device_id, duration_s) for target, duration_s in client.calls] == [
        ("test-shelly-irrigation-due", 6)
    ]
    assert len(runs) == 1
    assert runs[0].status == "dispatched"
    assert runs[0].error is None


@pytest.mark.parametrize(
    ("schedule_enabled", "item_enabled"),
    [
        (False, True),
        (True, False),
    ],
)
async def test_disabled_irrigation_schedule_or_item_does_not_dispatch(
    app_engine,
    schedule_enabled: bool,
    item_enabled: bool,
) -> None:
    async with AsyncSession(app_engine) as session:
        await _add_irrigation_schedule(
            session,
            suffix=f"disabled-{schedule_enabled}-{item_enabled}",
            schedule_enabled=schedule_enabled,
            item_enabled=item_enabled,
        )
        await session.commit()

    client = _FakeShellyClient()
    service = ShellyIrrigationScheduleService(
        app_engine,
        client=client,
        clock=lambda: DUE_AT,
    )

    results = await service.run_once()

    async with AsyncSession(app_engine) as session:
        runs = await _runs(session)

    assert results == []
    assert client.calls == []
    assert runs == []


async def test_irrigation_scheduler_dispatches_only_configured_shelly_target(
    app_engine,
) -> None:
    async with AsyncSession(app_engine) as session:
        await _add_irrigation_schedule(
            session,
            suffix="not-due",
            starts_local=time(12, 0),
        )
        await _add_irrigation_schedule(session, suffix="configured")
        await session.commit()

    client = _FakeShellyClient()
    service = ShellyIrrigationScheduleService(
        app_engine,
        client=client,
        clock=lambda: DUE_AT,
    )

    await service.run_once()

    assert [target.device_id for target, _ in client.calls] == [
        "test-shelly-irrigation-configured"
    ]


async def test_irrigation_scheduler_records_failed_dispatch(app_engine) -> None:
    async with AsyncSession(app_engine) as session:
        await _add_irrigation_schedule(session, suffix="failure")
        await session.commit()

    client = _FakeShellyClient(fail=True)
    service = ShellyIrrigationScheduleService(
        app_engine,
        client=client,
        clock=lambda: DUE_AT,
    )

    results = await service.run_once()

    async with AsyncSession(app_engine) as session:
        runs = await _runs(session)

    assert [result.status for result in results] == ["failed"]
    assert "simulated Shelly failure" in (results[0].error or "")
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert "simulated Shelly failure" in (runs[0].error or "")
