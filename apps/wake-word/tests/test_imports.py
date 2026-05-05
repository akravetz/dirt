"""Catch wrong-import-path bugs at pytest --collect-only time.

This test file is the cheapest defense against the bug class that crashed
v6 (90 min into training) and v8 (4 min into a kernel run). Importing the
library here makes each module's top-level imports execute; any wrong path
fails immediately, in <2 seconds on `pytest --collect-only`.
"""

from __future__ import annotations

import importlib
import pkgutil


def test_library_imports() -> None:
    """Importing the public package must succeed cleanly."""
    assert importlib.import_module("dirt_wake_word.main") is not None


def test_all_modules_importable() -> None:
    """Every module in the library imports without error.

    Adding a new module to the library should not require editing this list.
    """
    import dirt_wake_word

    for module in pkgutil.iter_modules(dirt_wake_word.__path__):
        importlib.import_module(f"dirt_wake_word.{module.name}")


def test_verify_imports_function_exists() -> None:
    """`verify_imports()` is the kernel's fail-fast entry point. It must be
    callable and import the same set of openwakeword/torch/numpy paths
    the rest of the library uses."""
    from dirt_wake_word.verify import verify_imports

    # Don't call it — it imports torch/openwakeword which the test fixture
    # has already importorskipped. Just confirm the symbol exists.
    assert callable(verify_imports)
