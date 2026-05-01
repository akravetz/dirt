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
    WANDB_CONSOLE=redirect

# WANDB_API_KEY is intentionally NOT set here — injected at runtime via RunPod's env block.
```

Why these:

- **`WANDB_PROJECT=dirt-wake-word`** — saves having to pass `project=` on every `wandb.init` call.
- **`WANDB_DIR=/workspace/wandb`** — the SDK stages local logs (history, config, system metrics) to `$WANDB_DIR/wandb/run-<id>` before upload. `/workspace` is the RunPod **volume disk** mount; it survives across container restarts (until pod delete) and is what you SCP off if you need post-mortem state.
- **`WANDB_SILENT=true`** — suppresses the SDK's "View run at https://..." banner and progress chatter. Keeps the RunPod console readable.
- **`WANDB_CONSOLE=redirect`** — default console capture mode. The trainer also passes `wandb.Settings(console="redirect", console_multipart=True, console_chunk_max_seconds=30, console_chunk_max_bytes=512 * 1024)` at `wandb.init()` time. Redirect mode captures stdout/stderr at the file-descriptor level (`os.dup2`), so subprocess output from upstream `train.py` is included. Multipart mode writes timestamped `logs/` chunks and uploads each closed chunk during long runs; this is the agent-readable path for near-real-time logs. The legacy single `output.log` may not be downloadable via the Public API until `wandb.finish()`.

## Console logs for long RunPod jobs

Use explicit `wandb.Settings` rather than relying on environment variables alone:

```python
run = wandb.init(
    job_type="train",
    config=resolved_config,
    settings=wandb.Settings(
        console="redirect",
        console_multipart=True,
        console_chunk_max_seconds=30,
        console_chunk_max_bytes=512 * 1024,
    ),
)
```

Why:

- **`console="redirect"`** captures stdout/stderr at file-descriptor level, including subprocess output. `wrap` patches Python streams and can miss shell/subprocess logs.
- **`console_multipart=True`** avoids the v25 failure mode where `output.log` existed only after `wandb.finish()`.
- **`console_chunk_max_seconds=30`** closes a log chunk every 30 seconds even if the trainer is in a long phase.
- **`console_chunk_max_bytes=512 * 1024`** closes large chunks early at 512 KiB.

When pulling logs mid-run, prefer files under the W&B run's `logs/` namespace. Keep `output.log` support as a post-finish fallback because older runs and non-multipart runs still use it.

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

## Completion signal — the volume sentinel, not `desiredStatus`

**`desiredStatus` is unusable for completion detection.** It's RunPod user-intent, not container state — see [pod-lifecycle.md](../runpod/pod-lifecycle.md). RunPod auto-restarts the container on exit until you DELETE, so polling `desiredStatus=EXITED` never fires.

Two valid completion signals:

| Signal | Source | Latency |
|---|---|---|
| Volume sentinel | `s3.head_object(Bucket=vol, Key=f"out/{pod_id}/SUCCESS|FAILURE")` | seconds (entrypoint writes immediately before `wandb.finish`) |
| W&B run state | `wandb.Api().run(...).state` in `{finished, failed, crashed}` | tens of seconds (wandb-core flushes to server async) |

The volume sentinel is the canonical signal — it's the same artifact channel the orchestrator already uses for SCP. The W&B state is useful as a backup or for sweep-level tracking; for a single-run orchestrator, just poll the sentinel.

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
- https://docs.wandb.ai/models/app/console-logs
- https://docs.wandb.ai/models/ref/python/experiments/settings
- https://docs.wandb.ai/models/ref/python/functions/finish/
- https://docs.wandb.ai/models/ref/cli/wandb-offline/
- https://github.com/wandb/wandb/blob/main/CHANGELOG.md (0.18.x `wandb-core` rename, 0.20.0 `WANDB_DISABLE_SERVICE` removal)
