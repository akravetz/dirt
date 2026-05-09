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
- [ ] Milestone 2: Drain existing outbox rows, then convert read-only gateway projections and outbox enqueue paths to typed DTOs with no legacy replay adapter.
- [ ] Milestone 3: Convert asset upload and retention payloads to typed DTOs and remove unused legacy raw-payload code.
- [ ] Milestone 4: Convert cloud command claim/result payloads to typed DTOs with discriminated PTZ payloads.
- [ ] Milestone 5: Add local Pydantic response models to hosted browser API routes and align generated frontend types.
- [ ] Milestone 6: Add narrow guardrail tests and log/audit data-consistency checks that prevent untyped boundary payloads from returning.


## Surprises & Discoveries

- Observation: The local `dirt-web` API already follows this pattern better than the hosted control-plane path.
  Evidence: Routes under `apps/web/src/dirt_web/api/` generally declare `response_model=...`, while hosted routes under `apps/control-plane/src/dirt_control/api/browser.py` mostly return `dict[str, Any]` or `list[dict[str, Any]]`.

- Observation: The highest-risk gap is the local gateway outbound protocol.
  Evidence: `apps/gateway/src/dirt_gateway/protocols.py` currently types all cloud payloads as `dict[str, Any]`; `local.py`, `sync.py`, `cloud.py`, and `commands.py` hand-build or consume nested dictionaries.

- Observation: The control-plane gateway API already has Pydantic request models, but they are local to `apps/control-plane` and are not shared with the producer.
  Evidence: `apps/control-plane/src/dirt_control/api/gateway.py` defines `CatalogRequest`, `LatestMetricsRequest`, `RollupsRequest`, and asset request models. The gateway producer cannot import them without depending on the control-plane package.

- Observation: Progressive-disclosure documentation should reveal this rule in layers, not bury it in an epic.
  Evidence: IBM's progressive-disclosure guidance emphasizes ordered disclosure and avoiding repeated information; Diataxis separates task-oriented how-to material from reference/explanation. In this repo that maps to `AGENTS.md` triggers, `docs/README.md` and `docs/rules/README.md` indexes, then a focused rule file.


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
