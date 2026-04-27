"""Shared RunPod primitives: REST control-plane + Network Volume S3 access."""

from __future__ import annotations

import os
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
    return Path(__file__).resolve().parent.parent


def load_env() -> None:
    load_dotenv(repo_root() / ".env")


def env(name: str, *, required: bool = True) -> str:
    v = os.environ.get(name, "").strip()
    if required and not v:
        sys.exit(f"error: {name} not set in environment (.env)")
    return v


def public_key(*, required: bool) -> str:
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
    return httpx.Client(
        base_url=REST_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def common_pod_body(*, name: str, network_volume_id: str, public_key: str) -> dict:
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
    r = http.post("/pods", json=body)
    if r.status_code >= 400:
        sys.exit(f"error: POST /pods → {r.status_code}: {r.text}")
    return r.json()["id"]


def get_pod(http: httpx.Client, pod_id: str) -> dict:
    r = http.get(f"/pods/{pod_id}")
    r.raise_for_status()
    return r.json()


def delete_pod(http: httpx.Client, pod_id: str) -> None:
    try:
        http.delete(f"/pods/{pod_id}").raise_for_status()
        print(f"deleted pod {pod_id}")
    except httpx.HTTPError as exc:
        print(f"WARN: pod {pod_id} delete failed: {exc!r}", file=sys.stderr)


@contextmanager
def leased_pod(
    http: httpx.Client, pod_id: str, *, keep_on_success: bool = False
) -> Iterator[None]:
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
    while time.monotonic() < deadline:
        pod = get_pod(http, pod_id)
        ip = (pod.get("publicIp") or "").strip()
        port = (pod.get("portMappings") or {}).get("22")
        if ip and port:
            return ip, int(port)
        time.sleep(poll_every)
    raise TimeoutError(f"pod {pod_id} never published an SSH endpoint")


def wait_for_exit(
    http: httpx.Client, pod_id: str, *, deadline: float, poll_every: int = 20
) -> str:
    while time.monotonic() < deadline:
        pod = get_pod(http, pod_id)
        status = pod.get("desiredStatus", "")
        print(f"  {time.strftime('%H:%M:%S')} pod {pod_id} status={status}")
        if status in ("EXITED", "TERMINATED"):
            return status
        time.sleep(poll_every)
    raise TimeoutError(f"pod {pod_id} did not reach a terminal state within deadline")


# ---------------------------------------------------------------------------
# Network Volume S3 API. Endpoint format: https://s3api-<dc-lower>.runpod.io/.
# Bucket name = volume id; volume contents map to bucket-root paths.
# Authenticated with separate S3 keys (RUNPOD_S3_*), not the REST API key.
# ---------------------------------------------------------------------------


def s3_client():
    import boto3

    dc = os.environ.get("RUNPOD_VOLUME_DATACENTER", "US-IL-1")
    return boto3.client(
        "s3",
        endpoint_url=f"https://s3api-{dc.lower()}.runpod.io/",
        aws_access_key_id=env("RUNPOD_S3_ACCESS_KEY_ID"),
        aws_secret_access_key=env("RUNPOD_S3_SECRET_ACCESS_KEY"),
        region_name=dc,
    )


def s3_download_prefix(s3, *, bucket: str, prefix: str, local_dest: Path) -> int:
    """Download every key under prefix into local_dest, preserving relative paths."""
    local_dest.mkdir(parents=True, exist_ok=True)
    paginator = s3.get_paginator("list_objects_v2")
    n = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            key = obj["Key"]
            rel = key[len(prefix):].lstrip("/")
            if not rel:
                continue
            dst = local_dest / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(dst))
            n += 1
    return n


def s3_upload_dir(s3, *, local_dir: Path, bucket: str, prefix: str) -> int:
    """Upload every file under local_dir to bucket/prefix/<relpath>."""
    n = 0
    for path in local_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir).as_posix()
        s3.upload_file(str(path), bucket, f"{prefix.rstrip('/')}/{rel}")
        n += 1
    return n


def s3_delete_prefix(s3, *, bucket: str, prefix: str) -> int:
    """Delete every key under prefix. Used to clear a per-run dir before upload."""
    paginator = s3.get_paginator("list_objects_v2")
    keys: list[dict[str, str]] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend({"Key": obj["Key"]} for obj in page.get("Contents") or [])
    for i in range(0, len(keys), 1000):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": keys[i:i + 1000]})
    return len(keys)
