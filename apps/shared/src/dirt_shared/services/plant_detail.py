"""Parse ``wiki/plants/plant-{code}.md`` into structured fields for the drawer.

The plant-detail drawer in the SPA (see API.md §5 and mockup
``plant_detail.jsx``) needs a ``timeline`` list plus a ``note`` blurb.
Those live as markdown sections inside the per-plant wiki file.

Parsing is narrow + pragmatic. The wiki is agent-authored and follows a
consistent structure:

- ``## Current State`` — first paragraph → the note.
- ``## Timeline`` — the immediately-following bullet list → timeline[].

Cached by file mtime so consecutive reads (dashboard + drawer both hitting
``/api/plants/{code}``) don't re-parse. The cache lives on the
``PlantDetailService`` instance — per-app, not per-process — so tests
that construct a fresh service get a clean cache.
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


_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")

# "2026-03-27 — [Day 13: Pre-transplant; …](../daily/2026-03-27.md)"
_TIMELINE_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s*[—\-]\s*(?:\[)?(?:Day\s+(\d+)\s*[:—]\s*)?(.+?)(?:\]\(.+?\))?\s*$",
    re.IGNORECASE,
)


class PlantDetailService:
    """Parses + caches per-plant wiki files. Constructor-inject the wiki dir.

    Cache lives on the instance so tests get a fresh cache per service.
    Wired into ``app.state.plant_detail`` by ``create_app``.
    """

    def __init__(self, wiki_dir: Path = WIKI_DIR) -> None:
        self._wiki_dir = wiki_dir
        self._cache: dict[str, tuple[float, PlantDetail]] = {}

    def _plant_path(self, code: str) -> Path:
        return self._wiki_dir / "plants" / f"plant-{code}.md"

    def get(self, code: str) -> PlantDetail | None:
        """Parse + cache the plant wiki file. Returns None if missing."""
        path = self._plant_path(code)
        if not path.exists():
            return None
        mtime = path.stat().st_mtime
        cached = self._cache.get(code)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        detail = self._parse(code, path)
        self._cache[code] = (mtime, detail)
        return detail

    def _parse(self, code: str, path: Path) -> PlantDetail:
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
    """Group body lines by their preceding ``## <name>`` heading."""
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
    """Parse the bullet list under ``## Timeline``."""
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
                TimelineEntry(
                    date=None, day=None, text=inner, highlight="**" in inner,
                )
            )
    return entries


def _parse_note(
    sections: dict[str, list[str]], updated_fm: object
) -> PlantNote | None:
    """Return the first paragraph under ``## Current State`` as the drawer note."""
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
