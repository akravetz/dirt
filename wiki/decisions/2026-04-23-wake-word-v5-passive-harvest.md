---
title: "Wake-Word v5 Plan — Passive harvest + Kaggle training pipeline"
type: decision
sources: []
related: [wiki/decisions/2026-04-18-wake-word-v4-plan.md, wiki/decisions/2026-04-16-wake-word-training-strategy.md, wiki/concepts/wake-word-detection.md, wiki/hardware/voice-channel.md]
created: 2026-04-23
updated: 2026-04-24
---

# Wake-Word v5 Plan — Passive harvest + Kaggle training pipeline

> **Update 2026-04-24:** v5 now has two halves: (1) the *passive harvest* methodology (original v5 thesis, unchanged) and (2) the *Kaggle training pipeline* that replaces the Colab notebook flow used through v3/v4. Pipeline is fully built and waiting on (a) the first harvest window to produce real hard-negatives and (b) one v5 baseline run on the data we already have. Synthetic ElevenLabs phonetic neighbors — originally **dropped** in this plan — are **back in scope** as a baseline negative pool while the harvest accumulates. See `### Synthetic neighbors — reinstated` and `## Kaggle training infrastructure` below.

Successor to [v4 plan (2026-04-18)](2026-04-18-wake-word-v4-plan.md). v4 imagined a triage-heavy capture flow — listen to every clip in `logs/wake_audio/`, file each one as positive or negative. v5 sidesteps that entirely by exploiting a property of the deployment: **if the operator commits to not saying the wake word during a defined window, every above-floor capture from that window is a negative by construction** — no human annotation needed.

## Motivation

v4's hard-negative pipeline assumed manual triage at the back end. In practice that's the bottleneck: the operator has to listen to N WAVs and label each. Worse, the false-positive cases v4 most needs (meeting audio, TV, phonetic neighbors) blend in with ambient noise, making triage slow and error-prone.

If we instead set up a "no-wake-word window" — operator promises not to say "hey Claudia" for ~2 days — every fire above the capture floor is unambiguously a negative. Bulk-label the directory in one operation, no per-file judgment.

## Operator workflow

1. `systemctl --user stop dirt-voice`
2. Set `DIRT_VOICE_HARVEST_ONLY=1` in the service environment (or export before a manual run).
3. `systemctl --user start dirt-voice` — service comes up in passive harvest mode. Startup log line: `Harvest-only mode: wake fires will be captured but no conversation will start. Floor lowered to 0.15.`
4. Use the room normally for ~2 days. Meetings, calls, TV, conversation — all encouraged. Just **do not say "hey Claudia"** (or anything close to it) during the window.
5. After the window: `systemctl --user stop dirt-voice`, unset `DIRT_VOICE_HARVEST_ONLY`, restart.
6. Bulk-move the entire contents of `var/logs/wake_audio/` from the window into `debug/wake_word_v5/hard_negatives/passive/`. Every file is a negative. No triage required.

Sanity check before bulk-labeling: grep `sessions/voice/<window-dates>.jsonl` for any `wake` events with `harvest_only: true` that the operator actually intended (forgot the rule) — those entries should be quarantined out before the bulk move. Expected count: zero or near-zero.

## Behavior changes vs the standard wake-word loop

| Knob | Normal | Harvest-only |
|------|--------|--------------|
| `WAKE_AUDIO_CAPTURE_FLOOR` | 0.3 | 0.15 |
| `WAKE_DEBOUNCE_S` | 3.0 | 5.0 |
| Action on wake fire (score ≥ 0.6) | Open Pipecat conversation | Log + save WAV, return to listening |
| Session-log `wake` event | Same | `harvest_only: true` flag added |

Floor dropped to 0.15 (rationale: with no UX cost to firing, there's no reason to filter borderline scores — a lower floor = more decision-boundary samples, which is exactly what the v5 retraining set wants). Debounce raised to 5 s so a single noisy event doesn't spam the disk with near-duplicate clips.

The harvest-only branch is gated by an env var (`DIRT_VOICE_HARVEST_ONLY=1`) read once at process start in `apps/voice/src/dirt_voice/channels/voice.py`. Restart the service to flip the mode.

## Components from v4 — kept, dropped, deferred

**Kept:**

- ElevenLabs voice-clone positives (2000 currently in `debug/voice_samples/`; regenerate via `debug/elevenlabs_clone_batch.py` if the pool needs refreshing).
- `max_negative_weight: 500 → 800 → 3000`. v4 bumped 500 → 800; v5 pushes to **3000** because (a) the deployment is FP-hostile (a false wake interrupts; a false reject just costs a re-say) and (b) openwakeword's auto-train loop will still escalate further if FP/hour stays high. See `apps/voice` precision priorities.
- Same `openwakeword/train.py` pipeline (same `target_recall: 0.85`, 20k-step baseline). What changed is the *runtime* — see `## Kaggle training infrastructure` below.

**Reinstated (was "Dropped" in original v5):**

### Synthetic neighbors — reinstated

Original v5 dropped ElevenLabs phonetic-neighbor synthesis on the theory that passive harvest would supply the same signal in real distribution. Reinstated for two reasons:

1. The harvest hasn't run yet. We need a baseline negative pool to train v5 on *now* — synthetic neighbors fill that role.
2. Synthetic and harvested are **complementary**, not redundant. Synthetic covers phonetically-adjacent phrases the operator might never say in a 2-day window (`hey claire`, `hey clyde`, `hey clay`); harvest covers ambient/meeting/TV cases the operator can't enumerate. Both go into `negative_train/`, separately weighted (see `## Negative-handling architecture` below).

Generated 2026-04-24 via `scripts/elevenlabs-neighbors-batch.py` (sister to `elevenlabs_clone_batch.py`). 440 WAVs in `var/elevenlabs/voice_samples_neighbors/` covering 9 phrases:

| Phrase | Count | Purpose |
|---|---:|---|
| `hey` | 75 | Decomposition: model must require BOTH halves |
| `claudia` | 75 | Decomposition |
| `okay claudia` | 50 | Prefix swap |
| `play claudia` | 30 | Prefix swap (likely real-life utterance) |
| `hey claire` / `clyde` / `clay` | 50 each | Phoneme-shifted suffix |
| `hey clouds` / `kappa` | 30 each | Distant rhymes (cheap padding) |

Cost: <$1 in ElevenLabs credits. Re-runnable by editing the `PHRASES` list at the top of the script.

**Deferred (optional fallback only):**

- Mining meeting recordings for phonetic-neighbor negatives (v4 §2). If passive volume after 2 days is too low to train on, this is the escape hatch. Caveat: most meeting recordings are direct system audio without room acoustics, so they'd need RIR convolution to match deployment distribution — adding complexity that v5's passive harvest sidesteps by definition.
- Additional far-field RIRs (v4 §4). Orthogonal to the precision problem v5 attacks; revisit only if recall regresses.

## Kaggle training infrastructure

v3 and v4 ran in Google Colab (the `automatic_model_training.ipynb` notebook from openwakeword). v5 moves training to **Kaggle Script Kernels on TPU** for two reasons: (a) Colab has no clean programmatic API — every retraining run required manual UI clicking; (b) Kaggle's free TPU quota (20 hr/week) is more than enough for a single openwakeword run and the whole flow is shell-scriptable.

Operator command: `scripts/kaggle-train` (push kernel, poll status, pull artifacts). One-time setup detail in `training/wake-word-kaggle/README.md`.

### Three Kaggle datasets

All private to the `akravetz` account.

| Dataset | Size | Contents | Refresh cadence |
|---|---:|---|---|
| `akravetz/dirt-wakeword-mine` | ~80 MB | Positives (`voice_samples/`, 2000 ElevenLabs clones), captured RIRs (`rirs/`, 9 WAVs), negatives (`negatives/`, 440 ElevenLabs neighbors as v2; harvested clips will land here as v3+) | Bumped on every harvest cycle (`kaggle datasets version -p ... -m "..."`) |
| `akravetz/dirt-wakeword-bg` | ~265 MB WAV | 500 AudioSet clips + 120 FMA-small clips, all converted to 16 kHz mono PCM. Used for `background_paths` augmentation (mixed *into* training clips, not as standalone negatives). | One-time; re-run `scripts/stage-kaggle-data` only if upstream parquets change |
| `akravetz/dirt-wakeword-features` | ~17 GB `.npy` | Precomputed openwakeword features from `davidscripka/openwakeword_features` HF: `openwakeword_features_ACAV100M_2000_hrs_16bit.npy` (training negatives) + `validation_set_features.npy` (FP-rate validation) | One-time; refresh only if upstream feature schema changes |

### Local staging script: `scripts/stage-kaggle-data`

Idempotent. Downloads + decodes both upstream sources to `/home/akcom/.cache/kaggle-stage/{features,bg}/`, then prints the final `kaggle datasets create` commands. Bypasses the HF `datasets`/`torchcodec` library entirely (5+ failure modes during initial bring-up, all rooted in HF library churn between v3.x → v4.x → torchcodec backend) — instead reads parquet shards directly via `pyarrow` and decodes embedded FLAC/MP3 bytes via `soundfile`. Resilient to upstream layout changes (`agkphysics/AudioSet` switched from `.tar` shards to parquet between v4 and v5; `rudraml/fma` is now a script-only repo and dead in current `datasets`, replaced by `benjamin-paine/free-music-archive-small`).

### Training kernel: `training/wake-word-kaggle/train_hey_claudia.py`

Configured as a Kaggle Script Kernel (`kernel_type: script`, TPU enabled, internet enabled). Auto-runs on `kaggle kernels push`. Steps:

1. `verify_inputs()` — fail-fast if any of the three datasets aren't mounted (saves burning TPU time)
2. `install_dependencies()` — clones `piper-sample-generator` + `openwakeword`, pip-installs the pinned ML stack
3. `build_config()` — generates `my_model.yaml` pointing all paths at `/kaggle/input/...` mounts
4. `prepare_seed_clips()` — copies user WAVs into openwakeword's expected pre-train directories (see `## Negative-handling architecture` for why)
5. `train()` — runs `train.py --generate_clips`, then `--augment_clips`, then `--train_model`
6. `export()` — converts ONNX → tflite, copies both to `/kaggle/working/` for auto-publish

Tunables at the top of the file: `TARGET_WORD`, `NUMBER_OF_EXAMPLES`, `NUMBER_OF_TRAINING_STEPS`, `FALSE_ACTIVATION_PENALTY`, plus three duplication factors (`CLONE_DUPLICATION`, `NEIGHBOR_DUPLICATION`, `HARVESTED_DUPLICATION`).

## Negative-handling architecture (what we learned wiring this up)

Three things about openwakeword's negative pipeline are non-obvious and worth recording so future agents don't relitigate them:

1. **No config key for user-provided WAVs.** Initial assumption (and the way our kernel was first written) was that `custom_target_phrase_clips` / `custom_negative_phrase_clips` would inject WAVs. Neither key exists. The canonical path is to **pre-populate `<output_dir>/<model_name>/{positive,negative}_{train,test}/`** with WAV files *before* running `--generate_clips`. The script reads `n_current_samples = len(os.listdir(...))` and either skips TTS generation (if ≥ 95% of `n_samples`) or tops up the rest. `prepare_seed_clips()` in the kernel does this with prefixed filenames.

2. **Negatives get the same RIR + background augmentation as positives** (`train.py:775-779`). This is fine for synthetic clips (TTS is studio-clean and needs realism) but suboptimal for real-room captures, which already have the room's RIR + ambience baked in. Convolving an already-room-recorded clip with another RIR is physically nonsensical (sound traveling through two rooms in series). For v5, accept this as imperfect; option-2 fork below addresses it cleanly when needed.

3. **No per-sample weighting.** Class-level weighting via `max_negative_weight` (default 1500, v5 bumped to 3000, auto-train loop will double if FP/hr stays high). Per-sample weighting must be done by **duplicating files on disk** — the dataloader reads filenames uniformly, so a clip present N times has N× pull on the loss. There's prior art for this exact hack: `background_paths_duplication_rate` is a YAML key that does it for backgrounds. We use the same trick manually for harvested negatives.

### Naming convention in `negative_train/`

The seed step prefixes filenames so option 2 (below) can split them with a glob:

| Prefix | Source | Duplication factor | Augmentation |
|---|---|---:|---|
| `synth_clone_*` (in `positive_train/`) | ElevenLabs voice clones | 1× | Full (TTS needs RIR + bg) |
| `synth_neighbor_*` | ElevenLabs phonetic neighbors | 1× | Full (same reason) |
| `harvested_*` | Real captures from `var/logs/wake_audio/` (post-harvest) | **10×** | Full *for v1*, can be skipped via option 2 |
| `<uuid>.wav` | TTS-generated by `--generate_clips` (Piper) | 1× | Full |

### Option 2 (per-subset augmentation control) — TODO

Stub at the bottom of `train_hey_claudia.py`. ~30 lines, no openwakeword fork — just calls `openwakeword.data.augment_clips` and `compute_features_from_generator` directly with different parameters per subset (full augmentation for `synth_*`, zeroed-out probabilities + empty `background_clip_paths` + empty `RIR_paths` for `harvested_*`), then chains the generators and writes `negative_features_train.npy` ourselves. Skips the `--augment_clips` step entirely (the script sees the .npy already exists and uses it).

Promote when v1 has a baseline confusion matrix to compare against — don't speculate on whether it helps.

## Speaker-verifier as runtime backstop (parallel work item)

A speaker-embedding verifier (ECAPA-TDNN or similar, ~1 MB) on the back end of every wake fire is the cleanest fix for the meeting false-positive class — it rejects any voice that isn't the enrolled user, which is exactly what's happening when other people in a Zoom call trigger a wake. This is **orthogonal** to retraining and worth pursuing in parallel:

- v5 retraining improves the base model's per-utterance precision.
- Speaker verifier improves precision-against-other-speakers regardless of base-model quality.

Not blocked on v5 — can ship before, after, or alongside. Tracked separately so this decision doesn't gate it.

## Status

**Infrastructure (Kaggle pipeline) — done 2026-04-24:**
- [x] Harvest-only mode implemented in `apps/voice/src/dirt_voice/channels/voice.py` (env var `DIRT_VOICE_HARVEST_ONLY=1`).
- [x] `kaggle` CLI added as workspace dev dep (`uv add --dev kaggle`); auth at `~/.kaggle/kaggle.json` (legacy API key, not the new "Access Token" — the latter doesn't work with the CLI's write endpoints).
- [x] Three Kaggle datasets created and `status: ready`: `akravetz/dirt-wakeword-mine` (v2: positives + RIRs + 440 ElevenLabs phonetic neighbors), `akravetz/dirt-wakeword-bg` (AudioSet+FMA WAVs), `akravetz/dirt-wakeword-features` (17 GB `.npy`s).
- [x] `scripts/stage-kaggle-data` — idempotent local staging via direct parquet read.
- [x] `scripts/kaggle-train` — push + poll + pull wrapper.
- [x] `training/wake-word-kaggle/train_hey_claudia.py` — training kernel with `prepare_seed_clips()` wired (option 1: uniform augmentation + 10× duplication for harvested negatives).
- [x] `scripts/elevenlabs-neighbors-batch.py` — sister to `elevenlabs_clone_batch.py`. 440 phonetic neighbors generated in `var/elevenlabs/voice_samples_neighbors/`.

**Next agent picks up here:**
- [ ] **First v5 Kaggle training run on synthetic-only negatives.** `scripts/kaggle-train`. ~30–60 min on TPU. Pulls `hey_claudia.onnx` + `.tflite` to `training/wake-word-kaggle/artifacts/`. This is the **baseline** — no harvested data yet, but real ElevenLabs neighbors at 1× weight.
- [ ] **Run a 2-day passive harvest window** (operator action). Workflow in `## Operator workflow` above.
- [ ] **Bulk-import the harvest** into the `dirt-wakeword-mine` dataset's `negatives/` folder with `harvested_*.wav` filenames, then `kaggle datasets version -p ... -m "added N harvested negatives from window YYYY-MM-DD"`. The kernel's seed step picks them up automatically and applies 10× duplication.
- [ ] **v5 second training run** on baseline + harvested. Compare to baseline confusion matrix.
- [ ] If real-room negatives' double-RIR problem is empirically hurting (option 2 stub at bottom of `train_hey_claudia.py`): promote the stub to working code.
- [ ] v5 `.onnx` deployed; before/after metrics on `debug/wake_word_test.py`. Swap into `apps/voice` runtime path; restart `dirt-voice`.
- [ ] (Parallel, not blocking) Speaker-verifier prototype.

**Operational gotchas worth a one-liner each:**
- Kaggle dataset titles must be ≤50 chars (we hit this on the bg dataset; first push 400'd silently with no useful error).
- `kaggle datasets create -p . --dir-mode zip` is required if the dataset has subdirectories — default mode skips them with "Skipping folder" warnings *and still creates an empty dataset*.
- The "wake-word" tag is invalid in Kaggle's taxonomy; the CLI silently drops invalid tags. Cosmetic only.
- Cached upstream parquets live at `/home/akcom/.cache/kaggle-stage/parquet-cache/` (not in the upload dirs) so re-runs of `scripts/stage-kaggle-data` are fast.
