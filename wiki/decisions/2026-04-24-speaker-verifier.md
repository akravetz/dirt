---
title: "Speaker Verifier — runtime precision filter for meeting FPs"
type: decision
sources: []
related: [wiki/decisions/2026-04-23-wake-word-v5-passive-harvest.md, wiki/decisions/2026-04-18-wake-word-v4-plan.md, wiki/concepts/wake-word-detection.md, wiki/hardware/voice-channel.md]
created: 2026-04-24
updated: 2026-04-24
---

# Speaker Verifier — runtime precision filter for meeting FPs

Parallel work stream to [v5 passive harvest](2026-04-23-wake-word-v5-passive-harvest.md). v5 retrains the base wake model on in-situ negatives; the speaker verifier adds a second stage that rejects anyone whose voice isn't the enrolled user's. The two stack — v5 shrinks the phonetic-neighbor attack surface, the verifier shrinks the speaker-identity attack surface.

## Motivating failure mode

The 2026-04-18 meeting FP (Zoom-audio phrase scored 0.74, Claudia interjected ~8 times) came from **someone else's voice** on the other end of a call. A perfectly-trained wake model can still fire on "hey Claude" / "hey, cloudia" / phonetic neighbors spoken by any voice, because the wake model doesn't condition on speaker identity — it's a phrase detector, not a person detector. Retraining with better negatives is a linear-axis fix; speaker verification is an orthogonal-axis fix.

## How the model works

Speaker embedding networks (ECAPA-TDNN, x-vector, ResNet-variants) are trained on large multi-speaker corpora (VoxCeleb: ~7k speakers, ~1M utterances) with a metric-learning objective: same-speaker clips → embeddings close in cosine space; different-speaker clips → embeddings far apart. Output is a fixed-size vector (192 or 256 dim) that represents "voice identity" — pitch contour, formant spacing, vocal-tract resonances — independent of phrase content.

**Frozen pretrained model, zero custom training.** The "model" the runtime carries is the embedding net's frozen weights plus a single stored vector per enrolled user.

Two phases:

1. **Enrollment (one-time).** User says "hey Claudia" 5× through the Jabra under varied conditions (close, far, morning voice). Each clip → embedding vector. Average the 5 → one ~256-dim "this is Joe" vector. Persist as `var/voice/enrollment.npy`.
2. **Verification (every wake fire).** When openWakeWord fires above `WAKE_THRESHOLD`, take the same ~1.9s ring-buffer audio already captured, run through the embedding net, compute cosine similarity against the enrolled vector. Accept if ≥ `SPEAKER_VERIFY_THRESHOLD` (start at 0.7); reject otherwise.

## Decision

Ship ECAPA-TDNN via [speechbrain](https://github.com/speechbrain/speechbrain) (Apache 2.0) as a second-stage filter in `apps/voice/src/dirt_voice/channels/voice.py:wait_for_wake`.

### Why ECAPA over alternatives

| Option | Verdict |
|---|---|
| **ECAPA-TDNN via speechbrain** | ✅ Chosen. Ships as a single `torch.load`-able checkpoint (~6 MB). One-line load, one-line inference. CPU-only. Industry default. |
| Resemblyzer | ❌ Still solid, but the packaged weights are older (2019) and accuracy lags ECAPA on VoxCeleb by ~2–3%. Lighter runtime (~16 MB model, pure PyTorch) but ECAPA is small enough we don't need to optimize. |
| pyannote.audio | ❌ More capable (diarization, overlap detection) but we don't need any of it and the dep tree is heavier. |
| openWakeWord "custom verifier" | ❌ Naming collision — it's a *logistic regression on top of the wake model's last-layer features*, not a speaker-identity model. Filters on "what does this specific phrase sound like through this user's voice" rather than "whose voice is this." Weaker mechanism for our exact failure mode. |
| Speaker verification via Deepgram / cloud API | ❌ Adds a network round-trip to the wake path. Local CPU inference is ~100ms and free. |

### Why a gate, not a retraining input

Training the wake model with "user voice only" positives doesn't solve the meeting-FP problem — at inference the wake model can still fire on anyone who produces a similar acoustic signature. The verifier is inherently a runtime gate. There's no retraining shortcut.

## Integration

### Runtime — `wait_for_wake`

```python
if score >= WAKE_THRESHOLD and (now - last_fire) >= WAKE_DEBOUNCE_S:
    if not _verify_speaker(recent_frames):
        log_event("wake_scores", "rejected_by_verifier",
                  score=round(score, 4), similarity=round(sim, 4))
        continue  # back to listening
    # ...existing wake-fire path
```

Uses the same `recent_frames` ring buffer the wake model already built. No extra mic capture. Verifier inference happens after the wake fire, so latency is additive only on the rare positive path (~50–150ms on CPU).

Bypass with `DIRT_VOICE_SKIP_VERIFIER=1` for development / harvest mode (harvest mode should pass through without verification — we want to capture everything the wake model fires on regardless of speaker). During v5 passive-harvest, `HARVEST_ONLY=1` short-circuits before the verifier anyway.

### Enrollment script — `debug/enroll_speaker.py`

Prompts the user to say "hey Claudia" 5 times with a 2s gap. Records through the Jabra at 16 kHz. For each clip, extracts the wake-word-shaped window (VAD-trimmed or fixed-length), runs through ECAPA, averages embeddings. Writes `var/voice/enrollment.npy` (shape `(256,)`, dtype float32).

Re-run anytime to re-enroll. Old vector is overwritten.

### Threshold tuning

Start at 0.7 cosine. Tune against two pools after enrollment:

- **Accept pool**: all `wake_score-*.wav` files in `var/logs/wake_audio/` (real wakes from the user during active deployment).
- **Reject pool**: the 2026-04-18 meeting-FP clip and any other non-user voice captured during v5 harvest.

Target operating point: ≤ 2% false reject on the accept pool, 0% false accept on the reject pool. If the pools overlap in similarity space, that's a signal to enroll more clips under varied conditions rather than lower the threshold.

Log every verifier decision to `wake_scores` stream (event `verifier_decision`, fields `score`, `similarity`, `decision`) for ongoing threshold review.

## Tradeoffs

| Aspect | Cost |
|---|---|
| Latency | +50–150ms on wake fire (CPU ECAPA on ~2s audio). User already waits ~200ms for Pipecat spin-up; marginal. |
| Model size | +6 MB on disk (checkpoint), negligible RAM at runtime. |
| Dependencies | `speechbrain` + its transitive PyTorch (already present via other deps — verify on install). |
| Cold-start | Model load is ~500ms on first wake after service start. Amortized across the process lifetime. |
| False-reject cases | Hoarse voice, very far, muffled. Mitigate via varied-condition enrollment. |
| Near-twin voices | Theoretical edge case; threshold tunable. Not a real concern in a single-occupant environment. |

## Execution sequence

1. Add `speechbrain` to `apps/voice` deps (`uv add --package dirt-voice speechbrain`).
2. Write `debug/enroll_speaker.py`. Verify it produces a stable vector across two consecutive enrollments of the same voice (cosine ≥ 0.9 between them).
3. Add `_verify_speaker(frames)` helper in `voice.py` that loads the enrollment vector + ECAPA model on first call (cached module-global) and returns `(passed, similarity)`.
4. Slot into `wait_for_wake` after the `WAKE_THRESHOLD` check, before `return score`.
5. Log `verifier_decision` events to `wake_scores` stream.
6. Tune threshold against the wake_audio/ pool post-v5-harvest (or sooner, using existing v3/v4 captures).
7. Document operational workflow in `wiki/hardware/voice-channel.md`.

## Shipping order vs. v5

**Ship verifier first.** It lets the user re-enable dirt-voice safely *today* without waiting on the v5 harvest → retrain cycle (≥ 2 days harvest + training time). The meeting-FP root cause (other speakers) is addressed immediately at the runtime layer. v5 retraining continues in parallel and improves the base model's precision; the two are multiplicative, not either/or.

## Success criteria

- False-accept rate on 2026-04-18 meeting audio: **0/hour** (the canonical failure case).
- False-reject rate on user's real wakes (measured against `wake_score-*.wav` pool): < 2%.
- Enrollment reproducibility: two consecutive enrollments of same user produce vectors with cosine similarity ≥ 0.9.
- Verifier latency: p95 < 200ms on the deployment host.

## Status

- [ ] `speechbrain` added to `apps/voice` deps.
- [ ] `debug/enroll_speaker.py` written + stability verified.
- [ ] `_verify_speaker` integrated in `voice.py`.
- [ ] `verifier_decision` logging live.
- [ ] Threshold tuned against wake_audio/ pool.
- [ ] Ops runbook appended to `wiki/hardware/voice-channel.md`.
