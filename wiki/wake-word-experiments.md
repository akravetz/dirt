---
title: Wake-Word Experiment Log
type: log
created: 2026-04-25
updated: 2026-04-25
---

# Wake-Word Experiment Log

Append-only record of every "hey Claudia" wake-word model we train. New
entries go at the **end** (chronological top-to-bottom). Don't edit historical
entries — if a number was wrong, add a correction in the next entry rather
than mutating the past.

## Entry template

````markdown
## vN — YYYY-MM-DD

**Status:** trained | deployed | superseded
**Model artifact:** `var/wake-word/models/YYYY-MM-DD-vN/hey_claudia.onnx`
**Kernel commit:** `<git sha>`

### What changed
- Bullet list of differences vs the previous trained model — code, data, config.

### Why
- One paragraph of rationale; what failure mode are we trying to fix?

### Training data
- Positives: M synth clones × N dup, K real-mic × M dup, …
- Negatives: M synth neighbors × N dup, K real-mic × M dup, J harvested × M dup, …
- Backgrounds: AudioSet/FMA from `dirt-wakeword-bg`
- Feature corpus: ACAV100M 2000 h from `dirt-wakeword-features`

### Training config
- `max_negative_weight`: N
- `target_false_positives_per_hour`: N
- `steps`: N
- `target_recall`: N (note: dead key in upstream — ignored)
- Driver: upstream `auto_train` | soft-fork `_custom_train_model`
- Best-checkpoint selection: percentile-averaging | max-recall (FP/hr ≤ 2.0)

### Validation set
- `var/wake-word/validation/good/`: N positives
- `var/wake-word/validation/bad/`: N negatives
- (note: any changes vs the validation set used for the previous experiment)

### Results — `scripts/validate-wake-model.py` sweep

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | … | … | … | …/N |
| 0.40 | … | … | … | …/N |
| 0.50 | … | … | … | …/N |
| 0.60 | … | … | … | …/N |

**Best operating point:** threshold X — recall Y%, precision Z%, F1 W

### Notes
- Anything else worth recording: failure modes observed, follow-ups, in-the-wild
  observations after deployment, etc.

---
````

## Maintenance protocol

After every new model is trained:

1. Append a new entry to the bottom of this file. Don't touch existing entries.
2. Run `uv run python scripts/validate-wake-model.py <new-model.onnx>` and a
   threshold sweep; copy the metrics into the table.
3. If you deploy the new model: change the previous entry's `**Status:**` to
   `superseded` (one-word edit, fine to do).
4. Update `var/wake-word/models/current` symlink to the deployed version.
5. The kernel's `validate_against_real_set()` produces a similar report at
   `/kaggle/working/validation-report.txt` — use it as a starting point.

The validation set itself can grow over time. When you change it, document the
delta in the *next* model's entry's "Validation set" section. Don't retroactively
re-run old models against new validation sets unless you mark the new numbers
clearly as a back-fill.

## Entries

### v1 — 2026-04-15

**Status:** superseded
**Model artifact:** `var/wake-word/models/2026-04-15-v1/hey_claudia.onnx`

Pre-experiment-log baseline. Piper-only synthetic positives, no ElevenLabs voice
clone, no captured RIRs. ~40–70 % recall depending on distance per
[`wiki/decisions/2026-04-16-wake-word-training-strategy.md`](decisions/2026-04-16-wake-word-training-strategy.md).
Kept for reference; no validation-set sweep available.

### v2 — 2026-04-16

**Status:** superseded
**Model artifact:** `var/wake-word/models/2026-04-16-v2/hey_claudia.onnx`

Pre-experiment-log baseline. Conservative training (~70 % recall claimed at
the time). Same Colab pipeline as v1 with a tweaked config; specifics not
documented. Kept for reference.

### v3 — 2026-04-16

**Status:** deployed (currently `var/wake-word/models/current` symlink)
**Model artifact:** `var/wake-word/models/2026-04-16-v3/hey_claudia.onnx`

The model that's been running in production since mid-April. Trained in
Colab on the upstream `automatic_model_training_simple.ipynb` notebook with
ElevenLabs voice clones for positives + the 9 captured RIRs.

#### What changed (vs v2)
- Switched positives from Piper-only to ElevenLabs voice clones (2000 samples,
  one cloned voice — operator's).
- Added 9 captured Room Impulse Responses for augmentation.
- Dropped `max_negative_weight` from 1500 → 500 to claw back recall.

#### Why
- v1/v2 had unacceptable recall at far-field positions. The clone+RIR mix was
  meant to tighten the positive distribution to deployment acoustics.

#### Reported in-the-wild metrics (Colab synthetic test, no validation set yet):
- 89 % recall at threshold 0.5
- Score peaks 0.95–0.99 on close-mic clean hits
- Validation FP/hour: 6.6 (high; "trade-off for recall")

#### Results — back-filled sweep on `var/wake-word/validation/` (28 good / 76 bad, 2026-04-25)
| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 50.0 % | 25.0 % | 0.333 | 52/76 |
| 0.40 | 42.9 % | 22.2 % | 0.293 | 42/76 |
| 0.50 | 42.9 % | 24.0 % | 0.308 | 38/76 |
| 0.60 | 42.9 % | 26.1 % | 0.324 | 34/76 |

The 9-positive validation subset earlier showed 78 % recall — but the
subset wasn't representative. On the full 28-positive set (which includes
real-mic samples from positions/voices v3 was never trained on), recall
floors out at 43 %. **v3 is meaningfully worse than the 89 % claim.**

#### Failure mode
- High FP rate on real ambient room audio. The bad/ class came largely from
  v3's own in-the-wild firings during meetings/TV — proof that v3 mistook
  meeting acoustics for the wake word at threshold 0.5–0.6. Decision pages:
  [v4 plan](decisions/2026-04-18-wake-word-v4-plan.md),
  [v5 plan](decisions/2026-04-23-wake-word-v5-passive-harvest.md).

### v5 — 2026-04-25

**Status:** trained, validated (not deployed)
**Model artifact:** `var/wake-word/models/2026-04-25-v5/hey_claudia.onnx`
**Kernel commit:** `5b18586`

#### What changed (vs v3)
- Migrated training from Colab to **Kaggle Script Kernels on GPU** for
  reproducibility. See `training/wake-word/kaggle/`.
- Reinstated synthetic phonetic-neighbor negatives via ElevenLabs (440 WAVs
  across 9 phrases) — file at `training/wake-word/data-gen/elevenlabs-neighbors-batch.py`.
  Later trimmed to 360 WAVs / 7 phrases (dropped `okay claudia`, `play claudia`
  on operator decision).
- Added `prepare_seed_clips()` step that copies user-provided WAVs into
  openwakeword's `positive_train/` and `negative_train/` *before* `--generate_clips`,
  with `synth_clone_*` / `synth_neighbor_*` / `harvested_*` filename prefixes
  for downstream subset selection.
- `CLONE_DUPLICATION = 5` (heavy upweighting of the cloned voice — operator
  doesn't deploy for other voices).
- Kept upstream `auto_train` pipeline.

#### Why
- v3's precision was destroying meetings; needed phonetic-neighbor coverage.

#### Training config
- `max_negative_weight`: 500 (auto_train escalated to 2000 across 3 sequences)
- `target_false_positives_per_hour`: 10 (no effect — best_val_fp bug)
- `steps`: 20 000 (sequence 1) + 2 × 2000 (sequences 2 + 3)
- Driver: upstream `auto_train`

#### Validation set
- Original 9 / 58 set (pre-real-mic capture)

#### Reported during training
- Final synthetic test recall: 38 %, accuracy 69 %, FP/hr 0.088

#### Results — sweep on `var/wake-word/validation/` (28 good / 76 bad, 2026-04-25 expanded)
| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 46.4 % | 86.7 % | 0.605 | 2/76 |
| 0.40 | 42.9 % | 85.7 % | 0.571 | 2/76 |
| 0.50 | 35.7 % | 90.9 % | 0.513 | 1/76 |
| 0.60 | 28.6 % | 100 %  | 0.444 | 0/76 |

**Best operating point on this validation set: threshold 0.40 — recall 43 %,
precision 86 %, F1 0.57, 2 FPs.** Strictly Pareto-better than v3 at every
useful threshold (v3 has 2× the FP rate at the same recall).

#### Notes
- First Kaggle run; ~5 distinct kernel failures during pipeline bring-up.
  Issues catalogued in [`wiki/decisions/2026-04-23-wake-word-v5-passive-harvest.md`](decisions/2026-04-23-wake-word-v5-passive-harvest.md).
- Real-audio recall ≈ synthetic recall × 1.5 in this run (38 % synthetic →
  56 % real on the 9-positive subset; 36 % real on the expanded 28-positive
  set). Synthetic recall reported by openwakeword's training loop is
  *misleading* — always re-validate on the real-audio set.
- Identified upstream bugs: `auto_train`'s `best_val_fp = 1000` initialized
  and never updated → escalation always fires twice → max_negative_weight
  ends up 4× configured. Also `convert_onnx_to_tflite` broken on python 3.11+.
  Both motivate the v6 soft-fork.

### v6 — 2026-04-25

**Status:** in flight at time of writing (Kaggle kernel `b8gscd5ng` running)
**Model artifact:** `var/wake-word/models/2026-04-25-v6/hey_claudia.onnx` (when pulled)
**Kernel commit:** `5b18586`

#### What changed (vs v5)
- **Soft-forked the training driver.** Replaced upstream's `auto_train`
  (broken — see v5 notes) with a custom training loop in
  `_custom_train_model()` that calls `openwakeword.openwakeword.Model.train_model()`
  directly. Single training pass, no escalation, no checkpoint averaging.
  Best checkpoint chosen by max `val_recall` subject to `val_fp/hr ≤ 2.0`.
- Skipped upstream's broken ONNX→tflite step (`from onnx_tf.backend import prepare`).
  Our `export()` does the conversion via `onnx2tf` cleanly.
- Added a 4th Kaggle dataset `dirt-wakeword-validation` (mounts at
  `/kaggle/input/dirt-wakeword-validation/{good,bad}/`).
- Added `validate_against_real_set()` step at the end of the kernel — runs
  the trained ONNX over the real-audio validation set and writes
  `/kaggle/working/validation-report.txt`. *This is the canonical metric* —
  synthetic Piper-test recall has been empirically misleading.

#### Why
- v5's recall ceiling (~43 %) traced to upstream's auto-escalation bug
  starving the model on positive signal. Even in the best case auto_train
  was choosing a precision-collapsed checkpoint. Soft-fork lets us see
  the model train_model() *actually* produces with sane settings.

#### Training data
- Same as v5 (the kernel was pushed before the real-mic capture session).
  Positives: 2000 ElevenLabs clones × 5 dup. Negatives: 360 ElevenLabs
  neighbors × 1, 0 harvested.
- *Important caveat:* this run is a **soft-fork-on-old-data** baseline.
  v7 will add real-mic samples + duplication retuning.

#### Training config
- `max_negative_weight`: 500 (no escalation)
- `target_false_positives_per_hour`: 10 (still set, now actually unused)
- `steps`: 20 000 (single pass)
- Driver: soft-fork `_custom_train_model`
- Best-checkpoint: max `val_recall` with `val_fp/hr ≤ 2.0` filter

#### Validation set
- `var/wake-word/validation/good/`: 9 positives (pre-real-mic — kernel mounted v1 of the dataset)
- `var/wake-word/validation/bad/`: 58 negatives

#### Results
*Pending.* Will be appended once the kernel finishes and we re-validate
locally against the *current* validation set (28/76, post-real-mic).

### v7 — planned

**Status:** planned, kernel staged
**Kernel commit:** *pending push after v6 finishes*

#### What changed (vs v6)
- **Real-mic data.** Both training and validation Kaggle datasets bumped to
  include the 2026-04-25 real-mic capture batches:
  - `dirt-wakeword-mine` v4 → 2018 voice clones (was 2000), 378 neighbors (was 360).
  - `dirt-wakeword-validation` v2 → 28 good (was 9), 76 bad (was 58).
- **New duplication factors** to weight gold-standard real-mic samples up:
  - `CLONE_DUPLICATION`: 5 → **1** (rebalance — synthetic clones already dominate).
  - `REALMIC_POSITIVE_DUPLICATION` = **10** (new) — pushes 18 real-mic positives to ~8 % of training pool.
  - `REALMIC_NEGATIVE_DUPLICATION` = **10** (new) — same for negatives.
- `prepare_seed_clips()` updated to detect `realmic-pos_*.wav` /
  `realmic-neg_*.wav` filename prefixes and apply the new dup factors.

#### Why
- v6 (in flight) is the soft-fork-only baseline. v7 adds the real-mic
  data we just collected — expected to lift recall on the expanded
  validation set, where v3 and v5 both floor at ~43 %.

#### Training config
- All other knobs same as v6 (steps 20 000, max_neg_weight 500, soft-fork driver).

#### Validation set
- `var/wake-word/validation/good/`: 28 positives (3.1× v6's set; includes 19 real-mic)
- `var/wake-word/validation/bad/`: 76 negatives (1.3× v6's set; includes 18 real-mic)

#### Results
*Pending.* Run after v6 finishes; bump both Kaggle datasets first.
