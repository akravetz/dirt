# Orchestration recipe

End-to-end pattern for "submit one training job, wait, pull artifacts back". Copy-adapt; not framework-y.

Dependencies: `httpx` (or `requests`), `subprocess` (stdlib) for SCP.

## Shape

```
build & push image (offline, before this script runs)
  -> POST /v1/pods                  # spawn
  -> poll GET /v1/pods/{id}          # wait
  -> wait for publicIp + portMappings["22"]   # may not be set immediately after RUNNING
  -> wait for desiredStatus == "EXITED"
  -> scp -P {port} root@{ip}:/workspace/out/. ./local/
  -> read local/SUCCESS sentinel
  -> DELETE /v1/pods/{id}            # ALWAYS, in finally
```

## Reference implementation

```python
"""Submit one training job to RunPod and pull artifacts back."""

from __future__ import annotations

import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import httpx

REST_BASE = "https://rest.runpod.io/v1"
POLL_EVERY_S = 20
MAX_WALL_S = 4 * 60 * 60  # 4 hours, hard cap; expected ~30-90 min
SSH_KEY = Path.home() / ".ssh" / "runpod_ed25519"


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=REST_BASE,
        headers={
            "Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def create_pod(client: httpx.Client, *, name: str, image: str,
               registry_auth_id: str | None) -> str:
    body: dict = {
        "name": name,
        "imageName": image,
        "computeType": "GPU",
        "gpuTypeIds": ["NVIDIA GeForce RTX 4090", "NVIDIA L4", "NVIDIA RTX A4000"],
        "gpuTypePriority": "availability",
        "gpuCount": 1,
        "containerDiskInGb": 50,
        "volumeInGb": 20,
        "volumeMountPath": "/workspace",
        "ports": ["22/tcp"],
        "supportPublicIp": True,
        "cloudType": "SECURE",
        "interruptible": False,
        "env": {
            "WAKE_WORD": "hey-claudia",
            "OUTPUT_DIR": "/workspace/out",
            "PUBLIC_KEY": SSH_KEY.with_suffix(".pub").read_text().strip(),
        },
        "dockerStartCmd": ["python", "/app/train.py"],
    }
    if registry_auth_id:
        body["containerRegistryAuthId"] = registry_auth_id

    r = client.post("/pods", json=body)
    r.raise_for_status()
    return r.json()["id"]


def get_pod(client: httpx.Client, pod_id: str) -> dict:
    r = client.get(f"/pods/{pod_id}")
    r.raise_for_status()
    return r.json()


def delete_pod(client: httpx.Client, pod_id: str) -> None:
    # Best-effort; never raise from the cleanup path.
    try:
        client.delete(f"/pods/{pod_id}").raise_for_status()
    except Exception as exc:
        print(f"WARN: pod {pod_id} delete failed: {exc!r}")


@contextmanager
def leased_pod(name: str, image: str, registry_auth_id: str | None) -> Iterator[str]:
    """Create a pod, yield its id, ALWAYS delete on exit."""
    client = _client()
    pod_id = create_pod(client, name=name, image=image, registry_auth_id=registry_auth_id)
    print(f"created pod {pod_id}")
    try:
        yield pod_id
    finally:
        delete_pod(client, pod_id)
        client.close()


def wait_for_endpoint(client: httpx.Client, pod_id: str,
                      deadline: float) -> tuple[str, int]:
    """Wait until the pod has both a public IP and a TCP-22 mapping. Returns (ip, port)."""
    while time.monotonic() < deadline:
        pod = get_pod(client, pod_id)
        ip = pod.get("publicIp") or ""
        port = (pod.get("portMappings") or {}).get("22")
        if ip and port:
            return ip, int(port)
        time.sleep(5)
    raise TimeoutError(f"pod {pod_id} never published an SSH endpoint")


def wait_for_exit(client: httpx.Client, pod_id: str, deadline: float) -> str:
    """Poll until desiredStatus is EXITED or TERMINATED. Returns the final status."""
    while time.monotonic() < deadline:
        pod = get_pod(client, pod_id)
        status = pod.get("desiredStatus", "")
        if status in ("EXITED", "TERMINATED"):
            return status
        print(f"  pod {pod_id} status={status}, polling...")
        time.sleep(POLL_EVERY_S)
    raise TimeoutError(f"pod {pod_id} did not finish within {MAX_WALL_S}s")


def scp_outputs(*, ip: str, port: int, remote_dir: str, local_dest: Path) -> None:
    local_dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "scp",
            "-i", str(SSH_KEY),
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=/dev/null",
            "-P", str(port),
            "-r",
            f"root@{ip}:{remote_dir}/.",
            str(local_dest),
        ],
        check=True,
    )


def main() -> None:
    image = "ghcr.io/akravetz/dirt-wake-word-trainer:latest"
    registry_auth_id = os.environ.get("RUNPOD_GHCR_AUTH_ID")  # None for public images
    name = f"wakeword-train-{time.strftime('%Y%m%d-%H%M%S')}"
    local_dest = Path(f"var/wake-word/models/{time.strftime('%Y-%m-%d')}")

    deadline = time.monotonic() + MAX_WALL_S

    with leased_pod(name, image, registry_auth_id) as pod_id:
        client = _client()

        # 1. Wait for SSH endpoint (publicIp + portMappings populated)
        ip, port = wait_for_endpoint(client, pod_id, deadline)
        print(f"pod {pod_id} reachable at {ip}:{port}")

        # 2. Wait for the training script to exit
        status = wait_for_exit(client, pod_id, deadline)
        print(f"pod {pod_id} reached status={status}")
        if status != "EXITED":
            raise RuntimeError(f"pod {pod_id} unexpectedly TERMINATED")

        # 3. Pull artifacts BEFORE delete (delete wipes the volume)
        scp_outputs(ip=ip, port=port, remote_dir="/workspace/out", local_dest=local_dest)

        # 4. Verify the success sentinel the trainer wrote on clean exit
        if not (local_dest / "SUCCESS").exists():
            raise RuntimeError(f"training failed (no SUCCESS sentinel in {local_dest})")

        print(f"artifacts pulled to {local_dest}")


if __name__ == "__main__":
    main()
```

## Why each piece is shaped the way it is

- **`leased_pod` context manager.** The `DELETE` MUST run even on exception (KeyboardInterrupt, network blip, scp failure). A `try / finally` block is the minimum viable cleanup; a context manager makes it impossible to forget. See [pod-lifecycle.md](pod-lifecycle.md) on why a forgotten `EXITED` Pod accrues storage charges forever.

- **Two-phase wait** (`wait_for_endpoint`, then `wait_for_exit`).
  - `publicIp` and `portMappings["22"]` are both empty during early `RUNNING` (host scheduling hasn't finished). Polling them at 5 s intervals is fine — they populate within 30–60 s of `desiredStatus == "RUNNING"`.
  - `desiredStatus` is what tells you the container exited; that's the slower, longer poll at 20 s.

- **`MAX_WALL_S` budget.** RunPod will happily run a stuck container forever (and bill you). The orchestrator's wall-clock deadline is the only safety net besides the account-wide $80/hr cap. 4× expected duration is generous; tighten as you trust the pipeline.

- **Sentinel file (`SUCCESS`).** REST does not expose container exit codes. The training script writes `/workspace/out/SUCCESS` on its last line; absence after `EXITED` means a crash. (See [pod-lifecycle.md](pod-lifecycle.md).)

- **SCP **before** DELETE.** Volume disk dies with the Pod on `DELETE`. Pull artifacts first.

- **`StrictHostKeyChecking=accept-new` + `UserKnownHostsFile=/dev/null`.** Each Pod gets a fresh IP; persisting host keys would create a "host key changed" warning on every run. We trade that for a small MITM surface on artifact retrieval — acceptable for non-secret model files. Don't use this pattern for credential transfer.

## Things to NOT add

- **Retries on `POST /pods` failures.** A failed create means RunPod accepted no resource; you can safely call again. But wrap in a retry-with-backoff loop only after diagnosing — most "no machines available" failures need you to relax constraints, not retry the same body.
- **Background polling.** Plain blocking polls are fine for a CLI orchestrator. Async is overkill.
- **A wrapper class.** This is a one-shot script; don't introduce `RunPodClient` abstractions before the second use case shows up.

## Sources

All field choices and endpoint shapes cite back to:

- https://docs.runpod.io/api-reference/pods/POST/pods
- https://docs.runpod.io/api-reference/pods/GET/pods (response shape, status enum)
- https://docs.runpod.io/api-reference/pods/DELETE/pods/{podId}
- https://docs.runpod.io/pods/configuration/use-ssh
- https://docs.runpod.io/pods/configuration/expose-ports
- https://docs.runpod.io/pods/storage/types
- https://docs.runpod.io/pods/pricing
