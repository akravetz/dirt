"""Declared contract for which metrics each sensor location carries.

Single source of truth, split into two concepts so hardware swaps and
derivation changes can be reasoned about independently:

- ``EMITTED_METRICS`` — the wire contract. What the device physically puts
  in the ``metrics`` dict at ``POST /api/ingest/sensors``. The ingest path
  logs a warning when a known location's payload is missing a key declared
  here. Update this set in the same PR as any firmware change that
  adds/removes a metric.

- ``PERSISTED_METRICS`` — the consumer contract. What downstream code
  (daily-report validation, metric-freshness watchdog, voice tools, charts)
  is guaranteed to find as queryable rows in the DB. Some persisted metrics
  are server-derived — ``_augment_temp_rh_metrics`` synthesises
  ``temperature_f`` / ``vpd_kpa`` / ``dew_point_f`` from ``temperature_c`` +
  ``humidity_pct``.

The two sets are *not* required to be subsets of each other. Raw inputs
(``temperature_c``) can be emitted without being a first-class consumer
metric; derived values (``vpd_kpa``) can be consumer-facing without being
on the wire. The behavioural guard is in
``apps/hwd/tests/test_ingest_derivation.py``: for every location, a payload
of emitted metrics must, after ingest derivation, yield every persisted
metric for that location.
"""

from __future__ import annotations

from collections.abc import Iterable

from dirt_shared.models.enums import SensorLocation

DeviceMetricContract = tuple[SensorLocation, frozenset[str], frozenset[str]]


DEVICE_METRICS: dict[str, DeviceMetricContract] = {
    "fan-controller": (
        SensorLocation.TENT,
        frozenset({"temperature_c", "humidity_pct"}),
        frozenset(
            {
                "temperature_f",
                "humidity_pct",
                "vpd_kpa",
                "dew_point_f",
            }
        ),
    ),
    "plant-a-node": (
        SensorLocation.PLANT_A,
        frozenset({"soil_moisture_raw"}),
        frozenset({"soil_moisture_raw"}),
    ),
    "plant-b-node": (
        SensorLocation.PLANT_B,
        frozenset({"soil_moisture_raw"}),
        frozenset({"soil_moisture_raw"}),
    ),
    "plant-c-node": (
        SensorLocation.PLANT_C,
        frozenset({"soil_moisture_raw"}),
        frozenset({"soil_moisture_raw"}),
    ),
    "plant-d-node": (
        SensorLocation.PLANT_D,
        frozenset({"soil_moisture_raw"}),
        frozenset({"soil_moisture_raw"}),
    ),
    "reservoir-node": (
        SensorLocation.RESERVOIR,
        frozenset({"reservoir_pressure_raw", "reservoir_in"}),
        frozenset({"reservoir_pressure_raw", "reservoir_in"}),
    ),
}

LEGACY_LOCATION_DEVICE_IDS: dict[SensorLocation, str] = {
    contract[0]: device_id for device_id, contract in DEVICE_METRICS.items()
}

EMITTED_METRICS: dict[SensorLocation, frozenset[str]] = {
    contract[0]: contract[1] for contract in DEVICE_METRICS.values()
}

PERSISTED_METRICS: dict[SensorLocation, frozenset[str]] = {
    contract[0]: contract[2] for contract in DEVICE_METRICS.values()
}


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
