"""Batch-generate voice-clone samples for openWakeWord training data.

Generates samples across a mix of text variants and voice settings,
saving as 16 kHz mono WAV files suitable for dropping into the
openWakeWord `positive_train/` directory.

Edit PHRASES and SETTINGS below to control the batch composition.

Usage:
    uv run python apps/wake-word/data-gen/elevenlabs-clones-batch.py
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
OUTPUT_DIR = ROOT / "var" / "wake-word" / "synth-clones"

# (prompt text, count)
PHRASES: list[tuple[str, int]] = [
    ("hey claudia", 500),
    ("Hey, Claudia", 500),
    ("hey Clowdia", 500),
    ("Hey, Clowdia", 500),
]

# Settings presets we cycle through to introduce acoustic diversity.
# Stability low -> more expressive variation. Similarity_boost high ->
# closer to the clone reference. Speed spread simulates natural pacing
# differences.
SETTINGS_PRESETS: list[dict] = [
    {"stability": 0.30, "similarity_boost": 1.00, "speed": 1.00},
    {"stability": 0.45, "similarity_boost": 0.90, "speed": 1.10},
    {"stability": 0.55, "similarity_boost": 1.00, "speed": 0.95},
    {"stability": 0.65, "similarity_boost": 0.80, "speed": 1.05},
    {"stability": 0.40, "similarity_boost": 1.00, "speed": 1.00},
]

SEED = 42  # reproducible settings ordering across runs


def save_pcm_as_wav(pcm_bytes: bytes, path: Path, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm_bytes)


def slugify(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")


def main() -> None:
    """Generate until each phrase in PHRASES has reached its target count.

    PHRASES values are TARGETS, not deltas — resume-safe. Running the
    script multiple times with the same PHRASES config converges on the
    target; each run only generates what's missing.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    client = ElevenLabs(api_key=API_KEY)
    rng = random.Random(SEED)

    # Figure out what still needs to be generated per phrase
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
        print(f"  {phrase!r:<25}  {existing}/{target}  {status}")
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
