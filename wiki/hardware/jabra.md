---
title: "Hardware — Jabra Speak 410 (Voice I/O)"
type: hardware
sources: []
related: [wiki/decisions/2026-04-12-audio-hardware-selection.md, wiki/decisions/2026-04-16-voice-pipeline-selections.md, docs/epics/live-audio/README.md, docs/adrs/005-agent-architecture.md]
created: 2026-04-15
updated: 2026-04-16
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
| Wake word | 🔧 Retraining | openWakeWord — custom "hey claudia" model. Initial model had 40% far-field recall; retraining with voice-clone + captured RIRs. See [wake-word-detection concept](../concepts/wake-word-detection.md) and [training strategy decision](../decisions/2026-04-16-wake-word-training-strategy.md). |
| Production voice channel | ❌ Not yet | No `channels/voice.py`, no session logging, no agent integration |
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

- `debug/deepgram_roundtrip.py` — end-to-end STT+TTS pilot (Deepgram Aura-2)
- `debug/elevenlabs_tts.py` — ElevenLabs TTS pilot ("Claudia" voice)
- `debug/jabra.md` — agent handoff: gotchas + production TODO
- `docs/epics/live-audio/README.md` — epic scope
- `wiki/decisions/2026-04-12-audio-hardware-selection.md` — why this device
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
- **Self-hear during playback.** The pilot mutes mic input while TTS plays to avoid transcribing Claude's own voice. A more robust approach would be acoustic echo cancellation (AEC) — the Jabra doesn't provide it; we'd have to add it upstream.
- **Older device, may not receive firmware updates.** The Speak 410 is the oldest Jabra Speak model; Jabra's supported its successors (510/710/810/2510 Speak 2) more actively. Treat the firmware clock-rate workaround as permanent.
