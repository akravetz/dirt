---
title: RunPod Reference Pack
concept: runpod
mode: hosted-api
api_version: REST v1 (rest.runpod.io/v1)
updated: 2026-04-25
---

# RunPod

RunPod is a GPU-cloud-on-demand platform. This pack covers the **REST API v1** at `https://rest.runpod.io/v1/`, the `runpodctl` CLI, and the `runpod` Python package — only the surface needed to **launch a single one-shot training job in a custom Docker image, poll it to completion, and pull artifacts back to a local machine**.

This pack is for the Dirt wake-word retraining workflow. The pipeline shape: push a job → poll status every ~20 s → on completion pull `.onnx` / `.tflite` / `validation-report.txt` back to `var/wake-word/models/<datestamp>/`. ~30–90 min wall, sub-$2/run target.

## When to consult this pack

Read this INDEX first (and the linked topic files) before writing code that:

- Calls `https://rest.runpod.io/v1/...` or `https://api.runpod.io/graphql`
- Calls `https://s3api-<dc>.runpod.io/...` (Network Volume S3 API) or shells out to `aws s3 cp/sync` against a RunPod volume
- Imports `runpod` (PyPI package, not "runpod-python")
- Shells out to `runpodctl`
- Builds a Docker image intended to be pulled by RunPod (private registry auth, base image, entrypoint)
- Decides between **Pods** and **Serverless** for a batch job
- Picks a GPU type, a datacenter, or a cloud type (`SECURE` vs `COMMUNITY`)
- Exfiltrates a trained artifact off a finished Pod

Prefer what is in this pack over recollection. RunPod has shipped a REST API (March 2025) that is now the canonical surface; training data still favors GraphQL via `runpod` Python and curl examples that hit `api.runpod.io/graphql`. The REST API has cleaner field names (`imageName`, `gpuTypeIds`, `dockerStartCmd`, `containerDiskInGb`, `volumeInGb`) and is the surface this pack standardizes on.

## TL;DR — recommended shape for one-shot training

1. **Build** your training image, push to a registry RunPod can pull from (Docker Hub public, Docker Hub private + creds, GHCR + creds). `linux/amd64` only. ([source](https://docs.runpod.io/tutorials/introduction/containers/create-dockerfiles))
2. **Surface**: REST API at `https://rest.runpod.io/v1/`, **not** GraphQL, **not** the Python SDK's `runpod.create_pod()` (which still uses GraphQL underneath). See [pod-vs-serverless.md](pod-vs-serverless.md) for why Pods over Serverless for a 30–90 min job.
3. **Auth**: one bearer token in `Authorization: Bearer $RUNPOD_API_KEY`. Create at `https://www.console.runpod.io/user/settings`. See [auth.md](auth.md).
4. **Lifecycle**: `POST /pods` with `dockerStartCmd: ["python", "train.py"]` → S3-poll `s3://<volume>/out/<pod_id>/SUCCESS|FAILURE` for the entrypoint's sentinel → S3-download `out/<pod_id>/` → `DELETE /pods/{id}`. **`desiredStatus` is user-intent, not container state — it never auto-transitions and RunPod auto-restarts the container on exit until you DELETE.** See [pod-lifecycle.md](pod-lifecycle.md).
5. **Artifact retrieval**: `scp -P <tcp_port> root@<public_ip>:/workspace/out/* ./local/` over the **Direct TCP Port 22** mapping (the `ssh.runpod.io` proxy does **not** support SCP/SFTP). See [artifacts.md](artifacts.md).
6. **Pricing**: per-second billing. RTX 4090 (24GB) is plenty for wake-word training. Storage is $0.10/GB-month for container disk while running, $0.20/GB-month for the volume disk while stopped — so **terminate, don't stop**, when the run is done. See [pricing.md](pricing.md).

A complete working orchestration pattern is in [orchestration-recipe.md](orchestration-recipe.md).

## Topics

- **[auth.md](auth.md)** — API keys: where to create, scopes (`All` / `Restricted` / `Read Only`), how the bearer header is shaped, what the user has to do once.
- **[pod-vs-serverless.md](pod-vs-serverless.md)** — Why **Pods** is the right surface for a 30–90 min, run-once-then-exit training job. What Serverless is actually for, and why retrofitting it for batch training is a mistake.
- **[pod-lifecycle.md](pod-lifecycle.md)** — `POST /pods` → S3-poll the volume sentinel → S3-download → `DELETE /pods/{id}`. Why `desiredStatus` is unusable as a completion signal (user-intent, not container-state) and why the container auto-restarts on exit until DELETE.
- **[network-volume-s3.md](network-volume-s3.md)** — RunPod's S3-compatible Network Volume API: endpoint format, dedicated S3 keys (separate from the REST `RUNPOD_API_KEY`), the documented 10K-file/10GB pagination wall, the unsupported bulk `DeleteObjects`, and the empirical paginator-leak / `InvalidArgument`-vs-`NoSuchKey` quirks. Crucial: prefer `aws s3 cp --recursive` over `aws s3 sync` for large local→volume pushes.
- **[rest-api-pods.md](rest-api-pods.md)** — Full request body for `POST /pods`: every field we care about (`imageName`, `gpuTypeIds`, `gpuCount`, `containerDiskInGb`, `volumeInGb`, `dockerStartCmd`, `dockerEntrypoint`, `env`, `ports`, `cloudType`, `supportPublicIp`, `dataCenterIds`, `containerRegistryAuthId`, `interruptible`, `networkVolumeId`).
- **[private-registry.md](private-registry.md)** — `POST /v1/containerregistryauth` to register Docker Hub / GHCR credentials, then pass the returned ID as `containerRegistryAuthId` on `POST /pods`. The token gotchas (GHCR username must be lowercase; whitespace bites).
- **[docker-image.md](docker-image.md)** — Dockerfile constraints: `linux/amd64`, CUDA-bearing base, what the image must do for SCP to work (start sshd if you skip the proxy), and what a sensible base image looks like (`runpod/pytorch:...`, NVIDIA CUDA, plain Ubuntu).
- **[artifacts.md](artifacts.md)** — Getting files OUT of a finished Pod: the SCP/Direct-TCP path (canonical), `runpodctl send`/`receive` (peer-to-peer code-pairing, awkward to script), Cloud Sync (S3/GCS/Azure — works but couples you to a third party), network volumes (works, but only mountable at create-time and only in Secure Cloud).
- **[pricing.md](pricing.md)** — Per-second billing model, GPU-tier ballparks, storage line items, the $80/hr default spend cap, savings plans (irrelevant for one-shot), interruptible/spot (probably not worth it for a 30–90 min run with no checkpointing).
- **[gpu-types.md](gpu-types.md)** — GPU type ID strings as the API expects them. Recommendation tier for wake-word training. T4 is **not** a current RunPod offering.
- **[runpodctl.md](runpodctl.md)** — When `runpodctl` is the right tool (`runpodctl pod create`, the SSH key sync, `runpodctl send`/`receive`) and when it isn't (status polling — use REST). Auth, install one-liner.
- **[python-sdk.md](python-sdk.md)** — The `runpod` PyPI package: what it actually is (a thin GraphQL wrapper for pod ops + a serverless-handler SDK), why we **don't** use its pod CRUD path for new code, and the only pieces we'd consider using.
- **[orchestration-recipe.md](orchestration-recipe.md)** — End-to-end sketch of the launch-poll-pull pattern in plain Python + `httpx` + `subprocess` for SCP. No abstractions, copy-adapt directly.

## Things to ignore (training-data drift)

These are the patterns LLMs will reach for from training data that are **wrong, deprecated, or strictly worse** for the one-shot training use case in this repo. Cross-references go to the topic file with the correct path.

- ❌ **`runpod.create_pod(...)` from the Python SDK** for new code. It's still GraphQL underneath (`runpod/api/ctl_commands.py` calls `run_graphql_query`) and parameter names diverge from REST (`image_name` vs `imageName`, `gpu_type_id` vs `gpuTypeIds`). ✅ Use REST `POST https://rest.runpod.io/v1/pods` with `httpx`/`requests`. See [python-sdk.md](python-sdk.md), [rest-api-pods.md](rest-api-pods.md).
- ❌ **GraphQL endpoint `https://api.runpod.io/graphql`** as the canonical surface. It still works, has no formal deprecation banner, and the spec lives at `graphql-spec.runpod.io`, but the REST API (launched 2025-03-10) covers all the same operations with cleaner shapes and is what new tooling should target. ✅ `https://rest.runpod.io/v1/`. See [pod-lifecycle.md](pod-lifecycle.md).
- ❌ **Serverless endpoints for batch training**. Serverless is queue-and-handler shaped — you author a `handler(event)` worker, build it into an image, deploy it as an *endpoint* with min/max workers, and clients submit *jobs* against it. It's optimized for sub-second-to-minute inference, has cold-start cost, costs more per second than a Pod, and the worker handler model fights the "run a script and exit" shape. ✅ Use Pods. See [pod-vs-serverless.md](pod-vs-serverless.md).
- ❌ **Stopping the Pod when training finishes** ("free tier" instinct: keep the box around in case I need it). Stopped Pods bill volume disk at $0.20/GB-month indefinitely. ✅ `DELETE /pods/{id}` — the artifacts go with it, so SCP first, then delete. See [pricing.md](pricing.md), [pod-lifecycle.md](pod-lifecycle.md).
- ❌ **The `ssh.runpod.io` proxy SSH route for file transfer**. It works for interactive shells but explicitly does **not** support SCP/SFTP — Cloudflare-style proxying that drops the file-transfer subsystems. ✅ Request `supportPublicIp: true`, `cloudType: "SECURE"`, expose port `22/tcp`, and use the Direct-TCP mapping (`ssh -p <port> root@<public_ip>`). See [artifacts.md](artifacts.md).
- ❌ **Pre-built RunPod templates** like `runpod-torch-v21` for a custom training image. Templates are a console-side convenience for deploying *someone else's* image; for your own image you specify `imageName` and friends inline on `POST /pods`. ✅ Specify the image directly. (Templates are still useful if you want to pre-bake an image's full launch config so a UI deploy is one click — not relevant for orchestration code.) See [rest-api-pods.md](rest-api-pods.md).
- ❌ **`countryCodes` / `dataCenterIds` constraint stacked with `cloudType: "SECURE"` and `supportPublicIp: true` and a specific GPU**. Each constraint cuts capacity — over-constraining returns "no machines available" intermittently. ✅ Specify GPU and cloud type, leave geo open unless the user has a reason. See [rest-api-pods.md](rest-api-pods.md).
- ❌ **`interruptible: true` (spot pricing) for a 30–90 min job with no checkpointing**. 5-second eviction warning, restart from scratch. The 20–40% savings are not worth a re-run. ✅ `interruptible: false` (the default). See [pricing.md](pricing.md).
- ❌ **Container disk for outputs.** Container disk is wiped on stop/restart. Volume disk persists for the Pod's lease (deleted on terminate). ✅ Write outputs to `/workspace` (volume mount path), then SCP off **before** `DELETE /pods/{id}`. See [artifacts.md](artifacts.md).
- ❌ **Network volumes as the artifact channel for a one-shot run.** They work but: must attach at create-time only, are Secure Cloud only, are billed continuously even after Pod delete, and getting data off them still requires *some* compute (a Pod or the S3-compatible API). Net: extra moving parts for no win. ✅ SCP off the Pod's volume. See [artifacts.md](artifacts.md).
- ❌ **Polling without a budget cap.** The default $80/hr account spend cap is the only safety net. ✅ Always pair `POST /pods` with a max-wall timeout in your orchestrator, and `DELETE /pods/{id}` in a `finally:` block. See [orchestration-recipe.md](orchestration-recipe.md).
- ❌ **The `runpod` PyPI package being called `runpod-python`.** The repo on GitHub is `runpod/runpod-python`; the install name is `pip install runpod`; the import is `import runpod`. ✅ `pip install runpod`. See [python-sdk.md](python-sdk.md).
- ❌ **Polling `GET /pods/{id}` `.desiredStatus` for completion.** `desiredStatus` is what YOU asked for (`RUNNING` because you POSTed the pod), not what the container is doing. It does not transition on container exit; RunPod auto-restarts the container as long as the pod is leased. ✅ Write a sentinel file at the end of the entrypoint (`/workspace/out/<pod_id>/SUCCESS` or `FAILURE`) and S3-poll the volume for it. The volume is the durable substrate. See [pod-lifecycle.md](pod-lifecycle.md).
- ❌ **`aws s3 sync` against large RunPod Network Volumes (>10K files in the bucket).** Sync lists the remote to compute its diff; RunPod's listing implementation pages through the underlying filesystem and applies the prefix filter post-page, so the `ContinuationToken` can leak across prefix boundaries. boto3 and awscli correctly raise `PaginationError` on duplicate tokens — but a partial sync may have already issued **incorrect deletes** before crashing. Documented by RunPod themselves; their recommended workaround is `aws s3 cp --recursive` (walks local only, never lists remote). ✅ Use `aws s3 cp --recursive` for local→volume; batch by subdir for volume→local. See [network-volume-s3.md](network-volume-s3.md).

## Sources

Anchored 2026-04-25. Each topic file cites its specific URL inline.

- API home: https://docs.runpod.io/api-reference/overview
- OpenAPI spec: https://docs.runpod.io/api-reference/openapi.json
- Pods CRUD: https://docs.runpod.io/api-reference/pods/POST/pods, `.../GET/pods`, `.../GET/pods/{podId}`, `.../DELETE/pods/{podId}`
- Pod lifecycle UX: https://docs.runpod.io/pods/manage-pods
- Pricing: https://docs.runpod.io/pods/pricing
- Storage types: https://docs.runpod.io/pods/storage/types
- Network volumes: https://docs.runpod.io/storage/network-volumes
- Container registry auth: https://docs.runpod.io/api-reference/container-registry-auths/POST/containerregistryauth
- API keys / auth: https://docs.runpod.io/get-started/api-keys
- runpodctl: https://docs.runpod.io/runpodctl/overview, `.../reference/runpodctl-pod`, `.../runpodctl-send`
- Port exposure: https://docs.runpod.io/pods/configuration/expose-ports
- SSH: https://docs.runpod.io/pods/configuration/use-ssh
- Serverless overview: https://docs.runpod.io/serverless/overview
- Serverless pricing: https://docs.runpod.io/serverless/pricing
- Serverless job states: https://docs.runpod.io/serverless/endpoints/job-states
- GPU types: https://docs.runpod.io/references/gpu-types
- runpod-python: https://github.com/runpod/runpod-python (v1.9.0, 2026-04-09)
- REST API launch announcement: https://www.runpod.io/blog/runpod-rest-api-gpu-management (2025-03-10)
- GraphQL spec (still live, no deprecation banner): https://graphql-spec.runpod.io/
