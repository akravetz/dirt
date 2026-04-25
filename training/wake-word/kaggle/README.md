# Kaggle wake-word training

Ports `training/wake-word/reference/automatic_model_training.py` (originally a Google Colab notebook)
to a headless Kaggle Script Kernel on TPU. One-time setup uploads the heavy
corpora; every training run is a `kaggle kernels push` + wait + pull.

## One-time setup

### 1. Auth the Kaggle CLI

`kaggle` is already installed as a dev dep of the workspace (`uv add --dev
kaggle`). Drop your API token at `~/.kaggle/kaggle.json` (chmod 600), generated
from Kaggle -> Account -> "Create New API Token". Then invoke via
`uv run kaggle ...` (the `scripts/kaggle-train` wrapper handles this for you).

### 2. Stage and upload the three datasets

**`dirt-wakeword-mine`** — your small, frequently-updated stuff:

```bash
MINE=/tmp/dirt-wakeword-mine
mkdir -p $MINE/voice_samples $MINE/rirs $MINE/negatives
cp var/wake-word/voice-clones/*.wav              $MINE/voice_samples/
cp var/wake-word/rirs/*.wav                    $MINE/rirs/
# Curate from var/logs/wake_audio/ manually, then:
# cp <curated>.wav                        $MINE/negatives/
cp training/wake-word/kaggle/datasets/dirt-wakeword-mine/dataset-metadata.json $MINE/
kaggle datasets create -p $MINE           # first time only
# Every subsequent push to add negatives / new clones:
# kaggle datasets version -p $MINE -m "added N harvested negatives"
```

**`dirt-wakeword-bg`** — background corpora, ~GB scale, upload once:

The Colab notebook downloads these at runtime; the fastest one-time capture
is to run the three relevant cells of `training/wake-word/reference/automatic_model_training.py` on
a laptop (or in a throwaway Colab session), then rsync the produced
`audioset_16k/` and `fma/` dirs down:

```bash
BG=/tmp/dirt-wakeword-bg
mkdir -p $BG
# produce $BG/audioset_16k/*.wav and $BG/fma/*.wav by running the relevant
# `!wget` + `scipy.io.wavfile.write` cells, then:
cp training/wake-word/kaggle/datasets/dirt-wakeword-bg/dataset-metadata.json $BG/
kaggle datasets create -p $BG --dir-mode tar   # tar mode keeps directory structure
```

**`dirt-wakeword-features`** — precomputed features, ~4 GB, upload once:

```bash
FEAT=/tmp/dirt-wakeword-features
mkdir -p $FEAT
cd $FEAT
wget https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/openwakeword_features_ACAV100M_2000_hrs_16bit.npy
wget https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/validation_set_features.npy
cp -r <repo>/training/wake-word/kaggle/datasets/dirt-wakeword-features/dataset-metadata.json .
kaggle datasets create -p .
```

## Training run

From the repo root:

```bash
scripts/kaggle-train
```

The wrapper pushes the kernel, polls status every 20s, and pulls
`hey_claudia.onnx` + `hey_claudia.tflite` into the current directory when done.

## Editing the training run

- **Wake-word or hyperparameters** — edit the top of `train_hey_claudia.py`
  (`TARGET_WORD`, `NUMBER_OF_EXAMPLES`, `NUMBER_OF_TRAINING_STEPS`,
  `FALSE_ACTIVATION_PENALTY`, `USE_CUSTOM_POSITIVE_CLIPS`).
- **Adding curated negatives** — drop WAVs into the `dirt-wakeword-mine`
  dataset's `negatives/` subfolder, bump the version, re-push the kernel.
  `custom_negative_phrase_clips` in the YAML config is the openwakeword
  key — wire it in `build_config()` the same way `custom_target_phrase_clips`
  is wired.
- **Force GPU instead of TPU** — toggle the two booleans in
  `kernel-metadata.json`. TPU quota is 20h/week on the free tier; GPU T4 is
  30h/week. TPU is faster for this workload.

## Troubleshooting

- `verify_inputs()` fails with "MISSING: …" — the dataset slug in
  `kernel-metadata.json` doesn't match what's actually uploaded, or the
  directory structure inside the dataset doesn't match `EXPECTED_INPUTS`.
  List the mount with `!ls /kaggle/input/<slug>/` from a Kaggle notebook cell
  to debug.
- `pip install` explosions on the kernel — the Kaggle base image ships newer
  torch/numpy every few months. Check the kernel log; usually a single pinned
  version needs bumping. Kaggle images: https://github.com/Kaggle/docker-python.
- Kernel silently truncates at 9 hours — that's the hard runtime cap. Lower
  `NUMBER_OF_TRAINING_STEPS` or request GPU runtime (which bills against a
  different quota and is sometimes faster than TPU for small models).
