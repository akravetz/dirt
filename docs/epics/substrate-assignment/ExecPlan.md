# Make substrate probe assignment safe and discoverable

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

An operator can move an RS485 substrate probe to another plant by running one supported command instead of editing PostgreSQL rows. The local gateway then sends an authoritative plant-metric-stream catalog so the hosted control plane activates the new mapping and deactivates stale mappings automatically. Future coding agents discover this workflow from a short phrase-triggered pointer in the root `AGENTS.md`, with full command details loaded from `docs/commands.md` only when relevant.

## Progress

- [x] (2026-07-21 06:40Z) Diagnosed the stale hosted mapping and selected the authoritative snapshot design.
- [x] (2026-07-21 06:42Z) Reviewed primary guidance on AGENTS.md and progressive disclosure for autonomous agents.
- [x] (2026-07-21 06:55Z) Implemented and tested the transactional substrate assignment service and CLI.
- [x] (2026-07-21 06:59Z) Implemented and tested gateway collection of inactive/unlocated mappings.
- [x] (2026-07-21 07:02Z) Implemented and tested hosted reconciliation of omitted mappings.
- [x] (2026-07-21 07:05Z) Added agent discoverability and operator command documentation.
- [x] (2026-07-21 07:14Z) Ran focused suites, invariants, formatting, lint, live CLI listing, and diff validation.

## Surprises & Discoveries

- Observation: `GatewayLocalServiceBundle._collect_plant_metric_streams()` does not filter `PlantMetricStream.is_active`, but its inner join to the current `PlantLocationHistory` silently removes mappings for plants without a current location.
  Evidence: locally deactivated SBBS mappings did not appear in the catalog, leaving their hosted rows active.

- Observation: the hosted catalog handler only upserts `CloudPlantMetricStream` rows.
  Evidence: an absent mapping retained its prior `is_active=true` value until manually corrected.

- Observation: pytest processes in the same worktree share one template database name and cannot safely build that template concurrently.
  Evidence: parallel shared/gateway/control-plane runs reset the template connection; the same suites passed when run sequentially.

- Observation: assigning metric streams without moving the logical device leaves non-moisture latest metrics and rollups under the probe's former tent.
  Evidence: MB-R1-008 was in source tent 2 while `plant-d-substrate-node` temperature, EC, pH, and all 5-minute rollups remained in source tent 1, so plant-detail queries correctly returned no matching history.

## Decision Log

- Decision: Treat `CatalogRequest.plant_metric_streams` as an authoritative full-site snapshot and mark omitted hosted stream rows inactive.
  Rationale: omission must converge cloud state even if a local tombstone is deleted or a collector changes scope. Marking inactive preserves history while preventing stale UI ownership.
  Date/Author: 2026-07-21 / Codex

- Decision: Scope local stream collection through the capability-owning device's `site_id`, not the plant's current location.
  Rationale: a stream remains site-owned and sync-relevant after its former plant leaves a tent; the current-location join was used only for ordering and made deactivation lossy.
  Date/Author: 2026-07-21 / Codex

- Decision: Provide `scripts/substrate assign <bus-id> <plant-key>` as the operator workflow.
  Rationale: physical probe moves are local operations against the local source of truth. A small transactional CLI is simpler than a hosted command workflow and can validate the whole four-capability assignment atomically.
  Date/Author: 2026-07-21 / Codex

- Decision: Probe assignment also moves the logical device to the target plant's current site/tent and clears its zone.
  Rationale: device placement owns metric and rollup source scope. Updating only `plant_metric_stream` creates a split-brain mapping where the plant and its telemetry live in different tents.
  Date/Author: 2026-07-21 / Codex

- Decision: Put a compact natural-language trigger in root `AGENTS.md` and detailed syntax in `docs/commands.md`.
  Rationale: AGENTS.md is the predictable always-loaded instruction surface, while just-in-time linked detail conserves agent context and follows progressive disclosure guidance.
  Date/Author: 2026-07-21 / Codex

## Outcomes & Retrospective

Operators can now run `scripts/substrate list` and `scripts/substrate assign <bus-id> <plant-key>` instead of editing mapping rows. The command validates the probe, canonical current plant, same-site ownership, and exact four-capability set before changing anything; it deactivates prior mappings and activates the target in one transaction and is idempotent.

Gateway catalog collection now scopes plant metric streams through the capability-owning device's site and includes inactive mappings even when the former plant has no current location. The hosted catalog treats that list as authoritative and marks omitted active stream identities inactive. The current live listing correctly reports `0x02 -> ESP-R1-002`, `0x03 -> MB-R1-008`, and `0x04 -> SD-F5-001`.

Validation passed: 9 shared assignment tests, 56 gateway tests, 62 control-plane tests, 51 human-owned invariants, full Ruff check, full Ruff format check, and `git diff --check`.

## Context and Orientation

`plant_metric_stream` is the local canonical mapping between a plant row and a device capability. Each DFRobot SEN0604 logical probe owns four enabled capabilities: `soil_moisture_pct`, `substrate_temp_c`, `substrate_ec_us_cm`, and `substrate_ph`. `apps/gateway/src/dirt_gateway/local.py` converts these mappings to typed `CatalogPlantMetricStream` DTOs from `apps/shared/src/dirt_shared/cloud_contract.py`. `apps/control-plane/src/dirt_control/api/gateway.py` stores the DTOs as `CloudPlantMetricStream` rows.

The operator-facing entry point will be `scripts/substrate`, backed by a small service under `apps/shared/src/dirt_shared/services/`. The service validates a Modbus address and a canonical plant key, finds the logical RS485 device and its four required capabilities, deactivates their prior mappings, and upserts active mappings for the target plant in one transaction.

## Plan of Work

Milestone 1 adds the assignment service, a thin CLI, and focused tests. The command accepts canonical hexadecimal or decimal Modbus addresses, validates a unique enabled RS485 device and current plant, requires the four expected capabilities, performs the reassignment transaction, and prints the canonical result.

Milestone 2 fixes catalog convergence. The gateway collector emits active and inactive mappings by joining through `Device.site_id`. The control plane builds the incoming structured identity set, upserts it, and marks any active site-owned cloud stream absent from the snapshot inactive.

Milestone 3 makes the workflow discoverable. Root `AGENTS.md` receives a short trigger covering phrases such as move, reassign, or associate a soil/substrate sensor with a plant. `docs/commands.md` documents listing and assignment commands, validation, and the no-direct-SQL rule.

## Concrete Steps

From `/home/akcom/code/dirt`:

    uv run pytest apps/shared/tests/test_substrate_assignment.py -q
    uv run pytest apps/gateway/tests/test_sync.py -q
    uv run pytest apps/control-plane/tests/test_api.py -q
    scripts/substrate list
    scripts/substrate assign 0x02 ESP-R1-002
    uv run pytest apps/tests/invariants/ -q
    uv run ruff check

The live assignment acceptance command is idempotent when the probe is already assigned to the requested plant.

## Validation and Acceptance

Tests must prove that a reassignment deactivates former mappings, activates exactly four expected target mappings, rejects unknown probes/plants or incomplete capability sets, and is safe to repeat. Gateway tests must prove an inactive mapping for a plant without a current location is still projected. Control-plane tests must prove a second catalog snapshot that omits a previously active mapping leaves the row present but inactive.

The human-visible acceptance behavior is that `scripts/substrate list` shows one active plant per probe and `scripts/substrate assign 0x02 ESP-R1-002` reports the four assigned metrics without direct SQL.

## Idempotence and Recovery

Assignment runs in one database transaction; validation errors occur before commit. Re-running the same assignment updates the same unique plant/capability rows and leaves the result unchanged. If cloud delivery fails, the gateway outbox retries the authoritative catalog. Hosted reconciliation only changes active rows omitted from the incoming site snapshot and is safe on repeated payloads.

## Artifacts and Notes

Research used to shape discoverability:

- The AGENTS.md open format describes root and nested `AGENTS.md` files as predictable agent instruction surfaces: https://agents.md/
- Anthropic's context-engineering guidance recommends lightweight identifiers and just-in-time retrieval for progressive disclosure: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic's Agent Skills guidance uses concise trigger metadata as the first disclosure level and detailed procedural content as the second: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills

Acceptance transcript:

    $ scripts/substrate list
    0x02  ESP-R1-002  (plant-a-substrate-node)
    0x03  MB-R1-008  (plant-d-substrate-node)
    0x04  SD-F5-001  (plant-c-substrate-node)

    9 passed in 2.57s
    56 passed in 35.19s
    62 passed in 18.78s
    51 passed in 3.62s

## Interfaces and Dependencies

The final interfaces are:

- `scripts/substrate list`
- `scripts/substrate assign <bus-id> <plant-key>`
- An internal async substrate assignment function accepting an `AsyncEngine`, bus ID, and plant key.
- Existing `CatalogRequest.plant_metric_streams`; no wire-shape change is required.
- Existing PostgreSQL and SQLModel dependencies; no new package is required.

## Revision Notes

- 2026-07-21: Initial plan written after reproducing stale hosted mappings and reviewing agent documentation guidance.
- 2026-07-21: Completed implementation and recorded validation plus the same-worktree pytest concurrency constraint.
