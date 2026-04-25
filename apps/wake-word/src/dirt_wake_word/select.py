"""v8 — pick the saved checkpoint with the highest F1 against real audio.

For each candidate in `oww.best_models`, export a temporary ONNX, score
every WAV in `validation/{good,bad}/`, compute F1 at the given threshold,
and pick max. Tiebreak by recall, then by latest training step.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from openwakeword.model import Model as InferenceModel


def _load_wav(p: Path) -> np.ndarray:
    with wave.open(str(p), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def _score_clips(
    model: InferenceModel, name: str, paths: list[Path], chunk: int = 1280
) -> list[float]:
    out = []
    for path in paths:
        wav = _load_wav(path)
        model.reset()
        peak = 0.0
        for s in range(0, len(wav) - chunk + 1, chunk):
            v = float(model.predict(wav[s : s + chunk])[name])
            if v > peak:
                peak = v
        out.append(peak)
    return out


def select_best_by_real_f1(
    oww,
    *,
    work_dir: Path,
    target_word: str,
    validation_good: Path,
    validation_bad: Path,
    threshold: float = 0.5,
):
    """Returns the chosen torch.nn.Module ready for export_model()."""
    if not oww.best_models:
        print(
            "No checkpoints saved — falling back to final model state",
            file=sys.stderr,
        )
        return oww.model

    good_paths = sorted(validation_good.glob("*.wav"))
    bad_paths = sorted(validation_bad.glob("*.wav"))
    n_good, n_bad = len(good_paths), len(bad_paths)
    if n_good == 0 or n_bad == 0:
        print(
            "Validation set empty; falling back to synthetic-recall selection",
            file=sys.stderr,
        )
        scores = oww.best_model_scores
        ok = [(i, s) for i, s in enumerate(scores) if float(s["val_fp_per_hr"]) <= 2.0]
        if not ok:
            ok = list(enumerate(scores))
        best_idx, _ = max(ok, key=lambda kv: float(kv[1]["val_recall"]))
        return oww.best_models[best_idx]

    tmp_dir = work_dir / "_candidates"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"=== real-audio F1 checkpoint selection: {len(oww.best_models)} candidates "
        f"vs {n_good} good / {n_bad} bad ===",
        flush=True,
    )

    rows: list[tuple[int, float, float, float, int]] = []
    for i, model in enumerate(oww.best_models):
        slug = f"cand_{i:03d}"
        oww.export_model(model=model, model_name=slug, output_dir=str(tmp_dir))
        onnx_path = tmp_dir / f"{slug}.onnx"
        infer = InferenceModel(wakeword_model_paths=[str(onnx_path)])
        name = next(iter(infer.models.keys()))
        good_scores = _score_clips(infer, name, good_paths)
        bad_scores = _score_clips(infer, name, bad_paths)
        tp = sum(1 for s in good_scores if s >= threshold)
        fp = sum(1 for s in bad_scores if s >= threshold)
        recall = tp / n_good
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        step = oww.best_model_scores[i].get("training_step_ndx", -1)
        rows.append((i, recall, precision, f1, int(step)))
        print(
            f"  cand {i:>3} step={step:>5} | recall={recall:.3f} "
            f"prec={precision:.3f} f1={f1:.3f}",
            flush=True,
        )
        onnx_path.unlink(missing_ok=True)

    rows.sort(key=lambda r: (r[3], r[1], r[4]), reverse=True)
    best_i, best_r, best_p, best_f1, best_step = rows[0]
    print(
        f"\nBest checkpoint by real-audio F1: cand {best_i} step={best_step} "
        f"(recall={best_r:.3f}, precision={best_p:.3f}, F1={best_f1:.3f})"
    )
    return oww.best_models[best_i]
