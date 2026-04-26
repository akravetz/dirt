# Obsolete or trap patterns

Patterns LLMs reach for from training data that are wrong, deprecated, or actively harmful in current `wandb` (>=0.21.x). Each entry cites the version that broke / deprecated it.

## Removed (errors / no-ops)

### `wandb.plots.*`

Removed in **0.17.0**. The whole `wandb.plots` namespace is gone.

```python
# ❌ wandb.plots.confusion_matrix(y_true, y_pred, labels)
# ❌ wandb.plots.matplotlib(plt.gcf())
# ❌ wandb.plots.precision_recall(y_true, y_probas)

# ✅ wandb.plot.confusion_matrix(y_true=..., preds=..., class_names=...)
# ✅ wandb.log({"chart": wandb.plot.line(table, "x", "y")})
```

(Source: https://github.com/wandb/wandb/blob/main/CHANGELOG.md, 0.17.0 release notes.)

### `wandb.beta.workflows`

Removed in **0.24.0**. `log_model()`, `use_model()`, `link_model()` no longer exist.

```python
# ❌ wandb.beta.workflows.log_model(model, "model-name")
# ❌ wandb.beta.workflows.use_model("model-name")
# ❌ wandb.beta.workflows.link_model(model, "registry/collection")

# ✅ art = wandb.Artifact("model-name", type="model")
# ✅ art.add_file("model.onnx")
# ✅ run.log_artifact(art, aliases=["latest", "production"])
# ✅ art.link("registry/collection")
```

(Source: same CHANGELOG, 0.24.0.)

### `WANDB_DISABLE_SERVICE` / `x_disable_service`

Removed in **0.20.0**. Setting either now raises an error. The `wandb-core` background process is mandatory.

```python
# ❌ os.environ["WANDB_DISABLE_SERVICE"] = "true"
# ❌ wandb.Settings(x_disable_service=True)

# ✅ Just don't set anything — service mode is the default and only mode.
```

(Source: same CHANGELOG, 0.20.0. Some training data still treats `WANDB_DISABLE_SERVICE=true` as a "make it run in-process" workaround for headless / Docker contexts. It is not.)

### `wandb.require("legacy-service")`

Removed in **0.21.0**. There is no longer a "legacy" code path.

```python
# ❌ wandb.require("legacy-service")  # raises in 0.21+
```

### `wandb.[catboost,fastai,keras,sklearn,...]` direct imports

Moved in **0.17.0**. Third-party integrations relocated.

```python
# ❌ from wandb.keras import WandbMetricsLogger
# ✅ from wandb.integration.keras import WandbMetricsLogger

# ❌ from wandb.fastai import WandbCallback
# ✅ from wandb.integration.fastai import WandbCallback
```

### `Run.save()` without `glob_str`

Made mandatory in **0.20.0**. The zero-arg form raises.

```python
# ❌ run.save()
# ✅ run.save("checkpoints/*.pt")
```

## Deprecated (still works, will go away)

### `Run` method calls that became properties

Deprecated in **0.19.10**.

```python
# ❌ run.project_name()       → ✅ run.project
# ❌ run.get_url()             → ✅ run.url
# ❌ run.get_project_url()     → ✅ run.project_url
# ❌ run.get_sweep_url()       → ✅ run.sweep_url
```

(Source: CHANGELOG 0.19.10.)

### `wandb.Table.add_row(...)`

Use `add_data(*row)` instead.

```python
# ❌ table.add_row(checkpoint_idx=0, threshold=0.5, f1=0.84)
# ✅ table.add_data(0, 0.5, 0.84)            # positional, in column order
```

### `define_metric(summary='best', goal=...)`

Deprecated in **0.17.9**. Use `summary='min'` / `summary='max'` instead.

```python
# ❌ run.define_metric("val/f1", summary="best", goal="maximize")
# ✅ run.define_metric("val/f1", summary="max")
# ✅ run.define_metric("train/loss", summary="min")
```

### Anonymous mode

Deprecation warning since **0.23.1**.

```python
# ❌ wandb.init(anonymous="allow")     # warns
# ✅ Just authenticate with WANDB_API_KEY.
```

### `Artifact.use_as` parameter

Deprecated in **0.20.0** (related to W&B Launch, not used here).

### `wandb.finish(quiet=True)`

Deprecated kwarg. Use `wandb.Settings(quiet=True)` at init time instead.

```python
# ❌ wandb.finish(exit_code=0, quiet=True)
# ✅ wandb.init(settings=wandb.Settings(quiet=True))   # set once at init
# ✅ wandb.finish(exit_code=0)
```

(Source: https://docs.wandb.ai/models/ref/python/functions/finish/.)

## Semantic traps (still works, but easy to misuse)

### `wandb.log(..., commit=False)` semantic

`commit=False` does NOT mean "don't write". It means "buffer this in the same step; flush on the next `log()` (commit=True default) or on `finish()`".

```python
# ❌ Bug: log once with commit=False, never call log again that step
run.log({"loss": x}, commit=False)
# ... loop iteration ends ...
# next iteration:
run.log({"loss": y}, commit=False)
# `x` was never written; `y` is buffered against the same step as `x` was supposed to be.

# ✅ Either omit commit (each call is a step):
run.log({"loss": x})
run.log({"loss": y})

# ✅ Or pair commit=False with a final commit=True log:
run.log({"loss": x, "lr": lr}, commit=False)
run.log({"grad_norm": gn})           # commits all three at this step
```

(Source: https://docs.wandb.ai/models/track/log/.)

### `wandb.log(..., step=N)` for arbitrary N

The SDK only writes to the **current** or **next** step. Lower N → silently dropped. Higher N → fast-forwards.

```python
# ❌ Out-of-order steps:
for epoch in range(20):
    val = evaluate()
    run.log({"val/f1": val}, step=epoch)   # works only because epoch monotonically increases
                                            # if a previous run already wrote step=15, step=10 here is dropped

# ✅ Use a custom x-axis:
run.define_metric("epoch")
run.define_metric("val/*", step_metric="epoch")
for epoch in range(20):
    run.log({"epoch": epoch, "val/f1": evaluate()})
```

### Mutating `wandb.run.name = "new-name"` post-init

Tightened across recent versions. Set the name at init or via `WANDB_NAME` env var.

```python
# ❌ wandb.init(...)
#    wandb.run.name = "my-run"     # silently no-op in some versions

# ✅ wandb.init(name="my-run")
# ✅ os.environ["WANDB_NAME"] = "my-run"; wandb.init()
```

### Forgetting `Api().flush()` in a polling loop

`wandb.Api()` caches `Run` objects. Repeated `api.run(path)` calls return the cached object — including a stale `state`.

```python
# ❌ Spin forever:
api = wandb.Api()
while api.run(path).state != "finished":
    time.sleep(30)

# ✅ Invalidate cache between polls:
api = wandb.Api()
while True:
    api.flush()
    if api.run(path).state in TERMINAL_STATES:
        break
    time.sleep(30)
```

(Source: https://docs.wandb.ai/models/ref/python/public-api/api/.)

### `wandb.run` as a global accessor across functions / multiprocessing

`wandb.run` is the module-level singleton most-recent run. In multi-process training (DDP, ray, etc.) it can be the wrong run, or `None`. Pass the `run` object explicitly.

```python
# ❌ Fragile:
def train():
    wandb.init(...)

def log_loss(loss):
    wandb.run.log({"loss": loss})    # which run? in DDP this is per-worker

# ✅ Explicit:
def train():
    run = wandb.init(...)
    log_loss(run, loss)

def log_loss(run, loss):
    run.log({"loss": loss})
```

### `wandb login` interactively in `entrypoint.py`

Blocks on stdin; never returns in a non-tty context.

```python
# ❌ wandb.login()           # in a Docker entrypoint
# ✅ Set WANDB_API_KEY env var before importing wandb.
# ✅ Or: wandb.login(key=os.environ["WANDB_API_KEY"])
```

## Python version drops

The SDK has aggressively dropped old Pythons:

| wandb version | Dropped Python |
|---|---|
| 0.16.0 | 3.6 |
| 0.19.0 | 3.7 |
| 0.25.0 | 3.8 |

The Dirt monorepo is on Python 3.13; no concern. But generated example code from older training data may still target 3.7+ syntax — fine, just don't pin `wandb` to a version that pre-dates your Python.

## Sources

- https://github.com/wandb/wandb/blob/main/CHANGELOG.md (canonical breaking-change list)
- https://docs.wandb.ai/models/track/log/
- https://docs.wandb.ai/models/ref/python/functions/finish/
- https://docs.wandb.ai/models/ref/python/public-api/api/
