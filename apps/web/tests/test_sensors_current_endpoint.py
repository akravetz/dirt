"""Unit tests for GET /api/sensors/current.

The endpoint composes ``ReadingsService.get_latest_reading``,
``grow_state.STAGE_TARGETS``, and ``grow_state.band_status``. The
reservoir is now real: ``reservoir_in`` is read from the ``reservoir``
capability (firmware does the cm → in conversion at publish time, so
the persisted unit matches the contract). Tests drive the full ASGI
stack with an isolated Postgres DB and assert the JSON body
deserializes into the generated Pydantic ``SensorsCurrent`` model.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

import pytest
from dirt_contracts.webapp_v1.models import SensorsCurrent
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorSource
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.scope import resolve_scope
from dirt_web.app import create_app


async def _capability_id(
    engine,
    *,
    device_id: str,
    metric_name: str,
) -> int:
    async with AsyncSession(engine) as s:
        result = await s.exec(
            select(Capability.id)
            .join(Device, Device.id == Capability.device_id)
            .where(Device.device_id == device_id)
            .where(Capability.metric_name == metric_name)
        )
        cap_id = result.one()
        return cap_id


async def _seed_readings(
    engine,
    *,
    temperature_f: float = 72.0,
    humidity_pct: float = 50.0,
    vpd_kpa: float = 1.0,
    reservoir_in: float = 23.62,
    stale: bool = False,
) -> None:
    """Seed a single batch of fresh readings at "now" for the five metrics.

    When ``stale=True`` we also backfill ``threshold`` identical
    temperature_f readings so ``is_sensor_stale()`` flips to True. The
    threshold is read from ``ReadingsService.is_sensor_stale``'s own
    default (the implementation's source of truth) rather than hardcoded
    here — if the default changes, this test still exercises the true
    boundary.
    """
    tent_caps = {
        metric: await _capability_id(
            engine, device_id="fan-controller", metric_name=metric
        )
        for metric in (
            "temperature_f",
            "humidity_pct",
            "vpd_kpa",
            "dew_point_f",
            "fan_duty_pct",
        )
    }
    reservoir_cap = await _capability_id(
        engine, device_id="reservoir-node", metric_name="reservoir_in"
    )
    now = datetime.now(UTC)
    rows: list[SensorReading] = []

    def add(
        metric: str,
        value: float,
        ts: datetime,
        capability_id: int | None = None,
    ) -> None:
        rows.append(
            SensorReading(
                ts=ts,
                capability_id=capability_id or tent_caps[metric],
                metric=metric,
                value=value,
                source=SensorSource.ARDUINO,
            )
        )

    # One fresh reading per metric.
    for metric, value in {
        "temperature_f": temperature_f,
        "humidity_pct": humidity_pct,
        "vpd_kpa": vpd_kpa,
        "dew_point_f": 55.0,
        "fan_duty_pct": 30.0,
    }.items():
        add(metric, value, now)
    add("reservoir_in", reservoir_in, now, reservoir_cap)

    if stale:
        threshold = (
            inspect.signature(ReadingsService.is_sensor_stale)
            .parameters["threshold"]
            .default
        )
        # Backfill identical temperature_f readings so the last N are
        # all the same value — the staleness signal the service defines.
        for i in range(1, threshold + 2):
            add("temperature_f", temperature_f, now - timedelta(minutes=i))

    async with AsyncSession(engine) as s:
        s.add_all(rows)
        await s.commit()


async def _seed_breeding_temperature(engine, value: float) -> None:
    async with AsyncSession(engine) as s:
        breeding = await resolve_scope(s, tent_id="breeding")
        assert breeding is not None
        device = Device(
            site_id=breeding.site_pk,
            tent_id=breeding.tent_pk,
            device_id="breeding-current-node",
            name="Breeding current node",
            kind="env_sensor",
            controller="test",
        )
        s.add(device)
        await s.flush()
        assert device.id is not None
        capability = Capability(
            device_id=device.id,
            capability_id="temperature_f",
            name="Temperature F",
            kind="measurement",
            metric_name="temperature_f",
            unit="degF",
            source="test",
        )
        s.add(capability)
        await s.flush()
        assert capability.id is not None
        s.add(
            SensorReading(
                ts=datetime.now(UTC),
                capability_id=capability.id,
                metric="temperature_f",
                value=value,
                source=SensorSource.MOCK,
            )
        )
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


async def test_sensors_current_requires_auth():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/sensors/current")
        # AuthMiddleware returns 401 JSON for unauthenticated /api/* —
        # the SPA handles /login routing client-side.
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")


async def test_sensors_current_returns_contract_shape(client: AsyncClient, app_engine):
    await _seed_readings(app_engine, temperature_f=72.0, humidity_pct=50.0, vpd_kpa=1.0)
    response = await client.get("/api/sensors/current")
    assert response.status_code == 200
    model = SensorsCurrent.model_validate(response.json())

    # All five metrics populated.
    assert model.metrics.temperature_f.value == pytest.approx(72.0)
    assert model.metrics.humidity_pct.value == pytest.approx(50.0)
    assert model.metrics.vpd_kpa.value == pytest.approx(1.0)
    assert model.metrics.fan_pct.value == pytest.approx(30.0)
    # Reservoir: firmware emits inches natively, server stores as-is.
    assert model.metrics.reservoir_in.value == pytest.approx(23.62)

    # Target bands present for every metric defined in STAGE_TARGETS;
    # absent for fan_pct and reservoir_in (no per-stage band declared).
    assert model.metrics.temperature_f.target is not None
    assert model.metrics.humidity_pct.target is not None
    assert model.metrics.vpd_kpa.target is not None
    assert model.metrics.fan_pct.target is not None
    assert model.metrics.reservoir_in.target is None

    # Veg-stage bands: temp 70-82, humidity envelope, tightened VPD, fan 20-80.
    # Seeded values sit inside each band → status "ok".
    assert model.metrics.temperature_f.status.value == "ok"
    assert model.metrics.humidity_pct.status.value == "ok"
    assert model.metrics.vpd_kpa.status.value == "ok"
    assert model.metrics.fan_pct.status.value == "ok"

    # Fresh seed → not stale.
    assert model.stale is False


async def test_sensors_current_accepts_tent_scope(client: AsyncClient, app_engine):
    await _seed_readings(app_engine, temperature_f=72.0)
    await _seed_breeding_temperature(app_engine, value=88.0)

    default_response = await client.get("/api/sensors/current")
    scoped_response = await client.get(
        "/api/sensors/current", params={"tent_id": "breeding"}
    )

    assert default_response.status_code == 200
    assert scoped_response.status_code == 200
    default_model = SensorsCurrent.model_validate(default_response.json())
    scoped_model = SensorsCurrent.model_validate(scoped_response.json())
    assert default_model.metrics.temperature_f.value == pytest.approx(72.0)
    assert scoped_model.metrics.temperature_f.value == pytest.approx(88.0)
    assert scoped_model.stale is False


async def test_sensors_current_stale_flag(client: AsyncClient, app_engine):
    # Seed a run of identical temperature_f readings long enough to
    # satisfy ReadingsService.is_sensor_stale's default threshold.
    await _seed_readings(app_engine, stale=True)
    response = await client.get("/api/sensors/current")
    assert response.status_code == 200
    model = SensorsCurrent.model_validate(response.json())
    assert model.stale is True
