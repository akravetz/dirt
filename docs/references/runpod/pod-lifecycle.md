# Pod lifecycle

The full flow for a one-shot training job:

```
POST /v1/pods                              -> 201, body has pod.id
HEAD s3://<vol>/out/<pod.id>/SUCCESS|FAILURE -> poll until one appears
[S3 download s3://<vol>/out/<pod.id>/]     -> pull artifacts
DELETE /v1/pods/{pod.id}                   -> tear down + reclaim resources
```

Source: https://docs.runpod.io/api-reference/openapi.json (`/pods` endpoint family) + https://docs.runpod.io/serverless/storage/s3-api (Network Volume S3 access).

## Critical: `desiredStatus` is user-intent, NOT container state

This is empirically demonstrated and contradicts what the early version of this doc claimed. **`desiredStatus` is the state YOU want the pod in, not the state the container is in.** It does not transition on its own when the container exits.

| Value | Meaning |
|---|---|
| `RUNNING` | You asked for the pod to be up. RunPod keeps the container alive and **auto-restarts it on any exit** (exit-0 included) until you ask otherwise. |
| `EXITED` | You explicitly stopped the pod (e.g. via `POST /pods/{id}/stop`). |
| `TERMINATED` | You DELETEd the pod. It's gone. |

What this means for orchestration: **you cannot poll `desiredStatus` to detect "training finished."** The container will exit cleanly, RunPod will auto-restart it, your training script will run a SECOND time, your trained-model artifacts (already on the volume) will be overwritten, and your wallet will keep emptying. We learned this empirically — see W&B group `phase1-final-20260426-201259` where two runs (`m1f811ys` finished, `e8xl0tiz` running) were created from a single orchestrator submission because the orchestrator was polling `desiredStatus=EXITED` (which never fires).

There is **no `exitCode`** field, **no `containerStatus`** field, **no `lastExitedAt`** field exposed by the REST API.

## The right signal: a sentinel on the volume, polled via S3

The training entrypoint writes `out/<RUNPOD_POD_ID>/SUCCESS` (or `FAILURE` with a traceback) to the Network Volume. The orchestrator polls the volume's S3 endpoint for that key:

```python
from botocore.exceptions import ClientError
import time

while time.monotonic() < deadline:
    for sentinel in ("SUCCESS", "FAILURE"):
        try:
            s3.head_object(Bucket=volume_id, Key=f"out/{pod_id}/{sentinel}")
            break  # found it
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("404", "NoSuchKey"):
                raise
    else:
        time.sleep(30)
        continue
    break
# now S3-download out/<pod_id>/ and DELETE the pod
```

The volume is the durable substrate; it persists across pod restarts and is accessible via S3 even when no pod is mounting it. See [artifacts.md](artifacts.md) for the S3 endpoint format.

## Why DELETE matters

The Pod stays leased after the container exits. A "stopped" pod still bills volume disk at $0.20/GB-month. **Always `DELETE` in a `finally:` block** — a forgotten pod accrues storage forever. (Source: https://docs.runpod.io/pods/storage/types, https://docs.runpod.io/pods/pricing.)

DELETE is also what actually stops the container. RunPod's container runtime keeps the container alive (auto-restarting on exit) for as long as the pod is leased.

## Defense-in-depth: self-DELETE from inside the container

Orchestrator-side `finally: DELETE` is necessary but not sufficient: if the orchestrator process dies mid-run (we've seen this — KeyboardInterrupt from a sibling process, OOM, ssh disconnect, etc.), the pod runs unsupervised at $0.34/h until something else cleans up.

Defense: pass `RUNPOD_API_KEY` into the container's env block on `POST /pods`, and have the entrypoint issue `DELETE /pods/<self_pod_id>` as the last step before exit (after the volume artifacts are written). DELETE-on-already-gone is idempotent (orchestrator's finally returns 404, swallow as success).

Additionally: the entrypoint should **quick-exit if `out/<pod_id>/SUCCESS` or `out/<pod_id>/FAILURE` already exists** at the top of `main()`. RunPod auto-restarts the container on exit; without this guard, a successful run that writes SUCCESS triggers a restart that re-runs training (or FATAL'd in our case on a partial-cache state). Quick-exit + self-DELETE in the quick-exit branch closes the loop in the case where the orchestrator missed its first poll window.

## Account-level spend cap

Set at https://www.console.runpod.io/user/billing — console-only (no REST API). The default $80/hr account-wide cap is hard; raising requires a support ticket (https://contact.runpod.io/). Tighten as much as your budget tolerates; this is the last-line backstop if both the orchestrator and the in-container self-DELETE fail.

## Race window

Between the moment the entrypoint writes SUCCESS to the volume and the moment the orchestrator polls + DELETEs, RunPod may auto-restart the container. With a 30 s poll interval, the race window is ≤ 30 s — at GPU rates that's a few cents of wasted compute. Negligible. (Don't poll faster — the API has rate limits and a faster cadence doesn't materially shrink the cost.)

## REST endpoint cheat sheet

All under `https://rest.runpod.io/v1/`:

| Method | Path | Use |
|---|---|---|
| `POST` | `/pods` | Create. Returns `201` with body `{id, name, image, desiredStatus, ...}`. See [rest-api-pods.md](rest-api-pods.md). |
| `GET` | `/pods/{podId}` | Read one. Useful for diagnostics, **not** for completion polling. |
| `GET` | `/pods` | List. Useful for "find any leftover pods to clean up". |
| `POST` | `/pods/{podId}/stop` | Stop. **Don't use** for end-of-run cleanup — leaves the volume disk billing. Use `DELETE`. |
| `DELETE` | `/pods/{podId}` | Terminate. **Use this in `finally:`.** |

Other endpoints (`/start`, `/restart`, `/reset`, `PATCH`) are not used in the one-shot flow.

## Sources

- Empirical: pod `xqwcy9djxraai9` (2026-04-27, group `phase1-final-20260426-201259`) demonstrated container auto-restart on clean exit while `desiredStatus` stayed `RUNNING`.
- https://docs.runpod.io/api-reference/openapi.json
- https://docs.runpod.io/api-reference/pods/POST/pods
- https://docs.runpod.io/api-reference/pods/GET/pods
- https://docs.runpod.io/pods/manage-pods
- https://docs.runpod.io/pods/storage/types
- https://docs.runpod.io/pods/pricing
- https://docs.runpod.io/serverless/storage/s3-api
