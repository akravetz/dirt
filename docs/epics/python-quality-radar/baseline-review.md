# Python Quality Radar Baseline Review

Reviewed: 2026-05-16T13:58:53-06:00
Source report: `var/reports/python-quality-radar/latest.json`

This is the Milestone 3 human review backlog for the first Python Quality Radar baseline. The raw reports stay under ignored `var/reports/python-quality-radar/`; this checked-in document is the durable review artifact.

## Baseline Counts

- Production files scanned: 140
- Test files used for proximity evidence: 82
- Findings: 457
- Review packets: 97

| Category | Count | Baseline read |
|---|---:|---|
| `complexity` | 110 | Strong signal when it clusters with boundary, route, or control-loop code. |
| `duplication` | 0 | No current jscpd hits at the configured threshold. |
| `route-edge` | 63 | Strong in `apps/control-plane`; expected to be partly noisy until service boundaries are reviewed. |
| `service-infrastructure` | 16 | Review signal only; hardware and cloud services legitimately touch clients. |
| `boundary` | 62 | Strong signal in gateway/control-plane protocol paths; weaker for deliberate model conversion helpers. |
| `dto-drift` | 0 | No current duplicate DTO drift detected. |
| `thin-wrapper` | 102 | Mixed signal; many settings aliases and protocol wrappers are probably intentional. |
| `error-handling` | 25 | Strongest when broad catches lack structured context or typed failure flow. |
| `security` | 0 | No Ruff `S` findings in this baseline. |
| `async` | 0 | No Ruff `ASYNC` findings in this baseline. |
| `suppression` | 60 | Periodic review signal, not cleanup by itself. |
| `test-proximity` | 19 | Weak signal; use only to prioritize tests around complex or boundary-heavy packets. |

Detector-level hotspots: `thin-wrapper` forwarding produced 69 findings, stale markers 33, raw boundary `dict[str, Any]` 42, boundary model conversion 20, direct route DB calls 45, route metrics 12, suppression comments 60, broad exceptions 21, and high-argument functions 31.

## Top Review Packets

| Rank | Packet | Score | Findings | Categories | Review priority |
|---:|---|---:|---:|---|---|
| 1 | `apps/control-plane/src/dirt_control/api/gateway.py` | 228 | 40 | `boundary`, `complexity`, `route-edge`, `thin-wrapper` | Highest. Gateway API routes mix route work, persistence, and protocol payload handling. Start with `catalog`, `camera_capture_policy`, `claim_commands`, and raw dict response points. |
| 2 | `apps/control-plane/src/dirt_control/api/browser.py` | 214 | 38 | `boundary`, `complexity`, `route-edge`, `suppression`, `thin-wrapper` | Highest. Browser API is the largest file at 984 non-comment LOC and has many direct route DB calls. Review endpoint/service split before adding more dashboard behavior. |
| 3 | `apps/hwd/src/dirt_hwd/services/humidifier.py` | 113 | 19 | `complexity`, `error-handling`, `service-infrastructure`, `suppression` | High. The humidifier loop is a legitimate control loop, but `run` spans 324 lines and the class spans 682 lines. Refactor only behind focused behavior tests. |
| 4 | `apps/shared/src/dirt_shared/services/readings.py` | 111 | 24 | `complexity`, `suppression`, `thin-wrapper` | High. Shared ingestion/query service has several high-argument entry points and broad responsibility. Good candidate for source-level API cleanup. |
| 5 | `apps/gateway/src/dirt_gateway/sync.py` | 80 | 17 | `boundary`, `complexity`, `suppression`, `thin-wrapper` | High. Boundary payload typing and outbox projection helpers deserve review before more cloud sync features land. |
| 6 | `apps/gateway/src/dirt_gateway/commands.py` | 78 | 14 | `boundary`, `complexity`, `error-handling`, `suppression` | High. Command payload/result dictionaries are likely true-positive boundary contract risks. |
| 7 | `apps/hwd/src/dirt_hwd/services/fan_controller.py` | 61 | 14 | `complexity`, `error-handling`, `service-infrastructure`, `suppression`, `thin-wrapper` | Medium-high. `decide_fan_trim` and `run` are worth reviewing, but hardware-control behavior needs careful test coverage first. |
| 8 | `apps/gateway/src/dirt_gateway/cloud.py` | 55 | 15 | `boundary`, `complexity`, `thin-wrapper` | Medium-high. Client methods are mostly expected wrappers, but response payload parsing is a useful typed-contract target. |
| 9 | `apps/shared/src/dirt_shared/services/daily_synthesis.py` | 54 | 12 | `complexity`, `suppression`, `thin-wrapper` | Medium. Large runner classes and stale markers may hide removable compatibility paths, but external agent execution creates real wrapper needs. |
| 10 | `apps/control-plane/src/dirt_control/settings.py` | 51 | 17 | `thin-wrapper` | Low as cleanup. This is mostly alias configuration; useful detector-noise example. |

## Likely True-Positive Cleanup Candidates

1. Gateway/control-plane boundary dictionaries.
   Evidence: 42 raw `dict[str, Any]` boundary findings, concentrated in `dirt_gateway/{commands,sync,cloud,outbox}.py`, `dirt_control/api/gateway.py`, shared command/cloud models, and cloud contract helpers. Cleanup direction: identify the owner DTO for command payloads, command results, outbox payloads, asset upload payloads, and gateway projection payloads. Prefer Pydantic models at producer and consumer boundaries over repeated raw dict signatures.

2. Control-plane route business logic.
   Evidence: 63 route-edge findings, including 45 direct DB-call findings. The two largest packets are `api/gateway.py` and `api/browser.py`. Cleanup direction: extract cohesive service functions for catalog sync, camera capture policy, command claiming/results, browser metric history, schedules, and command creation. Keep FastAPI handlers thin after behavior is covered.

3. Humidifier loop complexity.
   Evidence: `HumidifierLoopService.run` spans 324 lines, the class spans 682 lines, and helper signatures reach 17 arguments. Cleanup direction: first add or verify focused tests for dispatch decisions, lack-water handling, shadow logging, and alert paths. Then split pure decision/state transition helpers from IO-heavy loop orchestration.

4. Shared readings service parameter sprawl.
   Evidence: `ingest_reading` has 10 arguments, `_get_metric_series` has 8, `_touch_device_heartbeat` has 9, and several public query helpers have 7. Cleanup direction: introduce truthful request/value objects only where they represent existing domain concepts, not generic parameter bags. Review whether capabilities, device heartbeat, and metric history should have narrower service entry points.

5. Gateway command error handling.
   Evidence: `apps/gateway/src/dirt_gateway/commands.py` has boundary findings plus broad exception handling in command execution/reporting. Cleanup direction: preserve daemon resilience, but make command failure outcomes typed and consistently logged with enough context for replay/debugging.

6. Kasa and hardware loop broad exceptions.
   Evidence: 21 broad exception findings, many in `apps/hwd/src/dirt_hwd/services/*`. Cleanup direction: classify which catches intentionally keep loops alive, then require structured `log_event()` or explicit typed failure returns where the catch crosses a hardware or daemon boundary.

## Noisy Or False-Positive-Prone Detector Classes

- `thin-wrapper` in settings/configuration code: `apps/control-plane/src/dirt_control/settings.py` is mostly Pydantic alias declarations, not stale compatibility debt.
- Protocol/client forwarding wrappers: gateway cloud clients and PTZ executors often wrap process or network boundaries deliberately. Treat these as review prompts, not automatic deletion candidates.
- `suppression` comments: 60 findings are useful for periodic audit, but a `noqa` with local rationale is not itself a cleanup backlog item.
- `service-infrastructure` imports: hwd services legitimately own hardware and vendor client calls. This signal matters more when an infrastructure import appears in shared or route-edge code.
- `test-proximity`: 19 files have no obvious nearby test name or mention, but stem matching is weak. Use it only when the same file also has complexity, boundary, or error-handling findings.
- Route raw dict returns for simple health/ack endpoints: some raw `{"ok": true}` responses may be acceptable; prioritize owned protocol and generated-client boundaries first.
- Boundary model conversion calls: `model_dump()` and `model_validate()` are often correct at serialization edges. The risky class is unowned raw dict flow, not the presence of conversion by itself.

## Candidate Guardrails For Milestone 5

- Boundary DTO guardrail: agent-owned test or lint scan that rejects raw `dict[str, Any]` in gateway/control-plane command, outbox, cloud projection, and generated-client boundary paths unless an allowlist entry names the owning DTO decision.
- Broad exception guardrail: report-only test requiring broad catches in production loops to either log structured context with `log_event()`/logger context, return a typed failure outcome, or carry a local allowlist rationale.
- Route-edge guardrail: report-only test for FastAPI route handlers above an agreed span/branch threshold or with direct session DB calls, with explicit allowlist for tiny health/ack routes.
- Complexity budget guardrail: report-only review for functions/classes above thresholds, with stronger scoring when the same file also has boundary or error-handling findings.
- Duplication guardrail: keep jscpd in the radar even though this baseline has 0 hits; promote only after repeated nonzero true positives.
- Suppression audit guardrail: periodic report of `noqa`, `type: ignore`, and `pragma: no cover` comments with required local rationale for new suppressions.

## Prioritized Next Cleanup Backlog

1. Review and split `apps/control-plane/src/dirt_control/api/gateway.py` gateway protocol routes, starting with catalog sync and command claim/result paths. Deliverable: thinner routes plus typed DTO ownership preserved end-to-end.
2. Review `apps/gateway/src/dirt_gateway/{commands,sync,cloud,outbox}.py` as one boundary-contract slice. Deliverable: reduce raw dict payload flow for command and projection payloads without adding compatibility adapters.
3. Review `apps/control-plane/src/dirt_control/api/browser.py` endpoint clusters. Deliverable: extract service-level operations for metric history, schedules, and command creation where route code owns too much database behavior.
4. Add focused behavior tests around `HumidifierLoopService.run` decision points, then extract pure decision helpers. Deliverable: shorter loop body without changing hardware behavior.
5. Review `apps/shared/src/dirt_shared/services/readings.py` for parameter-object or narrower-entry-point cleanup. Deliverable: reduce high-argument public/internal helpers where there is a real domain object.
6. Audit broad exception handlers in gateway command execution and hwd loop services. Deliverable: typed failure outcomes or structured logging rationale for each retained broad catch.
7. Re-run the radar after each cleanup slice and update this backlog only with changed counts and newly proven detector behavior.

## Milestone 3 Boundary

No cleanup passes, guardrail tests, or detector changes are part of this milestone. This document records the baseline review and feeds later Milestone 4 and Milestone 5 work.
