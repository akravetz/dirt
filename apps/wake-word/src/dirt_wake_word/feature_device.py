"""Feature extraction device selection and ONNX Runtime CUDA setup."""

from __future__ import annotations

import gc
import os
import shutil
import subprocess
from typing import Any

FEATURE_DEVICE_ENV = "DIRT_WAKEWORD_FEATURE_DEVICE"
ORT_GPU_MEM_LIMIT_ENV = "DIRT_WAKEWORD_ORT_GPU_MEM_LIMIT"
DEFAULT_ORT_GPU_MEM_LIMIT = 2 * 1024 * 1024 * 1024


def onnxruntime_providers() -> list[str]:
    try:
        import onnxruntime as ort
    except ImportError:
        return []
    return list(ort.get_available_providers())


def resolve_feature_device(
    *,
    requested: str | None = None,
    torch_cuda_available: bool | None = None,
    onnx_providers: list[str] | None = None,
) -> str:
    """Resolve cpu/gpu for openwakeword AudioFeatures.

    `auto` only selects GPU when both PyTorch can see CUDA and ONNX Runtime
    exposes CUDAExecutionProvider. Explicit `gpu` is stricter and fails early.
    """
    requested = (requested or os.environ.get(FEATURE_DEVICE_ENV, "auto")).lower()
    if requested not in {"auto", "cpu", "gpu"}:
        raise ValueError(
            f"{FEATURE_DEVICE_ENV} must be one of auto, cpu, gpu; got {requested!r}"
        )

    if torch_cuda_available is None:
        import torch

        torch_cuda_available = torch.cuda.is_available()
    onnx_providers = (
        onnxruntime_providers() if onnx_providers is None else onnx_providers
    )
    has_ort_cuda = "CUDAExecutionProvider" in onnx_providers

    if requested == "cpu":
        return "cpu"
    if requested == "gpu":
        missing = []
        if not torch_cuda_available:
            missing.append("torch.cuda.is_available() is false")
        if not has_ort_cuda:
            missing.append("onnxruntime CUDAExecutionProvider is unavailable")
        if missing:
            raise RuntimeError(
                f"{FEATURE_DEVICE_ENV}=gpu requested but cannot use GPU features: "
                + "; ".join(missing)
                + f"; onnxruntime providers={onnx_providers}"
            )
        return "gpu"
    if torch_cuda_available and has_ort_cuda:
        return "gpu"
    return "cpu"


def log_cuda_runtime_compat() -> None:
    """Print the CUDA/cuDNN facts that uv cannot prove at resolve time."""
    try:
        import torch
    except ImportError:
        torch = None

    try:
        import onnxruntime as ort
    except ImportError:
        ort = None

    torch_version = getattr(torch, "__version__", "unavailable")
    torch_cuda = getattr(getattr(torch, "version", None), "cuda", None)
    cudnn_version = (
        torch.backends.cudnn.version() if torch is not None else "unavailable"
    )
    ort_version = getattr(ort, "__version__", "unavailable")
    providers = ort.get_available_providers() if ort is not None else []
    print(
        "=== cuda runtime compat: "
        f"torch={torch_version} torch_cuda={torch_cuda} "
        f"torch_cudnn={cudnn_version} onnxruntime={ort_version} "
        f"onnxruntime_providers={providers} ===",
        flush=True,
    )


def _format_bytes(n: int | None) -> str:
    if n is None:
        return "unknown"
    gib = n / (1024**3)
    return f"{gib:.2f}GiB"


def _nvidia_smi_memory() -> str:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return "nvidia_smi=unavailable"
    try:
        result = subprocess.run(  # noqa: S603
            [
                nvidia_smi,
                "--query-gpu=memory.used,memory.free,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"nvidia_smi_error={exc!r}"
    if result.returncode != 0:
        return f"nvidia_smi_error={result.stderr.strip()!r}"
    first = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if not first:
        return "nvidia_smi=empty"
    used_mib, free_mib, total_mib, util = [part.strip() for part in first.split(",")]
    return (
        f"nvidia_smi_used={used_mib}MiB "
        f"nvidia_smi_free={free_mib}MiB "
        f"nvidia_smi_total={total_mib}MiB "
        f"nvidia_smi_util={util}%"
    )


def log_gpu_memory(label: str) -> None:
    """Log both PyTorch allocator and whole-GPU memory at key boundaries."""
    try:
        import torch
    except ImportError:
        print(f"=== gpu memory ({label}): torch=unavailable ===", flush=True)
        return

    if not torch.cuda.is_available():
        print(f"=== gpu memory ({label}): cuda_available=False ===", flush=True)
        return

    free, total = torch.cuda.mem_get_info()
    print(
        f"=== gpu memory ({label}): "
        f"torch_allocated={_format_bytes(torch.cuda.memory_allocated())} "
        f"torch_reserved={_format_bytes(torch.cuda.memory_reserved())} "
        f"torch_max_allocated={_format_bytes(torch.cuda.max_memory_allocated())} "
        f"torch_max_reserved={_format_bytes(torch.cuda.max_memory_reserved())} "
        f"cuda_free={_format_bytes(free)} cuda_total={_format_bytes(total)} "
        f"{_nvidia_smi_memory()} ===",
        flush=True,
    )


def preload_onnxruntime_cuda() -> None:
    """Load CUDA/cuDNN libraries before ONNX Runtime sessions are created."""
    import torch  # noqa: F401  # importing torch preloads its CUDA/cuDNN libs

    try:
        import onnxruntime as ort
    except ImportError:
        return
    preload = getattr(ort, "preload_dlls", None)
    if preload is not None:
        preload()


def cuda_provider_options() -> dict[str, str]:
    """Conservative CUDA EP options for sharing the process with PyTorch."""
    return {
        "device_id": "0",
        "arena_extend_strategy": "kSameAsRequested",
        "do_copy_in_default_stream": "1",
        "cudnn_conv_algo_search": "HEURISTIC",
        "gpu_mem_limit": os.environ.get(
            ORT_GPU_MEM_LIMIT_ENV, str(DEFAULT_ORT_GPU_MEM_LIMIT)
        ),
    }


def execution_providers_for_device(device: str) -> list[Any]:
    if device == "gpu":
        return [
            ("CUDAExecutionProvider", cuda_provider_options()),
            "CPUExecutionProvider",
        ]
    if device == "cpu":
        return ["CPUExecutionProvider"]
    raise ValueError(f"unknown feature device: {device!r}")


def configure_audio_features(features: Any, *, device: str) -> str:
    """Apply provider options to openwakeword AudioFeatures sessions."""
    providers = execution_providers_for_device(device)
    for attr in ("melspec_model", "embedding_model"):
        session = getattr(features, attr, None)
        set_providers = getattr(session, "set_providers", None)
        if set_providers is not None:
            set_providers(providers)

    provider = getattr(features, "onnx_execution_provider", "unknown")
    melspec_model = getattr(features, "melspec_model", None)
    get_providers = getattr(melspec_model, "get_providers", None)
    if get_providers is not None:
        providers_after = get_providers()
        if providers_after:
            provider = providers_after[0]
            features.onnx_execution_provider = provider
    return provider


def release_audio_features(features: Any | None, *, device: str) -> None:
    """Drop ORT sessions and give PyTorch a clean CUDA cache boundary."""
    if features is not None:
        for attr in (
            "melspec_model",
            "embedding_model",
            "raw_data_buffer",
            "melspectrogram_buffer",
            "feature_buffer",
        ):
            if hasattr(features, attr):
                setattr(features, attr, None)
    gc.collect()
    if device == "gpu":
        try:
            import torch
        except ImportError:
            return
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
