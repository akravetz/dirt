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

## Test Value Rule

Tests should validate behavior, contracts, and architectural boundaries, not pin incidental configuration or seed data values.

Do not write tests that assert the current value of mutable configuration, database seed rows, schedule times, device names, plant labels, or other operator-owned data unless the value itself is the product contract. Those tests are configuration snapshots, not regression tests. They fail when the operator changes the system correctly, and they teach agents to preserve stale data instead of preserving behavior.

Every test should have a useful failure model. Before adding a test, ask: "If this fails, what product behavior, boundary contract, or safety property did we break?" If the honest answer is "the fixture was built differently" or "the implementation was refactored," the test is probably a change detector, not a behavior test.

Do not test fixture topology by itself. If a test creates a parent object, a child object, and then asserts that the child's foreign key equals the parent's ID, it usually proves only that the fixture was assembled the way the test assembled it. That is not useful unless the code under test is responsible for selecting, deriving, or validating that relationship. Prefer tests where behavior would be wrong if the relationship were wrong.

Treat configuration and seed data as inputs. Tests may create explicit fixtures with concrete values, but they should use those values to exercise behavior, not to declare today's operator choices permanent. When a seeded value matters operationally, verify it through migration review, a smoke query, or an acceptance checklist; do not turn it into an evergreen unit-test assertion unless the literal value is source-owned product behavior.

When database or config data is involved, test one of these instead:

- The code accepts and serializes whatever configured rows exist.
- A boundary payload includes required fields and rejects malformed shapes.
- A behavior changes correctly for an explicitly created test fixture.
- A safety invariant holds across values, preferably with a minimal fixture or parametrized examples.
- Selection behavior: given multiple valid configured targets, the system chooses the intended target and ignores unrelated ones.
- Gating behavior: disabled, stale, invalid, unauthorized, or out-of-scope inputs do not trigger side effects.
- Idempotency behavior: repeated processing of the same logical event does not duplicate side effects.
- Unit and range behavior: explicit units are honored and invalid ranges are rejected.

Bad:

- Assert exact current device IDs, schedule names, hostnames, times, labels, thresholds, or other mutable deployment values unless those values are declared constants in source and are the thing under test.
- Create related fixture rows, then only assert that their foreign-key IDs equal each other.
- Assert a private helper was called or an internal branch was reached when the externally visible behavior would catch the same bug.
- Snapshot a broad payload or generated file when the test only needs to protect a few boundary fields.

Good:

- Create two plausible targets and assert the system selects the one configured for the action.
- Create enabled and disabled inputs and assert only enabled inputs produce side effects.
- Process the same due event twice and assert the side effect occurs once.
- Assert required boundary fields are present, malformed shapes are rejected, and unknown owned-protocol fields fail loudly.
- Assert invalid units, negative durations, impossible ranges, or unknown control states fail at the model or database boundary.
- Assert a public API response, emitted event, database fact, or command payload has the required behavior while allowing unrelated fields to vary.

If a test breaks because normal config or seed data changed, first ask whether the test is pinning incidental data. Prefer deleting or rewriting the test over updating expected literals.

## Abstraction Test

Before adding an abstraction, ask:

Does this make the current implementation easier to understand and remove meaningful duplication around a real shared responsibility?

Or does it make a possible future easier at the cost of today's clarity?

Only do the former. When in doubt, choose direct explicit code and data first. Add abstraction later when duplication or domain pressure is real.

## Examples

Good:

- Keep `ScheduledKasaActuatorService` lights-only when schedules only own light plugs.
- Let `ClimateControllerService` own heater targets when heat is part of coupled VPD/RH/temperature control.
- Rename tests and imports to the new canonical service in the same PR.

Bad:

- Keep `LightsLoopService` as a thin wrapper after it no longer only controls lights.
- Encode climate heat as a fixed heater schedule after `ClimateControllerService` owns heat.
- Add adapter layers or compatibility aliases only to avoid updating owned callers.
