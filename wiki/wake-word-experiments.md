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

**Status:** superseded (deployed 2026-04-16 → 2026-04-27; replaced by v16)
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
  reproducibility. See `apps/wake-word/kaggle/`.
- Reinstated synthetic phonetic-neighbor negatives via ElevenLabs (440 WAVs
  across 9 phrases) — file at `apps/wake-word/data-gen/elevenlabs-neighbors-batch.py`.
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

### v8 — planned

**Status:** planned, kernel staged
**Kernel commit:** *pending push after v7 finishes*

Architectural upgrade based on a two-agent review (training architecture +
data augmentation). Three changes from v7, ranked by expected impact:

#### What changed (vs v7)

1. **Pick best checkpoint by real-audio F1, not synthetic `val_recall`.** Each
   saved checkpoint is exported to a temp ONNX, scored against the
   hand-labeled `var/wake-word/validation/{good,bad}/` set, and the one with
   highest F1 at threshold 0.5 wins. Synthetic Piper-test recall has been
   empirically misleading (v5: 38 % synthetic → 36 % real on the expanded
   set). Adds ~2 min of post-training overhead on CPU. Implementation:
   `_select_best_by_real_f1()` in the kernel.
2. **Per-subset augmentation.** Replaces upstream's `--augment_clips`
   shell-out with `_augment_and_compute_features()`, which splits clips by
   filename prefix: `realmic_*` and `harvested_*` clips get `RIR=0.0` +
   `AddBackgroundNoise=0.5` (their RIR is already baked in from real-room
   recording — convolving with another RIR is an unphysical 2-room cascade);
   synthetic clips keep the upstream defaults (`RIR=0.5`, `AddBackgroundNoise=0.75`).
   Promotes the option-2 TODO that's been sitting in the kernel since v5.
3. **Batch composition rebalance.** `batch_n_per_class` from upstream's
   `1024 ACAV / 50 adversarial / 50 positive` → `512 ACAV / 50 adversarial /
   200 positive`. Smaller batch (1124 → 762) but 4× the per-batch positive
   gradient slots. With real-mic at ~8 % of the duplicated positive pool,
   each batch now sees ~16 real-mic positives in expectation (was ~4) —
   directly targets the real-mic recall floor we've been chasing.

#### Why

Both reviewing agents independently flagged synthetic-vs-real metric drift
as the dominant unhandled failure mode. The training agent estimated +5–10 pp
F1 from real-audio checkpoint selection alone — essentially "the right
checkpoint was already in `oww.best_models`, we were picking the wrong one."

The augmentation agent flagged the double-RIR problem as a real (not in-the-
noise) bias: real-mic clips in v7 are convolved with a random in-room RIR on
top of their already-baked-in deployment RIR.

The training agent flagged that 50 positive batch slots × 8 % real-mic
fraction = 4 real-mic positives per batch, which is gradient-starved given
those are the ones we're trying to teach the model on.

Three independent fixes, each cheap to apply, expected to compound.

#### What we explicitly skipped

- **SpecAugment** (suggested by augmentation agent). Wrong abstraction
  level — openwakeword's training inputs are 96-dim *embedding* vectors
  (16-frame stacks), not raw mel-spectrograms. Masking learned embedding
  dimensions doesn't have the natural frequency-band semantics SpecAugment
  exploits. The training agent independently rejected this for the same
  reason. Could revisit at the raw-mel stage, but that requires a deeper
  pipeline fork.
- **AdamW + grad-clip + cosine LR + EMA weights** (training agent R2/R3/R5).
  Bundled together and deferred to v9 — they all require inline-forking
  upstream's `Model.train_model()` inner loop (~80 LOC of surgical edits
  with overlap risk). Promoting after v8 produces a baseline.
- **Background corpus expansion** (TV/dialog/HVAC) and **augmentation_rounds = 3**
  and **mixup**. All deferred to v10 (data-side bundle, separate from
  training-architecture changes for clean attribution).

#### Training config

- `max_negative_weight`: 500 (unchanged)
- `target_false_positives_per_hour`: 10 (unchanged; still unused)
- `batch_n_per_class`: **512 / 50 / 200** (was 1024 / 50 / 50)
- `steps`: 20 000 (unchanged)
- Driver: soft-fork `_custom_train_model` + new `_augment_and_compute_features`
- Best-checkpoint: real-audio **F1 at threshold 0.5** against `validation/`,
  tiebreak by recall, then by latest training step

#### Validation set
- Same as v7 (28 good / 76 bad — `dirt-wakeword-validation` v2)

#### Results
*Pending.* Push after v7 lands; expected v8 lift over v7: +5–15 pp F1 net.

### v9 — 2026-04-25 (failed in 4 min)

**Status:** failed at install — `ModuleNotFoundError: No module named 'openwakeword'`
**Kernel commit:** `a811829`
**Wall time:** ~4 minutes (crashed before training started)

#### What changed (vs v8 plan)
- Same training architecture as v8 (per-subset aug, real-audio F1 selection,
  512/50/200 batch composition).
- Pipeline restructured: kernel is now a thin shim that installs deps + clones
  repo at a pinned SHA + hands off to the `dirt_wake_word.main` library.
- SHA-injection in `scripts/kaggle-train` so each push pins to
  `git rev-parse HEAD`. Kernel was reproducibly tied to commit `a811829`.

#### Why it failed
After the library extract (commit `5a8f23b`) imports moved to
top-of-file in `dirt_wake_word/train.py`:

```python
from openwakeword.data import mmap_batch_generator   # line 22
```

A previous commit (`20f88eb`) had dropped `pip install -e ./openwakeword
--no-deps` from the shim, on the wrong assumption that Kaggle's base
image ships openwakeword 0.6.0. **It does not.** The module is niche
enough that it's not in the GPU base image. The eager top-level import
crashed at module load:

```
File "/kaggle/working/dirt/apps/wake-word/src/dirt_wake_word/train.py", line 22
    from openwakeword.data import mmap_batch_generator
ModuleNotFoundError: No module named 'openwakeword'
```

#### Fix
Add `openwakeword==0.6.0` to the existing pip install batch in the shim's
`install_dependencies()`. PyPI install (not editable) — the cloned
openwakeword source is still needed for two specific files (the
train.py CLI shell-out for `--generate_clips` and the
`examples/custom_model.yml` baseline) but the package itself comes from
PyPI. Commit: `d7a9704`.

#### Lesson
The lesson the local pre-flight import check now codifies: assumptions
about base-image contents are unreliable across image refreshes.
Pre-flight catches this class only if the [wake-word] extras are
installed locally — when they aren't, the check explicitly returns
"deps not installed locally — skipping deeper check" and we lose the
guarantee. Either install the [wake-word] extras locally, or accept
that this exact bug class will surface on Kaggle. v9 was the bill for
that trade-off.

### v10 — 2026-04-25 (failed in 4 min)

**Status:** failed at install — `pip install openwakeword==0.6.0` had no eligible release for python 3.12
**Kernel commit:** `d7a9704`
**Wall time:** ~3.5 min

#### What changed (vs v9)
- Added `openwakeword==0.6.0` to the shim's pip install batch (the v9 fix).

#### Why it failed
Two stacked PyPI compatibility issues against Kaggle's python 3.12:

```
ERROR: Ignored the following versions that require a different python version:
  0.5.0/0.5.1/0.6.0 Requires-Python >=3.6,<3.9
ERROR: Could not find a version that satisfies the requirement
  tflite-runtime<3,>=2.8.0; platform_system == "Linux" (from openwakeword)
```

1. openwakeword 0.6.0 — the last PyPI release with the auto_train shape
   our soft-fork builds on — declares `Requires-Python <3.9`. Kaggle is
   3.12, so pip silently skips it.
2. Newer GitHub-only versions DO support 3.12 but transitively pull
   `tflite-runtime`, which is not published for cp312 + Linux on PyPI.

So no version constraint works against PyPI on Kaggle's runtime.

#### Fix (v11)
Install openwakeword from the cloned GitHub source with `--no-deps`.
Same approach v6 quietly used. The `--no-deps` flag dodges the
tflite-runtime resolver failure entirely; the explicit dep list in the
next pip call covers everything that's actually needed at runtime.
Commit: `a11882f`.

### v11 — 2026-04-25 (failed in 5 min)

**Status:** failed at `git checkout` — kernel SHA was unpushed to origin
**Kernel commit:** `a11882f`
**Wall time:** ~5.5 min

#### What changed (vs v10)
- `pip install --quiet --no-deps ./openwakeword` (cloned source) — dodges
  both PyPI incompatibilities documented in v10.
- Otherwise identical to v9 / v10 / v8 staged: per-subset aug, real-audio
  F1 checkpoint selection, 512/50/200 batch composition.

#### Why
First actual run of the v8 architectural design. v9 + v10 were both
pure-infrastructure failures; v11 should produce a real model unless
something else fails downstream of `install_dependencies`.

#### Training config
Identical to v8:
- `max_negative_weight`: 500
- `batch_n_per_class`: 512 / 50 / 200
- `steps`: 20 000
- Per-subset augmentation (realmic_*/harvested_* skip RIR)
- Best-checkpoint: real-audio F1 against `validation/` (28 good / 76 bad)

#### Validation set
- Same as v8 (28 good / 76 bad — `dirt-wakeword-validation` v2)

#### Results
Install phase succeeded. Training never started — the shim's
`git checkout $DIRT_REPO_SHA` exited 128 because `a11882f` had been
committed locally but never pushed to origin/main. The kernel clones
the public `https://github.com/akravetz/dirt`; only commits already
on origin are reachable.

```
subprocess.CalledProcessError: Command 'git checkout a11882f...'
returned non-zero exit status 128.
```

#### Fix (v12)
Add a pre-push guard to `scripts/kaggle-train`:
`git fetch origin main && git merge-base --is-ancestor HEAD origin/main`.
Aborts with a clear "push first" message when HEAD isn't on origin/main,
saving the 5-min Kaggle no-op. Commit: `e83c5f1`.

### v12 — 2026-04-25 (failed at 22 min in train phase)

**Status:** install + generate_clips OK; crashed in `augment_and_compute_features`
**Kernel commit:** `e83c5f1`
**Wall time:** ~47 min (install 4 min, generate_clips 22 min, then bug)

#### What changed (vs v11)
- Pre-push verification of HEAD on origin/main (the v11 fix above).
- All commits actually pushed before kernel push.
- Otherwise identical to v11 (which was identical to v10/v9/v8 staged):
  per-subset aug + real-audio F1 selection + 512/50/200 batch composition.

#### Why
Fourth attempt at the v8 architectural baseline. v9–v11 were all
infrastructure failures (each fixed a different stacked bug):
1. v9 (a811829): no openwakeword install → ModuleNotFoundError.
2. v10 (d7a9704): pip install openwakeword==0.6.0 → no PyPI wheel for py3.12.
3. v11 (a11882f): pip install --no-deps from source → SHA not on origin.
v12 should be the first attempt that actually reaches the train phase.

#### Training config
Identical to v8 staged.

#### Validation set
- Same as v8 (28 good / 76 bad — `dirt-wakeword-validation` v2)

#### Results
First run that actually entered the train phase. `--generate_clips`
completed all 428 batches (~22 min wall, the dominant phase). Then
crashed in our soft-fork augmentation step:

```
File ".../dirt_wake_word/augment.py", line 92,
    in augment_and_compute_features
    total_length=config["total_length"],
KeyError: 'total_length'
```

Real code bug. `total_length` is the per-clip sample count for
augment_clips; upstream's `train.py` *computes* it post-generate_clips
from the median positive_test clip duration:

```python
config["total_length"] = int(round(np.median(durations)/1000)*1000) + 12000
if config["total_length"] < 32000: config["total_length"] = 32000  # 2s floor
```

It's not a YAML key. The soft-fork in `train.py` bypassed `--train_model`
entirely, taking the total_length-injection step with it.

#### Fix (v13)
Port the same calculation into a new `_compute_total_length()` helper
called at the top of `augment_and_compute_features()`, and persist the
value back into `my_model.yaml` so `_custom_train_model`'s later
`yaml.safe_load(...)` sees the same int. Commit: `51abdd8`.

### v13 — 2026-04-25 (failed at augment.py)

**Status:** install + generate_clips (cached) + total_length-calc OK; crashed on resource lookup in `compute_features_from_generator`
**Kernel commit:** `51abdd8`
**Wall time:** ~22 min (TTS regenerated since cache key changed; new bug surfaced just after v12's bug)

#### What changed (vs v12)
- `_compute_total_length()` added in augment.py (the v12 fix above).
- Otherwise identical to v12 / v11 / v10 / v9 / v8 staged.

#### Why
Fifth attempt at the v8 architectural baseline. v9–v12 each unblocked
a different failure stage:

| ver | wall  | failed at                            |
|-----|-------|--------------------------------------|
| v9  |  4 m  | top-level openwakeword import        |
| v10 |  4 m  | pip install openwakeword (no py3.12) |
| v11 |  6 m  | git checkout SHA (unpushed)          |
| v12 | 47 m  | augment.py KeyError: 'total_length'  |

v13 should be the first run to actually train.

#### Training config
Identical to v8 staged.

#### Validation set
- Same as v8 (28 good / 76 bad).

#### Results
total_length fix worked. generate_clips ran again (cache invalidated)
and `_compute_total_length()` produced the right value. Then crashed
one frame later in compute_features_from_generator → AudioFeatures():

```
onnxruntime.capi.onnxruntime_pybind11_state.NoSuchFile:
  Load model from
  /usr/local/lib/python3.12/dist-packages/openwakeword/resources/models/
  melspectrogram.onnx failed. File doesn't exist
```

`AudioFeatures()` resolves the bundled mel/embedding ONNX paths via
`__file__` of the *installed* openwakeword package. Our shim:
1. `pip install --no-deps ./openwakeword` — pip *copies* the source
   into `/usr/local/lib/python3.12/dist-packages/openwakeword/`.
2. `wget melspectrogram.onnx → /kaggle/working/openwakeword/openwakeword/resources/models/`

Step 2 lands in the *cloned* path, not the installed path. The runtime
looks at the installed path → file not found.

#### Fix (v14)
Switch to editable install: `pip install --no-deps -e ./openwakeword`.
With `-e`, the runtime `__file__` points back at /kaggle/working/openwakeword/,
which is exactly where our wget lands the resource files. Commit: `adadf02`.

### v14 — 2026-04-25 (failed at 4 min on import)

**Status:** editable install completed but `import openwakeword` failed
**Kernel commit:** `adadf02`
**Wall time:** ~4 min

#### What changed (vs v13)
- Editable openwakeword install (the v13 fix above).
- Otherwise identical to v13 / v12 / v11 / v10 / v9 / v8 staged.

#### Why
Sixth attempt at the v8 architectural baseline. The bug-tour table:

| ver | wall  | failed at                                    |
|-----|-------|----------------------------------------------|
| v9  |  4 m  | top-level openwakeword import                |
| v10 |  4 m  | pip install openwakeword (no py3.12)         |
| v11 |  6 m  | git checkout SHA (unpushed)                  |
| v12 | 47 m  | augment.py KeyError: 'total_length'          |
| v13 | 22 m  | AudioFeatures resource path (non-editable install) |

v14 should reach training proper.

#### Training config
Identical to v8 staged.

#### Validation set
- Same as v8 (28 good / 76 bad).

#### Results
The editable install ran (51 s wall, pip recognized openwakeword 0.6.0
during a later install's resolver pass) but at runtime:

```
File ".../dirt_wake_word/train.py", line 22, in <module>
    from openwakeword.data import mmap_batch_generator
ModuleNotFoundError: No module named 'openwakeword'
```

`pip install -e` evidently lands a `.pth` somewhere the runtime python
doesn't pick up on Kaggle's locked-down env (likely a user-local
site-packages dir). Verified by the v13 history: same shim minus `-e`
worked end-to-end through 22 minutes of generate_clips.

#### Fix (v15)
Revert to non-editable install (`pip install --no-deps ./openwakeword`)
and instead address the *resource path* problem from a different angle:

1. After install, discover the installed location via subprocess:
   `python -c "import openwakeword; print(Path(openwakeword.__file__).parent)"`
2. wget bundled resources into the cloned location (existing behavior).
3. cp them into the installed location too.

So both paths have the resources — robust to whichever side
`AudioFeatures()` resolves from. Commit: `15a7dfc`.

### v15 — 2026-04-25 (failed at 1h51m, deepest run yet)

**Status:** ERROR after 1 h 51 m wall time — past install, generate_clips,
augment+features. Failed somewhere inside `_custom_train_model` or
post-train selection/export.
**Kernel commit:** `15a7dfc`

#### What changed (vs v14)
- Reverted to non-editable openwakeword install.
- Added resource-path discovery + dual-write (cloned + installed).
- Otherwise identical to v14 / v13 / … / v8 staged.

#### Why
Seventh attempt at the v8 architectural baseline:

| ver | wall  | failed at                                                  |
|-----|-------|------------------------------------------------------------|
| v9  |  4 m  | top-level openwakeword import                              |
| v10 |  4 m  | pip install openwakeword (no py3.12 wheel)                 |
| v11 |  6 m  | git checkout SHA (unpushed)                                |
| v12 | 47 m  | augment.py KeyError: 'total_length'                        |
| v13 | 22 m  | AudioFeatures resource path (non-editable, but no cp step) |
| v14 |  4 m  | editable install — `import openwakeword` failed at runtime |

If v15 doesn't reach training, this is becoming a tour rather than a
fix sequence — at that point we should consider running upstream's
unmodified Colab notebook on Kaggle to establish a baseline before
soft-forking again.

#### Training config
Identical to v8 staged.

#### Validation set
- Same as v8 (28 good / 76 bad).

#### Results
v15 reached training proper — install ✓, generate_clips ✓, augment+features ✓
(the v13 resource-path fix held). Then ERROR at 1 h 51 m wall, deep
inside `_custom_train_model`, post-train selection, or export. Detailed
log was not pulled — the strategic decision to migrate off Kaggle made
debugging the dead Kaggle path low value.

| ver | wall    | failed at                                                  |
|-----|---------|------------------------------------------------------------|
| v9  |  4 m    | top-level openwakeword import                              |
| v10 |  4 m    | pip install openwakeword (no py3.12 wheel)                 |
| v11 |  6 m    | git checkout SHA (unpushed)                                |
| v12 | 47 m    | augment.py KeyError: 'total_length'                        |
| v13 | 22 m    | AudioFeatures resource path (non-editable, but no cp step) |
| v14 |  4 m    | editable install — `import openwakeword` failed at runtime |
| v15 | **1h51m** | deep in train phase — root cause not investigated          |

Each iteration cleared the previous failure mode and surfaced a new one.
The cumulative pattern — every fix was a Kaggle-environment quirk
(base-image contents, py3.12 PyPI wheels, editable-install path
quirks, locked-down package layout) — is what triggered the platform
migration. See **`wiki/decisions/2026-04-25-runpod-migration.md`**.

### Migration: Kaggle → RunPod (2026-04-25)

After v15, abandoned Kaggle Notebooks in favor of a self-controlled
Docker image on RunPod. Rationale + setup details in
[`wiki/decisions/2026-04-25-runpod-migration.md`](decisions/2026-04-25-runpod-migration.md).

The v8 architectural design (per-subset aug, real-audio F1 selection,
512/50/200 batch composition) is unchanged — what changed is the
runtime environment. v16+ entries below correspond to RunPod runs.

### v16 — 2026-04-27

**Status:** **deployed** (currently `var/wake-word/models/current` symlink, deployed 2026-04-27)
**Model artifact:** `var/wake-word/models/2026-04-27-v16/hey_claudia.onnx` (renamed from `2026-04-26-225546-95hpev0e07b2ea` for convention)
**Trainer commit:** `1d10a93` (TTS-cache reciprocal-bug fix landed mid-run; pod ran on the prior image's code)
**Image digest:** `sha256:f552c860573e2a6a2ed63e3ef46ad55af45c8d377102275e1c77ff52e69c7763`
**W&B run:** [`bwwafjyq`](https://wandb.ai/adkravetz/dirt-wake-word/runs/bwwafjyq) (group `exp1-realmic-20260426-225544`)
**Pod:** `95hpev0e07b2ea`, RTX 4090 / 64 vCPU / 270 GB RAM
**Wall:** ~47 min total (per-phase below)

#### What changed (vs v6/m1f811ys)
- **Real-mic training data**, finally landed. 18 `realmic-pos_*.wav` (×10 dup = 180) + 18 `realmic-neg_*.wav` (×10 dup = 180) included in the seed pool. v8's plan, finally executed end-to-end. (Prior runs reverted to synthetic-only because the data hadn't survived the Kaggle→RunPod migration.)
- **WORKING dir per-run-isolated** for real (Dockerfile previously baked `DIRT_WAKEWORD_WORKING=/workspace/working` at the bare path, beating the entrypoint's per-run `setdefault` — every run inherited the prior run's Piper output. Fix: drop the bake. `259fff7`).
- **TTS cache reciprocal-bug fix landed but did not affect this run** — the cache-key.json was deleted from the volume just before the run, so this run did Piper from scratch (~19 min). Persist will populate the cache cleanly for future runs (`1d10a93`).
- All four datasets now in `/workspace/input/MANIFEST.json` with content_hashes; trainer reads and stamps in `run-manifest.json`.

#### Why
v3 (deployed) and v5 both flooored at 35-43 % recall on the canonical 28/76 set; m1f811ys regressed to 21 % recall on the same set. The pattern: synthetic-only training doesn't generalize to real-mic positives. Real-mic-in-training was the explicit hypothesis.

#### Training data
- **Positives:** 2 000 ElevenLabs voice clones (×1) + 18 real-mic positives (×10) = 2 180 seeds → 30 000 augmented features
- **Negatives:** 360 ElevenLabs phonetic neighbors (×1) + 18 real-mic negatives (×10) + 0 harvested = 540 seeds → 30 000 augmented features
- **RIRs:** 9 captured room impulse responses
- **Background:** AudioSet_16k (1 000 clips) + FMA (~120 clips) from `dirt-wakeword-bg`
- **Feature corpus:** ACAV100M 2 000 h from `dirt-wakeword-features`
- Volume MANIFEST hashes:
  - `dirt-wakeword-mine`: sha256:6ee63220876e8296189aee2d211f01d8954d59cfb257cc8c749598df2c30fdae
  - `dirt-wakeword-bg`: sha256:05bf46e62edd60fa2…
  - `dirt-wakeword-validation`: sha256:93b03266683cb5b2b71ec25057883a475ff2c24a17e2e3e7891d503e1e623767
  - `dirt-wakeword-features`: sha256:0ee81d9a761139a6c033ac7014e01f30c45e1547767fa644c583d3e69132b836

#### Training config
- `max_negative_weight`: 500
- `batch_n_per_class`: 512 / 50 / 200 (ACAV / adversarial / positive — v8 rebalance)
- `steps`: 20 000
- `target_false_positives_per_hour`: 10 (unused — soft-fork)
- Per-subset augmentation: `realmic_*` clips skip RIR (already room-baked)
- Driver: soft-fork `_custom_train_model`
- DataLoader sharing strategy: `file_system` (workaround for Linux fd-exhaustion on RunPod hosts; see v9-v15 history)
- Best-checkpoint: real-audio F1 against `validation/`

#### Validation set
- `var/wake-word/validation/good/`: 28 positives (canonical 28/76 set, `dirt-wakeword-validation` content_hash sha256:93b03266…)
- `var/wake-word/validation/bad/`: 76 in-the-wild negatives

#### Results — sweep on the canonical 28/76 set

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 57.1 % | 59.3 % | **0.582** | 11/76 |
| 0.40 | 50.0 % | 66.7 % | 0.571 | 7/76 |
| 0.50 | 46.4 % | 72.2 % | 0.565 | 5/76 |
| 0.60 | 46.4 % | 76.5 % | 0.578 | 4/76 |
| 0.70 | 39.3 % | 84.6 % | 0.537 | 2/76 |

**Best F1 0.582 at threshold 0.30**; same recall as v3 (43 %) at threshold 0.50 with **3× the precision** (72 % vs 24 %).

Comparison vs prior:
| Model | recall@0.5 | F1@0.5 |
|---|---:|---:|
| v3 (deployed) | 42.9 % | 0.308 |
| v5 | 35.7 % | 0.513 |
| m1f811ys | 21.4 % | 0.324 |
| **v16** | **46.4 %** | **0.565** |

#### Per-phase wall time
| Phase | Wall |
|---:|---:|
| verify_inputs / imports / build_config / prepare_seed_clips | ~3 s |
| restore_tts_cache (MISS — cache-key deleted to force rebuild) | 0 s |
| generate_clips (Piper TTS — full from-scratch) | **18m57s** |
| augment+features | ~22 min |
| train_loop (20 000 steps) | ~5 min |
| validate_against_real_set | <1 s |
| **TOTAL** | **~47 min** |

#### Operational notes
- The orchestrator (`scripts/runpod-train`) died at ~14 min (root cause not yet identified — possible KeyboardInterrupt from a sibling process). Pod kept running; training succeeded; SUCCESS sentinel written. RunPod's container auto-restart then triggered a second container that FATAL'd on the partial-cache state and wrote FAILURE 34 s later. Pod was eventually reaped by RunPod's account spend cap.
- Artifacts recovered post-hoc via the new `scripts/wakeword-pull-pod-out 95hpev0e07b2ea` helper (direct boto3 head_object / download_file by known filename — no list_objects, immune to RunPod's paginator bug).
- Net result: training success, ~$0.10 of wasted GPU on the auto-restart loop, but artifacts intact on the volume.
- Open follow-up: orchestrator watchdog / quick-exit-on-existing-sentinel + container-side self-DELETE — see chat history for design.
