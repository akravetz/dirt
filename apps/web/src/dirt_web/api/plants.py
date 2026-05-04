"""Plant endpoints — dashboard strip + drawer + moisture history.

``GET /api/plants`` lists A–D for the dashboard strip with each plant's
latest calibrated moisture. ``GET /api/plants/{code}`` returns the full
drawer payload (header + moisture status + timeline + note + wiki_path).
``GET /api/plants/{code}/moisture`` returns bucketed moisture points
over a requested range plus an irrigation-event count heuristic.
All three are thin FastAPI wrappers around ``PlantsService`` +
``PlantDetailService``; payload shapes already match the contract.
"""

from __future__ import annotations

import asyncio

from dirt_contracts.webapp_v1.models import (
    BandStatus as ContractBandStatus,
)
from dirt_contracts.webapp_v1.models import (
    HistoryPoint,
    Plant,
    PlantCode,
    PlantDetail,
    PlantMoistureCurrent,
    PlantMoistureHistory,
    PlantNote,
    PlantsResponse,
    PlantStatus,
    PlantStickerColor,
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


def _parse_code(code: str) -> PlantCode:
    """Validate ``{code}`` path param against the contract enum; 404 otherwise."""
    try:
        return PlantCode(code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="unknown plant") from exc


def _plant_from_summary(s: PlantSummary) -> Plant:
    return Plant(
        code=PlantCode(s.code),
        name=s.name,
        sticker_color=PlantStickerColor(s.sticker_color.value),
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
    """Dashboard plants strip: A–D with latest calibrated moisture."""
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


@router.get("/api/plants/{code}", response_model=PlantDetail)
async def plants_detail(
    code: str,
    plants: PlantsService = Depends(get_plants),
) -> PlantDetail:
    """Plant-detail drawer payload — header + moisture + timeline + note."""
    parsed = _parse_code(code)
    detail = await plants.get_plant_detail_payload(parsed.value)
    if detail is None:
        raise HTTPException(status_code=404, detail="unknown plant")
    return PlantDetail(
        code=parsed,
        name=detail.name,
        sticker_color=PlantStickerColor(detail.sticker_color.value),
        status=PlantStatus(detail.status.value),
        purple=detail.purple,
        day=max(detail.day, 1),
        label=detail.label or "",
        moisture=_moisture_envelope(detail),
        timeline=_timeline_entries(detail),
        note=_note(detail),
        wiki_path=detail.wiki_path,
    )


@router.get("/api/plants/{code}/moisture", response_model=PlantMoistureHistory)
async def plants_moisture(
    code: str,
    range: Range = Query(...),
    plants: PlantsService = Depends(get_plants),
) -> PlantMoistureHistory:
    """Bucketed soil-moisture points + irrigation-events-in-24h heuristic."""
    parsed = _parse_code(code)

    # The irrigation-event badge is always over the last 24h regardless of
    # the requested sparkline range, so the drawer reads the same across
    # range toggles. When the requested range covers 24h, reuse those
    # points; otherwise fetch the 24h series in parallel with the summary.
    now = plants.now()
    cutoff = now - RANGE_DELTAS[range.value]
    day_cutoff = now - RANGE_DELTAS["24h"]
    needs_separate_day_query = cutoff > day_cutoff

    summary_task = plants.get_plant_by_code(parsed.value)
    points_task = plants.get_plant_moisture_history(parsed.value, cutoff)
    if needs_separate_day_query:
        day_task = plants.get_plant_moisture_history(parsed.value, day_cutoff)
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
        code=parsed,
        range=range,
        unit="%",
        target=TargetBand(
            root=[summary.moisture_target_low, summary.moisture_target_high]
        ),
        points=[HistoryPoint(ts=p.ts, value=round(p.value, 2)) for p in bucketed],
        irrigation_events_24h=events_24h,
    )
