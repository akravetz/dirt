"""Shared RunPod orchestration primitives for the wake-word scripts.

`scripts/runpod-train` and `scripts/runpod-seed-volume` both POST a pod
spec, poll its lifecycle, and DELETE in a finally block. This module
holds the bits they share: REST client, env loading, common pod body
fields, lifecycle helpers, and SCP. Each caller still owns its own
script-specific body fields (GPU type, dockerStartCmd, etc.).

Reference doc: docs/references/runpod/orchestration-recipe.md.

Importable as `_runpod_lib` from sibling scripts via:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _runpod_lib as rp
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv

REST_BASE = "https://rest.runpod.io/v1"
SSH_KEY_PATH = Path.home() / ".ssh" / "runpod_ed25519"


def repo_root() -> Path:
    """Resolve the repo root from this file's location (scripts/ → repo)."""
    return Path(__file__).resolve().parent.parent


def env(name: str, *, required: bool = True) -> str:
    """Read an env var (after `.env` has been loaded). Exits if required+missing."""
    v = os.environ.get(name, "").strip()
    if required and not v:
        sys.exit(f"error: {name} not set in environment (.env)")
    return v


def load_env() -> None:
    """Load `.env` from the repo root. Idempotent — safe to call multiple times."""
    load_dotenv(repo_root() / ".env")


def public_key(*, required: bool) -> str:
    """Read ~/.ssh/runpod_ed25519.pub. Empty string if optional and missing."""
    pub = SSH_KEY_PATH.with_suffix(".pub")
    if pub.exists():
        return pub.read_text().strip()
    if required:
        sys.exit(
            f"error: missing SSH public key at {pub}\n"
            "  Generate with: ssh-keygen -t ed25519 -f ~/.ssh/runpod_ed25519 -N ''\n"
            "  Then upload the .pub at https://www.console.runpod.io/user/settings"
        )
    return ""


def client(api_key: str) -> httpx.Client:
    """REST client with bearer auth + JSON content type."""
    return httpx.Client(
        base_url=REST_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def common_pod_body(
    *,
    name: str,
    network_volume_id: str,
    public_key: str,
) -> dict:
    """Fields every pod we create needs. Caller adds compute/image/cmd."""
    return {
        "name": name,
        "networkVolumeId": network_volume_id,
        "volumeMountPath": "/workspace",
        "ports": ["22/tcp"],
        "supportPublicIp": True,
        "cloudType": "SECURE",
        "interruptible": False,
        "env": {"PUBLIC_KEY": public_key} if public_key else {},
    }


def create_pod(http: httpx.Client, body: dict) -> str:
    """POST /pods, exit on 4xx/5xx, return new pod id."""
    r = http.post("/pods", json=body)
    if r.status_code >= 400:
        sys.exit(f"error: POST /pods → {r.status_code}: {r.text}")
    return r.json()["id"]


def get_pod(http: httpx.Client, pod_id: str) -> dict:
    r = http.get(f"/pods/{pod_id}")
    r.raise_for_status()
    return r.json()


def delete_pod(http: httpx.Client, pod_id: str) -> None:
    """Best-effort delete. Cleanup must not mask the original failure."""
    try:
        http.delete(f"/pods/{pod_id}").raise_for_status()
        print(f"deleted pod {pod_id}")
    except httpx.HTTPError as exc:
        print(f"WARN: pod {pod_id} delete failed: {exc!r}", file=sys.stderr)


@contextmanager
def leased_pod(
    http: httpx.Client, pod_id: str, *, keep_on_success: bool = False
) -> Iterator[None]:
    """Always DELETE on exit unless keep_on_success and the block raised nothing."""
    succeeded = False
    try:
        yield
        succeeded = True
    finally:
        if keep_on_success and succeeded:
            print(f"--keep set; leaving pod {pod_id} alive (DELETE manually)")
        else:
            delete_pod(http, pod_id)


def wait_for_endpoint(
    http: httpx.Client, pod_id: str, *, deadline: float, poll_every: int = 5
) -> tuple[str, int]:
    """Block until publicIp + portMappings['22'] are populated."""
    while time.monotonic() < deadline:
        pod = get_pod(http, pod_id)
        ip = (pod.get("publicIp") or "").strip()
        port = (pod.get("portMappings") or {}).get("22")
        if ip and port:
            return ip, int(port)
        time.sleep(poll_every)
    raise TimeoutError(f"pod {pod_id} never published an SSH endpoint")


def wait_for_exit(
    http: httpx.Client,
    pod_id: str,
    *,
    deadline: float,
    poll_every: int = 20,
) -> str:
    """Block until desiredStatus is EXITED or TERMINATED. Print every poll."""
    while time.monotonic() < deadline:
        pod = get_pod(http, pod_id)
        status = pod.get("desiredStatus", "")
        ts = time.strftime("%H:%M:%S")
        print(f"  {ts} pod {pod_id} status={status}")
        if status in ("EXITED", "TERMINATED"):
            return status
        time.sleep(poll_every)
    raise TimeoutError(
        f"pod {pod_id} did not reach a terminal state within deadline"
    )


def scp_pull(
    *,
    ip: str,
    port: int,
    remote_dir: str,
    local_dest: Path,
    ssh_key: Path = SSH_KEY_PATH,
) -> None:
    """SCP-r remote_dir/* into local_dest. Throws on failure."""
    local_dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "scp",
            "-i", str(ssh_key),
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=/dev/null",
            "-P", str(port),
            "-r",
            f"root@{ip}:{remote_dir}/.",
            str(local_dest),
        ],
        check=True,
    )
