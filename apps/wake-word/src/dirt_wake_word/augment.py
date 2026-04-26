"""Per-subset augmentation + feature compute (replaces upstream's --augment_clips).

For each of the 4 feature subsets (positive_train, negative_train,
positive_test, negative_test) we split files by filename prefix:

    synth (default):    Piper-generated UUIDs, synth_clone_*, synth_neighbor_*
    real-room recorded: realmic_*, harvested_*

Synth gets the default augmentation pipeline. Real-room recorded gets
RIR=0.0 + AddBackgroundNoise=0.5 (down from 0.75) — the clip already
carries the deployment room's reverb, so convolving with another RIR is an
unphysical 2-room cascade.
"""

from __future__ import annotations

import os
import wave
from itertools import chain
from pathlib import Path

import numpy as np
import torch
import yaml
from openwakeword.data import augment_clips
from openwakeword.utils import compute_features_from_generator

from .config import TARGET_WORD
from .subsets import SUBSETS, is_real_audio

DEFAULTS = {
    "SevenBandParametricEQ": 0.25,
    "TanhDistortion": 0.25,
    "PitchShift": 0.25,
    "BandStopFilter": 0.25,
    "AddColoredNoise": 0.25,
    "AddBackgroundNoise": 0.75,
    "Gain": 1.0,
    "RIR": 0.5,
}
REAL_AUDIO = {**DEFAULTS, "RIR": 0.0, "AddBackgroundNoise": 0.5}


# openwakeword expects feature files at well-known names per subset.
def _features_filename(subset: str) -> str:
    pos_neg, train_test = subset.split("_")
    return f"{pos_neg}_features_{train_test}.npy"


def _compute_total_length(positive_test_dir: Path, *, n_sample: int = 50) -> int:
    """Median clip length + 750 ms buffer, floored at 32000 samples (2 s).

    Ported from upstream openwakeword/train.py — our soft-fork skips the
    code path that originally set config["total_length"]. Numbers are in
    samples (16 kHz), so 1000 ≈ 62.5 ms and 12000 ≈ 750 ms.
    """
    clips = sorted(positive_test_dir.glob("*.wav"))
    if not clips:
        return 32000
    rng = np.random.default_rng(0)
    sampled = rng.choice(clips, size=min(n_sample, len(clips)), replace=False)
    durations = []
    for path in sampled:
        with wave.open(str(path), "rb") as w:
            durations.append(w.getnframes())
    total = int(round(np.median(durations) / 1000) * 1000) + 12000
    # Snap to 32 000 for both "below 2 s" and "near 2 s" clips — upstream
    # convention; simplifies feature-shape assumptions downstream.
    if total < 32000 or abs(total - 32000) <= 4000:
        total = 32000
    return total


def augment_and_compute_features(*, work_dir: Path, out_dir: Path) -> None:
    """Run the per-subset augmentation pipeline + write feature .npys."""
    config = yaml.safe_load((work_dir / "my_model.yaml").read_text())
    feature_save_dir = out_dir / TARGET_WORD

    # Upstream's train.py computes total_length post-generate_clips and stuffs
    # it back into the config dict. Soft-fork skipped that hop, so we do it
    # here before any augment_clips call. Persist it so _custom_train_model
    # reads the same value on its own yaml reload.
    total_length = _compute_total_length(feature_save_dir / "positive_test")
    config["total_length"] = total_length
    (work_dir / "my_model.yaml").write_text(yaml.dump(config))
    print(
        f"=== total_length = {total_length} samples ({total_length / 16000:.2f}s) ===",
        flush=True,
    )

    # background_paths handling (mirrors upstream)
    bg_dup = config.get("background_paths_duplication_rate") or [1] * len(
        config["background_paths"]
    )
    if len(bg_dup) != len(config["background_paths"]):
        bg_dup = [1] * len(config["background_paths"])
    bg_paths: list[str] = []
    for path, rate in zip(config["background_paths"], bg_dup, strict=False):
        bg_paths.extend([i.path for i in os.scandir(path)] * rate)
    rir_paths = [i.path for j in config["rir_paths"] for i in os.scandir(j)]

    rounds = config["augmentation_rounds"]
    n_cpus = os.cpu_count() or 1
    ncpu = 1 if torch.cuda.is_available() else max(1, n_cpus // 2)
    device = "gpu" if torch.cuda.is_available() else "cpu"

    print("=== per-subset augmentation + feature compute (v8) ===", flush=True)
    for subset_name in SUBSETS:
        subset_dir = out_dir / TARGET_WORD / subset_name
        all_files = sorted(str(f) for f in subset_dir.glob("*.wav"))
        synth = [f for f in all_files if not is_real_audio(Path(f).name)]
        real = [f for f in all_files if is_real_audio(Path(f).name)]
        if not synth and not real:
            print(f"  {subset_name}: empty, skipping", flush=True)
            continue

        synth_input = synth * rounds
        real_input = real * rounds
        n_total = len(synth_input) + len(real_input)

        gens = []
        if synth_input:
            gens.append(
                augment_clips(
                    synth_input,
                    total_length=config["total_length"],
                    batch_size=config["augmentation_batch_size"],
                    augmentation_probabilities=DEFAULTS,
                    background_clip_paths=bg_paths,
                    RIR_paths=rir_paths,
                )
            )
        if real_input:
            gens.append(
                augment_clips(
                    real_input,
                    total_length=config["total_length"],
                    batch_size=config["augmentation_batch_size"],
                    augmentation_probabilities=REAL_AUDIO,
                    background_clip_paths=bg_paths,
                    RIR_paths=rir_paths,
                )
            )

        out_path = feature_save_dir / _features_filename(subset_name)
        print(
            f"  {subset_name}: {len(synth)} synth (×{rounds}, RIR=0.5) + "
            f"{len(real)} realroom (×{rounds}, RIR=0) → {out_path.name}",
            flush=True,
        )
        compute_features_from_generator(
            chain(*gens),
            n_total=n_total,
            clip_duration=config["total_length"],
            output_file=str(out_path),
            device=device,
            ncpu=ncpu,
        )
