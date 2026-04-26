"""Trainer path discovery — input datasets and working scratch.

Two runtimes:
  - RunPod (primary): a Network Volume mounts at /workspace, with seeded
    datasets at /workspace/input/<slug>/ and trainer scratch at
    /workspace/working/.
  - Legacy Kaggle kernel: /kaggle/input + /kaggle/working.

Roots are env-overridable so the smoke test can point them at tmp_path
fixtures. Both env-var names accept either prefix; new code should use
DIRT_WAKEWORD_*, but the older DIRT_KAGGLE_* names work for the Kaggle
shim until that path is retired (see wiki/decisions/2026-04-25-runpod-migration.md).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _root(*env_names: str, default: str) -> Path:
    """First non-empty env value, else default."""
    for name in env_names:
        v = os.environ.get(name, "").strip()
        if v:
            return Path(v)
    return Path(default)


# DIRT_KAGGLE_* names retained as fallbacks for the legacy shim.
KAGGLE_INPUT = _root(
    "DIRT_WAKEWORD_INPUT", "DIRT_KAGGLE_INPUT", default="/kaggle/input"
)
KAGGLE_WORKING = _root(
    "DIRT_WAKEWORD_WORKING", "DIRT_KAGGLE_WORKING", default="/kaggle/working"
)


def _first_existing(candidates: list[Path]) -> Path | None:
    for c in candidates:
        if c.exists():
            return c
    return None


def find_openwakeword_source() -> Path:
    """Locate the cloned openwakeword source repo (used by build_config + train).

    RunPod: cloned at Docker build time into /opt/openwakeword/.
    Kaggle: cloned by the kernel shim into /kaggle/working/openwakeword/.
    """
    candidates = [Path("/opt/openwakeword"), KAGGLE_WORKING / "openwakeword"]
    found = _first_existing(candidates)
    if found is None:
        raise FileNotFoundError(
            f"openwakeword source repo not found in any of: {candidates}"
        )
    return found


def find_dataset(slug: str, owner: str = "akravetz") -> Path:
    """Return the mount path for a dataset, probing both Kaggle layouts.

    Standard layout (RunPod + Kaggle GPU/CPU): <input>/<slug>/.
    Legacy Kaggle TPU layout: <input>/datasets/<owner>/<slug>/.
    Returns the first candidate that exists; falls back to the primary so
    `verify_inputs` can print a useful diagnostic.
    """
    candidates = [KAGGLE_INPUT / slug, KAGGLE_INPUT / "datasets" / owner / slug]
    return _first_existing(candidates) or candidates[0]


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
    """Trainer artifact root — written under <working>/my_custom_model/.

    On RunPod the entrypoint copies the .onnx + report up to /workspace/out/
    after training. On Kaggle, files here are auto-published as kernel output.
    """
    return KAGGLE_WORKING / "my_custom_model"


def verify_inputs(expected: dict[str, Path]) -> None:
    """Fail fast if any expected mount is missing."""
    missing = [name for name, p in expected.items() if not p.exists()]
    if not missing:
        print("All expected input mounts present.")
        return

    print(f"=== {KAGGLE_INPUT}/ tree (3 levels) ===", file=sys.stderr)
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
        "One or more expected dataset mounts are missing. "
        "On RunPod, re-run scripts/runpod-seed-volume; "
        "on Kaggle, check kernel-metadata.json dataset_sources."
    )
