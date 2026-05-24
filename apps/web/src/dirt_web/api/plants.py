"""Plant endpoints — dashboard strip + drawer + moisture history.

``GET /api/plants`` lists plants for the dashboard strip with each plant's
latest calibrated moisture. ``GET /api/plants/{plant_id}`` returns the full
drawer payload (header + moisture status + timeline + note + wiki_path).
``GET /api/plants/{plant_id}/moisture`` returns bucketed moisture points
over a requested range plus an irrigation-event count heuristic.
All three are thin FastAPI wrappers around ``PlantsService`` +
``PlantDetailService``; payload construction targets the Milestone 3
contract shape.
"""

from __future__ import annotations

import asyncio

from dirt_contracts.webapp_v1.models import (
    BandStatus as ContractBandStatus,
)
from dirt_contracts.webapp_v1.models import (
    HistoryPoint,
    Plant,
    PlantDetail,
    PlantMoistureCurrent,
    PlantMoistureHistory,
    PlantNote,
    PlantsResponse,
    PlantStatus,
    Range,
    TargetBand,
    TimelineEntry,
)
from fastapi import APIRouter, Depends, HTTPException, Query

from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.plants import (
    PlantDetailPayload,
    PlantsService,
    PlantSummary,
    bucket_moisture_points,
    count_irrigation_events,
)
from dirt_shared.services.readings import RANGE_DELTAS
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID
from dirt_web.deps import get_grow, get_plants

router = APIRouter(tags=["plants"])


def _sticker_color_value(s: PlantSummary | PlantDetailPayload) -> str | None:
    return None if s.sticker_color is None else s.sticker_color.value


def _plant_from_summary(s: PlantSummary) -> Plant:
    return Plant(
        plant_id=s.plant_id,
        name=s.name,
        sticker_color=_sticker_color_value(s),
        status=PlantStatus(s.status.value),
        purple=s.purple,
        moisture_pct=s.moisture_pct,
        moisture_ts=s.moisture_ts,
    )


@router.get("/api/plants", response_model=PlantsResponse)
async def plants_list(
    site_id: str = Query(DEFAULT_SITE_ID),
    tent_id: str = Query(DEFAULT_TENT_ID),
    plants: PlantsService = Depends(get_plants),
    grow: GrowStateService = Depends(get_grow),
) -> PlantsResponse:
    """Dashboard plants strip with latest calibrated moisture."""
    summaries = await plants.list_plants(site_id=site_id, tent_id=tent_id)
    payload = await grow.get_grow_current_payload(site_id=site_id, tent_id=tent_id)
    return PlantsResponse(
        day=payload.day_number,
        plants=[_plant_from_summary(s) for s in summaries],
    )


def _moisture_envelope(detail: PlantDetailPayload) -> PlantMoistureCurrent:
    m = detail.moisture
    return PlantMoistureCurrent(
        current_pct=m.current_pct,
        target=TargetBand(root=[m.target[0], m.target[1]]),
        status=ContractBandStatus(m.status),
        ts=m.ts,
    )


def _timeline_entries(detail: PlantDetailPayload) -> list[TimelineEntry]:
    """Keep only entries the contract can validate (date + day >= 1 + text)."""
    out: list[TimelineEntry] = []
    for t in detail.timeline:
        if t.date is None or t.day is None or t.day < 1:
            continue
        out.append(
            TimelineEntry(date=t.date, day=t.day, text=t.text, highlight=t.highlight)
        )
    return out


def _note(detail: PlantDetailPayload) -> PlantNote | None:
    # The wiki parse may find a note paragraph but no ``updated`` frontmatter;
    # the contract requires ``updated`` on a non-null note, so drop noteless
    # pages rather than synthesizing a date.
    if detail.note is None or detail.note.updated is None:
        return None
    return PlantNote(text=detail.note.text, updated=detail.note.updated)


@router.get("/api/plants/{plant_id}", response_model=PlantDetail)
async def plants_detail(
    plant_id: str,
    site_id: str = Query(DEFAULT_SITE_ID),
    tent_id: str = Query(DEFAULT_TENT_ID),
    plants: PlantsService = Depends(get_plants),
) -> PlantDetail:
    """Plant-detail drawer payload — header + moisture + timeline + note."""
    detail = await plants.get_plant_detail_payload(
        plant_id, site_id=site_id, tent_id=tent_id
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="unknown plant")
    return PlantDetail(
        plant_id=detail.plant_id,
        name=detail.name,
        sticker_color=_sticker_color_value(detail),
        status=PlantStatus(detail.status.value),
        purple=detail.purple,
        day=max(detail.day, 1),
        moisture=_moisture_envelope(detail),
        timeline=_timeline_entries(detail),
        note=_note(detail),
        wiki_path=detail.wiki_path,
    )


@router.get("/api/plants/{plant_id}/moisture", response_model=PlantMoistureHistory)
async def plants_moisture(
    plant_id: str,
    range: Range = Query(...),
    site_id: str = Query(DEFAULT_SITE_ID),
    tent_id: str = Query(DEFAULT_TENT_ID),
    plants: PlantsService = Depends(get_plants),
) -> PlantMoistureHistory:
    """Bucketed soil-moisture points + irrigation-events-in-24h heuristic."""
    # The irrigation-event badge is always over the last 24h regardless of
    # the requested sparkline range, so the drawer reads the same across
    # range toggles. When the requested range covers 24h, reuse those
    # points; otherwise fetch the 24h series in parallel with the summary.
    now = plants.now()
    cutoff = now - RANGE_DELTAS[range.value]
    day_cutoff = now - RANGE_DELTAS["24h"]
    needs_separate_day_query = cutoff > day_cutoff

    summary_task = plants.get_plant_by_id(plant_id, site_id=site_id, tent_id=tent_id)
    points_task = plants.get_plant_moisture_history(
        plant_id, cutoff, site_id=site_id, tent_id=tent_id
    )
    if needs_separate_day_query:
        day_task = plants.get_plant_moisture_history(
            plant_id, day_cutoff, site_id=site_id, tent_id=tent_id
        )
        summary, points, day_points = await asyncio.gather(
            summary_task, points_task, day_task
        )
    else:
        summary, points = await asyncio.gather(summary_task, points_task)
        day_points = [p for p in points if p.ts >= day_cutoff]

    if summary is None:
        raise HTTPException(status_code=404, detail="unknown plant")
    # Irrigation-event detection needs raw transitions; bucket only the
    # chart points. At ~every-10s sensor cadence, 7d raw is 10k+ points
    # per plant — a multi-MiB response and unreadable chart. 5-min and
    # 1h buckets match /api/sensors/history's resolution per range.
    events_24h = count_irrigation_events(day_points)
    bucketed = bucket_moisture_points(points, range.value)

    return PlantMoistureHistory(
        plant_id=summary.plant_id,
        range=range,
        unit="%",
        target=TargetBand(
            root=[summary.moisture_target_low, summary.moisture_target_high]
        ),
        points=[HistoryPoint(ts=p.ts, value=round(p.value, 2)) for p in bucketed],
        irrigation_events_24h=events_24h,
    )
