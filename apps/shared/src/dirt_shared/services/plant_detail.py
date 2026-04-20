"""Parse ``wiki/plants/plant-{code}.md`` into structured fields for the drawer.

The plant-detail drawer in the SPA (see ``API.md`` §5 and mockup
``plant_detail.jsx``) needs structured ``vitals``, ``timeline``, and
``note`` fields. Those live as markdown sections inside the per-plant
wiki file — the agent writes them every daily-report cycle.

Parsing is narrow + pragmatic. The wiki is agent-authored and follows a
consistent structure — we don't need a full markdown AST, just regex
matchers for the sections we care about:

- ``## Current State`` — first paragraph → the note.
- ``## Vitals (live)`` — the immediately-following table → vitals[].
- ``## Timeline`` — the immediately-following bullet list → timeline[].

The result is cached by file mtime so consecutive reads (e.g., the SPA's
dashboard + drawer both hitting ``/api/plants/{code}``) don't re-parse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dirt_shared.services.wiki import WIKI_DIR, _parse_frontmatter


@dataclass(frozen=True)
class VitalRow:
    label: str
    value: str
    target: str
    status: str  # "ok" | "warn" | "crit" | "" when unknown


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
    vitals: list[VitalRow]
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
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")

# "2026-03-27 — [Day 13: Pre-transplant; …](../daily/2026-03-27.md)"
# date ISO, then em-dash (— or --), then optional markdown-linked day text.
_TIMELINE_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s*[—\-]\s*(?:\[)?(?:Day\s+(\d+)\s*[:—]\s*)?(.+?)(?:\]\(.+?\))?\s*$",
    re.IGNORECASE,
)

# Table target column value like "55–70" or "5.5-6.0" — not strictly validated.
# Status column emoji / text normalisation.
_STATUS_MAP = {
    "✓": "ok",
    "✅": "ok",
    "ok": "ok",
    "⚠": "warn",
    "⚠️": "warn",
    "warn": "warn",
    "❌": "crit",
    "crit": "crit",
    "⌀": "",  # wiki uses ⌀ for "n/a"
}


def _parse(code: str, path: Path) -> PlantDetail:
    raw = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(raw)

    sections = _split_h2_sections(body)
    vitals = _parse_vitals(sections.get("vitals (live)", [])) or _parse_vitals(
        sections.get("vitals", [])
    )
    timeline = _parse_timeline(sections.get("timeline", []))
    note = _parse_note(sections, fm.get("updated"))

    return PlantDetail(
        code=code,
        wiki_path=f"wiki/plants/{path.name}",
        frontmatter=fm,
        vitals=vitals,
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


def _parse_vitals(lines: list[str]) -> list[VitalRow]:
    """Parse the first markdown table found after ``## Vitals``.

    Table shape expected (per the wiki plant-a.md convention):
      | Metric | Value | Target | Status |
      |--------|-------|--------|--------|
      | Soil moisture | 62 % | 55–70 | ✓ OK |
      ...
    """
    rows: list[list[str]] = []
    for line in lines:
        m = _TABLE_ROW_RE.match(line.strip())
        if m:
            cells = [c.strip() for c in m.group(1).split("|")]
            # Skip the separator row ("|---|---|")
            if all(set(c) <= {"-", ":", " "} for c in cells if c):
                continue
            rows.append(cells)
        elif rows:
            # End of table — stop.
            break
    if len(rows) < 2:
        return []
    header = [c.lower() for c in rows[0]]
    try:
        i_label = next(i for i, h in enumerate(header) if "metric" in h or "label" in h)
    except StopIteration:
        i_label = 0
    i_value = _col_index(header, ("value",)) or 1
    i_target = _col_index(header, ("target", "range")) or 2
    i_status = _col_index(header, ("status",))

    out: list[VitalRow] = []
    for row in rows[1:]:
        if not any(row):
            continue
        label = row[i_label] if i_label < len(row) else ""
        value = row[i_value] if i_value < len(row) else ""
        target = row[i_target] if i_target < len(row) else ""
        raw_status = (row[i_status] if i_status is not None and i_status < len(row) else "")
        status = _normalise_status(raw_status)
        out.append(
            VitalRow(label=label, value=value, target=target, status=status)
        )
    return out


def _col_index(header: list[str], keywords: tuple[str, ...]) -> int | None:
    for i, h in enumerate(header):
        for kw in keywords:
            if kw in h:
                return i
    return None


def _normalise_status(raw: str) -> str:
    """Map ``✓ OK`` / ``⚠ warn`` / ``✅ Topped`` → a short enum-ish string."""
    raw = raw.strip()
    if not raw:
        return ""
    # Direct symbol / word hit — cheapest case first.
    first = raw.split()[0] if raw else ""
    if first in _STATUS_MAP:
        return _STATUS_MAP[first]
    lowered = raw.lower()
    for key, val in _STATUS_MAP.items():
        if key in lowered:
            return val
    return ""  # unknown — let the UI default to neutral styling


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
    """Pick a 'current status' note. Prefers a block quote at the end of the
    body; falls back to the first paragraph of ``## Current State``."""
    # Try the end of the body first — the convention in plant-a.md is a
    # block quote after the last H2.
    full_body_lines: list[str] = []
    for name, lines in sections.items():
        full_body_lines.extend(lines)
    for line in reversed(full_body_lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            return PlantNote(
                text=stripped.lstrip("> ").strip(),
                updated=_as_date(updated_fm),
            )
        break  # the last non-empty line isn't a quote; skip the quote path

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
