---
title: "Hardware — Jabra Speak 410 (Voice I/O)"
type: hardware
sources: []
related: [wiki/decisions/2026-04-12-audio-hardware-selection.md, wiki/decisions/2026-04-16-voice-pipeline-selections.md, docs/epics/live-audio/README.md, docs/adrs/005-agent-architecture.md, docs/references/pipecat/INDEX.md]
created: 2026-04-15
updated: 2026-04-18
---

# Jabra Speak 410 — Voice I/O

USB-corded conference speakerphone sitting outside the grow tent. Handles both mic capture and speaker playback for the live-voice channel to the agent. Decision rationale in [2026-04-12-audio-hardware-selection.md](../decisions/2026-04-12-audio-hardware-selection.md); architectural role in [ADR 005](../../docs/adrs/005-agent-architecture.md) (parallel to the Telegram bot channel).

## Deployment Status

| Component | Status | Notes |
|-----------|--------|-------|
| Physical device | ✅ Deployed 2026-04-15 | Desk near monitoring host, USB-A to RSHTECH hub |
| Kernel recognition | ✅ Working | `lsusb: 0b0e:0412`, ALSA card 2, serial `6CFBEDE70054x011200` |
| Playback volume | ✅ Set to max (100% / +8dB) | Default shipped at 55% / -12dB. Persist with `sudo alsactl store 2`. |
| STT pipeline | ✅ Pilot proven | `debug/deepgram_roundtrip.py` — Nova-3 streaming from the Jabra mic, transcribes cleanly over tent fan noise |
| TTS pipeline | ✅ Pilot proven | ElevenLabs `eleven_multilingual_v2` via `debug/elevenlabs_tts.py`; "Claudia" voice; +12 dB gain; PCM 48 kHz stereo. Replaces Deepgram Aura-2 from initial pilot. |
| Wake word | ✅ Trained (v3) | openWakeWord "hey claudia" — 89% real-world recall at threshold 0.4 after 3 training iterations. Final model at `var/wake-word/models/current/hey_claudia.onnx`. See [wake-word-detection concept](../concepts/wake-word-detection.md) and [training strategy decision](../decisions/2026-04-16-wake-word-training-strategy.md). |
| Production voice channel | ✅ Deployed 2026-04-18 | `src/dirt/channels/voice.py` running under `dirt-voice.service` (systemd user unit). Pipecat 1.0 pipeline: Deepgram Nova-3 STT → Claude Haiku 4.5 → ElevenLabs turbo_v2_5. Three agent tools (`get_current_status`, `get_sensor_trend`, `ask_wiki`). Session transcripts at `sessions/voice/YYYY-MM-DD.jsonl`. |
| Noise suppression | ❌ Not yet | Jabra has no echo cancellation for sustained fans; RNNoise or similar would help |

## Connection & ALSA Layout

- USB-A via RSHTECH 10-port hub → `/dev/bus/usb` → `snd-usb-audio` → **ALSA card 2**
- sounddevice enumerates it as device index `6` (`Jabra SPEAK 410 USB: Audio (hw:2,0)`)
- Device name by ID: `usb-0b0e_Jabra_SPEAK_410_USB-...`

## The Jabra's Asymmetric Endpoints

From `/proc/asound/card2/stream0`:

```
Playback:  Channels: 2 (FL/FR)   Rates: 8000, 16000, 48000   Format: S16_LE
Capture:   Channels: 1 (MONO)    Rates: 16000 only           Format: S16_LE
```

**The mic and speaker sides have different constraints.** Any voice pipeline has to handle this explicitly — you cannot pick "one sample rate, one channel count" for both.

## Firmware Quirk — Hardware Always Runs at 48 kHz

Documented in [Red Hat Bugzilla #766714](https://bugzilla.redhat.com/show_bug.cgi?id=766714). The Speak 410 advertises 8/16/48 kHz for playback, but its internal hardware clock **always runs at 48 kHz** regardless of what ALSA negotiates. Feeding 16 kHz audio plays at **3× speed** ("chipmunks"). Feeding 8 kHz plays at 6×.

- **Official fix:** Jabra firmware ≥ 1.3.0, flashable only via their Windows-only PC Suite. This host runs Linux; we have not flashed.
- **Practical workaround (what we do):** always resample or generate at **48 kHz** for playback, regardless of what the source rate would prefer.
- **Mic side is unaffected** — the capture endpoint runs mono 16 kHz only, and 16 kHz is what's negotiated, so no mismatch.
- Kernel maintainers refused to patch around this, saying Jabra needs to fix the firmware.

## Playback Is Stereo-Only

The playback endpoint only accepts **2 channels (FL + FR)**. If your source is mono (e.g. any TTS output), duplicate to stereo (`numpy.column_stack([pcm, pcm])` or equivalent) before handing to the device. A raw mono stream gets read as two mono samples per stereo frame, producing exactly 2× speed corruption on top of the 48 kHz firmware bug.

## Volume

Shipped default was `PCM = 6/11` (55%, -12 dB) which was noticeably quiet. Current setting:

```bash
amixer -c 2 sset PCM 100% unmute   # sets to 11/11 = +8 dB
sudo alsactl store 2               # persist across reboots
```

The Jabra exposes exactly two mixer controls: `PCM` (output, 0–11 range, joined mono) and `Mic` (input gain). No separate speaker/master.

## Production Voice Channel

Deployed 2026-04-18 as the `dirt-voice` systemd user service. Holds this device's ALSA handle continuously (wake-word loop) and claims the playback side during conversations.

**Operational spec, architecture, tool list, session log format, and Pipecat version gotchas all live in [`voice-channel.md`](voice-channel.md).** That page is the pipeline; this page is the device.

## Pilot Reference

`debug/deepgram_roundtrip.py` — streams the Jabra mic to Deepgram Nova-3 WebSocket, prints transcripts, and plays back a pre-synthesized Aura-2 response. Runs until Ctrl-C. Used to validate the full audio path end-to-end with fan noise present. See `debug/jabra.md` for gotchas an agent needs to know before productionizing.

`debug/elevenlabs_tts.py` — streams ElevenLabs TTS ("Claudia" voice, `eleven_multilingual_v2`) through the Jabra. PCM at 48 kHz, mono→stereo duplication, +12 dB gain boost. Voice settings: stability=0.55, similarity_boost=1.0, speed=1.08. See [voice pipeline decision](../decisions/2026-04-16-voice-pipeline-selections.md) for rationale.

## Daily-Use Commands

```bash
# Confirm device is connected
lsusb | grep -i jabra

# Check ALSA layout
cat /proc/asound/card2/stream0

# Adjust volume
amixer -c 2 sget PCM          # show current
amixer -c 2 sset PCM 100%     # max
sudo alsactl store 2          # persist
```

## Related Files

### Production code (2026-04-18 onwards)
See [`voice-channel.md`](voice-channel.md) for the full code + service layout.

### Debug scripts (pilot / test)
- `debug/deepgram_roundtrip.py` — STT+TTS pilot (Deepgram Nova-3 + Aura-2)
- `debug/deepgram_transcribe_only.py` — STT-only (no TTS response); used for mic-reach diagnostics
- `debug/elevenlabs_tts.py` — ElevenLabs TTS pilot ("Claudia" persona voice, +12 dB gain)
- `debug/elevenlabs_clone_test.py` — voice-clone smoke test (3 samples, varied settings)
- `apps/wake-word/data-gen/elevenlabs-clones-batch.py` — resume-safe batch voice-clone generator (target-based, not delta-based). Produced the 2,000 training samples.
- `apps/wake-word/validation/live-test.py` — openWakeWord diagnostic: logs every frame above floor with timestamp, no cooldown. Used for recall measurement and threshold tuning.
- `debug/wake_word_response.py` — **full wake→respond demo**: listens for "hey Claudia" via openWakeWord, plays cached ElevenLabs response through Jabra, handles self-hear quench. This is the closest thing to the production voice channel.
- `apps/wake-word/data-gen/capture-rir-record.py` — RIR capture recorder (runs on Jabra host). Records 30-45s sweep window, deconvolves (Farina method), saves IR + raw recording.
- `apps/wake-word/data-gen/capture-rir-play.py` — RIR capture sweep player (runs on laptop at capture position). Identical sweep parameters as recorder — no file sync needed.

### Data artifacts
- `var/wake-word/models/current/hey_claudia.onnx` — **current wake-word model (v3)**: 89% real-world recall at threshold 0.35, peaks 0.95–0.99. Trained on 1500 voice-clone positives + 9 captured RIRs + ACAV100M negatives.
- `var/wake-word/models/2026-04-16-v2/hey_claudia.onnx` — conservative v2 (70% recall). Kept for comparison.
- `var/wake-word/models/2026-04-15-v1/hey_claudia.onnx` — Piper-only baseline (40-70% recall depending on distance). Kept for comparison.
- `var/wake-word/voice-clones/` — 2,000 ElevenLabs voice-clone WAVs (16 kHz mono). 4 phrase variants × 500 each. Training data for wake-word model.
- `var/wake-word/rirs/` — 9 captured room impulse responses (16 kHz mono, 1505ms each, 65–77 dB SNR). Used as augmentation RIRs during training.
- `var/wake-word/rirs-raw/` — raw sweep recordings before deconvolution. For re-processing if needed.
- `debug/openwakeword_src/` — cloned openWakeWord repo (includes `train.py`, `data.py`, `examples/custom_model.yml`)
- `apps/wake-word/reference/automatic_model_training.py` — Colab training notebook exported as Python. Reference for training config and pipeline.

### Architecture / decisions
- `debug/jabra.md` — agent handoff: gotchas + production TODO
- `docs/epics/live-audio/README.md` — epic scope
- `wiki/decisions/2026-04-12-audio-hardware-selection.md` — why this device
- `wiki/decisions/2026-04-16-voice-pipeline-selections.md` — ElevenLabs + openWakeWord + Deepgram chosen
- `wiki/decisions/2026-04-16-wake-word-training-strategy.md` — voice clone + RIR retraining (full results + lessons learned)
- `wiki/concepts/wake-word-detection.md` — how openWakeWord works, training pipeline, threshold tuning
- `wiki/concepts/room-impulse-response.md` — RIR theory, Farina sine sweep method, capture setup
- `docs/adrs/005-agent-architecture.md` — channel adapter pattern (voice parallels Telegram)

## Hardware Specs

| Parameter | Value |
|-----------|-------|
| Model | Jabra Speak 410 |
| USB ID | `0b0e:0412` (GN Netcom) |
| Serial | `6CFBEDE70054x011200` |
| Interface | USB-A, full-speed |
| Mic | Omnidirectional, mono, 16 kHz |
| Speaker | Stereo FL/FR, native 48 kHz clock |
| Physical controls | Volume +/-, mute, call pickup/hangup |
| Indicator LED | Small ring around mute button (can be covered for dark-period) |

## Known Limitations

- **No echo cancellation for sustained fan noise.** Conference-call DSP only kicks in for speech-vs-silence, not speech-vs-broadband. Our tent fans run 24/7. Plan for a software noise suppressor (RNNoise, Krisp) before STT in the production path if Nova-3's built-in noise handling ever proves insufficient — the pilot showed it's adequate for now.
- **Self-hear during playback.** The Jabra's speaker output is picked up by its own mic. Software muting (`playing.set()` flag in the mic callback) prevents wake-word re-triggering during playback. Additionally, an 800ms "tail quench" period after `sd.play()` returns is needed because the speaker keeps emitting briefly after the software reports playback complete, and room reverb takes time to decay. Discovered and solved in `debug/wake_word_response.py`. A more robust long-term approach would be acoustic echo cancellation (AEC) — the Jabra doesn't provide it; we'd have to add it upstream.
- **Older device, may not receive firmware updates.** The Speak 410 is the oldest Jabra Speak model; Jabra's supported its successors (510/710/810/2510 Speak 2) more actively. Treat the firmware clock-rate workaround as permanent.
