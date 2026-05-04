"""Collate scoped device heartbeats into the ``/api/system/devices`` list."""

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

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorLocation
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID

DeviceKind = Literal["env_sensor", "moisture_node", "camera", "voice", "actuator"]
DeviceStatus_t = Literal["ok", "warn", "offline", "listening"]


@dataclass(frozen=True)
class DeviceStatus:
    name: str
    kind: DeviceKind
    status: DeviceStatus_t
    last_seen: datetime | None
    note: str | None = None
    device_id: str | None = None
    site_id: str = DEFAULT_SITE_ID
    tent_id: str | None = DEFAULT_TENT_ID
    zone_id: str | None = None


# How old a heartbeat can be before we flip ok → warn → offline.
_THRESHOLDS = {
    "env_sensor": (timedelta(minutes=2), timedelta(minutes=5)),
    "moisture_node": (timedelta(minutes=2), timedelta(minutes=5)),
    "actuator": (timedelta(minutes=2), timedelta(minutes=10)),
    "camera": (timedelta(minutes=1), timedelta(minutes=5)),
    "voice": (timedelta(minutes=30), timedelta(hours=24)),
}

_STATUS_DEVICE_ORDER = (
    "fan-controller",
    "plant-a-node",
    "plant-b-node",
    "plant-c-node",
    "plant-d-node",
    "govee-h7142-main",
    "obsbot-main",
    "jabra-claudia",
)

_DEVICE_KIND_MAP: dict[str, DeviceKind] = {
    "env_sensor": "env_sensor",
    "moisture_node": "moisture_node",
    "actuator": "actuator",
    "camera": "camera",
    "voice": "voice",
}


@dataclass(frozen=True)
class _ScopedDevice:
    pk: int
    device_id: str
    name: str
    kind: DeviceKind
    site_id: str
    tent_id: str | None
    zone_id: str | None
    metadata: dict


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
        camera_rpc: Callable[[str, str], dict[str, str]] = _camera_rpc,
        service_active_check: Callable[[str], bool] = _is_user_service_active,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._camera_rpc = camera_rpc
        self._service_active_check = service_active_check

    def now(self) -> datetime:
        """Injected-clock read. Endpoints stamp response envelopes via this."""
        return self._clock()

    async def get_device_statuses(self) -> list[DeviceStatus]:
        """Return the dashboard device list in stable render order."""
        now = self._clock()

        async with AsyncSession(self._engine) as session:
            devices = await self._status_devices(session)
            nodes = (await session.exec(select(SensorNode))).all()
            nodes_by_location = {node.location: node for node in nodes}

            out: list[DeviceStatus] = []
            for device in devices:
                if device.kind in {"env_sensor", "moisture_node"}:
                    out.append(
                        self._sensor_device_status(now, device, nodes_by_location)
                    )
                elif device.device_id == "govee-h7142-main":
                    out.append(await self._actuator_status(session, now, device))
                elif device.kind == "camera":
                    out.append(self._camera_status(now, device))
                elif device.kind == "voice":
                    out.append(self._voice_status(now, device))
        return out

    async def _status_devices(self, session: AsyncSession) -> list[_ScopedDevice]:
        rows = (
            await session.exec(
                select(Device, Site.site_id, Tent.tent_id, Zone.zone_id)
                .join(Site, Site.id == Device.site_id)
                .outerjoin(Tent, Tent.id == Device.tent_id)
                .outerjoin(Zone, Zone.id == Device.zone_id)
                .where(Site.site_id == DEFAULT_SITE_ID)
                .where(Device.device_id.in_(_STATUS_DEVICE_ORDER))
            )
        ).all()
        by_id = {}
        for device, site_id, tent_id, zone_id in rows:
            kind = _DEVICE_KIND_MAP.get(device.kind)
            if device.id is None or kind is None:
                continue
            by_id[device.device_id] = _ScopedDevice(
                pk=device.id,
                device_id=device.device_id,
                name=device.name,
                kind=kind,
                site_id=site_id,
                tent_id=tent_id,
                zone_id=zone_id,
                metadata=device.metadata_json,
            )
        return [
            by_id[device_id] for device_id in _STATUS_DEVICE_ORDER if device_id in by_id
        ]

    def _sensor_device_status(
        self,
        now: datetime,
        device: _ScopedDevice,
        nodes_by_location: dict[SensorLocation, SensorNode],
    ) -> DeviceStatus:
        location_value = device.metadata.get("legacy_location")
        node = None
        if location_value is not None:
            with contextlib.suppress(ValueError):
                node = nodes_by_location.get(SensorLocation(location_value))
        last_seen = node.last_seen if node is not None else None
        return DeviceStatus(
            name=device.name,
            kind=device.kind,
            status=_status_from_age(now, last_seen, device.kind),
            last_seen=last_seen,
            device_id=device.device_id,
            site_id=device.site_id,
            tent_id=device.tent_id,
            zone_id=device.zone_id,
        )

    async def _actuator_status(
        self,
        session: AsyncSession,
        now: datetime,
        device: _ScopedDevice,
    ) -> DeviceStatus:
        last_seen: datetime | None = None
        last = (
            await session.exec(
                select(SensorReading)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .where(Capability.device_id == device.pk)
                .where(Capability.metric_name == "humidifier_on")
                .order_by(SensorReading.ts.desc())
                .limit(1)
            )
        ).first()
        if last is not None:
            last_seen = last.ts
        return DeviceStatus(
            name=device.name,
            kind=device.kind,
            status=_status_from_age(now, last_seen, device.kind),
            last_seen=last_seen,
            device_id=device.device_id,
            site_id=device.site_id,
            tent_id=device.tent_id,
            zone_id=device.zone_id,
        )

    def _camera_status(self, now: datetime, device: _ScopedDevice) -> DeviceStatus:
        """Probe the dirt-camera daemon's unix socket via ``get_state``."""
        sock_path = _camera_socket_path()
        try:
            resp = self._camera_rpc(sock_path, "get_state")
        except (FileNotFoundError, ConnectionRefusedError, TimeoutError, OSError):
            return DeviceStatus(
                name=device.name,
                kind=device.kind,
                status="offline",
                last_seen=None,
                note="daemon unreachable",
                device_id=device.device_id,
                site_id=device.site_id,
                tent_id=device.tent_id,
                zone_id=device.zone_id,
            )
        if resp.get("_status") != "ok":
            return DeviceStatus(
                name=device.name,
                kind=device.kind,
                status="offline",
                last_seen=None,
                note=resp.get("msg") or str(resp.get("_status")),
                device_id=device.device_id,
                site_id=device.site_id,
                tent_id=device.tent_id,
                zone_id=device.zone_id,
            )
        connected = resp.get("camera_connected", False)
        return DeviceStatus(
            name=device.name,
            kind=device.kind,
            status="ok" if connected else "warn",
            last_seen=now,
            note=None if connected else "camera reported disconnected",
            device_id=device.device_id,
            site_id=device.site_id,
            tent_id=device.tent_id,
            zone_id=device.zone_id,
        )

    def _voice_status(self, now: datetime, device: _ScopedDevice) -> DeviceStatus:
        """Jabra / Claudia — infer from ``systemctl --user is-active dirt-voice``."""
        active = self._service_active_check("dirt-voice")
        if active:
            return DeviceStatus(
                name=device.name,
                kind=device.kind,
                status="listening",
                last_seen=now,
                device_id=device.device_id,
                site_id=device.site_id,
                tent_id=device.tent_id,
                zone_id=device.zone_id,
            )
        return DeviceStatus(
            name=device.name,
            kind=device.kind,
            status="offline",
            last_seen=None,
            device_id=device.device_id,
            site_id=device.site_id,
            tent_id=device.tent_id,
            zone_id=device.zone_id,
        )
