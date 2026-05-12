from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from dirt_camera_agent.config import CameraAgentSettings
from dirt_shared.camera import (
    CameraSource,
    ObsbotDaemonCameraSource,
    SnapshotArtifact,
    SnapshotSpool,
)
from dirt_shared.cloud_assets import AssetUploader, AssetUploadRequest
from dirt_shared.services.camera_publisher import (
    AsyncioSleeper,
    CameraCaptureMetadata,
    CameraCapturePublisher,
    CaptureGate,
    CloudAssetSink,
    Sleeper,
)
from dirt_shared.services.camera_publisher import (
    build_asset_idempotency_key as _build_asset_idempotency_key,
)
from dirt_shared.services.camera_publisher import (
    build_asset_upload_request as _build_asset_upload_request,
)
from dirt_shared.services.camera_publisher import (
    failure_backoff_s as _failure_backoff_s,
)


class AsyncCloser(Protocol):
    async def aclose(self) -> None: ...


@dataclass(frozen=True)
class CameraAgentCaptureResult:
    artifact: SnapshotArtifact
    payload: AssetUploadRequest
    idempotency_key: str


class CameraAgentService:
    def __init__(  # noqa: PLR0913
        self,
        *,
        settings: CameraAgentSettings,
        source: CameraSource,
        spool: SnapshotSpool,
        uploader: AssetUploader,
        capture_gate: CaptureGate | None = None,
        sleeper: Sleeper | None = None,
        closer: AsyncCloser | None = None,
    ) -> None:
        self._settings = settings
        self._closer = closer
        metadata = metadata_from_settings(settings)
        self._publisher = CameraCapturePublisher(
            metadata=metadata,
            source=source,
            writer=spool,
            sinks=(CloudAssetSink(uploader),),
            capture_interval_s=settings.capture_interval_s,
            gate=capture_gate,
            sleeper=sleeper or AsyncioSleeper(),
        )

    async def aclose(self) -> None:
        if self._closer is not None:
            await self._closer.aclose()

    async def run_once(self) -> CameraAgentCaptureResult | None:
        result = await self._publisher.run_once()
        if result is None:
            return None
        payload = result.sink_results[0]
        if not isinstance(payload, AssetUploadRequest):
            raise TypeError(f"unexpected camera-agent sink result: {type(payload)!r}")
        idempotency_key = build_asset_idempotency_key(self._settings, payload)
        return CameraAgentCaptureResult(
            artifact=result.artifact,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    async def run_forever(self) -> None:
        await self._publisher.run_forever()


def build_camera_source(settings: CameraAgentSettings) -> CameraSource:
    settings.validate_source()
    return ObsbotDaemonCameraSource(socket_path=Path(settings.camera_socket_path))


def metadata_from_settings(settings: CameraAgentSettings) -> CameraCaptureMetadata:
    return CameraCaptureMetadata(
        site_id=settings.site_id,
        tent_id=settings.tent_id,
        camera_device_id=settings.camera_device_id,
        camera_view_id=settings.camera_view_id,
        camera_kind=settings.camera_kind,
        gateway_id=settings.cloud_gateway_id,
        event_stream="camera_agent",
    )


def build_asset_upload_request(
    settings: CameraAgentSettings,
    artifact: SnapshotArtifact,
) -> AssetUploadRequest:
    return _build_asset_upload_request(metadata_from_settings(settings), artifact)


def build_asset_idempotency_key(
    settings: CameraAgentSettings,
    payload: AssetUploadRequest,
) -> str:
    return _build_asset_idempotency_key(metadata_from_settings(settings), payload)


def failure_backoff_s(
    attempt_count: int,
    *,
    base_s: float,
    max_s: float = 300.0,
) -> float:
    return _failure_backoff_s(attempt_count, base_s=base_s, max_s=max_s)
