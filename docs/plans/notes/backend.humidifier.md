# backend.humidifier cluster — generator notes

Cluster of two BE features (`backend.humidifier.state` +
`backend.humidifier.history`) landed over two agent runs plus an
orchestrator-side close-out because both agents hit the known
`/simplify` handoff exit-bug.

## Features

### backend.humidifier.state

- `GET /api/humidifier/state` returning on/off + duration since last
  transition + cycles_24h.
- Thin wrapper over `HumidifierStateService.get_state`.
- Cold-cluster handling in the router: contract requires non-null
  response fields even when the service returns `None` for
  "never-transitioned" state; the adapter returns non-null defaults
  rather than muddying the service's semantics (keeping the "no data"
  vs "data shows 0s duration" distinction clean at the service
  boundary).
- Invariant: `GET /api/humidifier/state` removed from
  `expected_missing` in `contract_status.json`.
- Tests: `apps/web/tests/test_humidifier_state_endpoint.py`.

### backend.humidifier.history

- `GET /api/humidifier/history?range=` returning the on/off transition
  list over the range.
- Thin wrapper over `HumidifierStateService.get_history`.
- Validates `range` against the contract's allowed values (1h / 24h /
  7d), 4xx on unknown.
- Invariant: `GET /api/humidifier/history` removed from
  `expected_missing`.
- Tests: `apps/web/tests/test_humidifier_history_endpoint.py`.

## Cluster simplify pass

Post-feat, `/simplify` flagged a single-use `_tent_id` helper in each
endpoint test file — inlined the SELECT + collapsed to one session
context per `_seed_humidifier_readings` call (saves a round-trip).
Applied verbatim.

## Final test state

- Invariants: 96 passed (new tests parametrize 2 additional rows;
  total matches pre-cluster baseline plus two new row instances).
- `apps/web/tests/`: 107 passed including the 2 new endpoint test
  files (6 tests total for this cluster).

## Harness observations

Both agent runs (original BE-1 + continuation) exited prematurely
after the `/simplify` skill printed "returning control." The
pre-cluster generator-prompt hardening ("DO NOT yield until ALL work
is complete" + explicit cluster protocol) did NOT prevent the exit.
This is a robust model-behavior anchor that the current prompt
architecture can't override.

**Decision going forward**: `/simplify` moves to the orchestrator's
context post-cherry-pick. Generator cluster prompts stop prescribing
it. Orchestrator runs `/simplify` as its own turn on main after the
cluster lands and commits the result as `chore(<cluster>): simplify
pass` directly on main.

## Suggested next

Orchestrator cherry-picks 4 commits (2 feats + 1 simplify + this
NOTES) onto main, flips both features' status to done, kicks off the
next BE cluster (`plants` — list + detail + moisture) under the
revised cluster protocol that omits agent-side /simplify.
