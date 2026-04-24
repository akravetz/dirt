"""Sensor ingest endpoint.

ESP32 plant nodes POST their readings here. Uses shared-secret bearer auth
(separate from the cookie-auth UI and the MCP bearer token). Excluded from
AuthMiddleware via the `/api/ingest` prefix in app.py.
"""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from dirt_hwd.deps import get_readings, get_settings
from dirt_shared.config import Settings
from dirt_shared.sensor_contract import missing_emitted
from dirt_shared.services.readings import ReadingsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


class IngestPayload(BaseModel):
    location: str = Field(min_length=1, max_length=64)
    metrics: dict[str, float]
    source: str = "esp32"
    ip: str | None = None
    firmware_version: str | None = None
    uptime_ms: int | None = None


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


def _warn_on_emitted_drift(location: str, payload_metrics: dict[str, float]) -> None:
    """Log a warning when a known location's payload is missing a metric the
    sensor contract says it emits — e.g. firmware was flashed but the
    contract in dirt_shared.sensor_contract wasn't updated. Permissive by
    design; never rejects ingest (would block legitimate rolling flashes).
    """
    missing = missing_emitted(location, payload_metrics.keys())
    if missing:
        logger.warning(
            "ingest %s missing expected metrics %s (got %s) — "
            "update sensor_contract.EMITTED_METRICS if this is intentional",
            location,
            sorted(missing),
            sorted(payload_metrics.keys()),
        )


def _check_token(authorization: str | None, expected_token: str) -> None:
    expected = f"Bearer {expected_token}"
    if not authorization or authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )


@router.post("/api/ingest/sensors", status_code=status.HTTP_202_ACCEPTED)
async def ingest_sensors(
    payload: IngestPayload,
    request: Request,
    authorization: str | None = Header(default=None),
    readings: ReadingsService = Depends(get_readings),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    _check_token(authorization, settings.sensor_ingest_token)

    # If caller didn't self-report IP, use the connection's remote address.
    ip = payload.ip or (request.client.host if request.client else None)

    _warn_on_emitted_drift(payload.location, payload.metrics)

    metrics = _augment_temp_rh_metrics(payload.metrics)

    await readings.ingest_reading(
        location=payload.location,
        metrics=metrics,
        source=payload.source,
        ip=ip,
        firmware_version=payload.firmware_version,
        uptime_ms=payload.uptime_ms,
    )
    return {"ok": True, "location": payload.location, "count": len(metrics)}
