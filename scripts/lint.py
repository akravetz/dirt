#!/usr/bin/env python3
"""Grow wiki health checker.

Usage:
    uv run scripts/lint.py

Runs 6 deterministic checks and exits 0 (all pass) or 1 (any failures).
"""

import re
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

REPO = Path(__file__).parent.parent
WIKI = REPO / "wiki"
RAW_PHOTOS = REPO / "raw" / "photos"

EXIF_TAG_DATETIME_ORIGINAL = 36867


# ─── helpers ──────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict | None:
    """Return dict of frontmatter fields, or None if missing/malformed."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end].strip()
    result = {}
    for line in block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


def extract_md_links(text: str) -> list[str]:
    """Return all link targets from [text](target) markdown syntax."""
    return re.findall(r"\[(?:[^\]]*)\]\(([^)]+)\)", text)


def get_exif_date(path: Path) -> str | None:
    """Return YYYY-MM-DD from EXIF DateTimeOriginal (tag 36867), or None."""
    try:
        with Image.open(path) as img:
            exif_data = img._getexif()
    except Exception:
        return None
    if not exif_data:
        return None
    raw = exif_data.get(EXIF_TAG_DATETIME_ORIGINAL)
    if not raw:
        return None
    try:
        date_part, _ = raw.split(" ", 1)
        return date_part.replace(":", "-")
    except ValueError:
        return None


# ─── check 1: index sync ──────────────────────────────────────────────────────

def check_index_sync() -> list[str]:
    """Parse index.md links vs actual wiki files."""
    issues = []
    index_path = WIKI / "index.md"

    if not index_path.exists():
        return ["wiki/index.md does not exist"]

    text = index_path.read_text()
    links = extract_md_links(text)

    # Normalise links: strip anchors, resolve relative to wiki/
    indexed: set[str] = set()
    for link in links:
        target = link.split("#")[0].strip()
        if not target or target.startswith("http"):
            continue
        # Links in index.md are relative to wiki/
        resolved = (WIKI / target).resolve()
        try:
            indexed.add(resolved.relative_to(WIKI.resolve()).as_posix())
        except ValueError:
            pass  # link points outside wiki/

    # All content .md files in wiki/ — skip meta files (index.md is the
    # catalog itself; CLAUDE.md is the operating manual; log.md is an
    # append-only activity log, skipped here too for consistency).
    META_FILES = {"index.md", "CLAUDE.md", "log.md"}
    all_wiki: set[str] = {
        p.resolve().relative_to(WIKI.resolve()).as_posix()
        for p in WIKI.rglob("*.md")
        if p.name not in META_FILES
    }

    for path_str in sorted(all_wiki - indexed):
        issues.append(f"  Not in index.md: wiki/{path_str}")

    for path_str in sorted(indexed - all_wiki):
        if path_str in META_FILES:
            continue
        issues.append(f"  index.md links to nonexistent file: wiki/{path_str}")

    return issues


# ─── check 2: backlink checker ────────────────────────────────────────────────

def check_backlinks() -> list[str]:
    """Dailies mentioning plants must be linked from plant timelines."""
    issues = []

    plants_dir = WIKI / "plants"
    daily_dir = WIKI / "daily"

    plant_files = list(plants_dir.glob("*.md")) if plants_dir.exists() else []
    daily_files = list(daily_dir.glob("*.md")) if daily_dir.exists() else []

    # For each plant file, extract dates in its Timeline section
    plant_timeline_dates: dict[str, set[str]] = {}

    for pf in plant_files:
        text = pf.read_text()
        linked_dates: set[str] = set()
        in_timeline = False
        for line in text.splitlines():
            if re.match(r"^#+\s+Timeline", line, re.IGNORECASE):
                in_timeline = True
                continue
            if in_timeline and re.match(r"^#+\s", line):
                in_timeline = False
            if in_timeline:
                for link in extract_md_links(line):
                    m = re.search(r"(\d{4}-\d{2}-\d{2})\.md", link)
                    if m:
                        date_str = m.group(1)
                        linked_dates.add(date_str)
                        # Verify the daily actually exists
                        if not (daily_dir / f"{date_str}.md").exists():
                            issues.append(
                                f"  {pf.relative_to(REPO)}: timeline links to nonexistent daily {date_str}"
                            )
        plant_timeline_dates[pf.stem] = linked_dates

    if not plant_files:
        return issues

    # For each daily, check plant mentions → must be in that plant's timeline
    for df in sorted(daily_files):
        date_str = df.stem
        if not re.match(r"\d{4}-\d{2}-\d{2}", date_str):
            continue
        # Search body only (skip frontmatter)
        text = df.read_text()
        body_start = text.find("\n---", 3)
        body = text[body_start + 4:] if body_start != -1 else text

        for pf in plant_files:
            stem = pf.stem  # e.g. "plant-1"
            num_match = re.search(r"(\d+)", stem)
            num = num_match.group(1) if num_match else None
            mentioned = bool(
                (num and re.search(rf"\bplant[-\s]?{re.escape(num)}\b", body, re.IGNORECASE)) or
                re.search(re.escape(stem), body, re.IGNORECASE)
            )
            if mentioned and date_str not in plant_timeline_dates.get(stem, set()):
                issues.append(
                    f"  {df.relative_to(REPO)}: mentions {stem} but not linked from {stem}.md timeline"
                )

    return issues


# ─── check 3: photo coverage ─────────────────────────────────────────────────

def check_photo_coverage() -> list[str]:
    """EXIF dates of raw/photos/*.jpg vs wiki/daily/ entries.

    Two photo layouts are accepted:
    - Legacy flat: ``raw/photos/<file>.jpg`` (any EXIF date).
    - Per-day folders introduced by the daily-report automation
      (2026-04-19 onward): ``raw/photos/YYYY-MM-DD/<preset>.jpg``.
      The folder name is the canonical date for the entry; we still
      verify EXIF DateTimeOriginal is present (the wiki photo-coverage
      check fails if it's missing) but don't require it to match the
      folder name.
    """
    issues = []

    if not RAW_PHOTOS.exists():
        return ["  raw/photos/ directory does not exist"]

    # Map EXIF date → list of filenames; track no-EXIF separately
    photo_dates: dict[str, list[str]] = {}
    no_exif: list[str] = []

    # Per-day folders (new format)
    for day_dir in sorted(RAW_PHOTOS.iterdir()):
        if not day_dir.is_dir():
            continue
        m = re.match(r"^(\d{4}-\d{2}-\d{2})$", day_dir.name)
        if not m:
            continue
        d = m.group(1)
        for photo in sorted(day_dir.glob("*")):
            if photo.suffix.lower() not in {".jpg", ".jpeg"}:
                continue
            if get_exif_date(photo) is None:
                no_exif.append(f"{day_dir.name}/{photo.name}")
            photo_dates.setdefault(d, []).append(f"{day_dir.name}/{photo.name}")

    # Legacy flat files (one EXIF date per file)
    for photo in sorted(RAW_PHOTOS.glob("*")):
        if not photo.is_file():
            continue
        if photo.suffix.lower() not in {".jpg", ".jpeg"}:
            continue
        d = get_exif_date(photo)
        if d:
            photo_dates.setdefault(d, []).append(photo.name)
        else:
            no_exif.append(photo.name)

    daily_dir = WIKI / "daily"
    daily_dates: set[str] = set()
    if daily_dir.exists():
        for f in daily_dir.glob("*.md"):
            m = re.match(r"(\d{4}-\d{2}-\d{2})\.md", f.name)
            if m:
                daily_dates.add(m.group(1))

    for fname in sorted(no_exif):
        issues.append(f"  Photo has no EXIF DateTimeOriginal: {fname}")

    for d, files in sorted(photo_dates.items()):
        if d not in daily_dates:
            for fname in files:
                issues.append(f"  Photo date {d} ({fname}) has no wiki/daily/{d}.md")

    for d in sorted(daily_dates - set(photo_dates)):
        if d in KNOWN_MISSING_PHOTOS:
            continue
        issues.append(f"  wiki/daily/{d}.md has no corresponding photo in raw/photos/")

    return issues


# Daily entries intentionally without a matching photo in raw/photos/.
KNOWN_MISSING_PHOTOS = {
    "2026-04-12",  # topping day for B/C/D; no photo taken
}


# ─── check 4: timeline continuity ────────────────────────────────────────────

# Known gaps where no photos or observations were taken.
# These dates are excluded from the timeline continuity check.
KNOWN_TIMELINE_GAPS = {
    date(2026, 3, 28),   # No photo/chat data
    date(2026, 3, 31),   # Events merged into 2026-03-30 entry
    date(2026, 4, 4),    # No photo/chat data
    date(2026, 4, 7),    # No photo/chat data
    date(2026, 4, 9),    # No photo/chat data
    date(2026, 4, 10),   # No photo/chat data
    date(2026, 4, 13),   # No photo/chat data
    date(2026, 4, 14),   # No photo/chat data
    date(2026, 4, 15),   # No photo/chat data
    date(2026, 4, 16),   # No photo/chat data
    date(2026, 4, 17),   # No photo/chat data
}


def check_timeline_continuity() -> list[str]:
    """Find gaps between first and last wiki/daily/ entry."""
    issues = []
    daily_dir = WIKI / "daily"
    if not daily_dir.exists():
        return []

    dates = []
    for f in daily_dir.glob("*.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})\.md", f.name)
        if m:
            try:
                dates.append(date.fromisoformat(m.group(1)))
            except ValueError:
                pass

    if len(dates) < 2:
        return []

    dates.sort()
    current = dates[0]
    for d in dates[1:]:
        current += timedelta(days=1)
        while current < d:
            if current not in KNOWN_TIMELINE_GAPS:
                issues.append(f"  Missing daily entry: {current.isoformat()}")
            current += timedelta(days=1)

    return issues


# ─── check 5: overview staleness ─────────────────────────────────────────────

def check_overview_staleness() -> list[str]:
    """overview.md frontmatter `updated` vs most recent daily filename."""
    overview_path = WIKI / "overview.md"
    if not overview_path.exists():
        return ["  wiki/overview.md does not exist"]

    daily_dir = WIKI / "daily"
    if not daily_dir.exists():
        return []

    daily_dates = sorted(
        m.group(1)
        for f in daily_dir.glob("*.md")
        if (m := re.match(r"(\d{4}-\d{2}-\d{2})\.md", f.name))
    )
    if not daily_dates:
        return []

    most_recent = daily_dates[-1]
    fm = parse_frontmatter(overview_path.read_text())

    if fm is None:
        return ["  wiki/overview.md has no parseable frontmatter"]

    updated = fm.get("updated", "").strip()
    if not updated:
        return ["  wiki/overview.md frontmatter missing 'updated' field"]

    if updated < most_recent:
        return [
            f"  wiki/overview.md updated={updated} but most recent daily is {most_recent}"
        ]

    return []


# ─── check 6: frontmatter validation ─────────────────────────────────────────

REQUIRED_FIELDS = {"title", "type", "created", "updated"}
SKIP_FILES = {"index.md", "log.md", "CLAUDE.md"}


def check_frontmatter() -> list[str]:
    """Every wiki .md (except index.md, log.md) must have required frontmatter."""
    issues = []
    for md_file in sorted(WIKI.rglob("*.md")):
        if md_file.name in SKIP_FILES:
            continue
        text = md_file.read_text()
        rel = md_file.relative_to(REPO)
        fm = parse_frontmatter(text)
        if fm is None:
            issues.append(f"  {rel}: missing or malformed YAML frontmatter")
            continue
        for field in sorted(REQUIRED_FIELDS - fm.keys()):
            issues.append(f"  {rel}: frontmatter missing required field '{field}'")
    return issues


# ─── check 7: file length ────────────────────────────────────────────────────

MAX_LINES_WARN = 200
MAX_LINES_FAIL = 400
LENGTH_SKIP_FILES = {"index.md", "log.md", "CLAUDE.md"}


def check_file_length() -> list[str]:
    """Flag wiki files that are getting long enough to consider splitting."""
    issues = []
    for md_file in sorted(WIKI.rglob("*.md")):
        if md_file.name in LENGTH_SKIP_FILES:
            continue
        lines = md_file.read_text().splitlines()
        line_count = len(lines)
        rel = md_file.relative_to(REPO)
        if line_count > MAX_LINES_FAIL:
            issues.append(
                f"  {rel}: {line_count} lines (>{MAX_LINES_FAIL}) — should be split"
            )
        elif line_count > MAX_LINES_WARN:
            issues.append(
                f"  {rel}: {line_count} lines (>{MAX_LINES_WARN}) — consider splitting"
            )
    return issues


# ─── runner ───────────────────────────────────────────────────────────────────

CHECKS = [
    ("Index sync",             check_index_sync),
    ("Backlink checker",       check_backlinks),
    ("Photo coverage",         check_photo_coverage),
    ("Timeline continuity",    check_timeline_continuity),
    ("Overview staleness",     check_overview_staleness),
    ("Frontmatter validation", check_frontmatter),
    ("File length",            check_file_length),
]


def main() -> int:
    total_issues = 0
    results: list[tuple[str, list[str]]] = []

    for name, fn in CHECKS:
        issues = fn()
        results.append((name, issues))
        total_issues += len(issues)

    width = 52
    print("=" * width)
    print("  GROW WIKI LINT REPORT")
    print("=" * width)

    failed = 0
    for name, issues in results:
        if issues:
            failed += 1
            print(f"\n[FAIL] {name}")
            for issue in issues:
                print(issue)
        else:
            print(f"\n[ OK ] {name}")

    passed = len(CHECKS) - failed
    print(f"\n{'=' * width}")
    if total_issues == 0:
        print(f"  {passed}/{len(CHECKS)} checks passed — no issues found")
    else:
        print(f"  {passed}/{len(CHECKS)} checks passed — {total_issues} issue(s) found")
    print("=" * width)

    print(
        "\n[LLM] Deterministic lint complete. Now run LLM lint checks:\n"
        "  1. Contradiction detection — cross-reference plant pages, dailies, decisions\n"
        "     and overview for conflicting claims about the same facts.\n"
        "  2. Concept gap scan — read recent daily entries and flag domain terms\n"
        "     (LST, VPD, flushing, trichomes, etc.) with no concepts/ page.\n"
        "  3. Overview accuracy — verify wiki/overview.md reflects the most recent\n"
        "     daily entries and plant pages; rewrite if stale.\n"
        "  File issues in wiki/log.md. Fix contradictions; flag ambiguous ones for user."
    )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
