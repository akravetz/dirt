"""Fail-fast import verification.

Hits every transitive openwakeword + torch import the library uses, so a
bad pin / wrong module path / missing dep dies in seconds instead of 90 min
into training. The Dockerfile's build-time `python -c "from
dirt_wake_word.main import main"` smoke test covers the same ground at
build time; `verify_imports()` is the runtime backstop. Adding a new lazy
import to a sibling module? Add it here too.
"""
# ruff: noqa: F401 — unused-import is the point; aliasing forces resolution.

from __future__ import annotations

import sys


def verify_imports() -> None:
    """Try every deferred import we use. Sys-exit on failure."""
    print("=== verifying deferred imports", flush=True)
    try:
        import numpy as _np
        import torch as _torch
        from openwakeword.data import augment_clips as _augment_clips
        from openwakeword.data import mmap_batch_generator as _mmap_batch_generator
        from openwakeword.model import Model as _InferenceModel
        from openwakeword.train import Model as _TrainingModel
        from openwakeword.utils import (
            compute_features_from_generator as _compute_features_from_generator,
        )
    except ImportError as e:
        sys.exit(
            f"FATAL: required import failed: {e}\n"
            "On RunPod this means the Docker image is missing a pin — check "
            "apps/wake-word/docker/Dockerfile's pip install. On Kaggle, check "
            "the kernel shim's install_dependencies()."
        )
    print("  all imports OK", flush=True)
