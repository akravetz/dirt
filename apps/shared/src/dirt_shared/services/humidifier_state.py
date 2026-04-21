"""Humidifier state + history — derived from ``sensorreading humidifier_on``.

The humidifier loop on dirt-hwd writes a ``humidifier_on`` reading every
poll (~30 s) with value 0.0 or 1.0 — see
``dirt_shared.services.humidifier._record``. This service turns those
into the shapes the SPA needs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import SensorLocation
from dirt_shared.models.sensor_node import SensorNode

METRIC = "humidifier_on"


@dataclass(frozen=True)
class HumidifierState:
    on: bool
    since: datetime | None
    duration_s: float | None
    cycles_24h: int
    ts: datetime


@dataclass(frozen=True)
class HumidifierTransition:
    ts: datetime
    on: bool


async def _tent_sensornode_id(session: AsyncSession) -> int | None:
    return (
        await session.exec(
            select(SensorNode.id).where(SensorNode.location == SensorLocation.TENT)
        )
    ).first()


class HumidifierStateService:
    """Derived humidifier on/off state. Constructor-inject the engine.

    Wired into ``app.state.humidifier_state`` by ``create_app``.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def get_state(self) -> HumidifierState:
        """Current on/off + last-transition timestamp + duration + cycles_24h."""
        now = self._clock()
        cutoff_24h = now - timedelta(hours=24)

        async with AsyncSession(self._engine) as session:
            tent_id = await _tent_sensornode_id(session)
            if tent_id is None:
                return HumidifierState(False, None, None, 0, now)

            latest = (
                await session.exec(
                    text(
                        "SELECT ts, value FROM sensorreading "
                        "WHERE sensornode_id = :node AND metric = :metric "
                        "ORDER BY ts DESC LIMIT 1"
                    ),
                    params={"node": tent_id, "metric": METRIC},
                )
            ).first()
            if latest is None:
                return HumidifierState(False, None, None, 0, now)
            on = bool(latest[1])

            # Transition-since: ts of the most recent row whose value differs
            # from the previous one (i.e. the current state's start).
            since_row = (
                await session.exec(
                    text(
                        """
                        SELECT ts FROM (
                            SELECT ts, value,
                                   LAG(value) OVER (ORDER BY ts) AS prev
                            FROM sensorreading
                            WHERE sensornode_id = :node AND metric = :metric
                        ) t
                        WHERE prev IS NULL OR value != prev
                        ORDER BY ts DESC LIMIT 1
                        """
                    ),
                    params={"node": tent_id, "metric": METRIC},
                )
            ).first()
            since = since_row[0] if since_row else None
            duration_s = (now - since).total_seconds() if since else None

            # cycles_24h = count of OFF→ON transitions in the last 24h.
            cycles_row = (
                await session.exec(
                    text(
                        """
                        SELECT COUNT(*) FROM (
                            SELECT ts, value,
                                   LAG(value) OVER (ORDER BY ts) AS prev
                            FROM sensorreading
                            WHERE sensornode_id = :node AND metric = :metric
                        ) t
                        WHERE ts >= :cutoff
                          AND value = 1
                          AND (prev IS NULL OR prev = 0)
                        """
                    ),
                    params={
                        "node": tent_id,
                        "metric": METRIC,
                        "cutoff": cutoff_24h,
                    },
                )
            ).first()
            cycles_24h = int(cycles_row[0]) if cycles_row else 0

            return HumidifierState(
                on=on,
                since=since,
                duration_s=duration_s,
                cycles_24h=cycles_24h,
                ts=now,
            )

    async def get_history(self, cutoff: datetime) -> list[HumidifierTransition]:
        """Return only state-change rows in [cutoff, now]."""
        async with AsyncSession(self._engine) as session:
            tent_id = await _tent_sensornode_id(session)
            if tent_id is None:
                return []

            rows = (
                await session.exec(
                    text(
                        """
                        SELECT ts, value FROM (
                            SELECT ts, value,
                                   LAG(value) OVER (ORDER BY ts) AS prev
                            FROM sensorreading
                            WHERE sensornode_id = :node AND metric = :metric
                              AND ts >= :cutoff
                        ) t
                        WHERE prev IS NULL OR value != prev
                        ORDER BY ts
                        """
                    ),
                    params={
                        "node": tent_id,
                        "metric": METRIC,
                        "cutoff": cutoff,
                    },
                )
            ).all()
            return [HumidifierTransition(ts=r[0], on=bool(r[1])) for r in rows]
