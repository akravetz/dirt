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

import copy
import gc
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml
from openwakeword.data import mmap_batch_generator
from openwakeword.train import Model
from tqdm import tqdm

from .augment import augment_and_compute_features
from .feature_device import log_gpu_memory
from .paths import OPENWAKEWORD_SOURCE
from .paths import expected_inputs as _expected_inputs_for_validation
from .select import select_best_by_real_f1
from .timing import phase, sh
from .tts_cache import restore_tts_cache_if_mounted

# shm-backed shared tensors instead of fd-passing IPC; default
# `file_descriptor` strategy exhausts the container's ulimit -n at our
# DataLoader-worker × prefetch × tensor-count scale. Set at import so it
# wins regardless of call path. See W&B run 164sz2ad (2026-04-26).
torch.multiprocessing.set_sharing_strategy("file_system")

FP_VAL_MAX_WINDOWS_ENV = "DIRT_WAKEWORD_FP_VAL_MAX_WINDOWS"
VAL_STEPS_COUNT_ENV = "DIRT_WAKEWORD_VAL_STEPS_COUNT"
TRAIN_TELEMETRY_EVERY_ENV = "DIRT_WAKEWORD_TRAIN_TELEMETRY_EVERY"
TORCH_MEMORY_SUMMARY_ENV = "DIRT_WAKEWORD_TORCH_MEMORY_SUMMARY"


def _env_int(name: str, *, default: int, minimum: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer; got {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}; got {value}")
    return value


def custom_train(
    *,
    config_path: Path,
    work_dir: Path,
    out_dir: Path,
    target_word: str,
) -> None:
    """End-to-end training: TTS-cache restore → generate → augment → train."""
    train_py = OPENWAKEWORD_SOURCE / "openwakeword/train.py"
    with phase("restore_tts_cache"):
        restore_tts_cache_if_mounted(out_dir)
    with phase("generate_clips"):
        sh(
            f"{sys.executable} {train_py} --training_config {config_path} --generate_clips"
        )
    with phase("augment+features"):
        augment_and_compute_features(work_dir=work_dir, out_dir=out_dir)
    _custom_train_model(work_dir=work_dir, out_dir=out_dir, target_word=target_word)


def _log_torch_runtime() -> None:
    """Print enough device/runtime context to diagnose slow training."""
    print("=== torch runtime ===", flush=True)
    print(f"  torch.__version__={torch.__version__}", flush=True)
    print(f"  cuda_available={torch.cuda.is_available()}", flush=True)
    print(f"  cuda_device_count={torch.cuda.device_count()}", flush=True)
    if torch.cuda.is_available():
        current = torch.cuda.current_device()
        print(f"  cuda_current_device={current}", flush=True)
        print(f"  cuda_device_name={torch.cuda.get_device_name(current)}", flush=True)
        print(
            f"  cuda_capability={torch.cuda.get_device_capability(current)}", flush=True
        )
    print(f"  cudnn_available={torch.backends.cudnn.is_available()}", flush=True)
    print(f"  cudnn_version={torch.backends.cudnn.version()}", flush=True)
    print(f"  torch_num_threads={torch.get_num_threads()}", flush=True)
    print(f"  torch_num_interop_threads={torch.get_num_interop_threads()}", flush=True)


def _log_model_runtime(label: str, oww: Model) -> None:
    model = getattr(oww, "model", None)
    if model is None:
        print(f"=== model runtime ({label}): no .model attr ===", flush=True)
        return
    params = list(model.parameters())
    if not params:
        print(f"=== model runtime ({label}): no parameters ===", flush=True)
        return
    total_params = sum(p.numel() for p in params)
    first = params[0]
    print(
        f"=== model runtime ({label}): device={first.device} dtype={first.dtype} "
        f"params={total_params:,} training={model.training} ===",
        flush=True,
    )


def _log_runtime_boundary(label: str) -> None:
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(
        f"=== runtime boundary ({label}): "
        f"rss_max_mb={rss_mb:.1f} gc_counts={gc.get_count()} ===",
        flush=True,
    )
    if torch.cuda.is_available():
        stats = torch.cuda.memory_stats()
        print(
            f"=== torch cuda stats ({label}): "
            f"allocated={torch.cuda.memory_allocated() / 1024**3:.2f}GiB "
            f"reserved={torch.cuda.memory_reserved() / 1024**3:.2f}GiB "
            f"active.all.current={stats.get('active.all.current', 0)} "
            f"reserved_bytes.all.peak={stats.get('reserved_bytes.all.peak', 0)} "
            f"num_alloc_retries={stats.get('num_alloc_retries', 0)} "
            f"num_ooms={stats.get('num_ooms', 0)} ===",
            flush=True,
        )
        if os.environ.get(TORCH_MEMORY_SUMMARY_ENV):
            print(
                f"=== torch cuda memory summary ({label}) START ===\n"
                f"{torch.cuda.memory_summary()}\n"
                f"=== torch cuda memory summary ({label}) END ===",
                flush=True,
            )


def _cuda_sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def _elapsed_since(t0: float, *, sync: bool) -> tuple[float, float]:
    if sync:
        _cuda_sync()
    now = time.perf_counter()
    return now - t0, now


def _telemetry_line(prefix: str, values: dict[str, object]) -> None:
    parts = []
    for key, value in values.items():
        if isinstance(value, float):
            parts.append(f"{key}={value:.6f}")
        else:
            parts.append(f"{key}={value}")
    tqdm.write(f"=== {prefix}: {' '.join(parts)} ===")


def _train_model_instrumented(  # noqa: PLR0915
    oww: Model,
    *,
    X,
    max_steps: int,
    warmup_steps: int,
    hold_steps: int,
    X_val=None,
    false_positive_val_data=None,
    positive_test_clips=None,
    negative_weight_schedule=None,
    val_steps=None,
    lr: float = 0.0001,
    val_set_hrs: float = 1,
) -> None:
    """Instrumented copy of upstream openwakeword.train.Model.train_model().

    Keep behavior aligned with upstream; add timing around data fetch, device
    transfer, model compute, optimizer work, and inner validation.
    """
    negative_weight_schedule = negative_weight_schedule or [1]
    val_steps = set(val_steps or [250])
    telemetry_every = _env_int(TRAIN_TELEMETRY_EVERY_ENV, default=500, minimum=0)

    oww.to(oww.device)
    oww.model.to(oww.device)

    accumulation_steps = 1
    accumulated_samples = 0
    accumulated_predictions = torch.Tensor([]).to(oww.device)
    accumulated_labels = torch.Tensor([]).to(oww.device)
    data_iter = iter(X)

    for step_ndx in tqdm(range(max_steps), total=max_steps, desc="Training"):
        sample_step = telemetry_every > 0 and (
            step_ndx % telemetry_every == 0 or step_ndx == max_steps - 1
        )
        sync_timers = sample_step and torch.cuda.is_available()
        step_t0 = time.perf_counter()
        t = step_t0
        timers: dict[str, float] = {}

        data = next(data_iter)
        timers["batch_fetch_s"], t = _elapsed_since(t, sync=sync_timers)

        x, y = data[0].to(oww.device), data[1].to(oww.device)
        y_ = y[..., None].to(torch.float32)
        timers["h2d_copy_s"], t = _elapsed_since(t, sync=sync_timers)

        for g in oww.optimizer.param_groups:
            g["lr"] = oww.lr_warmup_cosine_decay(
                step_ndx,
                warmup_steps=warmup_steps,
                hold=hold_steps,
                total_steps=max_steps,
                target_lr=lr,
            )
        timers["lr_update_s"], t = _elapsed_since(t, sync=sync_timers)

        oww.optimizer.zero_grad()
        timers["zero_grad_s"], t = _elapsed_since(t, sync=sync_timers)

        predictions = oww.model(x)
        timers["forward_s"], t = _elapsed_since(t, sync=sync_timers)

        neg_high_loss = predictions[(y == 0) & (predictions.squeeze() >= 0.001)]
        pos_high_loss = predictions[(y == 1) & (predictions.squeeze() < 0.999)]
        y = torch.cat(
            (
                y[(y == 0) & (predictions.squeeze() >= 0.001)],
                y[(y == 1) & (predictions.squeeze() < 0.999)],
            )
        )
        y_ = y[..., None].to(torch.float32)
        predictions = torch.cat((neg_high_loss, pos_high_loss))
        timers["high_loss_filter_s"], t = _elapsed_since(t, sync=sync_timers)

        selected_samples = int(predictions.shape[0])
        loss_value = None
        if predictions.shape[0] != 0:
            if len(negative_weight_schedule) == 1:
                w = torch.ones(y.shape[0]) * negative_weight_schedule[0]
                pos_ndcs = y == 1
                w[pos_ndcs] = 1
                w = w[..., None]
            else:
                if oww.n_classes == 1:
                    w = torch.ones(y.shape[0]) * negative_weight_schedule[step_ndx]
                    pos_ndcs = y == 1
                    w[pos_ndcs] = 1
                    w = w[..., None]
            timers["weight_build_s"], t = _elapsed_since(t, sync=sync_timers)

            loss = oww.loss(
                predictions,
                y_ if oww.n_classes == 1 else y,
                w.to(oww.device),
            )
            loss = loss / accumulation_steps
            loss_value = float(loss.detach().cpu().numpy())
            accumulated_samples += predictions.shape[0]
            timers["loss_s"], t = _elapsed_since(t, sync=sync_timers)

            if predictions.shape[0] >= 128:
                accumulated_predictions = predictions
                accumulated_labels = y_
            if accumulated_samples < 128:
                accumulation_steps += 1
                accumulated_predictions = torch.cat(
                    (accumulated_predictions, predictions)
                )
                accumulated_labels = torch.cat((accumulated_labels, y_))
                timers["accumulate_s"], t = _elapsed_since(t, sync=sync_timers)
            else:
                loss.backward()
                timers["backward_s"], t = _elapsed_since(t, sync=sync_timers)
                oww.optimizer.step()
                timers["optimizer_s"], t = _elapsed_since(t, sync=sync_timers)
                accumulation_steps = 1
                accumulated_samples = 0

                oww.history["loss"].append(loss.detach().cpu().numpy())

                fp = oww.fp(
                    accumulated_predictions,
                    accumulated_labels if oww.n_classes == 1 else y,
                )
                oww.n_fp += fp
                oww.history["recall"].append(
                    oww.recall(accumulated_predictions, accumulated_labels)
                    .detach()
                    .cpu()
                    .numpy()
                )

                accumulated_predictions = torch.Tensor([]).to(oww.device)
                accumulated_labels = torch.Tensor([]).to(oww.device)
                timers["metrics_s"], t = _elapsed_since(t, sync=sync_timers)
        else:
            timers["weight_build_s"] = 0.0
            timers["loss_s"] = 0.0

        should_validate = step_ndx in val_steps and step_ndx > 1
        if should_validate:
            val_t0 = time.perf_counter()
            fp_val_s = 0.0
            fp_val_batches = 0
            pos_clip_val_s = 0.0
            synth_val_s = 0.0
            if false_positive_val_data is not None:
                fp_t0 = time.perf_counter()
                val_fp = 0
                for _fp_val_batches, data in enumerate(
                    false_positive_val_data, start=1
                ):
                    fp_val_batches = _fp_val_batches
                    with torch.no_grad():
                        x_val, y_val = data[0].to(oww.device), data[1].to(oww.device)
                        val_predictions = oww.model(x_val)
                        val_fp += oww.fp(val_predictions, y_val[..., None])
                fp_val_s = time.perf_counter() - fp_t0
                val_fp_per_hr = (val_fp / val_set_hrs).detach().cpu().numpy()
                oww.history["val_fp_per_hr"].append(val_fp_per_hr)

            if positive_test_clips is not None:
                pos_t0 = time.perf_counter()
                tp = 0
                fn = 0
                for data in positive_test_clips:
                    with torch.no_grad():
                        x_val = data[0].to(oww.device)
                        batch = []
                        for i in range(0, x_val.shape[1] - 16, 1):
                            batch.append(x_val[:, i : i + 16, :])
                        batch = torch.vstack(batch)
                        preds = oww.model(batch)
                        if any(preds >= 0.5):
                            tp += 1
                        else:
                            fn += 1
                pos_clip_val_s = time.perf_counter() - pos_t0
                oww.history["positive_test_clips_recall"].append(tp / (tp + fn))

            synth_val_batches = 0
            if X_val is not None:
                synth_t0 = time.perf_counter()
                for _synth_val_batches, data in enumerate(X_val, start=1):
                    synth_val_batches = _synth_val_batches
                    with torch.no_grad():
                        x_val, y_val = data[0].to(oww.device), data[1].to(oww.device)
                        val_predictions = oww.model(x_val)
                        val_recall = (
                            oww.recall(val_predictions, y_val[..., None])
                            .detach()
                            .cpu()
                            .numpy()
                        )
                        val_acc = oww.accuracy(
                            val_predictions, y_val[..., None].to(torch.int64)
                        )
                        val_fp = oww.fp(val_predictions, y_val[..., None])
                synth_val_s = time.perf_counter() - synth_t0
                oww.history["val_accuracy"].append(val_acc.detach().cpu().numpy())
                oww.history["val_recall"].append(val_recall)
                oww.history["val_n_fp"].append(val_fp.detach().cpu().numpy())

            if (
                X_val is not None
                and oww.history["val_n_fp"][-1]
                <= np.percentile(oww.history["val_n_fp"], 50)
                and oww.history["val_recall"][-1]
                >= np.percentile(oww.history["val_recall"], 5)
            ):
                oww.best_models.append(copy.deepcopy(oww.model))
                oww.best_model_scores.append(
                    {
                        "training_step_ndx": step_ndx,
                        "val_n_fp": oww.history["val_n_fp"][-1],
                        "val_recall": oww.history["val_recall"][-1],
                        "val_accuracy": oww.history["val_accuracy"][-1],
                        "val_fp_per_hr": oww.history.get("val_fp_per_hr", [0])[-1],
                    }
                )
                oww.best_val_recall = oww.history["val_recall"][-1]
                oww.best_val_accuracy = oww.history["val_accuracy"][-1]

            _telemetry_line(
                "inner_validation_telemetry",
                {
                    "step": step_ndx,
                    "fp_val_s": fp_val_s,
                    "fp_val_batches": fp_val_batches,
                    "positive_clip_val_s": pos_clip_val_s,
                    "synthetic_val_s": synth_val_s,
                    "synthetic_val_batches": synth_val_batches,
                    "total_s": time.perf_counter() - val_t0,
                    "best_models": len(oww.best_models),
                },
            )

        if sample_step:
            step_total_s = time.perf_counter() - step_t0
            _telemetry_line(
                "train_step_telemetry",
                {
                    "step": step_ndx,
                    "loss": loss_value if loss_value is not None else "none",
                    "selected_samples": selected_samples,
                    "accumulation_steps": accumulation_steps,
                    "step_total_s": step_total_s,
                    **timers,
                },
            )


def _shape(path: Path) -> tuple[int, ...]:
    return tuple(np.load(path, mmap_mode="r").shape)


def _build_train_loader(
    *, config: dict, feature_paths: dict[str, Path], input_shape: tuple[int, ...]
) -> torch.utils.data.DataLoader:
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
    feature_data_files["positive"] = str(feature_paths["positive_train"])
    feature_data_files["adversarial_negative"] = str(feature_paths["negative_train"])

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
    n_workers = max(1, n_cpus // 2)
    prefetch_factor = 16
    print(f"  os_cpu_count={n_cpus}", flush=True)
    print(f"  train_dataloader_workers={n_workers}", flush=True)
    print(f"  train_dataloader_prefetch_factor={prefetch_factor}", flush=True)
    print(f"  batch_n_per_class={config['batch_n_per_class']}", flush=True)
    return torch.utils.data.DataLoader(
        IterDataset(batch_generator),
        batch_size=None,
        num_workers=n_workers,
        prefetch_factor=prefetch_factor,
    )


def _build_false_positive_validation(
    config: dict, input_shape: tuple[int, ...]
) -> torch.utils.data.DataLoader:
    X_val_fp_arr = np.load(config["false_positive_validation_data_path"])
    fp_val_max_windows = _env_int(FP_VAL_MAX_WINDOWS_ENV, default=0, minimum=0)
    fp_val_source_windows = X_val_fp_arr.shape[0] - input_shape[0]
    if fp_val_max_windows:
        fp_val_windows = min(fp_val_source_windows, fp_val_max_windows)
        print(
            f"  {FP_VAL_MAX_WINDOWS_ENV}={fp_val_max_windows}; "
            f"capping FP validation windows {fp_val_source_windows} → {fp_val_windows}",
            flush=True,
        )
    else:
        fp_val_windows = fp_val_source_windows
    X_val_fp_arr = np.array(
        [X_val_fp_arr[i : i + input_shape[0]] for i in range(0, fp_val_windows, 1)]
    )
    X_val_fp_labels = np.zeros(X_val_fp_arr.shape[0]).astype(np.float32)
    print(f"  X_val_fp_shape={X_val_fp_arr.shape}", flush=True)
    return torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(X_val_fp_arr), torch.from_numpy(X_val_fp_labels)
        ),
        batch_size=len(X_val_fp_labels),
    )


def _build_synthetic_validation(
    *,
    positive_features_path: Path,
    negative_features_path: Path,
) -> torch.utils.data.DataLoader:
    X_val_pos = np.load(positive_features_path)
    X_val_neg = np.load(negative_features_path)
    val_labels = np.hstack(
        (np.ones(X_val_pos.shape[0]), np.zeros(X_val_neg.shape[0]))
    ).astype(np.float32)
    print(f"  X_val_pos_shape={X_val_pos.shape}", flush=True)
    print(f"  X_val_neg_shape={X_val_neg.shape}", flush=True)
    return torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(np.vstack((X_val_pos, X_val_neg))),
            torch.from_numpy(val_labels),
        ),
        batch_size=len(val_labels),
    )


def _build_val_steps(steps: int) -> np.ndarray:
    val_steps_count = _env_int(VAL_STEPS_COUNT_ENV, default=20, minimum=1)
    val_steps = np.linspace(steps - int(steps * 0.25), steps, val_steps_count).astype(
        np.int64
    )
    print(f"  val_steps_count={len(val_steps)}", flush=True)
    print(
        f"  {VAL_STEPS_COUNT_ENV}={os.environ.get(VAL_STEPS_COUNT_ENV, '<unset>')}",
        flush=True,
    )
    print(
        f"  val_steps_first_last={int(val_steps[0])},{int(val_steps[-1])}",
        flush=True,
    )
    return val_steps


def _custom_train_model(*, work_dir: Path, out_dir: Path, target_word: str) -> None:
    """The soft-fork meat: replace upstream's --train_model __main__ block."""
    with phase("prepare_train_inputs"):
        _log_torch_runtime()
        _log_runtime_boundary("prepare_train_inputs_start")
        log_gpu_memory("prepare_train_inputs_start")
        config = yaml.safe_load((work_dir / "my_model.yaml").read_text())
        feature_save_dir = out_dir / target_word

        feature_paths = {
            "positive_train": feature_save_dir / "positive_features_train.npy",
            "negative_train": feature_save_dir / "negative_features_train.npy",
            "positive_test": feature_save_dir / "positive_features_test.npy",
            "negative_test": feature_save_dir / "negative_features_test.npy",
        }
        for name, path in feature_paths.items():
            print(f"  feature_shape[{name}]={_shape(path)}", flush=True)

        input_shape = _shape(feature_paths["positive_test"])[1:]

        oww = Model(
            n_classes=1,
            input_shape=input_shape,
            model_type=config["model_type"],
            layer_dim=config["layer_size"],
            seconds_per_example=1280 * input_shape[0] / 16000,
        )
        _log_model_runtime("after_init", oww)

        X_train = _build_train_loader(
            config=config, feature_paths=feature_paths, input_shape=input_shape
        )

        X_val_fp = _build_false_positive_validation(config, input_shape)
        X_val = _build_synthetic_validation(
            positive_features_path=feature_paths["positive_test"],
            negative_features_path=feature_paths["negative_test"],
        )

        # Single training pass; no auto_train escalation
        steps = config["steps"]
        max_negative_weight = config["max_negative_weight"]
        weights = np.linspace(1, max_negative_weight, int(steps)).tolist()
        val_steps = _build_val_steps(steps)
        print(f"  steps={steps}", flush=True)
        print(
            f"  {TRAIN_TELEMETRY_EVERY_ENV}="
            f"{os.environ.get(TRAIN_TELEMETRY_EVERY_ENV, '500')}",
            flush=True,
        )
        print(f"  warmup_steps={steps // 5}", flush=True)
        print(f"  hold_steps={steps // 3}", flush=True)
        print(
            "  negative_weight_schedule="
            f"{weights[0]:.3f} → {weights[-1]:.3f} "
            f"(mid={weights[len(weights) // 2]:.3f})",
            flush=True,
        )
        log_gpu_memory("prepare_train_inputs_end")
        _log_runtime_boundary("prepare_train_inputs_end")

    with phase("fit_model"):
        _log_runtime_boundary("before_fit_model")
        log_gpu_memory("before_fit_model")
        print(
            f"=== custom training: {steps} steps, "
            f"max_neg_weight ramps 1 → {max_negative_weight} ===",
            flush=True,
        )
        t0 = time.monotonic()
        _train_model_instrumented(
            oww,
            X=X_train,
            X_val=X_val,
            false_positive_val_data=X_val_fp,
            max_steps=steps,
            negative_weight_schedule=weights,
            val_steps=val_steps.tolist(),
            warmup_steps=steps // 5,
            hold_steps=steps // 3,
            lr=1e-4,
            val_set_hrs=11.3,
        )
        elapsed = time.monotonic() - t0
        print(
            f"=== fit_model throughput: {steps / elapsed:.2f} steps/sec ===", flush=True
        )
        _log_model_runtime("after_fit", oww)
        log_gpu_memory("after_fit_model")
        _log_runtime_boundary("after_fit_model")
        print(f"=== best_models_saved={len(oww.best_models)} ===", flush=True)

    # v8: pick best checkpoint by REAL-AUDIO F1
    with phase("select_checkpoint"):
        expected = _expected_inputs_for_validation(target_word)
        best_model = select_best_by_real_f1(
            oww,
            work_dir=work_dir,
            target_word=target_word,
            validation_good=expected["validation_good"],
            validation_bad=expected["validation_bad"],
        )

    with phase("export_model"):
        oww.export_model(
            model=best_model, model_name=target_word, output_dir=str(out_dir)
        )
        print(f"Exported ONNX → {out_dir / (target_word + '.onnx')}")
