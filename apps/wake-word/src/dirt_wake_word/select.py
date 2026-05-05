"""Pick the saved checkpoint with the highest F1 against real audio."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .real_audio_score import (
    OnnxWindowScorer,
    precision_recall_f1,
    prepare_validation_windows,
)


@dataclass(frozen=True)
class CandidateScore:
    index: int
    recall: float
    precision: float
    f1: float
    step: int

    def sort_key(self) -> tuple[float, float, int]:
        return (self.f1, self.recall, self.step)


def select_best_by_real_f1(
    oww,
    *,
    work_dir: Path,
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

    prep_t0 = time.perf_counter()
    validation_windows = prepare_validation_windows(
        validation_good=validation_good,
        validation_bad=validation_bad,
    )
    print(
        "=== checkpoint_feature_telemetry: "
        f"good_windows={validation_windows.telemetry['good_windows']} "
        f"good_preprocessor_s={validation_windows.telemetry['good_preprocessor_s']:.3f} "
        f"good_total_s={validation_windows.telemetry['good_total_s']:.3f} "
        f"bad_windows={validation_windows.telemetry['bad_windows']} "
        f"bad_preprocessor_s={validation_windows.telemetry['bad_preprocessor_s']:.3f} "
        f"bad_total_s={validation_windows.telemetry['bad_total_s']:.3f} "
        f"provider={validation_windows.telemetry['provider']} "
        f"total_s={time.perf_counter() - prep_t0:.3f} ===",
        flush=True,
    )

    rows: list[CandidateScore] = []
    for i, model in enumerate(oww.best_models):
        t0 = time.monotonic()
        slug = f"cand_{i:03d}"
        export_t0 = time.perf_counter()
        oww.export_model(model=model, model_name=slug, output_dir=str(tmp_dir))
        export_s = time.perf_counter() - export_t0
        onnx_path = tmp_dir / f"{slug}.onnx"

        scorer = OnnxWindowScorer(onnx_path)
        good_scores, good_telemetry = scorer.score(validation_windows.good)
        bad_scores, bad_telemetry = scorer.score(validation_windows.bad)
        metrics_t0 = time.perf_counter()
        _, fp, recall, precision, f1 = precision_recall_f1(
            good_scores, bad_scores, threshold=threshold
        )
        metrics_s = time.perf_counter() - metrics_t0

        step = oww.best_model_scores[i].get("training_step_ndx", -1)
        rows.append(
            CandidateScore(
                index=i,
                recall=recall,
                precision=precision,
                f1=f1,
                step=int(step),
            )
        )
        elapsed = time.monotonic() - t0
        print(
            f"  cand {i:>3} step={step:>5} | recall={recall:.3f} "
            f"prec={precision:.3f} f1={f1:.3f} fp={fp} elapsed={elapsed:.1f}s",
            flush=True,
        )
        print(
            "    checkpoint_selection_telemetry: "
            f"cand={i} provider={good_telemetry['provider']} export_s={export_s:.3f} "
            f"batchable={good_telemetry['batchable']} "
            f"original_batch_dim={good_telemetry['original_batch_dim']} "
            f"batch_size={good_telemetry['batch_size']} "
            f"good_session_init_s={good_telemetry['session_init_s']:.3f} "
            f"good_inference_s={good_telemetry['inference_s']:.3f} "
            f"good_batches={good_telemetry['batches']} "
            f"good_windows={good_telemetry['windows']} "
            f"bad_inference_s={bad_telemetry['inference_s']:.3f} "
            f"bad_batches={bad_telemetry['batches']} "
            f"bad_windows={bad_telemetry['windows']} "
            f"metrics_s={metrics_s:.3f} total_s={elapsed:.3f}",
            flush=True,
        )
        onnx_path.unlink(missing_ok=True)

    rows.sort(key=CandidateScore.sort_key, reverse=True)
    best = rows[0]
    print(
        f"\nBest checkpoint by real-audio F1: cand {best.index} step={best.step} "
        f"(recall={best.recall:.3f}, precision={best.precision:.3f}, "
        f"F1={best.f1:.3f})"
    )
    return oww.best_models[best.index]
