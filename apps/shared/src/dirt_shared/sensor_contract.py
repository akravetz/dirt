"""Code-owned sensor derivation contract and typed capability metadata.

``DEVICE_METRICS`` remains the code-owned derivation guard for legacy devices:
given a set of emitted wire metrics, ingest tests prove that local derivation
still yields the persisted metrics those code paths expect.

Durable device/capability inventory and operational freshness policy belong in
the database. Consumers that need those durable fields should read
``capability.metadata`` through ``CapabilityMetadata`` rather than inspecting
raw JSON dictionaries.

For ``DEVICE_METRICS``, emitted metrics are what the device physically puts in
the ``metrics`` dict at ``POST /api/ingest/sensors``. Persisted metrics are
legacy consumer-facing rows that may be server-derived —
``_augment_temp_rh_metrics`` synthesises ``temperature_f`` / ``vpd_kpa`` /
``dew_point_f`` from ``temperature_c`` + ``humidity_pct``.

The two sets are *not* required to be subsets of each other. Raw inputs
(``temperature_c``) can be emitted without being a first-class consumer
metric; derived values (``vpd_kpa``) can be consumer-facing without being
on the wire. The behavioural guard is in
``apps/hwd/tests/test_ingest_derivation.py``: for every device, a payload
of emitted metrics must, after ingest derivation, yield every persisted
metric for that device.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict


class CapabilityMetadata(BaseModel):
    """Typed fields in capability.metadata that production code reads."""

    model_config = ConfigDict(extra="allow", strict=True)

    expected_wire_metric: bool = False
    freshness_required: bool = False
    sensor_model: str | None = None
    modbus_address: str | None = None
    experimental: bool = False
    experimental_note: str | None = None


def capability_metadata_from_json(
    metadata: Mapping[str, Any] | None,
) -> CapabilityMetadata:
    return CapabilityMetadata.model_validate(metadata or {})


MetricContract = tuple[str, bool, bool]
DeviceContract = dict[str, MetricContract]


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
        "fan_pct": ("fan_pct", True, True),
    },
    "breeding-env-node": {
        "temperature_c": ("temperature_c", True, False),
        "temperature_f": ("temperature_f", False, True),
        "humidity_pct": ("humidity_pct", True, True),
        "vpd_kpa": ("vpd_kpa", False, True),
        "dew_point_f": ("dew_point_f", False, True),
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
        "reservoir_ph_raw": ("reservoir_ph_raw", True, True),
        "reservoir_ph_voltage": ("reservoir_ph_voltage", True, True),
        "reservoir_ph": ("reservoir_ph", True, True),
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
