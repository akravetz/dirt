"""Fail-fast import verification.

Runs after install_dependencies() so a wrong import path / missing pin /
version mismatch crashes the kernel within seconds — not 90 minutes into a
training run. Adding a new lazy import elsewhere in the library? Add it here too.
"""

from __future__ import annotations

import sys


def verify_imports() -> None:
    """Try every deferred import we use. Sys-exit on failure."""
    print("=== verifying deferred imports", flush=True)
    try:
        import numpy as _np  # noqa: F401
        import torch as _torch  # noqa: F401
        from openwakeword.data import (  # noqa: F401
            augment_clips as _augment_clips,
        )
        from openwakeword.data import (
            mmap_batch_generator as _mmap_batch_generator,
        )
        from openwakeword.model import Model as _InferenceModel  # noqa: F401
        from openwakeword.train import Model as _TrainingModel  # noqa: F401
        from openwakeword.utils import (  # noqa: F401
            compute_features_from_generator as _compute_features_from_generator,
        )
    except ImportError as e:
        sys.exit(
            f"FATAL: required import failed after install_dependencies(): {e}\n"
            "Check that install_dependencies pinned all required packages and "
            "that the openwakeword module path is correct."
        )
    print("  all imports OK", flush=True)
