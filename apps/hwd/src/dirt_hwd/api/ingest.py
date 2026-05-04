"""Sensor ingest endpoint.

ESP32 plant nodes POST their readings here. Uses shared-secret bearer auth
(separate from the cookie-auth UI and the MCP bearer token). Excluded from
AuthMiddleware via the `/api/ingest` prefix in app.py.
"""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator

from dirt_hwd.deps import get_readings, get_sensor_quality, get_settings
from dirt_hwd.services.sensor_quality import SensorQualityService
from dirt_shared.config import Settings
from dirt_shared.sensor_contract import (
    is_known_legacy_location,
    legacy_location_for_device_id,
    missing_emitted,
    missing_emitted_for_device_id,
)
from dirt_shared.services.readings import ReadingsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


class IngestPayload(BaseModel):
    location: str | None = Field(default=None, min_length=1, max_length=64)
    metrics: dict[str, float]
    source: str = "esp32"
    site_id: str = "homebox"
    tent_id: str | None = "main"
    zone_id: str | None = None
    device_id: str | None = None
    capability_id: str | None = None
    ip: str | None = None
    firmware_version: str | None = None
    uptime_ms: int | None = None

    @model_validator(mode="after")
    def require_legacy_or_scoped_identity(self) -> IngestPayload:
        if self.location is None and self.device_id is None:
            raise ValueError("location is required unless device_id is present")
        return self


def _augment_temp_rh_metrics(metrics: dict[str, float]) -> dict[str, float]:
    """Derive temperature_f, vpd_kpa, dew_point_f from temperature_c +
    humidity_pct. Passthrough when either input is missing."""
    t_c = metrics.get("temperature_c")
    rh = metrics.get("humidity_pct")
    if t_c is None or rh is None:
        return metrics
    svp_kpa = 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))
    vpd = svp_kpa * (1 - rh / 100)
    # Magnus formula for dew point (°C). max() guards against log(0) on
    # a malformed 0 %RH reading.
    a, b = 17.27, 237.7
    gamma = (a * t_c) / (b + t_c) + math.log(max(rh, 0.01) / 100)
    dew_c = (b * gamma) / (a - gamma)
    return {
        **metrics,
        "temperature_f": t_c * 9 / 5 + 32,
        "vpd_kpa": vpd,
        "dew_point_f": dew_c * 9 / 5 + 32,
    }


def _warn_on_emitted_drift(
    location: str | None, device_id: str | None, payload_metrics: dict[str, float]
) -> None:
    """Log a warning when a known device's payload is missing a metric the
    sensor contract says it emits — e.g. firmware was flashed but the
    contract in dirt_shared.sensor_contract wasn't updated. Permissive by
    design; never rejects ingest (would block legitimate rolling flashes).
    """
    missing = (
        missing_emitted_for_device_id(device_id, payload_metrics.keys())
        if device_id is not None
        else missing_emitted(location or "", payload_metrics.keys())
    )
    if missing:
        identity = device_id or location or "unknown"
        logger.warning(
            "ingest %s missing expected metrics %s (got %s) — "
            "update sensor_contract.DEVICE_METRICS if this is intentional",
            identity,
            sorted(missing),
            sorted(payload_metrics.keys()),
        )


def _reject_known_legacy_only_payload(payload: IngestPayload) -> None:
    if payload.device_id is not None or payload.location is None:
        return
    if not is_known_legacy_location(payload.location):
        return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=(
            "device_id is required for current sensor ingest; "
            "legacy location-only payloads are no longer accepted for "
            f"{payload.location}"
        ),
    )


def _compat_location(payload: IngestPayload) -> str:
    """Return the temporary legacy location used by SensorNode/quality paths.

    Current ESP32 payloads are scoped by device_id. Unknown location-only
    payloads remain as an explicit legacy/test-only path until sensornode
    storage is removed in a later milestone.
    """
    if payload.location is not None:
        return payload.location
    legacy_location = legacy_location_for_device_id(payload.device_id)
    if legacy_location is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "location is required until this device has a legacy "
                "compatibility mapping"
            ),
        )
    return legacy_location


def _check_token(authorization: str | None, expected_token: str) -> None:
    expected = f"Bearer {expected_token}"
    if not authorization or authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )


@router.post("/api/ingest/sensors", status_code=status.HTTP_202_ACCEPTED)
async def ingest_sensors(  # noqa: PLR0913 — FastAPI boundary bundles request, auth, services, and settings.
    payload: IngestPayload,
    request: Request,
    authorization: str | None = Header(default=None),
    readings: ReadingsService = Depends(get_readings),
    sensor_quality: SensorQualityService = Depends(get_sensor_quality),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    _check_token(authorization, settings.sensor_ingest_token)
    _reject_known_legacy_only_payload(payload)

    # If caller didn't self-report IP, use the connection's remote address.
    ip = payload.ip or (request.client.host if request.client else None)
    compat_location = _compat_location(payload)

    _warn_on_emitted_drift(payload.location, payload.device_id, payload.metrics)

    metrics = _augment_temp_rh_metrics(payload.metrics)
    quality = await sensor_quality.filter_metrics(compat_location, metrics)

    if not quality.metrics:
        if payload.device_id is None:
            await readings.touch_node(
                location=compat_location,
                ip=ip,
                firmware_version=payload.firmware_version,
                uptime_ms=payload.uptime_ms,
            )
        else:
            await readings.touch_device(
                device_id=payload.device_id,
                site_id=payload.site_id,
                tent_id=payload.tent_id,
                zone_id=payload.zone_id,
                ip=ip,
                firmware_version=payload.firmware_version,
                uptime_ms=payload.uptime_ms,
            )
        return {
            "ok": True,
            "location": compat_location,
            "count": 0,
            "rejected": sorted(quality.rejected),
        }

    await readings.ingest_reading(
        location=compat_location,
        metrics=quality.metrics,
        source=payload.source,
        ip=ip,
        firmware_version=payload.firmware_version,
        uptime_ms=payload.uptime_ms,
        site_id=payload.site_id,
        tent_id=payload.tent_id,
        zone_id=payload.zone_id,
        device_id=payload.device_id,
        capability_id=payload.capability_id,
    )
    response: dict[str, object] = {
        "ok": True,
        "location": compat_location,
        "count": len(quality.metrics),
    }
    if quality.rejected:
        response["rejected"] = sorted(quality.rejected)
    return response
