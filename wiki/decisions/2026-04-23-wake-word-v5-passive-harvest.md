---
title: "Wake-Word v5 Plan — Passive harvest"
type: decision
sources: []
related: [wiki/decisions/2026-04-18-wake-word-v4-plan.md, wiki/decisions/2026-04-16-wake-word-training-strategy.md, wiki/concepts/wake-word-detection.md, wiki/hardware/voice-channel.md]
created: 2026-04-23
updated: 2026-05-07
---

# Wake-Word v5 Plan — Passive harvest

> **Status 2026-05-07:** the passive-harvest method remains useful, but the
> notebook-style training runtime described in the original v5 plan is retired.
> Active training runs use the RunPod Docker trainer and Network Volume flow in
> [`apps/wake-word/RETRAINING.md`](../../apps/wake-word/RETRAINING.md).

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

- ElevenLabs voice-clone positives (2000 currently in `var/wake-word/synth-clones/`; regenerate via `apps/wake-word/data-gen/elevenlabs-clones-batch.py` if the pool needs refreshing).
- `max_negative_weight: 500 → 800 → 3000`. v4 bumped 500 → 800; v5 pushes to **3000** because (a) the deployment is FP-hostile (a false wake interrupts; a false reject just costs a re-say) and (b) openwakeword's auto-train loop will still escalate further if FP/hour stays high. See `apps/voice` precision priorities.
- Same `openwakeword/train.py` family of training logic, now executed through
  the RunPod Docker trainer rather than a notebook runtime.

**Reinstated (was "Dropped" in original v5):**

### Synthetic neighbors — reinstated

Original v5 dropped ElevenLabs phonetic-neighbor synthesis on the theory that passive harvest would supply the same signal in real distribution. Reinstated for two reasons:

1. The harvest hasn't run yet. We need a baseline negative pool to train v5 on *now* — synthetic neighbors fill that role.
2. Synthetic and harvested are **complementary**, not redundant. Synthetic covers phonetically-adjacent phrases the operator might never say in a 2-day window (`hey claire`, `hey clyde`, `hey clay`); harvest covers ambient/meeting/TV cases the operator can't enumerate. Both go into `negative_train/`, separately weighted (see `## Negative-handling architecture` below).

Generated 2026-04-24 via `apps/wake-word/data-gen/elevenlabs-neighbors-batch.py` (sister to `elevenlabs-clones-batch.py`). 360 WAVs in `var/wake-word/neighbors/` covering 7 phrases:

| Phrase | Count | Purpose |
|---|---:|---|
| `hey` | 75 | Decomposition: model must require BOTH halves |
| `claudia` | 75 | Decomposition |
| `hey claire` / `clyde` / `clay` | 50 each | Phoneme-shifted suffix |
| `hey clouds` / `kappa` | 30 each | Distant rhymes (cheap padding) |

> **2026-04-25 update:** `okay claudia` (50) and `play claudia` (30) were initially generated but removed — both share the `claudia` suffix with the wake word and the operator decided firing on those is acceptable (low UX cost). Don't re-add without re-evaluating that call.

Cost: <$1 in ElevenLabs credits. Re-runnable by editing the `PHRASES` list at the top of the script.

**Deferred (optional fallback only):**

- Mining meeting recordings for phonetic-neighbor negatives (v4 §2). If passive volume after 2 days is too low to train on, this is the escape hatch. Caveat: most meeting recordings are direct system audio without room acoustics, so they'd need RIR convolution to match deployment distribution — adding complexity that v5's passive harvest sidesteps by definition.
- Additional far-field RIRs (v4 §4). Orthogonal to the precision problem v5 attacks; revisit only if recall regresses.

## Training runtime

The active retraining path is:

`data-gen -> stage-wakeword-mine -> wakeword-volume-bump -> runpod-train -> validate -> log experiment -> deploy`

See [`apps/wake-word/RETRAINING.md`](../../apps/wake-word/RETRAINING.md) for
the current command sequence. Old local notebook caches and publishing scripts
are obsolete.

## Negative-handling architecture (what we learned wiring this up)

Three things about openwakeword's negative pipeline are non-obvious and worth recording so future agents don't relitigate them:

1. **No config key for user-provided WAVs.** Initial assumption was that `custom_target_phrase_clips` / `custom_negative_phrase_clips` would inject WAVs. Neither key exists. The canonical path is to **pre-populate `<output_dir>/<model_name>/{positive,negative}_{train,test}/`** with WAV files *before* running `--generate_clips`. The script reads `n_current_samples = len(os.listdir(...))` and either skips TTS generation (if ≥ 95% of `n_samples`) or tops up the rest. `prepare_seed_clips()` does this with prefixed filenames.

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

Implemented in the RunPod trainer library. It calls `openwakeword.data.augment_clips` and `compute_features_from_generator` directly with different parameters per subset (full augmentation for `synth_*`, zeroed-out probabilities + empty `background_clip_paths` + empty `RIR_paths` for `harvested_*`), then chains the generators and writes `negative_features_train.npy` itself. This skips the upstream `--augment_clips` path for the cases where per-subset control matters.

Promote when v1 has a baseline confusion matrix to compare against — don't speculate on whether it helps.

## Speaker-verifier as runtime backstop (parallel work item)

A speaker-embedding verifier (ECAPA-TDNN or similar, ~1 MB) on the back end of every wake fire is the cleanest fix for the meeting false-positive class — it rejects any voice that isn't the enrolled user, which is exactly what's happening when other people in a Zoom call trigger a wake. This is **orthogonal** to retraining and worth pursuing in parallel:

- v5 retraining improves the base model's per-utterance precision.
- Speaker verifier improves precision-against-other-speakers regardless of base-model quality.

Not blocked on v5 — can ship before, after, or alongside. Tracked separately so this decision doesn't gate it.

## Status

**Infrastructure — status 2026-05-07:**
- [x] Harvest-only mode implemented in `apps/voice/src/dirt_voice/channels/voice.py` (env var `DIRT_VOICE_HARVEST_ONLY=1`).
- [x] RunPod trainer image and orchestration are the active training path.
- [x] `scripts/stage-wakeword-mine` assembles local source WAVs for the mine dataset.
- [x] `scripts/wakeword-volume-bump` publishes staged datasets directly to the RunPod Network Volume and updates `MANIFEST.json`.
- [x] `apps/wake-word/data-gen/elevenlabs-neighbors-batch.py` — sister to `elevenlabs-clones-batch.py`. 360 phonetic neighbors generated in `var/wake-word/neighbors/`.

**Next agent picks up here:**
- [ ] **Run a 2-day passive harvest window** (operator action). Workflow in `## Operator workflow` above.
- [ ] Add reviewed harvest clips to `var/wake-word/realmic-negatives/`.
- [ ] Run `scripts/stage-wakeword-mine`, then `scripts/wakeword-volume-bump dirt-wakeword-mine var/wake-word/_stage-mine --notes "..."`.
- [ ] Train on RunPod and compare to the prior confusion matrix.
- [ ] v5 `.onnx` deployed; before/after metrics on `apps/wake-word/validation/live-test.py`. Swap into `apps/voice` runtime path; restart `dirt-voice`.
- [ ] (Parallel, not blocking) Speaker-verifier prototype.
