"""Batch-generate phonetic-neighbor negatives via ElevenLabs voice cloning.

Sister script to `elevenlabs_clone_batch.py` — same voice, same settings spread,
different phrase list. The output WAVs are *hard negatives* for openWakeWord
training: phrases that share enough acoustic structure with "hey claudia" to
trick a model that learned only on the positive set + broad ACAV background,
but which a human would clearly reject.

Phrase strategy:
- Decomposition negatives (`hey`, `claudia`): force the model to require BOTH
  halves rather than firing on either alone. Heaviest weight.
- Prefix swaps (`okay claudia`, `play claudia`): test that the wake word
  *prefix* matters, not just the suffix.
- Phoneme-shifted suffixes (`hey claire`, `hey clyde`, `hey clay`): test that
  the model requires the specific "claudia" phoneme sequence, not just
  "hey C-something".
- Distant rhymes (`hey clouds`, `hey kappa`): cheap padding for variety.

These are *synthetic* negatives. They MUST be paired with real-world harvested
false-positives from `var/logs/wake_audio/near_miss_*.wav` for a robust model
— TTS-rendered phonemes can have artifacts the model latches onto, so don't
ship a training run that uses *only* this bucket as hard negatives.

Output: var/elevenlabs/voice_samples_neighbors/<slug>_NNN_s..b..v...wav (16 kHz mono)
Cost: ~470 short phrases at ElevenLabs streaming rates ≈ <$1 in credits.

Usage:
    uv run python scripts/elevenlabs-neighbors-batch.py
"""

from __future__ import annotations

import os
import random
import sys
import wave
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs, VoiceSettings

# File lives at apps/wake-word/data-gen/<this>.py — 4 parents up to repo root.
ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("ELABS_API_KEY")
if not API_KEY:
    sys.exit("ELABS_API_KEY must be set in .env")

VOICE_ID = "mjXJZpUEgv69eq6xrhlW"
MODEL_ID = "eleven_multilingual_v2"
SAMPLE_RATE = 16000
OUTPUT_DIR = ROOT / "var" / "wake-word" / "neighbors"

# (prompt text, count) — see module docstring for the rationale per group.
#
# `okay claudia` and `play claudia` were generated initially but removed
# 2026-04-25 — they share the "claudia" suffix with the wake word and were
# decided to be acceptable false-positive triggers. Don't add them back
# unless we've reconsidered that call.
PHRASES: list[tuple[str, int]] = [
    # Decomposition: most important. Model must require both halves.
    ("hey", 75),
    ("claudia", 75),
    # Phoneme-shifted suffixes: hardest distractor class.
    ("hey claire", 50),
    ("hey clyde", 50),
    ("hey clay", 50),
    # Distant rhymes: cheap padding for diversity.
    ("hey clouds", 30),
    ("hey kappa", 30),
]

SETTINGS_PRESETS: list[dict] = [
    {"stability": 0.30, "similarity_boost": 1.00, "speed": 1.00},
    {"stability": 0.45, "similarity_boost": 0.90, "speed": 1.10},
    {"stability": 0.55, "similarity_boost": 1.00, "speed": 0.95},
    {"stability": 0.65, "similarity_boost": 0.80, "speed": 1.05},
    {"stability": 0.40, "similarity_boost": 1.00, "speed": 1.00},
]

SEED = 42


def save_pcm_as_wav(pcm_bytes: bytes, path: Path, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm_bytes)


def slugify(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")


def main() -> None:
    """PHRASES values are TARGETS, not deltas — resume-safe across runs."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=API_KEY)
    rng = random.Random(SEED)

    todo = []
    for phrase, target in PHRASES:
        slug = slugify(phrase)
        existing = len(list(OUTPUT_DIR.glob(f"{slug}_*.wav")))
        to_generate = max(0, target - existing)
        todo.append((phrase, slug, existing, target, to_generate))

    total_to_generate = sum(t[4] for t in todo)

    print(f"Voice: {VOICE_ID}")
    for phrase, _slug, existing, target, to_gen in todo:
        status = "✓" if to_gen == 0 else f"needs {to_gen}"
        print(f"  {phrase!r:<22}  {existing}/{target}  {status}")
    print()

    if total_to_generate == 0:
        print("All phrase targets already met — nothing to generate.")
        return

    print(f"Generating {total_to_generate} new samples...\n")

    counter = 0
    for phrase, slug, existing, _target, to_gen in todo:
        if to_gen == 0:
            continue
        print(f"=== {phrase!r}: generating {to_gen} more (starting from index {existing + 1}) ===")
        for n in range(to_gen):
            counter += 1
            settings = rng.choice(SETTINGS_PRESETS)
            stream = client.text_to_speech.stream(
                text=phrase,
                voice_id=VOICE_ID,
                model_id=MODEL_ID,
                output_format="pcm_16000",
                voice_settings=VoiceSettings(
                    stability=settings["stability"],
                    similarity_boost=settings["similarity_boost"],
                    speed=settings["speed"],
                ),
            )
            pcm_bytes = b"".join(stream)
            duration_s = len(pcm_bytes) / 2 / SAMPLE_RATE
            idx = existing + n + 1
            fname = (
                f"{slug}_{idx:03d}_"
                f"s{int(settings['stability']*100):02d}"
                f"b{int(settings['similarity_boost']*100):03d}"
                f"v{int(settings['speed']*100):03d}.wav"
            )
            out_path = OUTPUT_DIR / fname
            save_pcm_as_wav(pcm_bytes, out_path, SAMPLE_RATE)
            print(f"  [{counter:>4}/{total_to_generate}] {fname}  ({duration_s:.2f}s)")

    print()
    print(f"All {total_to_generate} samples saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
