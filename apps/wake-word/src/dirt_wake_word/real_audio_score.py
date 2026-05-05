"""Batched real-audio scoring for checkpoint selection and validation."""

from __future__ import annotations

import os
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
from openwakeword.utils import AudioFeatures


@dataclass(frozen=True)
class PreparedWindows:
    paths: list[Path]
    windows: np.ndarray
    clip_indices: np.ndarray
    telemetry: dict[str, float | int | str]


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def _reset_features(
    features: AudioFeatures, *, initial_feature_buffer: np.ndarray
) -> None:
    features.raw_data_buffer.clear()
    features.melspectrogram_buffer = np.ones((76, 32))
    features.accumulated_samples = 0
    features.raw_data_remainder = np.empty(0)
    features.feature_buffer = initial_feature_buffer.copy()


def prepare_streaming_windows(
    paths: list[Path],
    *,
    chunk: int = 1280,
    model_frames: int = 16,
    ncpu: int | None = None,
) -> PreparedWindows:
    """Precompute streaming feature windows once for a real-audio split.

    This intentionally follows openwakeword's streaming preprocessor path and
    first-five-frame warmup behavior, then makes model scoring batched and
    deterministic. The old per-clip `Model.reset()` recomputed random startup
    embeddings every clip; here we cache the initial buffer once and copy it.
    """
    t0 = time.perf_counter()
    ncpu = ncpu or max(1, min(os.cpu_count() or 1, 8))
    features = AudioFeatures(inference_framework="onnx", ncpu=ncpu, device="cpu")
    provider = getattr(features, "onnx_execution_provider", "unknown")
    initial_feature_buffer = features.feature_buffer.copy()

    wav_load_s = 0.0
    preprocessor_s = 0.0
    get_features_s = 0.0
    windows: list[np.ndarray] = []
    clip_indices: list[int] = []

    for clip_idx, path in enumerate(paths):
        load_t0 = time.perf_counter()
        wav = _load_wav(path)
        wav_load_s += time.perf_counter() - load_t0
        _reset_features(features, initial_feature_buffer=initial_feature_buffer)
        prediction_count = 0
        for start in range(0, len(wav) - chunk + 1, chunk):
            prep_t0 = time.perf_counter()
            n_prepared = features(wav[start : start + chunk])
            preprocessor_s += time.perf_counter() - prep_t0
            if n_prepared < chunk:
                continue
            # openwakeword.Model.predict returns zero for the first five
            # predictions after reset while its prediction buffer warms up.
            if prediction_count >= 5:
                feat_t0 = time.perf_counter()
                windows.append(features.get_features(model_frames)[0])
                get_features_s += time.perf_counter() - feat_t0
                clip_indices.append(clip_idx)
            prediction_count += max(1, int(n_prepared // chunk))

    if windows:
        window_array = np.asarray(windows, dtype=np.float32)
        clip_index_array = np.asarray(clip_indices, dtype=np.int64)
    else:
        window_array = np.empty((0, model_frames, 96), dtype=np.float32)
        clip_index_array = np.empty((0,), dtype=np.int64)

    telemetry = {
        "clips": len(paths),
        "windows": int(window_array.shape[0]),
        "provider": str(provider),
        "wav_load_s": wav_load_s,
        "preprocessor_s": preprocessor_s,
        "get_features_s": get_features_s,
        "total_s": time.perf_counter() - t0,
    }
    return PreparedWindows(paths, window_array, clip_index_array, telemetry)


def score_prepared_windows(
    onnx_path: Path,
    prepared: PreparedWindows,
    *,
    batch_size: int = 1024,
) -> tuple[list[float], dict[str, float | int | str]]:
    """Score precomputed windows with a classifier ONNX model in batches."""
    t0 = time.perf_counter()
    init_t0 = time.perf_counter()
    model_bytes, batchable, original_batch_dim = _model_with_dynamic_batch(onnx_path)
    session = ort.InferenceSession(model_bytes, providers=["CPUExecutionProvider"])
    init_s = time.perf_counter() - init_t0
    provider = ",".join(session.get_providers())
    input_name = session.get_inputs()[0].name

    peaks = np.zeros(len(prepared.paths), dtype=np.float32)
    inference_s = 0.0
    batches = 0
    for start in range(0, prepared.windows.shape[0], batch_size):
        batch = prepared.windows[start : start + batch_size]
        infer_t0 = time.perf_counter()
        raw = session.run(None, {input_name: batch})[0]
        inference_s += time.perf_counter() - infer_t0
        batches += 1
        scores = np.asarray(raw, dtype=np.float32).reshape(-1)
        for clip_idx, score in zip(
            prepared.clip_indices[start : start + batch_size],
            scores,
            strict=False,
        ):
            if score > peaks[int(clip_idx)]:
                peaks[int(clip_idx)] = score

    telemetry = {
        "provider": provider,
        "batchable": int(batchable),
        "original_batch_dim": str(original_batch_dim),
        "batch_size": batch_size,
        "session_init_s": init_s,
        "inference_s": inference_s,
        "batches": batches,
        "windows": int(prepared.windows.shape[0]),
        "total_s": time.perf_counter() - t0,
    }
    return peaks.tolist(), telemetry


def _model_with_dynamic_batch(onnx_path: Path) -> tuple[bytes, bool, str]:
    """Return ONNX bytes with a symbolic batch dimension on inputs/outputs."""
    import onnx

    model = onnx.load(str(onnx_path))
    original_batch_dim = _first_dim_label(model.graph.input[0])
    batchable = False
    for value_info in [*model.graph.input, *model.graph.output]:
        shape = value_info.type.tensor_type.shape
        if not shape.dim:
            continue
        dim = shape.dim[0]
        if dim.dim_value:
            dim.ClearField("dim_value")
            dim.dim_param = "batch"
            batchable = True
        elif not dim.dim_param:
            dim.dim_param = "batch"
            batchable = True
    return model.SerializeToString(), batchable, original_batch_dim


def _first_dim_label(value_info) -> str:
    shape = value_info.type.tensor_type.shape
    if not shape.dim:
        return "missing"
    dim = shape.dim[0]
    if dim.dim_value:
        return str(dim.dim_value)
    if dim.dim_param:
        return dim.dim_param
    return "unknown"


def precision_recall_f1(
    good_scores: list[float],
    bad_scores: list[float],
    *,
    threshold: float,
) -> tuple[int, int, float, float, float]:
    tp = sum(1 for score in good_scores if score >= threshold)
    fp = sum(1 for score in bad_scores if score >= threshold)
    recall = tp / len(good_scores) if good_scores else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return tp, fp, recall, precision, f1
