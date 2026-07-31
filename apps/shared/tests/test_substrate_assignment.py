from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models import (
    Capability,
    Device,
    Plant,
    PlantLine,
    PlantLocationHistory,
    PlantMetricStream,
    Site,
    Tent,
)
from dirt_shared.services.scope import require_default_site_pk
from dirt_shared.services.substrate_assignment import (
    SUBSTRATE_METRIC_DISPLAY_ORDER,
    SubstrateAssignmentError,
    assign_substrate_probe,
    list_substrate_assignments,
    normalize_modbus_address,
)


async def _seed_assignment_fixture(
    engine: AsyncEngine,
    *,
    metrics: tuple[str, ...] = tuple(SUBSTRATE_METRIC_DISPLAY_ORDER),
) -> tuple[int, int, list[int], int]:
    async with AsyncSession(engine) as session:
        site_id = await require_default_site_pk(session)
        tent = (
            await session.exec(
                select(Tent).where(Tent.site_id == site_id).order_by(Tent.id)
            )
        ).first()
        assert tent.id is not None
        target_tent = Tent(
            site_id=site_id,
            name="Target substrate test tent",
            role="test-target",
        )
        session.add(target_tent)
        await session.flush()
        assert target_tent.id is not None
        line = PlantLine(
            project_code="TEST-SUBSTRATE",
            generation_label="R1",
            strain="Test substrate line",
            cultivar="R1",
        )
        session.add(line)
        await session.flush()
        assert line.id is not None
        previous_plant = Plant(
            key="TEST-OLD-001",
            name="Previous test plant",
            line_id=line.id,
        )
        target_plant = Plant(
            key="TEST-NEW-001",
            name="Target test plant",
            line_id=line.id,
        )
        session.add_all([previous_plant, target_plant])
        await session.flush()
        assert previous_plant.id is not None
        assert target_plant.id is not None
        session.add(
            PlantLocationHistory(
                plant_id=target_plant.id,
                site_id=site_id,
                tent_id=target_tent.id,
                start_at=datetime(2026, 7, 21, tzinfo=UTC),
            )
        )
        device = Device(
            site_id=site_id,
            tent_id=tent.id,
            device_id="test-substrate-assignment-node",
            name="Test substrate assignment probe",
            kind="moisture_node",
            controller="esp32",
            metadata_json={
                "bus": "rs485",
                "modbus_address": "0x0A",
                "sensor_model": "DFRobot SEN0604",
            },
        )
        session.add(device)
        await session.flush()
        assert device.id is not None
        capabilities = [
            Capability(
                device_id=device.id,
                capability_id=metric,
                name=metric,
                kind="measurement",
                metric_name=metric,
                unit="test",
                source="esp32",
            )
            for metric in metrics
        ]
        session.add_all(capabilities)
        await session.flush()
        capability_ids = [item.id for item in capabilities]
        assert all(item is not None for item in capability_ids)
        previous_plant_id = previous_plant.id
        target_plant_id = target_plant.id
        target_tent_id = target_tent.id
        session.add_all(
            PlantMetricStream(
                plant_id=previous_plant.id,
                capability_id=capability_id,
                display_order=index,
                is_active=True,
            )
            for index, capability_id in enumerate(capability_ids, start=1)
            if capability_id is not None
        )
        await session.commit()
        return (
            previous_plant_id,
            target_plant_id,
            [item for item in capability_ids if item is not None],
            target_tent_id,
        )


def test_normalize_modbus_address_accepts_hex_and_decimal() -> None:
    assert normalize_modbus_address("0x0a") == "0x0A"
    assert normalize_modbus_address("10") == "0x0A"


@pytest.mark.parametrize("value", ["", "probe-a", "0", "248"])
def test_normalize_modbus_address_rejects_invalid_values(value: str) -> None:
    with pytest.raises(SubstrateAssignmentError):
        normalize_modbus_address(value)


async def test_assign_substrate_probe_moves_all_four_streams_and_is_idempotent(
    app_engine: AsyncEngine,
) -> None:
    (
        previous_plant_id,
        target_plant_id,
        capability_ids,
        target_tent_id,
    ) = await _seed_assignment_fixture(app_engine)

    first = await assign_substrate_probe(
        app_engine,
        bus_id="10",
        plant_key="test-new-001",
    )
    second = await assign_substrate_probe(
        app_engine,
        bus_id="0x0A",
        plant_key="TEST-NEW-001",
    )

    assert first.bus_id == "0x0A"
    assert first.plant_key == "TEST-NEW-001"
    assert first.tent_id == target_tent_id
    assert first.previous_plant_keys == ("TEST-OLD-001",)
    assert second.previous_plant_keys == ()
    async with AsyncSession(app_engine) as session:
        device = (
            await session.exec(
                select(Device).where(
                    Device.device_id == "test-substrate-assignment-node"
                )
            )
        ).one()
        streams = (
            await session.exec(
                select(PlantMetricStream)
                .where(col(PlantMetricStream.capability_id).in_(capability_ids))
                .order_by(PlantMetricStream.plant_id, PlantMetricStream.display_order)
            )
        ).all()
    assert device.tent_id == target_tent_id
    assert device.zone_id is None
    previous = [item for item in streams if item.plant_id == previous_plant_id]
    target = [item for item in streams if item.plant_id == target_plant_id]
    assert len(previous) == 4
    assert not any(item.is_active for item in previous)
    assert len(target) == 4
    assert all(item.is_active for item in target)
    assert [item.display_order for item in target] == [1, 2, 3, 4]

    assignments = await list_substrate_assignments(app_engine)
    assignment = next(item for item in assignments if item.bus_id == "0x0A")
    assert assignment.plant_keys == ("TEST-NEW-001",)


async def test_assign_substrate_probe_rejects_incomplete_probe_without_changes(
    app_engine: AsyncEngine,
) -> None:
    previous_plant_id, _, capability_ids, _ = await _seed_assignment_fixture(
        app_engine,
        metrics=(
            "soil_moisture_pct",
            "substrate_temp_c",
            "substrate_ec_us_cm",
        ),
    )

    with pytest.raises(SubstrateAssignmentError, match="substrate_ph"):
        await assign_substrate_probe(
            app_engine,
            bus_id="0x0A",
            plant_key="TEST-NEW-001",
        )

    async with AsyncSession(app_engine) as session:
        active_streams = (
            await session.exec(
                select(PlantMetricStream)
                .where(col(PlantMetricStream.capability_id).in_(capability_ids))
                .where(PlantMetricStream.is_active.is_(True))
            )
        ).all()
    assert len(active_streams) == 3
    assert {item.plant_id for item in active_streams} == {previous_plant_id}


async def test_assign_substrate_probe_requires_a_current_plant(
    app_engine: AsyncEngine,
) -> None:
    await _seed_assignment_fixture(app_engine)

    with pytest.raises(SubstrateAssignmentError, match="no current plant"):
        await assign_substrate_probe(
            app_engine,
            bus_id="0x0A",
            plant_key="TEST-OLD-001",
        )


async def test_assign_substrate_probe_rejects_a_plant_at_another_site(
    app_engine: AsyncEngine,
) -> None:
    _, target_plant_id, _, _ = await _seed_assignment_fixture(app_engine)
    async with AsyncSession(app_engine) as session:
        other_site = Site(name="Other substrate test site")
        session.add(other_site)
        await session.flush()
        assert other_site.id is not None
        other_tent = Tent(
            site_id=other_site.id,
            name="Other substrate test tent",
            role="test",
        )
        session.add(other_tent)
        await session.flush()
        assert other_tent.id is not None
        location = (
            await session.exec(
                select(PlantLocationHistory).where(
                    PlantLocationHistory.plant_id == target_plant_id,
                    PlantLocationHistory.end_at.is_(None),
                )
            )
        ).one()
        location.site_id = other_site.id
        location.tent_id = other_tent.id
        await session.commit()

    with pytest.raises(SubstrateAssignmentError, match="no current plant"):
        await assign_substrate_probe(
            app_engine,
            bus_id="0x0A",
            plant_key="TEST-NEW-001",
        )
