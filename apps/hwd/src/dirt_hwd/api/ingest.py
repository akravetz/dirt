"""Sensor ingest endpoint.

ESP32 plant nodes POST their readings here. Uses shared-secret bearer auth.
"""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from dirt_hwd.deps import get_readings, get_sensor_quality, get_settings
from dirt_hwd.services.sensor_quality import SensorQualityService
from dirt_shared.config import Settings
from dirt_shared.services.readings import ReadingsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])

_WIRE_METRIC_ALIASES: dict[str, dict[str, str]] = {
    "fan-controller": {
        "fan_duty_pct": "fan_pct",
    },
}


class DeviceDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    boot_count: int | None = None
    reset_reason: int | None = None
    loop_gap_max_ms: int | None = None
    loop_gap_over_5s_count: int | None = None
    http_get_fan_count: int | None = None
    http_post_fan_count: int | None = None
    http_not_found_count: int | None = None
    modbus_success_count: int | None = None
    modbus_failure_count: int | None = None
    modbus_crc_mismatch_count: int | None = None
    modbus_short_response_count: int | None = None
    modbus_no_response_count: int | None = None
    last_modbus_response_len: int | None = None
    ingest_ok_count: int | None = None
    ingest_fail_count: int | None = None
    last_ingest_code: int | None = None
    last_ingest_ms: int | None = None
    max_ingest_ms: int | None = None
    sht_read_fail_count: int | None = None
    free_heap_bytes: int | None = None
    min_free_heap_bytes: int | None = None
    max_alloc_heap_bytes: int | None = None


class IngestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: dict[str, float]
    source: str = "esp32"
    device_id: str = Field(min_length=1, max_length=64)
    capability_id: str | None = None
    ip: str | None = None
    firmware_version: str | None = None
    uptime_ms: int | None = None
    wifi_rssi_dbm: int | None = None
    wifi_reconnect_count: int | None = None
    wifi_driver_reset_count: int | None = None
    wifi_disconnect_reason: int | None = None
    wifi_disconnected_for_ms: int | None = None
    diagnostics: DeviceDiagnostics | None = None


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


def _canonicalize_wire_metrics(
    device_id: str | None, metrics: dict[str, float]
) -> dict[str, float]:
    aliases = _WIRE_METRIC_ALIASES.get(device_id or "")
    if not aliases:
        return metrics
    canonical = dict(metrics)
    for old_name, new_name in aliases.items():
        if old_name not in canonical:
            continue
        value = canonical.pop(old_name)
        canonical.setdefault(new_name, value)
    return canonical


async def _warn_on_emitted_drift(
    readings: ReadingsService,
    *,
    payload: IngestPayload,
    payload_metrics: dict[str, float],
) -> None:
    """Log when a known device omits a DB-backed expected wire metric.

    Permissive by design; never rejects ingest because that would block
    legitimate rolling flashes.
    """
    expected = await readings.get_expected_wire_metrics_for_device(
        device_id=payload.device_id,
    )
    missing = expected - set(payload_metrics)
    if missing:
        logger.warning(
            "ingest %s missing expected metrics %s (got %s) — "
            "update capability metadata if this is intentional",
            payload.device_id,
            sorted(missing),
            sorted(payload_metrics.keys()),
        )


def _check_token(authorization: str | None, expected_token: str) -> None:
    expected = f"Bearer {expected_token}"
    if not authorization or authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )


async def require_sensor_ingest_auth(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    _check_token(authorization, settings.sensor_ingest_token)


@router.post(
    "/api/ingest/sensors",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_sensor_ingest_auth)],
)
async def ingest_sensors(
    payload: IngestPayload,
    request: Request,
    readings: ReadingsService = Depends(get_readings),
    sensor_quality: SensorQualityService = Depends(get_sensor_quality),
) -> dict[str, object]:
    # If caller didn't self-report IP, use the connection's remote address.
    ip = payload.ip or (request.client.host if request.client else None)

    wire_metrics = _canonicalize_wire_metrics(payload.device_id, payload.metrics)
    await _warn_on_emitted_drift(
        readings,
        payload=payload,
        payload_metrics=wire_metrics,
    )

    metrics = _augment_temp_rh_metrics(wire_metrics)
    quality = await sensor_quality.filter_metrics(payload.device_id, metrics)

    if not quality.metrics:
        await readings.touch_device(
            device_id=payload.device_id,
            ip=ip,
            firmware_version=payload.firmware_version,
            uptime_ms=payload.uptime_ms,
            wifi_rssi_dbm=payload.wifi_rssi_dbm,
            wifi_reconnect_count=payload.wifi_reconnect_count,
            wifi_driver_reset_count=payload.wifi_driver_reset_count,
            wifi_disconnect_reason=payload.wifi_disconnect_reason,
            wifi_disconnected_for_ms=payload.wifi_disconnected_for_ms,
            diagnostics=payload.diagnostics.model_dump(exclude_none=True)
            if payload.diagnostics
            else None,
        )
        return {
            "ok": True,
            "device_id": payload.device_id,
            "count": 0,
            "rejected": sorted(quality.rejected),
        }

    inserted_count = await readings.ingest_reading(
        metrics=quality.metrics,
        source=payload.source,
        ip=ip,
        firmware_version=payload.firmware_version,
        uptime_ms=payload.uptime_ms,
        wifi_rssi_dbm=payload.wifi_rssi_dbm,
        wifi_reconnect_count=payload.wifi_reconnect_count,
        wifi_driver_reset_count=payload.wifi_driver_reset_count,
        wifi_disconnect_reason=payload.wifi_disconnect_reason,
        wifi_disconnected_for_ms=payload.wifi_disconnected_for_ms,
        diagnostics=payload.diagnostics.model_dump(exclude_none=True)
        if payload.diagnostics
        else None,
        device_id=payload.device_id,
        capability_id=payload.capability_id,
    )
    response: dict[str, object] = {
        "ok": True,
        "device_id": payload.device_id,
        "count": inserted_count,
    }
    if quality.rejected:
        response["rejected"] = sorted(quality.rejected)
    return response
