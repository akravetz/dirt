# Python Quality Radar Handoff

Updated: 2026-05-21

This document is the working handoff for a fresh agent picking up the Python
Quality Radar epic after the first implementation and review discussion. It
summarizes what has already been built, what the first report showed, what was
judged useful versus noisy, and where cleanup work should resume.

## Current State

The implementation work through Milestone 3 was completed on branch
`feature/python-quality-radar-m1-m3` in commit:

    aa69e72 Add Python quality radar baseline

That branch contains:

- `scripts/python-quality-radar`
- `scripts/lib/python_quality_radar.py`
- `scripts/python-quality-radar-semgrep.yml`
- `apps/shared/tests/test_python_quality_radar.py`
- `docs/epics/python-quality-radar/baseline-review.md`
- `docs/epics/python-quality-radar/ExecPlan.md` updated through Milestone 3

At the time this handoff was written, the current `main` checkout still had the
pre-implementation epic files. Check whether the branch has been merged before
continuing. If it has not, review or merge the branch before starting Milestone
4 cleanup work.

## Validation Already Run

The Milestone 1-3 branch passed:

    scripts/python-quality-radar --format markdown --output var/reports/python-quality-radar/latest.md
    scripts/python-quality-radar --format json --output var/reports/python-quality-radar/latest.json
    uv run pytest apps/shared/tests/test_python_quality_radar.py -q
    uv run pytest apps/tests/invariants/ -q
    uv run ruff check
    git diff --check

The commit hooks also passed the broader app test suites they run.

Generated report artifacts stay under ignored `var/reports/python-quality-radar/`
and should not be committed.

## Baseline Report Summary

The validated baseline report on the implementation branch scanned:

- Production files: 140
- Test files used for proximity evidence: 82
- Findings: 457
- Review packets: 97

Category counts:

| Category | Count | Interpretation |
|---|---:|---|
| `complexity` | 110 | Strong when clustered with boundary, route, or control-loop code. |
| `duplication` | 0 | No jscpd hits at the configured threshold. |
| `route-edge` | 63 | Strongest in control-plane API modules. |
| `service-infrastructure` | 16 | Review signal only; hardware/cloud services often legitimately touch clients. |
| `boundary` | 62 | Strongest in gateway/control-plane protocol paths. |
| `dto-drift` | 0 | No duplicate DTO drift found. |
| `thin-wrapper` | 102 | Noisy; many wrappers are deliberate boundary/protocol shapes. |
| `error-handling` | 25 | Useful where broad catches lack structured context or typed failure flow. |
| `security` | 0 | No Ruff `S` findings. |
| `async` | 0 | No Ruff `ASYNC` findings. |
| `suppression` | 60 | Periodic audit signal, not cleanup by itself. |
| `test-proximity` | 19 | Weak supporting signal only. |

Top packets from the baseline review:

1. `apps/control-plane/src/dirt_control/api/gateway.py`
2. `apps/control-plane/src/dirt_control/api/browser.py`
3. `apps/hwd/src/dirt_hwd/services/humidifier.py`
4. `apps/shared/src/dirt_shared/services/readings.py`
5. `apps/gateway/src/dirt_gateway/sync.py`
6. `apps/gateway/src/dirt_gateway/commands.py`
7. `apps/hwd/src/dirt_hwd/services/fan_controller.py`
8. `apps/gateway/src/dirt_gateway/cloud.py`

## Semgrep Usefulness

Semgrep produced 313 of 457 total findings, so it dominates the report. It is
useful as a high-recall review queue, not as a direct guardrail yet.

Semgrep detector counts:

| Detector | Count | Read |
|---|---:|---|
| `semgrep-thin-wrapper-forwarding` | 69 | Noisy. Many client/protocol wrappers are intentional. |
| `semgrep-suppression-comment` | 60 | Useful audit list, but not cleanup by itself. |
| `semgrep-route-direct-db-call` | 45 | Useful. Correctly points at fat control-plane routes. |
| `semgrep-boundary-raw-dict-any` | 42 | Useful. Best boundary-contract signal. |
| `semgrep-stale-marker` | 33 | Noisy. Flags settings aliases and compatibility wording. |
| `semgrep-broad-exception` | 21 | Useful but requires daemon-loop judgment. |
| `semgrep-boundary-json-model-conversion` | 20 | Mixed. `model_dump()` and `model_validate()` are often correct at boundaries. |
| `semgrep-service-infrastructure-import` | 16 | Mixed. Hardware/cloud services often own these imports legitimately. |
| `semgrep-route-raw-dict` | 6 | Mixed. Simple ack/health dictionaries may be acceptable. |
| `semgrep-pass-in-except` | 1 | Likely useful if still present. |

Best Semgrep promotion candidates after cleanup review:

- Raw `dict[str, Any]` in gateway/control-plane protocol, command, cloud, and outbox paths.
- FastAPI route handlers with direct DB calls plus high span/branch count.
- Broad exception handlers in daemon or boundary loops only when they lack
  structured context, typed failure outcome, or an explicit rationale.

Do not promote `thin-wrapper`, `stale-marker`, `suppression`, or generic
`model_dump()`/`model_validate()` findings without narrower rules or allowlists.

## Cleanup Candidate 1: Gateway/Control-Plane Boundary Dictionaries

The first reviewed true-positive class is raw dictionary flow around gateway,
cloud, outbox, and command boundaries. The code already has several good
Pydantic cloud contracts, so cleanup should tighten the remaining weak handoffs
rather than introduce a new abstraction layer.

Representative examples from the implementation branch/current codebase:

`apps/gateway/src/dirt_gateway/commands.py`

```python
async def _execute_ptz(self, item: ClaimedCommand) -> dict[str, Any]:
    payload = item.payload
    if isinstance(payload, PtzPresetPayload):
        return await self._ptz.apply_preset(payload.preset_id)
    if isinstance(payload, PtzLookPayload):
        return await self._ptz.look_at_normalized(payload.x, payload.y)
    if isinstance(payload, PtzZoomAbsolutePayload):
        return await self._ptz.zoom_to(payload.zoom)
    if isinstance(payload, PtzZoomRelativePayload):
        return await self._ptz.zoom_by(payload.delta)
    raise ValueError(f"unsupported command_type: {item.command_type}")
```

```python
def _local_payload(item: ClaimedCommand) -> dict[str, Any]:
    payload = item.payload
    if isinstance(payload, PtzPresetPayload):
        return {"preset_id": payload.preset_id}
    if isinstance(payload, PtzLookPayload):
        return {"x": payload.x, "y": payload.y}
    if isinstance(payload, PtzZoomAbsolutePayload):
        return {"zoom": payload.zoom}
    return {"delta": payload.delta}
```

`apps/gateway/src/dirt_gateway/sync.py`

```python
ReadOnlyProjectionPayload = (
    HeartbeatRequest | CatalogRequest | LatestMetricsRequest | RollupsRequest
)
TypedProjectionPayload = (
    ReadOnlyProjectionPayload | AssetRetentionRequest | AssetUploadProjection
)
ProjectionPayload = TypedProjectionPayload | dict[str, Any]
```

```python
def _projection_payload_json(payload: ProjectionPayload) -> dict[str, Any]:
    if isinstance(payload, AssetUploadProjection):
        return payload.to_outbox_payload().model_dump(mode="json")
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    return dict(payload)
```

Proposed cleanup:

1. Trace every constructor of `ProjectionPayload` and every command result/local
   command payload handoff.
2. Convert remaining raw dict payloads to existing Pydantic DTOs where possible.
3. Add small truthful DTOs only where the domain already has a real shape, such
   as local PTZ command payload/result data.
4. Remove `dict[str, Any]` from `ProjectionPayload`.
5. Make `_projection_payload_json()` reject unsupported payload types instead of
   copying arbitrary mappings.
6. Add focused tests proving malformed command/projection payloads fail before
   enqueueing or cloud reporting.

Important judgment: do not start with generic row-update helpers such as
`_upsert(..., values: dict[str, Any])` in the control-plane API. Those are
internal persistence plumbing. The higher-value boundary cleanup is the
gateway/outbox/command flow where raw dictionaries cross process, persistence,
or network boundaries.

## Cleanup Candidate 2: Control-Plane Route Business Logic

The second reviewed true-positive class is FastAPI route handlers that directly
own business workflow and persistence orchestration. A direct DB call in a route
is not automatically bad, but the clustered findings in control-plane gateway
and browser APIs are real.

Representative examples:

`apps/control-plane/src/dirt_control/api/gateway.py`

```python
@router.put("/catalog", response_model=CatalogResponse)
async def catalog(
    body: CatalogRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CatalogResponse:
    require_gateway_scope(principal, body.site.site_id)
    now = clock()
    await _upsert(
        session,
        CloudSite,
        body.site.site_id,
        {
            "site_id": body.site.site_id,
            "name": body.site.name,
            "timezone": body.site.timezone,
            "is_active": True,
            "last_catalog_sync_at": now,
            "created_at": now,
            "updated_at": now,
        },
        now=now,
    )
    for tent in body.tents:
        await _upsert(...)
```

This route continues with zones, devices, capabilities, and schedules. It is
really a catalog reconciliation operation living inside an HTTP handler.

`apps/control-plane/src/dirt_control/api/gateway.py`

```python
@router.post("/commands/claim", response_model=CommandClaimResponse)
async def claim_commands(
    body: CommandClaimRequest,
    principal: GatewayPrincipal = Depends(require_gateway),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandClaimResponse:
    require_gateway_scope(principal, body.site_id)
    now = clock()
    if not settings.gateway_command_claim_enabled:
        return CommandClaimResponse(commands=[])

    expired_rows = (
        await session.execute(
            select(CloudCommand).where(
                CloudCommand.site_id == body.site_id,
                CloudCommand.status.in_(["queued", "claimed"]),
                CloudCommand.expires_at <= now,
            )
        )
    ).scalars()
    for command in expired_rows:
        command.status = "expired"
        command.finished_at = now
        command.error = "command expired before local execution"
        command.updated_at = now
```

This handler then reuses previous claims, claims queued commands, writes audit
events, commits, and maps rows to response DTOs.

Proposed cleanup:

1. Start with `claim_commands` and `command_result`; they are smaller and easier
   to pin with tests than full catalog sync.
2. Add focused behavior tests for disabled claiming, expiring stale commands,
   returning still-valid claims, claiming queued commands, audit events, and
   command result idempotence.
3. Extract named domain operations such as `claim_gateway_commands()` and
   `record_gateway_command_result()`.
4. Keep route handlers responsible only for auth/scope, dependency acquisition,
   request DTOs, and response DTOs.
5. Then extract `sync_gateway_catalog()` from the catalog route after behavior is
   covered.

Avoid a generic "route service layer" abstraction. The useful shape here is
named domain operations: `sync_gateway_catalog`, `claim_gateway_commands`, and
`record_gateway_command_result`.

## Next Suggested Sequence

When a fresh agent resumes implementation, do this in order:

1. Confirm whether `feature/python-quality-radar-m1-m3` has been merged.
2. If not merged, inspect and merge/rebase that branch before cleanup work.
3. Read `docs/rules/simple-clean-architecture.md` and
   `docs/rules/boundary-contracts.md` before changing source code.
4. Start Milestone 4 with the gateway command/projection boundary cleanup, or
   with `claim_commands`/`command_result` extraction if the user wants route
   cleanup first.
5. Keep each cleanup slice small and test-backed.
6. Re-run the radar after each cleanup slice and update
   `docs/epics/python-quality-radar/baseline-review.md` with changed counts and
   detector behavior.

Preferred validation after each cleanup slice:

    uv run pytest apps/tests/invariants/ -q
    uv run pytest apps/gateway/tests apps/control-plane/tests apps/shared/tests -q
    uv run ruff check
    scripts/python-quality-radar --format json --output var/reports/python-quality-radar/latest.json
    scripts/python-quality-radar --format markdown --output var/reports/python-quality-radar/latest.md

Do not edit `apps/tests/invariants/`. If an invariant fails, fix source code.
