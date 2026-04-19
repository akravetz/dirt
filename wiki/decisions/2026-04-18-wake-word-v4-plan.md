---
title: "Wake-Word v4 Plan — Precision-focused retraining"
type: decision
sources: []
related: [wiki/decisions/2026-04-16-wake-word-training-strategy.md, wiki/concepts/wake-word-detection.md, wiki/hardware/voice-channel.md]
created: 2026-04-18
updated: 2026-04-18
---

# Wake-Word v4 Plan — Precision-focused retraining

Successor to [v3 training strategy (2026-04-16)](2026-04-16-wake-word-training-strategy.md). v3 solved the recall problem; v4 focuses on precision (fewer false positives) while nudging recall up for far-field positions we hadn't exercised.

## Motivating failure modes

v3 shipped at 89% recall / 0.95–0.99 confidence on clean hits. Observed in the wild since deployment:

- **Meeting false positive** (2026-04-18, conversation id `9a79c60…` era). Zoom-audio phrase scored 0.74 — well above the original 0.35 threshold and even the tightened 0.6 — opened a conversation during a real meeting, Claudia interjected ~8 times before the user could stop the service. Evidence in `wiki/hardware/voice-channel.md` "Deferred Enhancements" and `sessions/voice/2026-04-18.jsonl`.
- **Ambiguous-zone misses** (2026-04-18 15:43+). Three successive "hey Claudia" attempts from a position further than anywhere v3 was trained on. Scores landed at 0.48 and 0.49 (below the 0.6 threshold but well above the 0.1 near-miss floor) — legitimate wakes the model was uncertain about. Captured in `logs/wake_scores/*.jsonl`.

Both failure modes trace to the same root: v3's negatives were generic LibriTTS cross-speaker speech, which gave the model no exposure to meeting acoustics, TV/media audio, or phonetically-neighboring utterances in the user's own environment. Adding more RIRs alone (the obvious "more recall" fix) would worsen precision.

## v4 strategy

Four data-side moves, ordered cheapest-first. All feed into one retraining run using the same `openwakeword/train.py` pipeline v3 used.

### 1. In-situ hard-negative harvesting (AUTO, STARTED 2026-04-18)

`src/dirt/channels/voice.py:wait_for_wake` now keeps a ~1.9 s ring buffer of wake-mic audio and dumps a WAV on every event:

- `<ts>_wake_score-N.NNN.wav` — on real wakes. Positive training examples from the actual deployment environment.
- `<ts>_near_miss_score-N.NNN.wav` — on scores in the ambiguous zone (`WAKE_AUDIO_CAPTURE_FLOOR = 0.3`). Each of these is either a real wake the model wasn't confident about (positive to add) or a false-positive-to-be (negative to add), distinguished by whether a conversation actually followed in `sessions/voice/*.jsonl`.

Lands in `logs/wake_audio/`. **Intentionally not auto-rotated** — we want to accumulate for weeks. Ops must clean this directory manually when we harvest.

After ~1–2 weeks of normal use, expect 100–500 files. Triage workflow: listen to each, file into `debug/wake_word_v4/positives/` or `debug/wake_word_v4/hard_negatives/`, discard ambient noise.

### 2. Mine meeting audio for phonetic-neighbor negatives

User has both meeting recordings and transcripts. Plan:

1. Convert each meeting recording to 16 kHz mono WAV: `ffmpeg -i meeting.mp4 -ac 1 -ar 16000 meeting.wav`.
2. Parse the transcript for phonetic neighbors of "hey Claudia": `hey`, `claudio`, `hey there`, `hey dad`, `okay`, `wait`, `claudia` (without `hey`), plus any token the transcript shows the meeting running through. Use timestamps to cut a 1.5–2 s audio window around each hit.
3. Drop the neighbor clips into `debug/wake_word_v4/hard_negatives/phonetic/`.
4. Drop the full-meeting audio (with phonetic-neighbor clips already extracted) into `debug/wake_word_v4/hard_negatives/meetings_full/` as ambient-meeting-audio negatives.

Mined phonetic-neighbor clips are 10× more training-value per second than raw meeting ambience — they're exactly where the model's decision boundary is weakest.

### 3. Synthesize additional phonetic-neighbor negatives

Using the existing ElevenLabs voice clone (`mjXJZpUEgv69eq6xrhlW`, see v3 decision), synthesize 50–100 samples each of:

- `hey` (solo, varied intonation)
- `claudia` (no leading `hey`)
- `hey Claude` / `hey Clyde` / `hey Claudio`
- `okay` / `wait` / `see` / `be`

Same 5 TTS presets v3 used. Total cost ~$2 of ElevenLabs credits. Output into `debug/wake_word_v4/hard_negatives/synthetic_neighbors/`.

These complement the mined meeting negatives (real acoustics) with synthetic negatives (clean signal, high phonetic density). Both classes contribute.

### 4. Additional RIRs from new operating positions

During v4 testing we identified far-field positions not covered by v3's 9 RIRs — notably *beyond* the `tent_far` position. Capture 2–3 more using the existing scripts:

- `debug/capture_rir_record.py` (Jabra host)
- `debug/capture_rir_play.py` (laptop)

Add to the RIR set that training augmentation consumes. Target SNR still ≥ 25 dB, aim for 65+ dB as v3 achieved.

### 5. (Deferred) Real-mic recordings through Jabra

v3 deferred this. Still deferred. Capturing 20–50 actual "hey Claudia" utterances through the Jabra at varied positions is the single highest-value recall move but also the most labor. If v4 still misses at far-field after the above four moves, escalate here.

## Training config changes

Same `openwakeword/train.py` pipeline as v3. Changes:

- `negative_paths` / `background_paths` — add `debug/wake_word_v4/hard_negatives/` (all three sub-folders: `phonetic/`, `meetings_full/`, `synthetic_neighbors/`).
- `positive_paths` — add `debug/wake_word_v4/positives/` (harvested from deployment + any real-mic recordings we end up capturing). Continue generating fresh ElevenLabs clones if we want a bigger positive pool.
- `rir_paths` — extend with new captures from step 4.
- **`max_negative_weight`: 500 → 800**. v3 dropped this to 500 for recall, at the cost of pushing validation FP/hour from 1.3 to 6.6. With representative negatives now in the mix, pushing it back up should improve precision without sacrificing the recall gains — because the model now has genuine examples of "not-a-wake" rather than relying on generic speech.
- `target_recall` — stays at 0.85.
- Training steps — match v3 (20k) as baseline; rerun at 30k if v4 first pass looks promising but not there yet.

## Runtime mitigations (no retraining)

If v4 retraining schedule slips or falls short, two runtime-only options for additional precision:

- **Double-hit confirmation.** Require two wake fires within ~2 s before actually opening the pipeline. Cuts FP rate roughly quadratically (two independent FPs in 2 s ≈ FP² of single). Cost: ~1 s extra on the first wake, which the user will notice. Configurable.
- **Tiny speaker verifier (second stage).** Train or use an off-the-shelf speaker-embedding model (ECAPA-TDNN, ~1 MB). On each wake fire, compute cosine similarity between the audio window and an enrolled embedding of the user's real voice saying "hey Claudia". Reject if below threshold. Blocks any non-user voice from waking — ideal for meetings where the FP came from the other end of a call. Biggest implementation lift of the precision options.

Neither of these requires a retraining cycle; both can layer on top of v3 today or v4 when it ships.

## Execution sequence (when resumed)

1. Let `logs/wake_audio/` accumulate for 1–2 weeks of normal use. ✅ infrastructure live as of 2026-04-18.
2. Triage accumulated clips into positives / negatives.
3. Convert meeting audio, mine transcripts for phonetic neighbors, slice clips.
4. Synthesize phonetic-neighbor samples via ElevenLabs.
5. Capture 2–3 new far-field RIRs.
6. Retrain in Colab with expanded negatives + `max_negative_weight=800`.
7. Swap `debug/hey_claudia.onnx` → v4, restart service, run `debug/wake_word_test.py` at close / far / meeting-ambient-background conditions.

## Success criteria

- False-accept rate during continuous meeting audio: < 1/hour (v3 produced 1 FP in ~3 hrs of meeting; measured FP-rate needs a longer sample).
- Recall at furthest currently-captured position: ≥ 75% at threshold 0.5.
- No regression vs v3: ≥ 89% recall at normal operating positions at threshold 0.5.

## Status

- [x] Near-miss audio capture shipped — `logs/wake_audio/` accumulating from 2026-04-18.
- [ ] Meeting audio + transcripts staged in `debug/wake_word_v4/`.
- [ ] Phonetic-neighbor synthesis via ElevenLabs.
- [ ] Additional RIRs captured.
- [ ] v4 Colab training run.
- [ ] v4 `.onnx` deployed; before/after metrics on `debug/wake_word_test.py`.
