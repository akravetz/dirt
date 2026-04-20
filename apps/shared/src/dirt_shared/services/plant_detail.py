"""Parse ``wiki/plants/plant-{code}.md`` into structured fields for the drawer.

The plant-detail drawer in the SPA (see API.md §5 and mockup
``plant_detail.jsx``) needs a ``timeline`` list plus a ``note`` blurb.
Those live as markdown sections inside the per-plant wiki file — the
agent writes them every daily-report cycle.

Parsing is narrow + pragmatic. The wiki is agent-authored and follows a
consistent structure — we don't need a full markdown AST:

- ``## Current State`` — first paragraph → the note.
- ``## Timeline`` — the immediately-following bullet list → timeline[].

The result is cached by file mtime so consecutive reads (e.g., dashboard
+ drawer both hitting ``/api/plants/{code}``) don't re-parse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dirt_shared.services.wiki import WIKI_DIR, _parse_frontmatter


@dataclass(frozen=True)
class TimelineEntry:
    date: date | None
    day: int | None
    text: str
    highlight: bool


@dataclass(frozen=True)
class PlantNote:
    text: str
    updated: date | None


@dataclass(frozen=True)
class PlantDetail:
    code: str
    wiki_path: str
    frontmatter: dict[str, object]
    timeline: list[TimelineEntry]
    note: PlantNote | None


# ============================================================
# mtime-keyed cache
# ============================================================

_cache: dict[str, tuple[float, PlantDetail]] = {}


def _plant_path(code: str) -> Path:
    return WIKI_DIR / "plants" / f"plant-{code}.md"


def get_plant_detail(code: str) -> PlantDetail | None:
    """Parse and cache the plant wiki file. Returns None if missing."""
    path = _plant_path(code)
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    cached = _cache.get(code)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    detail = _parse(code, path)
    _cache[code] = (mtime, detail)
    return detail


# ============================================================
# Parsing
# ============================================================

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")

# "2026-03-27 — [Day 13: Pre-transplant; …](../daily/2026-03-27.md)"
# date ISO, then em-dash (— or --), then optional markdown-linked day text.
_TIMELINE_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s*[—\-]\s*(?:\[)?(?:Day\s+(\d+)\s*[:—]\s*)?(.+?)(?:\]\(.+?\))?\s*$",
    re.IGNORECASE,
)


def _parse(code: str, path: Path) -> PlantDetail:
    raw = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(raw)

    sections = _split_h2_sections(body)
    timeline = _parse_timeline(sections.get("timeline", []))
    note = _parse_note(sections, fm.get("updated"))

    return PlantDetail(
        code=code,
        wiki_path=f"wiki/plants/{path.name}",
        frontmatter=fm,
        timeline=timeline,
        note=note,
    )


def _split_h2_sections(body: str) -> dict[str, list[str]]:
    """Group body lines by their preceding ``## <name>`` heading.

    Returns a dict mapping lowercased heading text → list of lines under it
    (not including the heading). H1 + pre-H2 prelude go under the empty-string
    key so callers can still scan it.
    """
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for line in body.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            current = m.group(1).strip().lower()
            sections.setdefault(current, [])
        else:
            sections[current].append(line)
    return sections


def _parse_timeline(lines: list[str]) -> list[TimelineEntry]:
    """Parse the bullet list under ``## Timeline``.

    Each bullet is expected to start with ``2026-MM-DD — [Day N: text]...``.
    Entries that don't match the pattern are still included as raw text so
    the drawer shows them; ``date`` + ``day`` default to None.
    """
    entries: list[TimelineEntry] = []
    for line in lines:
        stripped = line.strip()
        b = _BULLET_RE.match(stripped)
        if not b:
            continue
        inner = b.group(1).strip()
        m = _TIMELINE_LINE_RE.match(inner)
        if m:
            try:
                d = date.fromisoformat(m.group(1))
            except ValueError:
                d = None
            day_s = m.group(2)
            day = int(day_s) if day_s and day_s.isdigit() else None
            text = m.group(3).strip().rstrip("]").rstrip(")")
            highlight = "**" in inner
            entries.append(
                TimelineEntry(date=d, day=day, text=text, highlight=highlight)
            )
        else:
            entries.append(
                TimelineEntry(date=None, day=None, text=inner, highlight="**" in inner)
            )
    return entries


def _parse_note(
    sections: dict[str, list[str]], updated_fm: object
) -> PlantNote | None:
    """Return the first paragraph under ``## Current State`` as the drawer note.

    The wiki convention (plant-a.md through plant-d.md) is a prose paragraph
    summarising today's state immediately after the Current State heading.
    An earlier iteration of this parser preferred a trailing `> ...` block
    quote, but the wiki doesn't use that convention — dropped to keep the
    code matching reality.
    """
    cs = sections.get("current state", [])
    paragraph_lines: list[str] = []
    for line in cs:
        if line.strip() == "" and paragraph_lines:
            break
        if line.strip():
            paragraph_lines.append(line.strip())
    if paragraph_lines:
        return PlantNote(
            text=" ".join(paragraph_lines),
            updated=_as_date(updated_fm),
        )
    return None


def _as_date(val: object) -> date | None:
    if isinstance(val, str):
        try:
            return date.fromisoformat(val)
        except ValueError:
            return None
    return None
