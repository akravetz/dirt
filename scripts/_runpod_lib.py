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
                code = exc.response["Error"]["Code"]
                if code in ("401", "403", "Unauthorized", "AccessDenied"):
                    print(
                        f"  {time.strftime('%H:%M:%S')} transient S3 auth error "
                        f"while polling {sentinel}: {code}; retrying"
                    )
                    continue
                if code not in ("404", "NoSuchKey"):
                    raise
        print(
            f"  {time.strftime('%H:%M:%S')} (waiting for sentinel at s3://{bucket}/{prefix})"
        )
        time.sleep(poll_every)
    raise TimeoutError(f"sentinel never appeared at s3://{bucket}/{prefix}")


# ---------------------------------------------------------------------------
# Network Volume S3 client. Endpoint: https://s3api-<dc-lower>.runpod.io/.
# Bucket = volume id; volume contents map to bucket-root paths. RunPod's
# list_objects_v2 leaks ContinuationTokens across prefixes (returns
# IsTruncated=True / KeyCount=0 with cursors pointing OUTSIDE the requested
# Prefix), so anything that lists — `aws s3 sync`, `aws s3 rm --recursive`,
# the boto3 paginator — eventually crashes with "same next token received
# twice". Single-key head_object / get_object / put_object / delete_object
# work fine. Pull artifacts by known filename instead of listing.
# ---------------------------------------------------------------------------

# Wake-word training artifacts written to /workspace/out/<pod_id>/ by the
# trainer entrypoint. Used by both runpod-train (post-sentinel pull) and
# wakeword-pull-pod-out (manual recovery). Sentinels first so the function
# can decide success/failure without a separate pass.
TRAINER_ARTIFACTS: tuple[str, ...] = (
    "SUCCESS",
    "FAILURE",
    "hey_claudia.onnx",
    "run-manifest.json",
    "validation-report.txt",
)


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


def pull_artifacts(
    s3, *, bucket: str, prefix: str, dest: Path, filenames: tuple[str, ...]
) -> int:
    """Download each known filename under prefix into dest. Returns count
    pulled. Missing files (404 / NoSuchKey / InvalidArgument) are reported
    and skipped — typical case is FAILURE absent on success runs and vice
    versa. Built around RunPod's broken listing — never use `aws s3 sync`."""
    from botocore.exceptions import ClientError

    prefix = prefix.rstrip("/") + "/"
    dest.mkdir(parents=True, exist_ok=True)
    pulled = 0
    for fn in filenames:
        try:
            s3.download_file(bucket, f"{prefix}{fn}", str(dest / fn))
            sz = (dest / fn).stat().st_size
            print(f"  pulled  {fn:<24}  ({sz} bytes)")
            pulled += 1
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchKey", "InvalidArgument"):
                print(f"  absent  {fn}")
            else:
                raise
    return pulled
