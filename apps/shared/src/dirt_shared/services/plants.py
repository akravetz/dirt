"""Plant CRUD + live moisture join.

Backs ``GET /api/plants`` (summary of all plants for the dashboard strip)
and the DB-side fields of ``GET /api/plants/{code}`` (drawer header +
live moisture). The narrative parts of the drawer — vitals table,
timeline entries, the closing note — come from
:mod:`dirt_shared.services.plant_detail`, which parses the plant's
wiki markdown.

Moisture is computed by joining the latest ``soil_moisture_raw`` reading
with the per-plant ``sensorcalibration`` row and running the value
through :func:`compute_calibrated_pct`. Plants without a calibration
(raw_low == raw_high — seen a single value) return ``moisture_pct=None``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.db import engine
from dirt_shared.models.enums import PlantStatus, PlantSticker
from dirt_shared.models.grow_state import GrowState
from dirt_shared.models.plant import Plant
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.grow_state import grow_week  # noqa: F401 (re-exported)
from dirt_shared.services.readings import compute_calibrated_pct


@dataclass(frozen=True)
class PlantSummary:
    """One row in ``GET /api/plants``."""

    id: int
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


async def list_plants() -> list[PlantSummary]:
    """Return one PlantSummary per plant in the current grow, with live moisture."""
    async with AsyncSession(engine) as session:
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
                    id=p.id,
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


async def get_plant_by_code(code: str) -> PlantSummary | None:
    """Return the current-grow plant whose natural-key code matches.

    ``code`` is the stable 'a'/'b'/'c'/'d' letter; for the SPA plant-detail
    drawer we identify plants by code, not by surrogate id, because the
    codes are stable across grows (the id changes when a new grow is flipped
    in — see ``growstate.is_current``).
    """
    async with AsyncSession(engine) as session:
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
            id=p.id,
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


@dataclass(frozen=True)
class MoisturePoint:
    ts: datetime
    value: float


async def get_plant_moisture_history(
    code: str, cutoff: datetime
) -> list[MoisturePoint]:
    """Calibrated soil-moisture % for one plant since ``cutoff``.

    Raw readings come from ``sensorreading``; each is converted via the
    plant's calibration row. Plants without calibration return an empty
    list (can't compute %).
    """
    async with AsyncSession(engine) as session:
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
            pct = compute_calibrated_pct(r.value, cal.raw_low, cal.raw_high)
            if pct is not None:
                points.append(MoisturePoint(ts=r.ts, value=pct))
        return points


def count_irrigation_events(points: list[MoisturePoint], jump_pct: float = 5.0) -> int:
    """Heuristic: count upward jumps >= ``jump_pct`` between adjacent samples.

    Autopot watering cycles look like a sharp rise in moisture followed by a
    slow dry-down. Counting jumps-up gives an approximate irrigation event
    count without parsing pump actuation logs (which we don't have yet).
    """
    n = 0
    for prev, curr in zip(points, points[1:]):
        if curr.value - prev.value >= jump_pct:
            n += 1
    return n


async def _latest_moisture_pct(
    session: AsyncSession, sensornode_id: int
) -> tuple[float | None, datetime | None]:
    """Most recent calibrated soil moisture % for a plant's node. ``(pct, ts)``.

    Returns (None, None) if no reading yet, or (None, ts) if we have a reading
    but no usable calibration (degenerate raw_low == raw_high).
    """
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
