# Tables

`wandb.Table` is the right surface for "I have N rows, M columns of mixed scalar / image / link data, and I want to compare them in the UI". The wake-word harness uses tables for two things:

1. **The per-checkpoint candidate sweep** in `select_best_by_real_f1()` — ~20 rows of `(checkpoint_idx, threshold, recall, precision, f1)`.
2. **The per-threshold validation report** from `validate.py` — one row per threshold from 0.30 → 0.95 in 0.05 steps.

Either is wrong as N parallel scalar series; both render natively as a sortable, filterable table in the run page.

## Constructors

Three forms (Source: https://docs.wandb.ai/models/ref/python/data-types/table/):

```python
import wandb
import pandas as pd

# 1. columns + data (the explicit form)
table = wandb.Table(
    columns=["checkpoint_idx", "threshold", "recall", "precision", "f1"],
    data=[
        [0, 0.50, 0.91, 0.78, 0.84],
        [0, 0.55, 0.88, 0.82, 0.85],
        ...
    ],
)

# 2. dataframe (overrides data + columns if both given)
df = pd.DataFrame({
    "checkpoint_idx": [0, 0, 1, 1],
    "threshold": [0.5, 0.6, 0.5, 0.6],
    "f1": [0.84, 0.86, 0.83, 0.85],
})
table = wandb.Table(dataframe=df)

# 3. empty + add_data (incremental during a loop)
table = wandb.Table(columns=["checkpoint_idx", "threshold", "recall", "precision", "f1"])
for ckpt_idx, ckpt_path in enumerate(checkpoints):
    for thresh in thresholds:
        recall, precision, f1 = evaluate(ckpt_path, thresh)
        table.add_data(ckpt_idx, thresh, recall, precision, f1)
```

## Logging

```python
run.log({"checkpoint_sweep": table})
```

That's it. The table renders in the run UI under the same key (`checkpoint_sweep`).

## Constructor params worth knowing

| Param | What it does |
|---|---|
| `columns` | List of column names. Defaults to `["Input", "Output", "Expected"]` (a leftover from the original "label studio" use case — always pass your own). |
| `data` | 2D row-oriented array. |
| `dataframe` | pandas `DataFrame`. Overrides `data` + `columns` if also given. |
| `optional` | Bool or list-of-bools per column. Allows `None` in that column. |
| `allow_mixed_types` | Set `True` if a column has heterogeneous types (rare for the harness — usually a code smell). |
| `log_mode` | `"IMMUTABLE"` (default) / `"MUTABLE"` / `"INCREMENTAL"`. The harness wants `IMMUTABLE` — log the table once at the end of the candidate sweep, don't try to update it. |

## `add_data()` not `add_row()`

`add_row(...)` is deprecated. Use `add_data(*row)` — the args are positional, in column order:

```python
table.add_data(ckpt_idx, threshold, recall, precision, f1)  # positional, matches columns=
```

Or `add_column(name, data, optional=False)` to bolt a new column onto an existing table.

(Source: https://docs.wandb.ai/models/ref/python/data-types/table/.)

## Limits

- Default upper bound: `wandb.Table.MAX_ARTIFACT_ROWS` (the SDK's compile-time constant; check `wandb.Table.MAX_ARTIFACT_ROWS` for the exact value in your installed version — historically 200K rows).
- For "log the table inline in `run.log({...})`" (vs. as an artifact), the practical limit is much smaller (~10K rows comfortable).
- The harness's two use cases are 20 rows and ~14 rows — nowhere near the limit.

## When a table beats parallel scalar series

| Use scalar series (`run.log({"metric": x})`) when... | Use a `wandb.Table` when... |
|---|---|
| The metric varies over time/step (training loss). | The metric varies over a non-time axis (threshold, checkpoint_idx, hyperparam). |
| You want an automatic chart. | You want a sortable, filterable table view. |
| Each datum is a single scalar. | Each datum is a tuple of related scalars (recall, precision, F1 *together*). |
| The series is open-ended. | The series is a fixed-size matrix you compute once. |

For `select_best_by_real_f1()`, the table is correct: it's a fixed-size grid of `(checkpoint_idx × threshold)` evaluations computed once at the end of training.

## Things to ignore

- ❌ **`add_row(...)`** — deprecated. (Source: https://docs.wandb.ai/models/ref/python/data-types/table/.)
- ❌ **`wandb.Table(rows=...)`** — legacy compatibility constructor; not recommended.
- ❌ **Logging a table per training step** ("inline streaming"). Tables are blob-shaped — each `log` re-uploads the whole table. ✅ Build the table in memory, log once.

## Sources

- https://docs.wandb.ai/models/ref/python/data-types/table/
- https://docs.wandb.ai/guides/data-types/tables/log-tables
