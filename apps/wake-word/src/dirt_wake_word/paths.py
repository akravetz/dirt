"""Trainer path discovery — input datasets and working scratch.

The trainer runs inside a Docker container on RunPod with a Network Volume
mounted at /workspace. Datasets are seeded under /workspace/input/ by
`scripts/runpod-seed-volume`; trainer scratch goes to /workspace/working/.
Roots are env-overridable so the smoke test can point them at tmp_path
fixtures (`scripts/smoke-trainer-image`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _root(env_name: str, default: str) -> Path:
    v = os.environ.get(env_name, "").strip()
    return Path(v) if v else Path(default)


INPUT_ROOT = _root("DIRT_WAKEWORD_INPUT", "/workspace/input")
WORKING_ROOT = _root("DIRT_WAKEWORD_WORKING", "/workspace/working")

# Cloned at Docker build time by apps/wake-word/docker/Dockerfile. Used by
# build_config (custom_model.yml baseline) and custom_train (train.py CLI
# shellout for --generate_clips).
OPENWAKEWORD_SOURCE = Path("/opt/openwakeword")


def find_dataset(slug: str) -> Path:
    """Return the mount path for a dataset under INPUT_ROOT/<slug>/.

    Doesn't check existence — `verify_inputs` does that and prints a tree
    on failure.
    """
    return INPUT_ROOT / slug


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

    The docker entrypoint copies the .onnx + report up to /workspace/out/
    after training so the orchestrator can SCP them off.
    """
    return WORKING_ROOT / "my_custom_model"


def verify_inputs(expected: dict[str, Path]) -> None:
    """Fail fast if any expected mount is missing."""
    missing = [name for name, p in expected.items() if not p.exists()]
    if not missing:
        print("All expected input mounts present.")
        return

    print(f"=== {INPUT_ROOT}/ tree (3 levels) ===", file=sys.stderr)
    if INPUT_ROOT.exists():
        for path in sorted(INPUT_ROOT.rglob("*")):
            rel = path.relative_to(INPUT_ROOT)
            if len(rel.parts) <= 3:
                print(f"  {rel}", file=sys.stderr)
    else:
        print("  (input root does not exist)", file=sys.stderr)
    print("=== expected mounts ===", file=sys.stderr)
    for name in missing:
        print(f"  MISSING: {name} -> {expected[name]}", file=sys.stderr)
    raise SystemExit(
        "One or more expected dataset mounts are missing. "
        "Re-run scripts/runpod-seed-volume to populate the volume."
    )
