# REST API: `POST /v1/pods`

Source for everything in this file: https://docs.runpod.io/api-reference/pods/POST/pods (PodCreateInput schema) and https://docs.runpod.io/api-reference/openapi.json.

Base URL: `https://rest.runpod.io/v1/`. All requests need:

```
Authorization: Bearer $RUNPOD_API_KEY
Content-Type: application/json
```

## Minimal body for one-shot training

```json
{
  "name": "wakeword-train-2026-04-25",
  "imageName": "ghcr.io/akravetz/dirt-wake-word-trainer:latest",
  "containerRegistryAuthId": "<id from POST /v1/containerregistryauth>",
  "computeType": "GPU",
  "gpuTypeIds": ["NVIDIA GeForce RTX 4090"],
  "gpuCount": 1,
  "containerDiskInGb": 50,
  "volumeInGb": 20,
  "volumeMountPath": "/workspace",
  "ports": ["22/tcp"],
  "supportPublicIp": true,
  "cloudType": "SECURE",
  "interruptible": false,
  "env": {
    "WAKE_WORD": "hey-claudia",
    "OUTPUT_DIR": "/workspace/out"
  },
  "dockerStartCmd": ["python", "/app/train.py"]
}
```

Returns `201` with a `Pod` body — only `id` and `desiredStatus` matter for orchestration; everything else is for diagnostics.

## Field reference (only the fields that matter for batch training)

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | `"my pod"` | Max 191 chars. Show up in console. |
| `imageName` | string | — | Docker image tag, e.g. `ghcr.io/owner/img:tag`. **Public Docker Hub images** (`runpod/pytorch:...`) need no auth. Private images need `containerRegistryAuthId`. |
| `containerRegistryAuthId` | string | — | ID returned by `POST /v1/containerregistryauth`. Required for private images. See [private-registry.md](private-registry.md). |
| `templateId` | string | — | Use a pre-saved template instead of inline image+config. Skip for one-shot. |
| `computeType` | enum | `"GPU"` | `"GPU"` or `"CPU"`. |
| `gpuTypeIds` | string[] | — | Array of GPU model strings. The string is the API ID, e.g. `"NVIDIA GeForce RTX 4090"`, `"NVIDIA L4"`, `"NVIDIA A40"`. See [gpu-types.md](gpu-types.md). Pass multiple to allow fallback. |
| `gpuCount` | int | `1` | |
| `gpuTypePriority` | enum | `"availability"` | `"availability"` (RunPod picks among `gpuTypeIds` based on what's free) or `"custom"` (strict order). |
| `vcpuCount` | int | `2` | CPU pods only — for GPU pods you get scaled vCPU based on GPU count. |
| `minRAMPerGPU` | int (GB) | `8` | |
| `minVCPUPerGPU` | int | `2` | |
| `containerDiskInGb` | int | `50` | Ephemeral. **Wiped on stop.** Sized for image + scratch. |
| `volumeInGb` | int | `20` | Persistent for Pod's lease, mounted at `volumeMountPath`. **Survives stop, dies on delete.** Size for outputs. |
| `volumeMountPath` | string | `"/workspace"` | Where the volume mounts inside the container. |
| `networkVolumeId` | string | — | Attach an existing network volume. Mutually exclusive with `volumeInGb`. Mounts at `volumeMountPath`, replacing the volume disk. **Cannot be detached without deleting the Pod.** Secure Cloud only. |
| `dockerEntrypoint` | string[] | — | Override the image's `ENTRYPOINT`. |
| `dockerStartCmd` | string[] | — | Override the image's `CMD`. **This is where you put `["python", "train.py"]`.** |
| `env` | object | `{}` | String→string. Available as env vars in the container. |
| `ports` | string[] | `["8888/http", "22/tcp"]` | `[port]/[protocol]`. **For SCP set `["22/tcp"]`** so the platform allocates a public TCP port mapping. |
| `supportPublicIp` | bool | — | **Set `true` to get a routable public IP** (Community Cloud only). For Secure Cloud, public IP is implicit when you expose a TCP port. |
| `globalNetworking` | bool | `false` | Enable global networking. Not needed for batch. |
| `cloudType` | enum | `"SECURE"` | `"SECURE"` (datacenter machines, more reliable, slightly more expensive) or `"COMMUNITY"` (host-provided, cheaper, more variable). For training: SECURE. |
| `dataCenterIds` | string[] | — | E.g. `["US-IL-1", "US-TX-1"]`. Restrict to specific DCs. **Don't set unless needed** — over-constrains capacity. |
| `dataCenterPriority` | enum | `"availability"` | Same shape as `gpuTypePriority`. |
| `countryCodes` | string[] | — | Country code restriction. Don't set unless needed. |
| `allowedCudaVersions` | string[] | — | E.g. `["12.1", "12.4"]`. Constrains the host kernel CUDA. Set if your image has a CUDA version requirement. |
| `interruptible` | bool | `false` | `true` enables spot pricing (~20–40% off) but with a **5-second eviction warning**. **Keep `false` for one-shot training without checkpointing.** |
| `locked` | bool | `false` | Prevents stop/reset via console. Not needed. |
| `minDownloadMbps`, `minUploadMbps`, `minDiskBandwidthMBps` | number | — | Network/disk perf floors. Don't set unless you've measured a need. |

## Response

```json
{
  "id": "xedezhzb9la3ye",
  "name": "wakeword-train-2026-04-25",
  "image": "ghcr.io/akravetz/dirt-wake-word-trainer:latest",
  "desiredStatus": "RUNNING",
  "costPerHr": 0.74,
  "adjustedCostPerHr": 0.69,
  "gpu": { "id": "...", "count": 1, "displayName": "NVIDIA GeForce RTX 4090" },
  "machine": { "gpuTypeId": "...", "dataCenterId": "US-IL-1", "location": "Chicago, IL, United States" },
  "memoryInGb": 62,
  "vcpuCount": 24,
  "volumeInGb": 20,
  "volumeMountPath": "/workspace",
  "containerDiskInGb": 50,
  "ports": ["22/tcp"],
  "portMappings": { "22": 10341 },
  "publicIp": "100.65.0.119",
  "env": { "WAKE_WORD": "hey-claudia" },
  "lastStartedAt": "2026-04-25T19:14:40.144Z"
}
```

Two fields you'll need post-create:

- **`portMappings["22"]`** — the externally-routable TCP port mapped to internal port 22. Use this for SCP.
- **`publicIp`** — the routable IP. **Empty string while initializing.** Re-`GET` until populated.

Both also get exposed inside the container as env vars `RUNPOD_TCP_PORT_22` (the external port) and `RUNPOD_PUBLIC_IP`. (Source: https://docs.runpod.io/pods/configuration/expose-ports.)

## Common gotchas

- **`gpuTypeIds` is an array, not a string.** Single-GPU jobs still pass `["NVIDIA GeForce RTX 4090"]`.
- **The GPU type strings are the human display names**, not opaque IDs. The exception is the GraphQL surface, which uses internal IDs like `NVIDIA GeForce RTX 4090`. REST accepts the display name.
- **Public Docker Hub images need no `containerRegistryAuthId`.** Private GHCR / private Docker Hub / ECR / GCR all need one.
- **`volumeInGb=0` is not valid.** If you want zero persistent volume, you can't — minimum is 1. For one-shot training where you SCP off and delete, 20–50 GB is fine.
- **`ports`: `"22/tcp"` exposes SSH; `"8888/http"` would route through the proxy. For SCP, `tcp` is mandatory.** The `http` protocol routes through `*.proxy.runpod.net` which does not pass SCP/SFTP.
- **Errors come back as `{"error": "..."}`** with HTTP 4xx. The most common is "no machines available with these constraints" (HTTP 400 or 503 depending on cause) — relax `dataCenterIds`, drop `countryCodes`, or add more entries to `gpuTypeIds`.

## Sources

- https://docs.runpod.io/api-reference/pods/POST/pods
- https://docs.runpod.io/api-reference/openapi.json
- https://docs.runpod.io/pods/storage/types
- https://docs.runpod.io/pods/configuration/expose-ports
- https://docs.runpod.io/storage/network-volumes
