"""Scoped site/tent API smoke tests for the multi-tent model."""

from __future__ import annotations

from datetime import date, time

import pytest
from dirt_contracts.webapp_v1.models import (
    GrowCurrent,
    SitesResponse,
    TentDevicesResponse,
    TentsResponse,
)
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.grow_run import GrowRun
from dirt_shared.services.scope import resolve_scope
from dirt_web.app import create_app


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


async def _insert_breeding_grow(app_engine) -> None:
    async with AsyncSession(app_engine) as session:
        scope = await resolve_scope(session, site_id="homebox", tent_id="breeding")
        assert scope is not None
        session.add(
            GrowRun(
                site_id=scope.site_pk,
                tent_id=scope.tent_pk,
                grow_run_id="breeding-2026-05-01",
                name="Breeding trial",
                purpose="breeding",
                germination_date=date(2026, 5, 1),
                flower_start_date=None,
                lights_on_local=time(6, 0),
                lights_off_local=time(18, 0),
                strain="Breeding stock",
                location="Denver, MT · breeding tent",
                timezone="America/Denver",
                plant_count=0,
                is_current=True,
            )
        )
        await session.commit()


async def test_scope_endpoints_require_auth():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/sites")

    assert response.status_code == 401


async def test_sites_and_tents_list_default_local_scope(client: AsyncClient):
    sites_response = await client.get("/api/sites")
    assert sites_response.status_code == 200
    sites = SitesResponse.model_validate(sites_response.json()).sites

    assert [site.site_id for site in sites] == ["homebox"]
    assert sites[0].is_default is True

    tents_response = await client.get("/api/tents")
    assert tents_response.status_code == 200
    tents = TentsResponse.model_validate(tents_response.json()).tents

    assert [tent.tent_id for tent in tents] == ["main", "breeding"]
    assert [tent.role for tent in tents] == ["flower", "breeding"]
    assert tents[0].is_default is True


async def test_tent_grow_current_is_scoped_and_preserves_main_default(
    client: AsyncClient,
    app_engine,
):
    missing = await client.get("/api/tents/breeding/grow/current")
    assert missing.status_code == 404

    await _insert_breeding_grow(app_engine)

    main_response = await client.get("/api/grow/current")
    assert main_response.status_code == 200
    main = GrowCurrent.model_validate(main_response.json())
    assert main.strain == "Sirius Black × BS01"
    assert main.plant_count == 4

    breeding_response = await client.get("/api/tents/breeding/grow/current")
    assert breeding_response.status_code == 200
    breeding = GrowCurrent.model_validate(breeding_response.json())
    assert breeding.strain == "Breeding stock"
    assert breeding.location == "Denver, MT · breeding tent"
    assert breeding.plant_count == 0
    assert breeding.lights.on_local == "06:00:00"
    assert breeding.lights.off_local == "18:00:00"


async def test_tent_devices_are_scoped(client: AsyncClient):
    main_response = await client.get("/api/tents/main/devices")
    assert main_response.status_code == 200
    main = TentDevicesResponse.model_validate(main_response.json())
    main_device_ids = {device.device_id for device in main.devices}

    assert main.site_id == "homebox"
    assert main.tent_id == "main"
    assert {
        "fan-controller",
        "plant-a-node",
        "plant-b-node",
        "plant-c-node",
        "plant-d-node",
        "govee-h7142-main",
        "obsbot-main",
        "reservoir-node",
        "kasa-lights-main",
    } <= main_device_ids
    assert "jabra-claudia" not in main_device_ids

    breeding_response = await client.get("/api/tents/breeding/devices")
    assert breeding_response.status_code == 200
    breeding = TentDevicesResponse.model_validate(breeding_response.json())
    assert breeding.site_id == "homebox"
    assert breeding.tent_id == "breeding"
    assert breeding.devices == []

    missing_response = await client.get("/api/tents/missing/devices")
    assert missing_response.status_code == 404
