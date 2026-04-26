"""Wake-word trainer entrypoint inside the RunPod container.

Wraps `dirt_wake_word.main.main()` with the harness-boundary concerns the
library shouldn't know about:

1. Set DIRT_WAKEWORD_INPUT / DIRT_WAKEWORD_WORKING to the volume-mounted
   paths so `paths.py` resolves training data from the Network Volume.
2. Open a W&B run in `console="redirect"` mode so the container's
   stdout/stderr (including subprocess output) streams live to the run's
   "Logs" tab and survives `DELETE /pods/{id}`. See
   docs/references/wandb/docker-and-runpod.md for env-var rationale.
3. Write `/workspace/out/run-manifest.json` recording git SHA, image tag,
   pod ID, GPU, volume manifest, resolved config, timestamps, W&B run URL.
   This is the durable provenance record — `runs.jsonl` (Phase 3) reads it.
4. Copy the produced .onnx + validation report into /workspace/out/ so
   SCP-off-the-pod hits one stable directory.
5. Write /workspace/out/SUCCESS or /workspace/out/FAILURE so the
   orchestrator can distinguish a clean exit from a crash — RunPod's REST
   API does NOT expose container exit codes.

Always exits 0 — RunPod's container runtime auto-restarts on non-zero
exit, which would silently burn $/hr in a crash loop. The FAILURE
sentinel + traceback is the failure signal; the orchestrator polls for
it via SCP after seeing desiredStatus=EXITED.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

INPUT = Path(os.environ.setdefault("DIRT_WAKEWORD_INPUT", "/workspace/input"))
WORKING = Path(os.environ.setdefault("DIRT_WAKEWORD_WORKING", "/workspace/working"))
OUT = Path("/workspace/out")
TARGET_WORD = "hey_claudia"
TTS_CACHE_DIR = INPUT / "dirt-wakeword-tts-cache"
VOLUME_MANIFEST_PATH = INPUT / "MANIFEST.json"


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


def _probe_gpu_name() -> str | None:
    """Best-effort `nvidia-smi` probe. None on CPU pods / smoke test."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return (r.stdout.strip().splitlines() or [None])[0] or None


def _read_volume_manifest() -> dict[str, Any] | None:
    """Read /workspace/input/MANIFEST.json. None if missing — graceful for
    first runs / local smoke before the manifest is bootstrapped."""
    if not VOLUME_MANIFEST_PATH.exists():
        return None
    try:
        return json.loads(VOLUME_MANIFEST_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARN: could not parse {VOLUME_MANIFEST_PATH}: {exc!r}", flush=True)
        return None


def _start_manifest(resolved_config: dict[str, Any]) -> dict[str, Any]:
    """Collect every fact knowable at run start. Mutated later with the
    finish_at timestamp, status, and W&B run URL. Written exactly once,
    in the appropriate sentinel branch."""
    return {
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "status": None,
        "git_sha": os.environ.get("DIRT_GIT_SHA") or None,
        "image_ref": os.environ.get("DIRT_IMAGE_REF") or None,
        "pod_id": os.environ.get("RUNPOD_POD_ID") or None,
        "gpu_name": _probe_gpu_name(),
        "wandb_run_url": None,
        "wandb_run_id": None,
        "volume_manifest": _read_volume_manifest(),
        "resolved_config": resolved_config,
    }


def _write_manifest(manifest: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def _maybe_init_wandb(manifest: dict[str, Any]) -> Any | None:
    """Open a W&B run, attach manifest fields as run config + tags. Returns
    the run handle, or None on any failure (we never let W&B problems block
    a training run — local artifacts + run-manifest.json are sufficient)."""
    if os.environ.get("WANDB_MODE") == "disabled":
        return None
    if not os.environ.get("WANDB_API_KEY"):
        print("(no WANDB_API_KEY; skipping W&B init)", flush=True)
        return None
    try:
        import wandb

        run = wandb.init(
            job_type="train",
            config=manifest["resolved_config"],
            tags=[t for t in [manifest["git_sha"], manifest["gpu_name"]] if t],
            notes=f"image={manifest['image_ref']} pod={manifest['pod_id']}",
        )
        manifest["wandb_run_url"] = getattr(run, "url", None)
        manifest["wandb_run_id"] = getattr(run, "id", None)
    except Exception as exc:  # noqa: BLE001 — degrade, never block training
        print(f"WARN: wandb.init failed; continuing without W&B: {exc!r}", flush=True)
        return None
    return run


def _finalize_wandb(run: Any | None, *, exit_code: int) -> None:
    if run is None:
        return
    try:
        import wandb

        wandb.finish(exit_code=exit_code)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: wandb.finish failed: {exc!r}", flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORKING.mkdir(parents=True, exist_ok=True)
    print(f"DIRT_WAKEWORD_INPUT={INPUT}", flush=True)
    print(f"DIRT_WAKEWORD_WORKING={WORKING}", flush=True)

    # Library import inside try so any ImportError lands in the FAILURE
    # sentinel rather than killing the entrypoint silently.
    try:
        from dirt_wake_word.config import current_tunables
        from dirt_wake_word.main import main as wake_word_main
    except BaseException:
        tb = traceback.format_exc()
        print(f"=== ENTRYPOINT IMPORT FAILED ===\n{tb}", flush=True, file=sys.stderr)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "FAILURE").write_text(tb)
        return

    manifest = _start_manifest(current_tunables())
    run = _maybe_init_wandb(manifest)

    try:
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
        # Catch + log + exit 0 so RunPod doesn't auto-restart the container.
        # The FAILURE sentinel + traceback is what the orchestrator reads.
        tb = traceback.format_exc()
        print(f"=== ENTRYPOINT FAILED ===\n{tb}", flush=True, file=sys.stderr)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "FAILURE").write_text(tb)
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        manifest["status"] = "failure"
        _write_manifest(manifest)
        try:
            _publish_artifacts()  # any partial artifacts help post-mortems
        except OSError:
            pass
        _finalize_wandb(run, exit_code=1)
        return

    manifest["finished_at"] = datetime.now(UTC).isoformat()
    manifest["status"] = "success"
    _write_manifest(manifest)
    _finalize_wandb(run, exit_code=0)
    (OUT / "SUCCESS").write_text("ok\n")
    print("=== entrypoint: SUCCESS sentinel written ===", flush=True)


def _hold() -> None:
    """Keep the container alive so the orchestrator can SCP off /workspace/out/.

    RunPod auto-restarts on non-zero exit; we always exit 0. But exit-0
    means sshd dies, so the orchestrator can't SCP. Block forever; the
    orchestrator's `finally: delete_pod` is the cleanup path.

    DIRT_TRAINER_NO_HOLD=1 (set by scripts/smoke-trainer-image) skips this
    so the local docker-run smoke can let the container exit naturally.
    """
    if os.environ.get("DIRT_TRAINER_NO_HOLD"):
        return
    print("(work done; sleeping for orchestrator to pull artifacts)", flush=True)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
    _hold()
