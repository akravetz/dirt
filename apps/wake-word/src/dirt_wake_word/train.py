"""Soft-fork training driver — bypass auto_train, single train_model() pass.

Reasons we don't shell out to upstream's --train_model:

1. auto_train's `self.best_val_fp = 1000` initialization + never-updated
   makes the FP/hr escalation always fire twice → max_negative_weight ends
   up 4× whatever we configured.
2. auto_train ends with a broken onnx_tf-based ONNX→tflite step.
3. We want real-audio F1 against `var/wake-word/validation/` as the
   canonical metric, not synthetic Piper-test recall.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import torch
import yaml
from openwakeword.data import mmap_batch_generator
from openwakeword.train import Model

from .augment import augment_and_compute_features
from .paths import (
    expected_inputs as _expected_inputs_for_validation,
)
from .paths import (
    find_openwakeword_source,
)
from .select import select_best_by_real_f1
from .timing import phase, sh
from .tts_cache import restore_tts_cache_if_mounted


def custom_train(
    *,
    config_path: Path,
    work_dir: Path,
    out_dir: Path,
    target_word: str,
) -> None:
    """End-to-end training: TTS-cache restore → generate → augment → train."""
    train_py = find_openwakeword_source() / "openwakeword/train.py"
    with phase("restore_tts_cache"):
        restore_tts_cache_if_mounted(out_dir)
    with phase("generate_clips"):
        sh(
            f"{sys.executable} {train_py} --training_config {config_path} --generate_clips"
        )
    with phase("augment+features"):
        augment_and_compute_features(work_dir=work_dir, out_dir=out_dir)
    with phase("train_loop"):
        _custom_train_model(work_dir=work_dir, out_dir=out_dir, target_word=target_word)


def _custom_train_model(*, work_dir: Path, out_dir: Path, target_word: str) -> None:
    """The soft-fork meat: replace upstream's --train_model __main__ block."""
    config = yaml.safe_load((work_dir / "my_model.yaml").read_text())
    feature_save_dir = out_dir / target_word

    input_shape = np.load(feature_save_dir / "positive_features_test.npy").shape[1:]

    oww = Model(
        n_classes=1,
        input_shape=input_shape,
        model_type=config["model_type"],
        layer_dim=config["layer_size"],
        seconds_per_example=1280 * input_shape[0] / 16000,
    )

    # ---- X_train: IterDataset over mmap'd feature files (mirrors upstream) ----
    def reshape_neg(x, n=input_shape[0]):
        if n != x.shape[1]:
            x = np.vstack(x)
            return np.array([x[i : i + n, :] for i in range(0, x.shape[0] - n, n)])
        return x

    data_transforms = {key: reshape_neg for key in config["feature_data_files"]}
    label_transforms = {
        key: (lambda x, k=key: [1 if k == "positive" else 0 for _ in x])
        for key in (
            ["positive"] + list(config["feature_data_files"]) + ["adversarial_negative"]
        )
    }

    feature_data_files = dict(config["feature_data_files"])
    feature_data_files["positive"] = str(
        feature_save_dir / "positive_features_train.npy"
    )
    feature_data_files["adversarial_negative"] = str(
        feature_save_dir / "negative_features_train.npy"
    )

    batch_generator = mmap_batch_generator(
        feature_data_files,
        n_per_class=config["batch_n_per_class"],
        data_transform_funcs=data_transforms,
        label_transform_funcs=label_transforms,
    )

    class IterDataset(torch.utils.data.IterableDataset):
        def __init__(self, gen):
            self.gen = gen

        def __iter__(self):
            return self.gen

    n_cpus = os.cpu_count() or 1
    n_cpus = max(1, n_cpus // 2)
    X_train = torch.utils.data.DataLoader(
        IterDataset(batch_generator),
        batch_size=None,
        num_workers=n_cpus,
        prefetch_factor=16,
    )

    # X_val_fp: 11.3 h ACAV speech, FP/hour metric
    X_val_fp_arr = np.load(config["false_positive_validation_data_path"])
    X_val_fp_arr = np.array(
        [
            X_val_fp_arr[i : i + input_shape[0]]
            for i in range(0, X_val_fp_arr.shape[0] - input_shape[0], 1)
        ]
    )
    X_val_fp_labels = np.zeros(X_val_fp_arr.shape[0]).astype(np.float32)
    X_val_fp = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(X_val_fp_arr), torch.from_numpy(X_val_fp_labels)
        ),
        batch_size=len(X_val_fp_labels),
    )

    # X_val: synthetic Piper test set (kept for inner-loop tracking; real metric
    # is post-training real-audio validation in select.py)
    X_val_pos = np.load(feature_save_dir / "positive_features_test.npy")
    X_val_neg = np.load(feature_save_dir / "negative_features_test.npy")
    val_labels = np.hstack(
        (np.ones(X_val_pos.shape[0]), np.zeros(X_val_neg.shape[0]))
    ).astype(np.float32)
    X_val = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(np.vstack((X_val_pos, X_val_neg))),
            torch.from_numpy(val_labels),
        ),
        batch_size=len(val_labels),
    )

    # Single training pass; no auto_train escalation
    steps = config["steps"]
    max_negative_weight = config["max_negative_weight"]
    weights = np.linspace(1, max_negative_weight, int(steps)).tolist()
    val_steps = np.linspace(steps - int(steps * 0.25), steps, 20).astype(np.int64)

    print(
        f"=== custom training: {steps} steps, "
        f"max_neg_weight ramps 1 → {max_negative_weight} ===",
        flush=True,
    )
    oww.train_model(
        X=X_train,
        X_val=X_val,
        false_positive_val_data=X_val_fp,
        max_steps=steps,
        negative_weight_schedule=weights,
        val_steps=val_steps,
        warmup_steps=steps // 5,
        hold_steps=steps // 3,
        lr=1e-4,
        val_set_hrs=11.3,
    )

    # v8: pick best checkpoint by REAL-AUDIO F1
    expected = _expected_inputs_for_validation(target_word)
    best_model = select_best_by_real_f1(
        oww,
        work_dir=work_dir,
        target_word=target_word,
        validation_good=expected["validation_good"],
        validation_bad=expected["validation_bad"],
    )

    oww.export_model(model=best_model, model_name=target_word, output_dir=str(out_dir))
    print(f"Exported ONNX → {out_dir / (target_word + '.onnx')}")
