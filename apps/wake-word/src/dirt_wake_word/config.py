"""Tunables + training-config builder.

All wake-word training knobs live in one place so tests can monkeypatch
them and so the experiment log entries can reference exact line numbers.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Tunables — mirror the @param sliders from the upstream Colab notebook
# ---------------------------------------------------------------------------

TARGET_WORD = "hey_claudia"
NUMBER_OF_EXAMPLES = 30_000
NUMBER_OF_TRAINING_STEPS = 20_000

# max_negative_weight floor. Critical knob: openwakeword's auto_train
# *automatically doubles* this value (up to twice) on FP/hour overshoot —
# but we soft-fork around auto_train, so this stays at the configured value.
# See wiki/wake-word-experiments.md for v5 collapse rationale.
FALSE_ACTIVATION_PENALTY = 500

# Currently unused (we replaced auto_train) but kept in YAML for upstream
# `--generate_clips` / `--augment_clips` shell-outs that read it.
TARGET_FP_PER_HOUR = 10.0

# Per-source duplication factors applied to files seeded into
# {positive,negative}_train/ before --generate_clips. The mmap dataloader
# samples files uniformly, so a clip present N times has N× pull on loss.
#
# Pool-share targeting: with 2000 clones × 1 + 18 realmic × 10, real-mic ≈
# 8 % of the duplicated positive pool. See wiki/wake-word-experiments.md v8.
CLONE_DUPLICATION = 1
NEIGHBOR_DUPLICATION = 1
REALMIC_POSITIVE_DUPLICATION = 10
REALMIC_NEGATIVE_DUPLICATION = 10
HARVESTED_DUPLICATION = 10


def build_config(
    *,
    work_dir: Path,
    out_dir: Path,
    expected_inputs: dict[str, Path],
) -> Path:
    """Build the openwakeword training YAML; return its path.

    Loads upstream's `examples/custom_model.yml` from the cloned openwakeword
    repo as a baseline, overrides every key we care about, writes
    `<work_dir>/my_model.yaml`.
    """
    base_yaml = work_dir / "openwakeword/examples/custom_model.yml"
    config = yaml.safe_load(base_yaml.read_text())

    config["target_phrase"] = [TARGET_WORD.replace("_", " ")]
    config["model_name"] = TARGET_WORD
    config["n_samples"] = NUMBER_OF_EXAMPLES
    config["n_samples_val"] = max(500, NUMBER_OF_EXAMPLES // 10)
    config["steps"] = NUMBER_OF_TRAINING_STEPS
    # NOTE: target_accuracy and target_recall are dead keys in upstream's
    # train.py — never read. The actual quality knob is target_fp_per_hour.
    config["output_dir"] = str(out_dir)
    config["max_negative_weight"] = FALSE_ACTIVATION_PENALTY
    config["target_false_positives_per_hour"] = TARGET_FP_PER_HOUR

    # v8 — rebalance batch composition. Upstream defaults
    #   ACAV100M_sample=1024, adversarial_negative=50, positive=50
    # mean only 50 positive gradient slots per batch. With real-mic at ~8 %
    # of the duplicated positive pool, each batch saw only ~4 real-mic
    # positives — too few for the recall-floor failure mode. v8 quadruples
    # per-batch positive slots.
    config["batch_n_per_class"] = {
        "ACAV100M_sample": 512,
        "adversarial_negative": 50,
        "positive": 200,
    }

    # Kaggle-mounted paths
    config["background_paths"] = [
        str(expected_inputs["audioset_16k"]),
        str(expected_inputs["fma"]),
    ]
    config["false_positive_validation_data_path"] = str(
        expected_inputs["validation_features"]
    )
    config["feature_data_files"] = {
        "ACAV100M_sample": str(expected_inputs["train_features"]),
    }
    config["rir_paths"] = [str(expected_inputs["custom_rirs"])]

    out_yaml = work_dir / "my_model.yaml"
    out_yaml.write_text(yaml.dump(config))
    print(f"Wrote training config -> {out_yaml}")
    return out_yaml
