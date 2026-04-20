#!/usr/bin/env python3
"""Extract EXIF DateTimeOriginal from JPEG files.

Usage:
    uv run scripts/exif_date.py path/to/photo.jpg
    uv run scripts/exif_date.py raw/photos/
    uv run scripts/exif_date.py img1.jpg img2.jpg

Output (tab-separated):
    filename\tdate\tdatetime
    filename\tNO_EXIF\t-
"""

import sys
from pathlib import Path

from PIL import Image

EXIF_TAG_DATETIME_ORIGINAL = 36867  # DateTimeOriginal tag ID


def get_exif_date(path: Path) -> tuple[str, str] | tuple[None, None]:
    """Return (date, datetime) strings from EXIF, or (None, None) if unavailable."""
    try:
        with Image.open(path) as img:
            exif_data = img._getexif()
    except Exception:
        return None, None

    if not exif_data:
        return None, None

    raw = exif_data.get(EXIF_TAG_DATETIME_ORIGINAL)
    if not raw:
        return None, None

    # EXIF format: "YYYY:MM:DD HH:MM:SS"
    try:
        date_part, time_part = raw.split(" ", 1)
        date = date_part.replace(":", "-")
        dt = f"{date} {time_part}"
        return date, dt
    except ValueError:
        return None, None


def collect_files(args: list[str]) -> list[Path]:
    files = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            files.extend(sorted(p.glob("*.[jJ][pP][gG]")))
            files.extend(sorted(p.glob("*.[jJ][pP][eE][gG]")))
        else:
            files.append(p)
    return files


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file_or_dir> [...]", file=sys.stderr)
        sys.exit(1)

    files = collect_files(sys.argv[1:])

    if not files:
        print("No JPEG files found.", file=sys.stderr)
        sys.exit(1)

    for path in files:
        date, dt = get_exif_date(path)
        if date:
            print(f"{path.name}\t{date}\t{dt}")
        else:
            print(f"{path.name}\tNO_EXIF\t-")


if __name__ == "__main__":
    main()
