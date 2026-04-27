"""Behavioural guard for the sensor contract.

For every declared location, a payload containing exactly the metrics in
``EMITTED_METRICS[loc]`` must, after the ingest derivation step, yield every
metric in ``PERSISTED_METRICS[loc]``. Catches: adding a derived metric to
the consumer contract without wiring the derivation; renaming a raw input
without updating the derivation; a future node type whose derivation
function isn't hooked up.
"""

from __future__ import annotations

import logging

import pytest

from dirt_hwd.api.ingest import _augment_temp_rh_metrics, _warn_on_emitted_drift
from dirt_shared.models.enums import SensorLocation
from dirt_shared.sensor_contract import EMITTED_METRICS, PERSISTED_METRICS

# Plausible readings for every metric that could appear on any emitted set.
# Populated once so adding a new raw metric forces a conscious test update.
_PLAUSIBLE: dict[str, float] = {
    "temperature_c": 24.0,
    "humidity_pct": 55.0,
    "soil_moisture_raw": 1800.0,
    "reservoir_pressure_raw": 22000.0,
    "reservoir_in": 12.0,
}


@pytest.mark.parametrize("location", list(EMITTED_METRICS.keys()))
def test_emitted_payload_yields_all_persisted_metrics(
    location: SensorLocation,
) -> None:
    emitted = EMITTED_METRICS[location]
    assert emitted <= _PLAUSIBLE.keys(), (
        f"test fixture _PLAUSIBLE missing values for {sorted(emitted - _PLAUSIBLE.keys())} — "
        "add plausible readings when declaring a new emitted metric"
    )
    payload = {m: _PLAUSIBLE[m] for m in emitted}
    derived = _augment_temp_rh_metrics(payload)
    missing = PERSISTED_METRICS[location] - derived.keys()
    assert not missing, (
        f"{location.value}: ingest derivation did not produce {sorted(missing)} "
        f"from emitted {sorted(emitted)} — wire up the derivation or shrink PERSISTED_METRICS"
    )


def test_warn_on_emitted_drift_logs_when_metric_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Firmware-contract drift surfaces as a structured warning at ingest time."""
    caplog.set_level(logging.WARNING, logger="dirt_hwd.api.ingest")
    # Tent emits temperature_c + humidity_pct; drop one.
    _warn_on_emitted_drift("tent", {"humidity_pct": 55.0})
    assert any(
        "missing expected metrics" in r.message and "temperature_c" in r.message
        for r in caplog.records
    ), caplog.text


def test_warn_on_emitted_drift_silent_when_complete(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="dirt_hwd.api.ingest")
    _warn_on_emitted_drift("tent", {"temperature_c": 24.0, "humidity_pct": 55.0})
    assert not caplog.records


def test_warn_on_emitted_drift_silent_for_unknown_location(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown locations are not in EMITTED_METRICS; treat as opaque, not broken."""
    caplog.set_level(logging.WARNING, logger="dirt_hwd.api.ingest")
    _warn_on_emitted_drift("not-a-real-location", {})
    assert not caplog.records
