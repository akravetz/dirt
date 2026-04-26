# PyTorch integration

Two integration tiers, with very different overhead. The wake-word trainer should default to the lightweight one.

## The lightweight path: `run.log({...})` from the training loop

90% of useful instrumentation is just logging scalars from your training loop:

```python
import wandb

with wandb.init(project="dirt-wake-word", config=hparams) as run:
    model = build_model(run.config)
    optimizer = make_optimizer(model, run.config)

    for step in range(run.config.n_steps):
        loss = train_step(model, optimizer, batch)

        if step % 100 == 0:
            run.log({
                "train/loss": loss.item(),
                "train/lr": optimizer.param_groups[0]["lr"],
            })

        if step % 1000 == 0:
            recall, precision, f1 = evaluate(model, val_loader)
            run.log({
                "val/recall": recall,
                "val/precision": precision,
                "val/f1": f1,
            })
```

This is what the harness should use for the soft-fork training loop in `_custom_train_model()`. Cost: negligible (one HTTP keep-alive POST every few seconds, batched in a background thread). Value: full loss curve + metric history, automatic system metrics (GPU util, mem), ability to compare runs side-by-side.

(Source: https://docs.wandb.ai/models/integrations/pytorch/.)

## The heavyweight path: `run.watch(model, log="all", log_freq=N)`

`watch` instruments the model to log:

- **Gradient histograms** per parameter tensor at every `log_freq` steps.
- **Parameter histograms** per parameter tensor at every `log_freq` steps.
- **Topology graph** (one-shot at first forward pass).

```python
run.watch(
    model,
    criterion=loss_fn,    # optional; enables loss surface viz
    log="all",            # "gradients" | "parameters" | "all" | None
    log_freq=100,         # every 100 forward passes
    idx=None,             # for multiple models; index into wandb's internal registry
    log_graph=False,      # set True to log the model topology
)

# Later, to detach
run.unwatch(model)
```

(Source: https://docs.wandb.ai/models/integrations/pytorch/.)

### Cost

- Each gradient histogram is computed via PyTorch hooks; runs after every backward pass for `log_freq` steps.
- For a model with 100 parameter tensors, `log="all", log_freq=100`: 200 histograms (100 grad + 100 param) every 100 steps, each ~64 buckets.
- Wallclock overhead: 5–20% slower training, depending on model size.
- W&B storage: small per histogram (~KB), but additive over a long run.

### When to use it

- ✅ **Debugging convergence**: "loss is NaN at step 5,000 — which layer's grad blew up?"
- ✅ **Initial training-pipeline bringup**: prove backprop is reaching all layers.
- ❌ **Steady-state production training**: you already trust the model; histograms are noise.

For the wake-word harness, default to scalar logging only. Reach for `watch()` when triaging a specific failure (a one-off run with `log="all"` while you investigate, then back to scalar-only).

## `wandb.unwatch(...)` and the multi-model case

```python
run.watch(model_a, log="gradients", log_freq=200, idx=0)
run.watch(model_b, log="gradients", log_freq=200, idx=1)
# ... train both ...
run.unwatch(model_a)
run.unwatch(model_b)
```

The `idx` parameter is mandatory if you `watch` multiple models in one run; it disambiguates the internal hook registry.

## What `watch` does NOT do

- It does **not** log model checkpoints. Use `wandb.Artifact` for that. ([artifacts.md](artifacts.md))
- It does **not** log activations. There's no built-in activation hook; if you want them, log manually inside a forward hook.
- It does **not** track optimizer state. Log `optimizer.param_groups[0]["lr"]` etc. yourself.

## Hugging Face Transformers — for context

Transformers ships a `WandbCallback` that auto-instruments `Trainer`-style training:

```python
from transformers import Trainer, TrainingArguments

trainer = Trainer(
    model=model,
    args=TrainingArguments(output_dir="out", report_to=["wandb"], run_name="my-run"),
    ...
)
trainer.train()    # logs loss, lr, eval metrics, all artifacts to wandb automatically
```

(Source: https://docs.wandb.ai/models/integrations/huggingface/, Hugging Face's `WandbCallback`.)

The wake-word trainer doesn't use HF Trainer (it has its own loop in `_custom_train_model()`), so this is for context only — don't reach for `report_to="wandb"` patterns; do explicit `run.log()` calls.

## Sources

- https://docs.wandb.ai/models/integrations/pytorch/
- https://docs.wandb.ai/models/integrations/huggingface/
- https://docs.wandb.ai/models/track/log/
