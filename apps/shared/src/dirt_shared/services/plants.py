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
from dirt_shared.services.grow_state import BandStatus, band_status
from dirt_shared.services.plant_detail import PlantDetail, get_plant_detail
from dirt_shared.services.readings import compute_calibrated_pct


@dataclass(frozen=True)
class PlantSummary:
    """One row in ``GET /api/plants``.

    ``code`` (the 'a'/'b'/'c'/'d' letter) is the plant's identity on the
    wire — API responses serialize it as the ``id`` field. The surrogate
    ``plant.id`` bigint is DB-internal only and deliberately absent here
    to prevent the endpoint layer from accidentally exposing it.
    """

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


@dataclass(frozen=True)
class PlantMoistureStatus:
    """Live moisture fields returned by ``/api/plants/{code}``."""

    current_pct: float | None
    target: tuple[float, float]
    status: BandStatus
    ts: datetime | None


@dataclass(frozen=True)
class PlantDetailPayload:
    """One-shot assembly for ``GET /api/plants/{code}`` — DB-live fields
    (summary + moisture status) merged with wiki-parsed fields
    (timeline + note). The endpoint layer just has to JSON-serialize.

    ``wiki_path`` comes from the wiki parse and is always present even if
    the wiki file is missing (it's the expected path, not a guarantee
    that the file exists).
    """

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


async def get_plant_detail_payload(
    code: str, today: object = None
) -> PlantDetailPayload | None:
    """Combine ``PlantSummary`` + live moisture + ``PlantDetail`` wiki parse.

    Returns None if the plant code doesn't exist in the current grow.
    Missing wiki file is tolerated — ``timeline=[]``, ``note=None``, but
    ``wiki_path`` still points at the expected location.

    ``today`` defaults to ``date.today()`` in the local tent TZ — same
    convention as ``grow_state.get_grow_current_payload`` so ``day``
    numbers are consistent across endpoints. Accepts either ``date`` or
    ``datetime``; tests typically pin a ``date``.
    """
    from datetime import date as _date, datetime as _dt

    summary = await get_plant_by_code(code)
    if summary is None:
        return None

    # Normalize `today` → local-tent `date`, matching GrowCurrentPayload.
    if today is None:
        today_d = _date.today()
    elif isinstance(today, _dt):
        today_d = today.date()
    else:
        today_d = today

    async with AsyncSession(engine) as session:
        gs = (
            await session.exec(
                select(GrowState).where(GrowState.is_current.is_(True))
            )
        ).first()
    if gs is None:
        day = 0
    else:
        day = (today_d - gs.germination_date).days + 1

    moisture = PlantMoistureStatus(
        current_pct=summary.moisture_pct,
        target=(summary.moisture_target_low, summary.moisture_target_high),
        status=band_status(
            summary.moisture_pct,
            (summary.moisture_target_low, summary.moisture_target_high),
        ) if summary.moisture_pct is not None else "ok",
        ts=summary.moisture_ts,
    )

    detail = get_plant_detail(code)
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
