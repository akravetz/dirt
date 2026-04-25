"""Kaggle port of the openWakeWord Colab training notebook.

Runs as a Kaggle Script Kernel (`kernel_type: script` in kernel-metadata.json).
End-to-end: generate synthetic positives (piper) -> augment -> train -> export
ONNX + tflite to /kaggle/working, which Kaggle auto-publishes as kernel output.

Source: apps/wake-word/reference/automatic_model_training.py (Colab). The three bulk-download cells
(MIT RIRs, AudioSet, FMA, 2000h features, 11h validation features) are replaced
with /kaggle/input/* mounts — those corpora are uploaded once as Kaggle Datasets
and mounted read-only at runtime. Edit EXPECTED_INPUTS below if you rename them.

Required datasets (attach via kernel-metadata.json `dataset_sources`):
  - <user>/dirt-wakeword-mine        ElevenLabs clones + captured RIRs + curated negatives
  - <user>/dirt-wakeword-bg          audioset_16k/ + fma/ as WAV trees
  - <user>/dirt-wakeword-features    ACAV100M 2000h features .npy + validation_set_features.npy
  - <user>/dirt-wakeword-validation  hand-labeled good/+bad/ WAVs (real-audio metric)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import wave
from contextlib import contextmanager
from itertools import chain
from pathlib import Path

import yaml

# Lazy-import note: anything that lives in a package only available *after*
# install_dependencies() runs (openwakeword, torch, numpy, audiomentations
# etc) is imported inside the function that uses it. `_verify_imports()` runs
# right after install_dependencies and tries every deferred import — if any
# is wrong, the kernel crashes in seconds, not 90 minutes into training.

# ---------------------------------------------------------------------------
# Tunables — mirror the @param sliders from the Colab notebook
# ---------------------------------------------------------------------------

TARGET_WORD = "hey_claudia"
NUMBER_OF_EXAMPLES = 30_000
NUMBER_OF_TRAINING_STEPS = 20_000
# max_negative_weight floor for auto_train. Critical knob: openwakeword's
# auto_train *automatically doubles* this value (up to twice) when validation
# FP/hour exceeds TARGET_FP_PER_HOUR. So 500 → 1000 → 2000 in the worst case.
# Setting this too high (we tried 3000) starves the model of positive signal —
# v5 first run collapsed to 21% recall because auto_train escalated to 12000.
# v3 (89% recall) used 500.
FALSE_ACTIVATION_PENALTY = 500
# How many FP/hour we tolerate before auto_train escalates max_negative_weight.
# Upstream default 0.2 → 1.0 still escalated twice (recall capped at 38%). The
# `best_val_fp` checked against this is the *training-time* validation FP/hr,
# which runs much higher than the final-model FP/hr; setting this very high
# disables escalation so max_negative_weight stays at its starting value.
# Speaker-verifier (parallel work) handles the precision tail; the wake model
# biases for recall.
TARGET_FP_PER_HOUR = 10.0

# Per-source duplication factors for files we seed into positive_train/ and
# negative_train/ before --generate_clips. Duplicating a clip on disk is
# openwakeword's only mechanism for per-sample weighting — the dataloader
# samples files uniformly, so a clip present N times has N× pull on the loss.
#
# Pool-share targeting: with N source clones and M source realmic, real-mic's
# share of the duplicated pool is M*REALMIC / (N*CLONE + M*REALMIC). At
# 2000 clones × 1 + 18 realmic × 10, real-mic = 180/2180 ≈ 8% of positives.
CLONE_DUPLICATION = 1  # ElevenLabs voice clones (synthetic positives)
NEIGHBOR_DUPLICATION = 1  # ElevenLabs phonetic-neighbor negatives (synthetic)
REALMIC_POSITIVE_DUPLICATION = 10  # Hand-recorded "hey claudia" through the Jabra (gold)
REALMIC_NEGATIVE_DUPLICATION = 10  # Hand-recorded non-wake phrases through the Jabra (gold)
HARVESTED_DUPLICATION = 10  # Real false-positives from var/logs/wake_audio/ (gold)

# ---------------------------------------------------------------------------
# Dataset mount points — adjust if you rename datasets in the Kaggle UI
# ---------------------------------------------------------------------------

# Kaggle dataset mount layout differs by runtime: GPU/CPU images mount at
# /kaggle/input/<slug>/, but the TPU runtime mounts at
# /kaggle/input/datasets/<owner>/<slug>/. Probe both at startup.
KAGGLE_INPUT = Path("/kaggle/input")


def _find_dataset(slug: str) -> Path:
    candidates = [
        KAGGLE_INPUT / slug,
        KAGGLE_INPUT / "datasets" / "akravetz" / slug,
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fall through and let verify_inputs() print a useful tree dump.
    return candidates[0]


MINE = _find_dataset("dirt-wakeword-mine")
BG = _find_dataset("dirt-wakeword-bg")
FEATURES = _find_dataset("dirt-wakeword-features")
VALIDATION = _find_dataset("dirt-wakeword-validation")

EXPECTED_INPUTS = {
    "voice_samples": MINE / "voice_samples",
    "custom_rirs": MINE / "rirs",
    "audioset_16k": BG / "audioset_16k",
    "fma": BG / "fma",
    "train_features": FEATURES / "openwakeword_features_ACAV100M_2000_hrs_16bit.npy",
    "validation_features": FEATURES / "validation_set_features.npy",
    "validation_good": VALIDATION / "good",
    "validation_bad": VALIDATION / "bad",
}

WORK = Path("/kaggle/working")
OUT_DIR = WORK / "my_custom_model"


def sh(cmd: str, *, cwd: Path | None = None) -> None:
    """Run a shell command, stream stdout, raise on non-zero exit."""
    print(f"$ {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True, cwd=cwd)


@contextmanager
def phase(name: str):
    """Wall-clock phase timer. Logs `=== phase {name} START / END elapsed=Ns`
    so a single grep over the kernel log gives a per-phase profile.

    Bracketed message format keeps phase entries greppable from upstream's
    chatter (Piper progress bars, openwakeword INFO lines, tqdm output)."""
    print(f"\n=== phase {name} START", flush=True)
    t0 = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - t0
        m, s = divmod(elapsed, 60)
        print(
            f"=== phase {name} END elapsed={elapsed:.1f}s ({int(m)}m{s:.1f}s)",
            flush=True,
        )


def _verify_imports() -> None:
    """Fail-fast import verification. Runs after install_dependencies() so a
    wrong import path / missing pin / version mismatch crashes the kernel
    within seconds — not 90 minutes into a training run.

    Adding a new lazy import elsewhere in this file? Add it here too.
    """
    print("=== verifying deferred imports", flush=True)
    try:
        import numpy as _np  # noqa: F401
        import torch as _torch  # noqa: F401
        from openwakeword.data import (  # noqa: F401
            augment_clips as _augment_clips,
            mmap_batch_generator as _mmap_batch_generator,
        )
        from openwakeword.model import Model as _InferenceModel  # noqa: F401
        from openwakeword.train import Model as _TrainingModel  # noqa: F401
        from openwakeword.utils import (  # noqa: F401
            compute_features_from_generator as _compute_features_from_generator,
        )
    except ImportError as e:
        sys.exit(
            f"FATAL: required import failed after install_dependencies(): {e}\n"
            "Check that install_dependencies pinned all required packages and "
            "that the openwakeword module path is correct."
        )
    print("  all imports OK", flush=True)


def verify_inputs() -> None:
    missing = [name for name, p in EXPECTED_INPUTS.items() if not p.exists()]
    if missing:
        # Diagnostic dump — show what's actually mounted so slug mismatches
        # (the most common cause) are obvious from the kernel log.
        print("=== /kaggle/input/ tree (3 levels) ===", file=sys.stderr)
        if KAGGLE_INPUT.exists():
            for path in sorted(KAGGLE_INPUT.rglob("*")):
                rel = path.relative_to(KAGGLE_INPUT)
                if len(rel.parts) <= 3:
                    print(f"  {rel}", file=sys.stderr)
        else:
            print("  (/kaggle/input does not exist)", file=sys.stderr)
        print("=== expected mounts ===", file=sys.stderr)
        for name in missing:
            print(f"  MISSING: {name} -> {EXPECTED_INPUTS[name]}", file=sys.stderr)
        raise SystemExit(
            "One or more expected Kaggle dataset mounts are missing. "
            "Check kernel-metadata.json `dataset_sources` and dataset contents."
        )
    print("All expected input mounts present.")


# ---------------------------------------------------------------------------
# Step 1: install dependencies + clone training repo
# ---------------------------------------------------------------------------


def install_dependencies() -> None:
    os.chdir(WORK)

    if not (WORK / "piper-sample-generator").exists():
        sh("git clone https://github.com/rhasspy/piper-sample-generator")
        sh(
            "wget -O piper-sample-generator/models/en_US-libritts_r-medium.pt "
            "https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt"
        )
        sh("git checkout 213d4d5", cwd=WORK / "piper-sample-generator")

    # Piper + torch stack (Kaggle images ship with torch but rarely the exact
    # version pinned by the upstream notebook; pin explicitly for reproducibility).
    sh("pip install --quiet piper-tts piper-phonemize-cross webrtcvad")
    sh(
        "pip install --quiet torch==2.5.0 torchvision==0.20.0 torchaudio==2.5.0 "
        "--index-url https://download.pytorch.org/whl/cu121"
    )

    if not (WORK / "openwakeword").exists():
        sh("git clone https://github.com/dscripka/openwakeword")
    sh("pip install --quiet -e ./openwakeword --no-deps")

    sh(
        "pip install --quiet "
        "mutagen==1.47.0 torchinfo==1.8.0 torchmetrics==1.2.0 "
        "speechbrain==0.5.14 audiomentations==0.33.0 torch-audiomentations==0.11.0 "
        "acoustics==0.2.6 onnxruntime==1.22.1 ai_edge_litert==1.4.0 onnxsim "
        "onnx2tf onnx==1.19.1 onnx_graphsurgeon sng4onnx pronouncing==0.2.0 "
        "datasets==2.14.6 deep-phonemizer==0.0.19"
    )

    # openwakeword's bundled embedding + mel models (Colab notebook pulls these
    # from GitHub releases; Kaggle kernels have internet by default so same flow works).
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


# ---------------------------------------------------------------------------
# Step 2: build the training YAML pointing at Kaggle mounts
# ---------------------------------------------------------------------------


def build_config() -> Path:
    base_yaml = WORK / "openwakeword/examples/custom_model.yml"
    config = yaml.safe_load(base_yaml.read_text())

    config["target_phrase"] = [TARGET_WORD.replace("_", " ")]
    config["model_name"] = TARGET_WORD
    config["n_samples"] = NUMBER_OF_EXAMPLES
    config["n_samples_val"] = max(500, NUMBER_OF_EXAMPLES // 10)
    config["steps"] = NUMBER_OF_TRAINING_STEPS
    # NOTE: target_accuracy and target_recall are dead keys in openwakeword's
    # train.py — never read. The actual quality knob is target_fp_per_hour
    # (which controls auto_train's max_negative_weight escalation).
    config["output_dir"] = str(OUT_DIR)
    config["max_negative_weight"] = FALSE_ACTIVATION_PENALTY
    config["target_false_positives_per_hour"] = TARGET_FP_PER_HOUR
    # v8 — rebalance batch composition. Upstream defaults
    #   ACAV100M_sample=1024, adversarial_negative=50, positive=50
    # mean only 50 positive gradient slots per batch. With 2018+180 positive
    # files (real-mic at 10× duplication), each batch sees ~4 real-mic
    # positives in expectation — too few for the recall-floor failure mode.
    # Bumping positive→200 + halving ACAV→512 keeps total batch size
    # manageable while quadrupling per-batch positive gradient diversity.
    config["batch_n_per_class"] = {
        "ACAV100M_sample": 512,
        "adversarial_negative": 50,
        "positive": 200,
    }

    # Kaggle-mounted paths
    config["background_paths"] = [
        str(EXPECTED_INPUTS["audioset_16k"]),
        str(EXPECTED_INPUTS["fma"]),
    ]
    config["false_positive_validation_data_path"] = str(
        EXPECTED_INPUTS["validation_features"]
    )
    config["feature_data_files"] = {
        "ACAV100M_sample": str(EXPECTED_INPUTS["train_features"]),
    }
    config["rir_paths"] = [str(EXPECTED_INPUTS["custom_rirs"])]

    out_yaml = WORK / "my_model.yaml"
    out_yaml.write_text(yaml.dump(config))
    print(f"Wrote training config -> {out_yaml}")
    return out_yaml


# ---------------------------------------------------------------------------
# Step 3: seed user-provided WAVs into openwakeword's pre-train directories
# ---------------------------------------------------------------------------
#
# Why this exists: openwakeword has NO config key for user-provided positive
# or negative WAVs. The canonical injection point is to drop files into
# <output_dir>/<model_name>/{positive,negative}_{train,test}/ BEFORE running
# --generate_clips. The script then sees `len(os.listdir(...)) >= 0.95 *
# n_samples` and either skips TTS generation or tops up the rest.
#
# Naming convention used here (matters for the option-2 augmentation fork):
#   positive_train/synth_clone_<orig>.wav      ElevenLabs voice clones (TTS)
#   positive_train/realmic_pos_<orig>.wav      Hand-recorded "hey claudia"
#   negative_train/synth_neighbor_<orig>.wav   ElevenLabs phonetic neighbors
#   negative_train/realmic_neg_<orig>.wav      Hand-recorded non-wake phrases
#   negative_train/harvested_<orig>.wav        Real var/logs/wake_audio/ captures


def _seed_dir(src_files, dest_dir: Path, prefix: str, n_dup: int) -> int:
    written = 0
    for src in src_files:
        for i in range(n_dup):
            suffix = f"_dup{i}" if n_dup > 1 else ""
            shutil.copy(src, dest_dir / f"{prefix}{src.stem}{suffix}.wav")
            written += 1
    return written


def prepare_seed_clips() -> None:
    pos_train = OUT_DIR / TARGET_WORD / "positive_train"
    neg_train = OUT_DIR / TARGET_WORD / "negative_train"
    pos_train.mkdir(parents=True, exist_ok=True)
    neg_train.mkdir(parents=True, exist_ok=True)

    # ---- Positives: split synthetic-clone from real-mic by filename prefix ----
    pos_src = EXPECTED_INPUTS["voice_samples"]
    realmic_pos = sorted(pos_src.glob("realmic-pos_*.wav"))
    synth_clones = [
        p for p in sorted(pos_src.glob("*.wav"))
        if not p.name.startswith("realmic-pos_")
    ]
    n_clones = _seed_dir(synth_clones, pos_train, "synth_clone_", CLONE_DUPLICATION)
    n_realmic_pos = _seed_dir(
        realmic_pos, pos_train, "realmic_pos_", REALMIC_POSITIVE_DUPLICATION
    )

    # ---- Negatives: split synthetic / harvested / realmic by filename prefix ----
    neg_src = MINE / "negatives"
    n_synth = n_harv = n_realmic_neg = 0
    if neg_src.exists():
        all_negs = sorted(neg_src.glob("*.wav"))
        harvested = [p for p in all_negs if p.name.startswith("harvested_")]
        realmic_neg = [p for p in all_negs if p.name.startswith("realmic-neg_")]
        synthetic = [
            p for p in all_negs
            if not p.name.startswith("harvested_")
            and not p.name.startswith("realmic-neg_")
        ]
        n_synth = _seed_dir(
            synthetic, neg_train, "synth_neighbor_", NEIGHBOR_DUPLICATION
        )
        n_realmic_neg = _seed_dir(
            realmic_neg, neg_train, "realmic_neg_", REALMIC_NEGATIVE_DUPLICATION
        )
        n_harv = _seed_dir(harvested, neg_train, "harvested_", HARVESTED_DUPLICATION)

    print(
        f"Seeded positives: {n_clones} synth-clone (×{CLONE_DUPLICATION}) "
        f"+ {n_realmic_pos} realmic-pos (×{REALMIC_POSITIVE_DUPLICATION}) "
        f"= {n_clones + n_realmic_pos} total"
    )
    print(
        f"Seeded negatives: {n_synth} synth-neighbor (×{NEIGHBOR_DUPLICATION}) "
        f"+ {n_realmic_neg} realmic-neg (×{REALMIC_NEGATIVE_DUPLICATION}) "
        f"+ {n_harv} harvested (×{HARVESTED_DUPLICATION}) "
        f"= {n_synth + n_realmic_neg + n_harv} total"
    )


def restore_tts_cache_if_mounted() -> bool:
    """v8 — if a `dirt-wakeword-tts-cache` Kaggle dataset is attached, copy
    the cached Piper-generated WAVs into the four pre-train directories.
    Upstream's `--generate_clips` then sees ≥95 % of `n_samples` already in
    place and skips Piper entirely (saves ~10–20 min per run, depending on
    what the timing instrumentation tells us).

    Cache is invalidated by a key mismatch — fail loud rather than silently
    train on stale TTS data. Operator workflow for rebuilding the cache lives
    in `apps/wake-word/CLAUDE.md`.

    Returns True if the cache was used. The dataset isn't yet attached —
    this hook is wired up in code so the moment we add it to
    `kernel-metadata.json:dataset_sources`, it activates with no further
    code change.
    """
    cache_dir = _find_dataset("dirt-wakeword-tts-cache")
    if not cache_dir.exists():
        print("(no TTS cache attached — `--generate_clips` will run Piper)")
        return False
    cache_key_path = cache_dir / "cache-key.json"
    if not cache_key_path.exists():
        print(
            f"WARNING: TTS cache attached at {cache_dir} but cache-key.json missing — "
            "ignoring cache and running Piper"
        )
        return False

    expected = {
        "target_phrase": TARGET_WORD.replace("_", " "),
        "n_samples": NUMBER_OF_EXAMPLES,
        "n_samples_val": max(500, NUMBER_OF_EXAMPLES // 10),
    }
    actual = json.loads(cache_key_path.read_text())
    if actual != expected:
        sys.exit(
            f"FATAL: TTS cache key mismatch.\n  cache: {actual}\n  run:   {expected}\n"
            "Rebuild the cache (operator workflow in apps/wake-word/CLAUDE.md) "
            "or detach the dataset from this kernel."
        )

    print(f"=== TTS cache hit: copying cached WAVs from {cache_dir}")
    total = 0
    for subdir in ("positive_train", "negative_train", "positive_test", "negative_test"):
        src = cache_dir / subdir
        if not src.is_dir():
            print(f"  (warning) {subdir}/ missing from cache; that subset will fall through to Piper")
            continue
        dst = OUT_DIR / TARGET_WORD / subdir
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for wav in src.glob("*.wav"):
            shutil.copy(wav, dst / wav.name)
            n += 1
        total += n
        print(f"  {subdir}: {n} WAVs restored")
    print(f"  TTS cache total: {total} WAVs (Piper TTS will be skipped)")
    return True


# ---------------------------------------------------------------------------
# Step 4: run openwakeword training pipeline (custom driver — soft-fork)
# ---------------------------------------------------------------------------


def custom_train(config_path: Path) -> None:
    """Soft-fork of openwakeword's --train_model.

    Reasons we don't shell out to upstream's --train_model:

    1. `auto_train` has a bug — `self.best_val_fp = 1000` is initialized and
       never updated, so `if self.best_val_fp > target_fp_per_hour:` always
       fires twice. End result: max_negative_weight is 4× whatever we
       configured, model converges precision-collapsed (recall 21–38%).
    2. `auto_train` ends by calling `convert_onnx_to_tflite` which imports
       `onnx_tf` — incompatible with python 3.11+ in current openwakeword.
       The .onnx is saved before the broken step but the process exit code
       is non-zero.
    3. We want real-audio validation (`var/wake-word/validation/`) as the
       canonical metric, not synthetic Piper-test recall (which was
       empirically misleading: 38% synthetic ≈ 56% real-audio recall).

    What we keep from upstream:

      - `--generate_clips` (Piper TTS); works fine
      - `--augment_clips` (audiomentations + feature compute); works fine
      - `Model` class + `train_model()` inner loop; the actual training
        mechanics are correct — only `auto_train`'s outer loop is broken
      - `export_model()` ONNX export

    What we replace:

      - `auto_train`'s 3-sequence escalation → single `train_model()` call
        with a linear weight schedule
      - synthetic-Piper-test as canonical metric → real-audio validation
        from /kaggle/input/dirt-wakeword-validation/
    """
    train_py = WORK / "openwakeword/openwakeword/train.py"
    with phase("restore_tts_cache"):
        restore_tts_cache_if_mounted()
    with phase("generate_clips"):
        sh(f"{sys.executable} {train_py} --training_config {config_path} --generate_clips")
    # v8: replace upstream's --augment_clips with our per-subset variant.
    # Real-mic and harvested clips already have RIR + ambient baked in;
    # convolving them with another RIR is an unphysical 2-room cascade.
    with phase("augment+features"):
        _augment_and_compute_features()
    with phase("train_loop"):
        _custom_train_model()


def _augment_and_compute_features() -> None:
    """v8 — soft-fork of `train.py --augment_clips` with per-subset augmentation.

    For each of the 4 feature subsets (positive_train, negative_train,
    positive_test, negative_test) we split files by filename prefix:

      synth (default):    Piper-generated UUIDs, synth_clone_*, synth_neighbor_*
      real-room recorded: realmic_*, harvested_*

    Synth gets the default augmentation pipeline. Real-room recorded gets
    `RIR=0.0` + `AddBackgroundNoise=0.5` (down from 0.75) — additive noise is
    still useful for robustness; the RIR is omitted because the clip already
    carries the deployment room's reverb.

    `n_total` for `compute_features_from_generator` is properly scaled by
    `augmentation_rounds` (upstream has a latent bug here when rounds > 1).
    """
    import torch
    from openwakeword.data import augment_clips
    from openwakeword.utils import compute_features_from_generator

    config = yaml.safe_load((WORK / "my_model.yaml").read_text())
    feature_save_dir = OUT_DIR / TARGET_WORD

    # Build the background and RIR file lists (mirrors upstream's __main__).
    bg_dup = config.get("background_paths_duplication_rate") or [
        1
    ] * len(config["background_paths"])
    if len(bg_dup) != len(config["background_paths"]):
        bg_dup = [1] * len(config["background_paths"])
    bg_paths: list[str] = []
    for path, rate in zip(config["background_paths"], bg_dup, strict=False):
        bg_paths.extend([i.path for i in os.scandir(path)] * rate)
    rir_paths = [i.path for j in config["rir_paths"] for i in os.scandir(j)]

    DEFAULTS = {
        "SevenBandParametricEQ": 0.25,
        "TanhDistortion": 0.25,
        "PitchShift": 0.25,
        "BandStopFilter": 0.25,
        "AddColoredNoise": 0.25,
        "AddBackgroundNoise": 0.75,
        "Gain": 1.0,
        "RIR": 0.5,
    }
    REAL_AUDIO = {**DEFAULTS, "RIR": 0.0, "AddBackgroundNoise": 0.5}

    rounds = config["augmentation_rounds"]
    n_cpus = os.cpu_count() or 1
    ncpu = 1 if torch.cuda.is_available() else max(1, n_cpus // 2)
    device = "gpu" if torch.cuda.is_available() else "cpu"

    SUBSETS = (
        ("positive_train", "positive_features_train.npy"),
        ("negative_train", "negative_features_train.npy"),
        ("positive_test", "positive_features_test.npy"),
        ("negative_test", "negative_features_test.npy"),
    )

    def is_real_audio(name: str) -> bool:
        return name.startswith("realmic_") or name.startswith("harvested_")

    print("=== per-subset augmentation + feature compute (v8) ===", flush=True)
    for subset_name, out_npy in SUBSETS:
        subset_dir = OUT_DIR / TARGET_WORD / subset_name
        all_files = sorted(str(f) for f in subset_dir.glob("*.wav"))
        synth = [f for f in all_files if not is_real_audio(Path(f).name)]
        real = [f for f in all_files if is_real_audio(Path(f).name)]
        if not synth and not real:
            print(f"  {subset_name}: empty, skipping", flush=True)
            continue

        synth_input = synth * rounds
        real_input = real * rounds
        n_total = len(synth_input) + len(real_input)

        gens = []
        if synth_input:
            gens.append(
                augment_clips(
                    synth_input,
                    total_length=config["total_length"],
                    batch_size=config["augmentation_batch_size"],
                    augmentation_probabilities=DEFAULTS,
                    background_clip_paths=bg_paths,
                    RIR_paths=rir_paths,
                )
            )
        if real_input:
            gens.append(
                augment_clips(
                    real_input,
                    total_length=config["total_length"],
                    batch_size=config["augmentation_batch_size"],
                    augmentation_probabilities=REAL_AUDIO,
                    background_clip_paths=bg_paths,
                    RIR_paths=rir_paths,
                )
            )

        out_path = feature_save_dir / out_npy
        print(
            f"  {subset_name}: {len(synth)} synth (×{rounds}, RIR=0.5) + "
            f"{len(real)} realroom (×{rounds}, RIR=0) → {out_path.name}",
            flush=True,
        )
        compute_features_from_generator(
            chain(*gens),
            n_total=n_total,
            clip_duration=config["total_length"],
            output_file=str(out_path),
            device=device,
            ncpu=ncpu,
        )


def _custom_train_model() -> None:
    """The soft-fork meat: replace upstream's --train_model __main__ block."""
    # Imports happen lazily so the module can still load when openwakeword
    # isn't installed (e.g., on the operator's laptop while editing).
    # `_verify_imports()` already validated these paths at the start of main.
    import numpy as np
    import torch
    from openwakeword.data import mmap_batch_generator
    from openwakeword.train import Model

    config = yaml.safe_load((WORK / "my_model.yaml").read_text())
    feature_save_dir = OUT_DIR / TARGET_WORD

    # Input shape derived from the positive_test feature file (same as upstream).
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
        """Reshape negative feature batches to model input length if needed."""
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
    feature_data_files["positive"] = str(feature_save_dir / "positive_features_train.npy")
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

    # ---- X_val_fp: 11.3 h ACAV speech, FP/hour metric ----
    X_val_fp_arr = np.load(config["false_positive_validation_data_path"])
    X_val_fp_arr = np.array(
        [X_val_fp_arr[i : i + input_shape[0]] for i in range(0, X_val_fp_arr.shape[0] - input_shape[0], 1)]
    )
    X_val_fp_labels = np.zeros(X_val_fp_arr.shape[0]).astype(np.float32)
    X_val_fp = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(X_val_fp_arr), torch.from_numpy(X_val_fp_labels)
        ),
        batch_size=len(X_val_fp_labels),
    )

    # ---- X_val: synthetic Piper test set (we keep this for inner-loop tracking;
    #             the real metric is post-training real-audio validation) ----
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

    # ---- Single training pass; no auto_train escalation ------------------
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

    # ---- v8: pick best checkpoint by REAL-AUDIO F1 ------------------------
    # Synthetic Piper-test recall (`val_recall`) drifts meaningfully from
    # deployment recall — v5 hit 38 % synthetic → 56 % real on the small set
    # and 36 % real on the expanded set. Selecting on synthetic ships the
    # wrong checkpoint. Score every saved checkpoint against the hand-labeled
    # real-audio set and pick max F1 at threshold 0.5.
    best_model = _select_best_by_real_f1(oww)

    oww.export_model(
        model=best_model, model_name=TARGET_WORD, output_dir=str(OUT_DIR)
    )
    print(f"Exported ONNX → {OUT_DIR / (TARGET_WORD + '.onnx')}")


def _select_best_by_real_f1(oww, threshold: float = 0.5):
    """v8 — pick the saved checkpoint with the highest F1 against real audio.

    For each candidate in `oww.best_models`, export a temporary ONNX,
    score every WAV in `validation/{good,bad}/`, compute F1 at the given
    threshold, and pick max. Tiebreak by recall.

    The cost is ~few hundred ms per candidate (export + ~104 forward passes
    on CPU); with 20 saved checkpoints that's a couple of minutes of
    post-training overhead — small relative to the 60-minute training run
    and bought us a meaningful win in v5 retrospect (the checkpoint we
    shipped was *not* the best by real-audio F1).
    """
    import numpy as np
    from openwakeword.model import Model as InferenceModel

    if not oww.best_models:
        print(
            "No checkpoints saved — falling back to final model state",
            file=sys.stderr,
        )
        return oww.model

    chunk = 1280  # 80 ms at 16 kHz

    def load_wav(p: Path) -> np.ndarray:
        with wave.open(str(p), "rb") as w:
            return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)



    def score_clips(model: InferenceModel, name: str, paths: list[Path]) -> list[float]:
        out = []
        for path in paths:
            wav = load_wav(path)
            model.reset()
            peak = 0.0
            for s in range(0, len(wav) - chunk + 1, chunk):
                v = float(model.predict(wav[s : s + chunk])[name])
                if v > peak:
                    peak = v
            out.append(peak)
        return out

    good_paths = sorted(EXPECTED_INPUTS["validation_good"].glob("*.wav"))
    bad_paths = sorted(EXPECTED_INPUTS["validation_bad"].glob("*.wav"))
    n_good, n_bad = len(good_paths), len(bad_paths)
    if n_good == 0 or n_bad == 0:
        print(
            "Validation set empty; falling back to synthetic-recall selection",
            file=sys.stderr,
        )
        scores = oww.best_model_scores
        ok = [(i, s) for i, s in enumerate(scores) if float(s["val_fp_per_hr"]) <= 2.0]
        if not ok:
            ok = list(enumerate(scores))
        best_idx, _ = max(ok, key=lambda kv: float(kv[1]["val_recall"]))
        return oww.best_models[best_idx]

    tmp_dir = WORK / "_candidates"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"=== real-audio F1 checkpoint selection: {len(oww.best_models)} candidates "
        f"vs {n_good} good / {n_bad} bad ===",
        flush=True,
    )

    rows: list[tuple[int, float, float, float, int]] = []
    for i, model in enumerate(oww.best_models):
        slug = f"cand_{i:03d}"
        oww.export_model(
            model=model, model_name=slug, output_dir=str(tmp_dir)
        )
        onnx_path = tmp_dir / f"{slug}.onnx"
        infer = InferenceModel(wakeword_model_paths=[str(onnx_path)])
        name = next(iter(infer.models.keys()))
        good_scores = score_clips(infer, name, good_paths)
        bad_scores = score_clips(infer, name, bad_paths)
        tp = sum(1 for s in good_scores if s >= threshold)
        fp = sum(1 for s in bad_scores if s >= threshold)
        recall = tp / n_good
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        step = oww.best_model_scores[i].get("training_step_ndx", -1)
        rows.append((i, recall, precision, f1, int(step)))
        print(
            f"  cand {i:>3} step={step:>5} | recall={recall:.3f} "
            f"prec={precision:.3f} f1={f1:.3f}",
            flush=True,
        )
        onnx_path.unlink(missing_ok=True)

    # Pick max F1; tie-break by recall, then by latest step
    rows.sort(key=lambda r: (r[3], r[1], r[4]), reverse=True)
    best_i, best_r, best_p, best_f1, best_step = rows[0]
    print(
        f"\nBest checkpoint by real-audio F1: cand {best_i} step={best_step} "
        f"(recall={best_r:.3f}, precision={best_p:.3f}, F1={best_f1:.3f})"
    )
    return oww.best_models[best_i]


def validate_against_real_set() -> None:
    """Score the trained ONNX against var/wake-word/validation/. Save report.

    This is the canonical metric. The synthetic Piper-test recall reported by
    Model.train_model's inner loop has been empirically misleading vs real
    deployment (38% synthetic → 56% real-audio in v5 first run). Always look
    here before deciding ship/no-ship.
    """
    import numpy as np
    from openwakeword.model import Model

    onnx_path = OUT_DIR / f"{TARGET_WORD}.onnx"
    if not onnx_path.exists():
        print("validate: no ONNX produced; skipping", file=sys.stderr)
        return

    chunk = 1280  # 80 ms at 16 kHz — openwakeword inference frame size
    model = Model(wakeword_model_paths=[str(onnx_path)])
    name = next(iter(model.models.keys()))

    def peak(wav_path: Path) -> float:
        with wave.open(str(wav_path), "rb") as w:
            wav = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        model.reset()
        p = 0.0
        for start in range(0, len(wav) - chunk + 1, chunk):
            s = float(model.predict(wav[start : start + chunk])[name])
            if s > p:
                p = s
        return p

    good = [
        peak(p) for p in sorted(EXPECTED_INPUTS["validation_good"].glob("*.wav"))
    ]
    bad = [
        peak(p) for p in sorted(EXPECTED_INPUTS["validation_bad"].glob("*.wav"))
    ]

    lines = [
        "VALIDATION REPORT (real audio)",
        "=" * 50,
        f"Model:  {onnx_path.name}",
        f"good/:  {len(good)} positives",
        f"bad/:   {len(bad)} negatives (in-the-wild false-positives)",
        "",
        f"{'thresh':>7} | {'recall':>7} | {'fps':>7} | {'precision':>9} | {'f1':>5}",
        "-" * 50,
    ]
    for t in (0.30, 0.40, 0.50, 0.60, 0.70):
        tp = sum(1 for s in good if s >= t)
        fp = sum(1 for s in bad if s >= t)
        recall = tp / len(good) if good else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        lines.append(
            f"  {t:>5.2f} | {recall:>7.1%} | {fp:>2}/{len(bad):<3}  | {precision:>9.1%} | {f1:>.3f}"
        )

    report = "\n".join(lines)
    print()
    print(report)
    print()
    (WORK / "validation-report.txt").write_text(report + "\n")


# ---------------------------------------------------------------------------
# Step 4: export tflite + stage outputs to /kaggle/working (auto-published)
# ---------------------------------------------------------------------------


def export() -> None:
    onnx_path = OUT_DIR / f"{TARGET_WORD}.onnx"
    float32_tflite = OUT_DIR / f"{TARGET_WORD}_float32.tflite"
    final_tflite = OUT_DIR / f"{TARGET_WORD}.tflite"

    sh(f"onnx2tf -i {onnx_path} -o {OUT_DIR} -kat onnx____Flatten_0")
    if float32_tflite.exists():
        shutil.move(str(float32_tflite), str(final_tflite))

    # Surface the two files at the /kaggle/working root so they show up as
    # prominent outputs in the kernel UI and in `kaggle kernels output`.
    for src in (onnx_path, final_tflite):
        if src.exists():
            shutil.copy(src, WORK / src.name)
            print(f"Published -> {WORK / src.name}")


# ---------------------------------------------------------------------------


def main() -> None:
    t_start = time.monotonic()
    with phase("verify_inputs"):
        verify_inputs()
    with phase("install_dependencies"):
        install_dependencies()
    with phase("verify_imports"):
        _verify_imports()
    with phase("build_config"):
        config_path = build_config()
    with phase("prepare_seed_clips"):
        prepare_seed_clips()
    with phase("custom_train"):
        custom_train(config_path)  # itself contains nested `phase()` blocks
    with phase("export"):
        export()
    with phase("validate_against_real_set"):
        validate_against_real_set()
    total = time.monotonic() - t_start
    m, s = divmod(total, 60)
    print(
        f"\n=== TOTAL elapsed={total:.1f}s ({int(m)}m{s:.1f}s)\n"
        "Training complete. Pull artifacts with: "
        "kaggle kernels output <kernel-slug>"
    )


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# TODO (option 2 — per-subset augmentation control):
#
# Current limitation: openwakeword's --augment_clips applies the SAME
# augmentation pipeline (RIR convolution + background mixing + noise injection)
# to every file in negative_train/. For real-room captures that's a
# physically-questionable double-convolve — the clip already has the room's
# RIR baked in. Synthetic neighbors absolutely need the augmentation; harvested
# don't.
#
# Patch sketch (~30 LOC, no openwakeword fork — calls its own data fns):
#
#   from itertools import chain
#   from openwakeword.data import augment_clips, compute_features_from_generator
#
#   DEFAULTS = {"SevenBandParametricEQ":0.25,"TanhDistortion":0.25,
#               "PitchShift":0.25,"BandStopFilter":0.25,
#               "AddColoredNoise":0.25,"AddBackgroundNoise":0.75,
#               "Gain":1.0,"RIR":0.5}
#   NO_AUG = dict.fromkeys(DEFAULTS, 0.0) | {"Gain": 1.0}
#
#   synth = list(neg_train.glob("synth_*.wav"))
#   harv  = list(neg_train.glob("harvested_*.wav"))
#   synth_gen = augment_clips(synth, total_length=L, batch_size=B,
#                             background_clip_paths=bg, RIR_paths=rir)
#   harv_gen  = augment_clips(harv, total_length=L, batch_size=B,
#                             augmentation_probabilities=NO_AUG,
#                             background_clip_paths=[], RIR_paths=[])
#   compute_features_from_generator(chain(synth_gen, harv_gen),
#       n_total=len(synth)+len(harv), clip_duration=L,
#       output_file=str(OUT_DIR/TARGET_WORD/"negative_features_train.npy"))
#
# Then SKIP --augment_clips in train() and go straight to --train_model;
# that step sees the .npy already exists and uses it. Mirror for _test.npy.
# Promote to real code once v1 has a baseline confusion matrix to compare to.
