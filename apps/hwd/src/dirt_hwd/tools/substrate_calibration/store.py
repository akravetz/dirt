from __future__ import annotations

import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from dirt_hwd.tools.substrate_calibration.calibration import (
    compute_capture_stats,
    summarize_session,
)
from dirt_hwd.tools.substrate_calibration.schemas import (
    CalibrationSession,
    Capture,
    CapturePreview,
    LatestCompletedArtifact,
    ProbeIdentity,
    SessionStatus,
)
from dirt_shared.config import Settings


class SessionNotFoundError(ValueError):
    pass


class SessionCompletedError(ValueError):
    pass


class CaptureNotFoundError(ValueError):
    pass


class CaptureProbeMismatchError(ValueError):
    pass


def default_storage_root(settings: Settings | None = None) -> Path:
    resolved = settings or Settings()
    return resolved.data_dir / "substrate-calibration"


class CalibrationStore:
    def __init__(
        self,
        root: Path | None = None,
        *,
        settings: Settings | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.root = root or default_storage_root(settings)
        self.sessions_dir = self.root / "sessions"
        self.latest_completed_path = self.root / "latest-completed.json"
        self._clock = clock

    def _ensure_dirs(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        if "/" in session_id or "\\" in session_id:
            raise SessionNotFoundError(f"invalid session id {session_id!r}")
        return self.sessions_dir / f"{session_id}.json"

    def _write_model(self, path: Path, model) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = model.model_dump(mode="json")
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

    def _read_json(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise SessionNotFoundError(path.stem) from exc

    def create_session(
        self,
        *,
        controller_url: str,
        probe_map: list[ProbeIdentity],
        input_ec_ms_cm: float | None = None,
        input_ph: float | None = None,
    ) -> CalibrationSession:
        self._ensure_dirs()
        created_at = self._clock()
        session = CalibrationSession(
            id=self._new_session_id(created_at),
            created_at=created_at,
            updated_at=created_at,
            status=SessionStatus.DRAFT,
            controller_url=controller_url,
            probe_map=probe_map,
            input_ec_ms_cm=input_ec_ms_cm,
            input_ph=input_ph,
            accepted_captures=[],
            summary=None,
        )
        self._write_model(self._session_path(session.id), session)
        return session

    def _new_session_id(self, created_at: datetime) -> str:
        timestamp = created_at.strftime("%Y%m%d-%H%M%S")
        return f"{timestamp}-{secrets.token_hex(3)}"

    def read_session(self, session_id: str) -> CalibrationSession:
        path = self._session_path(session_id)
        return CalibrationSession.model_validate_json(self._read_json(path))

    def save_session(self, session: CalibrationSession) -> CalibrationSession:
        self._write_model(self._session_path(session.id), session)
        return session

    def update_wet_reference(
        self,
        session_id: str,
        *,
        input_ec_ms_cm: float | None,
        input_ph: float | None,
    ) -> CalibrationSession:
        session = self.read_session(session_id)
        self._require_draft(session)
        updated = session.model_copy(
            update={
                "input_ec_ms_cm": input_ec_ms_cm,
                "input_ph": input_ph,
                "updated_at": self._clock(),
            }
        )
        return self.save_session(updated)

    def append_capture(
        self,
        session_id: str,
        preview: CapturePreview,
    ) -> CalibrationSession:
        session = self.read_session(session_id)
        self._require_draft(session)
        self._require_session_probe(session, preview)
        accepted_at = self._clock()
        capture = Capture(
            **preview.model_dump(exclude={"stats"}),
            stats=compute_capture_stats(preview.samples),
            accepted_at=accepted_at,
        )
        updated = session.model_copy(
            update={
                "accepted_captures": [*session.accepted_captures, capture],
                "updated_at": accepted_at,
            }
        )
        return self.save_session(updated)

    def remove_capture(
        self,
        session_id: str,
        capture_id: str,
    ) -> CalibrationSession:
        session = self.read_session(session_id)
        self._require_draft(session)
        captures = [
            capture for capture in session.accepted_captures if capture.id != capture_id
        ]
        if len(captures) == len(session.accepted_captures):
            raise CaptureNotFoundError(capture_id)
        updated = session.model_copy(
            update={
                "accepted_captures": captures,
                "updated_at": self._clock(),
            }
        )
        return self.save_session(updated)

    def complete_session(
        self,
        session_id: str,
    ) -> CalibrationSession:
        session = self.read_session(session_id)
        self._require_draft(session)
        completed_at = self._clock()
        summary = summarize_session(session, completed_at=completed_at)
        completed = session.model_copy(
            update={
                "status": SessionStatus.COMPLETED,
                "updated_at": completed_at,
                "summary": summary,
            }
        )
        self.save_session(completed)
        artifact = LatestCompletedArtifact(
            session_id=completed.id,
            session_path=f"sessions/{completed.id}.json",
            completed_at=completed_at,
            summary=summary,
        )
        self._write_model(self.latest_completed_path, artifact)
        return completed

    def read_latest_completed_artifact(self) -> LatestCompletedArtifact | None:
        if not self.latest_completed_path.exists():
            return None
        return LatestCompletedArtifact.model_validate_json(
            self.latest_completed_path.read_text(encoding="utf-8")
        )

    def read_latest_completed_session(self) -> CalibrationSession | None:
        artifact = self.read_latest_completed_artifact()
        if artifact is None:
            return None
        return self.read_session(artifact.session_id)

    def _require_draft(self, session: CalibrationSession) -> None:
        if session.status == SessionStatus.COMPLETED:
            raise SessionCompletedError(
                f"session {session.id} is completed and immutable"
            )

    def _require_session_probe(
        self,
        session: CalibrationSession,
        preview: CapturePreview,
    ) -> None:
        for probe in session.probe_map:
            if probe.probe_id != preview.probe_id:
                continue
            if (
                probe.modbus_address == preview.modbus_address
                and probe.device_id == preview.device_id
            ):
                return
            raise CaptureProbeMismatchError(
                f"capture {preview.id} probe {preview.probe_id} does not match "
                "session probe identity "
                f"(expected {probe.modbus_address} {probe.device_id}, "
                f"got {preview.modbus_address} {preview.device_id})"
            )
        raise CaptureProbeMismatchError(
            f"capture {preview.id} probe {preview.probe_id} is not present "
            f"in session {session.id}"
        )
