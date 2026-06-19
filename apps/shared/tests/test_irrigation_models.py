"""Database constraints for irrigation pulse storage."""

from __future__ import annotations

from datetime import UTC, datetime, time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models import (
    Capability,
    Device,
    IrrigationRun,
    IrrigationScheduleItem,
    Schedule,
    Site,
    Tent,
)
from dirt_shared.services.scope import require_default_site_pk
from dirt_shared.testing import resolve_test_tent_pk


async def _create_irrigation_fixture(session: AsyncSession):
    site_pk = await require_default_site_pk(session)
    site = (await session.exec(select(Site).where(Site.id == site_pk))).one()
    tent_pk = await resolve_test_tent_pk(session, "main", site_pk=site.id)
    tent = (await session.exec(select(Tent).where(Tent.id == tent_pk))).one()
    device = Device(
        site_id=site.id,
        tent_id=tent.id,
        device_id="test-irrigation-pump",
        name="Test irrigation pump",
        kind="actuator",
        controller="test",
    )
    session.add(device)
    await session.flush()

    capability = Capability(
        device_id=device.id,
        capability_id="pump_power",
        name="Pump Power",
        kind="actuator",
        metric_name="pump_on",
        unit="bool",
        source="test",
    )
    session.add(capability)
    await session.flush()

    schedule = Schedule(
        site_id=site.id,
        tent_id=tent.id,
        device_id=device.id,
        capability_id=capability.id,
        kind="irrigation",
        enabled=False,
    )
    session.add(schedule)
    await session.flush()

    item = IrrigationScheduleItem(
        schedule_id=schedule.id,
        starts_local=time(6, 30),
        duration_s=5,
        enabled=True,
    )
    session.add(item)
    await session.flush()

    return schedule, item, device, capability


async def test_irrigation_schedule_item_rejects_non_positive_duration(app_engine):
    async with AsyncSession(app_engine) as session:
        schedule, _, _, _ = await _create_irrigation_fixture(session)
        session.add(
            IrrigationScheduleItem(
                schedule_id=schedule.id,
                starts_local=time(7, 0),
                duration_s=0,
            )
        )

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.parametrize(
    ("duration_s", "status"),
    [
        (0, "pending"),
        (5, "queued"),
    ],
)
async def test_irrigation_run_rejects_invalid_control_fields(
    app_engine, duration_s, status
):
    async with AsyncSession(app_engine) as session:
        schedule, item, device, capability = await _create_irrigation_fixture(session)
        session.add(
            IrrigationRun(
                schedule_id=schedule.id,
                schedule_item_id=item.id,
                device_id=device.id,
                capability_id=capability.id,
                intended_start_at=datetime(2026, 5, 25, 12, 30, tzinfo=UTC),
                duration_s=duration_s,
                status=status,
            )
        )

        with pytest.raises(IntegrityError):
            await session.commit()


async def test_irrigation_run_prevents_duplicate_logical_pulse(app_engine):
    async with AsyncSession(app_engine) as session:
        schedule, item, device, capability = await _create_irrigation_fixture(session)
        intended_start_at = datetime(2026, 5, 25, 12, 30, tzinfo=UTC)
        run_kwargs = {
            "schedule_id": schedule.id,
            "schedule_item_id": item.id,
            "device_id": device.id,
            "capability_id": capability.id,
            "intended_start_at": intended_start_at,
            "duration_s": 5,
            "status": "pending",
        }
        session.add(IrrigationRun(**run_kwargs))
        await session.commit()

        session.add(IrrigationRun(**run_kwargs))
        with pytest.raises(IntegrityError):
            await session.commit()
