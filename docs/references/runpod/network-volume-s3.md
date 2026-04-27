# Network Volume S3-compatible API

RunPod exposes Network Volumes via an S3-compatible HTTPS API. **No pod required**: read/write the volume directly from anywhere with the right credentials. This is the canonical path for moving bytes between local disk and the volume — supersedes the SSH/SCP-via-helper-pod patterns the rest of this pack used to recommend.

Source: https://docs.runpod.io/storage/s3-api (canonical limitations list).

## Endpoint + auth

```
endpoint:  https://s3api-<dc-lower>.runpod.io/
bucket:    <network volume id>          # e.g. jj3zksmx29
region:    <DC code>                    # e.g. US-IL-1
```

Auth uses **separate S3 keys**, NOT the regular `RUNPOD_API_KEY`. Generate them at Console → Settings → S3 API Keys. Two env vars needed:

```
RUNPOD_S3_ACCESS_KEY_ID=user_…
RUNPOD_S3_SECRET_ACCESS_KEY=rps_…
```

boto3 client shape:

```python
boto3.client(
    "s3",
    endpoint_url=f"https://s3api-{dc.lower()}.runpod.io/",
    aws_access_key_id=os.environ["RUNPOD_S3_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["RUNPOD_S3_SECRET_ACCESS_KEY"],
    region_name=dc,
)
```

## Documented limitations

From [docs.runpod.io/storage/s3-api](https://docs.runpod.io/storage/s3-api):

- **`ListObjects`/`ListObjectsV2` warms an ETag cache lazily** for files written outside the S3 API (e.g. via volume mount on a pod). On directories with **>10K files or >10GB**, the listing call may return `503` or fail with pagination errors. **Workaround: retry after a pause** (the cache warms on the first attempt).
- **`aws s3 sync` "may encounter errors when syncing directories with very large numbers of files (over 10,000) or complex nested structures."** RunPod's own recommendation: **prefer `aws s3 cp --recursive` for large dirs**, OR break into smaller batches.
- **Bulk `DeleteObjects` (multi-key delete) is NOT SUPPORTED** — listed as `❌ Planned` in their Core Operations table. **Workaround: loop singular `DeleteObject` calls.**
- **Single-PUT max 500 MB.** Files above that need multipart (boto3 / `aws s3 cp` handles this transparently).

## Empirically observed bugs (not in their docs)

These showed up while building the wake-word harness. Filed as quirks; workarounds in place.

- **`list_objects_v2` paginator leaks `ContinuationToken` across prefix boundaries.** Asked for `Prefix=input/dirt-wakeword-mine/` and got tokens decoding to `working/my_custom_model/.../1087.wav`. boto3 (and awscli) correctly raise `PaginationError: The same next token was received twice` to prevent infinite loops. Root cause is consistent with RunPod's documented model — they page the underlying filesystem and apply the prefix filter post-page. **Workaround: pure-PUT operations (no remote listing) — see "right tool for the job" below.**
- **`KeyCount=0 IsTruncated=True`** sometimes returned for prefixes that demonstrably have keys (verified via direct `head_object`). Same root cause.
- **`get_object` on a missing key returns `InvalidArgument`** instead of standard `NoSuchKey`/`404`. Catch all three error codes.
- **Bulk `DeleteObjects` returns `307 Temporary Redirect`** (rather than a clean 501 Not Implemented). awscli / boto3 do not auto-follow.

## Right tool for the job

| Operation | Tool | Why |
|---|---|---|
| Local → volume, large dir (>1K files) | **`aws s3 cp --recursive`** | Walks local only, never lists remote. Immune to the paginator bug. Re-uploads everything (no diff), but bumps are rare. |
| Local → volume, small dir / single file | `boto3 s3.upload_file` | Direct PUT, no listing. |
| Volume → local, small prefix (<1K files, single subdir) | `aws s3 sync` or `cp --recursive` | Listing scope tight enough to dodge the paginator most of the time; retry-on-PaginationError if it bites. |
| Volume → local, full mirror | **batch by subdir** | Don't list the whole bucket. Iterate known subdirs (`input/dirt-wakeword-mine/`, `out/`, etc.) one at a time and `aws s3 cp --recursive` each. |
| Sentinel poll (single key existence) | `boto3 s3.head_object` | One round-trip, no listing. |
| Single delete | `boto3 s3.delete_object` | Singular form is supported. |
| Bulk delete | **don't** — loop singular `delete_object` instead | `DeleteObjects` returns 307. |
| Read MANIFEST.json (or any single file) | `boto3 s3.get_object` | Single-key ops are reliable. |

## Things to NOT do

- ❌ **`aws s3 sync` against large prefixes (>10K files).** Both `--delete` and the diff-skip step list the remote, which trips the paginator. Even worse, a sync that crashes mid-list **may erroneously delete files** (its diff logic crashes mid-iteration and incorrectly classifies in-source files as "missing from local"). Empirically observed on the `dirt-wakeword-mine` corpus (~30K files). ✅ Use `aws s3 cp --recursive`.
- ❌ **Hand-rolled boto3 upload-then-delete loops.** All the same bugs in raw form. ✅ Shell out to AWS CLI.
- ❌ **Treating S3 listing as authoritative.** The paginator can return `KeyCount=0 IsTruncated=True` while the prefix definitely has keys. ✅ For "does this key exist" use `head_object`.
- ❌ **Catching only `s3.exceptions.NoSuchKey`** when probing for missing files. ✅ Catch `ClientError` and check for `{NoSuchKey, 404, InvalidArgument}`.

## Sources

- [RunPod S3-compatible API docs](https://docs.runpod.io/storage/s3-api) — canonical limitations list
- [runpod/runpod-s3-examples](https://github.com/runpod/runpod-s3-examples) — official example scripts
- aws-cli `s3 sync` source (`awscli/customizations/s3/syncstrategy/`) — sync uses singular `DeleteObject` (not bulk), so `--delete` is safe in principle, but listing still fails before delete
- Empirical: bumps of `dirt-wakeword-validation` (104 files, OK) and `dirt-wakeword-mine` (~2400 files inside a bucket with ~30K total, paginator leaked)
