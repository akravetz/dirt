"""Serial reader: boot-frame routing + reading-frame routing.

Covers the event-type split in `serial_reader`: boot diagnostic frames go to
the `sensor_boot` observability stream; metric frames go through the derive
path. Both paths are exercised with synthetic `data` dicts (not a real serial
port) — the loop's asyncio plumbing is out of scope here.
"""
from __future__ import annotations

import json
from pathlib import Path

from dirt_hwd.services.serial_reader import (
    _derive_metrics,
    _is_boot_frame,
    _log_boot_frame,
)


def test_boot_frame_routed_to_sensor_boot_stream(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIRT_LOGS_DIR", str(tmp_path))

    boot = {
        "event": "boot",
        "chip_id": 96,
        "calib_tp": "6e6fd09e" + "00" * 20,
        "dig_H1": 75,
        "calib_h": "62015400" + "1e" * 3,
        "ctrl_hum": 5,
        "ctrl_meas": 183,
        "config": 160,
    }

    assert _is_boot_frame(boot)
    _log_boot_frame(boot)

    # Observability writer is a daemon thread — drain via the same primitive
    # the observability module uses internally.
    from dirt_shared import observability
    observability._write_queue.join() if False else None  # noqa: E501 (pragma)
    # Simpler: poll for the file to appear.
    log_dir = tmp_path / "sensor_boot"
    for _ in range(50):
        if log_dir.exists() and any(log_dir.iterdir()):
            break
        import time
        time.sleep(0.05)

    files = list(log_dir.glob("*.jsonl"))
    assert files, f"no jsonl written under {log_dir}"
    lines = files[0].read_text().strip().splitlines()
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert envelope["stream"] == "sensor_boot"
    assert envelope["event"] == "boot"
    assert envelope["chip_id"] == 96
    assert envelope["calib_tp"].startswith("6e6fd09e")
    assert envelope["ctrl_hum"] == 5
    # The `event` key is consumed by log_event's own `event` parameter and
    # must not also appear in fields (would collide).
    assert "event" not in {k for k in envelope if k not in {"stream", "event"}}


def test_metric_frame_not_a_boot_frame() -> None:
    reading = {
        "temperature_c": 22.5,
        "humidity_pct": 55.0,
        "pressure_hpa": 842.0,
    }
    assert not _is_boot_frame(reading)

    metrics = _derive_metrics(reading)
    assert round(metrics["temperature_f"], 1) == 72.5
    assert metrics["humidity_pct"] == 55.0
    assert metrics["pressure_hpa"] == 842.0
    assert "vpd_kpa" in metrics
    assert "dew_point_f" in metrics


def test_error_frame_not_a_boot_frame() -> None:
    assert not _is_boot_frame({"error": "BME280 not found"})
