"""Pytest fixtures for the wake-word library.

Strategy:
- `pytest.importorskip("openwakeword")` on collection, so a fresh checkout
  without the [wake-word] extra installed reports tests as skipped rather
  than failing collection.
- `fake_kaggle` fixture: tmp_path-backed `/kaggle/input/` and
  `/kaggle/working/` trees with a tiny corpus (5 voice clones, 2 RIRs,
  100-clip background, 4 validation clips). Tests can run end-to-end on
  CPU in <3 minutes against this rather than the real ~17 GB datasets.
- The `dirt_wake_word.paths` module reads `DIRT_KAGGLE_INPUT` /
  `DIRT_KAGGLE_WORKING` env vars; the fixture monkeypatches them so the
  library behaves identically to a real Kaggle run, just against tmp paths.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import pytest

# Skip the entire wake-word test directory when the heavy ML stack isn't
# installed. Run `uv sync --extra wake-word` to enable. Module-level
# `pytest.importorskip` crashes pytest's plugin init; `collect_ignore_glob`
# is the canonical opt-out for "test deps not available."
try:
    import numpy  # noqa: F401
    import openwakeword  # noqa: F401
    import torch  # noqa: F401

    collect_ignore_glob: list[str] = []
except ImportError:
    collect_ignore_glob = ["test_*.py"]

# When deps are present, conftest body continues and provides the fixture.
# When deps are missing, collect_ignore_glob skips test files entirely.
import numpy as np

SR = 16000


def _write_silent_wav(path: Path, duration_s: float = 1.5) -> None:
    """Write a silent 16-kHz mono WAV at the given path."""
    n_samples = int(duration_s * SR)
    data = np.zeros(n_samples, dtype=np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def _write_noisy_wav(
    path: Path, duration_s: float = 1.5, amplitude: int = 1000
) -> None:
    """Write a noise-filled WAV (so RMS analysis doesn't trip on pure silence)."""
    n_samples = int(duration_s * SR)
    rng = np.random.default_rng(42)
    data = rng.integers(-amplitude, amplitude, size=n_samples, dtype=np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


@pytest.fixture
def fake_kaggle(tmp_path, monkeypatch):
    """Mock the Kaggle environment.

    Layout:
        tmp_path/
            input/                     # mounted read-only datasets
                dirt-wakeword-mine/
                    voice_samples/      (5 clones + 2 realmic-pos)
                    rirs/               (2 RIRs)
                    negatives/          (5 synth + 2 realmic-neg)
                dirt-wakeword-bg/
                    audioset_16k/       (50 noisy WAVs)
                    fma/                (50 noisy WAVs)
                dirt-wakeword-features/ (.npy files; written by tests as needed)
                dirt-wakeword-validation/
                    good/               (4 noisy WAVs)
                    bad/                (4 noisy WAVs)
            working/                   # writable scratch
                my_custom_model/
                openwakeword/          # placeholder so build_config can find YAML

    Yields a (input_root, working_root) tuple. The library's paths module
    is monkeypatched to read these via env vars, so no production code
    needs to be aware of the mock.
    """
    input_root = tmp_path / "input"
    working_root = tmp_path / "working"
    input_root.mkdir()
    working_root.mkdir()

    # Datasets
    mine = input_root / "dirt-wakeword-mine"
    (mine / "voice_samples").mkdir(parents=True)
    (mine / "rirs").mkdir()
    (mine / "negatives").mkdir()

    # 5 synthetic clones + 2 realmic-pos
    for i in range(5):
        _write_noisy_wav(
            mine / "voice_samples" / f"hey_claudia_{i:03d}.wav", amplitude=2000
        )
    for i in range(2):
        _write_noisy_wav(
            mine / "voice_samples" / f"realmic-pos_{i:03d}.wav", amplitude=2000
        )

    # 2 RIRs
    for i in range(2):
        _write_noisy_wav(mine / "rirs" / f"pos_{i}.wav", duration_s=0.2, amplitude=4000)

    # 5 synth neighbors + 2 realmic-neg
    for i in range(5):
        _write_noisy_wav(mine / "negatives" / f"hey_clyde_{i:03d}.wav", amplitude=2000)
    for i in range(2):
        _write_noisy_wav(
            mine / "negatives" / f"realmic-neg_{i:03d}.wav", amplitude=2000
        )

    bg = input_root / "dirt-wakeword-bg"
    (bg / "audioset_16k").mkdir(parents=True)
    (bg / "fma").mkdir()
    for i in range(50):
        _write_noisy_wav(bg / "audioset_16k" / f"as_{i:03d}.wav", duration_s=2.0)
        _write_noisy_wav(bg / "fma" / f"fma_{i:03d}.wav", duration_s=2.0)

    features = input_root / "dirt-wakeword-features"
    features.mkdir()
    # Write tiny .npy stubs — full smoke test will overwrite or skip the
    # phases that need them. Real openwakeword features are 16-frame, 96-dim.
    np.save(
        features / "openwakeword_features_ACAV100M_2000_hrs_16bit.npy",
        np.zeros((1000, 96), dtype=np.float32),
    )
    np.save(
        features / "validation_set_features.npy",
        np.zeros((1000, 96), dtype=np.float32),
    )

    validation = input_root / "dirt-wakeword-validation"
    (validation / "good").mkdir(parents=True)
    (validation / "bad").mkdir()
    for i in range(4):
        _write_noisy_wav(validation / "good" / f"good_{i:03d}.wav")
        _write_noisy_wav(validation / "bad" / f"bad_{i:03d}.wav")

    # Working dir
    (working_root / "my_custom_model").mkdir()

    monkeypatch.setenv("DIRT_KAGGLE_INPUT", str(input_root))
    monkeypatch.setenv("DIRT_KAGGLE_WORKING", str(working_root))
    # paths module reads env at import time — must reload to pick up changes.
    for mod_name in [m for m in list(sys.modules) if m.startswith("dirt_wake_word")]:
        del sys.modules[mod_name]

    yield input_root, working_root
