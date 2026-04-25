"""Fail-fast import verification.

Runs after install_dependencies() so a wrong import path / missing pin /
version mismatch crashes the kernel within seconds — not 90 minutes into a
training run. Adding a new lazy import elsewhere in the library? Add it here too.
"""
# ruff: noqa: F401 — unused-import is the point of this module; the imports
# exist so a wrong module path crashes here instead of 90 min into training.

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
            f"FATAL: required import failed after install_dependencies(): {e}\n"
            "Check that install_dependencies pinned all required packages and "
            "that the openwakeword module path is correct."
        )
    print("  all imports OK", flush=True)
