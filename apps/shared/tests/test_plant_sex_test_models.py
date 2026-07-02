"""Database constraints for plant sex test storage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models import Plant, PlantSexTest

COLLECTED_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
SENT_AT = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
RECEIVED_AT = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)


async def _plant_ids(session: AsyncSession, count: int = 1) -> list[int]:
    ids = (await session.exec(select(Plant.id).order_by(Plant.id))).all()
    assert len(ids) >= count
    return ids[:count]


def _sex_test_kwargs(
    plant_id: int,
    *,
    vendor_test_code: str = "FF-001",
    **overrides,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "plant_id": plant_id,
        "vendor_name": "Farmer Freeman",
        "assay_name": "EZ-XY",
        "vendor_test_code": vendor_test_code,
        "sample_collected_at": COLLECTED_AT,
    }
    kwargs.update(overrides)
    return kwargs


async def test_plant_sex_test_persists_pending_and_received_rows(app_engine) -> None:
    async with AsyncSession(app_engine) as session:
        plant_a_id, plant_b_id = await _plant_ids(session, count=2)
        session.add(
            PlantSexTest(**_sex_test_kwargs(plant_a_id, vendor_test_code="FF-001"))
        )
        session.add(
            PlantSexTest(
                **_sex_test_kwargs(
                    plant_b_id,
                    vendor_test_code="FF-002",
                    sample_sent_at=SENT_AT,
                    result_received_at=RECEIVED_AT,
                    result_sex_key="female",
                    notes="Result entered from vendor portal.",
                )
            )
        )

        await session.commit()

        rows = (
            await session.exec(
                select(PlantSexTest).order_by(PlantSexTest.vendor_test_code)
            )
        ).all()

    assert [row.vendor_test_code for row in rows] == ["FF-001", "FF-002"]
    assert rows[0].result_received_at is None
    assert rows[0].is_inconclusive is False
    assert rows[1].result_sex_key == "female"


@pytest.mark.parametrize(
    "overrides",
    [
        {"vendor_name": " "},
        {"assay_name": " "},
        {"vendor_test_code": " "},
        {"notes": " "},
    ],
)
async def test_plant_sex_test_rejects_blank_text_fields(
    app_engine,
    overrides: dict[str, object],
) -> None:
    async with AsyncSession(app_engine) as session:
        (plant_id,) = await _plant_ids(session)
        session.add(PlantSexTest(**_sex_test_kwargs(plant_id, **overrides)))

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"sample_sent_at": COLLECTED_AT - timedelta(hours=1)},
        {
            "result_received_at": COLLECTED_AT - timedelta(hours=1),
            "result_sex_key": "female",
        },
        {
            "sample_sent_at": SENT_AT,
            "result_received_at": SENT_AT - timedelta(hours=1),
            "result_sex_key": "female",
        },
    ],
)
async def test_plant_sex_test_rejects_impossible_timestamp_order(
    app_engine,
    overrides: dict[str, object],
) -> None:
    async with AsyncSession(app_engine) as session:
        (plant_id,) = await _plant_ids(session)
        session.add(PlantSexTest(**_sex_test_kwargs(plant_id, **overrides)))

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"result_sex_key": "female"},
        {"is_inconclusive": True},
        {"result_received_at": RECEIVED_AT},
        {
            "result_received_at": RECEIVED_AT,
            "result_sex_key": "female",
            "is_inconclusive": True,
        },
    ],
)
async def test_plant_sex_test_rejects_invalid_result_state(
    app_engine,
    overrides: dict[str, object],
) -> None:
    async with AsyncSession(app_engine) as session:
        (plant_id,) = await _plant_ids(session)
        session.add(PlantSexTest(**_sex_test_kwargs(plant_id, **overrides)))

        with pytest.raises(IntegrityError):
            await session.commit()


async def test_plant_sex_test_prevents_duplicate_vendor_codes(app_engine) -> None:
    async with AsyncSession(app_engine) as session:
        plant_a_id, plant_b_id = await _plant_ids(session, count=2)
        session.add(
            PlantSexTest(**_sex_test_kwargs(plant_a_id, vendor_test_code="FF-001"))
        )
        await session.commit()

        session.add(
            PlantSexTest(**_sex_test_kwargs(plant_b_id, vendor_test_code="FF-001"))
        )

        with pytest.raises(IntegrityError):
            await session.commit()


async def test_plant_sex_test_allows_only_one_pending_test_per_plant(
    app_engine,
) -> None:
    async with AsyncSession(app_engine) as session:
        (plant_id,) = await _plant_ids(session)
        session.add(
            PlantSexTest(**_sex_test_kwargs(plant_id, vendor_test_code="FF-001"))
        )
        await session.commit()

        session.add(
            PlantSexTest(**_sex_test_kwargs(plant_id, vendor_test_code="FF-002"))
        )

        with pytest.raises(IntegrityError):
            await session.commit()
