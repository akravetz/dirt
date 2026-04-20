import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.app import create_app
from dirt_shared.config import Settings
from dirt_shared.models.enums import SensorLocation
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import compute_calibrated_pct


@pytest.fixture
async def client(app_engine):
    """Per-test app with all background loops disabled (background_services=[])."""
    app = create_app(engine=app_engine, background_services=[])
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac


def _auth_header() -> dict[str, str]:
    settings = Settings()
    return {"Authorization": f"Bearer {settings.sensor_ingest_token}"}


async def _plant_a_node_id(engine) -> int:
    async with AsyncSession(engine) as s:
        result = await s.exec(
            select(SensorNode.id).where(SensorNode.location == SensorLocation.PLANT_A)
        )
        return result.first()


async def test_ingest_without_token_is_401(client: AsyncClient):
    r = await client.post(
        "/api/ingest/sensors",
        json={"location": "plant-a", "metrics": {"soil_moisture_pct": 42.0}},
    )
    assert r.status_code == 401


async def test_ingest_with_wrong_token_is_401(client: AsyncClient):
    r = await client.post(
        "/api/ingest/sensors",
        json={"location": "plant-a", "metrics": {"soil_moisture_pct": 42.0}},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


async def test_ingest_writes_readings_and_node(client: AsyncClient, app_engine):
    r = await client.post(
        "/api/ingest/sensors",
        json={
            "location": "plant-a",
            "metrics": {"soil_moisture_pct": 42.0, "soil_moisture_raw": 1600},
            "firmware_version": "0.1.0",
            "ip": "192.168.1.103",
            "uptime_ms": 60000,
        },
        headers=_auth_header(),
    )
    assert r.status_code == 202
    body = r.json()
    assert body == {"ok": True, "location": "plant-a", "count": 2}

    node_id = await _plant_a_node_id(app_engine)
    async with AsyncSession(app_engine) as s:
        readings = (
            await s.exec(
                select(SensorReading).where(SensorReading.sensornode_id == node_id)
            )
        ).all()
        metrics = {r.metric: r.value for r in readings}
        assert metrics == {"soil_moisture_pct": 42.0, "soil_moisture_raw": 1600.0}
        for r in readings:
            assert r.source == "esp32"

        node = (
            await s.exec(
                select(SensorNode).where(SensorNode.location == SensorLocation.PLANT_A)
            )
        ).first()
        assert node is not None
        assert str(node.ip) == "192.168.1.103"
        assert node.firmware_version == "0.1.0"
        assert node.uptime_ms == 60000
        assert node.last_seen is not None


async def test_ingest_upserts_node_on_second_post(client: AsyncClient, app_engine):
    payload = {
        "location": "plant-a",
        "metrics": {"soil_moisture_pct": 10.0},
        "firmware_version": "0.1.0",
        "uptime_ms": 1000,
    }
    r1 = await client.post("/api/ingest/sensors", json=payload, headers=_auth_header())
    assert r1.status_code == 202

    payload["metrics"]["soil_moisture_pct"] = 11.0
    payload["uptime_ms"] = 2000
    r2 = await client.post("/api/ingest/sensors", json=payload, headers=_auth_header())
    assert r2.status_code == 202

    async with AsyncSession(app_engine) as s:
        plant_a = (
            await s.exec(
                select(SensorNode).where(SensorNode.location == SensorLocation.PLANT_A)
            )
        ).all()
        assert len(plant_a) == 1
        assert plant_a[0].uptime_ms == 2000


async def _post_raw(client: AsyncClient, value: float, location: str = "plant-a"):
    return await client.post(
        "/api/ingest/sensors",
        json={"location": location, "metrics": {"soil_moisture_raw": value}},
        headers=_auth_header(),
    )


async def _get_cal(engine, location: SensorLocation, metric: str) -> SensorCalibration | None:
    async with AsyncSession(engine) as s:
        result = await s.exec(
            select(SensorNode.id).where(SensorNode.location == location)
        )
        node_id = result.first()
        if node_id is None:
            return None
        return (
            await s.exec(
                select(SensorCalibration)
                .where(SensorCalibration.sensornode_id == node_id)
                .where(SensorCalibration.metric == metric)
            )
        ).first()


async def test_first_raw_reading_creates_calibration_row(
    client: AsyncClient, app_engine
):
    assert (await _post_raw(client, 2700)).status_code == 202
    cal = await _get_cal(app_engine, SensorLocation.PLANT_A, "soil_moisture_raw")
    assert cal is not None
    assert cal.raw_low == 2700
    assert cal.raw_high == 2700


async def test_calibration_widens_range_on_new_extrema(client: AsyncClient, app_engine):
    for v in [2750, 2700, 620, 1500, 640, 3000]:
        assert (await _post_raw(client, v)).status_code == 202

    cal = await _get_cal(app_engine, SensorLocation.PLANT_A, "soil_moisture_raw")
    assert cal is not None
    assert cal.raw_low == 620
    assert cal.raw_high == 3000


async def test_calibration_ignores_out_of_clamp_values(client: AsyncClient, app_engine):
    for v in [2500, 800]:
        assert (await _post_raw(client, v)).status_code == 202

    # Noise spikes — should be ignored
    assert (await _post_raw(client, 50)).status_code == 202  # impossibly wet
    assert (await _post_raw(client, 4000)).status_code == 202  # impossibly dry

    cal = await _get_cal(app_engine, SensorLocation.PLANT_A, "soil_moisture_raw")
    assert cal is not None
    assert cal.raw_low == 800
    assert cal.raw_high == 2500


async def test_calibration_not_triggered_for_other_metrics(
    client: AsyncClient, app_engine
):
    # humidity_pct is not in AUTO_CALIBRATED_METRICS
    r = await client.post(
        "/api/ingest/sensors",
        json={"location": "plant-a", "metrics": {"humidity_pct": 55.0}},
        headers=_auth_header(),
    )
    assert r.status_code == 202
    cal = await _get_cal(app_engine, SensorLocation.PLANT_A, "humidity_pct")
    assert cal is None


def test_compute_calibrated_pct_linear_math():
    assert compute_calibrated_pct(2750, raw_low=620, raw_high=2750) == 0.0
    assert compute_calibrated_pct(620, raw_low=620, raw_high=2750) == 100.0
    pct = compute_calibrated_pct(1685, raw_low=620, raw_high=2750)
    assert pct is not None and abs(pct - 50.0) < 0.01


def test_compute_calibrated_pct_clamps_out_of_range():
    assert compute_calibrated_pct(500, raw_low=620, raw_high=2750) == 100.0
    assert compute_calibrated_pct(3000, raw_low=620, raw_high=2750) == 0.0


def test_compute_calibrated_pct_degenerate_returns_none():
    assert compute_calibrated_pct(1500, raw_low=1500, raw_high=1500) is None
