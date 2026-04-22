"""System endpoints — device status table.

Thin wrapper over :class:`SystemStatusService.get_device_statuses` that
surfaces the 8-row device table the dashboard renders. Status taxonomy:
``ok | listening | warn | offline`` (see ``DeviceStatusKind`` in the
generated contract models). Jabra status is mocked from
``systemctl --user is-active dirt-voice`` inside the service layer.
"""

from __future__ import annotations

from dirt_contracts.webapp_v1.models import (
    DevicesResponse,
    DeviceStatus,
    DeviceStatusKind,
    Kind,
)
from fastapi import APIRouter, Depends

from dirt_shared.services.system_status import SystemStatusService
from dirt_web.deps import get_system_status

router = APIRouter(tags=["system"])


@router.get("/api/system/devices", response_model=DevicesResponse)
async def system_devices(
    service: SystemStatusService = Depends(get_system_status),
) -> DevicesResponse:
    """Return the 8-row device status table."""
    statuses = await service.get_device_statuses()
    devices = [
        DeviceStatus(
            name=s.name,
            kind=Kind(s.kind),
            status=DeviceStatusKind(s.status),
            last_seen=s.last_seen,
            note=s.note,
        )
        for s in statuses
    ]
    return DevicesResponse(ts=service.now(), devices=devices)
