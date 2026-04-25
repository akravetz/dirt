"""Kaggle Script Kernel — thin shim. Real logic lives in dirt_wake_word/.

The shim has two jobs and only two:

  1. Install runtime deps that the Kaggle environment doesn't have by default
     (Piper TTS, openwakeword, audiomentations, the rest of the ML stack).
  2. Put our `dirt_wake_word` library on the Python path by cloning the
     repo at a pinned commit, then hand off to `dirt_wake_word.main.main()`.

The library's eager top-level imports of openwakeword/torch/numpy succeed
because steps 1+2 ran before the import.

`scripts/kaggle-train` sed-injects the current `git rev-parse HEAD` into
DIRT_REPO_SHA before `kaggle kernels push`, so the kernel that runs on
Kaggle is reproducibly tied to the SHA you pushed from.

Required Kaggle datasets (attach via kernel-metadata.json `dataset_sources`):
  - <user>/dirt-wakeword-mine        ElevenLabs clones + captured RIRs + curated negatives
  - <user>/dirt-wakeword-bg          audioset_16k/ + fma/ as WAV trees
  - <user>/dirt-wakeword-features    ACAV100M 2000 h features .npy + validation_set_features.npy
  - <user>/dirt-wakeword-validation  hand-labeled good/ + bad/ WAVs (real-audio metric)
  - <user>/dirt-wakeword-tts-cache   (optional) pre-generated Piper WAVs to skip TTS step
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WORK = Path("/kaggle/working")

# Pinned commit — sed-injected by scripts/kaggle-train at push time.
# If the sentinel value is unchanged, fall through to fetching latest main
# (useful for ad-hoc kernel testing without going through scripts/kaggle-train).
DIRT_REPO_SHA = "__DIRT_REPO_SHA_INJECTED_AT_PUSH__"


def sh(cmd: str, *, cwd: Path | None = None) -> None:
    print(f"$ {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True, cwd=cwd)


def install_dependencies() -> None:
    """pip + git installs that need to happen before any library imports."""
    os.chdir(WORK)

    if not (WORK / "piper-sample-generator").exists():
        sh("git clone https://github.com/rhasspy/piper-sample-generator")
        sh(
            "wget -O piper-sample-generator/models/en_US-libritts_r-medium.pt "
            "https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt"
        )
        sh("git checkout 213d4d5", cwd=WORK / "piper-sample-generator")

    sh("pip install --quiet piper-tts piper-phonemize-cross webrtcvad")
    sh(
        "pip install --quiet torch==2.5.0 torchvision==0.20.0 torchaudio==2.5.0 "
        "--index-url https://download.pytorch.org/whl/cu121"
    )

    # Clone openwakeword's source — we install it from source via
    # `pip install --no-deps`, NOT from PyPI, because:
    #   - openwakeword 0.6.0 (last PyPI release with our auto_train shape)
    #     declares Requires-Python <3.9; Kaggle's runtime is 3.12.
    #   - Newer GitHub versions support 3.12 but transitively pull
    #     `tflite-runtime`, which isn't published for cp312 + Linux on PyPI.
    # The `--no-deps` flag dodges the tflite-runtime resolver failure;
    # we install all the actual deps explicitly in the next pip call.
    if not (WORK / "openwakeword").exists():
        sh("git clone https://github.com/dscripka/openwakeword")
    # Editable (`-e`) install matters here. AudioFeatures() resolves
    # `resources/models/melspectrogram.onnx` via `__file__` of the installed
    # package. A non-editable install copies the source into site-packages,
    # so our later wget into /kaggle/working/openwakeword/.../resources/
    # never reaches the runtime path. With `-e` the installed location IS
    # /kaggle/working/openwakeword/, so the resource files land where the
    # runtime looks for them.
    sh("pip install --quiet --no-deps -e ./openwakeword")

    sh(
        "pip install --quiet "
        "mutagen==1.47.0 torchinfo==1.8.0 torchmetrics==1.2.0 "
        "speechbrain==0.5.14 audiomentations==0.33.0 torch-audiomentations==0.11.0 "
        "acoustics==0.2.6 onnxruntime==1.22.1 ai_edge_litert==1.4.0 onnxsim "
        "onnx2tf onnx==1.19.1 onnx_graphsurgeon sng4onnx pronouncing==0.2.0 "
        "datasets==2.14.6 deep-phonemizer==0.0.19"
    )

    # openwakeword's bundled embedding + mel ONNX models
    resources = WORK / "openwakeword/openwakeword/resources/models"
    resources.mkdir(parents=True, exist_ok=True)
    base = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"
    for name in (
        "embedding_model.onnx",
        "embedding_model.tflite",
        "melspectrogram.onnx",
        "melspectrogram.tflite",
    ):
        dest = resources / name
        if not dest.exists():
            sh(f"wget -q {base}/{name} -O {dest}")


def install_dirt_repo() -> None:
    """Clone the dirt repo at the pinned SHA and put apps/wake-word/src on path."""
    if DIRT_REPO_SHA.startswith("__"):
        print(
            "WARN: DIRT_REPO_SHA sentinel not replaced; using latest main",
            file=sys.stderr,
        )
        sha = "main"
    else:
        sha = DIRT_REPO_SHA

    if not (WORK / "dirt").exists():
        sh("git clone https://github.com/akravetz/dirt", cwd=WORK)
    sh(f"git checkout {sha}", cwd=WORK / "dirt")

    # Skip pip install -e in favour of direct sys.path insertion — avoids
    # any pip-cache / editable-install quirks that can leave imports flaky.
    sys.path.insert(0, str(WORK / "dirt" / "apps" / "wake-word" / "src"))


def main() -> None:
    install_dependencies()
    install_dirt_repo()
    # Library imports happen lazily inside dirt_wake_word.main (import time
    # is now AFTER both installs have completed).
    from dirt_wake_word.main import main as wake_word_main

    wake_word_main()


if __name__ == "__main__":
    main()
