import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.app import create_app
from dirt_hwd.services.sensor_quality import SensorQualityConfig, SensorQualityService
from dirt_shared.config import Settings
from dirt_shared.models.device import Capability, Device
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.models.zone import Zone
from dirt_shared.sensor_contract import capability_metadata_from_json
from dirt_shared.services.readings import ReadingsService, compute_calibrated_pct
from dirt_shared.testing import create_test_capability, create_test_device


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


def _current_payload(
    *,
    device_id: str,
    metrics: dict[str, float],
    **extra: Any,
) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "metrics": metrics,
        **extra,
    }


SUBSTRATE_METRICS = {
    "soil_moisture_pct": 26.9,
    "substrate_temp_c": 21.4,
    "substrate_ec_us_cm": 147.0,
    "substrate_ph": 4.7,
}


async def test_ingest_without_token_is_401(client: AsyncClient):
    r = await client.post(
        "/api/ingest/sensors",
        json={"device_id": "plant-a-node", "metrics": {"soil_moisture_pct": 42.0}},
    )
    assert r.status_code == 401


async def test_ingest_with_wrong_token_is_401(client: AsyncClient):
    r = await client.post(
        "/api/ingest/sensors",
        json={"device_id": "plant-a-node", "metrics": {"soil_moisture_pct": 42.0}},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


async def test_ingest_writes_readings_and_node(client: AsyncClient, app_engine):
    r = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id="plant-a-substrate-node",
            metrics=SUBSTRATE_METRICS,
            firmware_version="0.1.0",
            ip="192.168.1.103",
            uptime_ms=60000,
            wifi_rssi_dbm=-71,
            wifi_reconnect_count=3,
            wifi_driver_reset_count=1,
            wifi_disconnect_reason=200,
            wifi_disconnected_for_ms=0,
        ),
        headers=_auth_header(),
    )
    assert r.status_code == 202
    body = r.json()
    assert body == {"ok": True, "device_id": "plant-a-substrate-node", "count": 4}

    async with AsyncSession(app_engine) as s:
        readings = (
            await s.exec(
                select(SensorReading, Device, Capability)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .join(Device, Device.id == Capability.device_id)
                .where(Device.device_id == "plant-a-substrate-node")
            )
        ).all()
        metrics = {r.metric: r.value for r, _, _ in readings}
        assert metrics == SUBSTRATE_METRICS
        for r, _, _ in readings:
            assert r.source == "esp32"

        device = (
            await s.exec(
                select(Device).where(Device.device_id == "plant-a-substrate-node")
            )
        ).one()
        assert str(device.ip) == "192.168.1.103"
        assert device.firmware_version == "0.1.0"
        assert device.uptime_ms == 60000
        assert device.wifi_rssi_dbm == -71
        assert device.wifi_reconnect_count == 3
        assert device.wifi_driver_reset_count == 1
        assert device.wifi_disconnect_reason == 200
        assert device.wifi_disconnected_for_ms == 0
        assert device.last_seen is not None


async def test_substrate_node_seed_declares_four_metadata_marked_capabilities(
    app_engine,
):
    async with AsyncSession(app_engine) as s:
        row = (
            await s.exec(
                select(Device).where(Device.device_id == "plant-a-substrate-node")
            )
        ).one()
        capabilities = (
            await s.exec(
                select(Capability)
                .where(Capability.device_id == row.id)
                .order_by(Capability.capability_id)
            )
        ).all()

    assert row.metadata_json["sensor_model"] == "DFRobot SEN0604"
    assert row.metadata_json["modbus_address"] == "0x02"
    assert row.metadata_json["ph_ec_status"] == "calibrated"

    by_id = {capability.capability_id: capability for capability in capabilities}
    assert set(by_id) == {
        "soil_moisture_pct",
        "substrate_ec_us_cm",
        "substrate_ph",
        "substrate_temp_c",
    }

    metadata = {
        capability_id: capability_metadata_from_json(capability.metadata_json)
        for capability_id, capability in by_id.items()
    }
    assert all(item.expected_wire_metric for item in metadata.values())
    assert all(item.freshness_required for item in metadata.values())
    assert all(item.sensor_model == "DFRobot SEN0604" for item in metadata.values())
    assert all(item.modbus_address == "0x02" for item in metadata.values())
    assert metadata["soil_moisture_pct"].experimental is False
    assert metadata["substrate_temp_c"].experimental is False
    assert metadata["substrate_ec_us_cm"].experimental is False
    assert metadata["substrate_ph"].experimental is False
    assert metadata["substrate_ec_us_cm"].experimental_note is None
    assert metadata["substrate_ph"].experimental_note is None


@pytest.mark.parametrize(
    ("device_id", "zone_id", "modbus_address"),
    [
        ("plant-d-substrate-node", "plant-d", "0x03"),
        ("plant-c-substrate-node", "plant-c", "0x04"),
    ],
)
async def test_logical_substrate_node_seed_declares_capabilities_for_c_and_d(
    app_engine,
    device_id: str,
    zone_id: str,
    modbus_address: str,
):
    async with AsyncSession(app_engine) as s:
        row = (
            await s.exec(
                select(Device, Zone.name)
                .join(Zone, Zone.id == Device.zone_id)
                .where(Device.device_id == device_id)
            )
        ).one()
        device, seeded_zone_id = row
        capabilities = (
            await s.exec(
                select(Capability)
                .where(Capability.device_id == device.id)
                .order_by(Capability.capability_id)
            )
        ).all()

    assert seeded_zone_id.lower().replace(" ", "-") == zone_id
    assert device.hostname == "plant-a-substrate-node.local"
    assert device.metadata_json["sensor_model"] == "DFRobot SEN0604"
    assert device.metadata_json["bus_controller_device_id"] == "plant-a-substrate-node"
    assert device.metadata_json["bus"] == "rs485"
    assert device.metadata_json["modbus_address"] == modbus_address
    assert device.metadata_json["ph_ec_status"] == "calibrated"

    by_id = {capability.capability_id: capability for capability in capabilities}
    assert set(by_id) == set(SUBSTRATE_METRICS)

    metadata = {
        capability_id: capability_metadata_from_json(capability.metadata_json)
        for capability_id, capability in by_id.items()
    }
    assert all(item.expected_wire_metric for item in metadata.values())
    assert all(item.freshness_required for item in metadata.values())
    assert all(item.sensor_model == "DFRobot SEN0604" for item in metadata.values())
    assert all(item.modbus_address == modbus_address for item in metadata.values())
    assert (
        by_id["substrate_ec_us_cm"].metadata_json["calibration_status"] == "calibrated"
    )
    assert by_id["substrate_ph"].metadata_json["calibration_status"] == "calibrated"
    assert "experimental" not in by_id["substrate_ec_us_cm"].metadata_json
    assert "experimental" not in by_id["substrate_ph"].metadata_json


@pytest.mark.parametrize(
    ("device_id", "zone_id"),
    [
        ("plant-d-substrate-node", "plant-d"),
        ("plant-c-substrate-node", "plant-c"),
    ],
)
async def test_logical_substrate_node_ingest_writes_four_capability_rows(
    client: AsyncClient,
    app_engine,
    device_id: str,
    zone_id: str,
):
    r = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id=device_id,
            metrics=SUBSTRATE_METRICS,
            firmware_version="rs485-0.1.0",
            ip="192.168.1.212",
            uptime_ms=30000,
        ),
        headers=_auth_header(),
    )

    assert r.status_code == 202
    assert r.json() == {
        "ok": True,
        "device_id": device_id,
        "count": 4,
    }

    async with AsyncSession(app_engine) as s:
        rows = (
            await s.exec(
                select(SensorReading, Device, Capability)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .join(Device, Device.id == Capability.device_id)
                .where(Device.device_id == device_id)
                .order_by(Capability.capability_id)
            )
        ).all()
        device = (
            await s.exec(select(Device).where(Device.device_id == device_id))
        ).one()

    assert {
        capability.capability_id: (reading.metric, reading.value)
        for reading, _, capability in rows
    } == {
        "soil_moisture_pct": ("soil_moisture_pct", 26.9),
        "substrate_ec_us_cm": ("substrate_ec_us_cm", 147.0),
        "substrate_ph": ("substrate_ph", 4.7),
        "substrate_temp_c": ("substrate_temp_c", 21.4),
    }
    assert str(device.ip) == "192.168.1.212"
    assert device.firmware_version == "rs485-0.1.0"
    assert device.uptime_ms == 30000
    assert device.last_seen is not None


async def test_freshness_snapshot_uses_required_metadata_and_device_heartbeat(
    client: AsyncClient, app_engine
):
    readings = ReadingsService(app_engine)
    stale_cutoff = datetime.now(UTC) - timedelta(minutes=5)

    before_heartbeat = await readings.get_capability_freshness_snapshot(stale_cutoff)
    assert not any(
        key.startswith(("plant-c-substrate-node:", "plant-d-substrate-node:"))
        for key in before_heartbeat
    )

    d_response = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id="plant-d-substrate-node",
            metrics={"soil_moisture_pct": 26.9},
        ),
        headers=_auth_header(),
    )
    assert d_response.status_code == 202

    c_response = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id="plant-c-substrate-node",
            metrics={"substrate_ph": 5.9},
        ),
        headers=_auth_header(),
    )
    assert c_response.status_code == 202

    snapshot = await readings.get_capability_freshness_snapshot(stale_cutoff)

    assert "fan-controller:humidity_pct" not in snapshot
    d_statuses = {
        key.removeprefix("plant-d-substrate-node:"): value[0]
        for key, value in snapshot.items()
        if key.startswith("plant-d-substrate-node:")
    }
    c_statuses = {
        key.removeprefix("plant-c-substrate-node:"): value[0]
        for key, value in snapshot.items()
        if key.startswith("plant-c-substrate-node:")
    }
    assert d_statuses == {
        "soil_moisture_pct": "fresh",
        "substrate_ec_us_cm": "stale",
        "substrate_ph": "stale",
        "substrate_temp_c": "stale",
    }
    assert c_statuses == {
        "soil_moisture_pct": "stale",
        "substrate_ec_us_cm": "stale",
        "substrate_ph": "fresh",
        "substrate_temp_c": "stale",
    }


async def test_ingest_stores_device_diagnostics(client: AsyncClient, app_engine):
    r = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id="fan-controller",
            metrics={
                "temperature_c": 20.6,
                "humidity_pct": 49.0,
                "fan_pct": 30.0,
            },
            diagnostics={
                "boot_count": 12,
                "reset_reason": 3,
                "loop_gap_max_ms": 1118,
                "http_get_fan_count": 44,
                "http_post_fan_count": 7,
                "ingest_ok_count": 120,
                "ingest_fail_count": 2,
                "last_ingest_code": 202,
                "max_ingest_ms": 391,
                "free_heap_bytes": 178320,
            },
        ),
        headers=_auth_header(),
    )

    assert r.status_code == 202

    async with AsyncSession(app_engine) as s:
        device = (
            await s.exec(select(Device).where(Device.device_id == "fan-controller"))
        ).one()

    assert device.metadata_json["diagnostics"] == {
        "boot_count": 12,
        "reset_reason": 3,
        "loop_gap_max_ms": 1118,
        "http_get_fan_count": 44,
        "http_post_fan_count": 7,
        "ingest_ok_count": 120,
        "ingest_fail_count": 2,
        "last_ingest_code": 202,
        "max_ingest_ms": 391,
        "free_heap_bytes": 178320,
    }


async def test_ingest_stores_substrate_node_modbus_diagnostics(
    client: AsyncClient, app_engine
):
    r = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id="plant-a-substrate-node",
            metrics={
                "soil_moisture_pct": 26.9,
                "substrate_temp_c": 21.4,
                "substrate_ec_us_cm": 147.0,
                "substrate_ph": 4.7,
            },
            diagnostics={
                "boot_count": 2,
                "reset_reason": 1,
                "modbus_success_count": 30,
                "modbus_failure_count": 3,
                "modbus_crc_mismatch_count": 1,
                "modbus_short_response_count": 1,
                "modbus_no_response_count": 1,
                "last_modbus_response_len": 13,
                "last_ingest_code": 202,
                "ingest_ok_count": 29,
                "ingest_fail_count": 1,
                "free_heap_bytes": 176000,
                "min_free_heap_bytes": 168000,
                "loop_gap_max_ms": 704,
            },
        ),
        headers=_auth_header(),
    )

    assert r.status_code == 202

    async with AsyncSession(app_engine) as s:
        device = (
            await s.exec(
                select(Device).where(Device.device_id == "plant-a-substrate-node")
            )
        ).one()

    assert device.metadata_json["diagnostics"] == {
        "boot_count": 2,
        "reset_reason": 1,
        "modbus_success_count": 30,
        "modbus_failure_count": 3,
        "modbus_crc_mismatch_count": 1,
        "modbus_short_response_count": 1,
        "modbus_no_response_count": 1,
        "last_modbus_response_len": 13,
        "last_ingest_code": 202,
        "ingest_ok_count": 29,
        "ingest_fail_count": 1,
        "free_heap_bytes": 176000,
        "min_free_heap_bytes": 168000,
        "loop_gap_max_ms": 704,
    }


async def test_device_id_writes_capability(client: AsyncClient, app_engine):
    r = await client.post(
        "/api/ingest/sensors",
        json={
            "device_id": "plant-a-substrate-node",
            "metrics": {"soil_moisture_pct": 26.9},
        },
        headers=_auth_header(),
    )

    assert r.status_code == 202
    assert r.json() == {
        "ok": True,
        "device_id": "plant-a-substrate-node",
        "count": 1,
    }

    async with AsyncSession(app_engine) as s:
        row = (
            await s.exec(
                select(SensorReading, Device, Capability)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .join(Device, Device.id == Capability.device_id)
                .where(SensorReading.metric == "soil_moisture_pct")
            )
        ).one()

    reading, device, capability = row
    assert reading.capability_id is not None
    assert device.device_id == "plant-a-substrate-node"
    assert device.last_seen is not None
    assert capability.capability_id == "soil_moisture_pct"


async def test_firmware_scope_fields_are_rejected(
    client: AsyncClient,
    app_engine,
):
    response = await client.post(
        "/api/ingest/sensors",
        json={
            "site_id": "homebox",
            "tent_id": "main",
            "zone_id": "plant-b",
            "device_id": "plant-a-substrate-node",
            "metrics": {"soil_moisture_pct": 26.9},
        },
        headers=_auth_header(),
    )

    assert response.status_code == 422
    assert {
        tuple(error["loc"])
        for error in response.json()["detail"]
        if error["type"] == "extra_forbidden"
    } == {
        ("body", "site_id"),
        ("body", "tent_id"),
        ("body", "zone_id"),
    }

    async with AsyncSession(app_engine) as s:
        rows = (
            await s.exec(
                select(SensorReading)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .join(Device, Device.id == Capability.device_id)
                .where(Device.device_id == "plant-a-substrate-node")
                .where(SensorReading.metric == "soil_moisture_pct")
            )
        ).all()

    assert rows == []


async def test_scoped_device_id_ingest_does_not_require_location(
    client: AsyncClient, app_engine
):
    r = await client.post(
        "/api/ingest/sensors",
        json={
            "device_id": "reservoir-node",
            "metrics": {"reservoir_in": 12.0},
        },
        headers=_auth_header(),
    )

    assert r.status_code == 202
    assert r.json() == {"ok": True, "device_id": "reservoir-node", "count": 1}

    async with AsyncSession(app_engine) as s:
        row = (
            await s.exec(
                select(SensorReading, Device, Capability)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .join(Device, Device.id == Capability.device_id)
                .where(SensorReading.metric == "reservoir_in")
            )
        ).one()

    reading, device, capability = row
    assert reading.capability_id is not None
    assert device.device_id == "reservoir-node"
    assert device.last_seen is not None
    assert capability.capability_id == "reservoir_in"


async def test_unknown_device_id_logs_unresolved_capability(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.WARNING, logger="dirt_shared.services.readings")
    r = await client.post(
        "/api/ingest/sensors",
        json={
            "device_id": "unknown-node",
            "metrics": {"soil_moisture_raw": 1600},
        },
        headers=_auth_header(),
    )

    assert r.status_code == 202
    assert any(
        getattr(record, "device_id", None) == "unknown-node"
        for record in caplog.records
    )


async def test_ingest_requires_location_or_device_id(client: AsyncClient):
    r = await client.post(
        "/api/ingest/sensors",
        json={"metrics": {"soil_moisture_raw": 1600}},
        headers=_auth_header(),
    )

    assert r.status_code == 422
    assert "device_id" in r.text


async def test_location_only_known_board_is_rejected(client: AsyncClient):
    r = await client.post(
        "/api/ingest/sensors",
        json={"location": "plant-a", "metrics": {"soil_moisture_raw": 1600}},
        headers=_auth_header(),
    )

    assert r.status_code == 422
    assert "device_id" in r.text


async def test_known_device_unresolved_metric_logs_warning(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.WARNING, logger="dirt_shared.services.readings")

    r = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id="fan-controller",
            metrics={"pressure_hpa": 843.0},
        ),
        headers=_auth_header(),
    )

    assert r.status_code == 202
    warning_records = [
        record
        for record in caplog.records
        if getattr(record, "unscoped_sensorreading", False) is True
    ]
    assert len(warning_records) == 1
    assert warning_records[0].device_id == "fan-controller"
    assert warning_records[0].metrics == ["pressure_hpa"]


async def test_ingest_updates_device_on_second_post(client: AsyncClient, app_engine):
    payload = _current_payload(
        device_id="plant-a-substrate-node",
        metrics={"soil_moisture_pct": 10.0},
        firmware_version="0.1.0",
        uptime_ms=1000,
    )
    r1 = await client.post("/api/ingest/sensors", json=payload, headers=_auth_header())
    assert r1.status_code == 202

    payload["metrics"]["soil_moisture_pct"] = 11.0
    payload["uptime_ms"] = 2000
    r2 = await client.post("/api/ingest/sensors", json=payload, headers=_auth_header())
    assert r2.status_code == 202

    async with AsyncSession(app_engine) as s:
        device = (
            await s.exec(
                select(Device).where(Device.device_id == "plant-a-substrate-node")
            )
        ).one()
        assert device.uptime_ms == 2000


async def _create_enabled_raw_node(app_engine, device_id: str = "test-raw-node"):
    async with AsyncSession(app_engine) as session:
        device = await create_test_device(
            session,
            tent_id="main",
            zone_id="plant-a",
            device_id=device_id,
            name="Test raw moisture node",
            kind="moisture_node",
            controller="test",
        )
        await create_test_capability(
            session,
            device=device,
            capability_id="soil_moisture_raw",
            name="Soil Moisture Raw",
            unit="raw",
            source="test",
        )
        await session.commit()


async def _post_raw(
    client: AsyncClient,
    value: float,
    *,
    device_id: str = "test-raw-node",
):
    return await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id=device_id,
            metrics={"soil_moisture_raw": value},
        ),
        headers=_auth_header(),
    )


async def _get_cal(engine, device_id: str, metric: str) -> SensorCalibration | None:
    async with AsyncSession(engine) as s:
        capability_id = (
            await s.exec(
                select(Capability.id)
                .join(Device, Device.id == Capability.device_id)
                .where(Device.device_id == device_id)
                .where(Capability.metric_name == metric)
            )
        ).first()
        if capability_id is None:
            return None
        return (
            await s.exec(
                select(SensorCalibration)
                .where(SensorCalibration.capability_id == capability_id)
                .where(SensorCalibration.metric == metric)
            )
        ).first()


async def test_first_raw_reading_creates_calibration_row(
    client: AsyncClient, app_engine
):
    await _create_enabled_raw_node(app_engine)
    assert (await _post_raw(client, 2700)).status_code == 202
    cal = await _get_cal(app_engine, "test-raw-node", "soil_moisture_raw")
    assert cal is not None
    assert cal.raw_low == 2700
    assert cal.raw_high == 2700


async def test_calibration_widens_range_on_new_extrema(client: AsyncClient, app_engine):
    await _create_enabled_raw_node(app_engine)
    for v in [2750, 2700, 620, 1500, 640, 3000]:
        assert (await _post_raw(client, v)).status_code == 202

    cal = await _get_cal(app_engine, "test-raw-node", "soil_moisture_raw")
    assert cal is not None
    assert cal.raw_low == 620
    assert cal.raw_high == 3000


async def test_calibration_ignores_out_of_clamp_values(client: AsyncClient, app_engine):
    await _create_enabled_raw_node(app_engine)
    for v in [2500, 800]:
        assert (await _post_raw(client, v)).status_code == 202

    # Noise spikes — should be ignored
    assert (await _post_raw(client, 50)).status_code == 202  # impossibly wet
    assert (await _post_raw(client, 4000)).status_code == 202  # impossibly dry

    cal = await _get_cal(app_engine, "test-raw-node", "soil_moisture_raw")
    assert cal is not None
    assert cal.raw_low == 800
    assert cal.raw_high == 2500


async def test_calibration_not_triggered_for_other_metrics(
    client: AsyncClient, app_engine
):
    # humidity_pct is not in AUTO_CALIBRATED_METRICS
    r = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id="fan-controller",
            metrics={"humidity_pct": 55.0},
        ),
        headers=_auth_header(),
    )
    assert r.status_code == 202
    cal = await _get_cal(app_engine, "fan-controller", "humidity_pct")
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


async def test_tent_ingest_derives_temperature_f_vpd_dew_point(
    client: AsyncClient, app_engine
):
    """Fan-controller posts with temperature_c + humidity_pct have
    temperature_f, vpd_kpa, and dew_point_f derived at ingest."""
    r = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id="fan-controller",
            metrics={
                "temperature_c": 20.6,
                "humidity_pct": 49.0,
                "fan_pct": 30.0,
            },
        ),
        headers=_auth_header(),
    )
    assert r.status_code == 202
    assert r.json()["count"] == 6  # 3 input + 3 derived

    async with AsyncSession(app_engine) as s:
        rows = (
            await s.exec(
                select(SensorReading.metric, SensorReading.value)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .join(Device, Device.id == Capability.device_id)
                .where(Device.device_id == "fan-controller")
                .order_by(SensorReading.id.desc())
                .limit(6)
            )
        ).all()
    by_metric = {m: v for m, v in rows}
    assert abs(by_metric["temperature_c"] - 20.6) < 1e-6
    assert abs(by_metric["humidity_pct"] - 49.0) < 1e-6
    assert abs(by_metric["fan_pct"] - 30.0) < 1e-6
    assert abs(by_metric["temperature_f"] - 69.08) < 0.01
    # 20.6°C / 49 %RH → VPD ≈ 1.24 kPa
    assert 1.2 < by_metric["vpd_kpa"] < 1.3
    assert 45.0 < by_metric["dew_point_f"] < 52.0


async def test_plant_node_ingest_passthrough_without_temp_rh(
    client: AsyncClient, app_engine
):
    """Single moisture metrics lack the temperature_c + humidity_pct pair."""
    r = await client.post(
        "/api/ingest/sensors",
        json=_current_payload(
            device_id="plant-a-substrate-node",
            metrics={"soil_moisture_pct": 26.9},
        ),
        headers=_auth_header(),
    )
    assert r.status_code == 202
    assert r.json()["count"] == 1


async def test_reservoir_fault_payload_is_rejected_but_device_touched(
    app_engine, tmp_path: Path
):
    app = create_app(engine=app_engine, background_services=[])
    app.state.sensor_quality = SensorQualityService(
        SensorQualityConfig(
            state_path=tmp_path / "sensor_quality_state.json",
            telegram_bot_token="",
            telegram_chat_id="",
        )
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.post(
            "/api/ingest/sensors",
            json=_current_payload(
                device_id="reservoir-node",
                metrics={
                    "reservoir_pressure_raw": 8300.0,
                    "reservoir_in": -35.9,
                },
                firmware_version="0.1.0",
                ip="192.168.1.23",
                uptime_ms=12345,
                wifi_rssi_dbm=-82,
                wifi_reconnect_count=7,
                wifi_driver_reset_count=2,
                wifi_disconnect_reason=201,
                wifi_disconnected_for_ms=45000,
            ),
            headers=_auth_header(),
        )

    assert response.status_code == 202
    assert response.json() == {
        "ok": True,
        "device_id": "reservoir-node",
        "count": 0,
        "rejected": ["reservoir_in", "reservoir_pressure_raw"],
    }

    async with AsyncSession(app_engine) as session:
        rows = (
            await session.exec(
                select(SensorReading, Device)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .join(Device, Device.id == Capability.device_id)
                .where(Device.device_id == "reservoir-node")
            )
        ).all()
        device = (
            await session.exec(
                select(Device).where(Device.device_id == "reservoir-node")
            )
        ).one()

    assert rows == []
    assert str(device.ip) == "192.168.1.23"
    assert device.firmware_version == "0.1.0"
    assert device.uptime_ms == 12345
    assert device.wifi_rssi_dbm == -82
    assert device.wifi_reconnect_count == 7
    assert device.wifi_driver_reset_count == 2
    assert device.wifi_disconnect_reason == 201
    assert device.wifi_disconnected_for_ms == 45000
    assert device.last_seen is not None


async def test_scoped_fault_payload_is_rejected_but_device_heartbeat_updates(
    app_engine, tmp_path: Path
):
    app = create_app(engine=app_engine, background_services=[])
    app.state.sensor_quality = SensorQualityService(
        SensorQualityConfig(
            state_path=tmp_path / "sensor_quality_state.json",
            telegram_bot_token="",
            telegram_chat_id="",
        )
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.post(
            "/api/ingest/sensors",
            json={
                "device_id": "reservoir-node",
                "metrics": {
                    "reservoir_pressure_raw": 8300.0,
                    "reservoir_in": -35.9,
                },
                "firmware_version": "0.1.0",
                "ip": "192.168.1.23",
                "uptime_ms": 12345,
            },
            headers=_auth_header(),
        )

    assert response.status_code == 202
    assert response.json() == {
        "ok": True,
        "device_id": "reservoir-node",
        "count": 0,
        "rejected": ["reservoir_in", "reservoir_pressure_raw"],
    }

    async with AsyncSession(app_engine) as session:
        device = (
            await session.exec(
                select(Device).where(Device.device_id == "reservoir-node")
            )
        ).one()

    assert str(device.ip) == "192.168.1.23"
    assert device.firmware_version == "0.1.0"
    assert device.uptime_ms == 12345
    assert device.last_seen is not None
