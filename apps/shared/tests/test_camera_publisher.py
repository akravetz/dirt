from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time

from dirt_shared.camera import CapturedFrame, SnapshotSpool
from dirt_shared.cloud_contract import CapturePolicyResponse
from dirt_shared.services.camera_publisher import (
    CameraCaptureMetadata,
    CameraCapturePublisher,
    CaptureDecision,
    HostedCapturePolicyGate,
    evaluate_capture_policy,
)

JPEG_BYTES = b"\xff\xd8publisher-jpeg\xff\xd9"
FIXED_NOW = datetime(2026, 5, 12, 12, 30, 45, tzinfo=UTC)


@dataclass
class FakeCameraSource:
    captures: int = 0

    async def capture(self) -> CapturedFrame:
        self.captures += 1
        return CapturedFrame(jpeg_bytes=JPEG_BYTES, captured_at=FIXED_NOW)


class DenyGate:
    async def evaluate(self, metadata: CameraCaptureMetadata) -> CaptureDecision:
        del metadata
        return CaptureDecision(allowed=False, reason="lights_off")


class RecordingSink:
    def __init__(self) -> None:
        self.calls = 0

    async def handle(self, artifact: object, metadata: CameraCaptureMetadata) -> str:
        del artifact, metadata
        self.calls += 1
        return "ok"


class FakePolicyClient:
    def __init__(self, policies: list[CapturePolicyResponse]) -> None:
        self.policies = policies
        self.calls = 0
        self.fail = False

    async def capture_policy(self, camera_device_id: str) -> CapturePolicyResponse:
        assert camera_device_id == "obsbot-breeding"
        self.calls += 1
        if self.fail:
            raise RuntimeError("policy unavailable")
        return self.policies[-1]


async def test_publisher_skips_before_capture_write_and_sink(tmp_path) -> None:
    source = FakeCameraSource()
    sink = RecordingSink()
    publisher = CameraCapturePublisher(
        metadata=CameraCaptureMetadata(
            site_id="homebox",
            tent_id="breeding",
            camera_device_id="obsbot-breeding",
        ),
        source=source,
        writer=SnapshotSpool(tmp_path / "snapshots"),
        sinks=(sink,),
        capture_interval_s=300,
        gate=DenyGate(),
    )

    result = await publisher.run_once()

    assert result is None
    assert source.captures == 0
    assert sink.calls == 0
    assert not (tmp_path / "snapshots").exists()


async def test_capture_policy_evaluation_uses_local_window() -> None:
    policy = CapturePolicyResponse(
        site_id="homebox",
        tent_id="breeding",
        camera_device_id="obsbot-breeding",
        enabled=True,
        require_lights_on=True,
        lights_on_local=time(6, 0),
        lights_off_local=time(18, 0),
        timezone="America/Denver",
        source_schedule_id="breeding-lights-photoperiod",
        reason=None,
    )

    assert (
        evaluate_capture_policy(
            policy, clock=lambda: datetime(2026, 5, 12, 18, 0, tzinfo=UTC)
        ).allowed
        is True
    )

    decision = evaluate_capture_policy(
        policy, clock=lambda: datetime(2026, 5, 12, 4, 0, tzinfo=UTC)
    )
    assert decision.allowed is False
    assert decision.reason == "lights_off"


async def test_hosted_capture_policy_gate_uses_cached_policy_on_fetch_failure() -> None:
    policy = CapturePolicyResponse(
        site_id="homebox",
        tent_id="breeding",
        camera_device_id="obsbot-breeding",
        enabled=True,
        require_lights_on=True,
        lights_on_local=time(6, 0),
        lights_off_local=time(18, 0),
        timezone="America/Denver",
        source_schedule_id="breeding-lights-photoperiod",
        reason=None,
    )
    client = FakePolicyClient([policy])
    gate = HostedCapturePolicyGate(
        client,
        camera_device_id="obsbot-breeding",
        clock=lambda: datetime(2026, 5, 12, 18, 0, tzinfo=UTC),
    )
    metadata = CameraCaptureMetadata(
        site_id="homebox",
        tent_id="breeding",
        camera_device_id="obsbot-breeding",
    )

    assert (await gate.evaluate(metadata)).allowed is True

    client.fail = True

    assert (await gate.evaluate(metadata)).allowed is True
    assert client.calls == 2
