from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.camera import CameraSource, SnapshotArtifact, SnapshotWriter
from dirt_shared.cloud_assets import AssetUploader, AssetUploadRequest
from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetSignUploadRequest,
    CapturePolicyReason,
    CapturePolicyResponse,
)
from dirt_shared.models.device import Device
from dirt_shared.models.grow_run import GrowRun
from dirt_shared.models.schedule import Schedule
from dirt_shared.models.site import Site
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.models.tent import Tent
from dirt_shared.observability import log_event
from dirt_shared.services.grow_state import derive_lights_from_times
from dirt_shared.services.scope import resolve_scope


class Sleeper(Protocol):
    async def sleep(self, delay_s: float) -> None: ...


class AsyncioSleeper:
    async def sleep(self, delay_s: float) -> None:
        await asyncio.sleep(delay_s)


@dataclass(frozen=True)
class CameraCaptureMetadata:
    site_id: str
    tent_id: str
    camera_device_id: str
    camera_view_id: str | None = None
    camera_kind: str = "snapshot"
    gateway_id: str | None = None
    event_stream: str = "camera_capture"


@dataclass(frozen=True)
class CameraCaptureResult:
    artifact: SnapshotArtifact
    sink_results: tuple[object, ...] = ()


@dataclass(frozen=True)
class CaptureDecision:
    allowed: bool
    reason: str | None = None


class CapturePolicyFetchError(RuntimeError):
    """Hosted capture policy could not be fetched or parsed."""


class CaptureGate(Protocol):
    async def evaluate(self, metadata: CameraCaptureMetadata) -> CaptureDecision: ...


class CapturePolicyClient(Protocol):
    async def capture_policy(self, camera_device_id: str) -> CapturePolicyResponse: ...


class CameraCaptureSink(Protocol):
    async def handle(
        self, artifact: SnapshotArtifact, metadata: CameraCaptureMetadata
    ) -> object: ...


class CloudAssetSink:
    def __init__(self, uploader: AssetUploader) -> None:
        self._uploader = uploader

    async def handle(
        self, artifact: SnapshotArtifact, metadata: CameraCaptureMetadata
    ) -> AssetUploadRequest:
        payload = build_asset_upload_request(metadata, artifact)
        idempotency_key = build_asset_idempotency_key(metadata, payload)
        try:
            await self._uploader.upload(payload, idempotency_key=idempotency_key)
        except Exception as exc:
            _log_event(
                metadata,
                "upload_failed",
                asset_id=payload.sign_request.asset_id,
                object_key=payload.sign_request.object_key,
                error=type(exc).__name__,
            )
            raise
        _log_event(
            metadata,
            "upload_completed",
            asset_id=payload.sign_request.asset_id,
            object_key=payload.sign_request.object_key,
            size_bytes=artifact.size_bytes,
        )
        return payload


class LocalSnapshotSink:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def handle(
        self, artifact: SnapshotArtifact, metadata: CameraCaptureMetadata
    ) -> Snapshot:
        snapshot = Snapshot(
            ts=artifact.captured_at,
            file_path=str(artifact.path),
            view_id=metadata.camera_view_id or "periodic",
            kind=metadata.camera_kind,
        )
        async with AsyncSession(self._engine) as session:
            scope = await resolve_scope(
                session, site_id=metadata.site_id, tent_id=metadata.tent_id
            )
            if scope is not None:
                snapshot.site_id = scope.site_pk
                snapshot.tent_id = scope.tent_pk
                snapshot.device_id = (
                    await session.exec(
                        select(Device.id)
                        .where(Device.site_id == scope.site_pk)
                        .where(Device.device_id == metadata.camera_device_id)
                        .limit(1)
                    )
                ).first()
                snapshot.growrun_id = (
                    await session.exec(
                        select(GrowRun.id)
                        .where(GrowRun.site_id == scope.site_pk)
                        .where(GrowRun.tent_id == scope.tent_pk)
                        .where(GrowRun.is_current.is_(True))
                        .limit(1)
                    )
                ).first()
            session.add(snapshot)
            await session.commit()
            await session.refresh(snapshot)
        _log_event(
            metadata,
            "snapshot_recorded",
            snapshot_id=snapshot.id,
            file_path=snapshot.file_path,
            size_bytes=artifact.size_bytes,
        )
        return snapshot


class CameraCapturePublisher:
    def __init__(  # noqa: PLR0913
        self,
        *,
        metadata: CameraCaptureMetadata,
        source: CameraSource,
        writer: SnapshotWriter,
        sinks: tuple[CameraCaptureSink, ...],
        capture_interval_s: float,
        gate: CaptureGate | None = None,
        sleeper: Sleeper | None = None,
    ) -> None:
        self._metadata = metadata
        self._source = source
        self._writer = writer
        self._sinks = sinks
        self._capture_interval_s = capture_interval_s
        self._gate = gate
        self._sleeper = sleeper or AsyncioSleeper()

    async def run_once(self) -> CameraCaptureResult | None:
        if self._gate is not None:
            decision = await self._gate.evaluate(self._metadata)
            if not decision.allowed:
                _log_event(
                    self._metadata,
                    "capture_skipped",
                    reason=decision.reason or "not_allowed",
                )
                return None
        _log_event(self._metadata, "capture_started")
        frame = await self._source.capture()
        artifact = await self._writer.write(frame)
        sink_results = []
        for sink in self._sinks:
            sink_results.append(await sink.handle(artifact, self._metadata))
        return CameraCaptureResult(
            artifact=artifact,
            sink_results=tuple(sink_results),
        )

    async def run_forever(self) -> None:
        failures = 0
        while True:
            try:
                await self.run_once()
                failures = 0
                delay_s = self._capture_interval_s
            except Exception as exc:
                failures += 1
                delay_s = failure_backoff_s(
                    failures,
                    base_s=self._capture_interval_s,
                )
                _log_event(
                    self._metadata,
                    "cycle_failed",
                    error=type(exc).__name__,
                    retry_delay_s=delay_s,
                )
            await self._sleeper.sleep(delay_s)


def build_asset_upload_request(
    metadata: CameraCaptureMetadata,
    artifact: SnapshotArtifact,
) -> AssetUploadRequest:
    object_key = f"{metadata.site_id}/{metadata.tent_id}/snapshots/{artifact.filename}"
    sign_request = AssetSignUploadRequest(
        site_id=metadata.site_id,
        tent_id=metadata.tent_id,
        content_type=artifact.content_type,
        byte_size=artifact.size_bytes,
        object_key=object_key,
        asset_id=artifact.sha256,
        sha256=artifact.sha256,
        kind=metadata.camera_kind,
    )
    return AssetUploadRequest(
        sign_request=sign_request,
        complete_request=AssetCompleteRequest(
            **sign_request.model_dump(),
            captured_at=artifact.captured_at,
            zone_id=metadata.camera_view_id,
            device_id=metadata.camera_device_id,
        ),
        file_path=artifact.path,
    )


def build_asset_idempotency_key(
    metadata: CameraCaptureMetadata,
    payload: AssetUploadRequest,
) -> str:
    return (
        f"{metadata.site_id}:{metadata.tent_id}:{metadata.camera_device_id}:"
        f"{payload.sign_request.sha256}"
    )


def failure_backoff_s(
    attempt_count: int,
    *,
    base_s: float,
    max_s: float = 300.0,
) -> float:
    return min(max_s, base_s * (2 ** max(0, attempt_count - 1)))


def open_capture_policy(
    *,
    site_id: str,
    tent_id: str | None,
    camera_device_id: str,
    timezone: str = "America/Denver",
    reason: CapturePolicyReason | None,
) -> CapturePolicyResponse:
    return CapturePolicyResponse(
        site_id=site_id,
        tent_id=tent_id,
        camera_device_id=camera_device_id,
        enabled=True,
        require_lights_on=False,
        lights_on_local=None,
        lights_off_local=None,
        timezone=timezone,
        source_schedule_id=None,
        reason=reason,
    )


def disabled_capture_policy(
    *,
    site_id: str,
    tent_id: str | None,
    camera_device_id: str,
    timezone: str = "America/Denver",
) -> CapturePolicyResponse:
    return CapturePolicyResponse(
        site_id=site_id,
        tent_id=tent_id,
        camera_device_id=camera_device_id,
        enabled=False,
        require_lights_on=False,
        lights_on_local=None,
        lights_off_local=None,
        timezone=timezone,
        source_schedule_id=None,
        reason="camera_disabled",
    )


def evaluate_capture_policy(
    policy: CapturePolicyResponse,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CaptureDecision:
    if not policy.enabled:
        return CaptureDecision(allowed=False, reason="policy_disabled")
    if not policy.require_lights_on:
        return CaptureDecision(allowed=True)
    if policy.lights_on_local is None or policy.lights_off_local is None:
        return CaptureDecision(allowed=True)

    now = clock().astimezone(ZoneInfo(policy.timezone))
    lights = derive_lights_from_times(
        policy.lights_on_local,
        policy.lights_off_local,
        now,
    )
    if lights.on:
        return CaptureDecision(allowed=True)
    return CaptureDecision(allowed=False, reason="lights_off")


class CameraLightScheduleResolver:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def resolve(
        self,
        *,
        site_id: str,
        camera_device_id: str,
    ) -> CapturePolicyResponse:
        async with AsyncSession(self._engine) as session:
            site_timezone = (
                await session.exec(
                    select(Site.timezone).where(Site.site_id == site_id).limit(1)
                )
            ).first() or "America/Denver"
            row = (
                await session.exec(
                    select(Device, Tent.tent_id)
                    .join(Site, Site.id == Device.site_id)
                    .outerjoin(Tent, Tent.id == Device.tent_id)
                    .where(Site.site_id == site_id)
                    .where(Device.device_id == camera_device_id)
                    .where(Device.kind == "camera")
                    .order_by(Device.enabled.desc(), Device.id.desc())
                    .limit(1)
                )
            ).first()
            if row is None:
                return open_capture_policy(
                    site_id=site_id,
                    tent_id=None,
                    camera_device_id=camera_device_id,
                    timezone=site_timezone,
                    reason="camera_not_found",
                )

            camera, tent_id = row
            if not camera.enabled:
                return disabled_capture_policy(
                    site_id=site_id,
                    tent_id=tent_id,
                    camera_device_id=camera_device_id,
                    timezone=site_timezone,
                )
            if camera.tent_id is None or tent_id is None:
                return open_capture_policy(
                    site_id=site_id,
                    tent_id=tent_id,
                    camera_device_id=camera_device_id,
                    timezone=site_timezone,
                    reason="lights_schedule_not_found",
                )

            schedule = (
                await session.exec(
                    select(Schedule)
                    .where(Schedule.site_id == camera.site_id)
                    .where(Schedule.tent_id == camera.tent_id)
                    .where(Schedule.kind == "lights")
                    .where(Schedule.enabled.is_(True))
                    .where(Schedule.starts_local.is_not(None))
                    .where(Schedule.ends_local.is_not(None))
                    .order_by(Schedule.id.desc())
                    .limit(1)
                )
            ).first()
            if schedule is None:
                return open_capture_policy(
                    site_id=site_id,
                    tent_id=tent_id,
                    camera_device_id=camera_device_id,
                    timezone=site_timezone,
                    reason="lights_schedule_not_found",
                )

            return CapturePolicyResponse(
                site_id=site_id,
                tent_id=tent_id,
                camera_device_id=camera_device_id,
                enabled=True,
                require_lights_on=True,
                lights_on_local=schedule.starts_local,
                lights_off_local=schedule.ends_local,
                timezone=schedule.timezone,
                source_schedule_id=schedule.schedule_id,
                reason=None,
            )


class DatabaseCameraLightScheduleGate:
    def __init__(
        self,
        resolver: CameraLightScheduleResolver,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._resolver = resolver
        self._clock = clock

    async def evaluate(self, metadata: CameraCaptureMetadata) -> CaptureDecision:
        policy = await self._resolver.resolve(
            site_id=metadata.site_id,
            camera_device_id=metadata.camera_device_id,
        )
        if policy.reason is not None and policy.enabled:
            _log_event(metadata, "capture_policy_unresolved", reason=policy.reason)
        return evaluate_capture_policy(policy, clock=self._clock)


class HttpHostedCapturePolicyClient:
    def __init__(
        self,
        *,
        base_url: str,
        gateway_token: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._gateway_token = gateway_token
        self._client = http_client or httpx.AsyncClient(timeout=20)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def capture_policy(self, camera_device_id: str) -> CapturePolicyResponse:
        headers = {"authorization": f"Bearer {self._gateway_token}"}
        try:
            response = await self._client.get(
                f"{self._base_url}/api/gateway/v1/cameras/"
                f"{camera_device_id}/capture-policy",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CapturePolicyFetchError(str(exc)) from exc
        return CapturePolicyResponse.model_validate(data)


class HostedCapturePolicyGate:
    def __init__(
        self,
        client: CapturePolicyClient,
        *,
        camera_device_id: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = client
        self._camera_device_id = camera_device_id
        self._clock = clock
        self._cached_policy: CapturePolicyResponse | None = None

    async def evaluate(self, metadata: CameraCaptureMetadata) -> CaptureDecision:
        policy = await self._fetch_policy(metadata)
        if policy is None:
            return CaptureDecision(allowed=True)
        if policy.reason is not None and policy.enabled:
            _log_event(metadata, "capture_policy_unresolved", reason=policy.reason)
        return evaluate_capture_policy(policy, clock=self._clock)

    async def _fetch_policy(
        self, metadata: CameraCaptureMetadata
    ) -> CapturePolicyResponse | None:
        try:
            policy = await self._client.capture_policy(self._camera_device_id)
        except Exception as exc:
            _log_event(
                metadata,
                "capture_policy_fetch_failed",
                error=type(exc).__name__,
                cached_policy=self._cached_policy is not None,
            )
            return self._cached_policy
        self._cached_policy = policy
        return policy


def _log_event(
    metadata: CameraCaptureMetadata,
    event: str,
    **fields: object,
) -> None:
    base = {
        "site_id": metadata.site_id,
        "tent_id": metadata.tent_id,
        "device_id": metadata.camera_device_id,
    }
    if metadata.gateway_id is not None:
        base["gateway_id"] = metadata.gateway_id
    log_event(metadata.event_stream, event, **base, **fields)
