"""
INVARIANT TEST — HUMAN-OWNED

This test is protected and MUST NOT be modified by the agent. If it fails,
fix the sensor contract (or the code that diverges from it); never edit
this file.

Purpose: The sensor contract in ``dirt_shared.sensor_contract`` is the
single source of truth for which metrics each location emits (wire) and
which it persists (consumer-facing). Two structural properties must hold:

1. Every location declared in ``EMITTED_METRICS`` must also appear in
   ``PERSISTED_METRICS``, and vice versa. A typo or a half-finished node
   addition should not silently land in one map but not the other.

2. Locations with a non-empty ``EMITTED_METRICS`` entry must have a
   non-empty ``PERSISTED_METRICS`` entry. An emitting node whose output
   no downstream consumer is allowed to read is almost certainly a bug —
   either the contract was under-declared or the node is dead weight.

Behavioural correctness ("emitted payload + derivation yields every
persisted metric") is not enforced here — that lives in
``apps/hwd/tests/test_ingest_derivation.py`` where the ingest derivation
function can be imported and exercised directly.
"""

from __future__ import annotations

from dirt_shared.sensor_contract import EMITTED_METRICS, PERSISTED_METRICS


def test_emitted_and_persisted_declare_same_locations():
    emitted_keys = set(EMITTED_METRICS.keys())
    persisted_keys = set(PERSISTED_METRICS.keys())
    assert emitted_keys == persisted_keys, (
        "EMITTED_METRICS and PERSISTED_METRICS must declare the same set of "
        f"locations. emitted_only={sorted(k.value for k in emitted_keys - persisted_keys)} "
        f"persisted_only={sorted(k.value for k in persisted_keys - emitted_keys)}"
    )


def test_emitting_locations_have_persisted_consumers():
    """A node that emits metrics must have at least one persisted metric
    declared — otherwise no consumer is allowed to read what it emits."""
    offenders = {
        loc.value
        for loc, emitted in EMITTED_METRICS.items()
        if emitted and not PERSISTED_METRICS.get(loc)
    }
    assert not offenders, (
        f"locations emit metrics but declare no persisted metrics: {sorted(offenders)} "
        "— either declare persisted metrics or drop the emitted entry"
    )
