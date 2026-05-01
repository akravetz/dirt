---
title: Weights & Biases (wandb) Reference Pack
concept: wandb
mode: hosted-api
sdk_version: wandb >= 0.26 (Python)
api_surface: SDK + Public API + REST automations
updated: 2026-04-29
---

# Weights & Biases (wandb)

[Weights & Biases](https://wandb.ai/) is an experiment-tracking + artifact-versioning + lightweight-orchestration SaaS for ML training. This pack covers the **`wandb` Python SDK (>=0.26.x)** and the **Public API (`wandb.Api()`)** — only the surface needed to instrument a one-shot training run, log scalars / tables / artifacts, and externally poll the run's terminal state from an orchestrator.

This pack exists for the Dirt wake-word retraining workflow. The pipeline shape: a RunPod GPU pod runs `dirt_wake_word.main.main()` inside a Docker container, the trainer logs metrics + the per-checkpoint candidate sweep + the final `.onnx`/`.tflite` to W&B, and a local orchestrator (`scripts/runpod-train`) polls `wandb.Api().run(id).state` instead of SSH-pinging a sentinel file.

## When to consult this pack

Read this INDEX first (and the linked topic files) before writing or editing code that:

- Imports `wandb` anywhere in `apps/wake-word/src/dirt_wake_word/` or `apps/wake-word/docker/entrypoint.py`
- Calls `wandb.init()`, `wandb.log()`, `wandb.finish()`, `wandb.log_artifact()`, `wandb.Table(...)`, or `wandb.alert()`
- Reads `wandb.Api().run(...).state` (the polling switch in `scripts/runpod-train`)
- Sets a `WANDB_*` environment variable in the trainer Dockerfile, `entrypoint.py`, `.env.example`, or `systemd/`
- Designs a sweep config (YAML or dict) for the auto-research harness's hyperparameter search
- Decides between cloud SaaS (`https://api.wandb.ai`) and a self-hosted W&B Server

Prefer what is in this pack over recollection. The SDK has been actively breaking surface every few minor releases (see [obsolete-or-trap-patterns.md](obsolete-or-trap-patterns.md)) — `wandb.beta.workflows` removed in 0.24.0, `run.project_name()` deprecated in favor of `run.project` in 0.19.10, `wandb.plots.*` collapsed into `wandb.plot` in 0.17.0, the legacy "no-service" mode removed in 0.21.0. Training data is rich with patterns that no longer work.

## TL;DR — recommended shape for the wake-word trainer

1. **Auth.** One env var: `WANDB_API_KEY=...` from `https://wandb.ai/authorize`. Inject into the RunPod container via the existing `env: { ... }` block in `POST /pods`. No interactive `wandb login`. See [auth-and-config.md](auth-and-config.md).
2. **Init.** `with wandb.init(project="dirt-wake-word", group=run_group, job_type="train", config=hp_dict) as run:` — the context-manager form is the new canonical shape (auto-`finish()` on exit, correct exit_code on exception). See [init-log-finish.md](init-log-finish.md).
3. **Log.** `run.log({"loss": ...})` per training step (auto-incrementing step). `run.log({"recall": ..., "precision": ...}, commit=False)` then `run.log({"f1": ...})` to bundle multiple metrics into one step. The per-checkpoint candidate sweep in `select_best_by_real_f1()` writes a `wandb.Table` of (checkpoint_idx, threshold, recall, precision, f1) — see [tables.md](tables.md).
4. **Artifacts.** The trained `.onnx`, `.tflite`, and `validation-report.txt` all go through `wandb.Artifact("hey-claudia-model", type="model")` → `art.add_file(...)` → `run.log_artifact(art, aliases=["latest", "candidate-2026-04-25"])`. The `production` alias is the promotion gate the harness will gate deploys on. See [artifacts.md](artifacts.md).
5. **Finish.** Inside the context manager, an unhandled exception sets `exit_code=1` automatically (state → `failed`). For the Docker `entrypoint.py` wrapper, catch the exception, call `wandb.finish(exit_code=1)` explicitly, and re-raise — the pod must report a non-zero exit so the orchestrator sees `state=failed`, not `state=crashed` (the latter requires a heartbeat timeout, ~5 min wait). See [init-log-finish.md](init-log-finish.md), [run-state-and-the-api.md](run-state-and-the-api.md).
6. **Poll externally.** `wandb.Api().run(f"{entity}/{project}/{run_id}").state` returns one of `running` / `finished` / `failed` / `crashed` / `killed` / `pending`. Poll every 20–30 s; call `Api().flush()` between polls because the SDK caches Run objects locally. See [run-state-and-the-api.md](run-state-and-the-api.md).
7. **Container hygiene.** `WANDB_DIR=/workspace/wandb` so the SDK's local logs survive in the volume disk (which is what gets SCP'd off). `WANDB_SILENT=true` to keep stdout clean for journalctl. Configure console capture in `wandb.init(settings=wandb.Settings(console="redirect", console_multipart=True, console_chunk_max_seconds=30, console_chunk_max_bytes=512 * 1024))` so long RunPod jobs upload console chunks during the run instead of only producing a final `output.log`. If a pod is offline, `WANDB_MODE=offline` + `wandb sync` post-hoc — but the auto-research harness's polling design assumes online mode. See [docker-and-runpod.md](docker-and-runpod.md).

A working orchestration shape (init → log → finish vs. external poll) is sketched in [init-log-finish.md](init-log-finish.md) and [run-state-and-the-api.md](run-state-and-the-api.md).

## Topics

- **[auth-and-config.md](auth-and-config.md)** — `WANDB_API_KEY`, where it comes from, `WANDB_PROJECT` / `WANDB_ENTITY` / `WANDB_RUN_GROUP` precedence vs. `wandb.init()` kwargs, and the headless-auth path for Docker containers (no `wandb login` prompt).
- **[init-log-finish.md](init-log-finish.md)** — The trinity. `wandb.init()` parameter table (project / entity / name / group / job_type / config / tags / notes / mode / id / resume / dir / settings), step semantics for `wandb.log()` (auto-increment vs. explicit), the `commit=False` bundling trick, and `wandb.finish(exit_code=...)` on success vs. failure vs. uncaught exception. The `with wandb.init(...) as run:` context-manager pattern.
- **[run-state-and-the-api.md](run-state-and-the-api.md)** — `wandb.Api()` instantiation, `Api().run("entity/project/run_id").state` enum, what each state means and how the transition is triggered, the heartbeat semantics (run is marked `crashed` after the SDK stops sending heartbeats — minutes-scale, not seconds), `Api.flush()` cache invalidation, polling cadence vs. webhook automations.
- **[artifacts.md](artifacts.md)** — `wandb.Artifact(name, type)`, `add_file` / `add_dir` / `add_reference`, `run.log_artifact()`, version numbers (`v0`, `v1`, ...), aliases (`latest` is automatic; `production` / `candidate-<date>` are user-applied), `use_artifact()` for downloading a previous version, retention defaults and quota.
- **[tables.md](tables.md)** — `wandb.Table(columns=, data=)`, `wandb.Table(dataframe=df)`, `add_data()` (deprecation note: `add_row()` is gone), table size limits, when a table beats just logging N parallel scalars.
- **[config-and-sweeps.md](config-and-sweeps.md)** — `wandb.config` for hyperparameters, `run.config["lr"]` access, `allow_val_change`, `define_metric()` for custom x-axes and summary aggregation. Sweeps overview: sweep config YAML/dict shape (method, parameters, metric, early_terminate), `wandb.sweep()` + `wandb.agent()`, when Sweeps is the right answer vs. the harness's hand-rolled candidate sweep.
- **[alerts-and-webhooks.md](alerts-and-webhooks.md)** — `run.alert(title, text, level, wait_duration)` from inside a run, where the alert delivers (email + Slack), throttling. Project-level Automations (UI-configured) for run-state transitions and webhooks — and why they're Pro-tier-only and not part of the OSS-friendly path.
- **[integrations-pytorch.md](integrations-pytorch.md)** — `run.watch(model, log="gradients", log_freq=100)` for histograms, `run.unwatch()`. The lightweight scalar-only path (`run.log({"loss": ...})`) is what the wake-word trainer should default to; `watch()` is for debugging convergence, not for steady-state runs.
- **[docker-and-runpod.md](docker-and-runpod.md)** — Running `wandb` inside a one-shot Docker container on RunPod: env-var injection (`WANDB_API_KEY`, `WANDB_PROJECT`, `WANDB_RUN_GROUP`, `WANDB_DIR`), the SDK's background `wandb-core` process (formerly `wandb-service`), how `wandb.finish()` blocks until upload completes, what to do on Ctrl-C / SIGTERM, the `WANDB_MODE=offline` + `wandb sync` flow.
- **[pricing-and-quotas.md](pricing-and-quotas.md)** — Free tier limits (5 GB storage, 1 GB Weave, 5 model seats; tracked-hours unlimited), Pro at $60/mo (100 GB), Enterprise. Academic license. What "100 MB / artifact version" means in practice for a `.onnx` model.
- **[local-vs-cloud.md](local-vs-cloud.md)** — Self-hosted W&B Server: when it makes sense (regulated/on-prem) vs. always-cloud (everyone else). Why for a solo researcher cloud beats ops-time. Dedicated Cloud as the middle ground.
- **[obsolete-or-trap-patterns.md](obsolete-or-trap-patterns.md)** — Patterns training data still suggests that are now wrong: `wandb.plots.*` (gone), `wandb.beta.workflows.log_model` (gone in 0.24), `WANDB_DISABLE_SERVICE=true` (errors in 0.20+), `run.project_name()` and friends (deprecated 0.19.10), `add_row()` on tables (use `add_data()`), `wandb.run.name = "..."` mutation pattern, `commit=False` semantic confusion.

## Things to ignore (training-data drift)

Patterns LLMs will reach for from training data that are **wrong, deprecated, or strictly worse** for the auto-research harness's use case. Cross-references go to the topic file with the correct path.

- ❌ **`wandb.plots.matplotlib(...)` / `wandb.plots.confusion_matrix(...)`** etc. The entire `wandb.plots` namespace was removed in 0.17.0. ✅ Use `wandb.plot.confusion_matrix(...)` (`wandb.plot`, singular). See [obsolete-or-trap-patterns.md](obsolete-or-trap-patterns.md). ([CHANGELOG 0.17.0](https://github.com/wandb/wandb/blob/main/CHANGELOG.md))
- ❌ **`wandb.beta.workflows.log_model(...)` / `use_model(...)` / `link_model(...)`** for model registry. The whole `wandb.beta.workflows` module was removed in 0.24.0. ✅ Use `run.log_artifact(artifact, aliases=[...])` + `artifact.link(...)`. See [artifacts.md](artifacts.md). ([CHANGELOG 0.24.0](https://github.com/wandb/wandb/blob/main/CHANGELOG.md))
- ❌ **`WANDB_DISABLE_SERVICE=true` / `x_disable_service=True` in settings**. Removed in 0.20.0; setting it now raises an error. The `wandb-core` background process is mandatory. ✅ Just don't set it. If you need to silence the SDK, use `WANDB_SILENT=true` + `quiet=True` in `Settings`. See [docker-and-runpod.md](docker-and-runpod.md). ([CHANGELOG 0.20.0](https://github.com/wandb/wandb/blob/main/CHANGELOG.md))
- ❌ **`run.project_name()` / `run.get_url()` / `run.get_project_url()` / `run.get_sweep_url()`** as method calls. Deprecated in 0.19.10 in favor of properties. ✅ `run.project` / `run.url` / `run.project_url` / `run.sweep_url`. See [obsolete-or-trap-patterns.md](obsolete-or-trap-patterns.md).
- ❌ **`wandb.Table(...).add_row(...)`**. Deprecated; use `add_data(*row)`. The naming change matters because tables are append-only and `add_row` had ambiguous semantics around column ordering. ✅ `table.add_data(checkpoint_idx, threshold, f1, recall, precision)`. See [tables.md](tables.md).
- ❌ **Mutating `wandb.run.name = "new-name"` after init**. The SDK has tightened around late mutation; the safe pattern is to set `name=` in `wandb.init(...)` or via the `WANDB_NAME` env var before init. Mutation post-init silently does nothing in some configurations. ✅ Set name at init time. See [init-log-finish.md](init-log-finish.md).
- ❌ **Calling `wandb.init()` without a context manager and forgetting `wandb.finish()`**. The script exit will eventually trigger a sync — but if the script crashes uncaught, the run hits the **crashed** state (heartbeat timeout, ~5 min after the process dies) rather than **failed** with a clean exit code. The orchestrator that's polling will wait an extra 5 min for nothing. ✅ Use the `with wandb.init(...) as run:` form, or wrap `try / finally: wandb.finish(exit_code=...)`. See [init-log-finish.md](init-log-finish.md), [run-state-and-the-api.md](run-state-and-the-api.md).
- ❌ **`wandb.log({"loss": x}, commit=False)` to "log without writing yet"**. `commit=False` does NOT mean "don't write" — it means "buffer this in the same step, write on the next `log()` call (or on `finish`)". A common bug: calling `log(..., commit=False)` once and never calling another `log()` → metrics never flush. ✅ Either omit `commit` (default True; each call is a step), OR pair every `commit=False` call with a final `log({...})` (defaults to `commit=True`) at the end of the step. See [init-log-finish.md](init-log-finish.md), [obsolete-or-trap-patterns.md](obsolete-or-trap-patterns.md).
- ❌ **`wandb.log({"loss": x}, step=epoch)` for arbitrary out-of-order steps**. The SDK only writes to the "current" or "next" step; passing a `step` lower than the current step silently drops the data. ✅ Use `define_metric("epoch_loss", step_metric="epoch")` to make `epoch` a custom x-axis. See [init-log-finish.md](init-log-finish.md), [config-and-sweeps.md](config-and-sweeps.md).
- ❌ **Hyperparameter sweeps via `wandb.sweep()` for the harness's per-checkpoint candidate selection in `select_best_by_real_f1()`**. Sweeps are designed for "launch N independent runs, each with different hyperparams, distributed across machines". The candidate sweep here is N evaluations of N checkpoints from one training run — that's a `wandb.Table` inside a single run. ✅ Use Sweeps when you actually want to grid/random/Bayes-search over `learning_rate`, `lstm_dim`, etc. across multiple training runs. Don't bend it for in-run analysis. See [config-and-sweeps.md](config-and-sweeps.md), [tables.md](tables.md).
- ❌ **`wandb.watch(model)` for production training runs**. `watch()` is heavyweight (gradient histograms per layer per `log_freq`); it's a debugging tool. ✅ Just `run.log({"train_loss": loss.item()})` from your training loop. See [integrations-pytorch.md](integrations-pytorch.md).
- ❌ **`wandb login` interactively in a Dockerfile / `entrypoint.py`**. The CLI prompt blocks forever on a non-tty. ✅ Set `WANDB_API_KEY` env var before any `wandb.*` call; the SDK auto-authenticates. See [auth-and-config.md](auth-and-config.md), [docker-and-runpod.md](docker-and-runpod.md).
- ❌ **The `run.summary` dict as a duplicate of `run.log()`**. Summary auto-tracks the most-recent value of each logged scalar. Manually setting `run.summary["best_f1"] = ...` is for values that don't naturally map to a step (e.g. final F1 chosen by the candidate sweep). ✅ Let `summary` auto-populate for streaming scalars; assign manually for run-level "the answer" values. See [init-log-finish.md](init-log-finish.md).
- ❌ **`WANDB_API_KEY` baked into the Docker image**. The image gets pushed to GHCR / Docker Hub; the key leaks. ✅ Inject at pod-create time via the `env: { WANDB_API_KEY: ... }` block on `POST /pods` — same channel as the existing RunPod env. See [docker-and-runpod.md](docker-and-runpod.md).
- ❌ **`wandb.run` as a global accessor after `wandb.init()`**. It still works, but the pattern is fragile across multi-process training and against future SDK refactors. ✅ Bind the `run` object returned by `wandb.init()` and pass it explicitly. See [init-log-finish.md](init-log-finish.md).

## Sources

Anchored 2026-04-25. Each topic file cites its specific URL inline. Top-level entries:

- Docs landing: https://docs.wandb.ai/
- Python SDK reference: https://docs.wandb.ai/ref/python/
- `wandb.init()`: https://docs.wandb.ai/ref/python/init/
- `wandb.Run`: https://docs.wandb.ai/models/ref/python/experiments/run/
- `wandb.log`: https://docs.wandb.ai/models/track/log/
- `wandb.finish`: https://docs.wandb.ai/models/ref/python/functions/finish/
- `wandb.Api`: https://docs.wandb.ai/ref/python/public-api/api/
- `wandb.Artifact`: https://docs.wandb.ai/models/ref/python/experiments/artifact/
- `wandb.Table`: https://docs.wandb.ai/models/ref/python/data-types/table/
- `wandb.alert`: https://docs.wandb.ai/models/runs/alert/
- `wandb.config`: https://docs.wandb.ai/models/track/config/
- Run states: https://docs.wandb.ai/models/runs/run-states/
- Environment variables: https://docs.wandb.ai/models/track/environment-variables/
- Sweeps: https://docs.wandb.ai/models/sweeps/
- Sweep config schema: https://docs.wandb.ai/models/sweeps/define-sweep-configuration/
- Automations: https://docs.wandb.ai/models/automations/
- PyTorch integration: https://docs.wandb.ai/models/integrations/pytorch/
- Offline mode: https://docs.wandb.ai/models/ref/cli/wandb-offline/
- Self-managed hosting: https://docs.wandb.ai/models/hosting/
- Pricing: https://wandb.ai/site/pricing
- CHANGELOG (canonical breaking-change source): https://github.com/wandb/wandb/blob/main/CHANGELOG.md
- SDK GitHub repo: https://github.com/wandb/wandb (active, weekly minor releases)
