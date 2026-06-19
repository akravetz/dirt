"""Migration-backed smoke tests for scoped controller identity rows."""

from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.plant import Plant, PlantLocationHistory
from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone


async def test_default_site_tents_zones_and_capabilities_are_seeded(app_engine):
    async with AsyncSession(app_engine) as session:
        site = (await session.exec(select(Site).where(Site.is_default.is_(True)))).one()
        tents = (
            await session.exec(
                select(Tent).where(Tent.site_id == site.id).order_by(Tent.role)
            )
        ).all()

        main = next(t for t in tents if t.is_default)
        breeding = next(t for t in tents if t.role == "breeding")

        zone_names = {
            zone.name
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
        breeding_env = (
            await session.exec(
                select(Device)
                .where(Device.site_id == site.id)
                .where(Device.tent_id == breeding.id)
                .where(Device.device_id == "breeding-env-node")
            )
        ).one()
        breeding_caps = {
            cap.capability_id
            for cap in (
                await session.exec(
                    select(Capability).where(Capability.device_id == breeding_env.id)
                )
            ).all()
        }

    assert site.is_default is True
    assert main.is_default is True
    assert main.role == "flower"
    assert breeding.is_default is False
    assert breeding.role == "breeding"
    # topology-contract-ok: this test intentionally pins migrated seed topology.
    assert breeding_env.zone_id is not None
    assert {"temperature_f", "humidity_pct", "vpd_kpa"} <= breeding_caps
    assert {
        "Canopy",
        "Reservoir",
        "Plant A",
        "Plant B",
        "Plant C",
        "Plant D",
        "Exhaust",
        "Lights",
    } <= zone_names
    assert {"temperature_f", "humidity_pct", "vpd_kpa", "fan_pct"} <= fan_caps


async def test_current_main_plant_locations_are_seeded(app_engine):
    async with AsyncSession(app_engine) as session:
        result = await session.exec(
            select(Plant, PlantLocationHistory)
            .join(PlantLocationHistory, PlantLocationHistory.plant_id == Plant.id)
            .join(Tent, Tent.id == PlantLocationHistory.tent_id)
            .where(Tent.is_default.is_(True))
            .where(PlantLocationHistory.end_at.is_(None))
            .order_by(PlantLocationHistory.grid_position, Plant.key)
        )
        rows = result.all()

    assert [plant.key for plant, _ in rows] == [
        "SBBS-R1-001",
        "SBBS-R1-002",
        "SBBS-R1-003",
        "SBBS-R1-004",
    ]
    assert [location.grid_position for _, location in rows] == ["A1", "B1", "C1", "D1"]
