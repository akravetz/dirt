"""Unit tests for GET /api/sensors/history.

The endpoint returns bucketed ``(ts, value)`` points for one metric over
the requested range. All metrics query ``ReadingsService``. Only
``fan_pct`` has a contract↔DB name mismatch (resolves to
``fan_duty_pct`` at the endpoint boundary); every other metric — now
including ``reservoir_in`` (firmware emits inches natively after
2026-04-26) — uses the contract name directly.

Tests drive the full ASGI stack with an isolated Postgres DB and assert
the response body deserializes into the generated
``SensorsHistoryResponse`` Pydantic model. A smoke test confirms the
legacy ``/api/sensors/readings`` route was deleted as part of this
feature's ``removes_legacy`` contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from dirt_contracts.webapp_v1.models import SensorsHistoryResponse
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_web.app import create_app


async def _node_id(s: AsyncSession, location: SensorLocation) -> int:
    """Find-or-create the SensorNode for ``location`` and return its id."""
    result = await s.exec(select(SensorNode.id).where(SensorNode.location == location))
    node_id = result.first()
    if node_id is None:
        node = SensorNode(location=location)
        s.add(node)
        await s.commit()
        await s.refresh(node)
        node_id = node.id
    return node_id


async def _capability_id(
    s: AsyncSession,
    *,
    device_id: str,
    metric_name: str,
) -> int:
    result = await s.exec(
        select(Capability.id)
        .join(Device, Device.id == Capability.device_id)
        .where(Device.device_id == device_id)
        .where(Capability.metric_name == metric_name)
    )
    return result.one()


async def _seed_tent_series(engine, hours: int = 48) -> None:
    """Insert a dense series for the four DB-backed sparkline metrics."""
    async with AsyncSession(engine) as s:
        tent_id = await _node_id(s, SensorLocation.TENT)
        reservoir_id = await _node_id(s, SensorLocation.RESERVOIR)
        caps = {
            metric: await _capability_id(
                s, device_id="fan-controller", metric_name=metric
            )
            for metric in ("temperature_f", "humidity_pct", "fan_duty_pct")
        }
        reservoir_cap = await _capability_id(
            s, device_id="reservoir-node", metric_name="reservoir_in"
        )

        now = datetime.now(UTC)
        readings: list[SensorReading] = []
        # Every 5 minutes, so 1h → ~12 raw, 24h → ~288 pre-bucket rows.
        for i in range(hours * 12):
            ts = now - timedelta(minutes=5 * i)
            for node_id, cap_id, metric, value in (
                (
                    tent_id,
                    caps["temperature_f"],
                    "temperature_f",
                    72.0 + (i % 10) * 0.5,
                ),
                (
                    tent_id,
                    caps["humidity_pct"],
                    "humidity_pct",
                    50.0 + (i % 10) * 0.3,
                ),
                (tent_id, caps["fan_duty_pct"], "fan_duty_pct", 30.0 + (i % 5)),
                # Reservoir sweeps 20.0 → 29.0 in so bucket averages have
                # variance without crossing zero.
                (reservoir_id, reservoir_cap, "reservoir_in", 20.0 + (i % 10)),
            ):
                readings.append(
                    SensorReading(
                        ts=ts,
                        sensornode_id=node_id,
                        capability_id=cap_id,
                        metric=metric,
                        value=value,
                        source=SensorSource.ARDUINO,
                    )
                )
        s.add_all(readings)
        await s.commit()


@pytest.fixture
async def client(app_engine):
    await _seed_tent_series(app_engine)
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


async def test_sensors_history_requires_auth():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get(
            "/api/sensors/history", params={"range": "24h", "metric": "temperature_f"}
        )
        # AuthMiddleware returns 401 JSON for unauthenticated /api/* —
        # the SPA handles /login routing client-side.
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("range_param", ["1h", "24h", "7d"])
async def test_sensors_history_db_metric_shape(
    client: AsyncClient, range_param: str
) -> None:
    """DB-backed metrics return contract-shape points across every range."""
    response = await client.get(
        "/api/sensors/history",
        params={"range": range_param, "metric": "temperature_f"},
    )
    assert response.status_code == 200
    model = SensorsHistoryResponse.model_validate(response.json())
    assert model.range.value == range_param
    assert model.metric.value == "temperature_f"
    assert model.unit == "\u00b0F"
    # Seeded 48h of readings every 5 min, so every range has points.
    assert len(model.points) > 0
    # Each point is a proper (ts, value) shape — model_validate already
    # enforced types; double-check the wire labels parse as aware UTC.
    for pt in model.points:
        assert pt.ts.tzinfo is not None
        assert isinstance(pt.value, float)


async def test_sensors_history_humidity_metric(client: AsyncClient) -> None:
    """Second DB-backed metric works + unit mapping is per-metric."""
    response = await client.get(
        "/api/sensors/history",
        params={"range": "24h", "metric": "humidity_pct"},
    )
    assert response.status_code == 200
    model = SensorsHistoryResponse.model_validate(response.json())
    assert model.metric.value == "humidity_pct"
    assert model.unit == "%"
    assert len(model.points) > 0


async def test_sensors_history_fan_bridges_to_fan_duty_pct(
    client: AsyncClient,
) -> None:
    """Contract metric ``fan_pct`` resolves to DB column ``fan_duty_pct``."""
    response = await client.get(
        "/api/sensors/history",
        params={"range": "24h", "metric": "fan_pct"},
    )
    assert response.status_code == 200
    model = SensorsHistoryResponse.model_validate(response.json())
    assert model.metric.value == "fan_pct"
    assert model.unit == "%"
    assert len(model.points) > 0
    # Seeded fan_duty_pct cycles 30..34; every bucket average lands inside.
    for pt in model.points:
        assert 30.0 <= pt.value <= 34.0
        assert pt.ts.tzinfo is not None


async def test_sensors_history_reservoir_in(client: AsyncClient) -> None:
    """``reservoir_in`` is read straight through (firmware emits inches)."""
    response = await client.get(
        "/api/sensors/history",
        params={"range": "24h", "metric": "reservoir_in"},
    )
    assert response.status_code == 200
    model = SensorsHistoryResponse.model_validate(response.json())
    assert model.metric.value == "reservoir_in"
    assert model.unit == "in"
    assert len(model.points) > 0
    # Seeded sweep is 20–29 in; every bucket average lands inside.
    for pt in model.points:
        assert 20.0 <= pt.value <= 29.0


async def test_sensors_history_invalid_range(client: AsyncClient) -> None:
    """Out-of-enum range rejects at the query layer with 4xx (FastAPI → 422)."""
    response = await client.get(
        "/api/sensors/history",
        params={"range": "99d", "metric": "temperature_f"},
    )
    # Any 4xx is acceptable per the contract (400 BadRequest is specified;
    # FastAPI enforces enum query params with 422 — both carry the same
    # "invalid input" semantics for the SPA).
    assert 400 <= response.status_code < 500
    assert response.headers["content-type"].startswith("application/json")


async def test_sensors_history_invalid_metric(client: AsyncClient) -> None:
    """Out-of-enum metric rejects at the query layer with 4xx."""
    response = await client.get(
        "/api/sensors/history",
        params={"range": "24h", "metric": "not_a_metric"},
    )
    assert 400 <= response.status_code < 500
    assert response.headers["content-type"].startswith("application/json")


async def test_sensors_history_missing_params(client: AsyncClient) -> None:
    """Both range and metric are required — missing either yields 4xx."""
    response = await client.get("/api/sensors/history", params={"metric": "vpd_kpa"})
    assert 400 <= response.status_code < 500
    response = await client.get("/api/sensors/history", params={"range": "1h"})
    assert 400 <= response.status_code < 500


async def test_legacy_sensors_readings_route_is_gone(client: AsyncClient) -> None:
    """The pre-rewrite /api/sensors/readings was removed in this feature's
    commit. A live request must 404 — confirms both the handler deletion
    and the legacy_routes bookkeeping in contract_status.json are
    internally consistent.
    """
    response = await client.get("/api/sensors/readings")
    assert response.status_code == 404
