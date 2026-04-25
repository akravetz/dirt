# `runpod` Python package

PyPI: `runpod` (v1.9.0 as of 2026-04-09). GitHub: `runpod/runpod-python`. The package name on PyPI is `runpod`, the import is `import runpod`, the repo is `runpod-python`. (Source: https://github.com/runpod/runpod-python.)

## What it is

Two unrelated halves bundled in one package:

1. **A GraphQL wrapper for pod / endpoint / template / volume management** (`runpod.api.ctl_commands`). Functions like `create_pod`, `get_pod`, `stop_pod`, `terminate_pod`, `resume_pod`. Underneath, every call hits `https://api.runpod.io/graphql` via `run_graphql_query()`. (Source: https://github.com/runpod/runpod-python/blob/main/runpod/api/ctl_commands.py.)
2. **A serverless-worker SDK** (`runpod.serverless`) for authoring `handler(event)` functions and starting a worker (`runpod.serverless.start({"handler": ...})`).

## Why we don't use the pod-management half

The package's `create_pod()` etc. is a thin, somewhat-stale wrapper over the **GraphQL** API. Specific issues for new code:

- **Field names diverge from REST** — `image_name` (Python) vs `imageName` (REST), `gpu_type_id` singular (Python) vs `gpuTypeIds` plural array (REST), `docker_args` vs `dockerStartCmd`. Maintaining a mental mapping for no benefit.
- **GraphQL is the older surface.** REST launched 2025-03-10 (https://www.runpod.io/blog/runpod-rest-api-gpu-management) with cleaner shapes and is what the docs front-of-house now leads with.
- **The Python SDK doesn't expose every REST field.** No first-class `containerRegistryAuthId`, no `cloudType` (it has `cloud_type` but the value enum is GraphQL-shaped), no clean way to set `supportPublicIp`.
- **Error handling collapses** — GraphQL errors come back as `{"errors": [...]}` and the wrapper doesn't always surface them informatively.

Net: for orchestration code, **call REST directly with `httpx` or `requests`**.

## When you'd still reach for it

- **Serverless workers.** If we ever do build a Serverless worker (we won't, see [pod-vs-serverless.md](pod-vs-serverless.md)), the `runpod.serverless` half is the only sane way — RunPod's worker-protocol expectations are baked into it.
- **Quick interactive scripting** in a notebook where ergonomics beat field-coverage. `runpod.api_key = "..."; runpod.get_pods()` is fine for "show me what's running".

## Function signatures (for completeness)

From `runpod-python` v1.9.0 (https://github.com/runpod/runpod-python/blob/main/runpod/api/ctl_commands.py):

```python
runpod.api_key: str  # module-level

runpod.get_pods(api_key: Optional[str] = None) -> list[dict]
runpod.get_pod(pod_id: str, api_key: Optional[str] = None) -> dict
runpod.create_pod(
    name: str,
    image_name: str,
    gpu_type_id: str,
    cloud_type: str = "ALL",
    support_public_ip: bool = True,
    start_ssh: bool = True,
    data_center_id: Optional[str] = None,
    country_code: Optional[str] = None,
    gpu_count: int = 1,
    volume_in_gb: int = 0,
    container_disk_in_gb: int = 50,
    min_vcpu_count: int = 1,
    min_memory_in_gb: int = 1,
    docker_args: str = "",
    ports: Optional[str] = None,
    volume_mount_path: str = "/runpod-volume",
    env: Optional[dict] = None,
    template_id: Optional[str] = None,
    network_volume_id: Optional[str] = None,
    allowed_cuda_versions: Optional[list[str]] = None,
    min_download: Optional[int] = None,
    min_upload: Optional[int] = None,
    instance_id: Optional[str] = None,
) -> dict
runpod.stop_pod(pod_id: str) -> dict
runpod.resume_pod(pod_id: str, gpu_count: int) -> dict
runpod.terminate_pod(pod_id: str) -> dict
```

Mapping to REST equivalents in [rest-api-pods.md](rest-api-pods.md):

| Python SDK | REST |
|---|---|
| `image_name` | `imageName` |
| `gpu_type_id` (single) | `gpuTypeIds` (array) |
| `gpu_count` | `gpuCount` |
| `volume_in_gb` | `volumeInGb` |
| `container_disk_in_gb` | `containerDiskInGb` |
| `cloud_type` ("ALL"/"COMMUNITY"/"SECURE") | `cloudType` ("SECURE"/"COMMUNITY") |
| `support_public_ip` | `supportPublicIp` |
| `data_center_id` (single) | `dataCenterIds` (array) |
| `docker_args` (string) | `dockerStartCmd` (array) |
| `ports` (string `"22/tcp,8888/http"`) | `ports` (array `["22/tcp", "8888/http"]`) |
| `volume_mount_path` | `volumeMountPath` (note: SDK default is `/runpod-volume`, REST default is `/workspace`) |
| `env` (dict) | `env` (object) |
| `template_id` | `templateId` |
| `network_volume_id` | `networkVolumeId` |
| `allowed_cuda_versions` | `allowedCudaVersions` |
| `terminate_pod` | `DELETE /v1/pods/{id}` |
| `stop_pod` | `POST /v1/pods/{id}/stop` |
| `resume_pod` | `POST /v1/pods/{id}/start` |

## Sources

- https://github.com/runpod/runpod-python (HEAD, v1.9.0 @ 2026-04-09)
- https://github.com/runpod/runpod-python/blob/main/runpod/api/ctl_commands.py
- https://docs.runpod.io/serverless/sdks
- https://www.runpod.io/blog/runpod-rest-api-gpu-management
