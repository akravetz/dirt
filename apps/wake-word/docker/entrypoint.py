"""Wake-word trainer entrypoint inside the RunPod container.

RUN_ID = DIRT_RUN_ID || RUNPOD_POD_ID || `local-<timestamp>`. Every
volume write is namespaced under it: /workspace/out/<RUN_ID>/ for
artifacts, /workspace/working/<RUN_ID>/ for scratch. The orchestrator
S3-downloads out/<RUN_ID>/ once the pod is EXITED.

Always exits 0 — RunPod auto-restarts on non-zero exit.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUN_ID = (
    os.environ.get("DIRT_RUN_ID")
    or os.environ.get("RUNPOD_POD_ID")
    or f"local-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
)

INPUT = Path(os.environ.setdefault("DIRT_WAKEWORD_INPUT", "/workspace/input"))
WORKING = Path(
    os.environ.setdefault("DIRT_WAKEWORD_WORKING", f"/workspace/working/{RUN_ID}")
)
OUT = Path(os.environ.get("DIRT_WAKEWORD_OUT") or f"/workspace/out/{RUN_ID}")
TARGET_WORD = "hey_claudia"
TTS_CACHE_DIR = INPUT / "dirt-wakeword-tts-cache"
VOLUME_MANIFEST_PATH = INPUT / "MANIFEST.json"


def _hardlink_or_copy(src: Path, dst: Path) -> None:
    try:
        if dst.exists():
            dst.unlink()
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _publish_artifacts() -> None:
    onnx_src = WORKING / "my_custom_model" / f"{TARGET_WORD}.onnx"
    if onnx_src.exists():
        _hardlink_or_copy(onnx_src, OUT / onnx_src.name)
    report_src = WORKING / "validation-report.txt"
    if report_src.exists():
        _hardlink_or_copy(report_src, OUT / report_src.name)


def _persist_tts_cache() -> None:
    """Always rewrite the cache, never short-circuit on matching cache-key.

    Earlier versions skipped writing when cache-key.json already matched —
    but if a prior run wrote the key while subset dirs were partial/missing,
    the cache stayed broken forever (subsequent runs hit the early return
    and never repaired). Hardlinks are essentially free, so always rebuild.
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
    print(f"=== persisting TTS cache to {TTS_CACHE_DIR} ===", flush=True)
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # WAVs actually live under .../my_custom_model/<TARGET_WORD>/<subset>/ —
    # that's where restore_tts_cache_if_mounted puts them and where
    # augment_and_compute_features reads them. Earlier code looked at
    # .../my_custom_model/<subset>/ (no TARGET_WORD level), so persist
    # always wrote cache-key.json with empty subdirs. Pre-existing bug,
    # masked until restore went strict.
    src_root = WORKING / "my_custom_model" / TARGET_WORD
    total = 0
    for subdir in SUBSETS:
        src = src_root / subdir
        if not src.is_dir():
            print(f"  (warning) {subdir}/ missing in WORKING — skipping", flush=True)
            continue
        dst = TTS_CACHE_DIR / subdir
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for wav in src.glob("*.wav"):
            _hardlink_or_copy(wav, dst / wav.name)
            n += 1
        total += n
        print(f"  {subdir}: {n} WAVs cached", flush=True)
    (TTS_CACHE_DIR / "cache-key.json").write_text(
        json.dumps(expected_key, indent=2) + "\n"
    )
    print(f"  total {total} WAVs; cache-key.json written", flush=True)


def _probe_gpu_name() -> str | None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    lines = r.stdout.strip().splitlines()
    return lines[0] if lines else None


def _read_volume_manifest() -> dict[str, Any] | None:
    try:
        return json.loads(VOLUME_MANIFEST_PATH.read_text())
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARN: could not parse {VOLUME_MANIFEST_PATH}: {exc!r}", flush=True)
        return None


def _start_manifest(resolved_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "status": None,
        "git_sha": os.environ.get("DIRT_GIT_SHA"),
        "image_ref": os.environ.get("DIRT_IMAGE_REF"),
        "pod_id": os.environ.get("RUNPOD_POD_ID"),
        "gpu_name": _probe_gpu_name(),
        "wandb_run_url": None,
        "wandb_run_id": None,
        "volume_manifest": _read_volume_manifest(),
        "resolved_config": resolved_config,
    }


def _maybe_init_wandb(manifest: dict[str, Any]) -> Any | None:
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
            tags=[
                t for t in [manifest["git_sha"], manifest["gpu_name"], RUN_ID] if t
            ],
            notes=f"image={manifest['image_ref']} pod={manifest['pod_id']} run_id={RUN_ID}",
        )
        manifest["wandb_run_url"] = getattr(run, "url", None)
        manifest["wandb_run_id"] = getattr(run, "id", None)
        return run
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: wandb.init failed; continuing without W&B: {exc!r}", flush=True)
        return None


def _finalize_wandb(run: Any | None, *, exit_code: int) -> None:
    if run is None:
        return
    try:
        import wandb

        wandb.finish(exit_code=exit_code)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: wandb.finish failed: {exc!r}", flush=True)


def _cleanup_working() -> None:
    """Remove WORKING/ scratch (per-run features, augmented WAVs, model build).

    The volume is the only durable copy of the dataset, so leaving N+1
    copies of 30k augmented WAVs around per training run blows past the
    quota in days. Sentinel + artifacts in OUT/ are preserved.
    """
    if not WORKING.exists():
        return
    print(f"=== cleaning up scratch dir {WORKING} ===", flush=True)
    shutil.rmtree(WORKING, ignore_errors=True)


def _self_delete() -> None:
    """DELETE this pod via the RunPod REST API. Best-effort.

    Belt-and-suspenders to the orchestrator's own `finally: DELETE`. If the
    orchestrator dies (or never existed), this stops the pod from running
    indefinitely after training finishes — RunPod auto-restarts containers
    on exit while the pod is leased, so without DELETE the GPU keeps
    billing on a tight restart loop. DELETE-on-already-gone is idempotent
    on the orchestrator side (404 swallowed by leased_pod's finally)."""
    pod_id = os.environ.get("RUNPOD_POD_ID")
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not pod_id or not api_key:
        print("(self-DELETE skipped: RUNPOD_POD_ID or RUNPOD_API_KEY missing)", flush=True)
        return
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"https://rest.runpod.io/v1/pods/{pod_id}",
        method="DELETE",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"=== self-DELETE pod={pod_id} status={resp.status} ===", flush=True)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"WARN: self-DELETE failed: {exc!r}", flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # Quick-exit if a sentinel already exists from a prior incarnation of
    # this pod. RunPod auto-restarts the container on exit while the pod
    # is leased; without this guard, every restart would re-run training
    # (or FATAL on cache state) and burn cycles. Self-DELETE on the way
    # out in case nothing else has cleaned up the pod.
    if (OUT / "SUCCESS").exists() or (OUT / "FAILURE").exists():
        print(
            f"=== sentinel already present at {OUT}; auto-restart detected, quick-exiting ===",
            flush=True,
        )
        _self_delete()
        return

    WORKING.mkdir(parents=True, exist_ok=True)
    print(f"DIRT_RUN_ID={RUN_ID}", flush=True)
    print(f"DIRT_WAKEWORD_INPUT={INPUT}", flush=True)
    print(f"DIRT_WAKEWORD_WORKING={WORKING}", flush=True)
    print(f"OUT={OUT}", flush=True)

    from dirt_wake_word.config import current_tunables
    from dirt_wake_word.main import main as wake_word_main

    manifest = _start_manifest(current_tunables())
    run = _maybe_init_wandb(manifest)

    try:
        wake_word_main()
        _publish_artifacts()
        try:
            _persist_tts_cache()
        except OSError:
            print(f"WARN: TTS cache persist failed:\n{traceback.format_exc()}", flush=True)
    except BaseException:
        tb = traceback.format_exc()
        print(f"=== ENTRYPOINT FAILED ===\n{tb}", flush=True, file=sys.stderr)
        (OUT / "FAILURE").write_text(tb)
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        manifest["status"] = "failure"
        (OUT / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        _finalize_wandb(run, exit_code=1)
        _cleanup_working()
        _self_delete()
        return

    manifest["finished_at"] = datetime.now(UTC).isoformat()
    manifest["status"] = "success"
    (OUT / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    _finalize_wandb(run, exit_code=0)
    (OUT / "SUCCESS").write_text("ok\n")
    print("=== entrypoint: SUCCESS sentinel written ===", flush=True)
    _cleanup_working()
    _self_delete()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        try:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "FAILURE").write_text(traceback.format_exc())
        except Exception:
            pass
        try:
            _cleanup_working()
        except Exception:
            pass
        try:
            _self_delete()
        except Exception:
            pass
    sys.exit(0)
