"""Seed user-provided WAVs into openwakeword's pre-train directories.

openwakeword has NO config key for user-provided positive or negative WAVs.
The canonical injection is to drop files into
`<output_dir>/<model_name>/{positive,negative}_train/` BEFORE running
`--generate_clips` — upstream's `--generate_clips` then sees `len(...) >=
0.95 * n_samples` and either skips TTS or tops up the rest.

Naming convention (matters for the per-subset augmentation in augment.py):
    positive_train/synth_clone_<orig>.wav      ElevenLabs voice clones
    positive_train/realmic_pos_<orig>.wav      Hand-recorded "hey claudia"
    negative_train/synth_neighbor_<orig>.wav   ElevenLabs phonetic neighbors
    negative_train/realmic_neg_<orig>.wav      Hand-recorded non-wake phrases
    negative_train/harvested_<orig>.wav        Real var/logs/wake_audio/ captures
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

from .config import (
    CLONE_DUPLICATION,
    HARVESTED_DUPLICATION,
    NEIGHBOR_DUPLICATION,
    REALMIC_NEGATIVE_DUPLICATION,
    REALMIC_POSITIVE_DUPLICATION,
    TARGET_WORD,
)


def seed_dir(
    src_files: Iterable[Path],
    dest_dir: Path,
    prefix: str,
    n_dup: int,
) -> int:
    """Copy each source file into dest_dir n_dup times with `prefix` filename.

    Returns the number of files written (= len(src_files) × n_dup).
    """
    written = 0
    for src in src_files:
        for i in range(n_dup):
            suffix = f"_dup{i}" if n_dup > 1 else ""
            shutil.copy(src, dest_dir / f"{prefix}{src.stem}{suffix}.wav")
            written += 1
    return written


def prepare_seed_clips(
    *,
    out_dir: Path,
    expected_inputs: dict[str, Path],
) -> dict[str, int]:
    """Seed positive_train/ + negative_train/ with all our user-provided WAVs.

    Returns a dict of counts (after duplication) for logging:
      {clones, realmic_pos, synth_neg, realmic_neg, harvested}
    """
    pos_train = out_dir / TARGET_WORD / "positive_train"
    neg_train = out_dir / TARGET_WORD / "negative_train"
    pos_train.mkdir(parents=True, exist_ok=True)
    neg_train.mkdir(parents=True, exist_ok=True)

    # ---- Positives: split synthetic-clone from real-mic by filename prefix ----
    pos_src = expected_inputs["voice_samples"]
    realmic_pos_files = sorted(pos_src.glob("realmic-pos_*.wav"))
    synth_clone_files = [
        p
        for p in sorted(pos_src.glob("*.wav"))
        if not p.name.startswith("realmic-pos_")
    ]
    n_clones = seed_dir(synth_clone_files, pos_train, "synth_clone_", CLONE_DUPLICATION)
    n_realmic_pos = seed_dir(
        realmic_pos_files, pos_train, "realmic_pos_", REALMIC_POSITIVE_DUPLICATION
    )

    # ---- Negatives: split synthetic / realmic / harvested by filename prefix ----
    neg_src = expected_inputs["negatives_dir"]
    n_synth = n_realmic_neg = n_harv = 0
    if neg_src.exists():
        all_negs = sorted(neg_src.glob("*.wav"))
        harvested = [p for p in all_negs if p.name.startswith("harvested_")]
        realmic_neg = [p for p in all_negs if p.name.startswith("realmic-neg_")]
        synthetic = [
            p
            for p in all_negs
            if not p.name.startswith("harvested_")
            and not p.name.startswith("realmic-neg_")
        ]
        n_synth = seed_dir(
            synthetic, neg_train, "synth_neighbor_", NEIGHBOR_DUPLICATION
        )
        n_realmic_neg = seed_dir(
            realmic_neg, neg_train, "realmic_neg_", REALMIC_NEGATIVE_DUPLICATION
        )
        n_harv = seed_dir(harvested, neg_train, "harvested_", HARVESTED_DUPLICATION)

    print(
        f"Seeded positives: {n_clones} synth-clone (×{CLONE_DUPLICATION}) "
        f"+ {n_realmic_pos} realmic-pos (×{REALMIC_POSITIVE_DUPLICATION}) "
        f"= {n_clones + n_realmic_pos} total"
    )
    print(
        f"Seeded negatives: {n_synth} synth-neighbor (×{NEIGHBOR_DUPLICATION}) "
        f"+ {n_realmic_neg} realmic-neg (×{REALMIC_NEGATIVE_DUPLICATION}) "
        f"+ {n_harv} harvested (×{HARVESTED_DUPLICATION}) "
        f"= {n_synth + n_realmic_neg + n_harv} total"
    )
    return {
        "clones": n_clones,
        "realmic_pos": n_realmic_pos,
        "synth_neg": n_synth,
        "realmic_neg": n_realmic_neg,
        "harvested": n_harv,
    }
