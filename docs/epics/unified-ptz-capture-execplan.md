# Unify PTZ Capture Across Mainbox and Dirt2

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

Mainbox and `dirt2` both take periodic PTZ camera snapshots, but today they use different orchestration paths. Mainbox runs `CaptureService` inside `dirt-hwd`, writes a JPEG under `var/snapshots`, records a local `snapshot` database row, and relies on `dirt-gateway` to upload the latest local snapshot. `dirt2` runs `dirt-camera-agent`, writes a JPEG into a camera-agent spool directory, and uploads that asset directly to the hosted control plane.

After this change, both boxes use one shared periodic PTZ capture architecture. The shared architecture captures a frame from `ObsbotDaemonCameraSource`, writes a `SnapshotArtifact`, then hands the artifact to one or more sinks. Mainbox keeps its local DB/feed behavior through a local snapshot sink; `dirt2` keeps its direct cloud upload behavior through a cloud asset sink. Once capture orchestration is unified, a shared lights-aware capture gate prevents both boxes from taking scheduled periodic pictures while the relevant tent lights are off, so black night images stop being created rather than merely skipped during upload.

The lights-aware gate must not hard-code a light window in camera-agent environment variables. It derives the relevant light schedule from the existing catalog model: an enabled camera `device` is scoped to a site/tent, and enabled `schedule` rows with `kind='lights'` are scoped to the same site/tent. Mainbox can resolve this from the local database. `dirt2`, which does not own local Postgres, should fetch the same scoped policy from the hosted control plane or a narrow hosted catalog/policy endpoint backed by the synced cloud catalog.

The user can observe the result through tests and logs: both mainbox and `dirt2` capture paths call the same shared service, and lights-off cycles produce a structured skipped-capture log without creating or uploading a JPEG.

## Progress

- [x] (2026-05-12 04:15Z) Inspected current capture split: mainbox `CaptureService.capture_snapshot()` persists local DB rows; `dirt2` `CameraAgentService.run_once()` uploads direct cloud assets; both already share `dirt_shared.camera` low-level source/spool primitives.
- [x] (2026-05-12 04:25Z) Milestone 1: Introduced `dirt_shared.services.camera_publisher` and ported `dirt-camera-agent` to delegate to it while preserving existing camera-agent public helpers/results.
- [x] (2026-05-12 04:34Z) Milestone 2: Ported mainbox `CaptureService` to delegate to the shared publisher with `LocalSnapshotSink`, preserving local feed/gateway behavior.
- [x] (2026-05-12 04:45Z) Milestone 3 prototype: Added shared capture gates, wired mainbox to the DB grow-lights schedule, and added optional `dirt2` static light-schedule settings.
- [x] (2026-05-12 04:52Z) Prototype validation: Updated docs/env examples for the initial static schedule approach, ran focused validation, and confirmed lint passes.
- [x] (2026-05-12) Re-checked the existing data model and decided the final `dirt2` gate should derive from existing device/schedule scoping instead of static environment schedule variables or a new camera-to-schedule model.
- [x] (2026-05-12 15:48Z) Replaced the static `dirt2` gate prototype with a catalog-derived hosted capture policy endpoint/cache.
- [x] (2026-05-12 15:57Z) Added an idempotent Atlas data migration that seeds `obsbot-breeding` as a `kind='camera'` device scoped to `homebox/breeding`.

## Surprises & Discoveries

- Observation: The previous refactor unified low-level camera primitives but not capture orchestration.
  Evidence: `apps/shared/src/dirt_shared/camera/source.py` provides `ObsbotDaemonCameraSource`; `apps/shared/src/dirt_shared/camera/spool.py` provides `SnapshotWriter` / `SnapshotSpool`. Mainbox still orchestrates via `apps/shared/src/dirt_shared/services/capture.py`, while `dirt2` orchestrates via `apps/camera-agent/src/dirt_camera_agent/service.py`.
- Observation: Mainbox local UI and gateway still consume local `snapshot` DB rows.
  Evidence: `apps/web/src/dirt_web/api/feed.py` serves `/api/feed/snapshot/latest` from `SnapshotsService`; `apps/gateway/src/dirt_gateway/local.py:latest_snapshot_asset` uploads the latest local `Snapshot`.
- Observation: The current local and cloud catalog model already carries the relationships needed to derive a camera's light schedule.
  Evidence: `device` rows have `site_id`, `tent_id`, `zone_id`, `kind`, and `enabled`; `schedule` rows have `site_id`, `tent_id`, optional `device_id`, optional `capability_id`, `kind`, local start/end times, timezone, and enabled state. `CatalogDevice` and `CatalogSchedule` expose the same fields to cloud sync.
- Observation: The live local database currently has `obsbot-main` scoped to `homebox/main`, plus enabled lights schedules for `main`, `breeding`, and `clones`, but no breeding camera device row yet.
  Evidence: A live query on 2026-05-12 returned `homebox/main/canopy/obsbot-main` as the only `kind='camera'` device, and returned `breeding-lights-photoperiod` for `homebox/breeding`.
- Observation: `zone_id` should not be used as the required join for the first implementation.
  Evidence: Cameras are naturally in a view zone such as `canopy`, while light devices and schedules are in a `lights` zone. Matching by site/tent is the correct current linkage.

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
- Decision: Do not add a new camera-to-light-schedule data model for this change.
  Rationale: The existing scoped catalog is sufficient: camera devices and light schedules both belong to a site/tent. A new explicit foreign key or join table would add model surface without solving a real current ambiguity.
  Date/Author: 2026-05-12 / Codex
- Decision: Do not hard-code `dirt2` light windows in environment variables as the final architecture.
  Rationale: Environment should identify the camera, site/tent, socket, and cloud credentials. Grow behavior belongs in the database/catalog so schedule changes automatically affect capture behavior on both boxes.
  Date/Author: 2026-05-12 / Codex
- Decision: Resolve capture policy by camera device scope, then the same site's enabled tent-level lights schedule.
  Rationale: The live model has cameras in view zones and light devices in lights zones, so tent-level matching is the right first-order relationship. Zone matching can be added later only if multiple independent light cycles exist in one tent.
  Date/Author: 2026-05-12 / Codex

## Outcomes & Retrospective

Milestone 1 complete. `dirt-camera-agent` now constructs a shared `CameraCapturePublisher` with a `CloudAssetSink`. The old camera-agent service class remains as a thin adapter so current callers and tests continue to work.

Milestone 2 complete. `CaptureService.capture_snapshot()` now delegates to `CameraCapturePublisher` and receives its DB `Snapshot` from `LocalSnapshotSink`. Focused validation passed: `uv run pytest apps/shared/tests/test_capture.py apps/web/tests/test_feed_snapshot_endpoint.py apps/gateway/tests/test_sync.py -q` reported 25 passed.

Milestone 3 prototype complete, but superseded for the final `dirt2` design. `CameraCapturePublisher` now evaluates an optional `CaptureGate` before calling the camera source. The initial local prototype used `GrowLightsCaptureGate` for mainbox and `StaticLightScheduleCaptureGate` for camera-only hosts. The final implementation should replace the static camera-agent schedule settings with a catalog-derived capture policy.

Prototype docs and validation completed before the catalog-policy revision. Documentation described the shared publisher and `capture_skipped` events, and `.env.example` temporarily included camera-agent light-window variables. Focused validation passed for the prototype: `uv run pytest apps/shared/tests/test_camera.py apps/shared/tests/test_camera_publisher.py apps/shared/tests/test_capture.py apps/camera-agent/tests/test_camera_agent.py apps/web/tests/test_feed_snapshot_endpoint.py apps/gateway/tests/test_sync.py -q` reported 40 passed. `uv run ruff check` passed.

Milestone 3b complete. The hosted control plane now exposes `GET /api/gateway/v1/cameras/{camera_device_id}/capture-policy` with a typed `CapturePolicyResponse`. Policy resolution matches a synced `CloudDevice(kind='camera')` to an enabled `CloudSchedule(kind='lights')` by the same site/tent, ignoring zone. `dirt-camera-agent` always uses `HostedCapturePolicyGate`, caches the last successful policy, fails open when policy fetches or catalog rows are missing, and no longer reads static camera light-window environment variables. Mainbox capture now uses the shared database camera/light-schedule resolver.

Milestone 3b validation passed: `uv run pytest apps/control-plane/tests/test_api.py apps/camera-agent/tests/test_camera_agent.py apps/shared/tests/test_camera_publisher.py -q` reported 33 passed, and `uv run ruff check` reported all checks passed. Simplify fallback pass removed a duplicate camera-agent HTTP client pool by sharing one `httpx.AsyncClient` between asset upload and policy fetch clients.

Breeding camera seed complete. Migration `migrations/20260512161000_seed_breeding_camera.sql` registers `obsbot-breeding` under `homebox/breeding/canopy` with `kind='camera'`, `controller='dirt-camera'`, and camera action capabilities. `atlas migrate hash --env local` regenerated `migrations/atlas.sum`. The gateway catalog sync test now asserts the seeded breeding camera is projected into the catalog. No live database apply was run as part of implementation.

Final focused validation passed: `uv run pytest apps/shared/tests/test_camera.py apps/shared/tests/test_camera_publisher.py apps/shared/tests/test_capture.py apps/camera-agent/tests/test_camera_agent.py apps/control-plane/tests/test_api.py apps/web/tests/test_feed_snapshot_endpoint.py apps/gateway/tests/test_sync.py -q` reported 63 passed, and `uv run ruff check` reported all checks passed.

## Context and Orientation

`dirt-camera` is the OBSBOT PTZ daemon. It exposes a Unix socket used by `ObsbotDaemonCameraSource` in `apps/shared/src/dirt_shared/camera/source.py`. A camera source returns a `CapturedFrame`.

`SnapshotWriter` and `SnapshotSpool` in `apps/shared/src/dirt_shared/camera/spool.py` atomically write a `CapturedFrame` as a JPEG and return a `SnapshotArtifact` with path, filename, SHA-256, size, content type, and capture timestamp.

Mainbox currently starts `CaptureService` in `apps/hwd/src/dirt_hwd/app.py`. `CaptureService` lives in `apps/shared/src/dirt_shared/services/capture.py`. Its `run()` loop calls `capture_snapshot()`, which captures one frame, writes it under `settings.snapshot_dir`, and inserts a scoped local `Snapshot` row for `homebox/main` and device `obsbot-main`.

`dirt2` currently starts `dirt-camera-agent` from `apps/camera-agent/src/dirt_camera_agent/main.py`. Its service implementation in `apps/camera-agent/src/dirt_camera_agent/service.py` calls `run_once()`, which captures one frame, writes it to a spool directory, builds typed cloud asset sign/complete payloads, uploads bytes, and logs `camera_agent` events.

The local feed endpoint `/api/feed/snapshot/latest` reads local DB snapshots through `SnapshotsService`. The local gateway also reads local DB snapshots and uploads the latest one to the hosted control plane. The new architecture must not accidentally remove those mainbox local rows unless explicitly planned.

The grow/lights schedule source of truth for mainbox is the scoped `schedule` table. `GrowStateService.lights_state()` in `apps/shared/src/dirt_shared/services/grow_state.py` already reads the current scoped `schedule` row with `kind='lights'` and falls back to 05:00-23:00 in the grow timezone for older/default behavior.

`dirt2` does not have local Postgres ownership. It should not receive hard-coded light windows in `.env.dirt2-camera-agent` as the final design. Instead, it should use its configured `site_id` and `camera_device_id` to request a typed capture policy from the hosted control plane. That hosted policy can be derived from synced `CloudDevice` and `CloudSchedule` rows using the same site/tent rule as mainbox.

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

Add shared policy/resolver pieces:

- `CameraLightScheduleResolver`: given `site_id` and `camera_device_id`, find an enabled `Device` with `kind='camera'`, then find the enabled `Schedule` with `kind='lights'` for the same site/tent. Do not require `zone_id` equality.
- `DatabaseCameraLightScheduleGate`: uses the local resolver for mainbox and calls `derive_lights_from_times()` against the resolved schedule.
- `HostedCapturePolicyGate`: used by `dirt-camera-agent`; fetches a typed hosted policy derived from `CloudDevice` and `CloudSchedule`, caches the last successful policy, and calls the same local time-window helper.

Do not add `DIRT_CAMERA_LIGHTS_ON_LOCAL`, `DIRT_CAMERA_LIGHTS_OFF_LOCAL`, or `DIRT_CAMERA_LIGHTS_TIMEZONE` as the final source of truth. `CameraAgentSettings` should keep only identity/connectivity configuration needed to ask for policy, such as site ID, tent ID if needed for upload object keys, camera device ID, cloud API base URL, gateway ID, gateway token, socket path, and capture interval.

Add or reuse a typed hosted endpoint for camera-agent policy. The preferred shape is narrow and derived, not a raw database dump:

    GET /api/gateway/v1/cameras/{camera_device_id}/capture-policy

The response should include `site_id`, `tent_id`, `camera_device_id`, `enabled`, `require_lights_on`, `lights_on_local`, `lights_off_local`, `timezone`, and `source_schedule_id`. A missing camera row or missing schedule should produce a clear response/log and should fail open for capture unless an explicit disabled policy is returned.

Before relying on this for `dirt2`, seed or sync a breeding camera device row scoped to `homebox/breeding`; the current live local database does not have one.

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

Milestone 3b:

    uv run pytest apps/control-plane/tests/test_api.py apps/camera-agent/tests/test_camera_agent.py apps/shared/tests/test_camera_publisher.py -q

Expected result: hosted policy resolution derives `dirt2` capture policy from synced camera device and lights schedule rows; camera-agent uses the hosted policy/cache rather than environment light-window values.

Final validation:

    uv run pytest apps/shared/tests/test_camera.py apps/shared/tests/test_camera_publisher.py apps/shared/tests/test_capture.py apps/camera-agent/tests/test_camera_agent.py apps/control-plane/tests/test_api.py apps/web/tests/test_feed_snapshot_endpoint.py apps/gateway/tests/test_sync.py -q
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
- No new database model is introduced for camera-to-light-schedule association.
- `dirt2` does not require hard-coded light start/end/timezone environment variables for normal operation.
- The breeding camera is present as a `kind='camera'` catalog device scoped to `homebox/breeding`, so policy can be derived from existing catalog linkages.

## Idempotence and Recovery

Code edits and tests are safe to repeat. The refactor does not require schema migrations. It includes an idempotent Atlas data migration that inserts the breeding camera as an enabled `device` row scoped to `homebox/breeding`.

If the mainbox port breaks local snapshot feed tests, revert only the mainbox wiring change and keep the shared publisher plus `dirt2` port intact while fixing `LocalSnapshotSink`.

If the lights gate causes unexpected skips, camera-agent should use cached policy or temporarily fail open while logging the policy resolution problem. For mainbox, remove the gate from wiring temporarily; do not change schedules to work around a code bug.

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
- `dirt_shared.services.camera_publisher.DatabaseCameraLightScheduleGate`
- `dirt_shared.services.camera_publisher.HostedCapturePolicyGate`
- shared camera/light schedule resolver function or service

Existing interfaces to preserve:

- `dirt_shared.camera.ObsbotDaemonCameraSource`
- `dirt_shared.camera.SnapshotWriter` and `SnapshotSpool`
- `dirt-camera-agent` CLI: `uv run --package dirt-camera-agent python -m dirt_camera_agent.main --once`
- Mainbox local feed endpoint: `/api/feed/snapshot/latest`
- Hosted object key shape for cloud assets.

Environment variables for camera-only hosts should remain identity/connectivity only:

- `DIRT_SITE_ID`
- `DIRT_TENT_ID`
- `DIRT_CAMERA_DEVICE_ID`
- cloud API base URL / gateway credentials
- camera socket path and capture interval

## Revision Notes

- 2026-05-12: Initial ExecPlan created from user request to unify mainbox and `dirt2` PTZ capture first, then add lights-on/lights-off capture suppression.
- 2026-05-12: Revised lights-off plan after inspecting the current data model. The final design derives camera capture policy from existing device/schedule site-tent scoping instead of static environment light windows or a new camera-to-schedule model.
