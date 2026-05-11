# Reusable Camera Edge Nodes

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt can run camera capture on more than one host without building one-off scripts for each tent. The immediate user-visible result is that `dirt2`, the LAN box attached to the breeding-tent camera, captures periodic breeding-tent photos and uploads them as private cloud assets under `homebox/breeding`. The hosted UI and API then show the breeding tent with fresh imagery the same way the main tent already has recent photos.

This matters because the project is moving from a single grow-box camera to modular, analogous hardware across tents. Camera capture should be reusable infrastructure: a host-local camera driver captures frames, shared snapshot code records scoped metadata, and shared cloud asset code publishes images through the existing signed upload contract. The OBSBOT-specific daemon remains a low-level device driver; Dirt-level services should not hard-code OBSBOT, `/dev/video0`, or one physical tent into their architecture.

The working behavior is observable by running a camera-agent service on `dirt2`, seeing successful systemd status and structured logs, finding JPEGs in its local spool, and fetching a signed hosted asset for `tent_id=breeding`.


## Progress

- [x] (2026-05-10T00:00Z) Confirmed `ssh dirt2` works as user `akcom` after adding the `dirt2` host key alias to local `known_hosts`.
- [x] (2026-05-10T00:00Z) Documented `dirt2` SSH access in `docs/commands.md`.
- [x] (2026-05-10T00:00Z) Documented the breeding-tent camera role for `dirt2` in `wiki/hardware/ptz-camera.md`.
- [x] (2026-05-10T00:00Z) Inspected `dirt2` hardware: the camera appears as OBSBOT Tiny 2 Lite USB device `3564:fef9` with `/dev/video0` and `/dev/video1`, and user `akcom` is in the `video` group.
- [x] (2026-05-10T00:00Z) Created this ExecPlan as the canonical implementation plan.
- [ ] Milestone 1: Extract reusable camera-source and snapshot-spool primitives without changing runtime behavior.
- [ ] Milestone 2: Refactor main-tent capture onto the shared primitives while preserving current `dirt-hwd` behavior.
- [ ] Milestone 3: Extract shared cloud asset upload code and make `dirt-gateway` use it.
- [ ] Milestone 4: Add the camera-agent service for edge camera hosts.
- [ ] Milestone 5: Deploy and smoke test `dirt-camera-daemon` plus camera-agent on `dirt2`.
- [ ] Milestone 6: Enable real breeding-tent asset uploads and verify hosted access.


## Surprises & Discoveries

- Observation: `dirt2` currently has the same OBSBOT Tiny 2 Lite USB identity as the main PTZ setup, not an unrelated camera class.
  Evidence: `ssh dirt2 'lsusb; v4l2-ctl --list-devices'` showed `3564:fef9 Remo Tech Co., Ltd. OBSBOT Tiny 2 Lite` and `/dev/video0`, `/dev/video1`.

- Observation: The existing `dirt-camera-daemon` is already a good low-level device-driver boundary for OBSBOT cameras.
  Evidence: `services/camera-daemon/src/commands.cpp` owns OBSBOT motor and zoom commands, partial-move retry, and line-oriented protocol dispatch; `services/camera-daemon/src/capture.cpp` owns V4L2 streaming, fresh-frame buffering, reconnect, and tempfile capture.

- Observation: The current gateway asset projection uploads at most one latest snapshot per sync cycle, preferring the default tent.
  Evidence: `apps/gateway/src/dirt_gateway/local.py::latest_snapshot_asset()` iterates tents sorted by default-first order and returns immediately after the first uploadable snapshot. This can starve non-default tent images if they rely on the main gateway path.

- Observation: `dirt2` should not run the full `dirt-gateway` as-is.
  Evidence: `dirt-gateway` sends site-level heartbeats, catalog, latest metrics, rollups, command claims, command results, assets, and retention. A camera-only edge node should not make the hosted control plane believe the main hardware controller is healthy or claim site commands.


## Decision Log

- Decision: Keep `dirt-camera-daemon` as a concrete OBSBOT camera driver, not as the Dirt-level camera application boundary.
  Rationale: The daemon correctly owns hardware-specific C++/SDK/V4L2 concerns: SDK lifecycle, gimbal movement, USB reconnect, frame buffering, and camera watchdogs. It should not learn about `site_id`, `tent_id`, Postgres, cloud credentials, or signed asset uploads.
  Date/Author: 2026-05-10 / Codex

- Decision: Introduce a shared camera-source interface above device drivers.
  Rationale: The first implementation can talk to the existing OBSBOT daemon over its Unix socket. Future implementations can use direct V4L2, RTSP/IP camera streams, or another vendor PTZ driver without changing snapshot scheduling, metadata, or cloud upload code.
  Date/Author: 2026-05-10 / Codex

- Decision: Build `dirt2` as a camera edge node, not a second full site gateway.
  Rationale: `dirt2` only needs camera capture and asset publishing for `homebox/breeding`. Full gateway behavior includes heartbeats and command claiming that should remain owned by the main controller unless `dirt2` later becomes a broader hardware authority.
  Date/Author: 2026-05-10 / Codex

- Decision: Reuse the existing gateway asset contract for camera-agent uploads.
  Rationale: `AssetSignUploadRequest`, `SignUploadResponse`, `AssetCompleteRequest`, `AssetCompleteResponse`, and `AssetFailureRequest` already model the cloud asset boundary. The camera-agent should share these Pydantic DTOs and the HTTP uploader implementation rather than hand-building raw JSON.
  Date/Author: 2026-05-10 / Codex

- Decision: Prefer a local spool on every camera host.
  Rationale: A spool gives retry/recovery room when cloud upload fails, provides local diagnostic artifacts, and keeps capture decoupled from network availability. Retention can be local and conservative because cloud assets have their own hosted retention.
  Date/Author: 2026-05-10 / Codex


## Outcomes & Retrospective

No implementation milestones are complete yet. This plan records the agreed architecture and the verified `dirt2` hardware/access baseline.


## Context and Orientation

Dirt currently has one main local controller. Python services live under `apps/`, shared code under `apps/shared`, systemd user units under `systemd/`, and hardware/wiki docs under `wiki/`. Commands and operational entry points are documented in `docs/commands.md`.

The current main camera stack has these layers:

- `services/camera-daemon/`: C++ OBSBOT daemon. It speaks a line-oriented Unix-socket protocol. Its `capture` command writes a recent JPEG frame to a tempfile and returns the path. Its `move_motor` and `set_zoom` commands use the OBSBOT SDK.
- `scripts/camera`: Python operator CLI. It loads `~/.config/dirt/camera.json`, translates user-frame controls into motor-frame commands, and talks to the daemon.
- `apps/shared/src/dirt_shared/services/capture.py`: Python `CaptureService` used by `dirt-hwd`. It calls the daemon's `capture` command, writes a snapshot JPEG under `var/snapshots`, and inserts a `snapshot` DB row scoped to `homebox/main` with device `obsbot-main`.
- `apps/gateway/src/dirt_gateway/local.py`: Gateway local projection code. It reads `snapshot` rows and produces asset upload projections.
- `apps/gateway/src/dirt_gateway/sync.py` and `apps/gateway/src/dirt_gateway/cloud.py`: Gateway delivery code. It signs upload URLs, uploads bytes, completes assets, reports failures, and prunes expired cloud assets.
- `apps/control-plane/src/dirt_control/api/gateway.py`: Hosted control-plane gateway routes for `/api/gateway/v1/assets/sign-upload`, `/assets/complete`, `/assets/upload-failure`, and retention.

Important repository rules:

- Read `docs/commands.md` before running commands.
- Read `docs/rules/boundary-contracts.md` before changing gateway/control-plane payloads or outbox JSON.
- Pydantic DTOs in `apps/shared/src/dirt_shared/cloud_contract.py` are the schema mechanism for gateway/control-plane payloads.
- Do not edit human-owned invariant tests under `apps/tests/invariants/`.
- Use `uv run ...` for Python commands.


## Plan of Work

Milestone 1 extracts shared camera-source and snapshot-spool primitives. Add a module such as `apps/shared/src/dirt_shared/camera/` with:

- `CapturedFrame`: a Pydantic or dataclass value carrying JPEG bytes, content type, captured time, source frame age, width, height, and optional driver diagnostics.
- `CameraSource` Protocol with `async capture() -> CapturedFrame`.
- `ObsbotDaemonCameraSource`, which uses the existing daemon RPC from `dirt_shared.services.capture` or a moved equivalent to call `capture` and read the returned tempfile.
- `SnapshotSpool` or `SnapshotWriter`, which writes JPEG bytes under a configured directory with stable names such as `snapshot_YYYYMMDD_HHMMSS.jpg`, computes SHA256, and returns a local artifact object.

This milestone must not change `dirt-hwd` behavior yet. It adds tests with fake camera sources and temporary spool directories.

Milestone 2 refactors main-tent capture onto shared primitives. Update `apps/shared/src/dirt_shared/services/capture.py` so `CaptureService` composes the shared `CameraSource` and `SnapshotWriter` instead of embedding daemon capture, filename, and file-write logic. Preserve:

- `capture_snapshot()` return type and DB writes.
- default snapshot directory from `Settings.capture()`.
- default scope `homebox/main`.
- default device lookup `obsbot-main`.
- periodic loop behavior and test injection seams.

Update `apps/shared/tests/test_capture.py` and any `apps/hwd` tests needed to prove behavior stays the same.

Milestone 3 extracts shared cloud asset upload code. Move reusable sign/upload/complete/failure behavior out of `apps/gateway/src/dirt_gateway/sync.py` and `apps/gateway/src/dirt_gateway/cloud.py` into an importable module that both gateway and camera-agent can use, while keeping gateway orchestration in `apps/gateway`. A likely shape is:

- `apps/shared/src/dirt_shared/cloud_assets.py`: Pydantic DTO helpers and an `AssetUploader` that takes an HTTP client adapter, request DTOs, file path, and idempotency key.
- `apps/gateway/src/dirt_gateway/cloud.py`: keeps gateway-specific authenticated HTTP client implementation, or a shared `CloudAssetClient` moves to `dirt_shared` if dependency direction stays clean.
- `apps/gateway/src/dirt_gateway/sync.py`: calls the shared uploader for asset events.

This milestone must preserve gateway outbox semantics and existing tests. If moving the HTTP client to shared would create dependency or configuration churn, keep only the upload workflow shared and inject the existing gateway client.

Milestone 4 adds a camera-agent service. Create a new uv workspace app under `apps/camera-agent/` with an entry point such as `python -m dirt_camera_agent.main`. The service:

- loads settings from environment and `.env`;
- configures `CameraSource` from `DIRT_CAMERA_AGENT_SOURCE=obsbot-daemon`;
- configures scoped metadata: `DIRT_SITE_ID`, `DIRT_TENT_ID`, `DIRT_CAMERA_DEVICE_ID`, optional `DIRT_CAMERA_VIEW_ID`, `DIRT_CAMERA_KIND`;
- captures periodically using `DIRT_CAMERA_CAPTURE_INTERVAL_S`;
- writes a local spool under `DIRT_DATA_DIR/camera-agent/<tent_id>/snapshots` or configured `DIRT_CAMERA_SPOOL_DIR`;
- uploads through the shared asset uploader using the existing cloud gateway asset routes;
- reports upload failures through the existing asset failure route;
- logs structured events through the existing observability helper.

The camera-agent is not allowed to collect metrics, send site heartbeat, claim commands, mutate local Postgres, or control environmental actuators. It can optionally support PTZ presets later through the same camera-source interface, but V1 should focus on periodic captures and asset upload.

Milestone 5 deploys and smoke tests `dirt2`. Install the repo or a deployment checkout on `dirt2`, build `services/camera-daemon/`, install a user-level `dirt-camera.service`, and add a `dirt-camera-agent.service`. Configure a dedicated cloud credential for `dirt2` such as `gateway-dirt2-camera`, scoped to `homebox`, and store only the plaintext token in ignored environment files on `dirt2`. Verify:

- `systemctl --user status dirt-camera`
- `scripts/camera capture --json` or direct daemon capture equivalent
- `systemctl --user status dirt-camera-agent`
- camera-agent logs show capture and upload attempts
- a local spool JPEG exists

Do not print private keys, gateway tokens, or full environment files.

Milestone 6 enables real breeding-tent uploads and hosted verification. Turn on non-dry-run upload for `homebox/breeding`, wait for an upload, then verify the cloud API returns a recent breeding-tent asset:

- authenticated browser API route `/api/tents/breeding/assets/latest`;
- signed URL route `/api/assets/{asset_id}/signed-url`;
- hosted UI if it already surfaces assets for the selected tent.

If main-box snapshots for multiple tents should ever flow through `dirt-gateway`, change `GatewayLocalServiceBundle.latest_snapshot_asset()` into a per-tent or pending-asset projection instead of returning the first default-tent snapshot. That fix is not required for direct `dirt2` camera-agent upload, but it is part of keeping the architecture coherent.


## Concrete Steps

Work from the repo root unless a step says otherwise:

    cd /home/akcom/code/dirt

Before changing boundary payloads:

    sed -n '1,240p' docs/rules/boundary-contracts.md

Milestone 1 validation:

    uv run pytest apps/shared/tests -q
    uv run ruff check apps/shared/src apps/shared/tests
    uv run ruff format apps/shared/src apps/shared/tests --check

Milestone 2 validation:

    uv run pytest apps/shared/tests/test_capture.py apps/hwd/tests -q
    uv run pytest apps/tests/invariants/ -q

Milestone 3 validation:

    uv run pytest apps/gateway/tests/test_cloud_client.py apps/gateway/tests/test_sync.py -q
    uv run pytest apps/gateway/tests -q

Milestone 4 validation:

    uv run pytest apps/camera-agent/tests -q
    uv run ruff check apps/camera-agent apps/shared/src
    uv run ruff format apps/camera-agent apps/shared/src --check

Milestones 5 and 6 hardware validation commands:

    ssh dirt2 'systemctl --user status dirt-camera --no-pager'
    ssh dirt2 'systemctl --user status dirt-camera-agent --no-pager'
    ssh dirt2 'journalctl --user -u dirt-camera-agent -n 100 --no-pager'

Use the hosted API with authenticated browser credentials or an existing browser session for asset verification. Do not paste tokens into command output.

Before committing implementation work:

    scripts/agent-fix
    git status --short


## Validation and Acceptance

Acceptance requires all of these signals:

- Main-tent capture remains green: focused capture tests pass and `dirt-hwd` still records `snapshot` rows for `homebox/main`.
- Gateway asset tests pass after extracting shared uploader code.
- Camera-agent unit tests prove retryable upload failure handling, local spool creation, idempotency key construction, and correct `AssetSignUploadRequest` / `AssetCompleteRequest` payloads for `homebox/breeding`.
- On `dirt2`, `dirt-camera.service` is active and capture returns a JPEG path with nonzero bytes.
- On `dirt2`, `dirt-camera-agent.service` is active and logs successful captures plus successful cloud upload completion.
- The hosted cloud API returns at least one recent asset where `site_id=homebox`, `tent_id=breeding`, and `device_id` is the configured breeding camera device.


## Idempotence and Recovery

Shared-code refactors should be repeatable and covered by tests. The camera-agent upload path should use deterministic idempotency keys based on site, tent, device, captured timestamp or file hash, and object key so retrying a failed upload does not create duplicate logical assets.

Local spool writes should be atomic: write to a temporary path and rename into place. A crash during capture may leave `.tmp` files; the service can safely sweep old temporary files on startup.

Systemd service installation on `dirt2` is safe to repeat with `scripts/install-systemd` or explicit copy plus `systemctl --user daemon-reload`. Restarting `dirt-camera-agent` should not delete the local spool or invalidate uploaded assets.

If camera-agent uploads fail, leave the local spool file in place and report an asset failure when the failure occurs after sign-upload. If auth fails, stop or back off rather than hammering the hosted API.

If `dirt2` camera setup fails, the main grow box remains unaffected because `dirt2` is not running the full gateway and does not own actuator loops.


## Artifacts and Notes

Verified `dirt2` SSH after known-host alias was added:

    host=dirt2
    user=akcom
    kernel=Linux 6.12.85+deb13-amd64

Verified `dirt2` camera hardware:

    Bus 001 Device 003: ID 3564:fef9 Remo Tech Co., Ltd. OBSBOT Tiny 2 Lite
    OBSBOT Tiny 2 Lite: OBSBOT Tiny (usb-0000:05:00.3-1):
        /dev/video0
        /dev/video1
        /dev/media0

Wiki lint after the dirt2 hardware note had no failures, only existing file-length warnings:

    6/7 checks passed, 1 warning check(s) - 3 warning(s), no failures


## Interfaces and Dependencies

Expected new or changed interfaces:

- `dirt_shared.camera.CameraSource`: async frame capture Protocol.
- `dirt_shared.camera.ObsbotDaemonCameraSource`: talks to the existing `dirt-camera-daemon` Unix socket.
- `dirt_shared.camera.CapturedFrame`: captured JPEG bytes plus metadata.
- `dirt_shared.camera.SnapshotWriter` or equivalent: writes local spool artifacts and computes SHA256.
- Shared cloud asset uploader that uses `dirt_shared.cloud_contract.AssetSignUploadRequest`, `SignUploadResponse`, `AssetCompleteRequest`, `AssetCompleteResponse`, `AssetFailureRequest`, and `AssetFailureResponse`.
- `apps/camera-agent/`: new uv workspace package for camera edge nodes.
- `systemd/dirt-camera-agent.service`: user service for edge camera capture/upload.
- Environment variables:
  - `DIRT_CAMERA_AGENT_SOURCE`
  - `DIRT_CAMERA_CAPTURE_INTERVAL_S`
  - `DIRT_CAMERA_SPOOL_DIR`
  - `DIRT_SITE_ID`
  - `DIRT_TENT_ID`
  - `DIRT_CAMERA_DEVICE_ID`
  - `DIRT_CAMERA_VIEW_ID`
  - `DIRT_CAMERA_KIND`
  - `DIRT_CLOUD_API_BASE_URL`
  - `DIRT_CLOUD_GATEWAY_TOKEN`
  - `DIRT_CLOUD_GATEWAY_ID`

External dependencies should stay minimal. The OBSBOT path should continue to rely on the existing C++ daemon and vendored SDK. Direct V4L2 or RTSP support should be added only when there is a real camera requiring it.


## Revision Notes

- 2026-05-10: Initial ExecPlan created after confirming `dirt2` SSH, OBSBOT hardware detection, and the desired reusable camera-edge architecture.
