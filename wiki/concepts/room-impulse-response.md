---
title: "Room Impulse Response (RIR)"
type: concept
sources: []
related: [wiki/concepts/wake-word-detection.md, wiki/hardware/jabra.md, wiki/decisions/2026-04-16-wake-word-training-strategy.md]
created: 2026-04-16
updated: 2026-04-16
---

# Room Impulse Response (RIR)

An RIR is a recording of how a sound, played at one position, arrives at a mic after bouncing through a room. It's a complete fingerprint of the acoustic channel between source and receiver — room geometry, surface reflectivity, mic coloration, all baked into a single ~1–2 second WAV file.

## What an IR captures

| In the IR | Not in the IR |
|-----------|---------------|
| Direct-path sound | Background noise (fans, HVAC, voices) |
| Reverb tail (first reflections → dense reverberation → decay) | Anything additive and uncorrelated with the source |
| Mic frequency response (the signal DID pass through the mic) | Time-varying effects |
| Distance attenuation (amplitude of direct path vs. tail) | Speaker coloration is a confound during capture |

An IR describes the response of a **linear time-invariant (LTI) system**. If the room is quiet and doesn't change, the IR fully describes the acoustic transformation from source signal to received signal:

```
received_audio = source_audio ⊛ room_ir
```

where ⊛ is convolution. So given an IR, you can take any clean audio and compute what it would have sounded like if played at the source position and recorded at the mic — purely in software, without the actual physical setup.

This is enormous for training audio models: **synthesize acoustic variety by convolving clean data with a library of real IRs** rather than trying to record every condition physically. That's exactly how openWakeWord's augmentation stage uses RIRs.

## Why we care

Audio training pipelines use IRs to teach models robustness to real-world rooms. openWakeWord's augmentation (`openwakeword/data.py`) randomly convolves each clean positive sample with an IR from the `rir_paths` config directory. The default RIR set is MIT's environmental IR collection — concert halls, lecture rooms, stairwells, generic indoor spaces.

By capturing our OWN IRs — laptop-speaker-to-Jabra-mic in our specific physical environment — training data can match deployment conditions far better than any generic collection. The model learns "what a 'hey Claudia' spoken in the loft actually sounds like by the time it reaches the Jabra," instead of "what 'hey Claudia' sounds like in MIT's Kresge Auditorium."

## How to capture one — the exponential sine sweep method

Naively: play a perfect impulse (a click, a clap) and record. The result IS the IR. But real claps are short and noisy, and a single measurement has terrible SNR.

**Farina's exponential sine sweep method** (Farina 2000) is the technique used in pro audio and acoustics:

1. Play a **15-second exponential sine sweep** (a tone that smoothly sweeps ~20 Hz → ~7.8 kHz logarithmically). The audible result is a dramatic "whoop" from deep bass up through high treble.
2. Record it through the mic in question.
3. **Deconvolve** the recording with an inverse filter — mathematically, the time-reversed sweep multiplied by an exponential amplitude envelope that whitens the sweep's spectrum.
4. The deconvolution result IS the impulse response.

The magic: deconvolution concentrates the 15 seconds of sweep energy into a single narrow peak at the direct-path arrival time. Background noise (uncorrelated with the sweep) stays spread out across the full duration of the deconvolution output and ends up far below the IR's peak — typical sweep-based captures hit 40–70 dB SNR even in modestly noisy rooms.

This is WHY sweeps beat impulses: the sweep spreads energy across 15 seconds during capture, then the deconvolution collapses it back to a narrow peak while the noise stays distributed. The signal gains ~12 dB for every doubling of sweep duration.

## The math, briefly

The sweep is `x(t) = sin(2π · f₁ · T/R · (e^(tR/T) − 1))` where `R = ln(f₂/f₁)`. This signal has the property that its spectrum decays at 3 dB/octave (a consequence of the logarithmic sweep spending proportionally more time at low frequencies).

The inverse filter is `x_inv(t) = x(T − t) · e^(−tR/T)` — time-reversed sweep with an exponential amplitude envelope. That envelope whitens the sweep's spectrum so convolution yields a near-ideal Dirac delta (plus the room's response).

`fftconvolve(recording, inverse_filter)` produces the impulse response. The peak of the magnitude locates the direct-path arrival; the samples after the peak are the room's reverb tail.

## Our capture setup

Two-device setup (laptop speaker is across the room from the Jabra, so each host runs its own script):

- **Jabra host** (monitoring machine): `debug/capture_rir_record.py <label>` — records 30–45s through the Jabra, deconvolves, saves IR + raw WAV
- **Laptop** (desk): `debug/capture_rir_play.py` — plays the matching sweep through the laptop speaker at ~80% volume

Both scripts use identical sweep parameters (SAMPLE_RATE, F_START, F_END, SWEEP_DURATION) as module constants so they generate bit-identical sweeps independently — no file sync needed. The recorder's 45s window is deliberately longer than the sweep so there's time to start the player after the recorder.

Output: `debug/rirs/ir/<label>.wav` (the clean IR, for training) and `debug/rirs/raw/<label>.wav` (the unprocessed recording, for re-deconvolution if parameters change).

## Results

Four IRs captured at the most likely wake-word interaction positions:

| Position | SNR | File |
|----------|-----|------|
| `loft_primary` | 65.8 dB | `debug/rirs/ir/loft_primary.wav` |
| `stairs_top` | 69.6 dB | `debug/rirs/ir/stairs_top.wav` |
| `couch` | 67.1 dB | `debug/rirs/ir/couch.wav` |
| `next_to_tent` | 77.3 dB | `debug/rirs/ir/next_to_tent.wav` |

All >25 dB SNR (our target minimum), most well above 60 dB. The close-range `next_to_tent` at 77.3 dB is cleanest because the direct path dominates. Each IR is 1505 ms long (IR_LEAD_MS + IR_KEEP_MS in the recorder), capturing direct path + first reflections + decay.

## Caveats

- **Laptop speaker coloration** — the captured IR includes the laptop speaker's imperfect frequency response, not a flat reference speaker. For wake-word training where phonetic/temporal structure matters more than absolute spectrum, this is tolerable. A near-flat Bluetooth speaker would reduce this confound.
- **Mouth directivity** — a human voice radiates with a direction-dependent pattern (louder forward, quieter behind). A point-source laptop speaker doesn't replicate this. Again, tolerable for wake-word training.
- **Room variability** — furniture moves, doors open, people walk around. The captured IR is a snapshot of a specific moment. Re-capture if the room changes significantly.

## Related concepts

- **Background noise ≠ IR.** Noise is captured separately and mixed with convolved samples at random SNR during augmentation. See `background_paths` in the openWakeWord config.
- **IR duration matters.** Short IRs (tens of ms) capture direct + early reflections. Long IRs (seconds) capture full decay in reverberant spaces. 1.5s is plenty for residential rooms.
- **IR symmetry** — an IR captured at position A with source B is NOT the same as source A receiver B. Each position gets its own IR.

## References

- Farina, A. (2000). "Simultaneous measurement of impulse response and distortion with a swept-sine technique." AES Convention 108.
- [MIT environmental impulse responses](https://huggingface.co/datasets/davidscripka/MIT_environmental_impulse_responses) — the default RIR dataset used by openWakeWord training.
