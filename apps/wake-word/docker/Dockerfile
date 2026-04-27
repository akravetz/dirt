# Wake-word trainer image. Self-contained: deps, openwakeword source,
# resource files, piper sample generator, and the dirt_wake_word library are
# all baked at build time so the runtime entrypoint is just `python -m
# dirt_wake_word.main`. Training data is NOT in the image — it lives on a
# RunPod Network Volume mounted at /workspace/input/, seeded once by
# scripts/runpod-seed-volume.
#
# RunPod requires linux/amd64 (see docs/references/runpod/docker-image.md).
# The runpod/pytorch base ships PyTorch + CUDA + sshd already wired so SCP
# off the running pod just works once PUBLIC_KEY env var is injected.

# syntax=docker/dockerfile:1.7
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# DIRT_GIT_SHA is passed by scripts/runpod-build-image (--build-arg) and
# echoed into ENV so the entrypoint can stamp it into run-manifest.json.
# Empty default keeps `docker build` working outside the script (e.g.
# IDE-driven builds), but those builds aren't pushed.
ARG DIRT_GIT_SHA=""

ENV PYTHONUNBUFFERED=1 \
    DIRT_WAKEWORD_INPUT=/workspace/input \
    DIRT_GIT_SHA=${DIRT_GIT_SHA} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    WANDB_PROJECT=dirt-wake-word \
    WANDB_DIR=/workspace/wandb \
    WANDB_SILENT=true \
    WANDB_CONSOLE=redirect
# DIRT_WAKEWORD_WORKING intentionally NOT baked here — entrypoint computes
# /workspace/working/<RUN_ID> per-run via os.environ.setdefault, which
# loses to a baked Dockerfile env. Leaving it unset lets the per-run
# isolation actually work.
# WANDB_API_KEY is intentionally NOT baked — image is pushed to GHCR;
# the orchestrator (scripts/runpod-train) injects the key at pod-create
# time via the env block. See docs/references/wandb/docker-and-runpod.md.

WORKDIR /opt

# cmake + build-essential are needed to build acoustics 0.2.6 from source
# (no manylinux wheel for cp311). Other tools are usually present in the
# base; explicit so a future base-image tag dropping them isn't silent.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git wget ca-certificates cmake build-essential \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------------------------------
# openwakeword from cloned source (PyPI versions don't work on py3.11/3.12 —
# 0.6.0 declares Requires-Python <3.9, newer versions transitively pull
# tflite-runtime which has no cp311+ Linux wheel). --no-deps avoids the
# resolver failure; the actual deps are installed below.
# ----------------------------------------------------------------------------
RUN git clone https://github.com/dscripka/openwakeword \
 && pip install --no-deps ./openwakeword

# ----------------------------------------------------------------------------
# piper-sample-generator + libritts checkpoint, pinned to a known-good SHA
# pipeline used.
# ----------------------------------------------------------------------------
RUN git clone https://github.com/rhasspy/piper-sample-generator \
 && cd piper-sample-generator \
 && wget -q -O models/en_US-libritts_r-medium.pt \
       https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt \
 && git checkout 213d4d5

# Audio + ML stack. Pinned versions that worked on the Kaggle path port
# cleanly to the RunPod base image given the scipy<1.15 constraint below.
RUN pip install \
        piper-tts piper-phonemize-cross webrtcvad \
        mutagen==1.47.0 torchinfo==1.8.0 torchmetrics==1.2.0 \
        speechbrain==0.5.14 audiomentations==0.33.0 torch-audiomentations==0.11.0 \
        acoustics==0.2.6 onnxruntime==1.22.1 onnx \
        pronouncing==0.2.0 datasets==2.14.6 deep-phonemizer==0.0.19 \
        "scipy<1.15" \
        "wandb>=0.21,<0.22"
# onnx — needed by torch.onnx.export (openwakeword.export_model) to write
# the trained .onnx artifact. Not the same as onnxruntime (inference).
# scipy<1.15 — acoustics 0.2.6 imports `sph_harm` from scipy.special, which
# scipy 1.15 removed (renamed to sph_harm_y with a transposed signature).
# The runpod/pytorch base ships scipy 1.15+, so the pin is mandatory.
#
# Not running `pip check` — openwakeword pins `ai-edge-litert` and
# `speexdsp-ns` for its tflite inference path which we don't use, and the
# runpod/pytorch base has unrelated noise (pygobject/pycairo). The
# `from dirt_wake_word.main import main` smoke at the end of this file
# exercises the actual import chain we care about.

# ----------------------------------------------------------------------------
# openwakeword's bundled embedding + melspectrogram ONNX/tflite resources.
# Written to BOTH the cloned source location and the installed site-packages
# location — AudioFeatures() resolves via __file__ of the installed package.
# (Kaggle v13 burned 22 min discovering this.)
# ----------------------------------------------------------------------------
RUN ow_pkg=$(python -c "import openwakeword, pathlib; print(pathlib.Path(openwakeword.__file__).parent)") \
 && mkdir -p "$ow_pkg/resources/models" /opt/openwakeword/openwakeword/resources/models \
 && for f in embedding_model.onnx embedding_model.tflite melspectrogram.onnx melspectrogram.tflite; do \
        wget -q "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/$f" \
             -O "/opt/openwakeword/openwakeword/resources/models/$f" \
        && cp "/opt/openwakeword/openwakeword/resources/models/$f" "$ow_pkg/resources/models/$f"; \
    done

# ----------------------------------------------------------------------------
# Our library and the in-container entrypoint. Last layer so iteration on
# library code only invalidates this layer (everything above is cached).
# ----------------------------------------------------------------------------
COPY src/dirt_wake_word /opt/dirt_wake_word/dirt_wake_word
ENV PYTHONPATH=/opt/dirt_wake_word

COPY docker/entrypoint.py /app/entrypoint.py

# Build-time smoke test: every transitive import in the library must resolve
# against the installed deps in this image. If a pip pin is wrong, the build
# fails here instead of paying $3 of H100 wall time discovering it at runtime.
RUN python -c "from dirt_wake_word.main import main; print('imports OK')"

# /workspace is the RunPod volume mount path — survives the container
# restart and is visible over SCP. The runpod/pytorch base starts sshd
# automatically and reads $PUBLIC_KEY into /root/.ssh/authorized_keys.
CMD ["python", "/app/entrypoint.py"]
