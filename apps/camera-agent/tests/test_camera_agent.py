from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from dirt_camera_agent.config import CameraAgentSettings
from dirt_camera_agent.main import build_capture_gate
from dirt_camera_agent.service import (
    CameraAgentService,
    build_asset_idempotency_key,
    build_asset_upload_request,
    build_camera_source,
    failure_backoff_s,
)
from dirt_shared.camera import CapturedFrame, SnapshotSpool
from dirt_shared.cloud_assets import AssetUploader
from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetCompleteResponse,
    AssetFailureRequest,
    AssetFailureResponse,
    AssetSignUploadRequest,
    CapturePolicyResponse,
    SignUploadResponse,
)

JPEG_BYTES = b"\xff\xd8camera-agent-jpeg\xff\xd9"
FIXED_NOW = datetime(2026, 5, 11, 12, 30, 45, tzinfo=UTC)


@dataclass
class FakeCameraSource:
    frame: CapturedFrame

    async def capture(self) -> CapturedFrame:
        return self.frame


class RecordingAssetClient:
    def __init__(self) -> None:
        self.upload_fail = False
        self.sign_requests: list[AssetSignUploadRequest] = []
        self.complete_requests: list[AssetCompleteRequest] = []
        self.failure_requests: list[AssetFailureRequest] = []
        self.calls: list[tuple[str, str]] = []
        self.uploads: list[dict[str, Any]] = []
        self.call_counts: defaultdict[str, int] = defaultdict(int)

    async def sign_upload(
        self, payload: AssetSignUploadRequest, *, idempotency_key: str
    ) -> SignUploadResponse:
        self._record("sign", idempotency_key)
        self.sign_requests.append(payload)
        return SignUploadResponse(
            asset_id=payload.asset_id,
            object_key=payload.object_key,
            upload_url="https://assets.test/upload",
            method="PUT",
            headers={"Content-Type": payload.content_type},
            expires_at=FIXED_NOW + timedelta(minutes=10),
            byte_size=payload.byte_size,
        )

    async def upload_asset(
        self,
        *,
        file_path: Path,
        upload_url: str,
        headers: dict[str, str],
        content_type: str,
    ) -> None:
        self._record("upload", "")
        if self.upload_fail:
            raise RuntimeError("asset byte upload failed")
        self.uploads.append(
            {
                "file_path": file_path,
                "upload_url": upload_url,
                "headers": headers,
                "content_type": content_type,
            }
        )

    async def complete_asset(
        self, payload: AssetCompleteRequest, *, idempotency_key: str
    ) -> AssetCompleteResponse:
        self._record("complete", idempotency_key)
        self.complete_requests.append(payload)
        return AssetCompleteResponse(
            asset_id=payload.asset_id or payload.object_key,
            object_key=payload.object_key,
            uploaded_at=FIXED_NOW,
        )

    async def report_asset_failure(
        self, payload: AssetFailureRequest, *, idempotency_key: str
    ) -> AssetFailureResponse:
        self._record("failure", idempotency_key)
        self.failure_requests.append(payload)
        return AssetFailureResponse(ok=True, received_at=FIXED_NOW)

    def _record(self, call: str, idempotency_key: str) -> None:
        self.calls.append((call, idempotency_key))
        self.call_counts[call] += 1


class FakePolicyClient:
    async def capture_policy(self, camera_device_id: str) -> CapturePolicyResponse:
        return CapturePolicyResponse(
            site_id="homebox",
            tent_id="breeding",
            camera_device_id=camera_device_id,
            enabled=True,
            require_lights_on=False,
            lights_on_local=None,
            lights_off_local=None,
            timezone="America/Denver",
            source_schedule_id=None,
            reason="lights_schedule_not_found",
        )


def _settings(tmp_path: Path, **overrides: Any) -> CameraAgentSettings:
    values = {
        "site_id": "homebox",
        "tent_id": "breeding",
        "camera_device_id": "obsbot-breeding",
        "camera_view_id": "canopy",
        "camera_kind": "periodic",
        "capture_interval_s": 60.0,
        "data_dir": tmp_path / "var",
        "cloud_api_base_url": "https://api.test",
        "cloud_gateway_id": "gateway-dirt2-camera",
        "cloud_gateway_token": "test-token",
    }
    values.update(overrides)
    return CameraAgentSettings.model_validate(values)


def test_config_defaults_spool_under_data_dir_and_uses_scoped_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIRT_SITE_ID", "homebox")
    monkeypatch.setenv("DIRT_TENT_ID", "breeding")
    monkeypatch.setenv("DIRT_CAMERA_DEVICE_ID", "obsbot-breeding")
    monkeypatch.setenv("DIRT_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("DIRT_CAMERA_CAPTURE_INTERVAL_S", "42.5")
    monkeypatch.setenv("DIRT_CLOUD_API_BASE_URL", "https://api.test")
    monkeypatch.setenv("DIRT_CLOUD_GATEWAY_ID", "gateway-dirt2-camera")
    monkeypatch.setenv("DIRT_CLOUD_GATEWAY_TOKEN", "token")

    settings = CameraAgentSettings()

    assert settings.source == "obsbot-daemon"
    assert settings.site_id == "homebox"
    assert settings.tent_id == "breeding"
    assert settings.camera_device_id == "obsbot-breeding"
    assert settings.capture_interval_s == 42.5
    assert settings.spool_dir == tmp_path / "var/camera-agent/breeding/snapshots"
    assert settings.cloud_gateway_id == "gateway-dirt2-camera"


def test_capture_gate_uses_hosted_policy_client(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    assert build_capture_gate(settings, policy_client=FakePolicyClient()) is not None


def test_unsupported_source_fails_clearly(tmp_path: Path) -> None:
    settings = _settings(tmp_path, source="rtsp")

    with pytest.raises(ValueError, match="unsupported camera agent source 'rtsp'"):
        build_camera_source(settings)


async def test_single_capture_spools_and_uploads_breeding_payload(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, spool_dir=tmp_path / "spool")
    client = RecordingAssetClient()
    service = CameraAgentService(
        settings=settings,
        source=FakeCameraSource(CapturedFrame(JPEG_BYTES, FIXED_NOW)),
        spool=SnapshotSpool(settings.spool_dir),
        uploader=AssetUploader(client),
    )

    result = await service.run_once()

    digest = hashlib.sha256(JPEG_BYTES).hexdigest()
    expected_object_key = "homebox/breeding/snapshots/snapshot_20260511_123045.jpg"
    assert result.artifact.path.read_bytes() == JPEG_BYTES
    assert result.payload.file_path == result.artifact.path
    assert result.idempotency_key == f"homebox:breeding:obsbot-breeding:{digest}"
    assert client.calls == [
        ("sign", f"{result.idempotency_key}:sign"),
        ("upload", ""),
        ("complete", f"{result.idempotency_key}:complete"),
    ]
    assert client.sign_requests == [
        AssetSignUploadRequest(
            site_id="homebox",
            tent_id="breeding",
            content_type="image/jpeg",
            byte_size=len(JPEG_BYTES),
            object_key=expected_object_key,
            asset_id=digest,
            sha256=digest,
            kind="periodic",
        )
    ]
    assert client.complete_requests == [
        AssetCompleteRequest(
            **client.sign_requests[0].model_dump(),
            captured_at=FIXED_NOW,
            zone_id="canopy",
            device_id="obsbot-breeding",
        )
    ]


def test_payload_builder_uses_homebox_breeding_scope(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    artifact = SnapshotSpool(tmp_path).write_sync(CapturedFrame(JPEG_BYTES, FIXED_NOW))

    payload = build_asset_upload_request(settings, artifact)
    idempotency_key = build_asset_idempotency_key(settings, payload)

    digest = hashlib.sha256(JPEG_BYTES).hexdigest()
    assert payload.sign_request.site_id == "homebox"
    assert payload.sign_request.tent_id == "breeding"
    assert payload.sign_request.object_key.endswith(
        "/breeding/snapshots/snapshot_20260511_123045.jpg"
    )
    assert payload.sign_request.asset_id == digest
    assert payload.complete_request.device_id == "obsbot-breeding"
    assert idempotency_key == f"homebox:breeding:obsbot-breeding:{digest}"


async def test_upload_failure_is_reported_and_leaves_spool_file(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, spool_dir=tmp_path / "spool")
    client = RecordingAssetClient()
    client.upload_fail = True
    service = CameraAgentService(
        settings=settings,
        source=FakeCameraSource(CapturedFrame(JPEG_BYTES, FIXED_NOW)),
        spool=SnapshotSpool(settings.spool_dir),
        uploader=AssetUploader(client),
    )

    with pytest.raises(RuntimeError, match="asset byte upload failed"):
        await service.run_once()

    digest = hashlib.sha256(JPEG_BYTES).hexdigest()
    spool_file = tmp_path / "spool" / "snapshot_20260511_123045.jpg"
    assert spool_file.read_bytes() == JPEG_BYTES
    assert client.call_counts["complete"] == 0
    assert client.failure_requests == [
        AssetFailureRequest(
            site_id="homebox",
            tent_id="breeding",
            asset_id=digest,
            object_key="homebox/breeding/snapshots/snapshot_20260511_123045.jpg",
            stage="upload_or_complete",
            error="asset byte upload failed",
        )
    ]


def test_failure_backoff_caps_exponential_delay() -> None:
    assert failure_backoff_s(1, base_s=10.0) == 10.0
    assert failure_backoff_s(2, base_s=10.0) == 20.0
    assert failure_backoff_s(10, base_s=10.0, max_s=60.0) == 60.0
