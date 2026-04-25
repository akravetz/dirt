---
title: "Wake-Word Training Pipeline — Kaggle → RunPod migration"
type: decision
sources: []
related: [wiki/decisions/2026-04-23-wake-word-v5-passive-harvest.md, wiki/wake-word-experiments.md, docs/references/runpod/INDEX.md]
created: 2026-04-25
updated: 2026-04-25
---

# Wake-Word Training Pipeline — Kaggle → RunPod migration

After seven Kaggle-side failures in a row (v9 through v15, see
[`wake-word-experiments.md`](../wake-word-experiments.md)), abandoned
Kaggle Notebooks as the training platform and migrated to a
self-controlled Docker image running on RunPod Pods.

## Why migrate

Each of v9–v15 fixed one specific bug, ran further than the previous
attempt, and surfaced a new failure one stage deeper. **Every single
fix was a Kaggle-environment quirk**, not a problem with our pipeline:

| ver | what we had to fix |
|---|---|
| v9 | base image doesn't ship openwakeword (assumption was wrong) |
| v10 | py3.12 has no PyPI wheel for openwakeword 0.6.0 |
| v11 | unpushed SHA → kernel's git checkout failed |
| v12 | upstream `total_length` calc skipped by our soft-fork |
| v13 | bundled ONNX resource paths split between cloned vs installed |
| v14 | `pip install -e` doesn't put package on sys.path on Kaggle |
| v15 | reached training, ERRORed at 1h51m (root cause not investigated) |

The pattern: a locked-down environment we don't control was bleeding
~30–90 min per attempt and producing failure modes not informative
about our actual training architecture. Continuing on Kaggle would
keep paying that tax indefinitely.

## What we picked

**RunPod Pods via the REST API v1** at `https://rest.runpod.io/v1/`.
Full reasoning + topic breakdown in
[`docs/references/runpod/INDEX.md`](../../docs/references/runpod/INDEX.md).

Key choices:

- **Pods, not Serverless.** Serverless is queue+`handler(event)` shaped,
  cold-start cost, ~3× per-second pricing, per-job timeouts inappropriate
  for a 30–90 min run that produces files.
- **REST API, not GraphQL or the `runpod` Python SDK.** SDK's pod-CRUD
  half is still GraphQL underneath with stale field names. REST has
  cleaner shapes and is the canonical surface as of 2025-03-10.
- **Self-controlled Docker image.** Bakes ALL deps + openwakeword source
  + bundled resources + piper-sample-generator + libritts model + the
  `dirt_wake_word` library at build time. Runtime entrypoint is a 3-job
  Python script: run training, copy artifacts to `/workspace/out/`,
  write SUCCESS/FAILURE sentinel.
- **Network Volume for datasets.** Seeded once via a small CPU pod
  that runs the Kaggle CLI; persists across training runs. Image stays
  ~12 GB (just code+deps), datasets stay on the volume.
- **SCP via Direct TCP** for artifact pull. The `ssh.runpod.io` proxy
  doesn't support file-transfer subsystems.

## What's in the repo (committed `f7b2a26`)

| Path | Role |
|---|---|
| `apps/wake-word/docker/Dockerfile` | Build def. Base on `runpod/pytorch` (sshd + CUDA already wired). |
| `apps/wake-word/docker/entrypoint.py` | In-container runtime: train + publish + sentinel. |
| `apps/wake-word/.dockerignore` | Build-context filter (apps/wake-word/ only). |
| `scripts/runpod-build-image` | `docker buildx --platform linux/amd64 --push` to GHCR. |
| `scripts/runpod-seed-volume` | One-time CPU pod that downloads the four Kaggle datasets onto the Network Volume. |
| `scripts/runpod-train` | Orchestration: `POST /v1/pods` → poll → SCP → `DELETE` in `finally`. |
| `docs/references/runpod/` | Version-pinned reference pack (12 topic files + INDEX). |

Plus three new env vars wired through `dirt_shared.config`:

- `RUNPOD_API_KEY` — bearer token for the REST API.
- `RUNPOD_NETWORK_VOLUME_ID` — pre-created volume holding the seeded datasets.
- `RUNPOD_GHCR_AUTH_ID` — registered via `POST /v1/containerregistryauth`,
  lets RunPod pull our private GHCR image.

## What we kept from Kaggle

- The `dirt_wake_word` library is unchanged. It already reads
  `DIRT_KAGGLE_INPUT` / `DIRT_KAGGLE_WORKING` from env (so the test
  suite could mock the Kaggle environment) — RunPod uses the same env
  vars pointing at `/workspace/input` / `/workspace/working`.
- `apps/wake-word/kaggle/` and `scripts/kaggle-train` left intact as
  fallback. Once a RunPod model trains successfully and validates, we
  can delete the Kaggle path.
- The four Kaggle datasets (`dirt-wakeword-{mine,bg,features,validation}`)
  remain the durable copy of training data. The seed pod pulls from
  them via the Kaggle CLI.

## Operational state at decision time

- Image built and pushed: `ghcr.io/akravetz/dirt-wake-word-trainer:latest`
  (12 GB, ~30 min first push, subsequent pushes ~5 min for changed layers).
- GHCR auth registered with RunPod: ID `cmoev2n9x0016ju07p15dhc3r`.
- Network Volume created (`dirt_data`, ID `b7rdtnmhkd`, 50 GB, US-CA-2).
- Volume seed pod **in flight** at time of writing.
- First trainer run pending volume seed.

## When to reconsider

If the RunPod path also produces a string of pre-training failures, the
problem is upstream of platform choice — likely in our soft-fork of
`auto_train` or in our augment / training driver. At that point: stop
iterating; run upstream's `automatic_model_training.py` Colab notebook
unmodified to establish a known-good baseline, then re-introduce our
v8 architectural changes one at a time.

## Sources

- v9–v15 failure trace: [`wiki/wake-word-experiments.md`](../wake-word-experiments.md)
- RunPod surface decisions: [`docs/references/runpod/INDEX.md`](../../docs/references/runpod/INDEX.md)
- Migration commit: `f7b2a26`
