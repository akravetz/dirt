---
title: "Voice Pipeline Selections — ElevenLabs TTS + openWakeWord"
type: decision
sources: []
related: [wiki/hardware/jabra.md, docs/epics/live-audio/README.md]
created: 2026-04-16
updated: 2026-04-16
---

# Voice Pipeline Selections — ElevenLabs TTS + openWakeWord

## Context

Building the always-on voice agent for the Jabra Speak 410. Need to choose a TTS provider (replacing Deepgram Aura-2 used in the pilot) and a wake-word engine to gate STT/LLM/TTS costs.

## Decisions

### TTS: ElevenLabs (eleven_multilingual_v2)

**Chosen over** Deepgram Aura-2 (pilot TTS) for voice quality. The voice persona is "Claudia" — bilingual English/Spanish character voice.

| Parameter | Value |
|-----------|-------|
| Provider | ElevenLabs |
| Model | `eleven_multilingual_v2` |
| Voice ID | stored in `ELABS_VOICE_ID` env var |
| Output format | `pcm_48000` (matches Jabra hardware clock) |
| Stability | 0.55 |
| Similarity boost | 1.0 |
| Speed | 1.08 |
| Gain | +12 dB (Jabra speaker is quiet at unity) |

Pilot: `debug/elevenlabs_tts.py` — streams PCM from ElevenLabs, duplicates mono→stereo, plays through Jabra via `sounddevice`.

### STT: Deepgram Nova-3 (unchanged)

Retained from the pilot. Cheap, accurate, handles tent fan noise well.

### Wake word: openWakeWord

**Chosen over** Picovoice Porcupine.

| Factor | openWakeWord | Porcupine |
|--------|-------------|-----------|
| License | Apache 2.0 code (model weights CC BY-NC-SA 4.0) | Proprietary, free tier with limits |
| Custom wake words | Trainable on synthetic data (~1hr in Colab) | Type a phrase, get a model instantly |
| Resource usage | 15–20 models on a single RPi3 core | Similar, but closed |
| Audio format | 16 kHz mono PCM (matches Jabra mic exactly) | 16 kHz mono PCM |
| Accuracy | <5% false-reject, <0.5/hr false-accept | Comparable |
| Vendor dependency | None | API key + license |

Training a custom "hey claudia" wake word model. The wake word listener runs continuously on the Jabra mic stream; STT/LLM/TTS only activate after a trigger, keeping cloud API costs near zero during idle.

## Architecture

```
Jabra mic (16kHz mono) ──► openWakeWord (always-on, ~0 CPU)
                                │
                          trigger detected
                                │
                                ▼
                     Deepgram STT websocket ──► LLM ──► ElevenLabs TTS ──► Jabra speaker
```
