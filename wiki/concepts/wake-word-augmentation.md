---
title: "Wake-Word Augmentation"
type: concept
sources: []
related: [wiki/concepts/wake-word-detection.md, wiki/concepts/room-impulse-response.md, wiki/wake-word-experiments.md, wiki/decisions/2026-04-16-wake-word-training-strategy.md, wiki/decisions/2026-04-23-wake-word-v5-passive-harvest.md]
created: 2026-05-01
updated: 2026-05-01
---

# Wake-Word Augmentation

Operational note for future wake-word agents: start here before changing real-mic augmentation. The core question is how to make a small number of real Jabra recordings pull more weight without teaching the model unrealistic acoustics.

## Current behavior

As of the v25 analysis, the realmic pool was 82 positives and 112 negatives, and local source buckets are split by meaning:

- `var/wake-word/synth-clones/` — ElevenLabs synthetic "hey Claudia" positives.
- `var/wake-word/realmic-positives/` — reviewed real Jabra "hey Claudia" positives.
- `var/wake-word/synth-neighbors/` — ElevenLabs phonetic-neighbor negatives.
- `var/wake-word/realmic-negatives/` — reviewed real Jabra false fires / near misses.

`apps/wake-word/src/dirt_wake_word/seed.py` seeds all realmic clips into `*_train` only, with `REALMIC_POSITIVE_DUPLICATION = 10` and `REALMIC_NEGATIVE_DUPLICATION = 10`. The `*_test` sets stay synthetic; v21/v22 showed that seeding the tiny realmic set into in-run test selection can pick real-mic-permissive checkpoints that regress precision.

`apps/wake-word/src/dirt_wake_word/augment.py` then splits by filename prefix:

| Source | Current augmentation |
|---|---|
| `synth_clone_*` | Full openWakeWord default: EQ, distortion, pitch shift, band-stop, colored noise, background noise, gain, RIR. |
| `synth_neighbor_*` | Same full synthetic pipeline. |
| `realmic_pos_*` | Gain only. |
| `realmic_neg_*` | Gain only. |

The realmic restriction is intentional. Real Jabra clips already include the deployment mic, room, reverb, and ambient bed. Full synthetic augmentation on top can stack impossible acoustics, especially double-RIR or extra background noise.

Do not augment the canonical validation set. Validation clips should remain raw real examples.

## Recommended experiment backlog

| Option | Apply to | LOE | Expected impact | Notes |
|---|---|---:|---|---|
| Controlled real-room background mixing | Realmic positives only | Medium | Medium/Large recall | Mix reviewed ambient/false-fire room audio under true wake clips at mild SNRs, e.g. 15-30 dB. Keep this positive-only unless explicitly testing another hypothesis. Do not use wake-like speech negatives as generic background. |
| Slightly wider placement jitter | Realmic positives + negatives | Low/Medium | Medium recall, small precision | openWakeWord already pads with 0-200 ms end jitter. A small expansion may help if live detections capture different phrase alignments, but too much can train the wrong window position. |
| Mild speed/tempo perturbation | Realmic positives first | Medium | Medium recall | Start with conservative tempo factors such as 0.95, 1.0, 1.05. Wake-word duration is part of the class shape, so avoid broad ASR-style speed ranges until validated. |
| Feature-domain SpecAugment | Train features, especially positives | Medium/High | Small/Medium recall | Time/frequency masking can regularize, but this phrase is short. Aggressive time masks can erase the wake word itself. Treat as a later A/B, not the first move. |
| Light negative-only augmentation | Realmic negatives | Low/Medium | Medium precision | Keep gain + timing jitter; maybe test very mild EQ/band-limiting. Avoid pitch/speed/RIR/background on negatives by default. |
| ElevenLabs TTS parameter sweep | Synth positives + synth neighbors | Low/Medium | Medium both | Use varied voice settings, seeds, speed, models, and phrasing to enrich synthetic coverage. This helps reduce pressure on the realmic count, but it is not realmic augmentation. |
| ElevenLabs voice changer / speech-to-speech | Experimental realmic-positive variants | Medium/High | Small/uncertain recall | It can preserve timing/delivery while altering voice, but may strip the Jabra/room artifacts we care about. Lower priority than real-room background mixing. |

## First A/B to try

Run a narrow experiment before adding more knobs:

1. Keep validation raw and unchanged.
2. Add a separate realmic-positive augmentation path:
   - gain, as today;
   - mild tempo perturbation;
   - optional real-room background mixing from vetted non-wake ambient clips.
3. Leave realmic negatives conservative: gain plus timing jitter only.
4. Compare against deployed v23 and v25 on:
   - canonical `var/wake-word/validation/{good,bad}/`;
   - held-out realmic positives;
   - production threshold `0.5`.

Deploy only if recall improves without the v25-style precision regression.

## External anchors

- [Speech Commands paper](https://arxiv.org/abs/1804.03209): keyword spotting baselines use time shift and background-noise augmentation.
- [Ko et al. speed perturbation](https://www.isca-archive.org/interspeech_2015/ko15_interspeech.html): classic speech augmentation via slight tempo/speed variation.
- [SpecAugment](https://arxiv.org/abs/1904.08779): feature-domain time/frequency masking for speech robustness.
- [openWakeWord `augment_clips`](https://github.com/dscripka/openWakeWord/blob/main/openwakeword/data.py): current default raw-audio augmentation stack.
- [ElevenLabs text-to-speech docs](https://elevenlabs.io/docs/api-reference/text-to-speech/convert): per-request voice settings, seed, model, and speed are useful for synthetic clone/neighbor diversity.
- [ElevenLabs voice changer docs](https://elevenlabs.io/docs/capabilities/voice-changer): possible speech-to-speech variant generation, but lower confidence for realmic enrichment.
