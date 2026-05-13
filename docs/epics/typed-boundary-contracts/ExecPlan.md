# Typed Boundary Contracts

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt agents and services cannot silently omit required fields from gateway, cloud, command, API, or outbox payloads. Pydantic DTOs become the single schema enforcement mechanism at codebase boundaries. The immediate user-visible benefit is that the hosted Sirius Forge dashboard cannot regress into showing impossible states such as an ESP32 device with fresh metrics but `last seen never` because the sync payload omitted `last_seen_at`.

The observable result is not merely cleaner code. A developer can run focused tests that fail if required boundary fields are missing, can inspect FastAPI OpenAPI output that matches the same Pydantic DTOs used by producers, and can see gateway logs fail loudly on validation errors before bad payloads reach the cloud.


## Progress

- [x] (2026-05-08T04:40Z) Researched progressive-disclosure and schema-validation practices and created this ExecPlan.
- [x] (2026-05-08T04:40Z) Added `docs/rules/boundary-contracts.md` and linked it from the progressive-disclosure indexes.
- [x] (2026-05-09T04:39Z) Resolved pre-implementation policy questions: drain old outbox rows before cutover, keep deployment compatibility temporary, scope command DTOs to PTZ payloads, keep hosted browser DTOs local unless shared by wire contract, report consistency gaps through logs/audits, and start with narrow guardrail tests.
- [x] (2026-05-09T04:49Z) Milestone 1: Add shared Pydantic gateway contract models without changing runtime behavior.
- [x] (2026-05-09T05:53Z) Milestone 2: Drained/verified read-only outbox state, then converted read-only gateway projections and outbox enqueue paths to typed DTOs with no legacy replay adapter.
- [x] (2026-05-09T06:06Z) Milestone 3: Converted asset upload and retention payloads to typed DTOs, validated asset outbox replay before cloud calls, and removed the legacy raw asset request path.
- [x] (2026-05-13T02:17Z) Milestone 4: Converted cloud command claim/result payloads to typed DTOs with explicit PTZ payload models.
- [x] (2026-05-13T02:24Z) Milestone 5: Add local Pydantic response models to hosted browser API routes and align generated frontend types.
- [x] (2026-05-13T02:33Z) Milestone 6: Added narrow guardrail tests and data-consistency audit checks that prevent untyped boundary payloads from returning.


## Surprises & Discoveries

- Observation: The local `dirt-web` API already follows this pattern better than the hosted control-plane path.
  Evidence: Routes under `apps/web/src/dirt_web/api/` generally declare `response_model=...`, while hosted routes under `apps/control-plane/src/dirt_control/api/browser.py` mostly return `dict[str, Any]` or `list[dict[str, Any]]`.

- Observation: The highest-risk gap is the local gateway outbound protocol.
  Evidence: `apps/gateway/src/dirt_gateway/protocols.py` currently types all cloud payloads as `dict[str, Any]`; `local.py`, `sync.py`, `cloud.py`, and `commands.py` hand-build or consume nested dictionaries.

- Observation: The control-plane gateway API already has Pydantic request models, but they are local to `apps/control-plane` and are not shared with the producer.
  Evidence: `apps/control-plane/src/dirt_control/api/gateway.py` defines `CatalogRequest`, `LatestMetricsRequest`, `RollupsRequest`, and asset request models. The gateway producer cannot import them without depending on the control-plane package.

- Observation: Progressive-disclosure documentation should reveal this rule in layers, not bury it in an epic.
  Evidence: IBM's progressive-disclosure guidance emphasizes ordered disclosure and avoiding repeated information; Diataxis separates task-oriented how-to material from reference/explanation. In this repo that maps to `AGENTS.md` triggers, `docs/README.md` and `docs/rules/README.md` indexes, then a focused rule file.

- Observation: Pydantic JSON serialization emits UTC datetimes with a `Z` suffix, so the catalog regression test now compares against `model_dump(mode="json")` instead of the old hand-written `datetime.isoformat()` output.
  Evidence: The breeding device `last_seen_at` value serialized as `2026-05-05T12:00:00Z` after the Milestone 2 DTO cutover.

- Observation: Re-uploading a snapshot to the same cloud `object_key` with a new content digest exposed a hosted control-plane asset identity bug.
  Evidence: The live pending `asset_upload` row uses `object_key=homebox/main/snapshots/plant-a.jpg` with a new digest `asset_id`, while a delivered row already used the same object key. The control-plane `cloud_asset` table has a unique constraint on `(site_id, tent_id, object_key)`, but `/assets/complete` previously upserted only by `asset_id`, causing a duplicate-object-key failure.


## Decision Log

- Decision: Use Pydantic `BaseModel` DTOs as Dirt's single boundary schema mechanism.
  Rationale: Pydantic models validate data, serialize to JSON, and generate JSON Schema/OpenAPI. FastAPI already uses Pydantic for request/response models, so using it for gateway/outbox boundaries avoids a second schema language.
  Date/Author: 2026-05-08 / Codex

- Decision: Keep SQLModel row models separate from wire DTOs.
  Rationale: Storage shape and wire shape have different compatibility rules. Reusing DB rows as wire models makes schema evolution risky and can leak persistence-only fields. SQLAlchemy remains the lower-level substrate used through SQLModel column/query constructs, not a second app-level row-modeling style.
  Date/Author: 2026-05-08 / Codex

- Decision: Put shared gateway DTOs in `apps/shared/src/dirt_shared/cloud_contract.py`.
  Rationale: Both `dirt-gateway` and `dirt-control-plane` already depend on `dirt-shared`. A shared module avoids importing control-plane API modules from gateway code and keeps the producer and receiver on one contract.
  Date/Author: 2026-05-08 / Codex

- Decision: Required-but-nullable fields must be modeled as required keys whose value may be `None`.
  Rationale: `last_seen_at: datetime | None = None` lets omission look the same as an intentionally unknown value. `last_seen_at: datetime | None = Field(...)` distinguishes those cases and catches missing keys.
  Date/Author: 2026-05-08 / Codex

- Decision: Owned gateway/control-plane protocol models should use `ConfigDict(extra="forbid")` unless a payload intentionally carries opaque metadata.
  Rationale: Extra fields often mean stale producers, typos, or partial migrations. Failing loudly is preferable for owned protocols.
  Date/Author: 2026-05-08 / Codex

- Decision: Drain existing cloud outbox rows before switching an event type to typed replay, then make a clean cutover with no old-shape compatibility adapter.
  Rationale: The outbox is durable replay state, so validators should not be forced to preserve legacy shapes indefinitely. Draining first lets implementation delete unused raw-payload code instead of carrying compatibility branches.
  Date/Author: 2026-05-09 / User + Codex

- Decision: Temporary cloud API compatibility is allowed only as a deployment bridge, and the next implementation step must remove or deprecate that bridge.
  Rationale: Gateway and hosted control-plane deploys may not happen at the same instant, but compatibility layers should not become the new permanent contract.
  Date/Author: 2026-05-09 / User + Codex

- Decision: Command DTOs are scoped to the current PTZ command surface: `ptz_preset`, `ptz_look`, and `ptz_zoom`.
  Rationale: These are the command types that exist today. Broader opaque command payloads can be introduced later only when a real capability needs them.
  Date/Author: 2026-05-09 / User + Codex

- Decision: Hosted browser API response DTOs should stay local to `apps/control-plane` unless a shape is also a shared gateway/control-plane wire contract.
  Rationale: Browser responses are generated API surface for the hosted UI, not producer-side gateway contracts. Keeping them local avoids overloading `dirt_shared.cloud_contract`.
  Date/Author: 2026-05-09 / User + Codex

- Decision: Cloud data-consistency gaps such as latest metrics with missing device liveness should emit logs/audits, not change health response status.
  Rationale: `/api/health` consumers should not be broken by adding stricter consistency semantics. Logs and audit events make the inconsistency visible without changing the health contract.
  Date/Author: 2026-05-09 / User + Codex

- Decision: Guardrail tests should start narrow, focused on the known high-risk protocol annotations and route response models.
  Rationale: Broad `dict[str, Any]` scans would catch legitimate opaque metadata and test helpers. Narrow tests give useful pressure without creating noisy false positives.
  Date/Author: 2026-05-09 / User + Codex


## Outcomes & Retrospective

Milestone 1 added `apps/shared/src/dirt_shared/cloud_contract.py` with additive Pydantic DTOs for gateway/control-plane requests and responses without changing runtime imports or behavior. The new shared contract covers heartbeat, catalog, latest metrics, rollups, asset sign/complete/failure/retention, command claim/result, and the focused response DTOs for sign-upload, command claim, command result, and prune responses.

During main-agent review, the retention DTO was updated to include `as_of_date` because the current gateway already includes that field in `asset_retention` projections. Keeping it in the shared model avoids a future `extra="forbid"` rejection during Milestone 3.

Validation passed:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run ruff check apps/shared/src/dirt_shared/cloud_contract.py apps/shared/tests/test_cloud_contract.py
    uv run ruff format apps/shared/src/dirt_shared/cloud_contract.py apps/shared/tests/test_cloud_contract.py --check

The simplify pass trimmed standalone PTZ payload union classes that belong to Milestone 4 rather than this additive Milestone 1 contract module.

Milestone 2 preflight found no pending read-only outbox rows, so no live outbox mutation was needed before tightening replay validation:

    catalog        delivered   1747
    heartbeat      delivered   2844
    latest_metrics delivered   2844
    rollups        delivered    725
    rollups        superseded  2090

Milestone 2 converted local read-only projections to shared DTOs: `GatewayLocalServiceBundle.collect_catalog()` now returns `CatalogRequest`, `collect_latest_metrics()` returns `LatestMetricsRequest`, and `collect_rollups()` returns `RollupsRequest`. `GatewaySyncService` keeps those projection models until enqueue, stores `model_dump(mode="json")` at the outbox boundary, hashes the serialized payload for idempotency, and validates stored read-only JSON back into the known DTO before dispatch. Asset upload, asset retention, and command result remain on the raw path for later milestones.

`apps/gateway/tests/test_sync.py` now asserts catalog projection model instances before enqueue and includes a replay regression proving that a stored catalog payload missing required `last_seen_at` fails validation before dispatch. The existing rollup behavior was preserved: pending rollups are superseded by newer projections, and 5m/1h/4h buckets keep their independent intervals.

Validation passed:

    uv run pytest apps/gateway/tests/test_sync.py -q
    uv run pytest apps/gateway/tests -q
    uv run ruff check apps/gateway/src apps/gateway/tests apps/shared/src/dirt_shared/cloud_contract.py
    uv run ruff format apps/gateway/src apps/gateway/tests apps/shared/src/dirt_shared/cloud_contract.py --check

The simplify fallback pass reviewed reuse, quality, and efficiency over the Milestone 2 diff. It applied one small cleanup: the HTTP client now serializes any Pydantic request via `BaseModel.model_dump(mode="json")` instead of repeating a read-only union check.

Milestone 3 converted gateway asset payloads to shared DTOs. `AssetUploadProjection` now carries `AssetSignUploadRequest`, `AssetCompleteRequest`, and local-only `file_path: Path`; enqueueing serializes through `AssetUploadOutboxPayload` with JSON-safe nested request DTOs and a string file path. Stored `asset_upload` rows are validated back into `AssetUploadOutboxPayload` before `sign_upload`, byte upload, `complete_asset`, or failure reporting. Stored `asset_retention` rows are validated into `AssetRetentionRequest` before pruning.

`CloudGatewayClient` and `HttpCloudGatewayClient` now use the shared asset request DTOs and validate asset responses with `SignUploadResponse`, `AssetCompleteResponse`, `AssetFailureResponse`, and `PruneAssetsResponse`. Command payloads remain raw for Milestone 4.

The hosted control-plane asset endpoints now reuse the shared asset request/response DTOs. A focused local fix changed `/assets/complete` to resolve an existing `CloudAsset` by `(site_id, tent_id, object_key)` when no row exists for the new `asset_id`, then update that row. This should allow the known live pending asset row to drain after the hosted control-plane is deployed, but no live outbox rows were mutated and no hosted deployment was performed in this milestone.

`apps/gateway/tests/test_sync.py` now proves asset upload requests are typed through enqueue and dispatch, and that malformed stored `asset_upload` JSON fails validation before any asset cloud calls. `apps/control-plane/tests/test_api.py` covers completing the same object key with a new asset id without violating the unique object-key constraint.

Validation passed:

    uv run pytest apps/gateway/tests/test_sync.py -q
    uv run pytest apps/gateway/tests -q
    uv run pytest apps/control-plane/tests/test_api.py::test_asset_complete_replaces_existing_asset_for_same_object_key -q
    uv run ruff check apps/gateway/src apps/gateway/tests apps/shared/src/dirt_shared/cloud_contract.py
    uv run ruff format apps/gateway/src apps/gateway/tests apps/shared/src/dirt_shared/cloud_contract.py --check
    uv run ruff check apps/control-plane/src/dirt_control/api/gateway.py apps/control-plane/tests/test_api.py
    uv run ruff format apps/control-plane/src/dirt_control/api/gateway.py apps/control-plane/tests/test_api.py --check

The simplify fallback pass reviewed reuse, quality, and efficiency over the Milestone 3 diff. It found no follow-up edits worth making; the duplicate-object-key control-plane fix stayed intentionally narrow and local to asset completion.

Milestone 4 converted the PTZ command boundary to shared Pydantic DTOs. `CommandClaimResponse` now validates claimed commands before gateway command handling, with explicit payload models for `ptz_preset`, `ptz_look`, `ptz_zoom` absolute zoom, and `ptz_zoom` relative delta. `CommandResultRequest` and `CommandResultOutboxPayload` now carry command result reports through direct reporting and outbox replay, and `HttpCloudGatewayClient` validates both command claim and command result responses before returning them to gateway services.

`GatewayCommandService` now handles typed `ClaimedCommand` instances instead of raw dictionaries. The old required-string, datetime, local-payload, and numeric payload parsing branches were removed; local safety checks remain for site scope, PTZ device/capability scope, and preset existence. The hosted control-plane gateway command claim/result endpoints now use the shared command request/response DTOs and declare response models.

`apps/gateway/tests/test_sync.py` covers valid PTZ claim execution, typed command result reports, command result outbox replay validation before cloud calls, business-rule rejection without PTZ execution, and malformed PTZ claim rejection before execution or result reporting. The shared cloud contract tests now cover explicit PTZ payload model selection and command-type/payload mismatch rejection. Control-plane API tests were updated to use the current `preset_id` PTZ payload shape.

Validation passed:

    uv run pytest apps/gateway/tests/test_sync.py -q
    uv run pytest apps/gateway/tests -q
    uv run ruff check apps/gateway/src apps/gateway/tests apps/shared/src/dirt_shared/cloud_contract.py
    uv run ruff format apps/gateway/src apps/gateway/tests apps/shared/src/dirt_shared/cloud_contract.py --check
    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run pytest apps/control-plane/tests/test_api.py -q
    uv run ruff check apps/control-plane/src/dirt_control/api/gateway.py apps/control-plane/tests/test_api.py apps/shared/tests/test_cloud_contract.py
    uv run ruff format apps/control-plane/src/dirt_control/api/gateway.py apps/control-plane/tests/test_api.py apps/shared/tests/test_cloud_contract.py --check

The simplify fallback pass reviewed reuse, quality, and efficiency over the Milestone 4 diff because this runtime did not expose subagent spawning. It applied one lint-driven cleanup in the local command safety check and found no additional cleanup worth making within the milestone scope.

Milestone 5 added local hosted browser response DTOs in `apps/control-plane/src/dirt_control/api/browser.py` and wired them into FastAPI `response_model` declarations for health, auth identity, sites, tents, tent state, current metrics, metric history, devices, light schedules, latest assets, signed asset responses, sync status, command create/detail/list responses, gateway credential rotation, and browser asset pruning. Route handlers and browser response helpers now return DTO instances instead of raw response dictionaries/lists where the shape is concrete.

The browser-only DTOs stayed local to `apps/control-plane`. The simplify fallback pass reused the shared `PruneAssetsResponse` because that prune response shape is already a gateway/control-plane wire contract, and changed the internal light-state helper to a dataclass rather than a Pydantic response model. Command payload/result fields remain typed as opaque `dict[str, Any]` because those nested values are intentionally command-specific payload data, not concrete browser response envelopes.

No generated frontend contract artifacts were updated. The hosted browser cloud client used by `web-ui` is manually typed in `web-ui/src/api-client/cloud.ts`; the generated contract path under `contracts/webapp-v1.yaml` still describes the local web API surface and was not changed by this hosted FastAPI response-model update.

Validation passed:

    uv run pytest apps/control-plane/tests -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint

Milestone 6 added agent-owned guardrails for the high-risk typed-boundary seams. `apps/gateway/tests/test_gateway_boundary_guardrails.py` now pins `dirt_gateway.protocols.CloudGatewayClient` request/response annotations and `LocalGatewayServices` projection returns to concrete DTOs where DTOs exist, while allowing intentional opaque values such as PTZ execution results and upload headers outside that owned protocol payload surface. `apps/control-plane/tests/test_control_plane_boundary_guardrails.py` now pins hosted browser `response_model` coverage from Milestone 5 and hosted gateway route request/response models for shared gateway DTOs. The guardrails also prove that catalog devices must include the required nullable `last_seen_at` key.

The guardrails exposed one remaining contract drift in the hosted gateway read-only routes: heartbeat/catalog/latest-metrics/rollups were still using local request models or raw response annotations even though shared DTOs existed. Milestone 6 converted those route annotations to the shared `HeartbeatRequest`/`HeartbeatResponse`, `CatalogRequest`/`CatalogResponse`, `LatestMetricsRequest`/`UpsertCountResponse`, and `RollupsRequest`/`UpsertCountResponse` models. The gateway HTTP client and protocol now validate those response DTOs before returning.

`/api/health` now emits a `data_consistency_missing_device_liveness` audit row when an active `CloudDevice` has current latest metrics for the same site/tent/device but `last_seen_at is None`. The health response keeps the existing 200/status semantics; the audit signal is deduped for the same device over a one-hour window and is committed only when a new audit row is emitted.

Validation passed:

    uv run pytest apps/gateway/tests/test_gateway_boundary_guardrails.py -q
    uv run pytest apps/control-plane/tests/test_control_plane_boundary_guardrails.py apps/control-plane/tests/test_api.py::test_health_audits_current_metrics_without_device_liveness -q
    uv run pytest apps/gateway/tests -q
    uv run pytest apps/control-plane/tests -q
    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run ruff check apps/gateway/src/dirt_gateway/protocols.py apps/gateway/src/dirt_gateway/cloud.py apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py apps/control-plane/src/dirt_control/api/gateway.py apps/control-plane/src/dirt_control/api/browser.py apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py
    uv run ruff format apps/gateway/src/dirt_gateway/protocols.py apps/gateway/src/dirt_gateway/cloud.py apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py apps/control-plane/src/dirt_control/api/gateway.py apps/control-plane/src/dirt_control/api/browser.py apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py --check

The simplify fallback pass found two small cleanup opportunities and applied both: `/api/health` now avoids a no-op commit when a recent audit already exists, and the catalog liveness guardrail validates actual `CatalogRequest` rejection rather than only checking JSON Schema metadata. No production deploys, migrations, or human-owned invariants were changed.

Final validation after completing all milestones:

    scripts/agent-fix
    git diff --check

Both passed. The full suite command `uv run pytest -q` was also run; all typed-boundary, gateway, control-plane, shared, and invariant tests reached by the suite passed, but the command failed in unrelated wake-word import tests because the installed SciPy no longer exposes `scipy.special.sph_harm` for the `acoustics` dependency imported by `openwakeword`.


## Context and Orientation

Dirt is a Python 3.13 uv workspace with multiple services under `apps/`. `dirt-gateway` is a local outbound-only process. It reads local Postgres state, projects it into JSON events, stores those events in a local outbox, and delivers them to the hosted `dirt-control-plane` API at `https://api.sirius-forge.com`. `dirt-control-plane` stores cloud state in Railway Postgres and provides the hosted Sirius Forge frontend API.

A "boundary" in this plan means data crossing any of these edges:

- HTTP request or response.
- Gateway-to-control-plane client call.
- Cloud-to-gateway command claim response.
- Durable outbox JSON payload that will be replayed later.
- JSON command payload or result consumed by another service.
- Generated frontend API contract.

The current local browser API is mostly covered by Pydantic response models and generated OpenAPI contracts. The hosted gateway path is not. Key files:

- `apps/gateway/src/dirt_gateway/protocols.py`: defines loose Protocols and `AssetProjection` with raw dict payloads.
- `apps/gateway/src/dirt_gateway/local.py`: builds catalog, latest metric, rollup, and asset payloads as raw dictionaries.
- `apps/gateway/src/dirt_gateway/sync.py`: stores and dispatches outbox events using event-type strings and raw dictionaries.
- `apps/gateway/src/dirt_gateway/cloud.py`: sends raw JSON to the cloud API and returns raw response dictionaries.
- `apps/gateway/src/dirt_gateway/commands.py`: parses claimed command dictionaries and emits command result dictionaries.
- `apps/control-plane/src/dirt_control/api/gateway.py`: validates inbound gateway requests using local Pydantic request models.
- `apps/control-plane/src/dirt_control/api/browser.py`: returns many hosted browser responses as raw dictionaries/lists.
- `apps/shared/src/dirt_shared/models/cloud_gateway.py`: local outbox and cursor DB rows store JSON payloads.

The bug that motivated this work occurred because `local.py` omitted `last_seen_at` in the raw catalog device dictionary. The cloud model had `last_seen_at` nullable with a default, so missing key and intentional null were indistinguishable.


## Plan of Work

Milestone 1 adds the shared contract module without changing delivery behavior. Create `apps/shared/src/dirt_shared/cloud_contract.py` with Pydantic models for the gateway/control-plane protocol. Start with read-only sync models: heartbeat, catalog, latest metrics, rollups, asset sign/complete/failure/retention, and command result. Include response DTOs for sign-upload, command claim, command result, and prune responses. Use `ConfigDict(extra="forbid")` for owned models. Add tests in `apps/shared/tests/test_cloud_contract.py` proving that `CatalogDevice(last_seen_at=...)` accepts timestamps, `CatalogDevice(last_seen_at=None)` accepts intentional null, and missing `last_seen_at` fails.

Milestone 2 drains existing cloud outbox rows, then converts read-only gateway projections. Before changing replay validation, inspect and drain pending `CloudOutbox` rows for the affected event types; document the observed state in this ExecPlan. After the outbox is clean, update `GatewayLocalServiceBundle.collect_catalog`, `collect_latest_metrics`, and `collect_rollups` to return Pydantic models instead of dictionaries. Update `LocalGatewayServices` Protocol accordingly. In `GatewaySyncService._collect_projections`, keep a typed projection map until enqueue time, then store `model_dump(mode="json")`. Update the idempotency hash helper to hash serialized model output. Extend `apps/gateway/tests/test_sync.py` to assert model instances before enqueue where useful. Do not add a legacy replay adapter for old raw projection shapes.

Milestone 3 converts assets and outbox asset dispatch after draining any pending asset outbox rows. Replace `AssetProjection.sign_request` and `complete_request` raw dicts with `AssetSignUploadRequest` and `AssetCompleteRequest` DTOs. Introduce an `AssetUploadProjection` DTO or dataclass that keeps `file_path: Path` as local-only process data while serializing only JSON-safe request models into the outbox. Validate deserialized `asset_upload` outbox rows before calling `sign_upload`, `upload_asset`, and `complete_asset`. Remove unused raw-payload helper code once the typed path is active.

Milestone 4 converts cloud commands. Define `ClaimedCommand`, `CommandClaimResponse`, `CommandResultRequest`, and PTZ payload models. Use discriminated unions or explicit models for only the current PTZ command types: `ptz_preset`, `ptz_look`, and `ptz_zoom`. Update `GatewayCommandService` so cloud claim responses are validated before command handling. Replace manual `_required_str`, `_local_payload`, and most of `_validate_claimed_command` with model validation plus business checks such as preset existence. Keep local safety guards for site/device/capability scope. If deployment ordering requires a temporary cloud compatibility branch, mark it explicitly and remove it in the next step.

Milestone 5 types hosted browser responses. Move repeated response shapes in `apps/control-plane/src/dirt_control/api/browser.py` into local Pydantic models, or import from `dirt_shared.cloud_contract` only when the shape is also a gateway/control-plane wire contract. Add `response_model=...` to hosted routes that currently return raw dictionaries/lists: health, sites, tents, tent state, current metrics, metric history, devices, assets, sync status, commands, command details, and admin prune/rotate responses. Regenerate frontend contracts if this changes the OpenAPI surface used by `web-ui`.

Milestone 6 adds guardrails. Add focused tests that scan high-risk interfaces for new raw boundary payload types. Start as agent-owned tests under `apps/gateway/tests/` and `apps/control-plane/tests/`, targeting `dirt_gateway.protocols.CloudGatewayClient`, `LocalGatewayServices`, and hosted route annotations rather than every `dict[str, Any]` in the tree. If stable, promote a narrow human-owned invariant later: for example, `dirt_gateway.protocols.CloudGatewayClient` methods must accept/return Pydantic DTOs, not `dict[str, Any]`. Add data-consistency log/audit events when an active cloud device has latest metrics but missing `last_seen_at`; do not change `/api/health` status semantics for this check.


## Concrete Steps

Work from the repo root:

    cd /home/akcom/code/dirt

Before implementing any milestone, read the boundary rule:

    sed -n '1,220p' docs/rules/boundary-contracts.md

Before Milestones 2 and 3, inspect and drain existing outbox rows for the event types being converted. Record the result under `Outcomes & Retrospective` before tightening replay validators. The intended implementation is a clean cutover, not a long-lived legacy-shape compatibility layer.

Milestone 1 commands:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run ruff check apps/shared/src/dirt_shared/cloud_contract.py apps/shared/tests/test_cloud_contract.py
    uv run ruff format apps/shared/src/dirt_shared/cloud_contract.py apps/shared/tests/test_cloud_contract.py --check

Milestones 2 through 4 commands:

    uv run pytest apps/gateway/tests/test_sync.py -q
    uv run pytest apps/gateway/tests -q
    uv run ruff check apps/gateway/src apps/gateway/tests apps/shared/src/dirt_shared/cloud_contract.py
    uv run ruff format apps/gateway/src apps/gateway/tests apps/shared/src/dirt_shared/cloud_contract.py --check

Milestone 5 commands:

    uv run pytest apps/control-plane/tests -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint

Full validation before completion:

    uv run pytest -q
    scripts/agent-fix

Expected result for the focused gateway test after Milestone 2:

    apps/gateway/tests/test_sync.py::test_catalog_syncs_homebox_main_and_breeding PASSED

That test must fail if `last_seen_at` is omitted from a catalog device.


## Validation and Acceptance

The implementation is accepted when all of these are true:

- A producer-side attempt to build a catalog device without `last_seen_at` raises a Pydantic validation error.
- Gateway projections are model instances until the single serialization point into the outbox.
- Outbox replay validates stored JSON into a known event model before dispatching.
- Gateway HTTP client validates cloud responses before command or asset logic consumes them.
- Control-plane gateway routes and hosted browser routes declare Pydantic request and response models for JSON bodies.
- Tests cover the previously observed bug: an actively reporting breeding-tent ESP32 syncs `last_seen_at` to the hosted device row.
- Data-consistency logs or audit events detect a cloud device that has current metrics but no device liveness timestamp, without changing `/api/health` status semantics.
- Documentation indexes tell future agents to read `docs/rules/boundary-contracts.md` before touching boundary code.


## Idempotence and Recovery

Adding Pydantic DTOs is safe and additive while the old raw dictionary shape is still serialized at the HTTP boundary. Migrate one event type at a time. If deployment ordering requires temporary compatibility, keep it narrow, mark it explicitly, and remove or deprecate it in the next implementation step.

Outbox rows created before this migration may contain older payload shapes. The chosen rollout policy is to drain old rows before tightening validation, then make a clean cutover. Do not delete outbox rows casually; inspect with SQL first, prefer normal gateway delivery to drain pending rows, and document the observed cleanup in this ExecPlan. Do not add long-lived validators for old outbox payload shapes.

Cloud API changes must remain backward compatible with the currently deployed gateway until the local gateway is restarted on new code. For owned request DTOs, make newly required fields required at the producer first, then tighten the receiver after deployment if necessary.

If `scripts/agent-fix` rewrites files, re-run the focused tests before committing. Do not modify `apps/tests/invariants/` unless the user explicitly asks; if an invariant fails, fix production code or add a new agent-owned test first.


## Artifacts and Notes

External references used for the plan:

- IBM progressive disclosure guidance: https://www.ibm.com/docs/en/technical-content?topic=practices-progressive-disclosure
- Diataxis documentation framework: https://diataxis.fr/
- Pydantic model validation and serialization: https://docs.pydantic.dev/latest/concepts/models/
- FastAPI response model docs: https://fastapi.tiangolo.com/tutorial/response-model/

Current inventory evidence:

- `apps/gateway/src/dirt_gateway/protocols.py` exposes raw `dict[str, Any]` for all gateway client payloads.
- `apps/control-plane/src/dirt_control/api/gateway.py` has local request models that should move to or reuse `dirt_shared.cloud_contract`.
- `apps/control-plane/src/dirt_control/api/browser.py` mostly returns raw dictionaries/lists and should gain response models.
- `apps/web/src/dirt_web/api/` already uses many `response_model=...` declarations and is the local pattern to emulate.


## Interfaces and Dependencies

New or revised interfaces expected by completion:

- `dirt_shared.cloud_contract` exports Pydantic DTOs for cloud gateway payloads. Hosted browser API response DTOs stay local to `apps/control-plane` unless they are also gateway/control-plane wire contracts.
- `dirt_gateway.protocols.CloudGatewayClient` accepts Pydantic request models and returns Pydantic response models.
- `dirt_gateway.protocols.LocalGatewayServices` returns Pydantic projection models.
- `CloudOutbox.payload` remains JSONB, but values stored there come from `model_dump(mode="json")` and are validated on replay.
- `apps/control-plane/src/dirt_control/api/gateway.py` imports shared DTOs instead of maintaining a divergent local copy.
- `apps/control-plane/src/dirt_control/api/browser.py` declares `response_model` for JSON routes.
- `docs/rules/boundary-contracts.md` remains the rule-of-record for boundary schema decisions.

Dependencies:

- Pydantic v2 through existing FastAPI/SQLModel dependency graph.
- Existing uv workspace package dependency from `dirt-gateway` and `dirt-control-plane` to `dirt-shared`.
- Existing OpenAPI/TypeScript generation flow under `contracts/` and `web-ui/src/api-client/generated/`.


## Revision Notes

- 2026-05-08 / Codex: Initial plan created after the hosted breeding device `last_seen_at` omission exposed raw gateway dictionaries as an architectural risk.
