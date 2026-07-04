from __future__ import annotations

import asyncio
import math
import secrets
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Path, status
from fastapi.responses import JSONResponse

from dirt_hwd.tools.substrate_calibration.calibration import (
    compute_capture_stats,
    summarize_session,
)
from dirt_hwd.tools.substrate_calibration.controller import (
    SubstrateControllerClient,
    probe_map_from_status,
    samples_for_probe,
)
from dirt_hwd.tools.substrate_calibration.schemas import (
    AcceptCaptureRequest,
    CalibrationSession,
    CapturePreview,
    CapturePreviewRequest,
    ControllerModeResponse,
    CreateSessionRequest,
    LatestCompletedResponse,
    LiveStatusResponse,
    ProbeIdentity,
    ProbeSample,
    SessionStatus,
    SessionSummaryResponse,
    StartCalibrationRequest,
    ToolInfoResponse,
    UpdateWetReferenceRequest,
)
from dirt_hwd.tools.substrate_calibration.store import (
    CalibrationStore,
    CaptureNotFoundError,
    CaptureProbeMismatchError,
    SessionCompletedError,
    SessionNotFoundError,
)
from dirt_shared.config import Settings

SessionId = Annotated[str, Path(min_length=1)]
CaptureId = Annotated[str, Path(min_length=1)]


def create_app(
    *,
    controller_url: str,
    settings: Settings | None = None,
    store: CalibrationStore | None = None,
    controller: SubstrateControllerClient | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    settings = settings or Settings()
    store = store or CalibrationStore(settings=settings, clock=clock)
    controller = controller or SubstrateControllerClient(controller_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            await controller.aclose()

    app = FastAPI(title="Dirt Substrate Calibration", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.controller = controller
    app.state.clock = clock

    @app.exception_handler(SessionNotFoundError)
    async def _session_not_found(_request, exc: SessionNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(CaptureNotFoundError)
    async def _capture_not_found(_request, exc: CaptureNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(CaptureProbeMismatchError)
    async def _capture_probe_mismatch(_request, exc: CaptureProbeMismatchError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(SessionCompletedError)
    async def _session_completed(_request, exc: SessionCompletedError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(httpx.HTTPError)
    async def _controller_http_error(_request, exc: httpx.HTTPError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"controller request failed: {exc}"},
        )

    @app.get("/", response_model=ToolInfoResponse)
    def info() -> ToolInfoResponse:
        return ToolInfoResponse(
            ok=True,
            controller_url=controller.base_url,
            storage_root=str(store.root),
        )

    @app.get("/api/controller/status", response_model=LiveStatusResponse)
    async def controller_status() -> LiveStatusResponse:
        return LiveStatusResponse(
            controller_url=controller.base_url,
            status=await controller.status(),
        )

    @app.post(
        "/api/controller/calibration/start",
        response_model=ControllerModeResponse,
    )
    async def start_controller_calibration(
        request: StartCalibrationRequest,
    ) -> ControllerModeResponse:
        response = await controller.start_calibration(
            duration_s=request.duration_s,
            interval_ms=request.interval_ms,
        )
        return ControllerModeResponse(
            controller_url=controller.base_url,
            state=response.state,
            calibration_mode=response.calibration_mode,
        )

    @app.post(
        "/api/controller/calibration/stop",
        response_model=ControllerModeResponse,
    )
    async def stop_controller_calibration() -> ControllerModeResponse:
        response = await controller.stop_calibration()
        return ControllerModeResponse(
            controller_url=controller.base_url,
            state=response.state,
            calibration_mode=response.calibration_mode,
        )

    @app.post("/api/sessions", response_model=CalibrationSession)
    async def create_session_route(
        request: CreateSessionRequest,
    ) -> CalibrationSession:
        live_status = await controller.status()
        return store.create_session(
            controller_url=controller.base_url,
            probe_map=probe_map_from_status(live_status),
            input_ec_ms_cm=request.input_ec_ms_cm,
            input_ph=request.input_ph,
        )

    @app.get(
        "/api/sessions/latest-completed",
        response_model=LatestCompletedResponse,
    )
    def latest_completed() -> LatestCompletedResponse:
        artifact = store.read_latest_completed_artifact()
        session = (
            store.read_latest_completed_session() if artifact is not None else None
        )
        return LatestCompletedResponse(artifact=artifact, session=session)

    @app.get("/api/sessions/{session_id}", response_model=CalibrationSession)
    def read_session(session_id: SessionId) -> CalibrationSession:
        return store.read_session(session_id)

    @app.patch(
        "/api/sessions/{session_id}/wet-reference", response_model=CalibrationSession
    )
    def update_wet_reference(
        session_id: SessionId,
        request: UpdateWetReferenceRequest,
    ) -> CalibrationSession:
        return store.update_wet_reference(
            session_id,
            input_ec_ms_cm=request.input_ec_ms_cm,
            input_ph=request.input_ph,
        )

    @app.post(
        "/api/sessions/{session_id}/captures/preview",
        response_model=CapturePreview,
    )
    async def preview_capture(
        session_id: SessionId,
        request: CapturePreviewRequest,
    ) -> CapturePreview:
        session = store.read_session(session_id)
        if session.status == SessionStatus.COMPLETED:
            raise SessionCompletedError(
                f"session {session.id} is completed and immutable"
            )
        probe = _probe_for_session(session.probe_map, request.probe_id)
        return await _capture_preview(controller, probe, request, clock=clock)

    @app.post(
        "/api/sessions/{session_id}/captures/accept",
        response_model=CalibrationSession,
    )
    def accept_capture(
        session_id: SessionId,
        request: AcceptCaptureRequest,
    ) -> CalibrationSession:
        return store.append_capture(session_id, request.capture)

    @app.delete(
        "/api/sessions/{session_id}/captures/{capture_id}",
        response_model=CalibrationSession,
    )
    def remove_capture(
        session_id: SessionId,
        capture_id: CaptureId,
    ) -> CalibrationSession:
        return store.remove_capture(session_id, capture_id)

    @app.post("/api/sessions/{session_id}/complete", response_model=CalibrationSession)
    def complete_session(session_id: SessionId) -> CalibrationSession:
        return store.complete_session(session_id)

    @app.get(
        "/api/sessions/{session_id}/summary",
        response_model=SessionSummaryResponse,
    )
    def session_summary(session_id: SessionId) -> SessionSummaryResponse:
        session = store.read_session(session_id)
        summary = session.summary or summarize_session(session)
        return SessionSummaryResponse(
            session_id=session.id,
            status=session.status,
            summary=summary,
        )

    return app


def _probe_for_session(
    probe_map: list[ProbeIdentity],
    probe_id: int,
) -> ProbeIdentity:
    for probe in probe_map:
        if probe.probe_id == probe_id:
            return probe
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"probe {probe_id} is not present in this session",
    )


def _capture_id(now: datetime) -> str:
    return f"capture-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


async def _capture_preview(
    controller: SubstrateControllerClient,
    probe: ProbeIdentity,
    request: CapturePreviewRequest,
    *,
    clock: Callable[[], datetime],
) -> CapturePreview:
    started_at = clock()
    deadline = time.monotonic() + request.duration_s
    samples: dict[tuple[int, int], ProbeSample] = {}
    capture_start_controller_ms: int | None = None
    window_s = min(120, max(1, math.ceil(request.duration_s) + 5))

    while True:
        response = await controller.samples(window_s=window_s)
        if capture_start_controller_ms is None:
            capture_start_controller_ms = response.controller.read_ms
        for sample in samples_for_probe(response, probe_id=probe.probe_id):
            if sample.read_ms < capture_start_controller_ms:
                continue
            samples.setdefault((sample.seq, sample.read_ms), sample)

        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            break
        await asyncio.sleep(min(request.poll_interval_s, remaining_s))

    ordered_samples = sorted(
        samples.values(), key=lambda item: (item.read_ms, item.seq)
    )
    ended_at = clock()
    return CapturePreview(
        id=_capture_id(started_at),
        anchor_type=request.anchor_type,
        probe_id=probe.probe_id,
        modbus_address=probe.modbus_address,
        device_id=probe.device_id,
        placement_label=request.placement_label,
        note=request.note,
        duration_s=request.duration_s,
        started_at=started_at,
        ended_at=ended_at,
        input_ec_ms_cm_override=request.input_ec_ms_cm_override,
        input_ph_override=request.input_ph_override,
        samples=ordered_samples,
        stats=compute_capture_stats(ordered_samples),
    )
