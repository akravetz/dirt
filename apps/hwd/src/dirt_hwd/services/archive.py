import asyncio
import contextlib
import logging
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from dirt.config import settings

logger = logging.getLogger(__name__)


class ArchiveVerificationError(Exception):
    """Raised when the archived video doesn't match the expected frame count."""


@dataclass
class ArchiveResult:
    video_path: Path
    frame_count: int
    jpegs_deleted: int


def find_jpegs_for_date(snapshot_dir: Path, target_date: date) -> list[Path]:
    """Find all snapshot JPEGs for a given date, sorted by name."""
    pattern = f"snapshot_{target_date.strftime('%Y%m%d')}_*.jpg"
    return sorted(snapshot_dir.glob(pattern))


def find_archivable_dates(snapshot_dir: Path, retention_days: int) -> list[date]:
    """Find dates with snapshots older than retention_days."""
    cutoff = datetime.now(UTC).date() - timedelta(days=retention_days)
    dates = set()
    for jpg in snapshot_dir.glob("snapshot_*.jpg"):
        # Parse date from filename: snapshot_YYYYMMDD_HHMMSS.jpg
        try:
            date_str = jpg.stem.split("_")[1]
            d = datetime.strptime(date_str, "%Y%m%d").date()
            if d < cutoff:
                dates.add(d)
        except (IndexError, ValueError):
            continue
    return sorted(dates)


def run_ffmpeg(jpegs: list[Path], output_path: Path) -> bool:
    """Stitch JPEGs into an MP4 time-lapse video. Returns True on success."""
    if not jpegs:
        return False

    # Create a temporary file list for ffmpeg concat demuxer
    list_file = output_path.parent / f".{output_path.stem}_files.txt"
    try:
        list_file.write_text(
            "\n".join(f"file '{j.resolve()}'\nduration 0.1" for j in jpegs)
        )

        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-vsync",
                "vfr",
                "-pix_fmt",
                "yuv420p",
                "-c:v",
                "libx264",
                "-crf",
                "23",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    finally:
        list_file.unlink(missing_ok=True)


def ffprobe_frame_count(video_path: Path) -> int:
    """Count frames in a video file using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def archive_date(target_date: date) -> ArchiveResult:
    """Archive a single day's snapshots into a time-lapse video.

    Safety invariant: JPEGs are only deleted after the video is verified
    to contain the expected number of frames.
    """
    snapshot_dir = Path(settings.snapshot_dir)
    archive_dir = Path(settings.archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    video_filename = f"timelapse_{target_date.strftime('%Y%m%d')}.mp4"
    video_path = archive_dir / video_filename

    # Idempotency: if video already exists, skip
    if video_path.exists():
        jpegs = find_jpegs_for_date(snapshot_dir, target_date)
        if not jpegs:
            logger.info("Archive %s already exists, no JPEGs to clean", video_filename)
            return ArchiveResult(video_path=video_path, frame_count=0, jpegs_deleted=0)
        # Video exists but JPEGs remain — verify and clean
        actual_frames = ffprobe_frame_count(video_path)
        if actual_frames >= len(jpegs):
            for j in jpegs:
                j.unlink()
            count = len(jpegs)
            logger.info("Cleaned %d JPEGs for archive %s", count, video_filename)
            return ArchiveResult(
                video_path=video_path,
                frame_count=actual_frames,
                jpegs_deleted=count,
            )

    jpegs = find_jpegs_for_date(snapshot_dir, target_date)
    if not jpegs:
        logger.info("No JPEGs found for %s, skipping", target_date)
        return ArchiveResult(video_path=video_path, frame_count=0, jpegs_deleted=0)

    expected_count = len(jpegs)
    logger.info("Archiving %d JPEGs for %s", expected_count, target_date)

    # Step 1: Create video
    success = run_ffmpeg(jpegs, video_path)
    if not success:
        logger.error("ffmpeg failed for %s — JPEGs NOT deleted", target_date)
        video_path.unlink(missing_ok=True)
        raise ArchiveVerificationError(f"ffmpeg failed for {target_date}")

    # Step 2: Verify frame count
    actual_frames = ffprobe_frame_count(video_path)
    if actual_frames != expected_count:
        logger.error(
            "Frame count mismatch for %s: expected %d, got %d — JPEGs NOT deleted",
            target_date,
            expected_count,
            actual_frames,
        )
        video_path.unlink(missing_ok=True)
        raise ArchiveVerificationError(
            f"Frame count mismatch for {target_date}: "
            f"expected {expected_count}, got {actual_frames}"
        )

    # Step 3: Delete source JPEGs (only after verified)
    for j in jpegs:
        j.unlink()
    logger.info(
        "Archived %s: %d frames → %s (%d bytes)",
        target_date,
        actual_frames,
        video_path,
        video_path.stat().st_size,
    )

    return ArchiveResult(
        video_path=video_path,
        frame_count=actual_frames,
        jpegs_deleted=expected_count,
    )


async def archive_loop(stop_event: asyncio.Event) -> None:
    """Periodically check for and archive old snapshots."""
    logger.info(
        "Starting archive loop (retention=%dd)",
        settings.archive_retention_days,
    )
    while not stop_event.is_set():
        try:
            snapshot_dir = Path(settings.snapshot_dir)
            if snapshot_dir.exists():
                dates = find_archivable_dates(
                    snapshot_dir, settings.archive_retention_days
                )
                for d in dates:
                    try:
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, archive_date, d)
                    except ArchiveVerificationError:
                        logger.exception("Archive verification failed for %s", d)
        except Exception:
            logger.exception("Error in archive loop")

        # Check once per hour
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=3600)
