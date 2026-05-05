from __future__ import annotations

from collections.abc import Sequence

import boto3

from dirt_control.settings import CloudSettings


class S3ObjectStore:
    def __init__(self, *, settings: CloudSettings) -> None:
        self._bucket_name = settings.bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def delete_objects(self, object_keys: Sequence[str]) -> int:
        deleted = 0
        for start in range(0, len(object_keys), 1000):
            chunk = object_keys[start : start + 1000]
            if not chunk:
                continue
            response = self._client.delete_objects(
                Bucket=self._bucket_name,
                Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
            )
            deleted += len(response.get("Deleted", []))
        return deleted
