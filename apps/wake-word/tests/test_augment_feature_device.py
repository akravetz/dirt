"""Feature extraction device-selection tests.

These tests do not require real CUDA. They pin the decision logic that keeps
RunPod GPU runs from silently falling back to CPU ONNX Runtime.
"""

from __future__ import annotations

import pytest

from dirt_wake_word.feature_device import (
    ORT_GPU_MEM_LIMIT_ENV,
    configure_audio_features,
    cuda_provider_options,
    execution_providers_for_device,
    resolve_feature_device,
)


def test_auto_uses_cpu_without_torch_cuda() -> None:
    assert (
        resolve_feature_device(
            requested="auto",
            torch_cuda_available=False,
            onnx_providers=["CPUExecutionProvider", "CUDAExecutionProvider"],
        )
        == "cpu"
    )


def test_auto_uses_cpu_without_onnx_cuda_provider() -> None:
    assert (
        resolve_feature_device(
            requested="auto",
            torch_cuda_available=True,
            onnx_providers=["CPUExecutionProvider"],
        )
        == "cpu"
    )


def test_auto_uses_gpu_when_torch_and_onnx_cuda_are_available() -> None:
    assert (
        resolve_feature_device(
            requested="auto",
            torch_cuda_available=True,
            onnx_providers=["CPUExecutionProvider", "CUDAExecutionProvider"],
        )
        == "gpu"
    )


def test_explicit_cpu_stays_cpu_even_when_cuda_is_available() -> None:
    assert (
        resolve_feature_device(
            requested="cpu",
            torch_cuda_available=True,
            onnx_providers=["CPUExecutionProvider", "CUDAExecutionProvider"],
        )
        == "cpu"
    )


def test_explicit_gpu_requires_torch_cuda() -> None:
    with pytest.raises(RuntimeError, match=r"torch\.cuda\.is_available"):
        resolve_feature_device(
            requested="gpu",
            torch_cuda_available=False,
            onnx_providers=["CPUExecutionProvider", "CUDAExecutionProvider"],
        )


def test_explicit_gpu_requires_onnx_cuda_provider() -> None:
    with pytest.raises(RuntimeError, match="CUDAExecutionProvider"):
        resolve_feature_device(
            requested="gpu",
            torch_cuda_available=True,
            onnx_providers=["CPUExecutionProvider"],
        )


def test_invalid_feature_device_rejected() -> None:
    with pytest.raises(ValueError, match="DIRT_WAKEWORD_FEATURE_DEVICE"):
        resolve_feature_device(
            requested="metal",
            torch_cuda_available=True,
            onnx_providers=["CPUExecutionProvider"],
        )


def test_cuda_provider_options_are_conservative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ORT_GPU_MEM_LIMIT_ENV, "12345")

    assert cuda_provider_options() == {
        "device_id": "0",
        "arena_extend_strategy": "kSameAsRequested",
        "do_copy_in_default_stream": "1",
        "cudnn_conv_algo_search": "HEURISTIC",
        "gpu_mem_limit": "12345",
    }


def test_execution_providers_for_gpu_include_cuda_options() -> None:
    providers = execution_providers_for_device("gpu")

    assert providers[0][0] == "CUDAExecutionProvider"
    assert providers[0][1]["arena_extend_strategy"] == "kSameAsRequested"
    assert providers[1] == "CPUExecutionProvider"


def test_configure_audio_features_sets_both_sessions() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.configured = None

        def set_providers(self, providers) -> None:
            self.configured = providers

        def get_providers(self) -> list[str]:
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]

    class FakeFeatures:
        def __init__(self) -> None:
            self.melspec_model = FakeSession()
            self.embedding_model = FakeSession()
            self.onnx_execution_provider = "CPUExecutionProvider"

    features = FakeFeatures()
    provider = configure_audio_features(features, device="gpu")

    assert provider == "CUDAExecutionProvider"
    assert features.onnx_execution_provider == "CUDAExecutionProvider"
    assert features.melspec_model.configured[0][0] == "CUDAExecutionProvider"
    assert features.embedding_model.configured[0][0] == "CUDAExecutionProvider"
