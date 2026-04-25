"""Kaggle path discovery + EXPECTED_INPUTS mapping.

All paths are env-overridable so the test suite can point them at a
tmp_path-backed fake `/kaggle/input/` and `/kaggle/working/` tree:

    DIRT_KAGGLE_INPUT    overrides /kaggle/input
    DIRT_KAGGLE_WORKING  overrides /kaggle/working
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

KAGGLE_INPUT = Path(os.environ.get("DIRT_KAGGLE_INPUT", "/kaggle/input"))
KAGGLE_WORKING = Path(os.environ.get("DIRT_KAGGLE_WORKING", "/kaggle/working"))


def find_dataset(slug: str, owner: str = "akravetz") -> Path:
    """Return the mount path for a Kaggle dataset, probing both possible layouts.

    GPU/CPU runtimes mount at /kaggle/input/<slug>/.
    TPU runtime mounts at /kaggle/input/datasets/<owner>/<slug>/.
    Returns the first candidate that exists; if neither does, returns the
    primary candidate (caller's `verify_inputs` will print a useful tree).
    """
    candidates = [
        KAGGLE_INPUT / slug,
        KAGGLE_INPUT / "datasets" / owner / slug,
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def expected_inputs(target_word: str) -> dict[str, Path]:
    """Build the EXPECTED_INPUTS dict for the given target word."""
    mine = find_dataset("dirt-wakeword-mine")
    bg = find_dataset("dirt-wakeword-bg")
    features = find_dataset("dirt-wakeword-features")
    validation = find_dataset("dirt-wakeword-validation")
    return {
        "voice_samples": mine / "voice_samples",
        "custom_rirs": mine / "rirs",
        "negatives_dir": mine / "negatives",
        "audioset_16k": bg / "audioset_16k",
        "fma": bg / "fma",
        "train_features": features
        / "openwakeword_features_ACAV100M_2000_hrs_16bit.npy",
        "validation_features": features / "validation_set_features.npy",
        "validation_good": validation / "good",
        "validation_bad": validation / "bad",
    }


def out_dir() -> Path:
    """Where trained model artifacts get written. Auto-published by Kaggle."""
    return KAGGLE_WORKING / "my_custom_model"


def verify_inputs(expected: dict[str, Path]) -> None:
    """Fail fast if any expected mount is missing."""
    missing = [name for name, p in expected.items() if not p.exists()]
    if missing:
        print("=== /kaggle/input/ tree (3 levels) ===", file=sys.stderr)
        if KAGGLE_INPUT.exists():
            for path in sorted(KAGGLE_INPUT.rglob("*")):
                rel = path.relative_to(KAGGLE_INPUT)
                if len(rel.parts) <= 3:
                    print(f"  {rel}", file=sys.stderr)
        else:
            print("  (input root does not exist)", file=sys.stderr)
        print("=== expected mounts ===", file=sys.stderr)
        for name in missing:
            print(f"  MISSING: {name} -> {expected[name]}", file=sys.stderr)
        raise SystemExit(
            "One or more expected Kaggle dataset mounts are missing. "
            "Check kernel-metadata.json `dataset_sources` and dataset contents."
        )
    print("All expected input mounts present.")
