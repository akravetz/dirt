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


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_env() -> None:
    load_dotenv(repo_root() / ".env")


def env(name: str, *, required: bool = True) -> str:
    v = os.environ.get(name, "").strip()
    if required and not v:
        sys.exit(f"error: {name} not set in environment (.env)")
    return v


def client(api_key: str) -> httpx.Client:
    return httpx.Client(
        base_url=REST_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


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


def wait_for_s3_sentinel(
    s3, *, bucket: str, prefix: str, deadline: float, poll_every: int = 30
) -> str:
    """Poll s3://bucket/<prefix>/{SUCCESS,FAILURE} until one appears. Returns
    'SUCCESS' or 'FAILURE'. The pod's `desiredStatus` is user-intent, not
    container state — it never transitions on its own — so we use the
    on-volume sentinel as the actual completion signal."""
    from botocore.exceptions import ClientError

    prefix = prefix.rstrip("/") + "/"
    while time.monotonic() < deadline:
        for sentinel in ("SUCCESS", "FAILURE"):
            try:
                s3.head_object(Bucket=bucket, Key=f"{prefix}{sentinel}")
                return sentinel
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in ("404", "NoSuchKey"):
                    raise
        print(f"  {time.strftime('%H:%M:%S')} (waiting for sentinel at s3://{bucket}/{prefix})")
        time.sleep(poll_every)
    raise TimeoutError(f"sentinel never appeared at s3://{bucket}/{prefix}")


# ---------------------------------------------------------------------------
# Network Volume S3 API. Endpoint: https://s3api-<dc-lower>.runpod.io/.
# Bucket = volume id; volume contents map to bucket-root paths.
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
    local_dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
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
    n = 0
    for path in local_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir).as_posix()
        s3.upload_file(str(path), bucket, f"{prefix.rstrip('/')}/{rel}")
        n += 1
    return n


def s3_delete_prefix(s3, *, bucket: str, prefix: str) -> int:
    keys: list[dict[str, str]] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        keys.extend({"Key": obj["Key"]} for obj in page.get("Contents") or [])
    for i in range(0, len(keys), 1000):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": keys[i:i + 1000]})
    return len(keys)
