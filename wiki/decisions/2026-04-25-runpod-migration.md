---
title: "Wake-Word Training Pipeline — Kaggle → RunPod migration"
type: decision
sources: []
related: [wiki/decisions/2026-04-23-wake-word-v5-passive-harvest.md, wiki/wake-word-experiments.md, docs/references/runpod/INDEX.md]
created: 2026-04-25
updated: 2026-04-26
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

- The four Kaggle datasets (`dirt-wakeword-{mine,bg,features,validation}`)
  remain the durable copy of training data. The seed pod pulls from
  them via the Kaggle CLI.
- The `dirt_wake_word` library is unchanged in shape. It reads
  `DIRT_WAKEWORD_INPUT` / `DIRT_WAKEWORD_WORKING` from env (RunPod
  mounts `/workspace/input` / `/workspace/working`) — the legacy
  `DIRT_KAGGLE_*` aliases were dropped along with the Kaggle path.

## Status update — Kaggle path removed

The first successful RunPod training run landed on 2026-04-25
(`hey_claudia.onnx`, 205 KB, 35.7% recall against the 28/76 real-mic
validation set). With RunPod proven end-to-end, the Kaggle scaffolding
was deleted in a follow-up commit:

- `apps/wake-word/kaggle/` (kernel shim, dataset metadata, README) — gone.
- `scripts/kaggle-train` — gone.
- `DIRT_KAGGLE_*` env-var aliases in `paths.py` — gone (now `DIRT_WAKEWORD_*` only).
- `find_openwakeword_source` / `find_dataset` candidate-list logic for the
  Kaggle TPU layout — gone (Docker path is the only path).

Future references to Kaggle in this repo are about the data source
(Kaggle hosts our datasets), not the training runtime.

## Operational state

- Trainer image: `ghcr.io/akravetz/dirt-wake-word-trainer:latest` (~12 GB).
- GHCR auth registered with RunPod: ID `cmoev2n9x0016ju07p15dhc3r`.
- Active Network Volume: `dirt_data_il`, ID `jj3zksmx29`, 50 GB, `US-IL-1`.
  (The original `dirt_data` in `US-CA-2` was abandoned when capacity dried up.)
- First successful end-to-end run: 2026-04-25, ~64 min wall, ~$0.74.
  Per-phase analysis in `debug/runpod_logs.txt`; the `ncpu` parallelism
  fix in commit `6d32ec0` is expected to drop typical run wall to ~30 min
  (or ~10 min after the TTS cache is primed on the volume).

## When to reconsider

If the RunPod path also produces a string of pre-training failures, the
problem is upstream of platform choice — likely in our soft-fork of
`auto_train` or in our augment / training driver. At that point: stop
iterating; run upstream's `automatic_model_training.py` Colab notebook
unmodified to establish a known-good baseline, then re-introduce our
v8 architectural changes one at a time.

## Update 2026-04-26 — Kaggle fully retired

The "What we kept from Kaggle" section above no longer applies. The
RunPod Network Volume `jj3zksmx29` is now the **sole** durable copy of
training data; Kaggle is not consulted at runtime or as a backup. Two
operational consequences:

1. **Versioning surface moved to the volume.** Each subdir's content
   hash lives in `/workspace/input/MANIFEST.json`, computed at bump
   time. The trainer reads it on init and stamps it into
   `wandb.config` + `/workspace/out/run-manifest.json` so any run is
   round-trippable to the bytes it consumed. No more `dirt-wakeword-mine
   v4 → v5` Kaggle version-string trust.

2. **Bump and DR workflows replaced.** `scripts/wakeword-volume-bump
   <slug> <local-dir>` is the new "publish fresh data" verb (replaces
   `kaggle datasets version` + `runpod-seed-volume --reset`).
   `scripts/wakeword-volume-snapshot` mirrors the volume to
   `var/wake-word/_volume-mirror/` for DR — RunPod has already lost a
   volume on us once (the original `dirt_data` in `US-CA-2`), and
   without Kaggle as a fallback, snapshot is the only safety net.

`scripts/runpod-seed-volume` is kept in the repo as a legacy
disaster-recovery path (Kaggle CLI → fresh volume), but is not part of
the routine workflow.

## Sources

- v9–v15 failure trace: [`wiki/wake-word-experiments.md`](../wake-word-experiments.md)
- RunPod surface decisions: [`docs/references/runpod/INDEX.md`](../../docs/references/runpod/INDEX.md)
- Migration commit: `f7b2a26`
