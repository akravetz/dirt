"""Local state projection for the hosted control-plane gateway."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_gateway.protocols import AssetProjection
from dirt_shared.models import (
    Capability,
    Device,
    Site,
    Snapshot,
    Tent,
    Zone,
)
from dirt_shared.services.light_schedules import LightScheduleService
from dirt_shared.services.scope_catalog import ScopeCatalogService
from dirt_shared.services.snapshots import SnapshotsService, get_snapshot_path

ROLLUP_SPECS: tuple[tuple[str, timedelta, int], ...] = (
    ("5m", timedelta(hours=24), 300),
    ("1h", timedelta(days=7), 3600),
    ("4h", timedelta(days=30), 14400),
)


class GatewayLocalServiceBundle:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock,
        stale_after_s: int = 300,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._stale_after_s = stale_after_s
        self._catalog = ScopeCatalogService(engine)
        self._light_schedules = LightScheduleService(engine, clock=clock)
        self._snapshots = SnapshotsService(engine)

    async def collect_catalog(self, site_id: str) -> dict[str, Any]:
        sites = [
            site for site in await self._catalog.list_sites() if site.site_id == site_id
        ]
        if not sites:
            return {
                "site": {
                    "site_id": site_id,
                    "name": site_id,
                    "timezone": "America/Denver",
                },
                "tents": [],
                "zones": [],
                "devices": [],
                "capabilities": [],
            }
        site = sites[0]
        tents = await self._catalog.list_tents(site_id=site_id)
        devices = []
        for tent in tents:
            tent_devices = await self._catalog.list_tent_devices(
                site_id=site_id, tent_id=tent.tent_id
            )
            devices.extend(tent_devices or [])

        return {
            "site": {
                "site_id": site.site_id,
                "name": site.name,
                "timezone": site.timezone,
            },
            "tents": [
                {
                    "tent_id": tent.tent_id,
                    "name": tent.name,
                    "is_active": tent.active,
                }
                for tent in tents
            ],
            "zones": await self._collect_zones(site_id),
            "devices": [
                {
                    "tent_id": device.tent_id,
                    "zone_id": device.zone_id,
                    "device_id": device.device_id,
                    "name": device.name,
                    "kind": device.kind,
                    "controller": device.controller,
                    "is_active": device.enabled,
                    "last_seen_at": device.last_seen,
                }
                for device in devices
                if device.tent_id is not None
            ],
            "capabilities": await self._collect_capabilities(site_id),
            "schedules": [
                {
                    "site_id": schedule.site_id,
                    "tent_id": schedule.tent_id,
                    "zone_id": schedule.zone_id,
                    "device_id": schedule.device_id,
                    "capability_id": schedule.capability_id,
                    "schedule_id": schedule.schedule_id,
                    "kind": schedule.kind,
                    "starts_local": schedule.starts_local.isoformat(),
                    "ends_local": schedule.ends_local.isoformat(),
                    "timezone": schedule.timezone,
                    "is_enabled": schedule.enabled,
                }
                for schedule in await self._light_schedules.list_light_schedules(
                    site_id=site_id
                )
            ],
        }

    async def collect_latest_metrics(self, site_id: str) -> dict[str, Any]:
        metrics: list[dict[str, Any]] = []
        async with AsyncSession(self._engine) as session:
            result = await session.exec(
                text(_LATEST_METRICS_SQL),
                params={"site_id": site_id},
            )
            for row in result.mappings().all():
                metrics.append(
                    {
                        "site_id": site_id,
                        "tent_id": row["tent_id"],
                        "zone_id": row["zone_id"],
                        "device_id": row["device_id"],
                        "capability_id": row["capability_id"],
                        "metric": row["metric"],
                        "value": float(row["value"]),
                        "unit": row["unit"],
                        "source_updated_at": _as_utc(row["source_updated_at"]),
                        "stale_after_s": self._stale_after_s,
                    }
                )
        return {"site_id": site_id, "metrics": metrics}

    async def collect_rollups(self, site_id: str) -> dict[str, Any]:
        now = self._clock()
        rollups: list[dict[str, Any]] = []
        async with AsyncSession(self._engine) as session:
            for bucket, window, bucket_s in ROLLUP_SPECS:
                result = await session.exec(
                    text(_ROLLUP_SQL),
                    params={
                        "site_id": site_id,
                        "since": now - window,
                        "bucket_s": bucket_s,
                    },
                )
                for row in result.mappings().all():
                    bucket_start = _as_utc(row["bucket_start_at"])
                    rollups.append(
                        {
                            "site_id": site_id,
                            "tent_id": row["tent_id"],
                            "capability_id": row["capability_id"],
                            "metric": row["metric"],
                            "bucket": bucket,
                            "bucket_start_at": bucket_start,
                            "bucket_end_at": bucket_start + timedelta(seconds=bucket_s),
                            "min_value": _maybe_float(row["min_value"]),
                            "avg_value": _maybe_float(row["avg_value"]),
                            "max_value": _maybe_float(row["max_value"]),
                            "sample_count": int(row["sample_count"]),
                            "unit": row["unit"],
                        }
                    )
        return {"site_id": site_id, "rollups": rollups}

    async def latest_snapshot_asset(self, site_id: str) -> AssetProjection | None:
        tents = await self._catalog.list_tents(site_id=site_id)
        for tent in sorted(tents, key=lambda item: (not item.is_default, item.tent_id)):
            snapshot = await self._snapshots.latest(
                site_id=site_id,
                tent_id=tent.tent_id,
            )
            if snapshot is None:
                continue
            path = get_snapshot_path(snapshot)
            if path is None:
                continue
            digest = _file_sha256(path)
            object_key = f"{site_id}/{tent.tent_id}/snapshots/{path.name}"
            sign_request = {
                "site_id": site_id,
                "tent_id": tent.tent_id,
                "content_type": "image/jpeg",
                "byte_size": path.stat().st_size,
                "object_key": object_key,
                "asset_id": digest,
                "sha256": digest,
                "kind": snapshot.kind,
            }
            complete_request = {
                **sign_request,
                "captured_at": _as_utc(snapshot.ts),
                "zone_id": await self._public_zone_id(snapshot),
                "device_id": await self._public_device_id(snapshot),
            }
            return AssetProjection(
                sign_request=sign_request,
                complete_request=complete_request,
                file_path=path,
            )
        return None

    async def _collect_zones(self, site_id: str) -> list[dict[str, Any]]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(Zone, Tent.tent_id)
                    .join(Site, Site.id == Zone.site_id)
                    .join(Tent, Tent.id == Zone.tent_id)
                    .where(Site.site_id == site_id)
                    .order_by(Tent.tent_id, Zone.zone_id)
                )
            ).all()
        return [
            {
                "tent_id": tent_id,
                "zone_id": zone.zone_id,
                "name": zone.name,
                "kind": zone.zone_type,
                "is_active": zone.active,
            }
            for zone, tent_id in rows
        ]

    async def _collect_capabilities(self, site_id: str) -> list[dict[str, Any]]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(Capability, Device.device_id, Tent.tent_id)
                    .join(Device, Device.id == Capability.device_id)
                    .join(Site, Site.id == Device.site_id)
                    .outerjoin(Tent, Tent.id == Device.tent_id)
                    .where(Site.site_id == site_id)
                    .order_by(Tent.tent_id, Device.device_id, Capability.capability_id)
                )
            ).all()
        return [
            {
                "tent_id": tent_id,
                "device_id": device_id,
                "capability_id": capability.capability_id,
                "metric_name": capability.metric_name,
                "kind": capability.kind,
                "unit": capability.unit,
                "is_enabled": capability.enabled,
            }
            for capability, device_id, tent_id in rows
            if tent_id is not None
        ]

    async def _public_zone_id(self, snapshot: Snapshot) -> str | None:
        if snapshot.zone_id is None:
            return None
        async with AsyncSession(self._engine) as session:
            zone = await session.get(Zone, snapshot.zone_id)
            return None if zone is None else zone.zone_id

    async def _public_device_id(self, snapshot: Snapshot) -> str | None:
        if snapshot.device_id is None:
            return None
        async with AsyncSession(self._engine) as session:
            device = await session.get(Device, snapshot.device_id)
            return None if device is None else device.device_id


_LATEST_METRICS_SQL = """
WITH latest AS (
  SELECT DISTINCT ON (capability_id)
    capability_id,
    value,
    ts
  FROM sensorreading
  ORDER BY capability_id, ts DESC
)
SELECT
  t.tent_id,
  z.zone_id,
  d.device_id,
  c.capability_id,
  c.metric_name AS metric,
  latest.value,
  c.unit,
  latest.ts AS source_updated_at
FROM capability c
JOIN latest ON latest.capability_id = c.id
JOIN device d ON d.id = c.device_id
JOIN site s ON s.id = d.site_id
JOIN tent t ON t.id = d.tent_id
LEFT JOIN zone z ON z.id = d.zone_id
WHERE s.site_id = :site_id
  AND c.enabled = true
  AND c.metric_name IS NOT NULL
ORDER BY d.device_id, c.capability_id
"""


_ROLLUP_SQL = """
SELECT
  t.tent_id,
  c.capability_id,
  c.metric_name AS metric,
  c.unit,
  date_bin(
    make_interval(secs => :bucket_s),
    sr.ts,
    TIMESTAMPTZ '1970-01-01'
  ) AS bucket_start_at,
  min(sr.value) AS min_value,
  avg(sr.value) AS avg_value,
  max(sr.value) AS max_value,
  count(*) AS sample_count
FROM sensorreading sr
JOIN capability c ON c.id = sr.capability_id
JOIN device d ON d.id = c.device_id
JOIN site s ON s.id = d.site_id
JOIN tent t ON t.id = d.tent_id
WHERE s.site_id = :site_id
  AND sr.ts >= :since
  AND c.metric_name IS NOT NULL
GROUP BY t.tent_id, c.capability_id, c.metric_name, c.unit, bucket_start_at
ORDER BY bucket_start_at, t.tent_id, c.capability_id
"""


def _as_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def _maybe_float(value: Any) -> float | None:
    return None if value is None else round(float(value), 4)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
