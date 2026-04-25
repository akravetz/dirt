"""Post-training real-audio validation report.

Score the trained ONNX against `var/wake-word/validation/{good,bad}/` and
write a recall/precision/F1 sweep to `<work>/validation-report.txt` so it
gets pulled back alongside the model.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from openwakeword.model import Model

from .config import TARGET_WORD


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

    chunk = 1280  # 80 ms at 16 kHz
    model = Model(wakeword_model_paths=[str(onnx_path)])
    name = next(iter(model.models.keys()))

    def peak(wav_path: Path) -> float:
        with wave.open(str(wav_path), "rb") as w:
            wav = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        model.reset()
        p = 0.0
        for start in range(0, len(wav) - chunk + 1, chunk):
            s = float(model.predict(wav[start : start + chunk])[name])
            if s > p:
                p = s
        return p

    good = [peak(p) for p in sorted(expected_inputs["validation_good"].glob("*.wav"))]
    bad = [peak(p) for p in sorted(expected_inputs["validation_bad"].glob("*.wav"))]

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
        tp = sum(1 for s in good if s >= t)
        fp = sum(1 for s in bad if s >= t)
        recall = tp / len(good) if good else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        lines.append(
            f"  {t:>5.2f} | {recall:>7.1%} | {fp:>2}/{len(bad):<3}  | {precision:>9.1%} | {f1:>.3f}"
        )

    report = "\n".join(lines)
    print()
    print(report)
    print()
    (work_dir / "validation-report.txt").write_text(report + "\n")
