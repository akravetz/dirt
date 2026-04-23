"""Collate heterogenous device heartbeats into the ``/api/system/devices`` list.

Eight rows in the mockup (``dashboard.jsx:SystemTable``):

- ESP32-C3 · fan+tent         — tent sensornode's ``last_seen``
                                 (fan driver + SHT45 on one board)
- ESP32-C3 · plant_{a,b,c,d}  — per-plant sensornode's ``last_seen``
- OBSBOT Tiny 2 Lite          — dirt-camera daemon's ``get_state`` RPC
- Jabra Speak 410 (Claudia)   — tail of ``var/sessions/voice/*.jsonl``
- Humidifier (Kasa EP10)      — latest ``humidifier_on`` reading timestamp

All heterogenous — DB rows, a unix socket, a JSONL file — so we normalise
them into a single ``DeviceStatus`` dataclass with a small status taxonomy.

This is read-only; no DB writes.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import SensorLocation
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading

DeviceKind = Literal["env_sensor", "moisture_node", "camera", "voice", "actuator"]
DeviceStatus_t = Literal["ok", "warn", "offline", "listening"]


@dataclass(frozen=True)
class DeviceStatus:
    name: str
    kind: DeviceKind
    status: DeviceStatus_t
    last_seen: datetime | None
    note: str | None = None


# How old a heartbeat can be before we flip ok → warn → offline.
_THRESHOLDS = {
    "env_sensor": (timedelta(minutes=2), timedelta(minutes=5)),
    "moisture_node": (timedelta(minutes=2), timedelta(minutes=5)),
    "actuator": (timedelta(minutes=2), timedelta(minutes=10)),
    "camera": (timedelta(minutes=1), timedelta(minutes=5)),
    "voice": (timedelta(minutes=30), timedelta(hours=24)),
}


# ============================================================
# Pure helpers — no engine, used by methods below.
# ============================================================


def _status_from_age(
    now: datetime,
    last_seen: datetime | None,
    kind: DeviceKind,
) -> DeviceStatus_t:
    """Map (last_seen, kind) to an ok/warn/offline status."""
    if last_seen is None:
        return "offline"
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    age = now - last_seen
    ok_th, warn_th = _THRESHOLDS[kind]
    if age <= ok_th:
        return "ok"
    if age <= warn_th:
        return "warn"
    return "offline"


def _camera_socket_path() -> str:
    explicit = os.environ.get("DIRT_CAMERA_SOCKET")
    if explicit:
        return explicit
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        return f"{xdg}/dirt-camera.sock"
    return "/tmp/dirt-camera.sock"


def _camera_rpc(sock_path: str, line: str, timeout: float = 1.0) -> dict[str, str]:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(sock_path)
        sock.sendall((line + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
    finally:
        with contextlib.suppress(Exception):
            sock.close()
    return _parse_camera_response(buf.decode().strip())


def _parse_camera_response(line: str) -> dict[str, str]:
    if not line:
        return {"_status": "empty"}
    toks = line.split()
    result: dict[str, object] = {"_status": toks[0]}
    for kv in toks[1:]:
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        if v == "true":
            result[k] = True
        elif v == "false":
            result[k] = False
        else:
            try:
                result[k] = float(v) if "." in v else int(v)
            except ValueError:
                result[k] = v
    return result


def _is_user_service_active(unit: str) -> bool:
    """Shell out to ``systemctl --user is-active <unit>``."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == "active"


class SystemStatusService:
    """Heterogenous device heartbeat collator. Constructor-inject the engine.

    Wired into ``app.state.system_status`` by ``create_app``.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    def now(self) -> datetime:
        """Injected-clock read. Endpoints stamp response envelopes via this."""
        return self._clock()

    async def get_device_statuses(self) -> list[DeviceStatus]:
        """Return the full device list in the mockup's render order."""
        now = self._clock()
        out: list[DeviceStatus] = []

        async with AsyncSession(self._engine) as session:
            out.append(await self._tent_sensor_status(session, now))
            for loc in (
                SensorLocation.PLANT_A,
                SensorLocation.PLANT_B,
                SensorLocation.PLANT_C,
                SensorLocation.PLANT_D,
            ):
                out.append(await self._plant_node_status(session, loc, now))
            out.append(await self._humidifier_status(session, now))

        out.append(self._camera_status(now))
        out.append(self._voice_status(now))
        return out

    async def _tent_sensor_status(
        self, session: AsyncSession, now: datetime
    ) -> DeviceStatus:
        node = (
            await session.exec(
                select(SensorNode).where(SensorNode.location == SensorLocation.TENT)
            )
        ).first()
        last_seen = node.last_seen if node is not None else None
        return DeviceStatus(
            name="ESP32-C3 · fan+tent",
            kind="env_sensor",
            status=_status_from_age(now, last_seen, "env_sensor"),
            last_seen=last_seen,
        )

    async def _plant_node_status(
        self, session: AsyncSession, loc: SensorLocation, now: datetime
    ) -> DeviceStatus:
        node = (
            await session.exec(select(SensorNode).where(SensorNode.location == loc))
        ).first()
        last_seen = node.last_seen if node is not None else None
        letter = loc.value.removeprefix("plant-")
        return DeviceStatus(
            name=f"ESP32-C3 · plant_{letter}",
            kind="moisture_node",
            status=_status_from_age(now, last_seen, "moisture_node"),
            last_seen=last_seen,
        )

    async def _humidifier_status(
        self, session: AsyncSession, now: datetime
    ) -> DeviceStatus:
        tent = (
            await session.exec(
                select(SensorNode.id).where(SensorNode.location == SensorLocation.TENT)
            )
        ).first()
        last_seen: datetime | None = None
        if tent is not None:
            last = (
                await session.exec(
                    select(SensorReading)
                    .where(SensorReading.sensornode_id == tent)
                    .where(SensorReading.metric == "humidifier_on")
                    .order_by(SensorReading.ts.desc())
                    .limit(1)
                )
            ).first()
            if last is not None:
                last_seen = last.ts
        status = _status_from_age(now, last_seen, "actuator")
        return DeviceStatus(
            name="Humidifier (Kasa EP10)",
            kind="actuator",
            status=status,
            last_seen=last_seen,
        )

    def _camera_status(self, now: datetime) -> DeviceStatus:
        """Probe the dirt-camera daemon's unix socket via ``get_state``."""
        sock_path = _camera_socket_path()
        try:
            resp = _camera_rpc(sock_path, "get_state")
        except (FileNotFoundError, ConnectionRefusedError, TimeoutError, OSError):
            return DeviceStatus(
                name="OBSBOT Tiny 2 Lite",
                kind="camera",
                status="offline",
                last_seen=None,
                note="daemon unreachable",
            )
        if resp.get("_status") != "ok":
            return DeviceStatus(
                name="OBSBOT Tiny 2 Lite",
                kind="camera",
                status="offline",
                last_seen=None,
                note=resp.get("msg") or str(resp.get("_status")),
            )
        connected = resp.get("camera_connected", False)
        return DeviceStatus(
            name="OBSBOT Tiny 2 Lite",
            kind="camera",
            status="ok" if connected else "warn",
            last_seen=now,
            note=None if connected else "camera reported disconnected",
        )

    def _voice_status(self, now: datetime) -> DeviceStatus:
        """Jabra / Claudia — infer from ``systemctl --user is-active dirt-voice``."""
        active = _is_user_service_active("dirt-voice")
        if active:
            return DeviceStatus(
                name="Jabra Speak 410 (Claudia)",
                kind="voice",
                status="listening",
                last_seen=now,
            )
        return DeviceStatus(
            name="Jabra Speak 410 (Claudia)",
            kind="voice",
            status="offline",
            last_seen=None,
        )
