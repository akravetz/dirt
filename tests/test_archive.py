"""Tests for the archive service.

Critical safety invariant: JPEGs must never be deleted unless a valid
video file exists with the expected frame count.
"""

import base64
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from dirt.services.archive import (
    ArchiveVerificationError,
    archive_date,
    ffprobe_frame_count,
    find_archivable_dates,
    find_jpegs_for_date,
    run_ffmpeg,
)

# Tiny (8x8, all-black) valid JPEG. ffmpeg treats each copy as one frame in
# an image-sequence input, which is all the archive tests need.
_TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYF"
    "BgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoK"
    "CgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
    "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx"
    "BhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK"
    "U1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3"
    "uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD+f+ii"
    "igD/2Q=="
)


def _create_test_jpegs(
    snapshot_dir: Path, target_date: date, count: int = 5
) -> list[Path]:
    """Create valid JPEG files for testing. ffmpeg only counts frames, not content."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    jpegs = []
    for i in range(count):
        name = f"snapshot_{target_date.strftime('%Y%m%d')}_{i:02d}0000.jpg"
        path = snapshot_dir / name
        path.write_bytes(_TINY_JPEG)
        jpegs.append(path)
    return jpegs


class TestFindJpegs:
    def test_finds_jpegs_for_date(self, tmp_path):
        d = date(2026, 3, 15)
        created = _create_test_jpegs(tmp_path, d, 3)
        # Add a JPEG for a different date
        _create_test_jpegs(tmp_path, date(2026, 3, 16), 2)

        found = find_jpegs_for_date(tmp_path, d)
        assert len(found) == 3
        assert found == created

    def test_returns_empty_for_no_matches(self, tmp_path):
        found = find_jpegs_for_date(tmp_path, date(2026, 1, 1))
        assert found == []


class TestFindArchivableDates:
    def test_finds_dates_older_than_retention(self, tmp_path):
        _create_test_jpegs(tmp_path, date(2026, 3, 1), 1)
        _create_test_jpegs(tmp_path, date(2026, 3, 10), 1)
        _create_test_jpegs(tmp_path, date(2026, 3, 22), 1)  # today

        with patch("dirt.services.archive.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 3, 22)
            mock_dt.strptime = __import__("datetime").datetime.strptime
            dates = find_archivable_dates(tmp_path, retention_days=7)

        assert date(2026, 3, 1) in dates
        assert date(2026, 3, 10) in dates
        assert date(2026, 3, 22) not in dates


class TestRunFfmpeg:
    def test_creates_valid_video(self, tmp_path):
        d = date(2026, 3, 15)
        jpegs = _create_test_jpegs(tmp_path / "snapshots", d, 5)
        output = tmp_path / "output.mp4"

        success = run_ffmpeg(jpegs, output)

        assert success
        assert output.exists()
        assert output.stat().st_size > 0

    def test_returns_false_on_empty_input(self, tmp_path):
        output = tmp_path / "output.mp4"
        success = run_ffmpeg([], output)
        assert not success

    def test_ffprobe_counts_frames(self, tmp_path):
        d = date(2026, 3, 15)
        jpegs = _create_test_jpegs(tmp_path / "snapshots", d, 5)
        output = tmp_path / "output.mp4"
        run_ffmpeg(jpegs, output)

        count = ffprobe_frame_count(output)
        assert count == 5


class TestArchiveDate:
    def test_archives_and_deletes_jpegs(self, tmp_path):
        d = date(2026, 3, 15)
        snapshot_dir = tmp_path / "snapshots"
        archive_dir = tmp_path / "archives"
        jpegs = _create_test_jpegs(snapshot_dir, d, 5)

        with patch("dirt.services.archive.settings") as mock_settings:
            mock_settings.snapshot_dir = str(snapshot_dir)
            mock_settings.archive_dir = str(archive_dir)

            result = archive_date(d)

        assert result.frame_count == 5
        assert result.jpegs_deleted == 5
        assert result.video_path.exists()
        # All source JPEGs should be deleted
        for j in jpegs:
            assert not j.exists(), f"{j} should have been deleted"

    def test_ffmpeg_failure_does_not_delete_jpegs(self, tmp_path):
        d = date(2026, 3, 15)
        snapshot_dir = tmp_path / "snapshots"
        archive_dir = tmp_path / "archives"
        jpegs = _create_test_jpegs(snapshot_dir, d, 5)

        with (
            patch("dirt.services.archive.settings") as mock_settings,
            patch("dirt.services.archive.run_ffmpeg", return_value=False),
        ):
            mock_settings.snapshot_dir = str(snapshot_dir)
            mock_settings.archive_dir = str(archive_dir)

            with pytest.raises(ArchiveVerificationError, match="ffmpeg failed"):
                archive_date(d)

        # All source JPEGs must still exist
        for j in jpegs:
            assert j.exists(), f"{j} should NOT have been deleted"

    def test_frame_count_mismatch_does_not_delete_jpegs(self, tmp_path):
        d = date(2026, 3, 15)
        snapshot_dir = tmp_path / "snapshots"
        archive_dir = tmp_path / "archives"
        jpegs = _create_test_jpegs(snapshot_dir, d, 5)

        with (
            patch("dirt.services.archive.settings") as mock_settings,
            patch("dirt.services.archive.ffprobe_frame_count", return_value=3),
        ):
            mock_settings.snapshot_dir = str(snapshot_dir)
            mock_settings.archive_dir = str(archive_dir)

            with pytest.raises(ArchiveVerificationError, match="Frame count mismatch"):
                archive_date(d)

        # All source JPEGs must still exist
        for j in jpegs:
            assert j.exists(), f"{j} should NOT have been deleted"
        # Incomplete video should be cleaned up
        video = archive_dir / f"timelapse_{d.strftime('%Y%m%d')}.mp4"
        assert not video.exists(), "Invalid video should have been deleted"

    def test_idempotent_second_run_is_noop(self, tmp_path):
        d = date(2026, 3, 15)
        snapshot_dir = tmp_path / "snapshots"
        archive_dir = tmp_path / "archives"
        _create_test_jpegs(snapshot_dir, d, 5)

        with patch("dirt.services.archive.settings") as mock_settings:
            mock_settings.snapshot_dir = str(snapshot_dir)
            mock_settings.archive_dir = str(archive_dir)

            result1 = archive_date(d)
            assert result1.jpegs_deleted == 5

            # Second run — video exists, no JPEGs left
            result2 = archive_date(d)
            assert result2.jpegs_deleted == 0

    def test_no_jpegs_is_noop(self, tmp_path):
        d = date(2026, 3, 15)
        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir()
        archive_dir = tmp_path / "archives"

        with patch("dirt.services.archive.settings") as mock_settings:
            mock_settings.snapshot_dir = str(snapshot_dir)
            mock_settings.archive_dir = str(archive_dir)

            result = archive_date(d)

        assert result.frame_count == 0
        assert result.jpegs_deleted == 0

    def test_corrupt_jpeg_handled(self, tmp_path):
        d = date(2026, 3, 15)
        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir(parents=True)
        archive_dir = tmp_path / "archives"

        # Create a 0-byte "JPEG"
        bad_file = snapshot_dir / f"snapshot_{d.strftime('%Y%m%d')}_000000.jpg"
        bad_file.write_bytes(b"")

        with patch("dirt.services.archive.settings") as mock_settings:
            mock_settings.snapshot_dir = str(snapshot_dir)
            mock_settings.archive_dir = str(archive_dir)

            # ffmpeg will fail on corrupt input — should not delete
            with pytest.raises(ArchiveVerificationError):
                archive_date(d)

        assert bad_file.exists(), "Corrupt file should NOT have been deleted"
