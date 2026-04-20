import asyncio
import contextlib
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from dirt_shared.config import ArchiveConfig

# Type aliases for the ffmpeg / ffprobe boundaries — exposed as
# constructor parameters of ``ArchiveService`` so tests can inject
# fakes without patching ``dirt_hwd.services.archive`` internals.
FfmpegRunner = Callable[[list[Path], Path], bool]
FrameCounter = Callable[[Path], int]

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


def find_archivable_dates(
    snapshot_dir: Path,
    retention_days: int,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> list[date]:
    """Find dates with snapshots older than retention_days.

    ``clock`` is a Callable[[], datetime] (default: ``datetime.now(UTC)``).
    Tests pass an explicit clock for deterministic behaviour without
    patching the datetime module.
    """
    today = clock().date()
    cutoff = today - timedelta(days=retention_days)
    dates = set()
    for jpg in snapshot_dir.glob("snapshot_*.jpg"):
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

    list_file = output_path.parent / f".{output_path.stem}_files.txt"
    try:
        list_file.write_text(
            "\n".join(f"file '{j.resolve()}'\nduration 0.1" for j in jpegs)
        )

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-vsync", "vfr",
                "-pix_fmt", "yuv420p",
                "-c:v", "libx264",
                "-crf", "23",
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
            "ffprobe", "-v", "error",
            "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames",
            "-of", "csv=p=0",
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


class ArchiveService:
    """Periodic archive of dated snapshot JPEGs into MP4 time-lapses.

    Constructor-inject ``ArchiveConfig`` plus the two external-binary
    wrappers (``ffmpeg_runner`` + ``frame_counter``) so tests can swap
    them with fakes — no need to patch ``dirt_hwd.services.archive``
    internals from the test side.
    """

    def __init__(
        self,
        config: ArchiveConfig,
        *,
        ffmpeg_runner: FfmpegRunner = run_ffmpeg,
        frame_counter: FrameCounter = ffprobe_frame_count,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._config = config
        self._ffmpeg_runner = ffmpeg_runner
        self._frame_counter = frame_counter
        self._clock = clock

    def archive_date(self, target_date: date) -> ArchiveResult:
        """Archive a single day's snapshots into a time-lapse video.

        Safety invariant: JPEGs are only deleted after the video is
        verified to contain the expected frames.
        """
        snapshot_dir = self._config.snapshot_dir
        archive_dir = self._config.archive_dir
        archive_dir.mkdir(parents=True, exist_ok=True)

        video_filename = f"timelapse_{target_date.strftime('%Y%m%d')}.mp4"
        video_path = archive_dir / video_filename

        # Idempotency: if video already exists, skip
        if video_path.exists():
            jpegs = find_jpegs_for_date(snapshot_dir, target_date)
            if not jpegs:
                logger.info(
                    "Archive %s already exists, no JPEGs to clean",
                    video_filename,
                )
                return ArchiveResult(
                    video_path=video_path, frame_count=0, jpegs_deleted=0,
                )
            actual_frames = self._frame_counter(video_path)
            if actual_frames >= len(jpegs):
                for j in jpegs:
                    j.unlink()
                count = len(jpegs)
                logger.info(
                    "Cleaned %d JPEGs for archive %s", count, video_filename,
                )
                return ArchiveResult(
                    video_path=video_path,
                    frame_count=actual_frames,
                    jpegs_deleted=count,
                )

        jpegs = find_jpegs_for_date(snapshot_dir, target_date)
        if not jpegs:
            logger.info("No JPEGs found for %s, skipping", target_date)
            return ArchiveResult(
                video_path=video_path, frame_count=0, jpegs_deleted=0,
            )

        expected_count = len(jpegs)
        logger.info("Archiving %d JPEGs for %s", expected_count, target_date)

        success = self._ffmpeg_runner(jpegs, video_path)
        if not success:
            logger.error(
                "ffmpeg failed for %s — JPEGs NOT deleted", target_date,
            )
            video_path.unlink(missing_ok=True)
            raise ArchiveVerificationError(f"ffmpeg failed for {target_date}")

        actual_frames = self._frame_counter(video_path)
        if actual_frames != expected_count:
            logger.error(
                "Frame count mismatch for %s: expected %d, got %d — JPEGs NOT deleted",
                target_date, expected_count, actual_frames,
            )
            video_path.unlink(missing_ok=True)
            raise ArchiveVerificationError(
                f"Frame count mismatch for {target_date}: "
                f"expected {expected_count}, got {actual_frames}"
            )

        for j in jpegs:
            j.unlink()
        logger.info(
            "Archived %s: %d frames → %s (%d bytes)",
            target_date, actual_frames, video_path, video_path.stat().st_size,
        )

        return ArchiveResult(
            video_path=video_path,
            frame_count=actual_frames,
            jpegs_deleted=expected_count,
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        """Periodically check for and archive old snapshots."""
        logger.info(
            "Starting archive loop (retention=%dd)",
            self._config.retention_days,
        )
        while not stop_event.is_set():
            try:
                snapshot_dir = self._config.snapshot_dir
                if snapshot_dir.exists():
                    dates = find_archivable_dates(
                        snapshot_dir,
                        self._config.retention_days,
                        clock=self._clock,
                    )
                    for d in dates:
                        try:
                            loop = asyncio.get_running_loop()
                            await loop.run_in_executor(
                                None, self.archive_date, d,
                            )
                        except ArchiveVerificationError:
                            logger.exception(
                                "Archive verification failed for %s", d,
                            )
            except Exception:
                logger.exception("Error in archive loop")

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=3600)
