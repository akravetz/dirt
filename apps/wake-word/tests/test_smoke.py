"""End-to-end smoke test: tiny data, real openwakeword, CPU, <5 min.

Marked `@pytest.mark.smoke` so pre-commit doesn't run it on every commit
(too slow for that). Run via `uv run pytest -m smoke apps/wake-word/tests`
or as a pre-flight gate in `scripts/kaggle-train`.

This catches the entire class of "training runs but produces a degenerate
model" bugs (loss-sign flips, label-mapping inversions, optimizer
misconfiguration) that pure import tests miss. v5's first run produced a
21% recall model that took 90 min to find out about — a ~3 min smoke test
on equivalent (but tiny) inputs would have failed in seconds.

Currently a placeholder — needs n_samples-overrideable hooks in
config.py + main.py to be fully wired (deferred to a follow-up commit so
the test infrastructure lands first).
"""

from __future__ import annotations

import pytest


@pytest.mark.smoke
@pytest.mark.skip(
    reason="Smoke harness pending — needs n_samples/steps overrides on main()."
)
def test_train_smoke(fake_kaggle) -> None:
    """End-to-end: run main() with tiny data, assert .onnx is produced.

    Skipped pending a follow-up commit that adds:
      - `dirt_wake_word.config.NUMBER_OF_EXAMPLES` env-var override
      - `dirt_wake_word.main.main(skip_install=...)` parameter so we can
        bypass install_dependencies (which is in the kernel shim, not
        the library — but main currently doesn't try to install)
      - A real openwakeword end-to-end run on ~50 samples × 20 steps
    """
    from dirt_wake_word.main import main

    main()  # would assert that .onnx was produced
