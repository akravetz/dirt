"""Unit tests for `dirt_wake_word.paths`."""

from __future__ import annotations


def test_find_dataset_uses_input_root_first(fake_volume) -> None:
    """find_dataset should resolve to the standard /input/<slug>/ layout
    when that directory exists (the GPU-runtime layout)."""
    from dirt_wake_word.paths import find_dataset

    input_root, _ = fake_volume
    found = find_dataset("dirt-wakeword-mine")
    assert found == input_root / "dirt-wakeword-mine"


def test_find_dataset_uses_input_root_without_legacy_fallback(
    tmp_path, monkeypatch
) -> None:
    """The RunPod trainer uses the plain /input/<slug>/ layout only."""
    monkeypatch.setenv("DIRT_WAKEWORD_INPUT", str(tmp_path))
    monkeypatch.setenv("DIRT_WAKEWORD_WORKING", str(tmp_path / "work"))

    # Reload paths to pick up the env override
    import importlib

    import dirt_wake_word.paths

    importlib.reload(dirt_wake_word.paths)

    from dirt_wake_word.paths import find_dataset

    found = find_dataset("some-slug")
    assert found == tmp_path / "some-slug"


def test_expected_inputs_keys(fake_volume) -> None:
    """expected_inputs returns all the keys downstream code expects."""
    from dirt_wake_word.paths import expected_inputs

    keys = expected_inputs("hey_claudia").keys()
    assert {
        "voice_samples",
        "custom_rirs",
        "negatives_dir",
        "audioset_16k",
        "fma",
        "train_features",
        "validation_features",
        "validation_good",
        "validation_bad",
    } <= keys


def test_verify_inputs_passes_when_all_mounted(fake_volume) -> None:
    """The fake_volume fixture creates all expected inputs; verify_inputs
    should not raise."""
    from dirt_wake_word.paths import expected_inputs, verify_inputs

    inputs = expected_inputs("hey_claudia")
    verify_inputs(inputs)  # should not raise


def test_verify_inputs_exits_on_missing(fake_volume, tmp_path) -> None:
    """verify_inputs should sys.exit when an expected mount is missing."""
    import pytest

    from dirt_wake_word.paths import verify_inputs

    fake_inputs = {
        "missing_dataset": tmp_path / "definitely-not-here",
    }
    with pytest.raises(SystemExit):
        verify_inputs(fake_inputs)
