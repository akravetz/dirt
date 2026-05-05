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
    prepare_validation_windows,
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
    validation_windows = prepare_validation_windows(
        validation_good=expected_inputs["validation_good"],
        validation_bad=expected_inputs["validation_bad"],
    )
    good, good_score_telemetry = score_prepared_windows(
        onnx_path, validation_windows.good
    )
    bad, bad_score_telemetry = score_prepared_windows(onnx_path, validation_windows.bad)
    print(
        "=== validation_score_telemetry: "
        f"good_windows={validation_windows.telemetry['good_windows']} "
        f"good_preprocessor_s={validation_windows.telemetry['good_preprocessor_s']:.3f} "
        f"good_score_s={good_score_telemetry['inference_s']:.3f} "
        f"bad_windows={validation_windows.telemetry['bad_windows']} "
        f"bad_preprocessor_s={validation_windows.telemetry['bad_preprocessor_s']:.3f} "
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
