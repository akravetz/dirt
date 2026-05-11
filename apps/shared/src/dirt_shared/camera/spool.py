from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dirt_shared.camera.source import CapturedFrame


@dataclass(frozen=True, slots=True)
class SnapshotArtifact:
    path: Path
    filename: str
    sha256: str
    size_bytes: int
    content_type: str
    captured_at: datetime


class SnapshotWriter:
    """Atomically writes captured JPEG frames to a local snapshot directory."""

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)

    async def write(self, frame: CapturedFrame) -> SnapshotArtifact:
        return await asyncio.to_thread(self.write_sync, frame)

    def write_sync(self, frame: CapturedFrame) -> SnapshotArtifact:
        self._directory.mkdir(parents=True, exist_ok=True)
        filename = f"snapshot_{frame.captured_at.strftime('%Y%m%d_%H%M%S')}.jpg"
        path = self._directory / filename
        tmp_path = self._directory / f".{filename}.{uuid4().hex}.tmp"

        try:
            tmp_path.write_bytes(frame.jpeg_bytes)
            os.replace(tmp_path, path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        return SnapshotArtifact(
            path=path,
            filename=filename,
            sha256=hashlib.sha256(frame.jpeg_bytes).hexdigest(),
            size_bytes=len(frame.jpeg_bytes),
            content_type=frame.content_type,
            captured_at=frame.captured_at,
        )


class SnapshotSpool(SnapshotWriter):
    """Alias for callers that model the directory as a local spool."""
