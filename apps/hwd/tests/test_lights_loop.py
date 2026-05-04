from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from dirt_hwd.services.lights import LightsLoopService
from dirt_shared.config import LightsConfig
from dirt_shared.services.grow_state import LightsState

T0 = datetime(2026, 5, 4, 18, 0, tzinfo=UTC)


class _FakePlug:
    def __init__(self, stop_event: asyncio.Event) -> None:
        self.is_on = False
        self.turn_on_calls = 0
        self._stop_event = stop_event

    async def update(self) -> None:
        return None

    async def turn_on(self) -> None:
        self.turn_on_calls += 1
        self.is_on = True
        self._stop_event.set()

    async def turn_off(self) -> None:
        raise AssertionError("expected turn_on, got turn_off")

    async def disconnect(self) -> None:
        return None


class _FakeGrow:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def lights_state(self, **kwargs) -> LightsState:
        self.calls.append(dict(kwargs))
        return LightsState(on=True, minutes_until_off=180.0, minutes_until_on=540.0)


async def test_lights_loop_reads_main_tent_schedule() -> None:
    stop_event = asyncio.Event()
    plug = _FakePlug(stop_event)
    grow = _FakeGrow()

    async def discover_single(host, *, credentials):
        assert host == "192.0.2.42"
        assert credentials is not None
        return plug

    service = LightsLoopService(
        LightsConfig(
            kasa_username="user",
            kasa_password="pass",
            kasa_lights_host="192.0.2.42",
            poll_interval=30,
        ),
        grow=grow,
        clock=lambda: T0,
        discover_single=discover_single,
    )

    await asyncio.wait_for(service.run(stop_event), timeout=2.0)

    assert plug.turn_on_calls == 1
    assert grow.calls == [{"site_id": "homebox", "tent_id": "main"}]
