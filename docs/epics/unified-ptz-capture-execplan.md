# Unify PTZ Capture Across Mainbox and Dirt2

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

Mainbox and `dirt2` both take periodic PTZ camera snapshots, but today they use different orchestration paths. Mainbox runs `CaptureService` inside `dirt-hwd`, writes a JPEG under `var/snapshots`, records a local `snapshot` database row, and relies on `dirt-gateway` to upload the latest local snapshot. `dirt2` runs `dirt-camera-agent`, writes a JPEG into a camera-agent spool directory, and uploads that asset directly to the hosted control plane.

After this change, both boxes use one shared periodic PTZ capture architecture. The shared architecture captures a frame from `ObsbotDaemonCameraSource`, writes a `SnapshotArtifact`, then hands the artifact to one or more sinks. Mainbox keeps its local DB/feed behavior through a local snapshot sink; `dirt2` keeps its direct cloud upload behavior through a cloud asset sink. Once capture orchestration is unified, a shared lights-aware capture gate prevents both boxes from taking scheduled periodic pictures while the relevant tent lights are off, so black night images stop being created rather than merely skipped during upload.

The user can observe the result through tests and logs: both mainbox and `dirt2` capture paths call the same shared service, and lights-off cycles produce a structured skipped-capture log without creating or uploading a JPEG.

## Progress

- [x] (2026-05-12 04:15Z) Inspected current capture split: mainbox `CaptureService.capture_snapshot()` persists local DB rows; `dirt2` `CameraAgentService.run_once()` uploads direct cloud assets; both already share `dirt_shared.camera` low-level source/spool primitives.
- [x] (2026-05-12 04:25Z) Milestone 1: Introduced `dirt_shared.services.camera_publisher` and ported `dirt-camera-agent` to delegate to it while preserving existing camera-agent public helpers/results.
- [x] (2026-05-12 04:34Z) Milestone 2: Ported mainbox `CaptureService` to delegate to the shared publisher with `LocalSnapshotSink`, preserving local feed/gateway behavior.
- [x] (2026-05-12 04:45Z) Milestone 3: Added shared capture gates, wired mainbox to the DB grow-lights schedule, and added optional `dirt2` static light-schedule settings.
- [x] (2026-05-12 04:52Z) Milestone 4: Updated docs/env examples, ran focused validation, and confirmed lint passes.

## Surprises & Discoveries

- Observation: The previous refactor unified low-level camera primitives but not capture orchestration.
  Evidence: `apps/shared/src/dirt_shared/camera/source.py` provides `ObsbotDaemonCameraSource`; `apps/shared/src/dirt_shared/camera/spool.py` provides `SnapshotWriter` / `SnapshotSpool`. Mainbox still orchestrates via `apps/shared/src/dirt_shared/services/capture.py`, while `dirt2` orchestrates via `apps/camera-agent/src/dirt_camera_agent/service.py`.
- Observation: Mainbox local UI and gateway still consume local `snapshot` DB rows.
  Evidence: `apps/web/src/dirt_web/api/feed.py` serves `/api/feed/snapshot/latest` from `SnapshotsService`; `apps/gateway/src/dirt_gateway/local.py:latest_snapshot_asset` uploads the latest local `Snapshot`.

## Decision Log

- Decision: Unify the capture orchestration in shared code, but keep separate sink behavior for mainbox and `dirt2`.
  Rationale: The user asked for unified PTZ capture, not necessarily identical asset delivery. Preserving mainbox local snapshot DB rows avoids breaking local feed and existing gateway behavior while still removing the parallel capture loop.
  Date/Author: 2026-05-12 / Codex
- Decision: Add the lights-off prevention as a shared capture gate after both boxes use the same publisher.
  Rationale: This keeps the policy in one place and prevents black images from being created at all. Adding it before unification would duplicate logic across `CaptureService` and `CameraAgentService`.
  Date/Author: 2026-05-12 / Codex
- Decision: Do not make the gateway/cloud asset protocol the center of this refactor.
  Rationale: The current protocol is already typed and working. This task is about capture orchestration and scheduling. Protocol churn would increase blast radius without helping stop black photos.
  Date/Author: 2026-05-12 / Codex

## Outcomes & Retrospective

Milestone 1 complete. `dirt-camera-agent` now constructs a shared `CameraCapturePublisher` with a `CloudAssetSink`. The old camera-agent service class remains as a thin adapter so current callers and tests continue to work.

Milestone 2 complete. `CaptureService.capture_snapshot()` now delegates to `CameraCapturePublisher` and receives its DB `Snapshot` from `LocalSnapshotSink`. Focused validation passed: `uv run pytest apps/shared/tests/test_capture.py apps/web/tests/test_feed_snapshot_endpoint.py apps/gateway/tests/test_sync.py -q` reported 25 passed.

Milestone 3 complete. `CameraCapturePublisher` now evaluates an optional `CaptureGate` before calling the camera source. `GrowLightsCaptureGate` uses `GrowStateService` for mainbox, and `StaticLightScheduleCaptureGate` supports camera-only hosts such as `dirt2`. Focused validation passed: `uv run pytest apps/shared/tests/test_camera_publisher.py apps/camera-agent/tests/test_camera_agent.py apps/shared/tests/test_capture.py -q` reported 13 passed.

Milestone 4 complete. Documentation now describes the shared publisher and `capture_skipped` events. `.env.example` includes the camera-agent light-window variables. Final focused validation passed: `uv run pytest apps/shared/tests/test_camera.py apps/shared/tests/test_camera_publisher.py apps/shared/tests/test_capture.py apps/camera-agent/tests/test_camera_agent.py apps/web/tests/test_feed_snapshot_endpoint.py apps/gateway/tests/test_sync.py -q` reported 40 passed. `uv run ruff check` passed.

## Context and Orientation

`dirt-camera` is the OBSBOT PTZ daemon. It exposes a Unix socket used by `ObsbotDaemonCameraSource` in `apps/shared/src/dirt_shared/camera/source.py`. A camera source returns a `CapturedFrame`.

`SnapshotWriter` and `SnapshotSpool` in `apps/shared/src/dirt_shared/camera/spool.py` atomically write a `CapturedFrame` as a JPEG and return a `SnapshotArtifact` with path, filename, SHA-256, size, content type, and capture timestamp.

Mainbox currently starts `CaptureService` in `apps/hwd/src/dirt_hwd/app.py`. `CaptureService` lives in `apps/shared/src/dirt_shared/services/capture.py`. Its `run()` loop calls `capture_snapshot()`, which captures one frame, writes it under `settings.snapshot_dir`, and inserts a scoped local `Snapshot` row for `homebox/main` and device `obsbot-main`.

`dirt2` currently starts `dirt-camera-agent` from `apps/camera-agent/src/dirt_camera_agent/main.py`. Its service implementation in `apps/camera-agent/src/dirt_camera_agent/service.py` calls `run_once()`, which captures one frame, writes it to a spool directory, builds typed cloud asset sign/complete payloads, uploads bytes, and logs `camera_agent` events.

The local feed endpoint `/api/feed/snapshot/latest` reads local DB snapshots through `SnapshotsService`. The local gateway also reads local DB snapshots and uploads the latest one to the hosted control plane. The new architecture must not accidentally remove those mainbox local rows unless explicitly planned.

The grow/lights schedule source of truth for mainbox is `GrowStateService.lights_state()` in `apps/shared/src/dirt_shared/services/grow_state.py`, which reads the current scoped `schedule` row with `kind='lights'` and falls back to 05:00-23:00 in the grow timezone.

`dirt2` does not have local Postgres ownership. Its initial lights gate should use host-local settings in `.env.dirt2-camera-agent` so it can decide locally whether to capture. The shared pure helper `derive_lights_from_times()` can evaluate that configured window.

## Plan of Work

Milestone 1 creates shared capture publisher primitives in `apps/shared/src/dirt_shared/services/camera_publisher.py`. The module should include:

- `CameraCaptureMetadata`: site ID, tent ID, camera device ID, optional view ID, asset kind, event stream.
- `CameraCaptureSink` protocol: receives one `SnapshotArtifact` plus metadata.
- `CameraCapturePublisher`: runs one capture cycle and the periodic loop. It logs start, success, sink failures, cycle failures, and later skipped captures.
- `CloudAssetSink`: builds the same `AssetUploadRequest` currently built in `apps/camera-agent/src/dirt_camera_agent/service.py` and calls `AssetUploader`.

`apps/camera-agent/src/dirt_camera_agent/service.py` should become a thin compatibility layer or be deleted in favor of constructing `CameraCapturePublisher` directly from `apps/camera-agent/src/dirt_camera_agent/main.py`. Existing camera-agent tests should move toward the shared publisher tests, with only composition-root tests remaining in the camera-agent app.

Milestone 2 ports mainbox to the shared publisher. Add a `LocalSnapshotSink` in shared code that inserts the same scoped `Snapshot` row currently inserted by `CaptureService.capture_snapshot()`. Change `apps/hwd/src/dirt_hwd/app.py` to construct the shared publisher with:

- `ObsbotDaemonCameraSource` using `settings.capture().camera_socket_path`
- `SnapshotWriter(settings.snapshot_dir)`
- `LocalSnapshotSink(engine, site_id="homebox", tent_id="main", camera_device_id="obsbot-main")`
- capture interval from `settings.capture().capture_interval`

`CaptureService` should either be removed or reduced to a compatibility shim only if tests still require it during the migration. The final state should not have a separate mainbox capture loop.

Milestone 3 adds capture gating. Add a `CaptureGate` protocol to the shared publisher. Before calling `source.capture()`, the publisher asks the gate whether capture is currently allowed. If not allowed, it logs `capture_skipped` with `reason="lights_off"` and does not write a JPEG or invoke sinks.

Add two gate implementations:

- `GrowLightsCaptureGate`: uses `GrowStateService.lights_state(site_id, tent_id)` for mainbox.
- `StaticLightScheduleCaptureGate`: uses configured local start/end times and timezone for `dirt2`, calling `derive_lights_from_times()`.

Add `DIRT_CAMERA_CAPTURE_REQUIRE_LIGHTS_ON`, `DIRT_CAMERA_LIGHTS_ON_LOCAL`, `DIRT_CAMERA_LIGHTS_OFF_LOCAL`, and `DIRT_CAMERA_LIGHTS_TIMEZONE` to `CameraAgentSettings` for `dirt2`. Keep default behavior conservative: if the setting is disabled or incomplete, capture proceeds and logs no skip. Mainbox should enable the gate by default because the DB schedule is local and authoritative.

Milestone 4 updates docs and removes stale code. `docs/commands.md` should say both mainbox and camera-only hosts use the shared capture publisher, with mainbox sink behavior in `dirt-hwd` and `dirt2` direct cloud upload in `dirt-camera-agent`. `docs/observability.md` should document `capture_skipped` events for `camera_agent` and whichever stream mainbox uses. Tests that still assert the old `CaptureService` shape should be updated to assert the shared publisher and local sink instead.

## Concrete Steps

Start in the repo root:

    cd /home/akcom/code/dirt

Milestone 1:

    uv run pytest apps/camera-agent/tests/test_camera_agent.py apps/shared/tests/test_camera.py -q

Expected result: camera-agent behavior still uploads an asset with stable object key and idempotency key, now through shared publisher code.

Milestone 2:

    uv run pytest apps/shared/tests/test_capture.py apps/web/tests/test_feed_snapshot_endpoint.py apps/gateway/tests/test_sync.py -q

Expected result: a mainbox capture still writes a local JPEG, inserts a scoped `Snapshot`, serves through `/api/feed/snapshot/latest`, and remains visible to the gateway projection.

Milestone 3:

    uv run pytest apps/shared/tests/test_camera_publisher.py apps/camera-agent/tests/test_camera_agent.py apps/shared/tests/test_capture.py -q

Expected result: lights-off tests prove no source capture is called, no JPEG is written, no sink runs, and a skip event is logged. Lights-on tests prove normal capture still works.

Final validation:

    uv run pytest apps/shared/tests/test_camera.py apps/shared/tests/test_capture.py apps/camera-agent/tests/test_camera_agent.py apps/web/tests/test_feed_snapshot_endpoint.py apps/gateway/tests/test_sync.py -q
    uv run ruff check

Expected result: focused tests and lint pass.

## Validation and Acceptance

The change is accepted when:

- Mainbox periodic capture and `dirt2` camera-agent capture both use `CameraCapturePublisher` or the same named shared capture orchestration class.
- Mainbox still writes scoped local `Snapshot` rows for `homebox/main` unless a later explicit decision changes that behavior.
- `dirt2` still uploads hosted assets using the same object key shape: `homebox/breeding/snapshots/<filename>.jpg`.
- When lights are off, the shared publisher does not call the camera source, does not write a JPEG, does not write a DB row, and does not upload to cloud.
- When lights are on, both mainbox and `dirt2` capture paths behave as before.
- Structured logs show why a capture was skipped, without logging secrets or signed URLs.

## Idempotence and Recovery

Code edits and tests are safe to repeat. The refactor should not require database migrations.

If the mainbox port breaks local snapshot feed tests, revert only the mainbox wiring change and keep the shared publisher plus `dirt2` port intact while fixing `LocalSnapshotSink`.

If the lights gate causes unexpected skips, disable the `dirt2` gate by leaving `DIRT_CAMERA_CAPTURE_REQUIRE_LIGHTS_ON` unset or false. For mainbox, remove the gate from wiring temporarily; do not change schedules to work around a code bug.

Do not delete user-created files under `var/`. Do not modify `apps/tests/invariants/`; failures there must be fixed in source code.

## Artifacts and Notes

Initial inspection commands:

    sed -n '1,180p' apps/shared/src/dirt_shared/services/capture.py
    sed -n '1,180p' apps/camera-agent/src/dirt_camera_agent/service.py
    sed -n '1,260p' apps/shared/src/dirt_shared/camera/source.py
    sed -n '1,240p' apps/shared/src/dirt_shared/camera/spool.py

Key evidence from inspection:

- Mainbox `CaptureService.capture_snapshot()` captures, writes a JPEG, and inserts a local `Snapshot`.
- `dirt2` `CameraAgentService.run_once()` captures, writes a spool artifact, and uploads to cloud.
- Both already share `ObsbotDaemonCameraSource` and `SnapshotWriter`/`SnapshotSpool`.

Validation evidence:

    uv run pytest apps/shared/tests/test_camera.py apps/shared/tests/test_camera_publisher.py apps/shared/tests/test_capture.py apps/camera-agent/tests/test_camera_agent.py apps/web/tests/test_feed_snapshot_endpoint.py apps/gateway/tests/test_sync.py -q
    40 passed in 22.06s

    uv run ruff check
    All checks passed!

## Interfaces and Dependencies

New or final interfaces:

- `dirt_shared.services.camera_publisher.CameraCapturePublisher`
- `dirt_shared.services.camera_publisher.CameraCaptureSink`
- `dirt_shared.services.camera_publisher.CloudAssetSink`
- `dirt_shared.services.camera_publisher.LocalSnapshotSink`
- `dirt_shared.services.camera_publisher.CaptureGate`
- `dirt_shared.services.camera_publisher.GrowLightsCaptureGate`
- `dirt_shared.services.camera_publisher.StaticLightScheduleCaptureGate`

Existing interfaces to preserve:

- `dirt_shared.camera.ObsbotDaemonCameraSource`
- `dirt_shared.camera.SnapshotWriter` and `SnapshotSpool`
- `dirt-camera-agent` CLI: `uv run --package dirt-camera-agent python -m dirt_camera_agent.main --once`
- Mainbox local feed endpoint: `/api/feed/snapshot/latest`
- Hosted object key shape for cloud assets.

Environment variables to add for camera-only hosts:

- `DIRT_CAMERA_CAPTURE_REQUIRE_LIGHTS_ON`
- `DIRT_CAMERA_LIGHTS_ON_LOCAL`
- `DIRT_CAMERA_LIGHTS_OFF_LOCAL`
- `DIRT_CAMERA_LIGHTS_TIMEZONE`

## Revision Notes

- 2026-05-12: Initial ExecPlan created from user request to unify mainbox and `dirt2` PTZ capture first, then add lights-on/lights-off capture suppression.
