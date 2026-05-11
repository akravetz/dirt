"""Reusable camera capture and snapshot spool primitives."""

from dirt_shared.camera.source import (
    CameraCaptureError,
    CameraSource,
    CapturedFrame,
    ObsbotDaemonCameraSource,
    daemon_rpc_for_socket,
)
from dirt_shared.camera.spool import SnapshotArtifact, SnapshotSpool, SnapshotWriter

__all__ = [
    "CameraCaptureError",
    "CameraSource",
    "CapturedFrame",
    "ObsbotDaemonCameraSource",
    "SnapshotArtifact",
    "SnapshotSpool",
    "SnapshotWriter",
    "daemon_rpc_for_socket",
]
