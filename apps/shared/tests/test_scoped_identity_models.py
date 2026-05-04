"""Migration-backed smoke tests for scoped controller identity rows."""

from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.grow_run import GrowRun
from dirt_shared.models.plant import Plant
from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone


async def test_default_site_tents_zones_and_capabilities_are_seeded(app_engine):
    async with AsyncSession(app_engine) as session:
        site = (await session.exec(select(Site).where(Site.site_id == "homebox"))).one()
        tents = (
            await session.exec(
                select(Tent).where(Tent.site_id == site.id).order_by(Tent.tent_id)
            )
        ).all()

        main = next(t for t in tents if t.tent_id == "main")
        breeding = next(t for t in tents if t.tent_id == "breeding")

        zone_ids = {
            zone.zone_id
            for zone in (
                await session.exec(select(Zone).where(Zone.tent_id == main.id))
            ).all()
        }

        fan = (
            await session.exec(
                select(Device).where(
                    Device.site_id == site.id,
                    Device.device_id == "fan-controller",
                )
            )
        ).one()
        fan_caps = {
            cap.capability_id
            for cap in (
                await session.exec(
                    select(Capability).where(Capability.device_id == fan.id)
                )
            ).all()
        }

    assert site.is_default is True
    assert main.is_default is True
    assert main.role == "flower"
    assert breeding.is_default is False
    assert breeding.role == "breeding"
    assert {
        "canopy",
        "reservoir",
        "plant-a",
        "plant-b",
        "plant-c",
        "plant-d",
        "exhaust",
        "lights",
    } <= zone_ids
    assert {"temperature_f", "humidity_pct", "vpd_kpa", "fan_duty_pct"} <= fan_caps


async def test_current_main_growrun_and_plants_are_seeded(app_engine):
    async with AsyncSession(app_engine) as session:
        result = await session.exec(
            select(GrowRun, Plant)
            .join(Plant, Plant.growrun_id == GrowRun.id)
            .where(GrowRun.is_current.is_(True))
            .order_by(Plant.code)
        )
        rows = result.all()

    assert [plant.code for _, plant in rows] == ["a", "b", "c", "d"]
    assert [plant.plant_id for _, plant in rows] == ["a", "b", "c", "d"]
    assert {grow.grow_run_id for grow, _ in rows} == {"main-2026-03-15"}
