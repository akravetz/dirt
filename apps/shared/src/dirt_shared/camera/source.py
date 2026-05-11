from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

DaemonRPC = Callable[[str], Awaitable[dict[str, str]]]
DEFAULT_DAEMON_SOCKET_PATH = Path("/tmp/dirt-camera.sock")  # noqa: S108
logger = logging.getLogger(__name__)


class CameraCaptureError(RuntimeError):
    """Raised when a camera source cannot return a captured frame."""


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    jpeg_bytes: bytes
    captured_at: datetime
    content_type: str = "image/jpeg"
    source_frame_age_ms: int | None = None
    width: int | None = None
    height: int | None = None
    driver_diagnostics: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class CameraSource(Protocol):
    async def capture(self) -> CapturedFrame:
        """Capture one frame from the source."""


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_response(line: str) -> dict[str, str]:
    """Parse `STATUS k=v k=v ...` into {'_status': STATUS, k: v, ...}."""
    toks = line.split()
    if not toks:
        return {"_status": "empty"}
    out: dict[str, str] = {"_status": toks[0]}
    for kv in toks[1:]:
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k] = v
    return out


async def _daemon_rpc(
    line: str,
    timeout: float = 5.0,
    *,
    socket_path: Path | str = DEFAULT_DAEMON_SOCKET_PATH,
) -> dict[str, str]:
    """Send one line to the daemon, return the parsed response."""
    path = str(socket_path)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(path), timeout=timeout
        )
    except (FileNotFoundError, ConnectionRefusedError) as exc:
        logger.error("camera daemon not reachable at %s: %s", path, exc)
        return {"_status": "error", "msg": "daemon_unreachable"}
    except TimeoutError:
        logger.error("camera daemon connect timeout at %s", path)
        return {"_status": "error", "msg": "connect_timeout"}

    try:
        writer.write((line + "\n").encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
    except TimeoutError:
        logger.error("camera daemon response timeout for: %s", line)
        writer.close()
        return {"_status": "error", "msg": "response_timeout"}
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()

    return _parse_response(raw.decode().strip())


def daemon_rpc_for_socket(
    socket_path: Path | str = DEFAULT_DAEMON_SOCKET_PATH,
) -> DaemonRPC:
    async def rpc(line: str) -> dict[str, str]:
        return await _daemon_rpc(line, socket_path=socket_path)

    return rpc


class ObsbotDaemonCameraSource:
    """Camera source backed by the existing dirt-camera daemon Unix socket."""

    def __init__(
        self,
        *,
        rpc: DaemonRPC | None = None,
        socket_path: Path | str = DEFAULT_DAEMON_SOCKET_PATH,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._rpc = rpc or daemon_rpc_for_socket(socket_path)
        self._clock = clock

    async def capture(self) -> CapturedFrame:
        response = await self._rpc("capture")
        if response.get("_status") != "ok":
            raise CameraCaptureError(f"camera capture failed: {response}")

        path = response.get("path")
        if not path:
            raise CameraCaptureError(
                f"camera capture response missing path: {response}"
            )

        try:
            jpeg_bytes = await asyncio.to_thread(Path(path).read_bytes)
        except OSError as exc:
            raise CameraCaptureError(
                f"failed to read camera capture tempfile {path}: {exc}"
            ) from exc

        diagnostics = {
            key: value
            for key, value in response.items()
            if key not in {"_status", "path", "width", "height", "age_ms"}
        }
        return CapturedFrame(
            jpeg_bytes=jpeg_bytes,
            captured_at=self._clock(),
            source_frame_age_ms=_parse_optional_int(response.get("age_ms")),
            width=_parse_optional_int(response.get("width")),
            height=_parse_optional_int(response.get("height")),
            driver_diagnostics=diagnostics,
        )
