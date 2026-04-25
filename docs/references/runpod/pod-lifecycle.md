# Pod lifecycle

The full flow for a one-shot training job:

```
POST /v1/pods                  -> 201, body has pod.id
GET  /v1/pods/{pod.id}         -> poll until desiredStatus == "EXITED"
scp -P <port> root@<ip>:...    -> pull artifacts (see artifacts.md)
DELETE /v1/pods/{pod.id}       -> reclaim resources
```

Source: https://docs.runpod.io/api-reference/openapi.json (`/pods` endpoint family).

## Status enum

`GET /v1/pods/{podId}` returns a Pod object whose runtime state is in **`desiredStatus`**, with three values:

| Value | Meaning |
|---|---|
| `RUNNING` | Pod has been requested up. The container is booting or has booted and is running. |
| `EXITED` | Container has exited (your `dockerStartCmd` returned, or it crashed). The Pod is still leased — billing for storage continues. |
| `TERMINATED` | Pod has been deleted. Volume disk is gone. |

Source: https://docs.runpod.io/api-reference/pods/GET/pods (response schema).

There is **no `exitCode`** field. There is **no `containerStatus`** field. The REST API does not surface whether your script returned 0 or non-zero. To distinguish success from crash, write a sentinel from inside your training entrypoint:

```python
# at end of train.py
Path("/workspace/out/SUCCESS").touch()
```

…then check for `/workspace/out/SUCCESS` after `desiredStatus == "EXITED"` (read it via SSH or just attempt SCP and treat absence as failure).

## "Phantom RUNNING" gotcha

`desiredStatus` is the **desired** state — i.e. what you asked for, not what's actually true on the host right now. A Pod whose container OOM-killed or crash-looped will still show `RUNNING` for a window before the platform marks it `EXITED`. Two consequences:

1. Don't poll faster than ~10–20 s. The state machine has lag; faster polling just burns API quota.
2. **Always cap your polling with a wall-clock timeout** (e.g. 2× expected training duration). If the timeout fires, force `DELETE /pods/{id}` and treat it as a failure — don't trust `desiredStatus` to eventually flip.

Source: this is empirical from `desiredStatus` being a "desired" field in the schema (https://docs.runpod.io/api-reference/pods/POST/pods response), not a "current" field; the docs at https://docs.runpod.io/pods/manage-pods explicitly call out troubleshooting "ensure you have an idle job (e.g., `sleep infinity`)" which is a tell that container-level health and Pod-level state can drift.

## Why we use `EXITED`, not `RUNNING → not-listed`

The Pod **stays in the system** after the container exits. A successful run lands in `EXITED`, *not* deleted. This is RunPod's storage-revenue contract: they keep your `/workspace` around (and bill volume disk at $0.20/GB-month) until you `DELETE`. (Source: https://docs.runpod.io/pods/storage/types — "Volume disk … is retained throughout the Pod's lease" and https://docs.runpod.io/pods/pricing — stopped/exited volume rate is $0.20/GB-month.)

So the polling loop watches for `EXITED`, then proceeds to artifact retrieval, then `DELETE`. **Never skip the `DELETE`** — a forgotten exited Pod will accrue storage forever.

## REST endpoint cheat sheet

All under `https://rest.runpod.io/v1/`:

| Method | Path | Use |
|---|---|---|
| `POST` | `/pods` | Create. Returns `201` with body `{id, name, image, desiredStatus, ...}`. See [rest-api-pods.md](rest-api-pods.md) for body. |
| `GET` | `/pods/{podId}` | Read one. Use this for polling. |
| `GET` | `/pods` | List. Useful for "find any leftover pods to clean up". |
| `POST` | `/pods/{podId}/start` | Start a stopped pod. Not used in one-shot flow. |
| `POST` | `/pods/{podId}/stop` | Stop. **Don't use** for end-of-run cleanup — use `DELETE`. |
| `POST` | `/pods/{podId}/restart` | Restart. Not used. |
| `POST` | `/pods/{podId}/reset` | Reset to initial. Not used. |
| `PATCH` | `/pods/{podId}` | Modify post-create (image, env, ports). Not used in one-shot flow. |
| `DELETE` | `/pods/{podId}` | Terminate. **Use this in `finally:`.** |

Source: https://docs.runpod.io/api-reference/openapi.json.

## Polling cadence

Match the existing Kaggle pattern (~20 s) — that's a good default for RunPod too:

```python
import time, httpx
while True:
    r = httpx.get(f"https://rest.runpod.io/v1/pods/{pod_id}",
                  headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    status = r.json()["desiredStatus"]
    if status in ("EXITED", "TERMINATED"):
        break
    if time.monotonic() - start > MAX_WALL_S:
        # bail out: force DELETE in caller's finally
        raise TimeoutError("training pod exceeded budget")
    time.sleep(20)
```

## Sources

- https://docs.runpod.io/api-reference/openapi.json
- https://docs.runpod.io/api-reference/pods/POST/pods
- https://docs.runpod.io/api-reference/pods/GET/pods
- https://docs.runpod.io/pods/manage-pods
- https://docs.runpod.io/pods/storage/types
- https://docs.runpod.io/pods/pricing
