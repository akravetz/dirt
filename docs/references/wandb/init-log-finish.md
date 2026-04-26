# init / log / finish — the trinity

The three calls that bracket every W&B run.

## `wandb.init(...) -> wandb.Run`

Returns a `Run` object; also assigned to `wandb.run` as a module-level singleton. The recommended modern shape is the **context manager**:

```python
import wandb

with wandb.init(
    project="dirt-wake-word",
    entity="akravetz",
    name=f"train-{run_timestamp}",
    group=os.environ["WANDB_RUN_GROUP"],     # bundle harness runs together
    job_type="train",
    config={"learning_rate": 1e-3, "n_steps": 50_000, "lstm_dim": 96},
    tags=["wake-word", "v5", "auto-research"],
    notes="Auto-research candidate, harness rev a1b2c3d.",
) as run:
    train(run)
    # run.finish() called automatically on __exit__, with exit_code=1 on exception
```

(Source: https://docs.wandb.ai/models/ref/python/experiments/run/ — the context-manager form is the recommended pattern; `finish()` is called on exit.)

### Useful kwargs (for the auto-research harness)

| Kwarg | What it does | Notes |
|---|---|---|
| `project` | Project under which the run lives. | Use `"dirt-wake-word"`. Auto-creates if missing. |
| `entity` | Username / team. | Defaults to your personal account. |
| `name` | Display name. | If not set, W&B generates a fun name (e.g. `crisp-paper-42`). Set this for harness traceability. |
| `group` | Run group. | The harness should bundle each "research session" of N runs under one `group`. Filterable in the UI; queryable via the public API. |
| `job_type` | Sub-label within a group. | E.g. `"train"`, `"validate"`, `"select_best"`. |
| `config` | Hyperparameters. | dict, YAML path, or argparse Namespace. Frozen after init unless `allow_val_change=True`. |
| `tags` | List of strings. | Cheap filter axis in the UI. |
| `notes` | Markdown. | Use for human context: "harness rev <git-sha>, fixture <data-rev>". |
| `mode` | `"online"` / `"offline"` / `"disabled"` / `"shared"`. | Default `online`. See [docker-and-runpod.md](docker-and-runpod.md). |
| `dir` | Where the SDK stages files. | Set to `/workspace/wandb` inside the RunPod container so it lands on the volume disk. |
| `id` | Globally unique within project. | Required for `resume`. Max 64 chars. Use UUID4 if you want to reattach. |
| `resume` | `"never"` (default) / `"allow"` / `"must"` / `"auto"`. | For preempt-restart. The harness probably doesn't need this. |
| `settings` | `wandb.Settings(...)` for advanced knobs. | E.g. `Settings(quiet=True, console="off")`. |
| `save_code` | Save the entrypoint .py. | Default depends on settings; explicit `True` for reproducibility. |

(Source: https://docs.wandb.ai/ref/python/init/.)

### Things to NOT pass

- `anonymous=True` — emits a deprecation warning since 0.23.1; not what you want for an authenticated harness.
- `magic=True` — best-effort autotelemetry; opaque, hard to debug.
- `sync_tensorboard=True` — only if you're already writing TensorBoard event files. The harness writes wandb directly.

## `wandb.log(data, *, step=None, commit=None) -> None`

The workhorse. Append metrics to the current run.

```python
# Per training step (auto-incrementing step counter)
for step in range(n_steps):
    loss = train_step(...)
    run.log({"train/loss": loss, "train/lr": optimizer.param_groups[0]["lr"]})

# Per validation pass — bundle multiple metrics into the same step
val_recall, val_precision, val_f1 = evaluate(...)
run.log({
    "val/recall": val_recall,
    "val/precision": val_precision,
    "val/f1": val_f1,
})
```

(Source: https://docs.wandb.ai/models/track/log/.)

### Step semantics — read this once

- **Default**: each `log()` call advances the step counter by 1. The step is implicit; you don't pass it.
- **Explicit step**: `log({...}, step=N)` only writes if `N == current_step` or `N == current_step + 1`. Lower → silently dropped. Higher → fast-forwards. The docs are explicit: "It is not possible to write to a specific history step." (Source: https://docs.wandb.ai/models/track/log/.)
- **Custom x-axis**: when "step" doesn't match your domain (e.g. you want to plot against `epoch` not `step`), use `run.define_metric()`:

  ```python
  run.define_metric("epoch")
  run.define_metric("val/*", step_metric="epoch")
  for epoch in range(20):
      ...
      run.log({"epoch": epoch, "val/f1": f1})
  ```

- **`commit=False` is NOT "don't write"**. It means "buffer this in the same step; flush on the next `log()` call (which defaults to `commit=True`) or on `finish()`". Use it only when you have multiple sub-modules contributing metrics at the same step:

  ```python
  run.log({"train/loss": loss}, commit=False)        # buffered
  run.log({"train/grad_norm": grad_norm}, commit=False)  # still buffered, same step
  run.log({"train/lr": lr})                           # commit=True default → flushes all three at this step
  ```

  A single `commit=False` call followed by no other `log()` for that step → metrics never flush until `finish()`. Common bug.

### `run.summary` vs. `run.log`

- `run.log(...)` writes to history (a time series).
- The most-recent value of each scalar in history is **automatically** mirrored to `run.summary` — you don't have to do anything.
- For a value that doesn't naturally fit a step (e.g. "the F1 of the best checkpoint, chosen post-hoc"), assign manually: `run.summary["best_f1"] = best_f1`.
- `run.summary` is what shows up in the **runs table** (the project's tabular comparison view); history is what shows up in **charts**. (Source: https://docs.wandb.ai/models/track/log/log-summary/.)

## `wandb.finish(exit_code=None, quiet=None) -> None`

Closes the run. Flushes any pending `log()` data, uploads the local `wandb/` dir, and transitions the run to a terminal state on the server side.

```python
wandb.finish(exit_code=0)   # marks state=finished
wandb.finish(exit_code=1)   # marks state=failed
```

(Source: https://docs.wandb.ai/models/ref/python/functions/finish/.)

### Behavior matrix

| How the script ends | Run state on the server | Exit code seen by the orchestrator |
|---|---|---|
| Context manager exits cleanly | `finished` | 0 |
| Context manager exits via uncaught exception | `failed` | 1 (auto, via `__exit__`) |
| Explicit `wandb.finish(exit_code=0)` | `finished` | 0 |
| Explicit `wandb.finish(exit_code=1)` | `failed` | 1 |
| Process dies (SIGKILL, OOM kill, machine crash) | `crashed` (after heartbeat timeout) | — |
| Script hangs but never calls finish | `running` (forever, until heartbeat times out) | — |

The crashed-state heartbeat timeout is on the order of minutes (5 min is a commonly observed value, but the docs do not guarantee a number). For the harness's external poll, **always prefer the explicit `failed` transition** — the orchestrator gets the answer immediately instead of waiting for a heartbeat-based mark.

(Source for the state enum: https://docs.wandb.ai/models/runs/run-states/.)

### The bullet-proof entrypoint pattern

For `apps/wake-word/docker/entrypoint.py`:

```python
import sys
import wandb

def main():
    run = wandb.init(...)        # do NOT use context manager here — we want explicit control
    try:
        train(run)
        wandb.finish(exit_code=0)
        sys.exit(0)
    except SystemExit:
        raise
    except BaseException as exc:
        # Log the failure to W&B before the run is torn down
        try:
            run.alert(title="Trainer crashed", text=repr(exc), level="ERROR")
        except Exception:
            pass
        wandb.finish(exit_code=1)
        raise            # propagate so Docker exits non-zero too
```

Why explicit `try/except` instead of the context manager: we want the `run.alert(...)` to fire on crash, and we want to control the order of (alert → finish → re-raise). The context manager handles 90% of cases but not the alert hook.

## Sources

- https://docs.wandb.ai/ref/python/init/
- https://docs.wandb.ai/models/ref/python/experiments/run/
- https://docs.wandb.ai/models/track/log/
- https://docs.wandb.ai/models/track/log/log-summary/
- https://docs.wandb.ai/models/ref/python/functions/finish/
- https://docs.wandb.ai/models/runs/run-states/
