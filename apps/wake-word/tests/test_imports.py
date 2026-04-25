"""Catch wrong-import-path bugs at pytest --collect-only time.

This test file is the cheapest defense against the bug class that crashed
v6 (90 min into training) and v8 (4 min into a kernel run). Importing the
library here makes each module's top-level imports execute; any wrong path
fails immediately, in <2 seconds on `pytest --collect-only`.
"""

from __future__ import annotations


def test_library_imports() -> None:
    """Importing the public package must succeed cleanly."""
    import dirt_wake_word

    assert hasattr(dirt_wake_word, "main")


def test_all_modules_importable() -> None:
    """Every module in the library imports without error.

    Adding a new module to the library? Add it here too.
    """
    from dirt_wake_word import (  # noqa: F401
        augment,
        config,
        export,
        main,
        paths,
        seed,
        select,
        timing,
        train,
        tts_cache,
        validate,
        verify,
    )


def test_verify_imports_function_exists() -> None:
    """`verify_imports()` is the kernel's fail-fast entry point. It must be
    callable and import the same set of openwakeword/torch/numpy paths
    the rest of the library uses."""
    from dirt_wake_word.verify import verify_imports

    # Don't call it — it imports torch/openwakeword which the test fixture
    # has already importorskipped. Just confirm the symbol exists.
    assert callable(verify_imports)
