"""Seed user-provided WAVs into openwakeword's pre-train directories.

openwakeword has NO config key for user-provided positive or negative WAVs.
The canonical injection is to drop files into
`<output_dir>/<model_name>/{positive,negative}_train/` BEFORE running
`--generate_clips` — upstream's `--generate_clips` then sees `len(...) >=
0.95 * n_samples` and either skips TTS or tops up the rest.

The filename prefixes here (synth_clone_, realmic_pos_, etc.) are the
contract that augment.py reads to pick the per-subset augmentation
pipeline. The canonical list lives in `subsets.py`.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from .config import (
    CLONE_DUPLICATION,
    NEIGHBOR_DUPLICATION,
    REALMIC_NEGATIVE_DUPLICATION,
    REALMIC_POSITIVE_DUPLICATION,
    TARGET_WORD,
)
from .subsets import (
    PREFIX_REALMIC_NEG,
    PREFIX_REALMIC_POS,
    PREFIX_SYNTH_CLONE,
    PREFIX_SYNTH_NEIGHBOR,
)


def _link_dup(src: Path, dst: Path) -> None:
    """Hardlink src→dst (cheap on the same fs); fall back to copy on EXDEV."""
    try:
        if dst.exists():
            dst.unlink()
        os.link(src, dst)
    except OSError:
        import shutil

        shutil.copy(src, dst)


def seed_dir(
    src_files: Iterable[Path],
    dest_dir: Path,
    prefix: str,
    n_dup: int,
) -> int:
    """Hardlink each source into dest_dir n_dup times with `prefix` filename.

    Returns the number of files written (= len(src_files) × n_dup).
    Always uses a `_dupN` suffix so re-runs with a different `n_dup` produce
    consistent filenames.
    """
    written = 0
    for src in src_files:
        for i in range(n_dup):
            _link_dup(src, dest_dir / f"{prefix}{src.stem}_dup{i}.wav")
            written += 1
    return written


def prepare_seed_clips(
    *,
    out_dir: Path,
    expected_inputs: dict[str, Path],
) -> dict[str, int]:
    """Seed positive_train/ + negative_train/ with all our user-provided WAVs.

    All realmic and synth seeds go to *_train. The per-epoch *_test sets
    are filled by upstream's `--generate_clips` (Piper TTS) — synth-only
    test signal is what v17/v20 selected against and they had clean lab
    precision. v21 added a real-mic test signal here and the best-checkpoint
    selector started picking real-mic-permissive checkpoints that fired
    on the lab 76-bad set; reverted in v22.

    Returns a dict of post-duplication counts for logging.
    """
    pos_train = out_dir / TARGET_WORD / "positive_train"
    neg_train = out_dir / TARGET_WORD / "negative_train"
    pos_train.mkdir(parents=True, exist_ok=True)
    neg_train.mkdir(parents=True, exist_ok=True)

    pos_src = expected_inputs["voice_samples"]
    realmic_pos_files = sorted(pos_src.glob("realmic-pos_*.wav"))
    synth_clone_files = [
        p
        for p in sorted(pos_src.glob("*.wav"))
        if not p.name.startswith("realmic-pos_")
    ]
    n_clones = seed_dir(
        synth_clone_files, pos_train, PREFIX_SYNTH_CLONE, CLONE_DUPLICATION
    )
    n_realmic_pos = seed_dir(
        realmic_pos_files, pos_train, PREFIX_REALMIC_POS, REALMIC_POSITIVE_DUPLICATION
    )

    n_synth = n_realmic_neg = 0
    neg_src = expected_inputs["negatives_dir"]
    if neg_src.exists():
        all_negs = sorted(neg_src.glob("*.wav"))
        realmic_neg = [p for p in all_negs if p.name.startswith("realmic-neg_")]
        synthetic = [p for p in all_negs if not p.name.startswith("realmic-neg_")]
        n_synth = seed_dir(
            synthetic, neg_train, PREFIX_SYNTH_NEIGHBOR, NEIGHBOR_DUPLICATION
        )
        n_realmic_neg = seed_dir(
            realmic_neg, neg_train, PREFIX_REALMIC_NEG, REALMIC_NEGATIVE_DUPLICATION
        )

    print(
        f"Seeded positives: {n_clones} synth-clone (×{CLONE_DUPLICATION}) "
        f"+ {n_realmic_pos} realmic-pos (×{REALMIC_POSITIVE_DUPLICATION}) "
        f"= {n_clones + n_realmic_pos} total"
    )
    print(
        f"Seeded negatives: {n_synth} synth-neighbor (×{NEIGHBOR_DUPLICATION}) "
        f"+ {n_realmic_neg} realmic-neg (×{REALMIC_NEGATIVE_DUPLICATION}) "
        f"= {n_synth + n_realmic_neg} total"
    )
    return {
        "clones": n_clones,
        "realmic_pos": n_realmic_pos,
        "synth_neg": n_synth,
        "realmic_neg": n_realmic_neg,
    }
