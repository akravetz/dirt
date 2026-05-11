from __future__ import annotations

import asyncio
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
from dirt_shared.cloud_contract import AssetCompleteRequest, AssetSignUploadRequest
from dirt_shared.observability import log_event


class Sleeper(Protocol):
    async def sleep(self, delay_s: float) -> None: ...


class AsyncCloser(Protocol):
    async def aclose(self) -> None: ...


class AsyncioSleeper:
    async def sleep(self, delay_s: float) -> None:
        await asyncio.sleep(delay_s)


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
        sleeper: Sleeper | None = None,
        closer: AsyncCloser | None = None,
    ) -> None:
        self._settings = settings
        self._source = source
        self._spool = spool
        self._uploader = uploader
        self._sleeper = sleeper or AsyncioSleeper()
        self._closer = closer

    async def aclose(self) -> None:
        if self._closer is not None:
            await self._closer.aclose()

    async def run_once(self) -> CameraAgentCaptureResult:
        log_event(
            "camera_agent",
            "capture_started",
            site_id=self._settings.site_id,
            tent_id=self._settings.tent_id,
            gateway_id=self._settings.cloud_gateway_id,
            device_id=self._settings.camera_device_id,
        )
        frame = await self._source.capture()
        artifact = await self._spool.write(frame)
        payload = build_asset_upload_request(self._settings, artifact)
        idempotency_key = build_asset_idempotency_key(self._settings, payload)

        try:
            await self._uploader.upload(payload, idempotency_key=idempotency_key)
        except Exception as exc:
            log_event(
                "camera_agent",
                "upload_failed",
                site_id=self._settings.site_id,
                tent_id=self._settings.tent_id,
                gateway_id=self._settings.cloud_gateway_id,
                device_id=self._settings.camera_device_id,
                asset_id=payload.sign_request.asset_id,
                object_key=payload.sign_request.object_key,
                error=type(exc).__name__,
            )
            raise

        log_event(
            "camera_agent",
            "upload_completed",
            site_id=self._settings.site_id,
            tent_id=self._settings.tent_id,
            gateway_id=self._settings.cloud_gateway_id,
            device_id=self._settings.camera_device_id,
            asset_id=payload.sign_request.asset_id,
            object_key=payload.sign_request.object_key,
            size_bytes=artifact.size_bytes,
        )
        return CameraAgentCaptureResult(
            artifact=artifact,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    async def run_forever(self) -> None:
        failures = 0
        while True:
            try:
                await self.run_once()
                failures = 0
                delay_s = self._settings.capture_interval_s
            except Exception as exc:
                failures += 1
                delay_s = failure_backoff_s(
                    failures,
                    base_s=self._settings.capture_interval_s,
                )
                log_event(
                    "camera_agent",
                    "cycle_failed",
                    site_id=self._settings.site_id,
                    tent_id=self._settings.tent_id,
                    gateway_id=self._settings.cloud_gateway_id,
                    device_id=self._settings.camera_device_id,
                    error=type(exc).__name__,
                    retry_delay_s=delay_s,
                )
            await self._sleeper.sleep(delay_s)


def build_camera_source(settings: CameraAgentSettings) -> CameraSource:
    settings.validate_source()
    return ObsbotDaemonCameraSource(socket_path=Path(settings.camera_socket_path))


def build_asset_upload_request(
    settings: CameraAgentSettings,
    artifact: SnapshotArtifact,
) -> AssetUploadRequest:
    object_key = f"{settings.site_id}/{settings.tent_id}/snapshots/{artifact.filename}"
    sign_request = AssetSignUploadRequest(
        site_id=settings.site_id,
        tent_id=settings.tent_id,
        content_type=artifact.content_type,
        byte_size=artifact.size_bytes,
        object_key=object_key,
        asset_id=artifact.sha256,
        sha256=artifact.sha256,
        kind=settings.camera_kind,
    )
    return AssetUploadRequest(
        sign_request=sign_request,
        complete_request=AssetCompleteRequest(
            **sign_request.model_dump(),
            captured_at=artifact.captured_at,
            zone_id=settings.camera_view_id,
            device_id=settings.camera_device_id,
        ),
        file_path=artifact.path,
    )


def build_asset_idempotency_key(
    settings: CameraAgentSettings,
    payload: AssetUploadRequest,
) -> str:
    return (
        f"{settings.site_id}:{settings.tent_id}:{settings.camera_device_id}:"
        f"{payload.sign_request.sha256}"
    )


def failure_backoff_s(
    attempt_count: int,
    *,
    base_s: float,
    max_s: float = 300.0,
) -> float:
    return min(max_s, base_s * (2 ** max(0, attempt_count - 1)))
