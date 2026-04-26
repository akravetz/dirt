# Artifacts

W&B Artifacts are versioned, deduplicated blob storage tied to a run. The wake-word harness uses them for the trained `.onnx` / `.tflite` model + the per-threshold validation report.

## Anatomy

```python
import wandb

with wandb.init(project="dirt-wake-word", job_type="train") as run:
    train(...)

    art = wandb.Artifact(
        name="hey-claudia-model",                # unique-within-project; [-_.A-Za-z0-9]+
        type="model",                            # any string, but "model" / "dataset" are conventional
        description="Wake-word v5 candidate from auto-research run abc123",
        metadata={
            "val_f1": 0.91,
            "val_recall": 0.93,
            "val_precision": 0.89,
            "best_threshold": 0.62,
            "training_steps": 50_000,
            "harness_rev": "a1b2c3d",
        },
    )
    art.add_file("/workspace/out/hey-claudia.onnx")
    art.add_file("/workspace/out/hey-claudia.tflite")
    art.add_file("/workspace/out/validation-report.txt")

    run.log_artifact(art, aliases=["latest", f"candidate-{run_date}"])
```

(Source: https://docs.wandb.ai/models/ref/python/experiments/artifact/ — fields and methods on `Artifact`.)

### Constructor params

| Param | What it does |
|---|---|
| `name` | Unique within `(entity, project)`. Allowed chars: letters, digits, `_`, `-`, `.`. |
| `type` | Free-form string. Conventional: `"model"`, `"dataset"`, `"results"`, `"code"`. Including the substring `"model"` opts the artifact into the Model Registry surface. |
| `description` | Long-form markdown. |
| `metadata` | Arbitrary JSON-serializable dict. **This is the queryable channel** — the harness's promotion gate reads `art.metadata["val_f1"]`. |
| `incremental` | For appending to an existing artifact across multiple runs (rare; not needed for the harness). |

## Adding content

Three methods:

```python
art.add_file("/local/path/model.onnx")              # upload one file
art.add_file("/local/path/model.onnx", name="onnx") # rename in the artifact
art.add_dir("/workspace/out/checkpoints")           # upload a directory tree
art.add_reference("s3://my-bucket/large-blob.bin")  # track without uploading
```

`add_reference` is the right call for things too large to upload (training data) — W&B stores the URI + a checksum, not the bytes. Useful for the wake-word training data corpus if it ever lands in S3.

(Source: https://docs.wandb.ai/models/ref/python/experiments/artifact/.)

## Versioning and aliases

- Every `run.log_artifact(art)` creates a new version: `v0`, `v1`, `v2`, ... auto-incrementing.
- The `latest` alias **automatically** points to the most-recent version. You can't (easily) overwrite this.
- All other aliases are user-applied — pass `aliases=[...]` to `log_artifact`, or call `art.aliases.append(...)` and re-save.

```python
# Promote a candidate to production
api = wandb.Api()
candidate = api.artifact("akravetz/dirt-wake-word/hey-claudia-model:candidate-2026-04-25")
candidate.aliases.append("production")
candidate.save()
```

The `production` alias is a stable name the consuming side resolves at deploy time:

```python
# Inside dirt-voice or the deploy script
api = wandb.Api()
prod = api.artifact("akravetz/dirt-wake-word/hey-claudia-model:production")
prod.download(root="var/wake-word/models/current/")
```

(Source: https://docs.wandb.ai/models/ref/python/experiments/artifact/ — aliases section.)

### Aliasing pattern for the harness

| Alias | Who applies it | When |
|---|---|---|
| `latest` | Automatic | Every successful `log_artifact()`. |
| `candidate-YYYY-MM-DD-HHMM` | Trainer | At train time, in `aliases=` on `log_artifact`. Provides a stable, datestamp-recoverable pointer. |
| `production` | Promotion gate (separate run/script) | After validation beats the current production baseline by margin. |
| `failed-validation` | Promotion gate | Optional; for "we tried this candidate, it lost". Keeps the artifact discoverable for diff. |

## Downloading

```python
art = api.artifact("entity/project/hey-claudia-model:production")
art.download(root="/local/dest/")     # extracts the artifact tree to /local/dest/

# Single-file artifact convenience
path = art.file("/local/dest/")        # returns the local filename of the (sole) file

# Sanity check
art.verify("/local/dest/")             # checksum each file against the manifest
```

(Source: https://docs.wandb.ai/models/ref/python/experiments/artifact/.)

The `use_artifact()` call on a `Run` is the same idea but also records lineage (this run consumed that artifact):

```python
with wandb.init(project="dirt-wake-word", job_type="validate") as run:
    art = run.use_artifact("hey-claudia-model:candidate-2026-04-25", type="model")
    local_dir = art.download()
    # ... evaluate the model from local_dir ...
```

This is the right shape for a separate "validation" run that consumes a "training" run's artifact.

## Retention and quota

- Artifacts count against your storage quota (free tier: 5 GB; Pro: 100 GB; see [pricing-and-quotas.md](pricing-and-quotas.md)).
- Old versions are **not** automatically pruned. They accrue forever.
- A version with **no aliases** is eligible for cleanup via `Artifact.delete(delete_aliases=False)` or via project-level retention rules in the UI (Pro+).
- Recommended pattern: keep `latest`, `production`, and the most recent N `candidate-*` aliases; bulk-delete unaliased older versions periodically.

```python
# Cleanup script (run weekly)
api = wandb.Api()
versions = api.artifact_versions("model", "akravetz/dirt-wake-word/hey-claudia-model")
for v in versions:
    if not v.aliases:        # no human-meaningful pointer
        v.delete()
```

## Things to NOT do

- ❌ **`run.log_artifact(art)` for every checkpoint**. The wake-word trainer produces ~20 candidate checkpoints during `select_best_by_real_f1()`. Each is ~MB. Logging all 20 as separate artifacts burns version slots and storage. ✅ Keep candidates as files in `/workspace/out/`, log a `wandb.Table` summarizing the F1 of each, and only `log_artifact` the final selected one. (See [tables.md](tables.md).)
- ❌ **Mutating an artifact after `log_artifact`**. Artifacts are finalized on log; further `add_file` calls are no-ops. To revise, create a new `Artifact` instance with the same name; W&B issues a new version.
- ❌ **`wandb.beta.workflows.log_model(...)`**. Removed in 0.24.0. ✅ `Artifact(type="model")` + `link()` to a Model Registry collection. (Source: [CHANGELOG 0.24.0](https://github.com/wandb/wandb/blob/main/CHANGELOG.md))

## Sources

- https://docs.wandb.ai/models/ref/python/experiments/artifact/
- https://docs.wandb.ai/guides/artifacts
- https://docs.wandb.ai/guides/artifacts/create-a-new-artifact-version
- https://docs.wandb.ai/guides/registry/
- https://github.com/wandb/wandb/blob/main/CHANGELOG.md (0.24.0 removal of `wandb.beta.workflows`)
