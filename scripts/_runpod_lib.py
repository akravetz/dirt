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
# Network Volume S3 client. Endpoint: https://s3api-<dc-lower>.runpod.io/.
# Bucket = volume id; volume contents map to bucket-root paths. Bulk
# transfers use `aws s3 sync` (CLI shell-out) to dodge two RunPod-S3 bugs:
# bulk DeleteObjects 307s, and list_objects_v2 paginator leaks tokens
# across prefixes. The single-key get_object/put_object/head_object
# operations the boto3 client is used for here are not affected.
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
