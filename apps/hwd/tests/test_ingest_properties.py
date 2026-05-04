"""Hypothesis property tests for the dirt-hwd ingest payload.

The wire contract with ESP32 plant nodes is the
``dirt_hwd.api.ingest.IngestPayload`` Pydantic model. Two properties
pin its contract so an agent can't narrow it by accident:

1. Any payload inside the declared bounds (device_id 1..64 chars,
   metrics is a dict[str, float], optional fields nullable) parses
   cleanly — no ValidationError.

2. Any payload breaking the bounds (empty device_id, device_id > 64
   chars) is rejected. This is the negative side of the first property
   and catches the common regression where someone "relaxes" the
   model to get a test to pass.

The tests never hit the DB — they exercise only the Pydantic model,
which is the layer whose contract matters for the ESP32 firmware that
was tested against it six months ago.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from dirt_hwd.api.ingest import IngestPayload

# Text in the 1..64-char range. Exclude control chars so hypothesis
# doesn't waste effort on bytes that no ESP32 would ever send.
_DEVICE_ID = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc")),
    min_size=1,
    max_size=64,
)
_METRIC_NAME = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc")),
    min_size=1,
    max_size=32,
)
_METRIC_VALUE = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)
_METRICS = st.dictionaries(_METRIC_NAME, _METRIC_VALUE, max_size=8)


@given(
    device_id=_DEVICE_ID,
    metrics=_METRICS,
    source=st.sampled_from(["esp32", "manual", "firmware-test"]),
    ip=st.none() | st.from_regex(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),
    firmware_version=st.none() | st.text(max_size=32),
    uptime_ms=st.none() | st.integers(min_value=0, max_value=2**32 - 1),
)
def test_valid_payload_parses(
    device_id: str,
    metrics: dict[str, float],
    source: str,
    ip: str | None,
    firmware_version: str | None,
    uptime_ms: int | None,
) -> None:
    """Any payload inside the declared bounds parses to an IngestPayload."""
    payload = IngestPayload(
        device_id=device_id,
        metrics=metrics,
        source=source,
        ip=ip,
        firmware_version=firmware_version,
        uptime_ms=uptime_ms,
    )
    assert payload.device_id == device_id
    assert payload.metrics == metrics
    assert payload.source == source


@given(device_id=st.text(min_size=65, max_size=200))
def test_oversize_device_id_is_rejected(device_id: str) -> None:
    """A device_id over 64 chars always fails validation."""
    try:
        IngestPayload(device_id=device_id, metrics={})
    except ValidationError:
        return
    raise AssertionError(
        "IngestPayload accepted a device_id > 64 chars — contract broken"
    )


def test_empty_device_id_is_rejected() -> None:
    """Zero-length device_id always fails validation."""
    try:
        IngestPayload(device_id="", metrics={})
    except ValidationError:
        return
    raise AssertionError("IngestPayload accepted an empty device_id — contract broken")
