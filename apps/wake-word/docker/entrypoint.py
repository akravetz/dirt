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

import os
import shutil
import sys
import traceback
from pathlib import Path

INPUT = Path(os.environ.setdefault("DIRT_KAGGLE_INPUT", "/workspace/input"))
WORKING = Path(os.environ.setdefault("DIRT_KAGGLE_WORKING", "/workspace/working"))
OUT = Path("/workspace/out")
TARGET_WORD = "hey_claudia"


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
