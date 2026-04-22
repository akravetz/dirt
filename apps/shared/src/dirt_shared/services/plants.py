"""Plant CRUD + live moisture join.

Backs ``GET /api/plants`` (summary of all plants for the dashboard strip)
and the DB-side fields of ``GET /api/plants/{code}`` (drawer header +
live moisture). The narrative parts of the drawer come from
``PlantDetailService``, which parses the plant's wiki markdown.

Moisture is computed by joining the latest ``soil_moisture_raw`` reading
with the per-plant ``sensorcalibration`` row and running the value
through :func:`compute_calibrated_pct`. Plants without a calibration
return ``moisture_pct=None``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import PlantStatus, PlantSticker
from dirt_shared.models.grow_state import GrowState
from dirt_shared.models.plant import Plant
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.grow_state import TENT_TZ, BandStatus, band_status
from dirt_shared.services.plant_detail import PlantDetailService
from dirt_shared.services.readings import compute_calibrated_pct


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


async def _latest_moisture_pct(
    session: AsyncSession, sensornode_id: int
) -> tuple[float | None, datetime | None]:
    """Most recent calibrated soil moisture % for a plant's node."""
    row = (
        await session.exec(
            select(SensorReading)
            .where(SensorReading.sensornode_id == sensornode_id)
            .where(SensorReading.metric == "soil_moisture_raw")
            .order_by(SensorReading.ts.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None, None
    cal = (
        await session.exec(
            select(SensorCalibration)
            .where(SensorCalibration.sensornode_id == sensornode_id)
            .where(SensorCalibration.metric == "soil_moisture_raw")
        )
    ).first()
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

    async def list_plants(self) -> list[PlantSummary]:
        """Return one PlantSummary per plant in the current grow."""
        async with AsyncSession(self._engine) as session:
            gs = (
                await session.exec(
                    select(GrowState).where(GrowState.is_current.is_(True))
                )
            ).first()
            if gs is None:
                return []

            plants = (
                await session.exec(
                    select(Plant)
                    .where(Plant.growstate_id == gs.id)
                    .order_by(Plant.code)
                )
            ).all()

            summaries: list[PlantSummary] = []
            for p in plants:
                pct, ts = await _latest_moisture_pct(session, p.sensornode_id)
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

    async def get_plant_by_code(self, code: str) -> PlantSummary | None:
        """Return the current-grow plant whose natural-key code matches."""
        async with AsyncSession(self._engine) as session:
            gs = (
                await session.exec(
                    select(GrowState).where(GrowState.is_current.is_(True))
                )
            ).first()
            if gs is None:
                return None
            p = (
                await session.exec(
                    select(Plant)
                    .where(Plant.growstate_id == gs.id)
                    .where(Plant.code == code)
                )
            ).first()
            if p is None:
                return None
            pct, ts = await _latest_moisture_pct(session, p.sensornode_id)
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
        self, code: str, cutoff: datetime
    ) -> list[MoisturePoint]:
        """Calibrated soil-moisture % for one plant since ``cutoff``."""
        async with AsyncSession(self._engine) as session:
            gs = (
                await session.exec(
                    select(GrowState).where(GrowState.is_current.is_(True))
                )
            ).first()
            if gs is None:
                return []
            p = (
                await session.exec(
                    select(Plant)
                    .where(Plant.growstate_id == gs.id)
                    .where(Plant.code == code)
                )
            ).first()
            if p is None:
                return []
            cal = (
                await session.exec(
                    select(SensorCalibration)
                    .where(SensorCalibration.sensornode_id == p.sensornode_id)
                    .where(SensorCalibration.metric == "soil_moisture_raw")
                )
            ).first()
            if cal is None:
                return []

            rows = (
                await session.exec(
                    select(SensorReading)
                    .where(SensorReading.sensornode_id == p.sensornode_id)
                    .where(SensorReading.metric == "soil_moisture_raw")
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

    async def get_plant_detail_payload(self, code: str) -> PlantDetailPayload | None:
        """Combine ``PlantSummary`` + live moisture + ``PlantDetail`` wiki parse."""
        summary = await self.get_plant_by_code(code)
        if summary is None:
            return None

        today_d = self._clock().astimezone(TENT_TZ).date()

        async with AsyncSession(self._engine) as session:
            gs = (
                await session.exec(
                    select(GrowState).where(GrowState.is_current.is_(True))
                )
            ).first()
        day = 0 if gs is None else (today_d - gs.germination_date).days + 1

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
