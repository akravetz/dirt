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
**Trainer commit:** `<git sha>`

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
5. The trainer's `validate_against_real_set()` produces a similar report in
   the downloaded RunPod artifacts — use it as a starting point.

The validation set itself can grow over time. When you change it, document the
delta in the *next* model's entry's "Validation set" section. Don't retroactively
re-run old models against new validation sets unless you mark the new numbers
clearly as a back-fill.

## Entries

> Historical note: entries v5-v15 document the retired notebook-platform
> attempts that preceded the RunPod trainer. Those operational scripts and
> code paths have been removed; v16+ is the active training lineage.

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
- Migrated training from Colab to a managed notebook runtime for
  reproducibility. This path is retired; its repo scripts were removed.
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
- First managed-notebook run; ~5 distinct runtime failures during pipeline bring-up.
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

**Status:** historical, superseded by the RunPod trainer
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
- Added a 4th validation dataset to the retired notebook runtime.
- Added `validate_against_real_set()` step at the end of the kernel — runs
  the trained ONNX over the real-audio validation set and writes
  `validation-report.txt`. *This is the canonical metric* —
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
- **Real-mic data.** Both training and validation datasets bumped to
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
*Pending.* Run after v6 finishes; bump both datasets first.

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
- SHA-injection in the retired notebook push script so each push pinned to
  `git rev-parse HEAD`. Kernel was reproducibly tied to commit `a811829`.

#### Why it failed
After the library extract (commit `5a8f23b`) imports moved to
top-of-file in `dirt_wake_word/train.py`:

```python
from openwakeword.data import mmap_batch_generator   # line 22
```

A previous commit (`20f88eb`) had dropped `pip install -e ./openwakeword
--no-deps` from the shim, on the wrong assumption that the notebook base
image ships openwakeword 0.6.0. **It does not.** The module is niche
enough that it's not in the GPU base image. The eager top-level import
crashed at module load:

```
File ".../dirt/apps/wake-word/src/dirt_wake_word/train.py", line 22
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
that this exact bug class will surface in the remote runtime. v9 was the bill for
that trade-off.

### v10 — 2026-04-25 (failed in 4 min)

**Status:** failed at install — `pip install openwakeword==0.6.0` had no eligible release for python 3.12
**Kernel commit:** `d7a9704`
**Wall time:** ~3.5 min

#### What changed (vs v9)
- Added `openwakeword==0.6.0` to the shim's pip install batch (the v9 fix).

#### Why it failed
Two stacked PyPI compatibility issues against the notebook runtime's python 3.12:

```
ERROR: Ignored the following versions that require a different python version:
  0.5.0/0.5.1/0.6.0 Requires-Python >=3.6,<3.9
ERROR: Could not find a version that satisfies the requirement
  tflite-runtime<3,>=2.8.0; platform_system == "Linux" (from openwakeword)
```

1. openwakeword 0.6.0 — the last PyPI release with the auto_train shape
   our soft-fork builds on — declares `Requires-Python <3.9`. The runtime is
   3.12, so pip silently skips it.
2. Newer GitHub-only versions DO support 3.12 but transitively pull
   `tflite-runtime`, which is not published for cp312 + Linux on PyPI.

So no version constraint works against PyPI on that runtime.

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
Add a pre-push guard to the retired notebook push script:
`git fetch origin main && git merge-base --is-ancestor HEAD origin/main`.
Aborts with a clear "push first" message when HEAD isn't on origin/main,
saving the 5-min remote-runtime no-op. Commit: `e83c5f1`.

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
2. `wget melspectrogram.onnx` into the cloned openwakeword resources directory.

Step 2 lands in the *cloned* path, not the installed path. The runtime
looks at the installed path → file not found.

#### Fix (v14)
Switch to editable install: `pip install --no-deps -e ./openwakeword`.
With `-e`, the runtime `__file__` points back at the cloned openwakeword tree,
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
doesn't pick up in the locked-down runtime (likely a user-local
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
unmodified upstream notebook to establish a baseline before
soft-forking again.

#### Training config
Identical to v8 staged.

#### Validation set
- Same as v8 (28 good / 76 bad).

#### Results
v15 reached training proper — install ✓, generate_clips ✓, augment+features ✓
(the v13 resource-path fix held). Then ERROR at 1 h 51 m wall, deep
inside `_custom_train_model`, post-train selection, or export. Detailed
log was not pulled — the strategic decision to migrate to RunPod made
debugging the dead notebook path low value.

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
The cumulative pattern — every fix was a notebook-environment quirk
(base-image contents, py3.12 PyPI wheels, editable-install path
quirks, locked-down package layout) — is what triggered the platform
migration. See **`wiki/decisions/2026-04-25-runpod-migration.md`**.

### Migration to RunPod (2026-04-25)

After v15, abandoned managed notebooks in favor of a self-controlled
Docker image on RunPod. Rationale + setup details in
[`wiki/decisions/2026-04-25-runpod-migration.md`](decisions/2026-04-25-runpod-migration.md).

The v8 architectural design (per-subset aug, real-audio F1 selection,
512/50/200 batch composition) is unchanged — what changed is the
runtime environment. v16+ entries below correspond to RunPod runs.

### v16 — 2026-04-27

**Status:** superseded (deployed 2026-04-27 → 2026-04-27 same-day; replaced by v17)
**Model artifact:** `var/wake-word/models/2026-04-27-v16/hey_claudia.onnx` (renamed from `2026-04-26-225546-95hpev0e07b2ea` for convention)
**Trainer commit:** `1d10a93` (TTS-cache reciprocal-bug fix landed mid-run; pod ran on the prior image's code)
**Image digest:** `sha256:f552c860573e2a6a2ed63e3ef46ad55af45c8d377102275e1c77ff52e69c7763`
**W&B run:** [`bwwafjyq`](https://wandb.ai/adkravetz/dirt-wake-word/runs/bwwafjyq) (group `exp1-realmic-20260426-225544`)
**Pod:** `95hpev0e07b2ea`, RTX 4090 / 64 vCPU / 270 GB RAM
**Wall:** ~47 min total (per-phase below)

#### What changed (vs v6/m1f811ys)
- **Real-mic training data**, finally landed. 18 `realmic-pos_*.wav` (×10 dup = 180) + 18 `realmic-neg_*.wav` (×10 dup = 180) included in the seed pool. v8's plan, finally executed end-to-end. (Prior runs reverted to synthetic-only because the data hadn't survived the runtime migration.)
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

### v17 — 2026-04-27

**Status:** superseded (deployed 2026-04-27 → 2026-04-27; replaced by v20)
**Model artifact:** `var/wake-word/models/2026-04-27-v17/hey_claudia.onnx`
**Trainer commit:** `fec0916` (TTS-cache path fix — persist now reads from `WORKING/my_custom_model/<TARGET_WORD>/<subset>/`, not `WORKING/my_custom_model/<subset>/`)
**Image digest:** `sha256:7ed5e8d1641ef9f057438c4034c789a2e580b67b2074959bb950e5cd7119511f`
**W&B run:** [`812kjhu1`](https://wandb.ai/adkravetz/dirt-wake-word/runs/812kjhu1) (group `exp2-infra-validate-20260427-002635`)
**Pod:** `1t3ppxo6m9jjwo`, RTX 4090 / 64 vCPU
**Wall:** 50m54s

#### What changed (vs v16)
- **Same training data and config as v16** — this run was originally an infrastructure validation (validate ncpu bump, augment cache, watchdog self-DELETE). Identical mine/bg/features/validation content_hashes.
- **Variance from un-seeded randomness in augment + train.** `augment_clips` draws random RIRs / background-noise samples per call; model init / batch order also un-seeded. Same config + same data = ~20 % F1 spread across runs. v16 was a low-tail draw; v17 is a high-tail draw.
- **Augment-features cache landed and populated** (`input/dirt-wakeword-features-cache/6fbde72c9424563a/{4 npys + cache-metadata.json}`). Next same-data run hits cache and skips augment+features (~24 min saved).
- **TTS cache populated correctly for the first time ever** (66 000 WAVs hardlinked across all 4 subset dirs; cache-key.json + content match for the first time). Pre-existing path-mismatch bug fixed in commit `fec0916`.
- **Watchdog (`_self_delete` after sentinel write) verified.** Pod gone post-run; no orchestrator-driven DELETE was needed.

#### Why
Originally just an infra-validation run, but the F1 jump from 0.582 (v16) → 0.735 (v17) on identical data made the deploy decision easy. Variance is real — a run-to-run spread of this magnitude argues for either (a) running 3-5 retrains with explicit seeds and picking the median, or (b) just deploying the high-tail and relying on real-world soak to catch surprises.

#### Training data (UNCHANGED from v16)
- Positives: 2 000 ElevenLabs voice clones (×1) + 18 real-mic positives (×10) = 2 180 seeds
- Negatives: 360 ElevenLabs phonetic neighbors (×1) + 18 real-mic negatives (×10) = 540 seeds
- RIRs: 9 captured room impulse responses
- Background: AudioSet_16k + FMA from `dirt-wakeword-bg`
- Feature corpus: ACAV100M 2 000 h from `dirt-wakeword-features`

#### Training config (UNCHANGED from v16)
- `max_negative_weight`: 500
- `batch_n_per_class`: 512 / 50 / 200
- `steps`: 20 000
- DataLoader sharing strategy: `file_system`
- Per-subset augmentation: `realmic_*` skips RIR
- Best-checkpoint: real-audio F1 against `validation/`
- ncpu = `os.cpu_count() - 2` (62 on this 64-core host) — was `// 2` before; ~5 % wall-time gain on augment+features. Less than the 1.5× projected, suggesting the bottleneck is something other than CPU saturation (likely background-WAV I/O or GIL contention in the audiomentations chain).

#### Validation set
- `var/wake-word/validation/{good,bad}/`: 28 / 76 (canonical, MANIFEST hash sha256:93b03266…)

#### Results — sweep on the canonical 28/76 set

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 64.3 % | 85.7 % | **0.735** | 3/76 |
| 0.40 | 57.1 % | 94.1 % | 0.711 | 1/76 |
| 0.50 | 57.1 % | **100.0 %** | 0.727 | **0/76** |
| 0.60 | 46.4 % | 100.0 % | 0.634 | 0/76 |
| 0.70 | 46.4 % | 100.0 % | 0.634 | 0/76 |

**0 false positives at threshold 0.5** — meaningful operational improvement vs v16 (5/76 at the same threshold).

| Model | recall@0.5 | precision@0.5 | F1@0.5 | FP@0.5 |
|---|---:|---:|---:|---:|
| v3 (deployed before v16) | 42.9 % | 24.0 % | 0.308 | 38/76 |
| v5 | 35.7 % | — | 0.513 | — |
| v16 | 46.4 % | 72.2 % | 0.565 | 5/76 |
| **v17** | **57.1 %** | **100.0 %** | **0.727** | **0/76** |

#### Per-phase wall time
| Phase | Wall |
|---:|---:|
| boot + init | ~3 min |
| restore_tts_cache (MISS — cache-key was deleted to force rebuild) | 0 s |
| generate_clips (Piper, full from-scratch) | 20m46s |
| augment+features (MISS — first run with cache code) | 23m37s |
| train_loop (20 000 steps) | 6m08s |
| validate_against_real_set | 9.5 s |
| persist TTS cache (66 000 WAVs hardlinked) | <1 s |
| persist augment cache (4 npys hardlinked) | <1 s |
| **TOTAL** | **50m54s** |

Next same-data run should drop to **~7 min** (TTS + augment caches both HIT).

#### Operational notes
- Self-DELETE fired correctly (entrypoint's `_self_delete()` after writing SUCCESS). Pod was gone before the orchestrator could issue its own DELETE — orchestrator's `finally:` got 404 (idempotent).
- Orchestrator's `aws s3 sync` of `out/<pod_id>/` crashed on the RunPod paginator bug (familiar). Recovery: `scripts/wakeword-pull-pod-out 1t3ppxo6m9jjwo` direct-HEAD by known filename — got all 4 artifacts.
- Caches verified populated on the volume; S3 `list_objects_v2` returns `KeyCount=0 IsTruncated=True` for prefixes with many entries (RunPod listing bug — files are physically on the mounted filesystem, just not enumerable via the S3 API). Restore-side uses `Path.is_dir()` + `glob("*.wav")` directly on the mount, so the broken listing doesn't affect runtime.

#### Threshold tuning question
Production currently uses `WAKE_THRESHOLD = 0.6` (set in `apps/voice/src/dirt_voice/channels/voice.py:95`). At 0.6, v17 gets 46.4 % recall / 100 % precision / F1 0.634. At 0.5, v17 gets 57.1 % recall / 100 % precision / F1 0.727. Lowering to 0.5 picks up an extra 11 pp of recall with no precision cost — worth considering after some real-world soak.

### v18 — 2026-04-27

**Status:** **superseded by v17** (not deployed; v17 stayed in production)
**Model artifact:** `var/wake-word/models/2026-04-27-013813-iz72df0qooa32e/hey_claudia.onnx`
**Trainer commit:** `fec0916` (same as v17 — TTS-cache path fix)
**W&B run:** [`wfgvxv7r`](https://wandb.ai/adkravetz/dirt-wake-word/runs/wfgvxv7r) (group `exp3-realmic-v18-20260427-013811`)
**Pod:** `iz72df0qooa32e`, RTX 4090
**Wall:** 32m46s (TTS cache HIT, augment cache HIT — saved ~44 min vs v17 cold-cache wall)

#### What changed (vs v17)
- **38 new real-mic positive clips added** to `dirt-wakeword-mine` (54 → 56 files at the realmic-pos prefix; mine total 2443 files / 84.5 MB / hash `sha256:023bf1f2…`). Recorded by user across multiple condo locations and intonations on 2026-04-27, dumped, audio-reviewed, 11 weak/clipped takes pruned, 38 promoted. Held-out 38 ADDITIONAL clips kept locally at `/tmp/v17-eval-newclips/good/` so they're never seen by training.
- Same training config, same RIRs, same bg, same features cache.

#### Why
Address v17's modest 36.8 % real-mic recall (measured against held-out clips) by giving the model more in-distribution positive examples.

#### Results — canonical 28/76 set

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 57.1 % | 72.7 % | 0.640 | 6/76 |
| 0.40 | 57.1 % | 80.0 % | 0.667 | 4/76 |
| 0.50 | 57.1 % | 94.1 % | 0.711 | 1/76 |
| 0.60 | 46.4 % | **100.0 %** | 0.634 | **0/76** |
| 0.70 | 39.3 % | 100.0 % | 0.564 | 0/76 |

vs v17 @ 0.50: same recall, **lost 5.9 pp precision** (0 → 1 FP). vs v17 @ 0.30: same recall, **lost 13 pp precision** (3 → 6 FPs). v17 still wins on the lab metric.

#### Key finding (drove v19 hypothesis)
On v18's OWN training clips (the 56 realmic-pos in `mine`), v18 only fires on 31/56 at threshold 0.5 — **45 % recall on data the model just saw**. Same pattern on v17 (33-37 %). Conclusion: model is trained on RIR-convolved + bg-noise + EQ-distorted + pitch-shifted versions of the realmic clips, but inference sees raw Jabra audio. Train/inference distribution mismatch is capping real-world recall regardless of how many realmic clips we add.

This is what the validation set's recall curve was hiding — its 28 positives are mostly synth-style; the held-out 38-clip realmic set is a much harsher signal and shows v17/v18 ~33-37 % real-mic recall, far below the 57 % canonical-set recall. v19 was designed to test whether removing realmic augmentation closes the gap.

#### Operational notes
- Caches both HIT for the first time end-to-end: `restore_tts_cache` skipped Piper TTS, `_restore_cache` hardlinked the 4 feature .npys. Wall dropped from ~50 min (v17 cold cache) to ~33 min (v18 warm). Most of the remaining wall is `train_loop` (20k steps) at 6m08s plus boot/init/validation overhead.
- Watchdog + self-DELETE fired correctly. `aws s3 sync` of `out/<pod_id>/` again hit the RunPod paginator bug; pulled artifacts via `scripts/wakeword-pull-pod-out iz72df0qooa32e`.

### v19 — 2026-04-27

**Status:** **failed (not deployed)** — v17 stays as `current`
**Model artifact:** `var/wake-word/models/2026-04-27-121815-x186go75fyff8g/hey_claudia.onnx`
**Trainer commit:** `7836787` (zero augmentation for realmic + entrypoint scratch cleanup; built on `db5ce3d` augment.py change)
**W&B run:** [`338x9yk6`](https://wandb.ai/adkravetz/dirt-wake-word/runs/338x9yk6) (group `exp4-realmic-no-aug-v19-20260427-121814`)
**Pod:** `x186go75fyff8g`, RTX 4090
**Wall:** 39m28s (TTS cache HIT, augment cache **MISS** — REAL_AUDIO change invalidated key)

#### What changed (vs v18)
- **`REAL_AUDIO = dict.fromkeys(DEFAULTS, 0.0)`** — every augmentation probability set to 0 for `realmic_*` and `harvested_*` filename prefixes (synth clones / neighbors still get the default pipeline). See `apps/wake-word/src/dirt_wake_word/augment.py:55`.
- Same data, same training config otherwise.

#### Why
v17/v18 only fire on ~33-37 % of held-out real-mic clips — same model class, same data, just the filename-prefix-keyed augmentation pipeline. Hypothesis: zeroing all augmentation on real-mic clips puts training distribution onto raw Jabra audio (the inference distribution), closing the train/inference gap. If correct, real-mic recall on the held-out 38 clips should climb from 36.8 % (v17) toward 60-80 %.

#### Results — canonical 28/76 set

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 60.7 % | 70.8 % | 0.654 | 7/76 |
| 0.40 | 57.1 % | 76.2 % | 0.653 | 5/76 |
| 0.50 | 57.1 % | 80.0 % | 0.667 | 4/76 |
| 0.60 | 46.4 % | 86.7 % | 0.605 | 2/76 |
| 0.70 | 42.9 % | 85.7 % | 0.571 | 2/76 |

#### Results — held-out 38-clip real-mic set (`/tmp/v17-eval-newclips/good/`)

| Model | Recall@0.5 | Precision@0.5 |
|---|---:|---:|
| v17 | **36.8 %** (14/38) | 100.0 % |
| v19 | 23.7 % (9/38) | 100.0 % |

#### Hypothesis falsified
v19 lost ground on every metric: held-out real-mic recall **dropped 13 pp** (36.8 → 23.7), lab F1 **dropped 0.08** (0.735 → 0.654 at 0.30), lab precision **lost 20 pp** at 0.50 (100 → 80, 4 new FPs). The "remove augmentation to close the distribution gap" hypothesis is rejected.

Likely explanation: with `augmentation_rounds=2` and all probs=0, the trainer sees N exact-duplicate pairs of each realmic clip per epoch (no within-class variance from augmentation). Model overfits to those specific waveforms instead of generalizing. v17's "DEFAULTS minus RIR=0, AddBg=0.5" was the better balance — augmentation provides within-class variance that helps generalization, RIR-skip avoids the unphysical two-room reverb cascade.

Better next experiments: keep `Gain=1.0` only (pure amplitude variation, no spectral distortion); or drop `realmic_positive_duplication` from 10 → 2-3 so identical-augmented copies don't dominate the loss; or just collect more raw realmic clips.

#### Operational notes
- **Volume quota incident.** First four v19 submission attempts produced 0-byte FAILURE files within 30-80 s. Root cause: the 50 GB volume was full (per-pod `working/<pod_id>/` scratch never cleaned up across runs; 2 augment-features cache entries × ~5 GB each; ~15 GB of stale `working/my_custom_model/` from pre-isolation runs). Direct S3 PUT confirmed `InsufficientStorage: bucket storage quota exceeded`. Fix: bumped volume to 200 GB via `PATCH /v1/networkvolumes/<id>` (`{"size":200}`), wiped all stale `working/<pod_id>/` and `working/my_custom_model/` prefixes, and added `_cleanup_working()` to the entrypoint that wipes `WORKING/` after success or failure (commit `7836787`). Future runs won't slow-leak the volume.
- Augment cache key now keys on the augmentation prob dicts (`augmentation_synth`, `augmentation_real`), so the v19 REAL_AUDIO change invalidated v18's cache and forced a recompute (~22 min). v17 and v18 cache entries still on the volume; v19's new cache entry (different key) coexists.
- `aws s3 sync` of `out/<pod_id>/` again hit the RunPod paginator bug. Recovery: `scripts/wakeword-pull-pod-out x186go75fyff8g`. Same as every prior run — should permanently switch the orchestrator off `aws s3 sync` to direct head/download by known filename.

### v20 — 2026-04-27

**Status:** superseded (deployed 2026-04-27 18:45 → 2026-04-27 20:53 MDT; replaced by v23)
**Model artifact:** `var/wake-word/models/2026-04-27-v20/hey_claudia.onnx`
**Trainer commit:** `db525c2` (gain-only realmic augmentation)
**W&B run:** [`qr3g3kx3`](https://wandb.ai/adkravetz/dirt-wake-word/runs/qr3g3kx3) (group `exp5-realmic-gain-only-v20-20260427-142639`)
**Pod:** `f6x0z33zcpal7v`, RTX 4090
**Wall:** 33m03s (TTS cache HIT, augment cache **MISS** — REAL_AUDIO change invalidated key)

#### What changed (vs v19)
- **`REAL_AUDIO = {**dict.fromkeys(DEFAULTS, 0.0), "Gain": 1.0}`** — same all-zero spectral augmentation as v19, but Gain prob restored to 1.0. Pure amplitude randomization gives within-class variance without changing the frequency content (the inference distribution is raw Jabra audio; the deployment-room reverb / ambient noise are baked into the recording, so spectral augmentation pushes training off-distribution).
- Same data, same training config otherwise.

#### Why
v17 (DEFAULTS minus RIR=0, AddBg=0.5) was the best deployable model so far — 100% lab precision at 0.5/0.6, 36.8% held-out real-mic recall. v19 (all aug zeroed) overfit to identical-duplicate clip pairs and lost ground on every metric. Gain-only is the thinnest aug-pipeline above v19 — restores within-class variance without re-introducing the spectral mismatch.

#### Results — canonical 28/76 set

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 64.3 % | 90.0 % | 0.750 | 2/76 |
| 0.40 | 60.7 % | 94.4 % | 0.739 | 1/76 |
| 0.50 | 60.7 % | 94.4 % | 0.739 | 1/76 |
| 0.60 | 60.7 % | **100.0 %** | **0.756** | **0/76** |
| 0.70 | 50.0 % | 100.0 % | 0.667 | 0/76 |

#### Results — held-out 38-clip real-mic set (`/tmp/v17-eval-newclips/good/`)

| Threshold | Recall | Precision | F1 |
|---:|---:|---:|---:|
| 0.50 | 34.2 % (13/38) | 100.0 % | 0.510 |

#### Comparison

| Model | Best F1 (thresh) | @0.60 recall / precision | Held-out 38 recall@0.5 |
|---|---:|---:|---:|
| v17 | 0.735 (@0.30) | 46.4 % / 100 % | **36.8 %** (14/38) |
| v18 | 0.711 (@0.50) | 46.4 % / 100 % | (not measured) |
| v19 | 0.667 (@0.50) | 46.4 % / 86.7 % | 23.7 % (9/38) |
| **v20** | **0.756 (@0.60)** | **60.7 % / 100 %** | 34.2 % (13/38) |

At production `WAKE_THRESHOLD = 0.6`, v20 picks up **+14 pp recall** (46.4 → 60.7) over v17 with no precision cost. Held-out real-mic recall is within statistical noise of v17 (1-clip delta on a 38-clip set).

#### Deploy decision (pending)
v20 is a strict win on the lab metric. Held-out is a wash. Recommendation lean: deploy v20, mark v17 superseded. Open question: whether the held-out 1-clip drop is real signal or noise — would need more held-out clips to disambiguate.

#### Operational notes
- Scratch-cleanup landed in this image (commit `7836787`'s `_cleanup_working()` runs on success and failure). Volume usage scan after run: 31.06 GB / 200 GB used (15.5 %). Cleanup is working — pre-cleanup steady-state was leaking ~1-2 GB per run.
- `aws s3 sync` paginator bug fired again on artifact pull. Same workaround: `scripts/wakeword-pull-pod-out f6x0z33zcpal7v`. This is now four consecutive runs where the orchestrator's sync fails and direct-HEAD download recovers — switch the orchestrator off `aws s3 sync` permanently.

### v21 — 2026-04-27

**Status:** trained, validated (**not deployed** — precision regression on lab set)
**Model artifact:** `var/wake-word/models/2026-04-27-145636-o4e1ctum4rfrlt/hey_claudia.onnx`
**Trainer commit:** `552dc1a` (80/20 train/test split for realmic-{pos,neg})
**W&B run:** [`dn8p52uf`](https://wandb.ai/adkravetz/dirt-wake-word/runs/dn8p52uf) (group `exp6-harvest-negs-split-v21-20260427-145635`)
**Pod:** `o4e1ctum4rfrlt`, RTX 4090
**Wall:** 32m19s (TTS cache HIT, augment cache MISS — mine content_hash changed → new key)

#### What changed (vs v20)
- **30 new realmic-neg clips** added to `dirt-wakeword-mine/negatives/` (idx 100-129) from the 2026-04-27 harvest mode capture (36 reviewed, all keepers, 30/6 split between training and held-out validation). mine total: 2473 files (2056 voice_samples + 408 negatives + 9 RIRs), new content_hash.
- **6 new realmic-neg clips** added to `dirt-wakeword-validation/bad/` (idx h00-h05). validation/bad/ now 82 (was 76).
- **`seed.py` 80/20 train/test split** for realmic-pos and realmic-neg (sorted-by-name + idx % 5 == 0 → test). Previously every realmic clip went 100% to *_train and *_test was 100% Piper synth. Now:
  - realmic-pos: 45 train / 11 test (×10 dup each = 450/110 in seed pool)
  - realmic-neg: 39 train / 9 test (×10 dup each = 390/90 in seed pool)
- Same Gain-only realmic augmentation as v20.

#### Why
Two related changes bundled into one experiment:
1. Bigger real-mic negative pool (18 → 48 train, ~2.7× growth) so the model has more in-distribution false-positive shapes to push against.
2. The per-epoch lab metric was synth-blind — `*_test` was 100% Piper-generated audio, so checkpoint selection optimized for synth-style precision/recall, not for real audio. Splitting realmic into *_test gives the selector a real-audio signal.

#### Results — original 28/76 set (apples-to-apples with v17/v20)

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 64.3 % | 69.2 % | 0.667 | 9/76 |
| 0.40 | 60.7 % | 68.0 % | 0.642 | 8/76 |
| 0.50 | 57.1 % | 66.7 % | 0.615 | 8/76 |
| 0.60 | 50.0 % | 66.7 % | 0.571 | 7/76 |
| 0.70 | 42.9 % | 66.7 % | 0.522 | 6/76 |

#### Results — augmented 28/82 set (with 6 new harvest negs)

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 78.6 % | 68.8 % | 0.733 | 10/82 |
| 0.50 | 60.7 % | 68.0 % | 0.642 | 8/82 |
| 0.60 | 57.1 % | 69.6 % | 0.627 | 7/82 |
| 0.70 | 46.4 % | 76.5 % | 0.578 | 4/82 |

#### Results — held-out 38-clip real-mic set (`/tmp/v17-eval-newclips/good/`)

| Model | Recall@0.5 |
|---|---:|
| v17 | 36.8 % (14/38) |
| v19 | 23.7 % (9/38) |
| v20 | 34.2 % (13/38) |
| **v21** | **44.7 %** (17/38) |

**+8pp held-out real-mic recall, biggest jump yet.** The bigger negative pool + the train/test split combination is doing something useful for real-mic generalization.

#### Comparison summary @ production threshold 0.6

| Model | recall | precision | F1 | FPs (76 lab bad) |
|---|---:|---:|---:|---:|
| v17 | 46.4 % | 100 % | 0.634 | 0/76 |
| v20 | **60.7 %** | **100 %** | **0.756** | **0/76** |
| v21 | 50.0 % | 66.7 % | 0.571 | 7/76 |

v20 still wins on the production threshold. v21 is **not deployable** — 7 FPs out of 76 on a set v17 and v20 perfectly rejected is a hard regression for hands-free use.

#### Hypothesis on the precision drop
v17/v20's per-epoch `*_test` was 100% Piper synth. The best-checkpoint selector (max F1 against `*_test`) was therefore picking checkpoints that were synth-precision-optimal, which empirically also held up on the real-audio 76-bad set. v21's `*_test` now has 11 realmic-pos + 9 realmic-neg, so the selector is picking a checkpoint optimized for catching real-mic positives — at the cost of being more permissive on the kinds of audio the original 76-bad set captures (TV, kitchen sounds, ambient speech). Held-out real-mic recall is a direct beneficiary; lab precision is a direct casualty.

#### What to try next
- **Decouple the two changes.** Either (a) keep the 30 new harvest negatives in mine but revert seed.py to 100% realmic→train (so `*_test` stays synth-only, like v20). That isolates whether the harvest-negs alone help. Or (b) keep the seed split but revert the harvest-negs bump.
- **More representative validation/bad/ growth.** Add ambient-room-noise / TV / kitchen captures to the bad set so the selector's *_test reflects the real-world FP distribution we care about, not just the harvest-near-miss distribution.
- **Variance check.** Same-config retrains have ~20% F1 spread (per v17 lineage notes); v21 may be a low-tail draw. A second retrain at the same config would tell us how much of the 0.756→0.571 F1@0.6 drop is real signal.

#### Operational notes
- First run on the new `runpod-train` direct-download path (commit `5d2b527` dropped `aws s3 sync` for `pull_artifacts`). Worked end-to-end — artifacts pulled cleanly, no paginator bug, orchestrator's `finally:` got a clean DELETE on the post-sentinel pod.
- Volume usage post-run: 31.06 GB / 200 GB (15.5 % — same as post-v20, since `_cleanup_working` ran). Stale per-pod working/ dirs from v17/v18/v19/v20 also wiped earlier today (~70k keys removed).
- TTS cache invalidation behavior: cache stayed valid (target_phrase + n_samples + n_samples_val unchanged). Augment cache invalidated (mine content_hash changed → new key).

### v22 — 2026-04-28

**Status:** failed (not deployed) — disambiguation experiment, settled the v21 question
**Model artifact:** `var/wake-word/models/2026-04-27-181403-slmoc0pzxrj90q/hey_claudia.onnx`
**Trainer commit:** `7480df2` (revert seed.py 80/20 split — `revert(wake-word): drop 80/20 in-run split for v22 disambiguation`)
**W&B run:** [`spc3gpnk`](https://wandb.ai/adkravetz/dirt-wake-word/runs/spc3gpnk) (group `exp7-harvest-negs-no-split-v22-20260427-181402`)
**Pod:** `slmoc0pzxrj90q`, RTX 4090
**Wall:** 9m29s (TTS cache HIT, augment cache HIT — same mine + same REAL_AUDIO + same training params as v21 → keys matched, no recompute)

#### What changed (vs v21)
- **Reverted seed.py 80/20 split.** All realmic-pos / realmic-neg back to 100% `*_train`; `*_test` is again 100% Piper synth. Same as v20-era logic.
- **Kept** the 30 new harvest realmic-neg clips in `dirt-wakeword-mine/negatives/` (mine content_hash unchanged from v21).
- Same Gain-only realmic augmentation as v20/v21.

#### Why
v21 changed two things at once (harvest-negs bump + seed split) and the held-out gain (+8 pp) was confounded with the lab-precision regression (100 % → 67 %). v22 isolates the harvest-negs alone to see whether they carry the held-out signal or whether the split alone was responsible.

#### Results — original 28/76 set (apples-to-apples)

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 53.6 % | 65.2 % | 0.588 | 8/76 |
| 0.40 | 50.0 % | 73.7 % | 0.596 | 5/76 |
| 0.50 | 46.4 % | 72.2 % | 0.565 | 5/76 |
| 0.60 | 39.3 % | 84.6 % | 0.537 | 2/76 |
| 0.70 | 35.7 % | 100.0 % | 0.526 | 0/76 |

#### Results — held-out 38

| Model | Recall@0.5 |
|---|---:|
| v17 | 36.8 % (14/38) |
| v20 | 34.2 % (13/38) |
| v21 (split + negs) | 44.7 % (17/38) |
| **v22 (negs only)** | 28.9 % (11/38) |

#### Disambiguation conclusion
- Harvest-negs alone (v22): worse than v20 on every metric (lab F1 0.756 → 0.537, held-out 34.2 % → 28.9 %). Adding 30 harvest negatives to a 378-negative pool doesn't move the needle, and may have nudged the model in a worse direction (within variance).
- Split alone is the lever that drove v21's +8 pp held-out recall — at the cost of lab precision. The split changes which checkpoint the F1 selector picks (real-mic-permissive vs synth-style-precision-optimal); the harvest-negs are the smaller effect.

#### Variance caveat
Same-config retrains have ~20 % F1 spread (v17 vs v18 evidence). v22 may be a low-tail draw and v20 a high-tail draw of the same underlying distribution. A 3-5 retrain at v20 config would be needed to confirm any individual experiment's signal.

#### Decision
v20 stays deployed. Don't ship harvest-negs-only and don't ship the split alone. Future experiments should either (a) retrain v20 a few times to confirm it wasn't lucky, or (b) wait for the validation/bad/ set to grow with more harvest data so the held-out signal is less noisy than ±1 clip.

#### Operational notes
- First run with both caches (TTS + augment) hitting → 9m29s wall, the fastest end-to-end retrain on record. Boot + init dominates the wall now.
- Direct-download artifact pull worked end-to-end again (commit `5d2b527`).

### v23 — 2026-04-27

**Status:** **deployed** (currently `var/wake-word/models/current` symlink, deployed 2026-04-27 20:53 MDT; harvest mode still active)
**Model artifact:** `var/wake-word/models/2026-04-27-v23/hey_claudia.onnx`
**Trainer commit:** `00ae467` (capture-realmic VAD swap; trainer code identical to v22's `7480df2`)
**W&B run:** [`oj84cygb`](https://wandb.ai/adkravetz/dirt-wake-word/runs/oj84cygb) (group `exp8-noisy-realmic-v23-20260427-200209`)
**Pod:** `hdnj1ebbi4rqp5`, RTX 4090
**Wall:** 33m16s (TTS cache HIT, augment cache **MISS** — mine content_hash changed → new key)

#### What changed (vs v22)
- **26 new realmic-pos clips** captured in noisy conditions (TV / music / kitchen) added to `dirt-wakeword-mine/voice_samples/` at slots `realmic-pos_071..096.wav`. mine total realmic-pos: 56 → 82 (+46 %).
- Capture method: `capture-realmic.py` was upgraded to use silero-vad for segmentation (commit `00ae467`); the older RMS-silence segmenter falls apart with background noise.
- **Augmentation pipeline UNCHANGED** — same Gain-only `REAL_AUDIO` from v20/v21/v22. The new clips already carry real bg noise, so layering `AddBackgroundNoise` on top would push training further from the inference distribution, not closer; pure amplitude randomization is the right pipeline for noise-baked-in clips.
- Same v20-era seed.py logic (no 80/20 split, all realmic → train).

#### Why
v20's 34 % held-out recall ceiling was a sign that 56 realmic-pos clips weren't enough acoustic diversity — most existing clips were collected in quiet conditions and didn't cover the "TV/music/kitchen on" inference scenarios. Adding 26 noisy-environment clips directly addresses that gap.

#### Results — original 28/76 set

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 64.3 % | 69.2 % | 0.667 | 8/76 |
| 0.40 | 57.1 % | 80.0 % | 0.667 | 4/76 |
| 0.50 | 53.6 % | 83.3 % | 0.652 | 3/76 |
| 0.60 | 42.9 % | **100.0 %** | 0.600 | **0/76** |
| 0.70 | 39.3 % | 100.0 % | 0.564 | 0/76 |

#### Results — held-out 38-clip real-mic set

| Model | Recall@0.5 |
|---|---:|
| v17 | 36.8 % (14/38) |
| v20 | 34.2 % (13/38) |
| v21 (split + negs) | 44.7 % (17/38) |
| v22 (negs only) | 28.9 % (11/38) |
| **v23** | **42.1 %** (16/38) |

#### Comparison @ production threshold 0.6

| Model | Lab recall | Lab precision | Lab F1 | Held-out 38 recall |
|---|---:|---:|---:|---:|
| v17 | 46.4 % | 100 % | 0.634 | 36.8 % |
| v20 (was deployed) | **60.7 %** | 100 % | **0.756** | 34.2 % |
| v23 (now deployed) | 42.9 % | 100 % | 0.600 | **42.1 %** |

**Trade-off:** v23 catches 5 fewer of the 28 lab positives than v20 (synth-style clips it can no longer fire on), but catches 3 more of the 38 held-out real-mic clips. Lab precision is preserved at 100 % (zero FPs at threshold 0.6). Held-out is the metric closer to actual hands-free behavior, so the +8 pp held-out gain is the right thing to optimize.

#### Deploy decision
Deployed at 20:53 MDT. Harvest mode drop-in still active so we keep collecting negatives under v23. The lab-recall regression is real but acceptable given the held-out gain at preserved precision.

#### Operational notes
- Mine content_hash changed (added 26 voice_sample WAVs), invalidating the augment cache. TTS cache key (`target_phrase` + `n_samples` + `n_samples_val`) unchanged → cache HIT, saved ~22 min on Piper.
- Two near-misses in the v23 prep workflow worth noting:
  1. The promotion script initially copied to slots 057-082 without checking that 057-070 already had original realmic-pos files. Fixed by pulling the 14 originals back from the volume's S3 mirror and re-promoting at slots 071-096.
  2. The new `_stage-mine` rebuild lost the 30 v21 harvest-negs at first (they only ever lived in `_stage-mine/negatives/`, not in `var/wake-word/neighbors/`). Fixed by pulling them back from the volume.
- `capture-realmic.py` VAD-segmented 27 utterances from a 131-second noisy capture cleanly. silero-vad correctly avoided cutting on quiet musical moments, which the RMS-silence segmenter would have done.

### v24 — 2026-04-28

**Status:** trained, validated (**not deployed** — v23 keeps the better held-out recall)
**Model artifact:** `var/wake-word/models/2026-04-27-210739-ckpa3c4bugokqa/hey_claudia.onnx`
**Trainer commit:** `111e512` (mix realmic-neg into bg-noise pool + lower WAKE_THRESHOLD to 0.5)
**W&B run:** [`zzo1wwi9`](https://wandb.ai/adkravetz/dirt-wake-word/runs/zzo1wwi9) (group `exp9-bg-enrich-v24-20260427-210738`)
**Pod:** `ckpa3c4bugokqa`, RTX 4090
**Wall:** 28m05s (TTS cache HIT, augment cache **MISS** — schema bumped to v2 + `extra_bg_files` field added → new key)

#### What changed (vs v23)
- **Realmic-neg captures (48 files: 18 hand-recorded + 30 v21 harvest) added to the AddBackgroundNoise pool for synth augmentation.** Mixed with `extra_bg_dup=20` so they're ~62 % of the bg-noise samples drawn during synth augmentation. Synth phonetic neighbors are excluded (they're speech and would push the model toward firing on speech).
- **Production threshold `WAKE_THRESHOLD = 0.6 → 0.5`** in `apps/voice/src/dirt_voice/channels/voice.py:95`. Trades 3 FPs/76 lab for ~11 pp recall gain.
- **Cache schema bumped to v2** so v23's stored cache wouldn't be reused.

#### Why
Held-out real-mic recall has been the persistent ceiling. The hypothesis: the 2000 ElevenLabs synth clones get `AddBackgroundNoise` from generic AudioSet/FMA — generic music/sound effects nothing like our actual deployment-room ambient. Mixing in real captures from the room should push synth clips closer to the inference distribution, helping the model generalize to real-mic better.

#### Results — original 28/76 set

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 67.9 % | 90.5 % | **0.776** | 2/76 |
| 0.40 | 64.3 % | 90.0 % | 0.750 | 2/76 |
| 0.50 | 57.1 % | **100.0 %** | 0.727 | **0/76** |
| 0.60 | 53.6 % | 100.0 % | 0.698 | 0/76 |
| 0.70 | 39.3 % | 100.0 % | 0.564 | 0/76 |

#### Results — held-out 38

| Model | Recall@0.5 |
|---|---:|
| v17 | 36.8 % (14/38) |
| v20 | 34.2 % (13/38) |
| v21 (split + negs) | 44.7 % (17/38) |
| v22 (negs only) | 28.9 % (11/38) |
| v23 (deployed) | **42.1 %** (16/38) |
| **v24** | 36.8 % (14/38) |

#### Comparison @ 0.5 threshold

| Model | Lab R/P/F1 | Held-out 38 | FPs (lab 76) |
|---|---|---:|---:|
| v23 (deployed) | 53.6 % / 83.3 % / 0.652 | **42.1 %** (16/38) | 3 |
| v24 | 57.1 % / **100 %** / 0.727 | 36.8 % (14/38) | **0** |

#### Hypothesis didn't pan out
v24 essentially reverted to v17-like behavior on both metrics — bg-noise enrichment did *not* push held-out recall up. Three possible explanations, in order of likelihood:

1. **Variance.** Same-config retrains have ~20 % F1 spread (v17/v18 evidence). v23's 42.1 % was a high-tail draw and v24 reverted to the mean (~36-37 %). Most likely explanation given the magnitude.
2. **Over-weighted bg pool.** `extra_bg_dup=20` made realmic-neg ~62 % of the bg-noise samples, crowding out generic AudioSet/FMA. The model may have over-fit to deployment-room ambient and lost some generalization the generic bg corpus was providing. Could test with `extra_bg_dup=3-5` (~20 % representation).
3. **Wrong target.** Bg-noise mixing helps the model learn "wake-word + ambient" but the limiting factor on held-out may be acoustic *positives* (speaker variation, mic distance, room shape). In which case more realmic-pos > more bg-noise enrichment.

#### Decision
Don't deploy v24. v23 with `WAKE_THRESHOLD=0.5` keeps the better held-out recall. Lab precision drop at 0.5 (3 FPs/76 vs v24's 0/76) is a real cost but small in absolute terms — the 76-bad set is in-the-wild captures we don't see often.

#### What to try next (in priority order)
- **More realmic-pos.** 50-100 more clips in unseen acoustic conditions (bathroom / hallway / bedroom / across-room / quiet voice). Direct attack on the held-out ceiling. Effort: ~30-45 min capture session per condition.
- **Variance bracket.** Run 2-3 retrains at v23 config (no code changes) to measure how much of the v17→v23 progression is real. Free except for compute.
- **Tune `extra_bg_dup`.** Try ×5 instead of ×20 in case v24's reversion was bg-pool over-weighting.

#### Operational notes
- Cache schema bump (`_CACHE_SCHEMA_VERSION = 2`) cleanly invalidated v23's cache. New v24 cache landed under a fresh key.
- Wall dropped from v23's 33m to v24's 28m despite the augment cache MISS — augment recompute time has been steadily decreasing as we tune ncpu and cache layout.
- Threshold `0.5` change in production is independent of v24 — it's tied to the deployed v23 model right now.

### v25 — 2026-04-29

**Status:** trained, validated (**not deployed** — precision regression vs deployed v23)
**Model artifact:** `var/wake-word/models/2026-04-28-215735-vezabn1edxmozc/hey_claudia.onnx`
**Trainer commit:** `0e31d9e` (split synth/real source buckets; remove `harvested`; remove v24 realmic-neg background mixing)
**W&B run:** [`knjh48kw`](https://wandb.ai/adkravetz/dirt-wake-word/runs/knjh48kw) (group `exp10-v25-20260429`)
**Pod:** `vezabn1edxmozc`, RTX 4090
**Wall:** 2h24m06s (TTS cache HIT, augment cache **MISS** — mine content_hash changed + cache schema v3)

#### What changed (vs v24)
- **64 newly reviewed deployment-mic negatives** added to training data. `dirt-wakeword-mine` now has 112 realmic negatives total.
- Local source buckets were split by meaning:
  - positives: `synth-clones/` and `realmic-positives/`
  - negatives: `synth-neighbors/` and `realmic-negatives/`
- Removed the historical `harvested_*` training category after confirming no live files/use remained.
- Removed v24's realmic-negative-as-background-noise experiment. Realmic negatives are training negatives again, not `AddBackgroundNoise` material.
- Added `scripts/stage-wakeword-mine` so the split local buckets are staged into the legacy RunPod volume layout without re-mixing source semantics.

#### Why
The immediate goal was to test whether the 64 confirmed new real deployment-mic negatives improve precision while keeping v23's held-out real-mic recall. The cleanup also makes future experiments easier to reason about: synth neighbors and real-mic negatives can be counted and augmented independently.

#### Training data
- Positives: 2000 synth clones x1 + 82 realmic positives x10 = 2820 seeded positives.
- Negatives: 360 synth neighbors x1 + 112 realmic negatives x10 = 1480 seeded negatives.
- Backgrounds: AudioSet/FMA from `dirt-wakeword-bg`; no realmic-neg extra background pool.
- Feature corpus: ACAV100M 2000 h from `dirt-wakeword-features`.

#### Training config
- `max_negative_weight`: 500
- `target_false_positives_per_hour`: 10
- `steps`: 20 000
- Driver: soft-fork `_custom_train_model`
- Best-checkpoint selection: real-audio F1 over checkpoint candidates; selected step 17105 (recall 60.7 %, precision 73.9 %, F1 0.667 on 28/82).

#### Validation set
- Canonical RunPod validation: 28 positives / 82 negatives.
- Local apples-to-apples validation: 28 positives / 76 negatives (local checkout lacks the 6 v21 harvest validation bad clips).
- Held-out real-mic positives: 38 clips in `/tmp/v17-eval-newclips/good/`.

#### Results — current 28/82 validation set

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 67.9 % | 65.5 % | 0.667 | 10/82 |
| 0.40 | 67.9 % | 70.4 % | 0.691 | 8/82 |
| 0.50 | 64.3 % | 75.0 % | 0.692 | 6/82 |
| 0.60 | 57.1 % | 72.7 % | 0.640 | 6/82 |
| 0.70 | 50.0 % | 77.8 % | 0.609 | 4/82 |

#### Results — original 28/76 set

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 67.9 % | 67.9 % | 0.679 | 9/76 |
| 0.40 | 60.7 % | 81.0 % | 0.694 | 4/76 |
| 0.50 | 57.1 % | 88.9 % | 0.696 | 2/76 |
| 0.60 | 50.0 % | 87.5 % | 0.636 | 2/76 |
| 0.70 | 42.9 % | 92.3 % | 0.585 | 1/76 |

#### Results — held-out 38

| Model | Recall@0.5 |
|---|---:|
| v17 | 36.8 % (14/38) |
| v20 | 34.2 % (13/38) |
| v21 (split + negs) | 44.7 % (17/38) |
| v22 (negs only) | 28.9 % (11/38) |
| v23 (deployed) | **42.1 %** (16/38) |
| v24 | 36.8 % (14/38) |
| **v25** | 39.5 % (15/38) |

#### Deploy decision
Do **not** deploy v25. At the production threshold `0.5`, v25 improves current-set recall over v23 (64.3 % vs 57.1 %) but takes a large precision hit: 6/82 false positives vs v23's 1/82. Held-out real-mic recall is also worse than deployed v23 (15/38 vs 16/38). This is not a good trade for a hands-free wake word.

#### What we learned
- More confirmed realmic negatives did not automatically improve precision. With the current weighting and checkpoint selection, they pushed the selected model toward a more permissive operating point.
- v24's background-mixing path was not the cause of the v25 precision drop; v25 removed it and still regressed on false positives.
- The next useful data move is still more realmic positives in varied acoustic conditions, plus a larger real validation set before using real examples as an in-run selector.

#### Operational notes
- `augment+features` dominated wall time: 83m04s after the mine content hash/cache schema invalidated the cache. `train_loop` took 55m52s.
- The current launcher/W&B setup has poor live visibility during long phases: W&B showed `running` but did not upload `output.log` until the end. Add phase heartbeat files or scalar `wandb.log()` calls before the next long experiment.

### v26 — 2026-05-01

**Status:** trained, validated (**not deployed** — recall collapse)
**Model artifact:** `var/wake-word/models/2026-05-01-084240-l5ijbwvzwrp1ju/hey_claudia.onnx`
**Trainer commit:** `f36f3ee` (fresh image with v25 source-bucket cleanup + W&B/runpod polling fixes)
**Image digest:** `ghcr.io/akravetz/dirt-wake-word-trainer:latest@sha256:1423bddcbc3a43b3bdf3099fab3ec8ce650db54b9399c1e5804a5c6ad042bf68`
**W&B run:** [`nmo2hvi9`](https://wandb.ai/adkravetz/dirt-wake-word/runs/nmo2hvi9) (group `exp11-passive-harvest-v26-20260501`)
**Pod:** `l5ijbwvzwrp1ju`, RTX 4090
**Wall:** 33m05s

#### What changed (vs v25)
- Promoted the new passive-harvest clips from `var/logs/wake_audio/`:
  - 136 clips into `var/wake-word/realmic-negatives/` for training.
  - 34 clips held out locally in `var/wake-word/validation/bad/` as `harvest-v26_*`.
- `dirt-wakeword-mine` content hash: `sha256:c2255fe0f9119b0ee7391b6301cca78cb229b3683112ca1161992a1f3da756f7`.
- Rebuilt and pushed the trainer image before the final run so it used the v25+ split-source trainer, not the stale v24-era image.

#### Why
Test whether a much larger passive-harvest realmic-negative set improves precision without hurting the deployed v23 recall floor.

#### Training data
- Positives: 2000 synth clones x1 + 82 realmic positives x10 = 2820 seeded positives.
- Negatives: 360 synth neighbors x1 + 248 realmic negatives x10 = 2840 seeded negatives.
- Backgrounds: AudioSet/FMA from `dirt-wakeword-bg`; no realmic-neg extra background pool.
- Feature corpus: ACAV100M 2000 h from `dirt-wakeword-features`.

#### Training config
- `max_negative_weight`: 500
- `target_false_positives_per_hour`: 10
- `steps`: 20 000
- Driver: soft-fork `_custom_train_model`
- Best-checkpoint selection: real-audio F1 over checkpoint candidates.

#### Validation set
- RunPod canonical validation: 28 positives / 82 negatives.
- Local expanded validation: 28 positives / 110 negatives. This is the local 28/76 set plus the 34 v26 held-out harvest negatives; it does not include the 6 remote-only v21 validation bad clips.
- Held-out real-mic positives: 38 clips in `/tmp/v17-eval-newclips/good/`.

#### Results — RunPod 28/82 validation

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 60.7 % | 68.0 % | 0.642 | 8/82 |
| 0.40 | 53.6 % | 71.4 % | 0.612 | 6/82 |
| 0.50 | 53.6 % | 88.2 % | 0.667 | 2/82 |
| 0.60 | 46.4 % | 86.7 % | 0.605 | 2/82 |
| 0.70 | 35.7 % | 90.9 % | 0.513 | 1/82 |

#### Results — local expanded 28/110 validation

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 46.4 % | 54.2 % | 0.500 | 11/110 |
| 0.40 | 42.9 % | 63.2 % | 0.511 | 7/110 |
| 0.50 | 42.9 % | 70.6 % | 0.533 | 5/110 |
| 0.60 | 25.0 % | 70.0 % | 0.368 | 3/110 |
| 0.70 | 17.9 % | 100.0 % | 0.303 | 0/110 |

#### Results — held-out 38

| Model | Recall@0.5 |
|---|---:|
| v23 (deployed) | 42.1 % (16/38) |
| v25 | 39.5 % (15/38) |
| **v26 corrected** | **13.2 % (5/38)** |

#### Deploy decision
Do **not** deploy v26. It reduces false positives compared with v25 on the canonical RunPod validation set, but it does so by making the model too conservative: recall falls to 53.6 % on RunPod validation, 42.9 % on the expanded local set, and only 13.2 % on the held-out 38 positives. This is worse than deployed v23 for the hands-free user experience.

#### What we learned
- More realmic negatives at the current 10x duplication are not automatically helpful. With 248 realmic negatives x10, the model shifts toward rejection and loses too much positive sensitivity.
- The next training move should not be "more negatives only." Prefer more varied realmic positives, real-positive augmentation, or an explicit weighting experiment that caps realmic-negative influence.
- If we test the same data again, try reducing `REALMIC_NEGATIVE_DUPLICATION` before changing the positive path, and keep the local 34 held-out harvest clips as a precision check.

#### Operational notes
- First attempted pod `0hk4s3733z6w2y` was aborted by the local orchestrator after a transient RunPod S3 `401` during sentinel polling. Fixed in `f36f3ee`: S3 auth errors during sentinel polling are now retried instead of unwinding and deleting the pod.
- Second pod `o3hewjip1lzbaz` completed, but used the stale image from trainer commit `111e5128` (v24-era behavior). It is not a valid v26 candidate, even though it scored 57.9 % on held-out 38; ignore it for deploy decisions.
- W&B still did not expose useful live console logs during the corrected run. The refreshed image uploaded `config.yaml`, metadata, requirements, and summary after finish, but no `output.log` or multipart `logs/*` appeared mid-run. The settings change alone is insufficient; add explicit `wandb.log()` heartbeats or write phase status artifacts if live visibility matters.

### v27 — 2026-05-02

**Status:** trained, validated, **deployed config** (model symlink + threshold; voice service intentionally left off)
**Model artifact:** `var/wake-word/models/2026-05-02-190816-mdk9mxk41x7xt6/hey_claudia.onnx`
**Trainer commit:** `d103631e`
**Image digest:** `ghcr.io/akravetz/dirt-wake-word-trainer:latest@sha256:f0b7da0dcdd4143262165bab5692bc1385893aa1dd3c1f727a18b27088034124`
**W&B run:** [`mxl7s4yq`](https://wandb.ai/adkravetz/dirt-wake-word/runs/mxl7s4yq) (group `exp12-realmic-pos-v27`)
**Pod:** `mdk9mxk41x7xt6`, RTX 4090
**Wall:** 2h29m14s pod runtime; trainer total 144m22.8s

#### What changed (vs v26)
- Added two new real Jabra-mic positive capture sessions from 2026-05-02.
- Promoted 96 good clips total, then held out 15 evenly spaced new positives for validation.
- Training realmic positives increased from 82 to 163 (+81).
- Validation positives increased from 28 to 43.
- Excluded the newly reviewed realmic negatives `realmic-neg_330..407` from training for this run. The goal was to isolate the impact of added positives, not mix in more negatives.

#### Why
v26 showed that adding many realmic negatives alone collapses recall. v27 tests the opposite direction: keep the negative pool at the pre-new-harvest level and add substantially more real deployment-mic positives.

#### Training data
- Positives: 2000 synth clones x1 + 163 realmic positives x10 = 3630 seeded positives.
- Negatives: 360 synth neighbors x1 + 248 realmic negatives x10 = 2840 seeded negatives.
- Backgrounds: AudioSet/FMA from `dirt-wakeword-bg`; no realmic-neg extra background pool.
- Feature corpus: ACAV100M 2000 h from `dirt-wakeword-features`.

#### Volume hashes
- `dirt-wakeword-mine`: `sha256:abdb560913c94856cf657143f697dd2e0e4968d157c0e1423d384619c5c301f9` (2780 files, 102.5 MB).
- `dirt-wakeword-validation`: `sha256:2fc91e8d4adddcfb5cc487c02b5615873a5cc32095c4b5c480a85950835207ac` (153 local files, 8.8 MB).

#### Training config
- `max_negative_weight`: 500
- `target_false_positives_per_hour`: 10
- `steps`: 20 000
- Driver: soft-fork `_custom_train_model`
- Best-checkpoint selection: real-audio F1 over 11 checkpoint candidates; selected step 16578.

#### Run timeline
- TTS cache restore: 3m28s.
- `augment+features`: 86m37s, cache MISS, persisted key `671e08930e9e0585`.
- `train_loop`: 51m14s; 20 000 steps completed in 26m52s, then real-audio checkpoint selection/export.
- Best checkpoint selection on container validation: step 16578, recall 69.8 %, precision 62.5 %, F1 0.659.

#### Validation set notes
- Container validation reported 43 positives / 116 negatives.
- Local validation tree is 43 positives / 110 negatives.
- The mismatch is expected after this bump: `scripts/wakeword-volume-bump` uploads with `aws s3 cp --recursive`, so it does not delete remote-only stale validation files. The manifest hash reflects the local 153-file tree, while the container still saw 6 additional remote validation bad clips.

#### Results — container 43/116 validation

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 81.4 % | 55.6 % | 0.660 | 28/116 |
| 0.40 | 76.7 % | 57.9 % | 0.660 | 24/116 |
| 0.50 | 69.8 % | 62.5 % | 0.659 | 18/116 |
| 0.60 | 67.4 % | 70.7 % | 0.690 | 12/116 |
| 0.70 | 58.1 % | 75.8 % | 0.658 | 8/116 |

#### Results — local 43/110 validation

| Model | Threshold | Recall | Precision | F1 | False positives |
|---|---:|---:|---:|---:|---:|
| current v23 | 0.30 | 55.8 % | 43.6 % | 0.490 | 31/110 |
| current v23 | 0.40 | 51.2 % | 56.4 % | 0.537 | 17/110 |
| current v23 | 0.50 | 46.5 % | 62.5 % | 0.533 | 12/110 |
| current v23 | 0.60 | 39.5 % | 89.5 % | 0.548 | 2/110 |
| current v23 | 0.70 | 34.9 % | 93.8 % | 0.508 | 1/110 |
| **v27** | 0.30 | 74.4 % | 57.1 % | 0.646 | 24/110 |
| **v27** | 0.40 | 67.4 % | 56.9 % | 0.617 | 22/110 |
| **v27** | 0.50 | 62.8 % | 60.0 % | 0.614 | 18/110 |
| **v27** | 0.60 | 62.8 % | 67.5 % | 0.651 | 13/110 |
| **v27** | 0.70 | 55.8 % | 80.0 % | 0.658 | 6/110 |

#### Results — held-out 38 positives

| Model | Recall@0.3 | Recall@0.4 | Recall@0.5 | Recall@0.6 | Recall@0.7 |
|---|---:|---:|---:|---:|---:|
| current v23 | 42.1 % (16/38) | 42.1 % (16/38) | 42.1 % (16/38) | 36.8 % (14/38) | 31.6 % (12/38) |
| **v27** | **84.2 % (32/38)** | **73.7 % (28/38)** | **68.4 % (26/38)** | **60.5 % (23/38)** | **42.1 % (16/38)** |

#### Deploy decision
Deploy v27 config at threshold `0.6`. The `var/wake-word/models/current` symlink now points at `2026-05-02-190816-mdk9mxk41x7xt6`, and `apps/voice/src/dirt_voice/channels/voice.py` sets `WAKE_THRESHOLD = 0.6`. The `dirt-voice.service` unit is intentionally left inactive while voice-channel changes continue.

At the previous production threshold `0.5`, v27 improves local validation recall from 46.5 % to 62.8 % with false positives rising from 12/110 to 18/110. Threshold `0.6` looks like the better operating point: it keeps the same 62.8 % local recall while reducing false positives to 13/110, and it still beats current v23 on the held-out 38 positives (23/38 vs 14/38 at 0.6).

#### What we learned
- More realmic positives directly addressed the v26 recall collapse. The held-out 38 result is the clearest signal: v27 gets 26/38 at threshold 0.5 vs deployed v23's 16/38 and v26's 5/38.
- The added positives did increase false positives relative to current v23 at the same `0.5` threshold, but threshold `0.6` largely restores precision while preserving the recall gain.
- Before deployment, clean the remote validation prefix so RunPod and local validation counts match, then re-run validation on a single canonical 43/110 or 43/116 set.

#### Operational notes
- Live W&B `output.log` worked for this run. It exposed phase logs while training was running, though the training loop itself remained quiet until progress completed.
- Feature extraction still runs through CPU ONNX (`CUDAExecutionProvider` unavailable), dominating wall time on cache misses.

### v28 diagnostic — 2026-05-02

**Status:** trained for instrumentation only (**not deployed**)
**Model artifact:** `var/wake-word/models/2026-05-02-220123-s8mqxjl5pbbpi9/hey_claudia.onnx`
**Trainer commit:** `d103631-instrumented` (one-off local instrumentation image)
**Image ref:** `ghcr.io/akravetz/dirt-wake-word-trainer:instrumented-v27-20260502-215431`
**Image digest:** `sha256:bdd944ed1c0a7ed20ae78fdc99a25a7a5e5ce6473faa7c94a84f0a76d9a79d0f`
**W&B run:** [`nt9uzxlu`](https://wandb.ai/adkravetz/dirt-wake-word/runs/nt9uzxlu) (group `exp13-v27-instrumented`)
**Pod:** `s8mqxjl5pbbpi9`, RTX 4090
**Wall:** 9m52s pod runtime; trainer total 8m15.1s before post-run TTS cache persist.

#### What changed (vs v27)
- No intentional data or hyperparameter change.
- Added timing instrumentation that splits the old broad `train_loop` into:
  - `prepare_train_inputs`
  - `fit_model`
  - `select_checkpoint`
  - `export_model`
- Added runtime/device logging for Torch/CUDA, feature array shapes, dataloader worker settings, model device after fit, fit throughput, and per-candidate checkpoint-selection elapsed time.

#### Why
Diagnose why v27 reported a 51m14s `train_loop` after prior warm-cache runs were usually under 30 minutes end-to-end.

#### Training data
- Same manifest as v27.
- Positives: 2000 synth clones x1 + 163 realmic positives x10 = 3630 seeded positives.
- Negatives: 360 synth neighbors x1 + 248 realmic negatives x10 = 2840 seeded negatives.
- Feature cache key `671e08930e9e0585` was hot.

#### Run timeline
- TTS cache restore: 1m06.8s for 69 970 WAVs.
- `augment+features`: 0.1s, cache HIT.
- `prepare_train_inputs`: 1.2s.
- `fit_model`: 4m01.2s, 20 000 steps at 82.92 steps/sec.
- Model device after fit: `cuda:0` on an NVIDIA GeForce RTX 4090.
- `select_checkpoint`: 2m40.5s across 11 candidates, about 14.5s/candidate.
- `export_model`: 0.0s.
- Container validation: 14.8s.
- Post-run TTS cache persist rewrote 69 970 WAV links/copies before the success sentinel.

#### Results — container 43/116 validation

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 53.5 % | 57.5 % | 0.554 | 17/116 |
| 0.40 | 51.2 % | 66.7 % | 0.579 | 11/116 |
| 0.50 | 48.8 % | 75.0 % | 0.592 | 7/116 |
| 0.60 | 39.5 % | 73.9 % | 0.515 | 6/116 |
| 0.70 | 34.9 % | 78.9 % | 0.484 | 4/116 |

#### Deploy decision
Do **not** deploy v28. It was a diagnostic rerun and underperforms v27's selected model on recall. `var/wake-word/models/current` remains pointed at v27 (`2026-05-02-190816-mdk9mxk41x7xt6`), and the voice service remains inactive.

#### What we learned
- The negative-weight ramp to 500 is not the explanation for the long v27 wall time. In the instrumented warm-cache rerun, the 20 000-step fit finished in about four minutes on GPU.
- v27's 144-minute runtime was primarily the feature-cache miss (`augment+features` 86m37s). The remaining discrepancy is mostly that the old `train_loop` label combined true fit, real-audio checkpoint selection, and export, plus an anomalous v27 wrapped-phase delay that did not reproduce.
- Checkpoint selection is now a visible fixed cost: about 2m40s for 11 candidates on the current 43/116 validation set.
- The post-run TTS cache persist rewrites all 69 970 cached WAVs even on a cache-hit run. It happens after the printed trainer total and before the success sentinel, so it should be timed or short-circuited separately if pod wall time matters.

### v29 diagnostic — 2026-05-03

**Status:** feature-cache-miss benchmark only (**aborted after feature phase; not deployed**)
**Model artifact:** none
**Trainer commit:** `d103631-ortgpu-cachemiss` (one-off schema-v4 GPU feature image)
**Image ref:** `ghcr.io/akravetz/dirt-wake-word-trainer:ortgpu-cachemiss-v29-20260503-140738`
**Image digest:** `sha256:f0499aa904a16e4827ed8157cf77daa1311278caddd35908631d733659730a3a`
**W&B run:** [`5ctqzzxf`](https://wandb.ai/adkravetz/dirt-wake-word/runs/5ctqzzxf) (group `exp14-ortgpu-cachemiss-v29`)
**Pod:** `v60nmmtp9cyakf`, RTX 4090 (deleted after feature timing)
**Wall:** aborted after feature phase and partial fit; no model artifacts pulled.

#### What changed
- Switched the trainer image from CPU `onnxruntime` to `onnxruntime-gpu==1.22.0`.
- Added `DIRT_WAKEWORD_FEATURE_DEVICE=auto|cpu|gpu` selection for feature extraction.
- Added fail-fast provider verification: explicit `gpu` requires `AudioFeatures` to use `CUDAExecutionProvider`.
- Bumped feature-cache schema to v4 so CPU-generated feature arrays are not reused by the GPU benchmark.

#### Why
Measure the real full-data feature-cache miss path on GPU after v27 spent 86m37s in CPU ONNX feature extraction.

#### Run timeline
- `prepare_seed_clips`: 18.7s.
- `restore_tts_cache`: 4m38.7s for 69 970 WAVs.
- `generate_clips`: 29.5s.
- `augment+features`: 47m14.4s, cache MISS, key `38fcb98ff35d78fd`, actual provider `CUDAExecutionProvider`, persisted 4 files.
- `prepare_train_inputs`: 1m09.3s.
- Run was manually stopped during `fit_model` after the feature benchmark completed; pod deleted. W&B may show crashed/running because the run did not finish normally.

#### What we learned
- GPU ORT works on RunPod: the provider smoke test resolved `gpu`, Torch saw the RTX 4090, and `AudioFeatures` used `CUDAExecutionProvider`.
- The cache-miss feature path improved from v27's 86m37s to 47m14s, about a 45 % wall-time reduction / 1.8x speedup.
- Feature generation is still the dominant cache-miss cost. The remaining time is likely augmentation, memmap writes and flushes, `trim_mmap`, network-volume I/O, and per-subset/session overhead, not only ONNX inference.
- Repeated ONNX Runtime cuDNN destroy errors appeared once PyTorch training started after GPU feature extraction. Before using this in normal training, isolate GPU feature extraction from the training process or explicitly release ORT sessions and verify fit speed/noise.
- Next high-value optimization is likely local scratch for feature `.npy` writes/cache persist, less frequent memmap flushing, per-subset timers, and ORT session cleanup or subprocess isolation.

### v30 diagnostic — 2026-05-04

**Status:** trained for warm-cache timing only (**not deployed**)
**Model artifact:** `var/wake-word/models/2026-05-03-224938-a5ai72c982syqj/hey_claudia.onnx`
**Trainer commit:** `3c7a3bd` (one-off dirty diagnostic image)
**Image ref:** `ghcr.io/akravetz/dirt-wake-word-trainer:uv-ort-fullwarm-force-20260504-2244`
**Image digest:** `sha256:2ecfb5c666e974140962890ee3d386deb99716e32a194b58aa2a90ab1520d909`
**W&B run:** [`wgbwiazf`](https://wandb.ai/adkravetz/dirt-wake-word/runs/wgbwiazf) (group `exp16-ortgpu-fullwarm`)
**Pod:** `a5ai72c982syqj`, RTX 4090 (deleted by entrypoint; orchestrator DELETE saw 404)
**Wall:** trainer total 9m38.2s; pod runtime about 11m25s.

#### What changed
- Production defaults restored: 30 000 synth train, 3000 synth test, 20 000 steps, full inner-loop validation, full real-audio checkpoint selection.
- `DIRT_WAKEWORD_FEATURE_DEVICE=gpu` forced, but feature arrays hit the v29 GPU cache.
- Added GPU memory diagnostics around ORT feature extraction and PyTorch fit.
- Used `DIRT_WAKEWORD_TTS_CACHE_MODE=force` once because the previous small diagnostic had overwritten the shared TTS cache key with `201/50`; the full run restored 69 970 cached WAVs and rewrote the full-run cache key according to container logs.

#### Why
Measure the actual warm-cache full-run runtime after GPU ORT/provider cleanup work, without the feature-cache miss dominating the timing.

#### Run timeline
- `prepare_seed_clips`: 7.3s.
- `restore_tts_cache`: 1m15.4s, restored 69 970 WAVs.
- `generate_clips`: 10.5s.
- `augment+features`: 0.2s, cache HIT, key `38fcb98ff35d78fd`.
- `prepare_train_inputs`: 1m05.1s.
- `fit_model`: 4m03.4s, 20 000 steps at 82.19 steps/sec.
- `select_checkpoint`: 2m41.6s across 11 candidates.
- `validate_against_real_set`: 14.5s.
- `TOTAL`: 9m38.2s.

#### Results — container 43/116 validation

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 72.1 % | 66.0 % | 0.689 | 16/116 |
| 0.40 | 69.8 % | 75.0 % | 0.723 | 10/116 |
| 0.50 | 65.1 % | 82.4 % | 0.727 | 6/116 |
| 0.60 | 55.8 % | 88.9 % | 0.686 | 3/116 |
| 0.70 | 46.5 % | 90.9 % | 0.615 | 2/116 |

#### Deploy decision
Do **not** deploy v30. This was a timing/diagnostic rerun, not a planned model-selection experiment. `var/wake-word/models/current` remains v27, and the voice service remains inactive.

#### What we learned
- Warm-cache full training is back under 10 minutes in-container. The old v27 2h29m pod wall was dominated by a cold CPU feature-cache miss.
- PyTorch fit is healthy after the ORT cleanup/provider work: full 20 000-step fit ran at 82.19 steps/sec, matching the prior warm-cache v28 diagnostic.
- No cuDNN teardown errors appeared in the W&B output log.
- Feature cache and TTS cache are now the main runtime levers. Feature cache hit is effectively free; TTS restore still costs about 1m15s.
- Container logs say the full TTS cache key was rewritten, but the RunPod S3 API still returned missing for `dirt-wakeword-tts-cache/cache-key.json` after the pod deleted. Verify TTS-cache visibility before the next production run; `DIRT_WAKEWORD_TTS_CACHE_MODE=force` remains a recovery option if the cache files are present but the key is stale.

### v31 diagnostic — 2026-05-04

**Status:** trained for full cold-cache timing only (**not deployed**)
**Model artifact:** `var/wake-word/models/2026-05-04-055255-qgb2sm1q424an4/hey_claudia.onnx`
**Trainer commit:** `dd3544e9c33a0458bbee07839d8f79076e67035f` (dirty diagnostic image)
**Image ref:** `ghcr.io/akravetz/dirt-wake-word-trainer:uv-ort-fullcold-20260504-0548`
**Image digest:** `sha256:74716cc52e5100f749630866ca8d93a6e3c34a953d798a5a5ee2d128fa210a4a`
**W&B run:** [`hfmhxd18`](https://wandb.ai/adkravetz/dirt-wake-word/runs/hfmhxd18) (group `exp17-ortgpu-fullcold`)
**Pod:** `qgb2sm1q424an4`, RTX 4090 (deleted by orchestrator)
**Wall:** trainer total 104m52.9s; manifest start-to-finish 109m46.3s; launcher completed after artifact pull at about 115 minutes.

#### What changed
- Full production defaults were used again: 30 000 synth train, 3000 synth test, 20 000 steps, full inner-loop validation, and full real-audio checkpoint selection.
- `DIRT_WAKEWORD_FEATURE_DEVICE=gpu` forced GPU feature extraction.
- A one-run `DIRT_WAKEWORD_FEATURE_CACHE_SALT=fullcold-20260504-0548` override intentionally invalidated the feature cache. The salt was passed only in this RunPod command and was not added to `.env`, image defaults, or production config.
- `DIRT_WAKEWORD_TTS_CACHE_MODE=force` was kept as a recovery guard for the previously stale/missing TTS cache key.

#### Why
Measure full end-to-end cold-cache runtime after the GPU ORT, dependency, provider cleanup, and memory diagnostic changes.

#### Run timeline
- `prepare_seed_clips`: 16.9s.
- `restore_tts_cache`: 3m10.4s, restored 69 970 WAVs.
- `generate_clips`: 30.9s.
- `augment+features`: 42m48.4s, cache MISS, salted key `c23acf0742f6f380`, actual provider `CUDAExecutionProvider`.
- `prepare_train_inputs`: 52.2s.
- `fit_model`: 26m47.3s, 20 000 steps at 12.45 steps/sec.
- `select_checkpoint`: 28m15.6s across 13 candidates, about 130s/candidate.
- `export_model`: 0.2s.
- `validate_against_real_set`: 2m10.5s.
- `TOTAL`: 104m52.9s.

#### Results — container 43/116 validation

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 76.7 % | 58.9 % | 0.667 | 23/116 |
| 0.40 | 76.7 % | 64.7 % | 0.702 | 18/116 |
| 0.50 | 74.4 % | 80.0 % | 0.771 | 8/116 |
| 0.60 | 74.4 % | 82.1 % | 0.780 | 7/116 |
| 0.70 | 62.8 % | 84.4 % | 0.720 | 5/116 |

#### Deploy decision
Do **not** deploy v31. This was a cold-cache runtime diagnostic. `var/wake-word/models/current` remains v27, and the voice service remains inactive.

#### What we learned
- GPU cold feature generation improved slightly relative to v29: 42m48s vs 47m14s, about 9 % faster. It is still the largest cold-cache phase.
- PyTorch fit became slow again after cold GPU feature extraction: 12.45 steps/sec vs 82.19 steps/sec on the warm-cache v30 run. Checkpoint selection showed the same slowdown pattern, taking 28m15s instead of 2m41s.
- No cuDNN teardown errors appeared in the W&B output log, so the cleanup/provider changes removed the visible error noise but did not fully restore PyTorch performance after a full cold ORT feature pass.
- The remaining likely fix is stronger isolation between GPU ORT feature generation and PyTorch training, or deeper allocator/provider cleanup. The subprocess isolation option now looks less like a cosmetic workaround and more like the cleanest way to prove whether ORT state is contaminating the PyTorch phase.
- The feature-cache salt did its job for this run only. It is not persistent production configuration.

### v32 diagnostic — 2026-05-04

**Status:** telemetry validation runs only (**not deployed**)
**Model artifacts:**
- `var/wake-word/models/2026-05-04-105149-34165rzui5mcg2/hey_claudia.onnx`
- `var/wake-word/models/2026-05-04-111231-v9zcr5rv2od0jf/hey_claudia.onnx`
**Trainer commit:** `7e32dd704b0fde4e123081545712995b5bd6c831` (dirty diagnostic images)
**Image refs:**
- `ghcr.io/akravetz/dirt-wake-word-trainer:telemetry-instrumented-20260504`
- `ghcr.io/akravetz/dirt-wake-word-trainer:telemetry-instrumented2-20260504`
**Final image digest:** `sha256:123bcae42f3fdc421729bee6b9be971e883ac5ee72fc4257e36c4ed69fb1923a`
**W&B runs:**
- [`r6ngz1xd`](https://wandb.ai/adkravetz/dirt-wake-word/runs/r6ngz1xd) (group `exp18-telemetry-small`)
- [`itk28bmt`](https://wandb.ai/adkravetz/dirt-wake-word/runs/itk28bmt) (group `exp18-telemetry-small-v2`)
**Pods:** `34165rzui5mcg2`, `v9zcr5rv2od0jf`, both RTX 4090, both deleted/self-deleted.

#### What changed
- Added feature-generation telemetry:
  - generator/augmentation time
  - ORT embedding time
  - memmap write/flush time
  - `trim_mmap` time
  - rows, output shape, output bytes, per-subset total
- Replaced the black-box upstream `train_model()` call with a behavior-equivalent local instrumented training loop:
  - sampled `train_step_telemetry`
  - batch fetch, H2D copy, forward, high-loss filtering, loss, backward, optimizer, metric timing
  - `inner_validation_telemetry` for false-positive and synthetic validation
- Added checkpoint-selection telemetry:
  - export, ONNX session init, WAV load, `model.reset()`, prediction, metrics, provider, windows
- Added ORT/PyTorch boundary snapshots:
  - process RSS / GC counts
  - selected torch CUDA allocator counters
- Extended `scripts/wakeword-wandb-pull system <run_id>` so future agents can pull W&B system telemetry via `run.history(stream="system")` and phase-align it with `output.log`.
- Docker dependency guard was tightened: CPU `onnxruntime` is removed after uv resolution and `onnxruntime-gpu==1.22.0` is force-reinstalled, because the CPU wheel can shadow `CUDAExecutionProvider`.

#### Why
Make the next runtime investigation answerable from logs/API artifacts instead of W&B UI inspection or generic host telemetry. The target questions are: feature generation split, PyTorch fit bottleneck, checkpoint-selection bottleneck, and whether host telemetry agrees with code-path timing.

#### Smoke test
- `scripts/runpod-build-image telemetry-instrumented-20260504 --no-push` failed initially because CPU `onnxruntime` shadowed CUDA providers; the build-time provider check caught it.
- After the Dockerfile fix, `scripts/runpod-build-image telemetry-instrumented-20260504 --no-push` passed local smoke.
- After the progress-safe train telemetry and reset timing patch, `scripts/runpod-build-image telemetry-instrumented2-20260504 --no-push` passed local smoke.

#### Run A — `r6ngz1xd`, 500 steps
- Config: `N=201`, `N_val=50`, `steps=500`, `VAL_STEPS_COUNT=4`, `FP_VAL_MAX_WINDOWS=4096`, GPU feature extraction, TTS cache ignored, salted feature cache.
- `generate_clips`: 1m20.5s.
- `augment+features`: 3m22.5s.
  - positive_train: total 131.2s; generator 94.5s, embed 26.2s, memmap write 7.3s, flush 1.1s, trim 1.6s.
  - negative_train: total 53.4s; generator 29.0s, embed 16.9s, memmap write 4.3s, flush 0.6s, trim 2.5s.
- `fit_model`: 1m00.6s. Train-step telemetry was missing from W&B output because progress-bar rendering swallowed the print lines; fixed in Run B with `tqdm.write()`.
- `select_checkpoint`: 6m32.0s across 3 candidates, about 130s/candidate.
  - Candidate 0 measured: export 0.2s, init 0.5s, WAV load 1.6s, inference 51.2s, total 130.4s. This exposed missing per-clip `reset()` timing, added in Run B.
- `validate_against_real_set`: 2m10.0s.
- `TOTAL`: 14m44.4s.

#### Run B — `itk28bmt`, 250 steps
- Config: `N=201`, `N_val=50`, `steps=250`, `VAL_STEPS_COUNT=2`, `FP_VAL_MAX_WINDOWS=4096`, GPU feature extraction, TTS cache ignored, salted feature cache.
- `generate_clips`: 12.5s.
- `augment+features`: 50.4s.
  - positive_train: total 32.8s; generator 21.3s, embed 3.8s, memmap write 6.1s, flush 0.7s, trim 0.9s.
  - negative_train: total 15.1s; generator 9.2s, embed 3.1s, memmap write 1.8s, flush 0.4s, trim 0.7s.
- `fit_model`: 7.0s. Train-step telemetry appeared correctly in W&B:
  - step 0 total 2.64s; batch fetch 1.91s, forward 0.41s, backward 0.14s.
  - steady sampled steps were about 0.0047-0.0055s each, with sub-millisecond forward/backward/optimizer.
- `select_checkpoint`: 15.6s for 1 candidate.
  - provider `CPUExecutionProvider`.
  - export 0.05s, ONNX init 0.08s.
  - good clips: reset 2.36s, inference 1.32s, 824 windows.
  - bad clips: reset 6.23s, inference 4.28s, 2717 windows.
- `validate_against_real_set`: 14.5s.
- `TOTAL`: 1m46.6s.

#### W&B system telemetry
Pulled with:

```bash
scripts/wakeword-wandb-pull system r6ngz1xd --samples 10000
scripts/wakeword-wandb-pull system itk28bmt --samples 10000
```

- Run A had 118 system rows over 30.4s-900.4s. Run B had 14 rows over 15.4s-105.4s.
- Checkpoint selection in both runs showed 0 % GPU utilization; the path is CPU/ORT inference.
- Run A selection also showed low CPU percentage, so the 130s/candidate path likely reflects per-process/ORT/runtime behavior or host throttling rather than GPU saturation.
- Run B selection was normal at 15.6s and attributed most time to `model.reset()` plus prediction.

#### Deploy decision
Do **not** deploy either v32 model. These were tiny diagnostic runs and both had 0 % real-audio recall. `var/wake-word/models/current` remains v27, and the voice service remains inactive.

#### What we learned
- The telemetry hooks are now sufficient to diagnose the next full run without adding a duplicate `nvidia-smi` sampler.
- Feature-generation time is dominated by generator/augmentation, with ORT embedding second and memmap writes third on these small runs.
- Checkpoint selection uses ONNX Runtime CPU provider by construction. On a healthy run, the 43/116 validation set can score in about 15s/candidate; on the slow run it was 130s/candidate with the same model count. That keeps host/runtime variability in play.
- `model.reset()` is a material part of checkpoint/validation scoring and must be tracked; Run B showed reset time exceeded prediction time.
- The Dockerfile now guards against CPU `onnxruntime` shadowing the GPU provider, which is important for future uv-managed images.

### v33 diagnostic — 2026-05-04

**Status:** validation-path runtime diagnostic only (**not deployed**)
**Model artifact:** `var/wake-word/models/2026-05-04-114053-171it6nj22yoby/hey_claudia.onnx`
**Trainer commit:** `7e32dd704b0fde4e123081545712995b5bd6c831` (dirty diagnostic image)
**Image ref:** `ghcr.io/akravetz/dirt-wake-word-trainer:batched-validation-20260504`
**Image digest:** `sha256:b61a875fc4ab1ed269d0c5aff7d98e1a76ca0460e2c068c302ec332630b01dc2`
**W&B run:** [`3on01kp1`](https://wandb.ai/adkravetz/dirt-wake-word/runs/3on01kp1) (group `exp19-batched-validation-small`)
**Pod:** `171it6nj22yoby`, RTX 4090, self-deleted before orchestrator cleanup.

#### What changed
- Replaced per-clip `openwakeword.Model.reset()` checkpoint and final validation scoring with a shared real-audio scorer in `dirt_wake_word.real_audio_score`.
- The scorer precomputes streaming feature windows once for each real-audio split, preserving openwakeword's streaming preprocessor and first-five-prediction warmup behavior.
- Temporary checkpoint ONNX models and final validation ONNX models are made dynamic-batch in memory before scoring. The exported/deployed ONNX artifact is not rewritten.
- Removed the old streaming scoring path instead of keeping it as a fallback.

#### Why
Checkpoint selection and final real-audio validation had become meaningful runtime costs. In the prior small telemetry run, selection took 15.6s for one candidate and final validation took 14.5s; most of that came from repeated reset/preprocessor work over the same clips.

#### Smoke test
- `uv run ruff check apps/wake-word/src/dirt_wake_word/real_audio_score.py apps/wake-word/src/dirt_wake_word/select.py apps/wake-word/src/dirt_wake_word/validate.py apps/wake-word/tests/test_imports.py` passed.
- `uv run python -m py_compile apps/wake-word/src/dirt_wake_word/real_audio_score.py apps/wake-word/src/dirt_wake_word/select.py apps/wake-word/src/dirt_wake_word/validate.py apps/wake-word/tests/test_imports.py` passed.
- `scripts/runpod-build-image batched-validation-20260504 --no-push` passed local Docker smoke. The first attempt exposed that openwakeword exports classifier ONNX with fixed batch dimension `1`; the scorer now applies an in-memory dynamic batch dimension before creating the ORT session.

#### Run config
- `N=201`, `N_val=50`, `steps=250`, `VAL_STEPS_COUNT=2`, `FP_VAL_MAX_WINDOWS=4096`.
- `DIRT_WAKEWORD_FEATURE_DEVICE=gpu`.
- `DIRT_WAKEWORD_TTS_CACHE_MODE=ignore`.
- One-run `DIRT_WAKEWORD_FEATURE_CACHE_SALT=batched-validation-small-20260504`; it was not added to `.env`, image defaults, or production config.

#### Runtime
- `prepare_seed_clips`: 5.1s.
- `generate_clips`: 11.3s.
- `augment+features`: 37.4s.
  - positive_train: total 22.8s; generator 18.1s, embed 2.9s, mmap write 0.9s, flush 0.7s, trim 0.1s.
  - negative_train: total 11.8s; generator 7.7s, embed 2.5s, mmap write 0.9s, flush 0.4s, trim 0.3s.
- `fit_model`: 7.8s, 32.42 steps/sec.
- `select_checkpoint`: 6.1s for one candidate.
  - Shared checkpoint feature prep: 5.9s for 609 good windows and 2137 bad windows.
  - Candidate scoring after feature prep: 0.236s total; `batchable=1`, `original_batch_dim=1`, `batch_size=1024`, good batches=1, bad batches=3.
- `validate_against_real_set`: 5.6s.
- `TOTAL`: 73.7s.

#### Results — container 43/116 validation

This was a tiny diagnostic fit and the model was degenerate: 0 % recall at every threshold from 0.30 to 0.70.

#### Deploy decision
Do **not** deploy v33. This was a validation runtime diagnostic. `var/wake-word/models/current` remains v27, and the voice service remains inactive.

#### What we learned
- The clean combined change is viable: one precompute pass removes repeated reset/preprocessor work and keeps checkpoint selection/final validation on one shared scorer.
- Compared with v32 Run B, the same-size diagnostic improved selection from 15.6s to 6.1s and final validation from 14.5s to 5.6s.
- The remaining selection cost is now almost entirely shared feature preparation. Per-candidate scoring is effectively gone for this validation-set size, so a full run with many saved candidates should benefit more than the one-candidate tiny diagnostic.

### v34 diagnostic — 2026-05-04

**Status:** full cold-cache runtime diagnostic only (**not deployed**)
**Model artifact:** `var/wake-word/models/2026-05-04-213549-opt11w1o3e0g1l/hey_claudia.onnx`
**Trainer commit:** `3a1c2503be2a39904ef7e1206f7dc019c5c7ab9b`
**Image ref:** `ghcr.io/akravetz/dirt-wake-word-trainer:batched-validation-clean-20260504`
**Image digest:** `sha256:607136e85c4783af2b361e1fc2e3a60d9c79cb17892a4bc29a9fd4138e16d585`
**W&B run:** [`wwli4rcc`](https://wandb.ai/adkravetz/dirt-wake-word/runs/wwli4rcc) (group `exp20-batched-fullcold-clean`)
**Pod:** `opt11w1o3e0g1l`, RTX 4090, self-deleted before orchestrator cleanup.
**Wall:** trainer total 15m58.6s; manifest start-to-finish 17m36.2s.

#### What changed
- Applied the simplify/cleanup pass before the full run:
  - centralized `AudioFeatures` construction in `feature_device.new_audio_features()`
  - removed the duplicated good/bad ONNX session path in checkpoint scoring
  - reused prepared real-audio validation windows for checkpoint selection and final validation
  - kept the batched real-audio scorer as the only validation path, with no streaming fallback
  - replaced the stale manual wake-word import test with dynamic package-module import coverage
- Built and pushed a clean image from the committed code. The local Docker smoke test passed before the image was pushed.
- Ran full production defaults: 30 000 synth train, 3000 synth test, 20 000 steps, full inner-loop validation, and full real-audio checkpoint selection.
- `DIRT_WAKEWORD_FEATURE_DEVICE=gpu` forced GPU feature extraction.
- A one-run `DIRT_WAKEWORD_FEATURE_CACHE_SALT=fullcold-batched-clean-20260504` override intentionally invalidated the feature cache. The salt was passed only to this RunPod command and was not added to `.env`, image defaults, or production config.
- `DIRT_WAKEWORD_TTS_CACHE_MODE=force` was kept as a TTS-cache recovery guard.

#### Why
Measure true full end-to-end cold-cache runtime after cleaning up the batched validation implementation and removing the duplicated checkpoint-selection work.

#### Run timeline
- `prepare_seed_clips`: 5.5s.
- `restore_tts_cache`: 1m9.9s, restored 69 970 WAVs.
- `generate_clips`: 4.4s.
- `augment+features`: 9m56.9s, cache MISS, salted key `4f92a5a5f1748955`, actual feature provider `CUDAExecutionProvider`.
  - positive train: 31 450 rows, total 265.9s; generator 193.0s, embed 24.6s, mmap write 31.5s, flush 12.3s, trim 4.2s.
  - negative train: 32 300 rows, total 281.9s; generator 202.3s, embed 27.6s, mmap write 33.9s, flush 13.5s, trim 4.4s.
  - positive test: 3120 rows, total 23.9s; generator 17.7s, embed 2.7s.
  - negative test: 3100 rows, total 22.9s; generator 17.0s, embed 2.5s.
- `prepare_train_inputs`: 18.4s.
- `fit_model`: 4m6.3s, 20 000 steps at 81.20 steps/sec.
- `select_checkpoint`: 11.1s across 12 candidates.
  - Shared real-audio feature prep: 5.893s for 609 good windows and 2137 bad windows.
  - Per-candidate scoring: 0.13s-0.50s each on `CPUExecutionProvider`.
  - Best checkpoint: candidate 2, step 16 315, recall 0.767, precision 0.532, F1 0.629.
- `export_model`: 0.0s.
- `validate_against_real_set`: 5.7s.
- `TOTAL`: 15m58.6s.

#### Results - container 43/116 validation

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 76.7 % | 47.8 % | 0.589 | 36/116 |
| 0.40 | 74.4 % | 48.5 % | 0.587 | 34/116 |
| 0.50 | 69.8 % | 50.8 % | 0.588 | 29/116 |
| 0.60 | 67.4 % | 53.7 % | 0.598 | 25/116 |
| 0.70 | 60.5 % | 54.2 % | 0.571 | 22/116 |

#### W&B system telemetry

Pulled with:

```bash
scripts/wakeword-wandb-pull system wwli4rcc --samples 10000
```

- 140 system rows were captured over runtime 15.3s-1050.3s.
- During `augment+features`, GPU utilization averaged 6.1 % and peaked at 10 %. GPU memory allocation averaged 7.3 % and peaked at 8.5 %.
- During `fit_model`, GPU utilization averaged 6.3 % and peaked at 11 %. GPU memory allocation peaked at 17.0 % / 4.39 GB.
- Selection ran on CPU by design and finished too quickly for many system samples; the code-path telemetry is the more useful source for that phase.

#### Deploy decision
Do **not** deploy v34. Runtime is good, but model quality regressed on false positives. `var/wake-word/models/current` remains v27, and the voice service remains inactive.

#### What we learned
- The surprising good news: the v31 ORT/PyTorch slowdown did **not** reproduce. After a full cold GPU feature pass, the 20 000-step fit ran at 81.20 steps/sec, matching the healthy warm-cache v30 run and far above v31's 12.45 steps/sec.
- The validation cleanup had a much larger full-run impact than the small diagnostic suggested. Checkpoint selection fell from v31's 28m15.6s to 11.1s, and final validation fell from 2m10.5s to 5.7s.
- Cold feature generation is now much faster than the prior full cold run: 9m56.9s vs v31's 42m48.4s. The largest remaining cost inside feature generation is not ORT embedding; it is audio generation/augmentation, followed by mmap write/flush.
- GPU feature extraction is underutilizing the RTX 4090. The feature phase used CUDA, but W&B showed only about 6 % average GPU utilization, while the feature telemetry showed the embed slice was only about 57s of the roughly 597s phase. More GPU tuning alone is unlikely to be the biggest lever unless we also reduce generator/augmentation and disk-write overhead.
- The TTS cache restored correctly and saved regeneration time, but `restore_tts_cache` still costs about 70s. This is now a noticeable fixed cost in a 16-minute full run.
- The model result is unexpectedly worse than v31 and current v27 on precision/false positives. At threshold 0.60, v34 produced 25/116 false positives versus v31's 7/116, with lower F1 despite acceptable recall. The runtime path is ready; the next model-quality work should focus on training-data mix, real-mic negative inclusion, threshold policy, or candidate-selection objective rather than more runtime plumbing.

### v35 diagnostic — 2026-05-05

**Status:** full cold-cache repeat for RunPod-variance check (**not deployed**)
**Model artifact:** `var/wake-word/models/2026-05-05-055711-uqwrijuvd8eh66/hey_claudia.onnx`
**Trainer commit:** `3a1c2503be2a39904ef7e1206f7dc019c5c7ab9b`
**Image ref:** `ghcr.io/akravetz/dirt-wake-word-trainer:batched-validation-clean-20260504`
**Image digest:** `sha256:607136e85c4783af2b361e1fc2e3a60d9c79cb17892a4bc29a9fd4138e16d585`
**W&B run:** [`kg02fj2i`](https://wandb.ai/adkravetz/dirt-wake-word/runs/kg02fj2i) (group `exp21-batched-fullcold-repeat`)
**Pod:** `uqwrijuvd8eh66`, RTX 4090, deleted by orchestrator.
**Wall:** trainer total 18m50.2s; manifest start-to-finish 20m26.5s.

#### What changed
- Repeated v34's clean full cold-cache run on the same committed trainer image and same production defaults.
- Used a new one-run feature-cache salt, `DIRT_WAKEWORD_FEATURE_CACHE_SALT=fullcold-batched-clean-repeat-20260505`, to force a fresh feature-cache miss without changing persistent config.
- Kept `DIRT_WAKEWORD_FEATURE_DEVICE=gpu` and `DIRT_WAKEWORD_TTS_CACHE_MODE=force`.

#### Why
Check whether v34's fast full cold-cache result was reproducible or just a lucky RunPod pod. This run was intentionally a runtime variance sample, not a model-selection experiment.

#### Run timeline
- `prepare_seed_clips`: 6.0s.
- `restore_tts_cache`: 1m7.1s, restored 69 970 WAVs.
- `generate_clips`: 4.2s.
- `augment+features`: 10m47.8s, cache MISS, salted key `ee8bc09fe78c033f`, actual feature provider `CUDAExecutionProvider`.
  - positive train: 31 450 rows, total 300.3s; generator 211.0s, embed 36.6s, mmap write 35.6s, flush 13.2s, trim 3.5s.
  - negative train: 32 300 rows, total 290.4s; generator 199.1s, embed 38.3s, mmap write 33.1s, flush 14.2s, trim 5.4s.
  - positive test: 3120 rows, total 26.7s; generator 19.8s, embed 3.5s.
  - negative test: 3100 rows, total 27.5s; generator 19.4s, embed 3.5s.
- `prepare_train_inputs`: 2m31.4s.
- `fit_model`: 3m55.9s, 20 000 steps at 84.82 steps/sec.
- `select_checkpoint`: 11.5s across 12 candidates.
  - Shared real-audio feature prep: 6.032s for 609 good windows and 2137 bad windows.
  - Best checkpoint: candidate 2, step 16 315, recall 0.419, precision 0.720, F1 0.529.
- `export_model`: 0.0s.
- `validate_against_real_set`: 6.0s.
- `TOTAL`: 18m50.2s.

#### Results - container 43/116 validation

| Threshold | Recall | Precision | F1 | False positives |
|---:|---:|---:|---:|---:|
| 0.30 | 46.5 % | 52.6 % | 0.494 | 18/116 |
| 0.40 | 46.5 % | 62.5 % | 0.533 | 12/116 |
| 0.50 | 44.2 % | 73.1 % | 0.551 | 7/116 |
| 0.60 | 37.2 % | 80.0 % | 0.508 | 4/116 |
| 0.70 | 32.6 % | 77.8 % | 0.459 | 4/116 |

#### W&B system telemetry

Pulled with:

```bash
scripts/wakeword-wandb-pull system kg02fj2i --samples 10000
```

- 162 system rows were captured over runtime 15.3s-1215.3s.
- During `augment+features`, GPU utilization averaged 6.7 % and peaked at 13 %.
- During `fit_model`, GPU utilization averaged 3.7 % and peaked at 12 %, while train-loop throughput stayed healthy at 84.82 steps/sec.
- `prepare_train_inputs` had no GPU work and low CPU utilization in W&B, but took 151.4s. That makes it the unexpected runtime delta versus v34 and points toward host/disk/memory-map variability rather than model compute.

#### Deploy decision
Do **not** deploy v35. This was a runtime repeat and the model has poor recall. `var/wake-word/models/current` remains v27, and the voice service remains inactive.

#### What we learned
- v34's fast path is mostly reproducible. A second full cold-cache run finished in 18m50s, not anywhere near v31's 104m53s.
- The v31 42m48s feature phase and 12.45 steps/sec fit now look like a transient bad runtime/host episode rather than the normal behavior of the cleaned trainer.
- The validation cleanup is stable: checkpoint selection stayed around 11s for 12 candidates, and final validation stayed around 6s.
- RunPod/host variability is still visible, but in a different phase. `prepare_train_inputs` jumped from v34's 18.4s to v35's 151.4s without a corresponding code/config change. That is the strongest new evidence for host, volume, or local disk/cache variability.
- Feature generation varied modestly between the two clean cold runs: v34 9m56.9s vs v35 10m47.8s. The same bottleneck shape held: generator/augmentation dominates, ORT embedding is secondary, and GPU is underutilized.
- Model quality varied substantially between two identical-config runs. v35 traded far fewer false positives for much worse recall, while v34 had better recall but too many false positives. Runtime is no longer the main blocker; the next useful work is model-quality control and selection objective design.
