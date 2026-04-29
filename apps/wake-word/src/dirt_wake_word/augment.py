"""Per-subset augmentation + feature compute (replaces upstream's --augment_clips).

For each of the 4 feature subsets (positive_train, negative_train,
positive_test, negative_test) we split files by filename prefix:

    synth (default):    Piper-generated UUIDs, synth_clone_*, synth_neighbor_*
    real-room recorded: realmic_*

Synth gets the default augmentation pipeline. Real-room recorded gets
Gain=1.0 only, every other prob 0. Reasoning:
- Spectral distortions (RIR / EQ / TanhDistortion / PitchShift / BandStopFilter
  / AddColoredNoise / AddBackgroundNoise) push the training distribution off
  the inference distribution (raw Jabra audio carries the deployment-room
  reverb already; mixing in another RIR is unphysical, and adding more bg
  noise on top of clips that already include ambient noise just spreads the
  positive class.
- Gain randomization is pure amplitude scaling — same waveform, different
  level. It DOES help generalization (mic distance, speech volume) without
  shifting the spectral distribution. v19 went too far by zeroing Gain too,
  which left the trainer with N exact-duplicate pairs of each clip per epoch
  (rounds=2) and the model overfit to those exact waveforms — held-out
  realmic recall dropped 36.8% (v17) → 23.7% (v19).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import wave
from datetime import UTC, datetime
from itertools import chain
from pathlib import Path

import numpy as np
import torch
import yaml
from openwakeword.data import augment_clips
from openwakeword.utils import compute_features_from_generator

from .config import (
    CLONE_DUPLICATION,
    NEIGHBOR_DUPLICATION,
    NUMBER_OF_EXAMPLES,
    NUMBER_OF_EXAMPLES_VAL,
    REALMIC_NEGATIVE_DUPLICATION,
    REALMIC_POSITIVE_DUPLICATION,
    TARGET_WORD,
)
from .paths import INPUT_ROOT
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
REAL_AUDIO = {**dict.fromkeys(DEFAULTS, 0.0), "Gain": 1.0}

# Bump this if the cache layout/contract changes (e.g. new .npy file
# added, or augment_clips behavior changes upstream).
# v3: realmic-neg files are no longer mixed into synth AddBackgroundNoise;
# they are training negatives only.
_CACHE_SCHEMA_VERSION = 3
_CACHE_ROOT = INPUT_ROOT / "dirt-wakeword-features-cache"


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


def _cache_inputs(*, total_length: int, config: dict) -> dict | None:
    """Build the cache-key payload, or None if MANIFEST is unavailable."""
    manifest_path = INPUT_ROOT / "MANIFEST.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    datasets = manifest.get("datasets") or {}
    mine = (datasets.get("dirt-wakeword-mine") or {}).get("content_hash")
    bg = (datasets.get("dirt-wakeword-bg") or {}).get("content_hash")
    if not mine or not bg:
        return None
    return {
        "schema_version": _CACHE_SCHEMA_VERSION,
        "mine_hash": mine,
        "bg_hash": bg,
        "n_samples": NUMBER_OF_EXAMPLES,
        "n_samples_val": NUMBER_OF_EXAMPLES_VAL,
        "target_phrase": TARGET_WORD.replace("_", " "),
        "duplication": {
            "clone": CLONE_DUPLICATION,
            "neighbor": NEIGHBOR_DUPLICATION,
            "realmic_pos": REALMIC_POSITIVE_DUPLICATION,
            "realmic_neg": REALMIC_NEGATIVE_DUPLICATION,
        },
        "augmentation_synth": DEFAULTS,
        "augmentation_real": REAL_AUDIO,
        "rounds": config.get("augmentation_rounds"),
        "batch_size": config.get("augmentation_batch_size"),
        "total_length": total_length,
    }


def _cache_key(inputs: dict) -> str:
    payload = json.dumps(inputs, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _link_or_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _restore_cache(key: str, feature_save_dir: Path) -> bool:
    cache_dir = _CACHE_ROOT / key
    if not (cache_dir / "cache-metadata.json").exists():
        return False
    expected = [_features_filename(s) for s in SUBSETS]
    if not all((cache_dir / fn).exists() for fn in expected):
        print(f"  augment cache key {key} matched but files incomplete — recomputing")
        return False
    feature_save_dir.mkdir(parents=True, exist_ok=True)
    for fn in expected:
        _link_or_copy(cache_dir / fn, feature_save_dir / fn)
    print(f"  augment cache HIT key={key}; hardlinked {len(expected)} feature files")
    return True


def _persist_cache(key: str, feature_save_dir: Path, inputs: dict) -> None:
    cache_dir = _CACHE_ROOT / key
    cache_dir.mkdir(parents=True, exist_ok=True)
    persisted = 0
    for s in SUBSETS:
        src = feature_save_dir / _features_filename(s)
        if not src.exists():
            continue
        _link_or_copy(src, cache_dir / src.name)
        persisted += 1
    (cache_dir / "cache-metadata.json").write_text(
        json.dumps(
            {"persisted_at": datetime.now(UTC).isoformat(), "inputs": inputs},
            indent=2,
            default=str,
        )
        + "\n"
    )
    print(f"  augment cache PERSIST key={key} ({persisted} files)")


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

    # Augment-feature cache: deterministic given (mine+bg content_hash from
    # MANIFEST, n_samples{,_val}, target_phrase, duplication factors,
    # augmentation config, rounds, batch_size, total_length). On hit,
    # hardlink the 4 .npy files in and skip the 22-min compute.
    cache_inputs = _cache_inputs(total_length=total_length, config=config)
    cache_key = _cache_key(cache_inputs) if cache_inputs else None
    if cache_key and _restore_cache(cache_key, feature_save_dir):
        return
    if not cache_key:
        print("  augment cache disabled (no MANIFEST or hashes missing)", flush=True)
    else:
        print(f"  augment cache MISS key={cache_key}; computing", flush=True)

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
    # CPU-bound audiomentations dominates wall time. ONNX (mel + embedding)
    # runs on GPU when available, leaving ~all CPUs free for augmentation.
    # Reserve 2 cores: main thread + GPU dispatch.
    ncpu = max(1, n_cpus - 2)
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
            f"  {subset_name}: {len(synth)} synth (×{rounds}, default aug) + "
            f"{len(real)} realroom (×{rounds}, gain-only) → {out_path.name}",
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

    if cache_key and cache_inputs is not None:
        _persist_cache(cache_key, feature_save_dir, cache_inputs)
