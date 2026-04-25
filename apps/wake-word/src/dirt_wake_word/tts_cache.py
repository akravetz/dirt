"""TTS cache hook — skip Piper TTS when a cached dataset is mounted.

If a `dirt-wakeword-tts-cache` Kaggle dataset is attached to the kernel,
copy the cached Piper-generated WAVs into the four pre-train directories.
Upstream's `--generate_clips` then sees ≥95 % of `n_samples` already in
place and skips Piper entirely.

Cache invalidation by key file (target_phrase + n_samples + n_samples_val).
A mismatch causes loud sys.exit, never silent stale-data training.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from .config import NUMBER_OF_EXAMPLES, TARGET_WORD
from .paths import find_dataset


def restore_tts_cache_if_mounted(out_dir: Path) -> bool:
    """Return True if the cache was used; False if Piper still needs to run."""
    cache_dir = find_dataset("dirt-wakeword-tts-cache")
    if not cache_dir.exists():
        print("(no TTS cache attached — `--generate_clips` will run Piper)")
        return False
    cache_key_path = cache_dir / "cache-key.json"
    if not cache_key_path.exists():
        print(
            f"WARNING: TTS cache attached at {cache_dir} but cache-key.json missing — "
            "ignoring cache and running Piper"
        )
        return False

    expected = {
        "target_phrase": TARGET_WORD.replace("_", " "),
        "n_samples": NUMBER_OF_EXAMPLES,
        "n_samples_val": max(500, NUMBER_OF_EXAMPLES // 10),
    }
    actual = json.loads(cache_key_path.read_text())
    if actual != expected:
        sys.exit(
            f"FATAL: TTS cache key mismatch.\n  cache: {actual}\n  run:   {expected}\n"
            "Rebuild the cache (operator workflow in apps/wake-word/CLAUDE.md) "
            "or detach the dataset from this kernel."
        )

    print(f"=== TTS cache hit: copying cached WAVs from {cache_dir}")
    total = 0
    for subdir in (
        "positive_train",
        "negative_train",
        "positive_test",
        "negative_test",
    ):
        src = cache_dir / subdir
        if not src.is_dir():
            print(
                f"  (warning) {subdir}/ missing from cache; that subset falls through to Piper"
            )
            continue
        dst = out_dir / TARGET_WORD / subdir
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for wav in src.glob("*.wav"):
            shutil.copy(wav, dst / wav.name)
            n += 1
        total += n
        print(f"  {subdir}: {n} WAVs restored")
    print(f"  TTS cache total: {total} WAVs (Piper TTS will be skipped)")
    return True
