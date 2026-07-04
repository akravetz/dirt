from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from dirt_hwd.tools.substrate_calibration.app import _capture_preview, create_app
from dirt_hwd.tools.substrate_calibration.calibration import (
    compute_capture_stats,
    summarize_session,
)
from dirt_hwd.tools.substrate_calibration.schemas import (
    FORMULA_TEMPLATE,
    AnchorType,
    CalibrationSession,
    Capture,
    CapturePreview,
    CapturePreviewRequest,
    ControllerStatus,
    ProbeIdentity,
    ProbeSample,
    SamplesResponse,
    SessionStatus,
)
from dirt_hwd.tools.substrate_calibration.store import (
    CalibrationStore,
    CaptureProbeMismatchError,
    SessionCompletedError,
)

T0 = datetime(2026, 7, 4, 15, 30, tzinfo=UTC)


def _probe(probe_id: int, address: str) -> ProbeIdentity:
    return ProbeIdentity(
        probe_id=probe_id,
        modbus_address=address,
        device_id=f"plant-{probe_id}-substrate-node",
    )


def _sample(
    seq: int,
    probe: ProbeIdentity,
    moisture: float,
    *,
    read_ms: int | None = None,
) -> ProbeSample:
    return ProbeSample(
        seq=seq,
        read_ms=read_ms or 1000 + seq,
        probe_id=probe.probe_id,
        modbus_address=probe.modbus_address,
        modbus_status="ok",
        valid=True,
        soil_moisture_pct=moisture,
        substrate_temp_c=21.0,
        substrate_ec_us_cm=125.0,
        substrate_ph=5.8,
        raw_modbus_frame_hex="02030800F500CA007E00310640",
    )


def _preview(
    capture_id: str,
    probe: ProbeIdentity,
    anchor: AnchorType,
    values: list[float],
) -> CapturePreview:
    samples = [
        _sample(index, probe, value) for index, value in enumerate(values, start=1)
    ]
    return CapturePreview(
        id=capture_id,
        anchor_type=anchor,
        probe_id=probe.probe_id,
        modbus_address=probe.modbus_address,
        device_id=probe.device_id,
        duration_s=60,
        started_at=T0,
        ended_at=T0 + timedelta(seconds=60),
        samples=samples,
        stats=compute_capture_stats(samples),
    )


def _capture(
    capture_id: str,
    probe: ProbeIdentity,
    anchor: AnchorType,
    values: list[float],
) -> Capture:
    preview = _preview(capture_id, probe, anchor, values)
    return Capture(**preview.model_dump(), accepted_at=T0 + timedelta(seconds=61))


def test_summary_computes_formula_and_missing_anchor_warnings() -> None:
    probe_1 = _probe(1, "0x02")
    probe_2 = _probe(2, "0x03")
    session = CalibrationSession(
        id="session-1",
        created_at=T0,
        updated_at=T0,
        status=SessionStatus.DRAFT,
        controller_url="http://controller.local",
        probe_map=[probe_1, probe_2],
        accepted_captures=[
            _capture("dry-1", probe_1, AnchorType.DRY, [2.0] * 10),
            _capture("wet-1", probe_1, AnchorType.WET_CAPACITY, [42.0] * 10),
            _capture("dry-2", probe_2, AnchorType.DRY, [3.0] * 10),
        ],
    )

    summary = summarize_session(session)

    assert summary.formula_template == FORMULA_TEMPLATE
    by_probe = {item.probe.probe_id: item for item in summary.probes}
    assert by_probe[1].ready is True
    assert by_probe[1].dry_anchor_mean == 2.0
    assert by_probe[1].wet_anchor_mean == 42.0
    assert by_probe[1].span == 40.0
    assert by_probe[1].formula == "100 * (raw_moisture_pct - 2.000) / 40.000"
    assert by_probe[2].ready is False
    assert "missing wet_capacity anchor" in by_probe[2].warnings


def test_store_writes_under_root_and_allows_draft_capture_removal(tmp_path) -> None:
    store = CalibrationStore(
        root=tmp_path / "substrate-calibration",
        clock=lambda: T0,
    )
    probe = _probe(1, "0x02")
    session = store.create_session(
        controller_url="http://controller.local",
        probe_map=[probe],
    )
    preview = _preview("capture-1", probe, AnchorType.DRY, [2.0] * 10)

    with_capture = store.append_capture(session.id, preview)
    without_capture = store.remove_capture(with_capture.id, preview.id)

    assert store.root == tmp_path / "substrate-calibration"
    assert (store.sessions_dir / f"{session.id}.json").exists()
    assert without_capture.accepted_captures == []


def test_accept_capture_rejects_probe_identity_mismatch(tmp_path) -> None:
    store = CalibrationStore(
        root=tmp_path / "substrate-calibration",
        clock=lambda: T0,
    )
    session_probe = _probe(1, "0x02")
    session = store.create_session(
        controller_url="http://controller.local",
        probe_map=[session_probe],
    )
    mismatched_probe = _probe(1, "0x03")
    preview = _preview(
        "capture-1",
        mismatched_probe,
        AnchorType.DRY,
        [2.0] * 10,
    )

    with pytest.raises(CaptureProbeMismatchError, match="does not match"):
        store.append_capture(session.id, preview)


def test_completed_sessions_are_immutable_and_update_latest(tmp_path) -> None:
    store = CalibrationStore(
        root=tmp_path / "substrate-calibration",
        clock=lambda: T0,
    )
    probe = _probe(1, "0x02")
    session = store.create_session(
        controller_url="http://controller.local",
        probe_map=[probe],
    )
    preview = _preview("capture-1", probe, AnchorType.DRY, [2.0] * 10)
    store.append_capture(session.id, preview)

    completed = store.complete_session(session.id)

    assert completed.status == SessionStatus.COMPLETED
    assert store.latest_completed_path.exists()
    assert store.read_latest_completed_artifact().session_id == session.id
    with pytest.raises(SessionCompletedError):
        store.append_capture(session.id, preview)
    with pytest.raises(SessionCompletedError):
        store.remove_capture(session.id, preview.id)


async def test_latest_completed_route_is_not_shadowed_by_session_id(tmp_path) -> None:
    store = CalibrationStore(
        root=tmp_path / "substrate-calibration",
        clock=lambda: T0,
    )
    app = create_app(
        controller_url="http://controller.local",
        store=store,
        clock=lambda: T0,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/sessions/latest-completed")

    assert response.status_code == 200
    assert response.json() == {"artifact": None, "session": None}


async def test_root_serves_browser_ui_and_info_route_remains_json(tmp_path) -> None:
    store = CalibrationStore(
        root=tmp_path / "substrate-calibration",
        clock=lambda: T0,
    )
    app = create_app(
        controller_url="http://controller.local",
        store=store,
        clock=lambda: T0,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        root_response = await client.get("/")
        info_response = await client.get("/api/info")

    assert root_response.status_code == 200
    assert "text/html" in root_response.headers["content-type"]
    assert "Substrate Probe Calibration" in root_response.text
    assert info_response.status_code == 200
    assert info_response.json() == {
        "ok": True,
        "controller_url": "http://controller.local",
        "storage_root": str(tmp_path / "substrate-calibration"),
    }


async def test_controller_samples_route_proxies_firmware_samples(tmp_path) -> None:
    probe = _probe(1, "0x02")
    sample = _sample(1, probe, 12.5)
    controller = _RouteFakeController(
        _firmware_samples_response(
            probe=probe,
            samples=[sample],
            window_s=60,
        )
    )
    store = CalibrationStore(
        root=tmp_path / "substrate-calibration",
        clock=lambda: T0,
    )
    app = create_app(
        controller_url="http://controller.local",
        controller=controller,
        store=store,
        clock=lambda: T0,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/controller/samples?window_s=60")

    assert response.status_code == 200
    assert controller.last_window_s == 60
    payload = response.json()
    assert payload["slots"][0]["samples"][0]["soil_moisture_pct"] == 12.5


async def test_controller_samples_route_rejects_window_above_firmware_max(
    tmp_path,
) -> None:
    probe = _probe(1, "0x02")
    controller = _RouteFakeController(
        _firmware_samples_response(
            probe=probe,
            samples=[],
            window_s=60,
        )
    )
    store = CalibrationStore(
        root=tmp_path / "substrate-calibration",
        clock=lambda: T0,
    )
    app = create_app(
        controller_url="http://controller.local",
        controller=controller,
        store=store,
        clock=lambda: T0,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/controller/samples?window_s=121")

    assert response.status_code == 422
    assert controller.last_window_s is None


def test_controller_status_accepts_pre_calibration_firmware_payload() -> None:
    status = ControllerStatus.model_validate(_old_status_payload())

    assert status.controller.normal_measurement_interval_ms == 30000
    assert status.controller.ingest_interval_ms == 30000
    assert status.calibration_mode.active is False
    assert status.calibration_mode.counters.start_count == 0
    by_address = {slot.modbus_address: slot for slot in status.slots}
    assert by_address["0x02"].probe_id == 1
    assert by_address["0x03"].probe_id == 2
    assert by_address["0x04"].probe_id == 3
    assert by_address["0x02"].sample_ring_count == 0
    assert by_address["0x02"].latest_sample.soil_moisture_pct == 24.5


async def test_capture_preview_excludes_samples_before_controller_start() -> None:
    probe = _probe(1, "0x02")
    pre_capture = _sample(1, probe, 9.0, read_ms=900)
    first_capture = _sample(2, probe, 10.0, read_ms=1000)
    later_capture = _sample(3, probe, 11.0, read_ms=1010)
    controller = _FakeController(
        [
            _samples_response(1000, probe, [pre_capture, first_capture]),
            _samples_response(
                1010,
                probe,
                [pre_capture, first_capture, later_capture],
            ),
        ]
    )

    preview = await _capture_preview(
        controller,
        probe,
        CapturePreviewRequest(
            probe_id=probe.probe_id,
            anchor_type=AnchorType.DRY,
            duration_s=0.01,
            poll_interval_s=0.001,
        ),
        clock=lambda: T0,
    )

    assert [sample.read_ms for sample in preview.samples] == [1000, 1010]


class _FakeController:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = responses
        self._index = 0

    async def samples(self, *, window_s: int):
        response = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return response


class _RouteFakeController:
    def __init__(self, response: SamplesResponse) -> None:
        self._response = response
        self.last_window_s: int | None = None
        self.base_url = "http://controller.local"

    async def samples(self, *, window_s: int) -> SamplesResponse:
        self.last_window_s = window_s
        return self._response

    async def aclose(self) -> None:
        return None


def _samples_response(
    controller_read_ms: int,
    probe: ProbeIdentity,
    samples: list[ProbeSample],
) -> SimpleNamespace:
    return SimpleNamespace(
        controller=SimpleNamespace(read_ms=controller_read_ms),
        slots=[
            SimpleNamespace(
                probe_id=probe.probe_id,
                samples=samples,
            )
        ],
    )


def _calibration_mode_payload() -> dict[str, object]:
    return {
        "active": True,
        "started_ms": 1000,
        "expires_ms": 901000,
        "remaining_ms": 900000,
        "interval_ms": 2000,
        "normal_measurement_interval_ms": 30000,
        "ingest_interval_ms": 30000,
        "counters": {
            "start_count": 1,
            "stop_count": 0,
            "auto_expire_count": 0,
            "measurement_cycle_count": 1,
            "sample_success_count": 1,
            "sample_failure_count": 0,
        },
    }


def _old_status_payload() -> dict[str, object]:
    return {
        "controller": {
            "device_id": "plant-a-substrate-node",
            "hostname": "plant-a-substrate-node",
            "slot_count": 3,
            "enabled_slot_count": 3,
            "any_enabled_slot_failing": False,
        },
        "firmware_version": "0.1.0-rs485-substrate",
        "wifi": {
            "connected": True,
            "ip": "192.168.1.40",
            "rssi_dbm": -50,
            "reconnect_count": 0,
            "driver_reset_count": 0,
            "last_disconnect_reason": 0,
            "disconnected_for_ms": 0,
        },
        "diagnostics": {},
        "provisioning": {},
        "slots": [
            _old_status_slot(
                address="0x02",
                device_id="plant-a-substrate-node",
                moisture=24.5,
            ),
            _old_status_slot(
                address="0x03",
                device_id="plant-d-substrate-node",
                moisture=25.5,
            ),
            _old_status_slot(
                address="0x04",
                device_id="plant-c-substrate-node",
                moisture=26.5,
            ),
        ],
    }


def _old_status_slot(
    *,
    address: str,
    device_id: str,
    moisture: float,
) -> dict[str, object]:
    return {
        "plant_label": device_id.removesuffix("-substrate-node"),
        "device_id": device_id,
        "modbus_address": address,
        "enabled": True,
        "assigned": True,
        "provisioning_target": False,
        "latest_sample": {
            "soil_moisture_pct": moisture,
            "substrate_temp_c": 20.2,
            "substrate_ec_us_cm": 126,
            "substrate_ph": 4.9,
            "age_ms": 1000,
        },
        "latest_raw_modbus_frame_hex": "02030800F500CA007E00310640",
        "last_modbus_status": "ok",
        "last_ingest_status": {
            "code": 200,
            "ok_count": 1,
            "fail_count": 0,
        },
        "modbus_counters": {
            "success_count": 1,
            "failure_count": 0,
            "crc_mismatch_count": 0,
            "short_response_count": 0,
            "no_response_count": 0,
            "bad_header_count": 0,
        },
    }


def _firmware_samples_response(
    *,
    probe: ProbeIdentity,
    samples: list[ProbeSample],
    window_s: int,
) -> SamplesResponse:
    return SamplesResponse.model_validate(
        {
            "controller": {
                "device_id": "plant-a-substrate-node",
                "hostname": "plant-a-substrate-node",
                "firmware_version": "0.1.0-rs485-substrate",
                "read_ms": 2000,
                "window_s": window_s,
                "calibration_mode": _calibration_mode_payload(),
            },
            "slots": [
                {
                    "probe_id": probe.probe_id,
                    "device_id": probe.device_id,
                    "modbus_address": probe.modbus_address,
                    "enabled": True,
                    "ring_capacity": 150,
                    "ring_sample_count": len(samples),
                    "returned_sample_count": len(samples),
                    "samples": [sample.model_dump(mode="json") for sample in samples],
                }
            ],
        }
    )
