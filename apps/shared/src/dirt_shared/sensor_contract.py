"""Declared contract for which metrics each scoped sensor device carries.

Single source of truth, split into two concepts so hardware swaps and
derivation changes can be reasoned about independently:

- ``DEVICE_METRICS`` — the canonical scoped contract, keyed by public
  ``device_id`` and then public ``capability_id``. Each capability declares
  its persisted ``metric_name`` and whether the ESP32 emits it on the wire.

Emitted metrics are what the device physically puts in the ``metrics`` dict
at ``POST /api/ingest/sensors``. The ingest path logs a warning when a known
device's payload is missing a key declared here. Persisted metrics are what
downstream code (daily-report validation, metric-freshness watchdog, voice
tools, charts) is guaranteed to find as queryable rows in the DB. Some
persisted metrics are server-derived — ``_augment_temp_rh_metrics`` synthesises
  ``temperature_f`` / ``vpd_kpa`` / ``dew_point_f`` from ``temperature_c`` +
  ``humidity_pct``.

The two sets are *not* required to be subsets of each other. Raw inputs
(``temperature_c``) can be emitted without being a first-class consumer
metric; derived values (``vpd_kpa``) can be consumer-facing without being
on the wire. The behavioural guard is in
``apps/hwd/tests/test_ingest_derivation.py``: for every device, a payload
of emitted metrics must, after ingest derivation, yield every persisted
metric for that device.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

MetricContract = tuple[str, bool, bool]
DeviceContract = dict[str, MetricContract]


class ContractLocation(StrEnum):
    TENT = "tent"
    PLANT_A = "plant-a"
    PLANT_B = "plant-b"
    PLANT_C = "plant-c"
    PLANT_D = "plant-d"
    RESERVOIR = "reservoir"


_METRIC_NAME = 0
_EMITTED = 1
_PERSISTED = 2


DEVICE_METRICS: dict[str, DeviceContract] = {
    "fan-controller": {
        "temperature_c": ("temperature_c", True, False),
        "temperature_f": ("temperature_f", False, True),
        "humidity_pct": ("humidity_pct", True, True),
        "vpd_kpa": ("vpd_kpa", False, True),
        "dew_point_f": ("dew_point_f", False, True),
        "fan_duty_pct": ("fan_duty_pct", True, False),
    },
    "plant-a-node": {
        "soil_moisture_raw": ("soil_moisture_raw", True, True),
    },
    "plant-b-node": {
        "soil_moisture_raw": ("soil_moisture_raw", True, True),
    },
    "plant-c-node": {
        "soil_moisture_raw": ("soil_moisture_raw", True, True),
    },
    "plant-d-node": {
        "soil_moisture_raw": ("soil_moisture_raw", True, True),
    },
    "reservoir-node": {
        "reservoir_pressure_raw": ("reservoir_pressure_raw", True, True),
        "reservoir_in": ("reservoir_in", True, True),
    },
}


def emitted_metrics_for_device_id(device_id: str) -> frozenset[str]:
    contract = DEVICE_METRICS.get(device_id)
    if contract is None:
        return frozenset()
    return frozenset(
        metric[_METRIC_NAME] for metric in contract.values() if metric[_EMITTED]
    )


def persisted_metrics_for_device_id(device_id: str) -> frozenset[str]:
    contract = DEVICE_METRICS.get(device_id)
    if contract is None:
        return frozenset()
    return frozenset(
        metric[_METRIC_NAME] for metric in contract.values() if metric[_PERSISTED]
    )


def persisted_capability_ids_for_device_id(device_id: str) -> frozenset[str]:
    contract = DEVICE_METRICS.get(device_id)
    if contract is None:
        return frozenset()
    return frozenset(
        capability_id
        for capability_id, metric in contract.items()
        if metric[_PERSISTED]
    )


def missing_emitted_for_device_id(
    device_id: str | None, payload_metrics: Iterable[str]
) -> frozenset[str]:
    if device_id is None:
        return frozenset()
    return emitted_metrics_for_device_id(device_id) - set(payload_metrics)


# Compatibility exports kept for the human-owned sensor-contract invariant.
# Production code should use the device/capability helpers above.
_INVARIANT_DEVICE_BY_LOCATION: dict[ContractLocation, str] = {
    ContractLocation.TENT: "fan-controller",
    ContractLocation.PLANT_A: "plant-a-node",
    ContractLocation.PLANT_B: "plant-b-node",
    ContractLocation.PLANT_C: "plant-c-node",
    ContractLocation.PLANT_D: "plant-d-node",
    ContractLocation.RESERVOIR: "reservoir-node",
}
EMITTED_METRICS: dict[ContractLocation, frozenset[str]] = {
    location: frozenset(
        metric[_METRIC_NAME]
        for metric in DEVICE_METRICS[device_id].values()
        if metric[_EMITTED]
    )
    for location, device_id in _INVARIANT_DEVICE_BY_LOCATION.items()
}
PERSISTED_METRICS: dict[ContractLocation, frozenset[str]] = {
    location: frozenset(
        metric[_METRIC_NAME]
        for metric in DEVICE_METRICS[device_id].values()
        if metric[_PERSISTED]
    )
    for location, device_id in _INVARIANT_DEVICE_BY_LOCATION.items()
}
