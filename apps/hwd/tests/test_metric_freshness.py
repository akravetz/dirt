from __future__ import annotations

from datetime import UTC, datetime

from dirt_hwd.services.metric_freshness import _diff, _Freshness


def test_metric_freshness_transition_uses_device_capability_identity() -> None:
    last_seen = datetime(2026, 5, 4, 20, 0, tzinfo=UTC)

    transitions = _diff(
        {"plant-a-node:soil_moisture_raw": "fresh"},
        {
            "plant-a-node:soil_moisture_raw": _Freshness(
                status="stale",
                last_seen=last_seen,
                site_id="homebox",
                tent_id="main",
                device_id="plant-a-node",
                capability_id="soil_moisture_raw",
                metric="soil_moisture_raw",
            )
        },
    )

    assert len(transitions) == 1
    assert transitions[0].key == "plant-a-node:soil_moisture_raw"
    assert transitions[0].device_id == "plant-a-node"
    assert transitions[0].capability_id == "soil_moisture_raw"
