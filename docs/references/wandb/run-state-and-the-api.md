# Run state and the public API

The Public API (`wandb.Api`) is how the local orchestrator (`scripts/runpod-train`) finds out whether the GPU pod's training job has finished, without SSH-polling a sentinel file inside the container.

## The state enum

`wandb.Api().run("entity/project/run_id").state` returns one of:

| State | Meaning | Transition trigger |
|---|---|---|
| `pending` | Run is scheduled but hasn't started executing. | Common in Sweeps and Launch jobs; rare for direct `wandb.init()`. |
| `running` | Run is alive — sent a heartbeat recently. | Active training. |
| `finished` | Run ended cleanly. | `wandb.finish()` called with no exit code (or `exit_code=0`). |
| `failed` | Run ended with a non-zero exit status. | `wandb.finish(exit_code=1)` (or auto via `__exit__` on uncaught exception). |
| `crashed` | Run stopped sending heartbeats. | Process killed (SIGKILL, OOM kill, machine crash) — server marks crashed after the heartbeat timeout. |
| `killed` | Run was forcibly stopped before it could finish. | Sweep cancellation; Launch cancellation; manual stop in UI. |

(Source: https://docs.wandb.ai/models/runs/run-states/.)

The four terminal states from the orchestrator's POV are `finished`, `failed`, `crashed`, and `killed`. Anything else means "keep polling".

```python
TERMINAL = {"finished", "failed", "crashed", "killed"}
```

### `failed` vs. `crashed` — why this matters for the harness

- `failed` is **immediate**: the trainer called `wandb.finish(exit_code=1)`, the server flips state synchronously, the orchestrator's next poll sees the answer.
- `crashed` is **delayed**: the trainer process died without calling finish; the server waits for the heartbeat timeout (~5 min, observed; not contractual) before flipping state.

The harness should structure its `entrypoint.py` to reach `failed` on every controllable error path — see [init-log-finish.md](init-log-finish.md) for the bullet-proof try/finally pattern. Reserve `crashed` for actual kernel/hardware failures.

## Polling pattern

```python
import time
import wandb

POLL_EVERY_S = 30
TERMINAL = {"finished", "failed", "crashed", "killed"}

def wait_for_run(entity: str, project: str, run_id: str, deadline_s: float) -> str:
    api = wandb.Api(timeout=30)
    path = f"{entity}/{project}/{run_id}"
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline:
        api.flush()                          # invalidate the local Run cache
        run = api.run(path)
        state = run.state
        if state in TERMINAL:
            return state
        time.sleep(POLL_EVERY_S)
    raise TimeoutError(f"run {path} did not finish in {deadline_s}s")
```

### Why `api.flush()` matters

`wandb.Api()` caches `Run` objects in memory. A second call to `api.run(...)` for the same path returns the **cached** object, including a stale `state`. Without `api.flush()` you'll spin forever waiting for the cached `running` to flip.

(Source: https://docs.wandb.ai/models/ref/python/public-api/api/ — "the api object keeps a local cache of runs," and the docs explicitly recommend `api.flush()` to invalidate.)

### Polling cadence

- 20–30 s is the right cadence. The training run is 30–90 min; you don't need sub-second granularity.
- The Public API has rate limits; aggressive polling (every second) can earn you a 429. Stay >=10 s between polls.
- Don't bother with exponential backoff for this use case — the cadence is bounded by your patience for end-of-run detection latency, not by API cost.

## Getting metrics out post-run

Beyond `.state`, the `Run` object exposes:

```python
run = api.run("entity/project/run_id")

# Scalar summary (the auto-mirrored "last value" of every logged metric, plus manual run.summary[...] writes)
print(run.summary["best_f1"])
print(run.summary["val/recall"])

# Full history (time series of every wandb.log call). Returns a pandas DataFrame.
history = run.history(keys=["train/loss", "val/f1"], samples=10000)

# Memory-friendly streaming form for very long runs
for row in run.scan_history(keys=["train/loss"]):
    ...

# Config (frozen hyperparams from wandb.init(config=...))
print(run.config["learning_rate"])

# Artifacts produced by this run
for art in run.logged_artifacts():
    print(art.name, art.aliases)
```

(Source: https://docs.wandb.ai/models/ref/python/public-api/api/.)

For the harness's "did the trained model beat the production baseline?" gate, the pattern is:

1. Wait for `state == "finished"`.
2. Pull `run.summary["val/best_f1"]` (the trainer's manually-set summary key).
3. Compare against `Api().artifact("entity/project/hey-claudia-model:production").metadata["val_f1"]`.
4. If new ≥ prod by some margin, link the new artifact with the `production` alias (see [artifacts.md](artifacts.md)).

## Webhooks vs polling

W&B project-level **Automations** can fire a webhook on run-state transitions (Pro/Enterprise feature; multi-tenant cloud only). For the harness's solo-researcher OSS path, **polling is the right answer**: no infrastructure to host a webhook receiver, no Pro tier required.

(Source: https://docs.wandb.ai/models/automations/ — "Run metric automations and run metrics z-score change automations are currently supported only in W&B Multi-tenant Cloud" and require Pro/Enterprise.)

If the harness graduates to a multi-user setup, swap polling for an Automations webhook → small FastAPI receiver → notifies the orchestrator. Until then, polling stays.

## Sources

- https://docs.wandb.ai/models/runs/run-states/
- https://docs.wandb.ai/models/ref/python/public-api/api/
- https://docs.wandb.ai/models/automations/
- https://github.com/wandb/wandb/issues/1526 (community report of ~2h heartbeat-to-crashed timing — non-authoritative; the docs do not specify the timeout)
