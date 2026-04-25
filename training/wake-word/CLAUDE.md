# training/wake-word/ — operating manual

Wake-word retraining pipeline for the `dirt-voice` channel ("hey Claudia").
Read this before touching any wake-word code, data, or model deployment.

## Layout

**Code (committed, this directory):**

| Path | Purpose |
|---|---|
| `kaggle/` | Kaggle Script Kernel + dataset metadata (the training driver itself) |
| `kaggle/train-hey-claudia.py` | Kernel entrypoint. Runs end-to-end on Kaggle GPU. |
| `kaggle/kernel-metadata.json` | `kaggle kernels push` config (slug, GPU, internet, dataset attachments) |
| `kaggle/datasets/<slug>/dataset-metadata.json` | One file per uploaded Kaggle dataset |
| `data-gen/elevenlabs-clones-batch.py` | Generate synthetic positives via ElevenLabs voice clone |
| `data-gen/elevenlabs-neighbors-batch.py` | Generate synthetic phonetic-neighbor negatives |
| `data-gen/capture-rir-record.py` | RIR capture (Jabra-host side) |
| `data-gen/capture-rir-play.py` | RIR capture (laptop-side sweep player) |
| `validation/live-test.py` | Interactive Jabra-mic test (real-time score stream) |
| `reference/automatic_model_training.py` | Frozen original openwakeword Colab notebook (DO NOT EDIT — kept for reference) |

**Data (gitignored, lives at `<repo>/var/wake-word/`):**

| Path | Contents |
|---|---|
| `voice-clones/` | ElevenLabs synthetic positives (~2000 WAVs). Re-generate via `elevenlabs-clones-batch.py`. |
| `neighbors/` | ElevenLabs synthetic negatives (currently 360 WAVs across 7 phrases). Re-generate via `elevenlabs-neighbors-batch.py`. |
| `rirs/` | Captured room impulse responses (9 WAVs). Re-generate via `capture-rir-record.py` + `capture-rir-play.py`. |
| `rirs-raw/` | Raw sweep recordings before deconvolution (kept for reprocessing). |
| `validation/good/` | Hand-labeled real "hey claudia" utterances. |
| `validation/bad/` | Hand-labeled in-the-wild false positives the model produced. |
| `models/<datestamp>-<version>/hey_claudia.{onnx,tflite}` | Trained outputs versioned by date. |
| `models/current` | Symlink to the active version. **`apps/voice/.../voice.py` reads this path.** |
| `kaggle-stage/` | Local pipeline staging (features `.npy`, parquet cache, bg WAVs). |

**Operator entry points (committed at `<repo>/scripts/`):**

| Script | Purpose |
|---|---|
| `scripts/kaggle-train` | Push the kernel, poll status, pull artifacts. The end-to-end retrain command. |
| `scripts/stage-kaggle-data` | One-time local stage of background corpora + features. Run before first kernel push. |
| `scripts/validate-wake-model.py` | Score a model against the validation set. Reports recall/precision per threshold. |

## Retraining workflow

```bash
# 1. (Optional, infrequent) refresh data:
uv run python training/wake-word/data-gen/elevenlabs-clones-batch.py
uv run python training/wake-word/data-gen/elevenlabs-neighbors-batch.py
# RIR capture is two-machine — see capture-rir-record.py docstring

# 2. (One-time per dataset bump) re-stage local data:
scripts/stage-kaggle-data
# Then `kaggle datasets version -p <stage-dir> -m "msg"` for each
# (mine, bg, features, validation) dataset that was modified.

# 3. Trigger a training run:
scripts/kaggle-train
# Wraps: kaggle kernels push → poll status every 20s → pull artifacts to
# var/wake-word/models/<datestamp>/. ~30-90 min on free GPU tier.

# 4. Validate the new model offline:
uv run python scripts/validate-wake-model.py \
    var/wake-word/models/<datestamp>/hey_claudia.onnx
# Compare recall/precision against var/wake-word/models/current/.

# 5. (Optional) live-test through the Jabra:
systemctl --user stop dirt-voice
uv run python training/wake-word/validation/live-test.py \
    var/wake-word/models/<datestamp>/hey_claudia.onnx
# (speak; Ctrl-C; restart service)

# 6. Deploy if validation looks good:
ln -sfn <datestamp>-<version> var/wake-word/models/current
systemctl --user restart dirt-voice
```

## Critical gotchas

- **`debug/hey_claudia.onnx` is gone.** All references should now point at `var/wake-word/models/current/hey_claudia.onnx` (symlink). If you find a `debug/` reference in newer code, it's a regression.
- **Don't commit anything under `var/`** — gitignored on purpose. WAVs, ONNX, NPYs, parquets, all stay local. The Kaggle datasets are the durable copy of training data.
- **TPU runtime has no internet** even with `enable_internet: true`. Use GPU. (Phone-verified accounts get internet on GPU.) See `kernel-metadata.json` — `enable_gpu: true, enable_tpu: false`.
- **`auto_train` in upstream openwakeword has a bug** (`self.best_val_fp` initialized to 1000 and never updated). Escalation always fires twice, doubling `max_negative_weight` regardless of the `target_fp_per_hour` config. Mitigations:
  - Set `FALSE_ACTIVATION_PENALTY` (max_negative_weight floor) low (≤500). Final value will be 4× that.
  - The proper fix is the soft-fork TODO at the bottom of `kaggle/train-hey-claudia.py` — write our own training loop that calls `openwakeword.model.Model.train_model()` directly with sane escalation logic + validation against `var/wake-word/validation/`. ~100 LOC, no openwakeword fork required.
- **`auto_train` ends with a broken ONNX→tflite step** (`from onnx_tf.backend import prepare`, `onnx_tf` not python-3.11+ compatible). The `.onnx` is saved before the broken step; the kernel's `train()` catches the failure if the `.onnx` exists, then `export()` does the conversion via `onnx2tf` cleanly.
- **`target_recall` and `target_accuracy` are dead config keys** in upstream `train.py` — never read. Don't waste time tuning them.

## Validation set

`var/wake-word/validation/{good,bad}/` is the canonical real-audio metric. The synthetic recall reported by openwakeword's auto_train (on Piper-generated test clips) was empirically *misleading* — v5 hit 38% synthetic recall but only 56% real-audio recall on this set. **Always validate against this set before deploying.**

When you grow the validation set: place real utterances in `good/`, hand-curated false-positives (typically pulled from `var/logs/wake_audio/` after listening) in `bad/`. Then bump the `dirt-wakeword-validation` Kaggle dataset (when it exists — currently planned, not yet uploaded) with `kaggle datasets version`.

## Where to look for context

- **What's currently deployed and why:** `wiki/decisions/2026-04-23-wake-word-v5-passive-harvest.md` (most current plan). v3 / v4 successors are linked from there.
- **The runtime side:** `apps/voice/src/dirt_voice/channels/voice.py` reads `WAKE_MODEL_PATH = var/wake-word/models/current/hey_claudia.onnx`. `wiki/hardware/voice-channel.md` is the production operating manual.
- **Wake-word concept primer:** `wiki/concepts/wake-word-detection.md`.
- **RIR-capture method:** `wiki/concepts/room-impulse-response.md`.
- **The "what's the model doing" diagnostic:** `validation/live-test.py` (interactive) + `scripts/validate-wake-model.py` (batch).
