"""Post-training real-audio validation report.

Score the trained ONNX against `var/wake-word/validation/{good,bad}/` and
write a recall/precision/F1 sweep to `<work>/validation-report.txt` so it
gets pulled back alongside the model.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from .config import TARGET_WORD
from .real_audio_score import (
    precision_recall_f1,
    prepare_streaming_windows,
    score_prepared_windows,
)


def validate_against_real_set(
    *,
    work_dir: Path,
    out_dir: Path,
    expected_inputs: dict[str, Path],
) -> None:
    onnx_path = out_dir / f"{TARGET_WORD}.onnx"
    if not onnx_path.exists():
        print("validate: no ONNX produced; skipping", file=sys.stderr)
        return

    t0 = time.perf_counter()
    good_windows = prepare_streaming_windows(
        sorted(expected_inputs["validation_good"].glob("*.wav"))
    )
    bad_windows = prepare_streaming_windows(
        sorted(expected_inputs["validation_bad"].glob("*.wav"))
    )
    good, good_score_telemetry = score_prepared_windows(onnx_path, good_windows)
    bad, bad_score_telemetry = score_prepared_windows(onnx_path, bad_windows)
    print(
        "=== validation_score_telemetry: "
        f"good_windows={good_windows.telemetry['windows']} "
        f"good_preprocessor_s={good_windows.telemetry['preprocessor_s']:.3f} "
        f"good_score_s={good_score_telemetry['inference_s']:.3f} "
        f"bad_windows={bad_windows.telemetry['windows']} "
        f"bad_preprocessor_s={bad_windows.telemetry['preprocessor_s']:.3f} "
        f"bad_score_s={bad_score_telemetry['inference_s']:.3f} "
        f"provider={good_score_telemetry['provider']} "
        f"batchable={good_score_telemetry['batchable']} "
        f"original_batch_dim={good_score_telemetry['original_batch_dim']} "
        f"batch_size={good_score_telemetry['batch_size']} "
        f"total_s={time.perf_counter() - t0:.3f} ===",
        flush=True,
    )

    lines = [
        "VALIDATION REPORT (real audio)",
        "=" * 50,
        f"Model:  {onnx_path.name}",
        f"good/:  {len(good)} positives",
        f"bad/:   {len(bad)} negatives (in-the-wild false-positives)",
        "",
        f"{'thresh':>7} | {'recall':>7} | {'fps':>7} | {'precision':>9} | {'f1':>5}",
        "-" * 50,
    ]
    for t in (0.30, 0.40, 0.50, 0.60, 0.70):
        _, fp, recall, precision, f1 = precision_recall_f1(good, bad, threshold=t)
        lines.append(
            f"  {t:>5.2f} | {recall:>7.1%} | {fp:>2}/{len(bad):<3}  | {precision:>9.1%} | {f1:>.3f}"
        )

    report = "\n".join(lines)
    print()
    print(report)
    print()
    (work_dir / "validation-report.txt").write_text(report + "\n")
