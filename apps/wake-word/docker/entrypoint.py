"""Wake-word trainer entrypoint inside the RunPod container.

Wraps `dirt_wake_word.main.main()` with three things the orchestrator needs:

1. Set DIRT_WAKEWORD_INPUT / DIRT_WAKEWORD_WORKING to the volume-mounted
   paths so the library's `paths.py` resolves training data from the
   Network Volume seeded by `scripts/runpod-seed-volume`.
2. Copy the produced .onnx + validation report into /workspace/out/ so
   SCP-off-the-pod hits one stable directory.
3. Write /workspace/out/SUCCESS or /workspace/out/FAILURE so the
   orchestrator can distinguish a clean exit from a crash — RunPod's REST
   API does NOT expose container exit codes.

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

INPUT = Path(os.environ.setdefault("DIRT_WAKEWORD_INPUT", "/workspace/input"))
WORKING = Path(os.environ.setdefault("DIRT_WAKEWORD_WORKING", "/workspace/working"))
OUT = Path("/workspace/out")
TARGET_WORD = "hey_claudia"
TTS_CACHE_DIR = INPUT / "dirt-wakeword-tts-cache"


def _hardlink_or_copy(src: Path, dst: Path) -> None:
    """os.link is ~free (same fs) — only fall back to copy on EXDEV/EPERM."""
    try:
        if dst.exists():
            dst.unlink()
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _publish_artifacts() -> None:
    """Stage what the orchestrator pulls off the pod into /workspace/out/."""
    OUT.mkdir(parents=True, exist_ok=True)
    onnx_src = WORKING / "my_custom_model" / f"{TARGET_WORD}.onnx"
    if onnx_src.exists():
        _hardlink_or_copy(onnx_src, OUT / onnx_src.name)
    report_src = WORKING / "validation-report.txt"
    if report_src.exists():
        _hardlink_or_copy(report_src, OUT / report_src.name)


def _persist_tts_cache() -> None:
    """Hardlink generated TTS WAVs to the volume so future runs skip Piper.

    `restore_tts_cache_if_mounted()` (in tts_cache.py) reads
    /workspace/input/dirt-wakeword-tts-cache/ at the next run's start; if
    its cache-key.json matches the current config, the entire ~22 min
    Piper phase is short-circuited.
    """
    from dirt_wake_word.config import (
        NUMBER_OF_EXAMPLES,
        NUMBER_OF_EXAMPLES_VAL,
        TARGET_WORD as _tw,
    )
    from dirt_wake_word.subsets import SUBSETS

    expected_key = {
        "target_phrase": _tw.replace("_", " "),
        "n_samples": NUMBER_OF_EXAMPLES,
        "n_samples_val": NUMBER_OF_EXAMPLES_VAL,
    }
    key_path = TTS_CACHE_DIR / "cache-key.json"
    if key_path.exists() and json.loads(key_path.read_text()) == expected_key:
        print(f"=== TTS cache already up-to-date at {TTS_CACHE_DIR}", flush=True)
        return

    print(f"=== persisting TTS cache to {TTS_CACHE_DIR} ===", flush=True)
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    src_root = WORKING / "my_custom_model"
    total = 0
    for subdir in SUBSETS:
        src = src_root / subdir
        if not src.is_dir():
            print(f"  (warning) {subdir}/ missing — skipping in cache", flush=True)
            continue
        dst = TTS_CACHE_DIR / subdir
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for wav in src.glob("*.wav"):
            _hardlink_or_copy(wav, dst / wav.name)
            n += 1
        total += n
        print(f"  {subdir}: {n} WAVs cached", flush=True)
    key_path.write_text(json.dumps(expected_key, indent=2) + "\n")
    print(f"  total {total} WAVs; cache-key.json written", flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORKING.mkdir(parents=True, exist_ok=True)
    print(f"DIRT_WAKEWORD_INPUT={INPUT}", flush=True)
    print(f"DIRT_WAKEWORD_WORKING={WORKING}", flush=True)

    try:
        # Library import inside try so any ImportError lands in the FAILURE
        # sentinel rather than killing the entrypoint silently.
        from dirt_wake_word.main import main as wake_word_main

        wake_word_main()
        _publish_artifacts()
        try:
            _persist_tts_cache()
        except OSError:
            print(
                f"WARN: TTS cache persist failed:\n{traceback.format_exc()}",
                flush=True,
            )
    except BaseException:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "FAILURE").write_text(traceback.format_exc())
        try:
            _publish_artifacts()  # best-effort: any partial artifacts help post-mortems
        except OSError:
            pass
        raise

    (OUT / "SUCCESS").write_text("ok\n")
    print("=== entrypoint: SUCCESS sentinel written, exiting 0 ===", flush=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
