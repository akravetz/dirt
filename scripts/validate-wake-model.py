"""Local validation harness for openwakeword .onnx models.

Runs a wake-word model against a labeled WAV set and reports recall, false-
positive rate, and per-file peak scores. Independent of Kaggle and the live
service — this is the metric we should be optimizing for, since synthetic
test recall (Piper-generated clips) was misleading vs real-audio behavior.

Validation set layout (default: var/wake-word/validation/):
    good/  — positives: real "hey claudia" utterances. Model SHOULD fire.
    bad/   — negatives: false positives the model caught in the wild that
             we know are not the wake word. Model should NOT fire.

Usage:
    uv run python scripts/validate-wake-model.py var/wake-word/models/current/hey_claudia.onnx
    uv run python scripts/validate-wake-model.py var/wake-word/models/2026-04-25-v5/hey_claudia.onnx --threshold 0.5
    uv run python scripts/validate-wake-model.py path/to/model.onnx \\
        --validation-dir path/to/validation/ --threshold 0.4
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

import numpy as np
from openwakeword.model import Model

ROOT = Path(__file__).resolve().parent.parent

SAMPLE_RATE = 16000
CHUNK_MS = 80
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_MS // 1000  # 1280


def load_wav_int16(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getframerate() != SAMPLE_RATE or w.getsampwidth() != 2:
            raise ValueError(
                f"{path.name}: expected 16 kHz mono 16-bit PCM, got "
                f"{w.getframerate()} Hz / {w.getnchannels()} ch / {w.getsampwidth()*8}-bit"
            )
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def peak_score(model: Model, model_name: str, wav: np.ndarray) -> float:
    """Run the model frame-by-frame; return the maximum score across the clip."""
    model.reset()
    peak = 0.0
    for start in range(0, len(wav) - CHUNK_SAMPLES + 1, CHUNK_SAMPLES):
        frame = wav[start : start + CHUNK_SAMPLES]
        scores = model.predict(frame)
        score = float(scores[model_name])
        if score > peak:
            peak = score
    return peak


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("model_path", type=Path, help="Path to .onnx model")
    p.add_argument(
        "--validation-dir",
        type=Path,
        default=ROOT / "var" / "wake-word" / "validation",
        help="Directory containing good/ and bad/ subdirs (default: var/wake-word/validation/)",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Detection threshold (peak score >= this counts as a fire). Default 0.5.",
    )
    p.add_argument(
        "--show-all",
        action="store_true",
        help="Show every per-file score, not just misclassifications.",
    )
    args = p.parse_args()

    if not args.model_path.exists():
        sys.exit(f"Model not found: {args.model_path}")
    good_dir = args.validation_dir / "good"
    bad_dir = args.validation_dir / "bad"
    if not good_dir.is_dir() or not bad_dir.is_dir():
        sys.exit(
            f"Validation set not found. Expected {good_dir}/ and {bad_dir}/ to exist."
        )

    print(f"Model:        {args.model_path}")
    print(f"Validation:   {args.validation_dir}")
    print(f"Threshold:    {args.threshold}")
    print()

    model = Model(wakeword_model_paths=[str(args.model_path)])
    model_name = next(iter(model.models.keys()))

    # Score every file
    good_scores: list[tuple[Path, float]] = []
    bad_scores: list[tuple[Path, float]] = []
    for wav_path in sorted(good_dir.glob("*.wav")):
        good_scores.append((wav_path, peak_score(model, model_name, load_wav_int16(wav_path))))
    for wav_path in sorted(bad_dir.glob("*.wav")):
        bad_scores.append((wav_path, peak_score(model, model_name, load_wav_int16(wav_path))))

    # Classify
    tp = sum(1 for _, s in good_scores if s >= args.threshold)
    fn = len(good_scores) - tp
    fp = sum(1 for _, s in bad_scores if s >= args.threshold)
    tn = len(bad_scores) - fp

    recall = tp / len(good_scores) if good_scores else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    accuracy = (tp + tn) / (len(good_scores) + len(bad_scores))
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # ---- Misclassifications first (the actionable cases) -------------------
    print("=" * 70)
    print("MISSED POSITIVES (good/ files that scored below threshold)")
    print("=" * 70)
    misses = sorted([(p, s) for p, s in good_scores if s < args.threshold], key=lambda x: x[1])
    if not misses:
        print("  (none — perfect recall)")
    for path, score in misses:
        print(f"  {score:.3f}  {path.name}")
    print()

    print("=" * 70)
    print("FALSE POSITIVES (bad/ files that scored at or above threshold)")
    print("=" * 70)
    fps = sorted([(p, s) for p, s in bad_scores if s >= args.threshold], key=lambda x: -x[1])
    if not fps:
        print("  (none — perfect precision)")
    for path, score in fps:
        print(f"  {score:.3f}  {path.name}")
    print()

    if args.show_all:
        print("=" * 70)
        print("ALL POSITIVES (good/) — peak scores")
        print("=" * 70)
        for path, score in sorted(good_scores, key=lambda x: x[1]):
            mark = "✓" if score >= args.threshold else "✗"
            print(f"  {mark} {score:.3f}  {path.name}")
        print()
        print("=" * 70)
        print("ALL NEGATIVES (bad/) — peak scores")
        print("=" * 70)
        for path, score in sorted(bad_scores, key=lambda x: -x[1]):
            mark = "✗" if score >= args.threshold else "✓"
            print(f"  {mark} {score:.3f}  {path.name}")
        print()

    # ---- Summary -----------------------------------------------------------
    print("=" * 70)
    print(f"SUMMARY @ threshold={args.threshold}")
    print("=" * 70)
    print(f"  Positives (good/):     {len(good_scores)}")
    print(f"    fired:                {tp:>3}  (true positives)")
    print(f"    missed:               {fn:>3}  (false negatives)")
    print(f"  Negatives (bad/):      {len(bad_scores)}")
    print(f"    correctly rejected:   {tn:>3}  (true negatives)")
    print(f"    false-fired:          {fp:>3}  (false positives)")
    print()
    print(f"  Recall                  {recall:>7.1%}    (catch rate)")
    print(f"  Precision               {precision:>7.1%}    (when it fires, how often is it right)")
    print(f"  Accuracy                {accuracy:>7.1%}    (overall correctness)")
    print(f"  F1                      {f1:>7.3f}")


if __name__ == "__main__":
    main()
