# Simple Clean Architecture

Use this rule when designing or implementing source-owned code, writing ExecPlans, reviewing abstractions, or choosing between a direct design and a more flexible design.

## Rule

Build the simplest truthful model of the domain, then keep the codebase honest by deleting misleading old structure.

Clean architecture does not mean more architecture. It means the code's structure matches the real domain with the least machinery needed. Simplicity does not mean ad hoc or under-modeled. It means no clever indirection until the domain actually demands it.

Optimize repo-wide for:

- Clean architecture.
- Clean code.
- No dead code.
- No thin wrappers.
- Simplicity.
- Direct, inspectable data and behavior.

## How to Apply It

Model real concepts, not convenient aliases. Do not collapse different domain concepts into one misleading type just because it is easier to reuse the current code. A heat pad is not a light. A camera is not a sensor reading. A hosted command is not a local hardware call.

Share only the real shared responsibility. If two concepts use the same mechanical workflow, extract that workflow behind a name that describes the workflow. Lights and heat pads can share scheduled Kasa power reconciliation because that is the real common behavior. They should not share a light-specific service name.

Prefer explicit data over derived magic. If a user may reasonably tune a value independently, store it directly. Avoid hidden coupling such as "inverse of another schedule" when an explicit `starts_local` / `ends_local` row is clearer, easier to inspect, and easier to change.

Choose direct cutover for source-owned code. When the right abstraction is clear, replace misleading names, update owned call sites and tests, and remove obsolete paths in the same change. Do not keep durable wrappers, aliases, compatibility classes, duplicated implementations, feature flags, or transitional branches merely to reduce implementation churn.

Use compatibility only for a real boundary. Compatibility and migration safety are exceptional. Add compatibility glue only when there is a concrete external contract, live data migration, staged deploy requirement, or user-stated rollback need. If a short-lived wrapper or transition path is necessary, it must be removed before the same PR or ExecPlan is complete.

Move tests to the canonical contract. Agent-owned tests should validate the new source of truth. Do not preserve old names or old shapes in tests unless they are public contracts that still exist.

## Abstraction Test

Before adding an abstraction, ask:

Does this make the current implementation easier to understand and remove meaningful duplication around a real shared responsibility?

Or does it make a possible future easier at the cost of today's clarity?

Only do the former. When in doubt, choose direct explicit code and data first. Add abstraction later when duplication or domain pressure is real.

## Examples

Good:

- Replace `LightsLoopService` with `ScheduledKasaActuatorService` when the same loop controls both light plugs and heat-pad plugs.
- Give a heat pad its own `kind='heat_pad'` schedule with explicit `starts_local` and `ends_local`.
- Rename tests and imports to the new canonical service in the same PR.

Bad:

- Keep `LightsLoopService` as a thin wrapper after it no longer only controls lights.
- Store a heat-pad schedule as "inverse of lights" when explicit start/end times are enough.
- Add adapter layers or compatibility aliases only to avoid updating owned callers.

