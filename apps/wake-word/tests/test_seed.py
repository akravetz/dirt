"""Unit tests for `dirt_wake_word.seed`.

`seed_dir` and `prepare_seed_clips` are pure-Python (no openwakeword
dependency) — they just shuffle WAV files between directories with
duplication. Easy to test in isolation.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(np.zeros(800, dtype=np.int16).tobytes())


def test_seed_dir_writes_n_dup_copies(tmp_path: Path) -> None:
    """Each source file should produce exactly n_dup files in dest_dir."""
    from dirt_wake_word.seed import seed_dir

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    dst_dir = tmp_path / "dst"
    dst_dir.mkdir()

    src_files = []
    for i in range(3):
        p = src_dir / f"clip_{i}.wav"
        _write_wav(p)
        src_files.append(p)

    n = seed_dir(src_files, dst_dir, prefix="prefix_", n_dup=4)
    assert n == 12  # 3 files × 4 dup
    out_files = sorted(dst_dir.glob("*.wav"))
    assert len(out_files) == 12
    # Every output starts with the prefix
    assert all(p.name.startswith("prefix_") for p in out_files)


def test_seed_dir_n_dup_one_no_suffix(tmp_path: Path) -> None:
    """When n_dup=1 there should be no `_dupN` suffix on filenames."""
    from dirt_wake_word.seed import seed_dir

    src = tmp_path / "src.wav"
    _write_wav(src)
    dst = tmp_path / "dst"
    dst.mkdir()

    seed_dir([src], dst, prefix="x_", n_dup=1)
    files = list(dst.glob("*.wav"))
    assert len(files) == 1
    assert files[0].name == "x_src.wav"  # no _dup0


def test_prepare_seed_clips_splits_by_prefix(fake_volume, monkeypatch) -> None:
    """realmic-pos clips go through realmic_pos_ prefix + 10× dup; clones
    go through synth_clone_ prefix + 1× dup. Same for negatives."""
    from dirt_wake_word.paths import expected_inputs, out_dir
    from dirt_wake_word.seed import prepare_seed_clips

    inputs = expected_inputs("hey_claudia")
    out = out_dir()

    counts = prepare_seed_clips(out_dir=out, expected_inputs=inputs)

    # Fake Kaggle has: 5 synth clones × 1 + 2 realmic_pos × 10 = 25
    assert counts["clones"] == 5
    assert counts["realmic_pos"] == 20

    # Negatives: 5 synth + 2 realmic-neg × 10
    assert counts["synth_neg"] == 5
    assert counts["realmic_neg"] == 20
    assert counts["harvested"] == 0  # no harvested in fake Kaggle yet

    # Verify on disk
    pos_train = out / "hey_claudia" / "positive_train"
    neg_train = out / "hey_claudia" / "negative_train"
    pos_files = sorted(p.name for p in pos_train.glob("*.wav"))
    neg_files = sorted(p.name for p in neg_train.glob("*.wav"))

    assert sum(1 for n in pos_files if n.startswith("synth_clone_")) == 5
    assert sum(1 for n in pos_files if n.startswith("realmic_pos_")) == 20
    assert sum(1 for n in neg_files if n.startswith("synth_neighbor_")) == 5
    assert sum(1 for n in neg_files if n.startswith("realmic_neg_")) == 20
