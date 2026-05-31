"""Local state projection for the hosted control-plane gateway."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_gateway.protocols import AssetUploadProjection
from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetSignUploadRequest,
    CatalogCapability,
    CatalogDevice,
    CatalogPlant,
    CatalogRequest,
    CatalogSchedule,
    CatalogSite,
    CatalogTent,
    CatalogZone,
    LatestMetricItem,
    LatestMetricsRequest,
    RollupItem,
    RollupsRequest,
    WikiProjectionPage,
    WikiProjectionRequest,
)
from dirt_shared.models import (
    Capability,
    Device,
    GrowRun,
    Plant,
    Site,
    Snapshot,
    Tent,
    Zone,
)
from dirt_shared.models.enums import PlantStatus
from dirt_shared.services.light_schedules import LightScheduleService
from dirt_shared.services.scope_catalog import ScopeCatalogService
from dirt_shared.services.snapshots import SnapshotsService, get_snapshot_path

ROLLUP_SPECS: tuple[tuple[str, timedelta, int], ...] = (
    ("5m", timedelta(hours=24), 300),
    ("1h", timedelta(days=7), 3600),
    ("4h", timedelta(days=30), 14400),
    ("1d", timedelta(days=90), 86400),
)
WIKI_ROOT = Path(__file__).resolve().parents[4] / "wiki"
WIKI_EXCLUDED_PATHS = ("wiki/AGENTS.md", "wiki/private/**", "wiki/raw/**")
WIKI_PLANT_PAGE_GLOB = "grows/*/plants/*.md"


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

    async def collect_catalog(self, site_id: str) -> CatalogRequest:
        sites = [
            site for site in await self._catalog.list_sites() if site.site_id == site_id
        ]
        if not sites:
            return CatalogRequest(
                site=CatalogSite(
                    site_id=site_id,
                    name=site_id,
                    timezone="America/Denver",
                )
            )
        site = sites[0]
        tents = await self._catalog.list_tents(site_id=site_id)
        devices = []
        for tent in tents:
            tent_devices = await self._catalog.list_tent_devices(
                site_id=site_id, tent_id=tent.tent_id
            )
            devices.extend(tent_devices or [])

        return CatalogRequest(
            site=CatalogSite(
                site_id=site.site_id,
                name=site.name,
                timezone=site.timezone,
            ),
            tents=[
                CatalogTent(
                    tent_id=tent.tent_id,
                    name=tent.name,
                    is_active=tent.active,
                )
                for tent in tents
            ],
            zones=await self._collect_zones(site_id),
            devices=[
                CatalogDevice(
                    tent_id=device.tent_id,
                    zone_id=device.zone_id,
                    device_id=device.device_id,
                    name=device.name,
                    kind=device.kind,
                    controller=device.controller,
                    is_active=device.enabled,
                    last_seen_at=device.last_seen,
                )
                for device in devices
                if device.tent_id is not None
            ],
            capabilities=await self._collect_capabilities(site_id),
            schedules=[
                CatalogSchedule(
                    site_id=schedule.site_id,
                    tent_id=schedule.tent_id,
                    zone_id=schedule.zone_id,
                    device_id=schedule.device_id,
                    capability_id=schedule.capability_id,
                    schedule_id=schedule.schedule_id,
                    kind=schedule.kind,
                    starts_local=schedule.starts_local,
                    ends_local=schedule.ends_local,
                    timezone=schedule.timezone,
                    is_enabled=schedule.enabled,
                )
                for schedule in await self._light_schedules.list_light_schedules(
                    site_id=site_id
                )
            ],
            plants=await self._collect_plants(site_id),
        )

    async def collect_latest_metrics(self, site_id: str) -> LatestMetricsRequest:
        metrics: list[LatestMetricItem] = []
        async with AsyncSession(self._engine) as session:
            result = await session.exec(
                text(_latest_metrics_sql()),
                params={"site_id": site_id},
            )
            for row in result.mappings().all():
                metrics.append(
                    LatestMetricItem(
                        site_id=site_id,
                        tent_id=row["tent_id"],
                        zone_id=row["zone_id"],
                        device_id=row["device_id"],
                        capability_id=row["capability_id"],
                        metric=row["metric"],
                        value=float(row["value"]),
                        unit=row["unit"],
                        source_updated_at=_as_utc(row["source_updated_at"]),
                        stale_after_s=self._stale_after_s,
                    )
                )
        return LatestMetricsRequest(site_id=site_id, metrics=metrics)

    async def collect_rollups(
        self, site_id: str, *, bucket_names: set[str] | None = None
    ) -> RollupsRequest:
        now = self._clock()
        rollups: list[RollupItem] = []
        async with AsyncSession(self._engine) as session:
            for bucket, window, bucket_s in ROLLUP_SPECS:
                if bucket_names is not None and bucket not in bucket_names:
                    continue
                rollups.extend(
                    await collect_canonical_history_rollups(
                        session,
                        site_id=site_id,
                        since=now - window,
                        bucket=bucket,
                        bucket_s=bucket_s,
                    )
                )
                rollups.extend(
                    await collect_legacy_calibrated_soil_moisture_rollups(
                        session,
                        site_id=site_id,
                        since=now - window,
                        bucket=bucket,
                        bucket_s=bucket_s,
                    )
                )
        return RollupsRequest(site_id=site_id, rollups=rollups)

    async def collect_wiki_pages(self, site_id: str) -> WikiProjectionRequest:
        pages = [
            _wiki_projection_page(path)
            for path in sorted(WIKI_ROOT.glob(WIKI_PLANT_PAGE_GLOB))
            if _wiki_path_is_projected(path)
        ]
        return WikiProjectionRequest(
            site_id=site_id,
            generated_at=self._clock(),
            pages=pages,
            excluded_paths=list(WIKI_EXCLUDED_PATHS),
            content_hash=_wiki_projection_hash(pages, WIKI_EXCLUDED_PATHS),
        )

    async def latest_snapshot_asset(self, site_id: str) -> AssetUploadProjection | None:
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
            sign_request = AssetSignUploadRequest(
                site_id=site_id,
                tent_id=tent.tent_id,
                content_type="image/jpeg",
                byte_size=path.stat().st_size,
                object_key=object_key,
                asset_id=digest,
                sha256=digest,
                kind=snapshot.kind,
            )
            complete_request = AssetCompleteRequest(
                **sign_request.model_dump(),
                captured_at=_as_utc(snapshot.ts),
                zone_id=await self._public_zone_id(snapshot),
                device_id=await self._public_device_id(snapshot),
            )
            return AssetUploadProjection(
                sign_request=sign_request,
                complete_request=complete_request,
                file_path=path,
            )
        return None

    async def _collect_zones(self, site_id: str) -> list[CatalogZone]:
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
            CatalogZone(
                tent_id=tent_id,
                zone_id=zone.zone_id,
                name=zone.name,
                kind=zone.zone_type,
                is_active=zone.active,
            )
            for zone, tent_id in rows
        ]

    async def _collect_capabilities(self, site_id: str) -> list[CatalogCapability]:
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
            CatalogCapability(
                tent_id=tent_id,
                device_id=device_id,
                capability_id=capability.capability_id,
                metric_name=capability.metric_name,
                kind=capability.kind,
                unit=capability.unit,
                is_enabled=capability.enabled,
            )
            for capability, device_id, tent_id in rows
            if tent_id is not None
        ]

    async def _collect_plants(self, site_id: str) -> list[CatalogPlant]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(
                        Plant,
                        GrowRun.grow_run_id,
                        Tent.tent_id,
                        Device.device_id,
                        Capability.capability_id,
                    )
                    .join(GrowRun, GrowRun.id == Plant.growrun_id)
                    .join(Site, Site.id == Plant.site_id)
                    .join(Tent, Tent.id == Plant.tent_id)
                    .outerjoin(
                        Capability, Capability.id == Plant.moisture_capability_id
                    )
                    .outerjoin(Device, Device.id == Capability.device_id)
                    .where(Site.site_id == site_id)
                    .where(GrowRun.is_current.is_(True))
                    .order_by(Tent.tent_id, Plant.display_order, Plant.plant_id)
                )
            ).all()
        return [
            CatalogPlant(
                tent_id=tent_id,
                grow_run_id=grow_run_id,
                plant_id=plant.plant_id,
                name=plant.name,
                display_order=plant.display_order,
                sticker_color=plant.sticker_color,
                status=plant.status,
                purple=plant.purple,
                moisture_target_low=plant.moisture_target_low,
                moisture_target_high=plant.moisture_target_high,
                moisture_device_id=device_id,
                moisture_capability_id=capability_id,
                wiki_path=_plant_wiki_path(grow_run_id, plant.plant_id),
                is_active=plant.status != PlantStatus.RETIRED,
            )
            for plant, grow_run_id, tent_id, device_id, capability_id in rows
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


async def collect_canonical_history_rollups(
    session: AsyncSession,
    *,
    site_id: str,
    since: datetime,
    bucket: str,
    bucket_s: int,
) -> list[RollupItem]:
    sql = """
SELECT
  t.tent_id,
  d.device_id,
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
JOIN metric_presentation mp
  ON mp.metric = c.metric_name
 AND mp.history_enabled = true
JOIN device d ON d.id = c.device_id
JOIN site s ON s.id = d.site_id
JOIN tent t ON t.id = d.tent_id
WHERE s.site_id = :site_id
  AND sr.ts >= :since
  AND c.enabled = true
  AND c.metric_name IS NOT NULL
  AND sr.metric = c.metric_name
GROUP BY
  t.tent_id,
  d.device_id,
  c.capability_id,
  c.metric_name,
  c.unit,
  bucket_start_at
ORDER BY bucket_start_at, t.tent_id, d.device_id, c.capability_id, c.metric_name
"""
    result = await session.exec(
        text(sql),
        params={"site_id": site_id, "since": since, "bucket_s": bucket_s},
    )
    return _rollup_items_from_rows(
        result.mappings().all(),
        site_id=site_id,
        bucket=bucket,
        bucket_s=bucket_s,
    )


async def collect_legacy_calibrated_soil_moisture_rollups(
    session: AsyncSession,
    *,
    site_id: str,
    since: datetime,
    bucket: str,
    bucket_s: int,
) -> list[RollupItem]:
    sql = """
SELECT
  t.tent_id,
  d.device_id,
  c.capability_id,
  mp.metric AS metric,
  mp.unit,
  date_bin(
    make_interval(secs => :bucket_s),
    sr.ts,
    TIMESTAMPTZ '1970-01-01'
  ) AS bucket_start_at,
  round(
    (
      LEAST(
        100.0,
        GREATEST(
          0.0,
          100.0 * (sc.raw_high - max(sr.value)) / (sc.raw_high - sc.raw_low)
        )
      )
    )::numeric,
    4
  )::double precision AS min_value,
  round(
    (
      LEAST(
        100.0,
        GREATEST(
          0.0,
          100.0 * (sc.raw_high - avg(sr.value)) / (sc.raw_high - sc.raw_low)
        )
      )
    )::numeric,
    4
  )::double precision AS avg_value,
  round(
    (
      LEAST(
        100.0,
        GREATEST(
          0.0,
          100.0 * (sc.raw_high - min(sr.value)) / (sc.raw_high - sc.raw_low)
        )
      )
    )::numeric,
    4
  )::double precision AS max_value,
  count(*) AS sample_count
FROM sensorreading sr
JOIN capability c ON c.id = sr.capability_id
JOIN sensorcalibration sc
  ON sc.capability_id = c.id
 AND sc.metric = 'soil_moisture_raw'
 AND sc.raw_high > sc.raw_low
JOIN metric_presentation mp
  ON mp.metric = 'soil_moisture_pct'
 AND mp.history_enabled = true
JOIN device d ON d.id = c.device_id
JOIN site s ON s.id = d.site_id
JOIN tent t ON t.id = d.tent_id
WHERE s.site_id = :site_id
  AND sr.ts >= :since
  AND c.enabled = true
  AND c.metric_name = 'soil_moisture_raw'
  AND sr.metric = 'soil_moisture_raw'
GROUP BY
  t.tent_id,
  d.device_id,
  c.capability_id,
  mp.metric,
  mp.unit,
  sc.raw_low,
  sc.raw_high,
  bucket_start_at
ORDER BY bucket_start_at, t.tent_id, d.device_id, c.capability_id, mp.metric
"""
    result = await session.exec(
        text(sql),
        params={"site_id": site_id, "since": since, "bucket_s": bucket_s},
    )
    return _rollup_items_from_rows(
        result.mappings().all(),
        site_id=site_id,
        bucket=bucket,
        bucket_s=bucket_s,
    )


def _latest_metrics_sql() -> str:
    return """
WITH latest AS (
  SELECT DISTINCT ON (capability_id)
    capability_id,
    value,
    ts
  FROM sensorreading
  ORDER BY capability_id, ts DESC
),
base AS (
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
)
SELECT
  tent_id,
  zone_id,
  device_id,
  capability_id,
  metric,
  value,
  unit,
  source_updated_at
FROM base
UNION ALL
SELECT
  base.tent_id,
  base.zone_id,
  base.device_id,
  base.capability_id,
  'soil_moisture_pct' AS metric,
  round(
    (
      LEAST(
        100.0,
        GREATEST(
          0.0,
          100.0 * (sc.raw_high - base.value) / (sc.raw_high - sc.raw_low)
        )
      )
    )::numeric,
    4
  )::double precision AS value,
  '%' AS unit,
  base.source_updated_at
FROM base
JOIN device d ON d.device_id = base.device_id
JOIN capability c ON c.device_id = d.id AND c.capability_id = base.capability_id
JOIN sensorcalibration sc ON sc.capability_id = c.id AND sc.metric = base.metric
WHERE base.metric = 'soil_moisture_raw'
  AND sc.raw_high > sc.raw_low
ORDER BY device_id, capability_id, metric
"""


def _rollup_items_from_rows(
    rows: list[Any],
    *,
    site_id: str,
    bucket: str,
    bucket_s: int,
) -> list[RollupItem]:
    rollups: list[RollupItem] = []
    for row in rows:
        bucket_start = _as_utc(row["bucket_start_at"])
        rollups.append(
            RollupItem(
                site_id=site_id,
                tent_id=row["tent_id"],
                device_id=row["device_id"],
                capability_id=row["capability_id"],
                metric=row["metric"],
                bucket=bucket,
                bucket_start_at=bucket_start,
                bucket_end_at=bucket_start + timedelta(seconds=bucket_s),
                min_value=_maybe_float(row["min_value"]),
                avg_value=_maybe_float(row["avg_value"]),
                max_value=_maybe_float(row["max_value"]),
                sample_count=int(row["sample_count"]),
                unit=row["unit"],
            )
        )
    return rollups


def _as_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def _maybe_float(value: Any) -> float | None:
    return None if value is None else round(float(value), 4)


def _plant_wiki_path(grow_run_id: str, plant_id: str) -> str | None:
    wiki_path = f"grows/{grow_run_id}/plants/plant-{plant_id}.md"
    return f"wiki/{wiki_path}" if (WIKI_ROOT / wiki_path).exists() else None


def _wiki_projection_page(path: Path) -> WikiProjectionPage:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    frontmatter, body = _split_frontmatter(text)
    title = _wiki_title(path, frontmatter=frontmatter, body_markdown=body)
    return WikiProjectionPage(
        path=_wiki_payload_path(path),
        title=title,
        frontmatter=frontmatter,
        body_markdown=body,
        sha256=_wiki_content_hash(frontmatter=frontmatter, body_markdown=body),
        source_updated_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
    )


def _wiki_path_is_projected(path: Path) -> bool:
    payload_path = _wiki_payload_path(path)
    return (
        payload_path not in WIKI_EXCLUDED_PATHS
        and not payload_path.startswith("wiki/private/")
        and not payload_path.startswith("wiki/raw/")
    )


def _wiki_payload_path(path: Path) -> str:
    return f"wiki/{path.relative_to(WIKI_ROOT).as_posix()}"


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    remainder = text.removeprefix("---\n")
    if "\n---\n" not in remainder:
        return {}, text
    frontmatter_text, body = remainder.split("\n---\n", 1)
    return _parse_frontmatter(frontmatter_text), body


def _parse_frontmatter(text: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        values[key.strip()] = _parse_frontmatter_value(raw_value.strip())
    return values


def _parse_frontmatter_value(value: str) -> Any:
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_strip_yaml_quotes(item.strip()) for item in inner.split(",")]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "~"}:
        return None
    return _strip_yaml_quotes(value)


def _strip_yaml_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _wiki_title(path: Path, *, frontmatter: dict[str, Any], body_markdown: str) -> str:
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in body_markdown.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return path.stem


def _wiki_content_hash(*, frontmatter: dict[str, Any], body_markdown: str) -> str:
    return _sha256_json(
        {
            "frontmatter": frontmatter,
            "body_markdown": body_markdown,
        }
    )


def _wiki_projection_hash(
    pages: list[WikiProjectionPage], excluded_paths: tuple[str, ...]
) -> str:
    return _sha256_json(
        {
            "pages": [
                page.model_dump(
                    mode="json",
                    exclude={"source_updated_at"},
                )
                for page in pages
            ],
            "excluded_paths": list(excluded_paths),
        }
    )


def _sha256_json(value: dict[str, Any]) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
