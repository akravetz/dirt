"""Plant CRUD + live moisture join.

Backs ``GET /api/plants`` (summary of all plants for the dashboard strip)
and the DB-side fields of ``GET /api/plants/{code}`` (drawer header +
live moisture). The narrative parts of the drawer come from
``PlantDetailService``, which parses the plant's wiki markdown.

Moisture is computed from the plant's canonical
``moisture_capability_id`` and the matching ``sensorcalibration`` row.
Plants without a calibration return ``moisture_pct=None``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import PlantStatus, PlantSticker
from dirt_shared.models.plant import Plant
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.grow_state import BandStatus, band_status, tent_tz
from dirt_shared.services.plant_detail import PlantDetailService
from dirt_shared.services.readings import (
    compute_calibrated_pct,
    get_sensor_calibration,
)
from dirt_shared.services.scope import (
    DEFAULT_SITE_ID,
    DEFAULT_TENT_ID,
    current_grow_run,
)


@dataclass(frozen=True)
class PlantSummary:
    """One row in ``GET /api/plants``."""

    code: str
    name: str
    sticker_color: PlantSticker
    status: PlantStatus
    purple: bool
    label: str | None
    moisture_pct: float | None
    moisture_ts: datetime | None
    moisture_target_low: float
    moisture_target_high: float


@dataclass(frozen=True)
class MoisturePoint:
    ts: datetime
    value: float


# Bucket widths mirror ``_BUCKET_SQL`` in services/readings.py so the
# plant moisture series matches the sensor history resolution per range.
# 1h: raw (no bucketing). 24h: 5-minute buckets. 7d: hourly buckets.
# Applied after the per-reading calibration pass so each bucket's value
# is the mean of calibrated percentages, not raw ADC counts.
_MOISTURE_BUCKET_WIDTH: dict[str, timedelta] = {
    "24h": timedelta(minutes=5),
    "7d": timedelta(hours=1),
}


def bucket_moisture_points(
    points: list[MoisturePoint], range_key: str
) -> list[MoisturePoint]:
    """Downsample per-reading moisture points into fixed-width time buckets.

    Without this, a 7d window at the sensors' native ~every-10s cadence
    produces >10k points per plant per response — a few MiB of JSON and
    a chart component drowning in data. 1h responses stay raw so the
    "last hour" view keeps full resolution.
    """
    width = _MOISTURE_BUCKET_WIDTH.get(range_key)
    if width is None:
        return points
    width_s = int(width.total_seconds())
    buckets: dict[int, list[float]] = {}
    # Align each timestamp down to the nearest bucket-width boundary
    # (epoch seconds // width). Use the aligned epoch second as both
    # the dict key and the resulting point's ts.
    for p in points:
        epoch = int(p.ts.timestamp())
        aligned = (epoch // width_s) * width_s
        buckets.setdefault(aligned, []).append(p.value)
    return [
        MoisturePoint(
            ts=datetime.fromtimestamp(aligned, tz=UTC),
            value=sum(vs) / len(vs),
        )
        for aligned, vs in sorted(buckets.items())
    ]


@dataclass(frozen=True)
class PlantMoistureStatus:
    """Live moisture fields returned by ``/api/plants/{code}``."""

    current_pct: float | None
    target: tuple[float, float]
    status: BandStatus
    ts: datetime | None


@dataclass(frozen=True)
class PlantDetailPayload:
    """One-shot assembly for ``GET /api/plants/{code}``."""

    code: str
    name: str
    sticker_color: PlantSticker
    status: PlantStatus
    purple: bool
    label: str | None
    day: int
    moisture: PlantMoistureStatus
    timeline: list
    note: object  # plant_detail.PlantNote | None
    wiki_path: str


def count_irrigation_events(points: list[MoisturePoint], jump_pct: float = 5.0) -> int:
    """Heuristic: count upward jumps >= ``jump_pct`` between adjacent samples."""
    from itertools import pairwise

    n = 0
    for prev, curr in pairwise(points):
        if curr.value - prev.value >= jump_pct:
            n += 1
    return n


def _plant_readings_stmt(capability_id: int):
    return (
        select(SensorReading)
        .where(SensorReading.capability_id == capability_id)
        .where(SensorReading.metric == "soil_moisture_raw")
    )


async def _latest_moisture_pct(
    session: AsyncSession,
    plant: Plant,
    *,
    site_id: str,
    tent_id: str,
) -> tuple[float | None, datetime | None]:
    """Most recent calibrated soil moisture % for a plant's capability."""
    capability_id = plant.moisture_capability_id
    if capability_id is None:
        return None, None
    row = (
        await session.exec(
            _plant_readings_stmt(capability_id)
            .order_by(SensorReading.ts.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None, None
    cal = await get_sensor_calibration(
        session,
        metric="soil_moisture_raw",
        capability_id=row.capability_id or capability_id,
    )
    if cal is None:
        return None, row.ts
    pct = compute_calibrated_pct(row.value, cal.raw_low, cal.raw_high)
    return pct, row.ts


class PlantsService:
    """Plant CRUD + live moisture. Constructor-inject the engine + plant_detail."""

    def __init__(
        self,
        engine: AsyncEngine,
        plant_detail: PlantDetailService,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._plant_detail = plant_detail
        self._clock = clock

    def now(self) -> datetime:
        """Injected wall clock — UTC-aware.

        Exposed so API handlers can derive range cutoffs without importing
        ``datetime.now`` themselves (which would violate the
        no-concrete-clock-in-production invariant).
        """
        return self._clock()

    async def list_plants(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> list[PlantSummary]:
        """Return one PlantSummary per plant in the current scoped grow run."""
        async with AsyncSession(self._engine) as session:
            grow = await current_grow_run(session, site_id=site_id, tent_id=tent_id)
            if grow is None:
                return []

            plants = (
                await session.exec(
                    select(Plant)
                    .where(Plant.growrun_id == grow.id)
                    .order_by(Plant.code)
                )
            ).all()

            summaries: list[PlantSummary] = []
            for p in plants:
                pct, ts = await _latest_moisture_pct(
                    session, p, site_id=site_id, tent_id=tent_id
                )
                summaries.append(
                    PlantSummary(
                        code=p.code,
                        name=p.name,
                        sticker_color=p.sticker_color,
                        status=p.status,
                        purple=p.purple,
                        label=p.label,
                        moisture_pct=pct,
                        moisture_ts=ts,
                        moisture_target_low=p.moisture_target_low,
                        moisture_target_high=p.moisture_target_high,
                    )
                )
            return summaries

    async def get_plant_by_code(
        self,
        code: str,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> PlantSummary | None:
        """Return the current scoped grow-run plant whose natural-key code matches."""
        async with AsyncSession(self._engine) as session:
            grow = await current_grow_run(session, site_id=site_id, tent_id=tent_id)
            if grow is None:
                return None
            p = (
                await session.exec(
                    select(Plant)
                    .where(Plant.growrun_id == grow.id)
                    .where(Plant.code == code)
                )
            ).first()
            if p is None:
                return None
            pct, ts = await _latest_moisture_pct(
                session, p, site_id=site_id, tent_id=tent_id
            )
            return PlantSummary(
                code=p.code,
                name=p.name,
                sticker_color=p.sticker_color,
                status=p.status,
                purple=p.purple,
                label=p.label,
                moisture_pct=pct,
                moisture_ts=ts,
                moisture_target_low=p.moisture_target_low,
                moisture_target_high=p.moisture_target_high,
            )

    async def get_plant_moisture_history(
        self,
        code: str,
        cutoff: datetime,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> list[MoisturePoint]:
        """Calibrated soil-moisture % for one plant since ``cutoff``."""
        async with AsyncSession(self._engine) as session:
            grow = await current_grow_run(session, site_id=site_id, tent_id=tent_id)
            if grow is None:
                return []
            p = (
                await session.exec(
                    select(Plant)
                    .where(Plant.growrun_id == grow.id)
                    .where(Plant.code == code)
                )
            ).first()
            if p is None:
                return []
            capability_id = p.moisture_capability_id
            if capability_id is None:
                return []
            cal = await get_sensor_calibration(
                session,
                metric="soil_moisture_raw",
                capability_id=capability_id,
            )
            if cal is None:
                return []

            rows = (
                await session.exec(
                    _plant_readings_stmt(capability_id)
                    .where(SensorReading.ts >= cutoff)
                    .order_by(SensorReading.ts)
                )
            ).all()

            points: list[MoisturePoint] = []
            for r in rows:
                pct = compute_calibrated_pct(
                    r.value,
                    cal.raw_low,
                    cal.raw_high,
                )
                if pct is not None:
                    points.append(MoisturePoint(ts=r.ts, value=pct))
            return points

    async def get_plant_detail_payload(
        self,
        code: str,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> PlantDetailPayload | None:
        """Combine ``PlantSummary`` + live moisture + ``PlantDetail`` wiki parse."""
        summary = await self.get_plant_by_code(code, site_id=site_id, tent_id=tent_id)
        if summary is None:
            return None

        async with AsyncSession(self._engine) as session:
            grow = await current_grow_run(session, site_id=site_id, tent_id=tent_id)
        if grow is None or grow.germination_date is None:
            day = 0
        else:
            today_d = self._clock().astimezone(tent_tz(grow)).date()
            day = (today_d - grow.germination_date).days + 1

        moisture = PlantMoistureStatus(
            current_pct=summary.moisture_pct,
            target=(summary.moisture_target_low, summary.moisture_target_high),
            status=band_status(
                summary.moisture_pct,
                (summary.moisture_target_low, summary.moisture_target_high),
            )
            if summary.moisture_pct is not None
            else "ok",
            ts=summary.moisture_ts,
        )

        detail = self._plant_detail.get(code)
        timeline = list(detail.timeline) if detail else []
        note = detail.note if detail else None
        wiki_path = detail.wiki_path if detail else f"wiki/plants/plant-{code}.md"

        return PlantDetailPayload(
            code=summary.code,
            name=summary.name,
            sticker_color=summary.sticker_color,
            status=summary.status,
            purple=summary.purple,
            label=summary.label,
            day=day,
            moisture=moisture,
            timeline=timeline,
            note=note,
            wiki_path=wiki_path,
        )
