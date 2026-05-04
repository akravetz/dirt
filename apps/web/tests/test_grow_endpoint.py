"""Unit tests for GET /api/grow/current.

The endpoint is a thin FastAPI wrapper around
``GrowStateService.get_grow_current_payload()``; tests drive the full
ASGI stack with an isolated Postgres DB and assert the JSON response
deserializes into the generated Pydantic ``GrowCurrent`` model.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from dirt_contracts.webapp_v1.models import GrowCurrent, GrowFlowerFlipRequest, Stage
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.schedule import Schedule
from dirt_shared.services.scope import current_grow_run
from dirt_web.app import create_app


async def _update_current_grow(
    engine,
    *,
    germination_date: date = date(2026, 3, 15),
    flower_start_date: date | None = None,
    strain: str = "Sirius Black × BS01",
    plant_count: int = 4,
    lights_on_local: time = time(5, 0, 0),
    lights_off_local: time = time(23, 0, 0),
) -> None:
    """Mutate the template-seeded default main GrowRun row.

    The multi-tent migrations seed exactly one current grow run for
    ``homebox/main``. Other tents may have their own current row.
    """
    async with AsyncSession(engine) as s:
        row = await current_grow_run(s)
        assert row is not None
        row.germination_date = germination_date
        row.flower_start_date = flower_start_date
        row.strain = strain
        row.plant_count = plant_count
        s.add(row)
        schedule = (
            await s.exec(
                select(Schedule)
                .where(Schedule.site_id == row.site_id)
                .where(Schedule.tent_id == row.tent_id)
                .where(Schedule.kind == "lights")
                .limit(1)
            )
        ).first()
        assert schedule is not None
        schedule.starts_local = lights_on_local
        schedule.ends_local = lights_off_local
        s.add(schedule)
        await s.commit()


@pytest.fixture
async def client(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "changeme"},
        )
        ac.cookies = login.cookies
        yield ac


async def test_grow_current_requires_auth():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/grow/current")
        # AuthMiddleware returns 401 JSON for unauthenticated /api/*
        # callers — the SPA handles redirection client-side.
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")


async def test_grow_current_returns_contract_shape(client: AsyncClient, app_engine):
    await _update_current_grow(app_engine)
    response = await client.get("/api/grow/current")
    assert response.status_code == 200
    model = GrowCurrent.model_validate(response.json())

    assert model.germination_date == date(2026, 3, 15)
    assert model.flower_start_date is None
    assert model.stage == Stage.veg
    assert model.flower_week_number is None
    assert model.strain == "Sirius Black × BS01"
    assert model.plant_count == 4
    assert model.day_number >= 1
    assert model.grow_week_number >= 1
    assert model.lights.on_local == "05:00:00"
    assert model.lights.off_local == "23:00:00"
    assert model.lights.minutes_until_off > 0
    assert model.lights.minutes_until_on > 0


async def test_grow_current_flower_stage_derivation(client: AsyncClient, app_engine):
    # Flower start 30 days ago → stage = flower_late (≥21 days in flower).
    today = datetime.now(UTC).date()
    flower_start = today - timedelta(days=30)
    await _update_current_grow(
        app_engine,
        germination_date=today - timedelta(days=90),
        flower_start_date=flower_start,
    )

    response = await client.get("/api/grow/current")
    assert response.status_code == 200
    model = GrowCurrent.model_validate(response.json())

    assert model.flower_start_date == flower_start
    assert model.stage == Stage.flower_late
    # 30 days in flower → week 5 (days 29–35).
    assert model.flower_week_number == 5


async def test_grow_flower_flip_updates_current_grow(client: AsyncClient, app_engine):
    await _update_current_grow(app_engine)
    flower_start = datetime.now(ZoneInfo("America/Denver")).date()
    payload = GrowFlowerFlipRequest(
        flower_start_date=flower_start,
        lights_on_local="09:00:00",
        lights_off_local="21:00:00",
    )

    response = await client.post(
        "/api/grow/flower-flip",
        json=payload.model_dump(mode="json"),
    )
    assert response.status_code == 200
    model = GrowCurrent.model_validate(response.json())

    assert model.flower_start_date == flower_start
    assert model.stage == Stage.flower_early
    assert model.flower_week_number == 1
    assert model.lights.on_local == "09:00:00"
    assert model.lights.off_local == "21:00:00"


async def test_grow_flower_flip_rejects_non_12_12_schedule(
    client: AsyncClient, app_engine
):
    await _update_current_grow(app_engine)

    response = await client.post(
        "/api/grow/flower-flip",
        json={
            "flower_start_date": "2026-05-03",
            "lights_on_local": "09:00:00",
            "lights_off_local": "22:00:00",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "flower light schedule must be exactly 12 hours on"
    }
