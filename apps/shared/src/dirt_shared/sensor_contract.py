"""Declared contract for which metrics each scoped sensor device carries.

Single source of truth, split into two concepts so hardware swaps and
derivation changes can be reasoned about independently:

- ``DEVICE_METRICS`` — the canonical scoped contract, keyed by public
  ``device_id`` and then public ``capability_id``. Each capability declares
  its persisted ``metric_name`` and whether the ESP32 emits it on the wire.

- ``EMITTED_METRICS`` / ``PERSISTED_METRICS`` — legacy ``SensorLocation``
  maps derived from ``DEVICE_METRICS`` for firmware compatibility and older
  consumers. Do not add new metrics directly to these maps.

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

from dirt_shared.models.enums import SensorLocation

MetricContract = tuple[str, bool, bool]
DeviceContract = tuple[SensorLocation, dict[str, MetricContract]]

_LEGACY_LOCATION = 0
_CAPABILITIES = 1
_METRIC_NAME = 0
_EMITTED = 1
_PERSISTED = 2


DEVICE_METRICS: dict[str, DeviceContract] = {
    "fan-controller": (
        SensorLocation.TENT,
        {
            "temperature_c": ("temperature_c", True, False),
            "temperature_f": ("temperature_f", False, True),
            "humidity_pct": ("humidity_pct", True, True),
            "vpd_kpa": ("vpd_kpa", False, True),
            "dew_point_f": ("dew_point_f", False, True),
            "fan_duty_pct": ("fan_duty_pct", True, False),
        },
    ),
    "plant-a-node": (
        SensorLocation.PLANT_A,
        {
            "soil_moisture_raw": ("soil_moisture_raw", True, True),
        },
    ),
    "plant-b-node": (
        SensorLocation.PLANT_B,
        {
            "soil_moisture_raw": ("soil_moisture_raw", True, True),
        },
    ),
    "plant-c-node": (
        SensorLocation.PLANT_C,
        {
            "soil_moisture_raw": ("soil_moisture_raw", True, True),
        },
    ),
    "plant-d-node": (
        SensorLocation.PLANT_D,
        {
            "soil_moisture_raw": ("soil_moisture_raw", True, True),
        },
    ),
    "reservoir-node": (
        SensorLocation.RESERVOIR,
        {
            "reservoir_pressure_raw": ("reservoir_pressure_raw", True, True),
            "reservoir_in": ("reservoir_in", True, True),
        },
    ),
}

LEGACY_LOCATION_DEVICE_IDS: dict[SensorLocation, str] = {
    contract[_LEGACY_LOCATION]: device_id
    for device_id, contract in DEVICE_METRICS.items()
}

EMITTED_METRICS: dict[SensorLocation, frozenset[str]] = {
    contract[_LEGACY_LOCATION]: frozenset(
        metric[_METRIC_NAME]
        for metric in contract[_CAPABILITIES].values()
        if metric[_EMITTED]
    )
    for contract in DEVICE_METRICS.values()
}

PERSISTED_METRICS: dict[SensorLocation, frozenset[str]] = {
    contract[_LEGACY_LOCATION]: frozenset(
        metric[_METRIC_NAME]
        for metric in contract[_CAPABILITIES].values()
        if metric[_PERSISTED]
    )
    for contract in DEVICE_METRICS.values()
}


def legacy_location_for_device_id(device_id: str | None) -> str | None:
    if device_id is None:
        return None
    contract = DEVICE_METRICS.get(device_id)
    if contract is None:
        return None
    return contract[_LEGACY_LOCATION].value


def is_known_legacy_location(location_str: str | None) -> bool:
    if location_str is None:
        return False
    try:
        loc = SensorLocation(location_str)
    except ValueError:
        return False
    return loc in LEGACY_LOCATION_DEVICE_IDS


def emitted_metrics_for_device_id(device_id: str) -> frozenset[str]:
    contract = DEVICE_METRICS.get(device_id)
    if contract is None:
        return frozenset()
    return frozenset(
        metric[_METRIC_NAME]
        for metric in contract[_CAPABILITIES].values()
        if metric[_EMITTED]
    )


def persisted_metrics_for_device_id(device_id: str) -> frozenset[str]:
    contract = DEVICE_METRICS.get(device_id)
    if contract is None:
        return frozenset()
    return frozenset(
        metric[_METRIC_NAME]
        for metric in contract[_CAPABILITIES].values()
        if metric[_PERSISTED]
    )


def emitted_metrics(location: SensorLocation) -> frozenset[str]:
    return EMITTED_METRICS.get(location, frozenset())


def persisted_metrics(location: SensorLocation) -> frozenset[str]:
    return PERSISTED_METRICS.get(location, frozenset())


def missing_emitted(
    location_str: str, payload_metrics: Iterable[str]
) -> frozenset[str]:
    """Metrics the location is declared to emit but the payload omitted.

    Accepts a raw location string so callers at the ingest boundary don't
    have to import SensorLocation (keeps api modules off dirt_shared.models).
    Returns an empty set for unknown locations — opaque devices are
    permitted, not broken.
    """
    try:
        loc = SensorLocation(location_str)
    except ValueError:
        return frozenset()
    return emitted_metrics(loc) - set(payload_metrics)


def missing_emitted_for_device_id(
    device_id: str | None, payload_metrics: Iterable[str]
) -> frozenset[str]:
    if device_id is None:
        return frozenset()
    return emitted_metrics_for_device_id(device_id) - set(payload_metrics)
