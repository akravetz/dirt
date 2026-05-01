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
import time
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


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, *, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_float(name: str, *, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _wandb_console_config() -> dict[str, Any]:
    return {
        "console": os.environ.get("DIRT_WANDB_CONSOLE", "redirect"),
        "console_multipart": _env_bool("DIRT_WANDB_CONSOLE_MULTIPART", default=True),
        "console_chunk_max_seconds": _env_int(
            "DIRT_WANDB_CONSOLE_CHUNK_SECONDS", default=30
        ),
        "console_chunk_max_bytes": _env_int(
            "DIRT_WANDB_CONSOLE_CHUNK_BYTES", default=512 * 1024
        ),
    }


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
            capture_output=True,
            text=True,
            timeout=5,
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

        console_config = _wandb_console_config()
        run = wandb.init(
            job_type=os.environ.get("DIRT_WANDB_JOB_TYPE", "train"),
            config=manifest["resolved_config"],
            settings=wandb.Settings(**console_config),
            tags=[t for t in [manifest["git_sha"], manifest["gpu_name"], RUN_ID] if t],
            notes=f"image={manifest['image_ref']} pod={manifest['pod_id']} run_id={RUN_ID}",
        )
        manifest["wandb_run_url"] = getattr(run, "url", None)
        manifest["wandb_run_id"] = getattr(run, "id", None)
        _register_wandb_output_log(run)
        return run
    except Exception as exc:
        print(f"WARN: wandb.init failed; continuing without W&B: {exc!r}", flush=True)
        return None


def _register_wandb_output_log(run: Any) -> None:
    """Make W&B's console log visible through the Files/Public API path."""
    try:
        run_dir = Path(str(run.dir))
        output_log = run_dir / "output.log"
        output_log.touch(exist_ok=True)
        saved = run.save(str(output_log), base_path=str(run_dir), policy="live")
        print(f"=== wandb live-save registered output.log: {saved} ===", flush=True)
    except Exception as exc:
        print(f"WARN: could not register W&B output.log: {exc!r}", flush=True)


def _wandb_smoke_config() -> dict[str, Any]:
    return {
        "wandb_smoke": True,
        "seconds": _env_float("DIRT_WANDB_SMOKE_SECONDS", default=90.0),
        "interval_seconds": _env_float("DIRT_WANDB_SMOKE_INTERVAL", default=5.0),
        "console_settings": _wandb_console_config(),
        "wandb_silent": os.environ.get("WANDB_SILENT"),
        "wandb_console_env": os.environ.get("WANDB_CONSOLE"),
    }


def _wandb_local_tree(run: Any | None) -> list[str]:
    if run is None:
        return []
    run_dir = Path(str(run.dir)).parent
    if not run_dir.exists():
        return [f"(missing local run dir {run_dir})"]
    entries: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(run_dir).as_posix()
            entries.append(f"{rel}\t{path.stat().st_size}")
    return entries


def _run_wandb_smoke(run: Any | None, manifest: dict[str, Any]) -> None:
    """Exercise W&B console capture without running wake-word training."""
    config = manifest["resolved_config"]
    seconds = float(config["seconds"])
    interval = float(config["interval_seconds"])
    started = time.monotonic()
    end_at = started + seconds
    step = 0
    lines: list[str] = []

    print("=== W&B CONSOLE SMOKE START ===", flush=True)
    print(f"run_id={RUN_ID}", flush=True)
    print(f"wandb_run_id={manifest.get('wandb_run_id')}", flush=True)
    print(f"wandb_run_url={manifest.get('wandb_run_url')}", flush=True)
    print(f"console_settings={config['console_settings']}", flush=True)
    print(f"WANDB_SILENT={config['wandb_silent']}", flush=True)

    while True:
        elapsed = time.monotonic() - started
        line = f"smoke step={step} elapsed={elapsed:.1f}s"
        print(f"STDOUT print {line}", flush=True)
        print(f"STDERR print {line}", file=sys.stderr, flush=True)
        os.write(1, f"FD1 os.write {line}\n".encode())
        os.write(2, f"FD2 os.write {line}\n".encode())
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    f"print('SUBPROCESS stdout {line}'); "
                    f"print('SUBPROCESS stderr {line}', file=sys.stderr)"
                ),
            ],
            check=False,
        )
        if run is not None:
            run.log({"smoke/step": step, "smoke/elapsed_s": elapsed})
        lines.append(line)
        if time.monotonic() >= end_at:
            break
        step += 1
        time.sleep(interval)

    local_tree = _wandb_local_tree(run)
    print("=== W&B LOCAL RUN FILES ===", flush=True)
    for entry in local_tree:
        print(entry, flush=True)
    (OUT / "wandb-smoke.txt").write_text(
        "\n".join(
            [
                "W&B console smoke",
                f"run_id={RUN_ID}",
                f"wandb_run_id={manifest.get('wandb_run_id')}",
                f"wandb_run_url={manifest.get('wandb_run_url')}",
                f"console_settings={json.dumps(config['console_settings'], sort_keys=True)}",
                "",
                "emitted_lines:",
                *lines,
                "",
                "local_run_files:",
                *local_tree,
            ]
        )
        + "\n"
    )
    print("=== W&B CONSOLE SMOKE END ===", flush=True)


def _finalize_wandb(run: Any | None, *, exit_code: int) -> None:
    if run is None:
        return
    try:
        import wandb

        wandb.finish(exit_code=exit_code)
    except Exception as exc:
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
        print(
            "(self-DELETE skipped: RUNPOD_POD_ID or RUNPOD_API_KEY missing)", flush=True
        )
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

    if _env_bool("DIRT_WANDB_SMOKE"):
        manifest = _start_manifest(_wandb_smoke_config())
        run = _maybe_init_wandb(manifest)
        try:
            _run_wandb_smoke(run, manifest)
        except BaseException:
            tb = traceback.format_exc()
            print(f"=== W&B SMOKE FAILED ===\n{tb}", flush=True, file=sys.stderr)
            (OUT / "FAILURE").write_text(tb)
            manifest["finished_at"] = datetime.now(UTC).isoformat()
            manifest["status"] = "failure"
            (OUT / "run-manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n"
            )
            _finalize_wandb(run, exit_code=1)
            _cleanup_working()
            _self_delete()
            return
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        manifest["status"] = "success"
        (OUT / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        _finalize_wandb(run, exit_code=0)
        (OUT / "SUCCESS").write_text("ok\n")
        print("=== entrypoint: W&B smoke SUCCESS sentinel written ===", flush=True)
        _cleanup_working()
        _self_delete()
        return

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
            print(
                f"WARN: TTS cache persist failed:\n{traceback.format_exc()}", flush=True
            )
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
