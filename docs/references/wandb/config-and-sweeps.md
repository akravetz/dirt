# Config and Sweeps

Two related but distinct concepts:

- **`wandb.config`** is **per-run hyperparameter capture** — what knobs did this run use?
- **W&B Sweeps** is **multi-run hyperparameter search** — try many combinations of those knobs across many runs, find the best.

The auto-research harness uses `wandb.config` for sure. Whether it uses Sweeps is a design call (see "When to use Sweeps" below).

## `wandb.config`

A dict-like object scoped to one run. Set at init, accessed throughout, frozen by default.

```python
config = {
    "learning_rate": 1e-3,
    "batch_size": 64,
    "lstm_dim": 96,
    "n_steps": 50_000,
    "data_revision": "2026-04-23",
    "harness_rev": "a1b2c3d",
}
with wandb.init(project="dirt-wake-word", config=config) as run:
    lr = run.config["learning_rate"]
    # or: lr = run.config.get("learning_rate", 1e-3)

    # Update a config value mid-run (rare; usually a code smell)
    run.config.update({"actual_n_steps": actual_steps_run}, allow_val_change=True)
```

(Source: https://docs.wandb.ai/models/track/config/.)

### Best practices

- **Snapshot upstream context**, not just hyperparams: data revision, fixture path, git SHA of the training repo. The "what produced this run?" question is answered by `config`.
- **Use underscores or dashes in keys, not periods.** Periods get interpreted as nested-key access in the UI. (Source: https://docs.wandb.ai/models/track/config/.)
- **Reserve `wandb.log` for dependent variables** (loss, accuracy, F1) and `wandb.config` for independent variables (hyperparams). Don't log a hyperparameter as a metric.
- **One harness run, one `wandb.init(config=...)` call.** Don't try to share config across runs by mutation; each run gets its own snapshot.

### `allow_val_change=True`

By default, `run.config["lr"] = new_lr` raises if `lr` was already set. To explicitly allow late updates:

```python
run.config.update({"lr": new_lr}, allow_val_change=True)
```

Useful for "the harness picked up a different `n_steps` than configured because of early stopping" — record the actual value, not the requested one.

## W&B Sweeps

Sweeps coordinate N runs across one or more workers, each with a distinct hyperparameter combination, and pick the best by some metric.

### Sweep config (YAML or dict)

```yaml
program: train.py                    # the script to run
method: bayes                        # grid | random | bayes
metric:
  name: val/f1
  goal: maximize
parameters:
  learning_rate:
    distribution: log_uniform_values
    min: 1e-5
    max: 1e-2
  lstm_dim:
    values: [64, 96, 128, 192]
  batch_size:
    values: [32, 64, 128]
early_terminate:
  type: hyperband
  s: 2
  eta: 3
  max_iter: 27
```

(Source: https://docs.wandb.ai/models/sweeps/define-sweep-configuration/.)

### Top-level keys

| Key | What it does |
|---|---|
| `program` | The Python script the agent will run for each trial. |
| `method` | Search strategy: `grid` (exhaustive), `random` (uniform sampling), `bayes` (Bayesian-opt). |
| `metric.name` | The W&B metric the search optimizes — must match a `run.log()` key (e.g. `"val/f1"`). |
| `metric.goal` | `maximize` or `minimize`. |
| `parameters.<name>` | One sub-block per hyperparameter. |
| `early_terminate.type` | `hyperband` is the only supported algorithm; aggressive early stopping for unpromising trials. |
| `command` | Optional; override how the agent invokes the program (e.g. add CLI args via `${parameter_name}` macros). |

### Parameter formats

| Form | Use case |
|---|---|
| `value: X` | Fixed constant (still recorded for cross-run comparison). |
| `values: [X, Y, Z]` | Discrete choices. |
| `distribution: uniform` + `min` / `max` | Continuous range. |
| `distribution: log_uniform_values` + `min` / `max` | Log-scale range (use for learning rate). |
| `distribution: q_log_uniform_values` + `min` / `max` + `q` | Quantized log scale (e.g. integer dimensions). |

### Running a sweep

```python
import wandb

sweep_id = wandb.sweep(sweep_config_dict, project="dirt-wake-word")
# sweep_id is a short string like "abc12def"

# Then start agents (each runs N trials)
wandb.agent(sweep_id, function=train_one_trial, count=20)
```

Inside `train_one_trial()`, call `wandb.init()` with no `config=` — the sweep agent injects the trial's hyperparams into `wandb.config` automatically:

```python
def train_one_trial():
    with wandb.init() as run:
        lr = run.config.learning_rate     # injected by the sweep
        ...
        run.log({"val/f1": f1})           # the sweep reads this for ranking
```

CLI form:

```sh
wandb sweep --project dirt-wake-word sweep.yaml      # prints sweep_id
wandb agent <entity>/<project>/<sweep_id>            # blocks, runs trials
```

(Source: https://docs.wandb.ai/models/sweeps/.)

## When to use Sweeps vs. hand-rolling

**Use Sweeps when:**
- Searching across multiple **independent training runs**, each with a different hyperparam combination.
- You want distributed search — start agents on multiple machines, all pulling from the same sweep queue.
- You want Bayesian opt or Hyperband early-termination "for free".
- The metric you're optimizing is logged with `run.log(...)` from a normal training run.

**Hand-roll (don't use Sweeps) when:**
- You want to evaluate N **checkpoints from one training run** (this is what `select_best_by_real_f1()` does — it's a `wandb.Table`, not a sweep).
- You want to threshold-sweep a **single trained model** (also a `wandb.Table`, not a sweep).
- You want to chain runs (run A produces an artifact run B consumes) with branching logic — Sweeps is for parallel search, not pipelines.
- The "harness" coordinator already exists (which it will, for the auto-research workflow) — duplicating the orchestration in two places is worse than one custom orchestrator that reads `Api().runs(filters={...})`.

For the wake-word harness specifically:

- **Inner candidate selection** (different checkpoints + thresholds for one trained model) → `wandb.Table`. NOT a Sweep.
- **Outer hyperparameter search** (different `lstm_dim`, different `learning_rate`, etc., each requiring a fresh training run) → either Sweeps or a custom orchestrator. If the harness already has a custom orchestrator (`scripts/runpod-train` + the per-trial pod-create), use that — Sweeps adds another coordinator that fights with yours.

## `define_metric` for custom x-axes

Useful when the natural x-axis is "epoch" or "samples_seen", not the auto-incrementing step:

```python
run.define_metric("epoch")
run.define_metric("val/*", step_metric="epoch")        # all val/ metrics use epoch as x

run.define_metric("train/loss", summary="min")         # the run summary captures min loss
run.define_metric("val/f1", summary="max")             # captures max F1
```

(Source: https://docs.wandb.ai/models/track/log/customize-logging-axes/.)

The `summary="best"` form is **deprecated** since 0.17.9 — use `summary="min"` or `summary="max"` with the appropriate goal. ([CHANGELOG](https://github.com/wandb/wandb/blob/main/CHANGELOG.md))

## Sources

- https://docs.wandb.ai/models/track/config/
- https://docs.wandb.ai/models/sweeps/
- https://docs.wandb.ai/models/sweeps/define-sweep-configuration/
- https://docs.wandb.ai/models/track/log/customize-logging-axes/
