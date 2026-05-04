"""
INVARIANT TEST

This test is protected by default. Edit it only with explicit user permission.

Purpose: The sensor contract in ``dirt_shared.sensor_contract`` is the
single source of truth for which metrics each scoped device emits (wire) and
which it persists (consumer-facing). Three structural properties must hold:

1. Device and capability identifiers must be explicit, non-empty strings.

2. Each capability entry must be useful: emitted, persisted, or both.

3. Devices with non-empty emitted metrics must have at least one persisted
   metric. An emitting node whose output no downstream consumer is allowed to
   read is almost certainly a bug — either the contract was under-declared or
   the node is dead weight.

Behavioural correctness ("emitted payload + derivation yields every
persisted metric") is not enforced here — that lives in
``apps/hwd/tests/test_ingest_derivation.py`` where the ingest derivation
function can be imported and exercised directly.
"""

from __future__ import annotations

from dirt_shared.sensor_contract import (
    DEVICE_METRICS,
    emitted_metrics_for_device_id,
    persisted_capability_ids_for_device_id,
    persisted_metrics_for_device_id,
)


def test_device_contract_entries_are_well_formed() -> None:
    assert DEVICE_METRICS, "DEVICE_METRICS must declare at least one sensor device"

    for device_id, capabilities in DEVICE_METRICS.items():
        assert device_id, "DEVICE_METRICS contains an empty device_id"
        assert capabilities, f"{device_id} declares no capabilities"

        for capability_id, (metric_name, emitted, persisted) in capabilities.items():
            assert capability_id, f"{device_id} contains an empty capability_id"
            assert metric_name, f"{device_id}/{capability_id} has empty metric_name"
            assert emitted or persisted, (
                f"{device_id}/{capability_id} is neither emitted nor persisted"
            )


def test_sensor_contract_helpers_are_derived_from_device_contracts() -> None:
    for device_id, capabilities in DEVICE_METRICS.items():
        assert emitted_metrics_for_device_id(device_id) == {
            metric_name
            for metric_name, emitted, _persisted in capabilities.values()
            if emitted
        }
        assert persisted_metrics_for_device_id(device_id) == {
            metric_name
            for metric_name, _emitted, persisted in capabilities.values()
            if persisted
        }
        assert persisted_capability_ids_for_device_id(device_id) == {
            capability_id
            for capability_id, (
                _metric_name,
                _emitted,
                persisted,
            ) in capabilities.items()
            if persisted
        }


def test_emitting_devices_have_persisted_consumers() -> None:
    """A device that emits metrics must have at least one persisted metric."""
    offenders = {
        device_id
        for device_id in DEVICE_METRICS
        if emitted_metrics_for_device_id(device_id)
        and not persisted_metrics_for_device_id(device_id)
    }
    assert not offenders, (
        f"devices emit metrics but declare no persisted metrics: {sorted(offenders)} "
        "— either declare persisted metrics or drop the emitted entry"
    )
