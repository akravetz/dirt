"""Wake-word trainer entrypoint inside the RunPod container.

Wraps `dirt_wake_word.main.main()` with three things the orchestrator needs:

1. Set DIRT_KAGGLE_INPUT / DIRT_KAGGLE_WORKING to the volume-mounted paths
   so the library's `paths.py` resolves training data from the Network
   Volume seeded by `scripts/runpod-seed-volume`.
2. Copy the produced ONNX / tflite / validation report into /workspace/out/
   so SCP-off-the-pod hits one stable directory.
3. Write /workspace/out/SUCCESS or /workspace/out/FAILURE so the
   orchestrator can distinguish a clean exit from a crash — the RunPod
   REST API does NOT expose container exit codes.

Re-raises on failure so the Pod exits non-zero (helps surface in logs even
though the orchestrator only reads the sentinel).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import traceback
from pathlib import Path

INPUT = Path(os.environ.setdefault("DIRT_KAGGLE_INPUT", "/workspace/input"))
WORKING = Path(os.environ.setdefault("DIRT_KAGGLE_WORKING", "/workspace/working"))
OUT = Path("/workspace/out")
TARGET_WORD = "hey_claudia"
TTS_CACHE_DIR = INPUT / "dirt-wakeword-tts-cache"
TTS_SUBDIRS = ("positive_train", "negative_train", "positive_test", "negative_test")


def _publish_artifacts() -> None:
    """Copy what the orchestrator needs to pull off the pod into one dir."""
    OUT.mkdir(parents=True, exist_ok=True)
    artifacts_src = WORKING / "my_custom_model"
    for fname in (f"{TARGET_WORD}.onnx", f"{TARGET_WORD}.tflite"):
        src = artifacts_src / fname
        if src.exists():
            shutil.copy2(src, OUT / fname)
    report = WORKING / "validation-report.txt"
    if report.exists():
        shutil.copy2(report, OUT / "validation-report.txt")


def _persist_tts_cache() -> None:
    """Copy generated TTS WAVs to the volume so future runs skip Piper.

    The library's `restore_tts_cache_if_mounted()` hook (in tts_cache.py)
    looks for `/workspace/input/dirt-wakeword-tts-cache/` with a matching
    cache-key.json. If we wrote that here, the next run reads it and
    short-circuits the ~22 min `--generate_clips` Piper phase.

    Skips silently when the cache is already populated and matches the
    current run's parameters — re-running v2 onwards shouldn't redo the
    write since prepare_seed_clips already restored the same WAVs.
    """
    from dirt_wake_word.config import NUMBER_OF_EXAMPLES, TARGET_WORD as _tw

    expected_key = {
        "target_phrase": _tw.replace("_", " "),
        "n_samples": NUMBER_OF_EXAMPLES,
        "n_samples_val": max(500, NUMBER_OF_EXAMPLES // 10),
    }
    key_path = TTS_CACHE_DIR / "cache-key.json"
    if key_path.exists():
        existing = json.loads(key_path.read_text())
        if existing == expected_key:
            print(
                f"=== TTS cache already up-to-date at {TTS_CACHE_DIR} (skipping persist)",
                flush=True,
            )
            return

    print(f"=== persisting TTS cache to {TTS_CACHE_DIR} ===", flush=True)
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    src_root = WORKING / "my_custom_model"
    total = 0
    for subdir in TTS_SUBDIRS:
        src = src_root / subdir
        if not src.is_dir():
            print(f"  (warning) {subdir}/ missing — skipping in cache", flush=True)
            continue
        dst = TTS_CACHE_DIR / subdir
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for wav in src.glob("*.wav"):
            shutil.copy2(wav, dst / wav.name)
            n += 1
        total += n
        print(f"  {subdir}: {n} WAVs cached", flush=True)
    key_path.write_text(json.dumps(expected_key, indent=2) + "\n")
    print(f"  total {total} WAVs; cache-key.json written", flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORKING.mkdir(parents=True, exist_ok=True)
    print(f"DIRT_KAGGLE_INPUT={INPUT}", flush=True)
    print(f"DIRT_KAGGLE_WORKING={WORKING}", flush=True)

    try:
        # Imported here so an ImportError shows up in the FAILURE sentinel
        # rather than blowing up before we have a place to write it.
        from dirt_wake_word.main import main as wake_word_main

        wake_word_main()
        _publish_artifacts()
        # Persist generated TTS WAVs so v2+ runs skip the ~22 min Piper phase.
        # Best-effort: a failure here shouldn't fail the run.
        try:
            _persist_tts_cache()
        except Exception as exc:
            print(f"WARN: TTS cache persist failed: {exc!r}", flush=True)
    except BaseException:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "FAILURE").write_text(traceback.format_exc())
        # Best-effort copy of any partial artifacts so post-mortems have data.
        try:
            _publish_artifacts()
        except Exception:
            pass
        raise

    (OUT / "SUCCESS").write_text("ok\n")
    print("=== entrypoint: SUCCESS sentinel written, exiting 0 ===", flush=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
