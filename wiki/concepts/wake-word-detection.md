---
title: "Wake-Word Detection"
type: concept
sources: []
related: [wiki/hardware/jabra.md, wiki/concepts/room-impulse-response.md, wiki/decisions/2026-04-16-voice-pipeline-selections.md, wiki/decisions/2026-04-16-wake-word-training-strategy.md, wiki/decisions/2026-04-18-wake-word-v4-plan.md, wiki/decisions/2026-04-23-wake-word-v5-passive-harvest.md]
created: 2026-04-16
updated: 2026-04-23
---

# Wake-Word Detection

A wake word is a short phrase ("hey Claudia," "Alexa," "OK Google") that gates the start of a voice interaction. An always-on detector runs on raw mic audio at near-zero CPU/cost and only activates the expensive downstream pipeline (STT → LLM → TTS) after a trigger fires.

In this project: [openWakeWord](https://github.com/dscripka/openWakeWord) (Apache 2.0) runs on the Jabra mic stream. When it fires, the harness opens a Deepgram STT websocket. See the [voice pipeline decision](../decisions/2026-04-16-voice-pipeline-selections.md).

## How openWakeWord actually works

Internally the model is a three-stage pipeline:

1. **Melspectrogram** — each 80ms audio chunk → a 32×96 mel-frequency feature matrix. Standard speech front-end.
2. **Speech embedding** — the melspec passes through a pre-trained Google `speech_embedding` network producing a small feature vector per frame. This is a frozen, speaker-invariant model that captures phonetic content generically.
3. **Wake-word classifier** — a tiny fully-connected network (`layer_dim=32`, ~1k parameters) outputs a score ∈ [0, 1]. This is the ONLY part that's custom-trained per wake word.

The combination is what makes the approach work: the pretrained embedding does the hard generalization, the tiny classifier only has to learn "what does the embedding look like when any voice says the target phrase."

## Synthetic training data (the default)

Because the embedding is speaker-invariant, you don't need recordings of YOUR voice to train the classifier at all. The default Colab pipeline uses [Piper TTS](https://github.com/rhasspy/piper-sample-generator) with LibriTTS speaker embeddings to generate tens of thousands of synthetic "hey Claudia" samples, all with different voices, pacing, and cadence.

Works surprisingly well — but with caveats:

- **Speaker distribution matters.** LibriTTS skews one way; your voice may not match.
- **Acoustic path matters.** Synthetic clips are close-mic and clean. A real deployment has a room, a mic, and noise — none of that is in the synthetic training distribution.

## The far-field FRR problem (what we hit)

First "hey claudia" model trained in Colab with the default Piper-only recipe, tested via `apps/wake-word/validation/live-test.py`:

| Condition | Recall at threshold 0.5 |
|-----------|------------------------|
| Close range (~2 ft) | 70% |
| Close range, threshold 0.4 | 80% |
| Far range (~15 ft across room) | 40% |

At a distance, many "hey Claudia" utterances scored near zero (<0.05) — the model simply didn't register them. Threshold tuning can't fix scores that low; it's a **training-data-coverage problem**, not a threshold problem.

Control check: ran Deepgram Nova-3 from the same far spot. About half the utterances came back garbled ("a client," "pay client") — acoustic path degradation is real. But the wake-word model missed utterances that Deepgram got crisply, meaning the model is the tighter bottleneck.

Frame behavior: a single utterance produces a **burst of 3–5 consecutive frames** scoring above threshold (spans 240–400ms). Production code needs a ~500ms cooldown to avoid multiple firings per utterance. Separation between "clear signal" and "noise floor" is huge — roughly 3 orders of magnitude (~0.9 vs ~0.001). When the model fires it's confident; when it misses, it's oblivious.

## Fix: retrain with voice-matched + environment-matched data

Instead of retraining from scratch on generic data, inject:

- **Voice-clone samples** — ElevenLabs voice clone of the actual user, generating hundreds/thousands of "hey Claudia" samples across varied TTS stability/similarity/speed settings for acoustic diversity
- **Captured room impulse responses** — measure the real laptop-speaker-to-Jabra-mic acoustic chain at several positions (see `room-impulse-response.md`), use as augmentation RIRs in place of the generic MIT dataset
- **Optional: real mic recordings** — captured utterances through the Jabra for acoustic grounding
- **Optional: real background noise recordings** — tent fans / HVAC / ambient sound as `background_paths` in the training config

The training pipeline then:

1. Checks `positive_train/` — if pre-populated with your clips, Piper generation is skipped (the `n_current_samples <= 0.95 * config["n_samples"]` guard in `train.py:675`)
2. Augments each clean sample: convolves with a random RIR + mixes with a random background clip at a random SNR + optional generated noise
3. Trains the classifier on the augmented features

`augmentation_rounds` in the config controls how many times each clean sample is reused with fresh random augmentation. A value of 5 turns 2,000 clean samples into 10,000 effective training examples.

## Alternative: custom verifier models

openWakeWord ships a "custom verifier" feature — a logistic regression trained on top of the base model using just 3+ recordings of the target speaker. It's fast (<1 min to train), tiny, and can dramatically reduce false-accepts. Conceptually similar to Gemini's "say it 3 times to enroll" pattern.

Catch: it's a **filter on top of the base model** — only invoked when the base model fires above some low threshold (e.g. 0.3). It can only REJECT activations, never create them. For a far-field recall problem where the base model scores 0.04, the verifier is never called. So it fixes precision, not recall.

Worth keeping in the back pocket as a per-user enrollment pattern once the base model is strong. See `docs/custom_verifier_models.md` in the openWakeWord repo.

## Tuning the threshold

Defaults to 0.5 in openWakeWord; we're using 0.4 because of the giant signal/noise separation observed in practice. The right choice is recall-vs-precision tradeoff on top of the base model's quality:

- Lower threshold → catches borderline utterances but invites false-accepts
- Higher threshold → misses borderline but rock-solid against noise

Diagnostic protocol: run `apps/wake-word/validation/live-test.py` with `LOG_FLOOR=0.02` and no cooldown. Log every frame scoring above floor. Say the wake word ~10 times; look at the distribution of peak scores per utterance. Pick a threshold between the 10th-percentile hit score and the max noise score.

## References

- [openWakeWord repo](https://github.com/dscripka/openWakeWord)
- [Custom verifier model docs](https://github.com/dscripka/openWakeWord/blob/main/docs/custom_verifier_models.md)
- [Synthetic data generation rationale](https://github.com/dscripka/openWakeWord/blob/main/docs/synthetic_data_generation.md)
- Pretrained-embedding paper: Lugosch et al. 2019, [Speech Model Pre-training for End-to-End Spoken Language Understanding](https://arxiv.org/abs/1904.03670)
