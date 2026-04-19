---
title: "Wake-Word Training Strategy — Voice Clone + Captured RIRs"
type: decision
sources: []
related: [wiki/decisions/2026-04-16-voice-pipeline-selections.md, wiki/decisions/2026-04-18-wake-word-v4-plan.md, wiki/concepts/wake-word-detection.md, wiki/concepts/room-impulse-response.md, wiki/hardware/jabra.md]
created: 2026-04-16
updated: 2026-04-18
---

# Wake-Word Training Strategy — Voice Clone + Captured RIRs

> **Successor:** [Wake-Word v4 Plan (2026-04-18)](2026-04-18-wake-word-v4-plan.md). v3 shipped and solved recall; v4 targets precision (meeting false positives + ambiguous-zone misses) via in-situ hard negatives, mined meeting audio, and bumped `max_negative_weight`.

## Context

First "hey Claudia" model (trained in Colab with default Piper TTS synthetic samples only) showed unacceptable recall:

| Condition | Recall at threshold 0.5 |
|-----------|------------------------|
| Close range (~2 ft) | 70% |
| Far range (~15 ft) | 40% |

Many far-field utterances registered near zero (<0.05). Threshold tuning can't recover scores that low — it's a training-distribution problem. Deepgram STT run as a control showed acoustic degradation is real (some utterances garbled to "a client" / "pay client") but the wake-word model was blinder than Deepgram, so the model is the tighter bottleneck.

## Options considered

| Option | Verdict |
|--------|---------|
| Lower threshold further | ❌ Doesn't help utterances that score near zero |
| Retrain on default Piper + default MIT RIRs | ❌ Same training distribution; same likely outcome |
| LoRA / fine-tune existing model | ❌ Classifier is ~1k params; no built-in LoRA hook; not worth writing |
| Custom verifier model (Gemini-style 3-sample enrollment) | ❌ Rejected as primary fix — verifier is a precision filter, can't recover missed activations |
| **Retrain with voice-matched + environment-matched data** | ✅ Chosen |

## Decision

Retrain the base wake-word model with:

1. **Voice-clone positive samples** via ElevenLabs cloning of the user's voice
   - Target 2,000+ samples across 4 phrase variants: "hey claudia," "Hey, Claudia," "hey Clowdia," "Hey, Clowdia"
   - Cycled across 5 TTS-setting presets (varied stability, similarity_boost, speed) for acoustic diversity
   - Output format: 16 kHz mono WAV (openWakeWord's native format) via `pcm_16000` ElevenLabs output
   - Script: `debug/elevenlabs_clone_batch.py` (resume-safe: targets are absolute, not deltas)
   - Voice ID: `mjXJZpUEgv69eq6xrhlW` (cloned 2026-04-16)

2. **Captured Room Impulse Responses** from our actual environment
   - 4 positions captured via exponential sine sweep + Farina deconvolution (see `concepts/room-impulse-response.md`)
   - SNR 65–77 dB across all captures (threshold: 25 dB)
   - Replace the default MIT RIR dataset in training config
   - Scripts: `debug/capture_rir_record.py` (Jabra host), `debug/capture_rir_play.py` (laptop)

3. **Colab training** using the existing `openwakeword/train.py` pipeline
   - Pre-populate `positive_train/` with voice-clone samples (Piper generation is automatically skipped once directory is 95% full)
   - Set `rir_paths` to point at the captured IRs
   - Run `--augment_clips` then `--train_model`

## Rationale

- **Recall problem demands distribution matching.** Far-field recall failures trace to training data that doesn't cover (user's voice) × (room acoustics) × (Jabra mic) combined. Voice clone fixes the voice axis; captured RIRs fix the room/Jabra axis.
- **Voice cloning is orders of magnitude cheaper than recording 2k real samples manually** and acoustically close enough to the user that playback is indistinguishable. ElevenLabs `eleven_multilingual_v2` clones are strong.
- **Captured RIRs are uniquely valuable.** No public dataset contains "this laptop → Jabra → this specific house" transfer functions; they have to be measured in-situ.
- **Augmentation multiplies each clean sample.** 2,000 clean × N augmentation rounds × 4 RIRs × varied SNR/noise yields an effective corpus of 10k–40k training examples without additional generation cost.
- **Deferred complications** — tent-fan noise recording for `background_paths`, real-mic voice recordings for acoustic grounding, custom verifier model for speaker-specific precision. Can add if current strategy underperforms.

## Cost

- ElevenLabs: ~24k credits for 2,000-sample batch (12 chars × 2,000 = 24,000). Under $5 at Creator tier.
- Colab: free T4 tier, ~1–2 hrs unattended training time.
- Disk: ~1 GB intermediate artifacts, ~200 KB final model.

## Success criteria

Re-run `debug/wake_word_test.py` at both close and far distances after training. Targets:

- Close range: ≥ 90% recall at threshold 0.5
- Far range: ≥ 70% recall at threshold 0.5
- False-accept rate: < 1/hour in normal household audio

If recall still insufficient, next escalations (ordered): capture more RIRs at additional positions; add tent-fan-noise recordings as `background_paths`; capture real-mic "hey Claudia" positives through the Jabra.

## Status

- [x] Scripts written and validated
- [x] 9 RIRs captured (`loft_primary`, `loft_2`, `mid_loft`, `stairs_top`, `couch`, `couch_far`, `kitchen_far`, `next_to_tent`, `tent_far`), SNR 65–77 dB
- [x] Voice clone created (ElevenLabs ID `mjXJZpUEgv69eq6xrhlW`)
- [x] 2,000 voice-clone samples generated across 4 phrase variants
- [x] Colab training (3 iterations; v3 shipped)
- [x] Real-world test on Jabra — 89% recall at threshold 0.4, confidence 0.95–0.99 on clean hits

## Results (v3, 2026-04-16)

Three training runs:

| Version | Validation accuracy | Validation recall | FP/hour | Notes |
|---------|-------------------|-------------------|---------|-------|
| v1 | — | — | — | Default Piper-only baseline. Real-world: 70% close, 40% far. |
| v2 | 0.849 | 0.700 | ~1.3 | Added voice clones + RIRs + train/test split. Real-world: 71% (5/7). |
| **v3** | **0.890** | **0.794** | 6.64 | Plus `max_negative_weight=500`, `target_recall=0.85`, 20k training steps. Real-world: **89% (8/9)**, peaks consistently 0.95–0.99. |

Key lessons:
- **The train/test split was the biggest lever.** v1 → v2 took validation recall from 11% (measuring cross-speaker generalization on LibriTTS) to 70% (measuring our-voice recall on held-out clones). The initial "low recall" signal in v1 was largely an artifact of distribution mismatch.
- **`max_negative_weight` tunes the precision/recall tradeoff directly.** Dropping it from 1500 to 500 moved real-world recall from 71% → 89% at the cost of pushing validation FP/hour from 1.3 to 6.6 (still unknown how that translates to real household audio).
- **Confidence jumped qualitatively, not just quantitatively.** v3's clean hits land at 0.95–0.99 where v2's topped out around 0.88. This means the runtime threshold has headroom — could be raised to 0.5 or higher to trade a bit of recall for precision without losing most clean fires.

Final model shipped at `debug/hey_claudia.onnx` (~206 KB ONNX). Older versions archived at `hey_claudia_v1.onnx` (Piper-only baseline) and `hey_claudia_v2.onnx` (conservative).
