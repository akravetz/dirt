"""Kaggle port of the openWakeWord Colab training notebook.

Runs as a Kaggle Script Kernel (`kernel_type: script` in kernel-metadata.json).
End-to-end: generate synthetic positives (piper) -> augment -> train -> export
ONNX + tflite to /kaggle/working, which Kaggle auto-publishes as kernel output.

Source: debug/automatic_model_training.py (Colab). The three bulk-download cells
(MIT RIRs, AudioSet, FMA, 2000h features, 11h validation features) are replaced
with /kaggle/input/* mounts — those corpora are uploaded once as Kaggle Datasets
and mounted read-only at runtime. Edit EXPECTED_INPUTS below if you rename them.

Required datasets (attach via kernel-metadata.json `dataset_sources`):
  - <user>/dirt-wakeword-mine       ElevenLabs clones + captured RIRs + curated negatives
  - <user>/dirt-wakeword-bg         audioset_16k/ + fma/ as WAV trees
  - <user>/dirt-wakeword-features   ACAV100M 2000h features .npy + validation_set_features.npy
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Tunables — mirror the @param sliders from the Colab notebook
# ---------------------------------------------------------------------------

TARGET_WORD = "hey_claudia"
NUMBER_OF_EXAMPLES = 30_000
NUMBER_OF_TRAINING_STEPS = 20_000
FALSE_ACTIVATION_PENALTY = 3_000  # per-class loss weight cap (linspace 1 -> this over training)

# Per-source duplication factors for files we seed into positive_train/ and
# negative_train/ before --generate_clips. Duplicating a clip on disk is
# openwakeword's only mechanism for per-sample weighting — the dataloader
# samples files uniformly, so a clip present N times has N× pull on the loss.
CLONE_DUPLICATION = 1       # ElevenLabs voice clones (synthetic positives)
NEIGHBOR_DUPLICATION = 1    # ElevenLabs phonetic-neighbor negatives (synthetic)
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

EXPECTED_INPUTS = {
    "voice_samples": MINE / "voice_samples",
    "custom_rirs": MINE / "rirs",
    "audioset_16k": BG / "audioset_16k",
    "fma": BG / "fma",
    "train_features": FEATURES / "openwakeword_features_ACAV100M_2000_hrs_16bit.npy",
    "validation_features": FEATURES / "validation_set_features.npy",
}

WORK = Path("/kaggle/working")
OUT_DIR = WORK / "my_custom_model"


def sh(cmd: str, *, cwd: Path | None = None) -> None:
    """Run a shell command, stream stdout, raise on non-zero exit."""
    print(f"$ {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True, cwd=cwd)


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
    for name in ("embedding_model.onnx", "embedding_model.tflite",
                 "melspectrogram.onnx", "melspectrogram.tflite"):
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
    config["target_accuracy"] = 0.5
    config["target_recall"] = 0.25
    config["output_dir"] = str(OUT_DIR)
    config["max_negative_weight"] = FALSE_ACTIVATION_PENALTY

    # Kaggle-mounted paths
    config["background_paths"] = [
        str(EXPECTED_INPUTS["audioset_16k"]),
        str(EXPECTED_INPUTS["fma"]),
    ]
    config["false_positive_validation_data_path"] = str(EXPECTED_INPUTS["validation_features"])
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
#   negative_train/synth_neighbor_<orig>.wav   ElevenLabs phonetic neighbors
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

    # Positives — ElevenLabs voice clones
    clones = sorted(EXPECTED_INPUTS["voice_samples"].glob("*.wav"))
    n_pos = _seed_dir(clones, pos_train, "synth_clone_", CLONE_DUPLICATION)

    # Negatives — split harvested (real) from synthetic (TTS neighbors) by name
    neg_src = MINE / "negatives"
    n_synth = n_harv = 0
    if neg_src.exists():
        harvested = sorted(neg_src.glob("harvested_*.wav"))
        synthetic = [p for p in sorted(neg_src.glob("*.wav"))
                     if not p.name.startswith("harvested_")]
        n_synth = _seed_dir(synthetic, neg_train, "synth_neighbor_", NEIGHBOR_DUPLICATION)
        n_harv = _seed_dir(harvested, neg_train, "harvested_", HARVESTED_DUPLICATION)

    print(
        f"Seeded {n_pos} positives | "
        f"{n_synth} synthetic-neighbor + {n_harv} harvested negatives "
        f"(harvested duplicated {HARVESTED_DUPLICATION}x)"
    )


# ---------------------------------------------------------------------------
# Step 4: run openwakeword training pipeline
# ---------------------------------------------------------------------------

def train(config_path: Path) -> None:
    train_py = WORK / "openwakeword/openwakeword/train.py"
    for flag in ("--generate_clips", "--augment_clips", "--train_model"):
        sh(f"{sys.executable} {train_py} --training_config {config_path} {flag}")


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
    verify_inputs()
    install_dependencies()
    config_path = build_config()
    prepare_seed_clips()
    train(config_path)
    export()
    print("Training complete. Pull artifacts with: kaggle kernels output <kernel-slug>")


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
