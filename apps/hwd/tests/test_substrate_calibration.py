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
    ProbeIdentity,
    ProbeSample,
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
