"""TTS cache hook — skip Piper TTS when a cached dataset is mounted.

If `/workspace/input/dirt-wakeword-tts-cache/` is present (populated by a
prior successful run via entrypoint._persist_tts_cache), hardlink the
cached Piper-generated WAVs into the four pre-train directories.
Upstream's `--generate_clips` then sees ≥95% of n_samples already in
place and skips Piper entirely — saves ~20 min per run.

Cache invalidation by key file (target_phrase + n_samples + n_samples_val).
A mismatch causes loud sys.exit, never silent stale-data training.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from .config import NUMBER_OF_EXAMPLES, NUMBER_OF_EXAMPLES_VAL, TARGET_WORD
from .paths import find_dataset
from .subsets import SUBSETS

TTS_CACHE_MODE_ENV = "DIRT_WAKEWORD_TTS_CACHE_MODE"


def _link(src: Path, dst: Path) -> None:
    """Hardlink src→dst (cheap, same fs); copy on EXDEV (different fs)."""
    try:
        if dst.exists():
            dst.unlink()
        os.link(src, dst)
    except OSError:
        shutil.copy(src, dst)


def restore_tts_cache_if_mounted(out_dir: Path) -> bool:
    """Return True if the cache was used; False if Piper still needs to run."""
    cache_mode = os.environ.get(TTS_CACHE_MODE_ENV, "restore").strip().lower()
    if cache_mode not in {"restore", "ignore", "force"}:
        sys.exit(
            f"FATAL: {TTS_CACHE_MODE_ENV} must be one of restore, ignore, force; "
            f"got {cache_mode!r}"
        )
    if cache_mode == "ignore":
        print(f"({TTS_CACHE_MODE_ENV}=ignore — skipping TTS cache restore)")
        return False

    cache_dir = find_dataset("dirt-wakeword-tts-cache")
    if not cache_dir.exists():
        print("(no TTS cache attached — `--generate_clips` will run Piper)")
        return False
    cache_key_path = cache_dir / "cache-key.json"
    if not cache_key_path.exists():
        print(
            f"WARNING: TTS cache attached at {cache_dir} but cache-key.json "
            "missing — ignoring cache and running Piper"
        )
        return False

    expected = {
        "target_phrase": TARGET_WORD.replace("_", " "),
        "n_samples": NUMBER_OF_EXAMPLES,
        "n_samples_val": NUMBER_OF_EXAMPLES_VAL,
    }
    actual = json.loads(cache_key_path.read_text())
    if actual != expected:
        if cache_mode == "force":
            print(
                "WARNING: TTS cache key mismatch but "
                f"{TTS_CACHE_MODE_ENV}=force; restoring cache anyway.\n"
                f"  cache: {actual}\n  run:   {expected}",
                flush=True,
            )
        else:
            sys.exit(
                f"FATAL: TTS cache key mismatch.\n"
                f"  cache: {actual}\n  run:   {expected}\n"
                "Clear /workspace/input/dirt-wakeword-tts-cache/ on the volume "
                "(SSH to a pod and `rm -rf`, or re-seed) so the next run rebuilds it."
            )

    # If cache-key matches but subset dirs are missing/empty, the cache is
    # corrupt-partial. Hard-fail rather than silently falling through to
    # Piper — silent fallthrough is what kept this state alive across runs
    # (the old _persist_tts_cache short-circuited on matching key, so
    # corruption never got repaired).
    missing = [s for s in SUBSETS if not (cache_dir / s).is_dir()]
    if missing:
        sys.exit(
            f"FATAL: TTS cache key matches but subset dirs missing: {missing}\n"
            f"Either delete /workspace/input/dirt-wakeword-tts-cache/cache-key.json "
            f"on the volume to force a clean rebuild on the next run, or run a "
            f"server-side cp -al from /workspace/working/my_custom_model/."
        )

    print(f"=== TTS cache hit: hardlinking cached WAVs from {cache_dir}")
    total = 0
    for subdir in SUBSETS:
        dst = out_dir / TARGET_WORD / subdir
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for wav in (cache_dir / subdir).glob("*.wav"):
            _link(wav, dst / wav.name)
            n += 1
        total += n
        print(f"  {subdir}: {n} WAVs restored")
    print(f"  TTS cache total: {total} WAVs (Piper TTS will be skipped)")
    return True
