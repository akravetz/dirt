"""Sensor ingest endpoint.

ESP32 plant nodes POST their readings here. Uses shared-secret bearer auth
(separate from the cookie-auth UI and the MCP bearer token). Excluded from
AuthMiddleware via the `/api/ingest` prefix in app.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from dirt_hwd.deps import get_readings, get_settings
from dirt_shared.config import Settings
from dirt_shared.services.readings import ReadingsService

router = APIRouter(tags=["ingest"])


class IngestPayload(BaseModel):
    location: str = Field(min_length=1, max_length=64)
    metrics: dict[str, float]
    source: str = "esp32"
    ip: str | None = None
    firmware_version: str | None = None
    uptime_ms: int | None = None


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

    await readings.ingest_reading(
        location=payload.location,
        metrics=payload.metrics,
        source=payload.source,
        ip=ip,
        firmware_version=payload.firmware_version,
        uptime_ms=payload.uptime_ms,
    )
    return {"ok": True, "location": payload.location, "count": len(payload.metrics)}
