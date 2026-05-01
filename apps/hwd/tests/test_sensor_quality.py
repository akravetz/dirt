"""Tests for ingest-time sensor quality rejection + alert dedupe."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from dirt_hwd.services.sensor_quality import (
    SensorQualityConfig,
    SensorQualityService,
    evaluate_metrics,
)


def _capture_transport(sink: list[dict[str, str]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        sink.append(form)
        return httpx.Response(200, json={"ok": True, "result": {}})

    return httpx.MockTransport(handler)


def test_reservoir_negative_depth_is_rejected() -> None:
    decision = evaluate_metrics(
        "reservoir",
        {"reservoir_pressure_raw": 8300.0, "reservoir_in": -35.9},
    )

    assert decision.metrics == {}
    assert decision.rejected == frozenset({"reservoir_pressure_raw", "reservoir_in"})
    assert any("below alive floor" in r for r in decision.reasons)
    assert any("below 0" in r for r in decision.reasons)


def test_reservoir_plausible_depth_passes_through() -> None:
    metrics = {"reservoir_pressure_raw": 23940.0, "reservoir_in": 20.14}

    decision = evaluate_metrics("reservoir", metrics)

    assert decision.metrics == metrics
    assert decision.rejected == frozenset()
    assert decision.reasons == ()


def test_non_reservoir_metrics_pass_through() -> None:
    metrics = {"soil_moisture_raw": 1800.0}

    decision = evaluate_metrics("plant-a", metrics)

    assert decision.metrics == metrics
    assert decision.rejected == frozenset()


@pytest.mark.asyncio
async def test_bad_state_alerts_once_then_recovery_alerts(tmp_path: Path) -> None:
    calls: list[dict[str, str]] = []
    state_path = tmp_path / "state.json"
    svc = SensorQualityService(
        SensorQualityConfig(
            state_path=state_path,
            telegram_bot_token="test-token",
            telegram_chat_id="chat-1",
        ),
        http_client_factory=lambda: httpx.AsyncClient(
            transport=_capture_transport(calls)
        ),
    )

    bad = {"reservoir_pressure_raw": 8300.0, "reservoir_in": -35.9}
    good = {"reservoir_pressure_raw": 23940.0, "reservoir_in": 20.14}

    await svc.filter_metrics("reservoir", bad)
    await svc.filter_metrics("reservoir", bad)
    await svc.filter_metrics("reservoir", good)

    assert len(calls) == 2
    assert "data rejected" in calls[0]["text"]
    assert "looks valid again" in calls[1]["text"]
    assert json.loads(state_path.read_text()) == {"reservoir": "ok"}
