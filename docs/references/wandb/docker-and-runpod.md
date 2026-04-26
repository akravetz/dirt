# Docker and RunPod

Running the W&B SDK inside the wake-word trainer's Docker container on a RunPod GPU pod. Most of this is "set the right env vars and don't fight the SDK"; one section is the exit-code dance that interacts with RunPod's lifecycle.

## Env vars to set in the Dockerfile (image-layer, baked)

```dockerfile
# Trainer Dockerfile
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04 AS base
# ... install python, deps ...

ENV WANDB_PROJECT=dirt-wake-word \
    WANDB_DIR=/workspace/wandb \
    WANDB_SILENT=true \
    WANDB_CONSOLE=off

# WANDB_API_KEY is intentionally NOT set here — injected at runtime via RunPod's env block.
```

Why these:

- **`WANDB_PROJECT=dirt-wake-word`** — saves having to pass `project=` on every `wandb.init` call.
- **`WANDB_DIR=/workspace/wandb`** — the SDK stages local logs (history, config, system metrics) to `$WANDB_DIR/wandb/run-<id>` before upload. `/workspace` is the RunPod **volume disk** mount; it survives across container restarts (until pod delete) and is what you SCP off if you need post-mortem state.
- **`WANDB_SILENT=true`** — suppresses the SDK's "View run at https://..." banner and progress chatter. Keeps `journalctl --user -u dirt-voice -f` (or the RunPod console) readable.
- **`WANDB_CONSOLE=off`** — tells the SDK not to capture stdout/stderr and re-emit it to the W&B run's "logs" tab. The RunPod stdout is already captured by RunPod itself; double-piping is wasteful and creates noise.

## Env vars to inject at pod-create (per-invocation)

In the RunPod `POST /pods` body:

```json
{
  "env": {
    "WANDB_API_KEY": "<from local .env>",
    "WANDB_RUN_GROUP": "auto-research-2026-04-25-1430",
    "WANDB_NAME": "candidate-7"
  }
}
```

Why per-invocation:

- **`WANDB_API_KEY`** — the secret. Never bake into the image (image is pushed to GHCR; key would leak). Inject from the local orchestrator's `.env`.
- **`WANDB_RUN_GROUP`** — varies per harness session. The orchestrator decides which "research session" each pod belongs to.
- **`WANDB_NAME`** — optional; useful for human-readable run names like `candidate-7`. Without it, W&B generates `crisp-paper-42`-style names.

## The exit-code dance

RunPod's pod state machine is independent from W&B's run state machine. The orchestrator will see **two** signals:

| Signal source | What it tells you |
|---|---|
| `wandb.Api().run(...).state` | Did the trainer reach a terminal W&B state? (`finished` / `failed` / `crashed`) |
| `GET /pods/{id}` `.desiredStatus` | Did the container exit? (`RUNNING` / `EXITED`) |

Ideally these agree:

| Trainer outcome | W&B state | RunPod desiredStatus |
|---|---|---|
| Clean success, `wandb.finish(0)` called | `finished` | `EXITED` |
| Caught exception, `wandb.finish(1)` called, then `sys.exit(1)` | `failed` | `EXITED` |
| Uncaught exception, `__exit__` calls `wandb.finish(1)`, Python exits 1 | `failed` | `EXITED` |
| OOM kill / SIGKILL | `crashed` (after heartbeat timeout) | `EXITED` |
| Trainer hangs forever | `running` | `RUNNING` |

The harness orchestrator's poll should treat **either** signal as terminal — first-to-fire wins:

```python
def is_done(pod_status: str, wandb_state: str) -> bool:
    return pod_status == "EXITED" or wandb_state in {"finished", "failed", "crashed", "killed"}
```

In practice, if the trainer's `entrypoint.py` is well-behaved (see [init-log-finish.md](init-log-finish.md) for the bullet-proof pattern), W&B will reach `finished` or `failed` ~5–30 s before the pod EXITED state. Use whichever the orchestrator polls first.

## `wandb.finish()` blocks on upload

The SDK uploads run history asynchronously via the `wandb-core` background process (formerly `wandb-service`; the rename happened in 0.18.x). On `wandb.finish()`, the foreground waits for the background process to flush.

Implications:

- **Don't `kill -9` the trainer** — last few seconds of metrics will be lost. Use SIGTERM, let `__exit__` / explicit `finish` run.
- **`finish` can take 5–60 s** depending on how much pending history there is. Budget for it in the orchestrator's wall-clock deadline.
- **`finish` can fail to upload** if the network is dead. The local `$WANDB_DIR/wandb/run-*` directory still has the run; you can `wandb sync /workspace/wandb/run-<id>` later from a machine with connectivity.

(Source: https://docs.wandb.ai/models/ref/python/functions/finish/.)

## Offline mode

For a pod with no outbound internet (rare on RunPod, but possible behind some firewalled configs):

```bash
ENV WANDB_MODE=offline
```

The SDK writes everything to `$WANDB_DIR/wandb/offline-run-<id>/` and never attempts upload. To sync after the pod is back online:

```sh
# After SCP'ing /workspace/wandb back to the local machine
wandb sync /local/wandb/offline-run-<id>
# or sync everything
wandb sync --sync-all /local/wandb/
```

(Source: https://docs.wandb.ai/models/ref/cli/wandb-offline/.)

For the harness's online polling design, **offline mode breaks the design**: the orchestrator can't poll `Api().run().state` because the run never exists on the server until sync runs. Use offline mode only as a fallback when online genuinely fails; don't make it the default.

## SIGTERM handling

RunPod sends SIGTERM when you `DELETE /pods/{id}` while the container is still running. The Python default behavior is to raise `KeyboardInterrupt`, which propagates through `with wandb.init()` and triggers `wandb.finish(exit_code=1)`. State on the server: `failed`. This is the right behavior — the orchestrator sees the failure cleanly.

If you've installed your own SIGTERM handler (rare), make sure it gives the W&B finish path enough time:

```python
import signal

def _shutdown(signum, frame):
    if wandb.run is not None:
        wandb.finish(exit_code=143)   # 128 + 15 (SIGTERM); marks state=failed
    raise SystemExit(143)

signal.signal(signal.SIGTERM, _shutdown)
```

## Disk usage inside the container

`$WANDB_DIR/wandb/` grows over the run:

| Subdirectory | Contents | Size order |
|---|---|---|
| `run-<id>/files/` | Saved code, config.yaml, requirements.txt | KB |
| `run-<id>/logs/` | SDK debug logs | KB–MB |
| `run-<id>/tmp/` | Pre-upload spool of metrics | depends on log frequency; usually MB |
| `run-<id>/media/` | Tables, images, plots staged for upload | KB |

For a 90-min training run with `run.log()` every 100 steps, expect ~10–50 MB. Well below RunPod's 50 GB container disk default. Don't bother with cleanup.

## Sources

- https://docs.wandb.ai/models/track/environment-variables/
- https://docs.wandb.ai/models/ref/python/functions/finish/
- https://docs.wandb.ai/models/ref/cli/wandb-offline/
- https://github.com/wandb/wandb/blob/main/CHANGELOG.md (0.18.x `wandb-core` rename, 0.20.0 `WANDB_DISABLE_SERVICE` removal)
