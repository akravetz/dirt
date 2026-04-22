"""Plant endpoints — dashboard strip + drawer + moisture history.

``GET /api/plants`` lists A–D for the dashboard strip with each plant's
latest calibrated moisture. ``GET /api/plants/{code}`` returns the full
drawer payload (header + moisture status + timeline + note + wiki_path).
Both endpoints are thin FastAPI wrappers around ``PlantsService`` +
``PlantDetailService``; payload shapes already match the contract.
"""

from __future__ import annotations

from dirt_contracts.webapp_v1.models import (
    BandStatus as ContractBandStatus,
)
from dirt_contracts.webapp_v1.models import (
    Plant,
    PlantCode,
    PlantDetail,
    PlantMoistureCurrent,
    PlantNote,
    PlantsResponse,
    PlantStatus,
    PlantStickerColor,
    TargetBand,
    TimelineEntry,
)
from fastapi import APIRouter, Depends, HTTPException

from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.plants import (
    PlantDetailPayload,
    PlantsService,
    PlantSummary,
)
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
    plants: PlantsService = Depends(get_plants),
    grow: GrowStateService = Depends(get_grow),
) -> PlantsResponse:
    """Dashboard plants strip: A–D with latest calibrated moisture."""
    summaries = await plants.list_plants()
    payload = await grow.get_grow_current_payload()
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
