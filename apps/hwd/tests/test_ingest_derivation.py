"""Behavioural guard for the sensor contract.

For every declared device, a payload containing exactly the metrics it emits
must, after the ingest derivation step, yield every metric it persists.
Catches: adding a derived metric to
the consumer contract without wiring the derivation; renaming a raw input
without updating the derivation; a future node type whose derivation
function isn't hooked up.
"""

from __future__ import annotations

import logging

import pytest

from dirt_hwd.api.ingest import _augment_temp_rh_metrics, _warn_on_emitted_drift
from dirt_shared.sensor_contract import (
    DEVICE_METRICS,
    emitted_metrics_for_device_id,
    persisted_metrics_for_device_id,
)

# Plausible readings for every metric that could appear on any emitted set.
# Populated once so adding a new raw metric forces a conscious test update.
_PLAUSIBLE: dict[str, float] = {
    "temperature_c": 24.0,
    "humidity_pct": 55.0,
    "fan_duty_pct": 30.0,
    "soil_moisture_raw": 1800.0,
    "reservoir_pressure_raw": 22000.0,
    "reservoir_in": 12.0,
}


@pytest.mark.parametrize("device_id", list(DEVICE_METRICS.keys()))
def test_emitted_payload_yields_all_persisted_metrics(
    device_id: str,
) -> None:
    emitted = emitted_metrics_for_device_id(device_id)
    persisted = persisted_metrics_for_device_id(device_id)
    assert emitted <= _PLAUSIBLE.keys(), (
        f"test fixture _PLAUSIBLE missing values for {sorted(emitted - _PLAUSIBLE.keys())} — "
        "add plausible readings when declaring a new emitted metric"
    )
    payload = {m: _PLAUSIBLE[m] for m in emitted}
    derived = _augment_temp_rh_metrics(payload)
    missing = persisted - derived.keys()
    assert not missing, (
        f"{device_id}: ingest derivation did not produce {sorted(missing)} "
        f"from emitted {sorted(emitted)} — wire up the derivation or shrink DEVICE_METRICS"
    )


def test_warn_on_emitted_drift_logs_when_metric_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Firmware-contract drift surfaces as a structured warning at ingest time."""
    caplog.set_level(logging.WARNING, logger="dirt_hwd.api.ingest")
    # Tent emits temperature_c + humidity_pct; drop one.
    _warn_on_emitted_drift("fan-controller", {"humidity_pct": 55.0})
    assert any(
        "missing expected metrics" in r.message and "temperature_c" in r.message
        for r in caplog.records
    ), caplog.text


def test_warn_on_emitted_drift_silent_when_complete(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="dirt_hwd.api.ingest")
    _warn_on_emitted_drift(
        "fan-controller",
        {"temperature_c": 24.0, "humidity_pct": 55.0, "fan_duty_pct": 30.0},
    )
    assert not caplog.records


def test_warn_on_emitted_drift_silent_for_unknown_device(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown devices are not in the contract; treat as opaque, not broken."""
    caplog.set_level(logging.WARNING, logger="dirt_hwd.api.ingest")
    _warn_on_emitted_drift("not-a-real-device", {})
    assert not caplog.records
