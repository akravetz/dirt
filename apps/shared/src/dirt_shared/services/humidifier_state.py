"""Humidifier state + history — derived from ``sensorreading humidifier_on``.

The humidifier loop on dirt-hwd writes a ``humidifier_on`` reading every
poll (~30 s) with value 0.0 or 1.0 — see
``dirt_shared.services.humidifier._record``. This service turns those
into the shapes the SPA needs:

- ``GET /api/humidifier/state``: current on/off + duration since last
  transition + cycles in the last 24 h.
- ``GET /api/humidifier/history``: the *transitions* themselves over the
  requested range (not every sample — the UI renders on/off bands).

The transition set is computed with a ``LAG`` window function, which is
the big datetime-pattern win of the pg cutover — on SQLite this was an
N-pass Python scan.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.db import engine
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


async def get_state(now: datetime | None = None) -> HumidifierState:
    """Current on/off + last-transition timestamp + duration + cycles_24h.

    When there are zero humidifier_on readings yet (fresh install, seeded
    migration), returns ``on=False, since=None, duration_s=None``.
    """
    now = now or datetime.now(UTC)
    cutoff_24h = now - timedelta(hours=24)

    async with AsyncSession(engine) as session:
        tent_id = await _tent_sensornode_id(session)
        if tent_id is None:
            return HumidifierState(False, None, None, 0, now)

        # Latest reading = current state.
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

        # Transition-since: the ts of the most recent row whose value differs
        # from the one BEFORE it (i.e. the current state's starting point).
        # LAG handles both the first row (null prev) and subsequent rows.
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

        # cycles_24h = count of OFF→ON transitions (value went from 0→1) in
        # the last 24h. First-row-with-value-1 (prev IS NULL) also counts as
        # one cycle start for accuracy when the DB was seeded fresh.
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
                params={"node": tent_id, "metric": METRIC, "cutoff": cutoff_24h},
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


async def get_history(cutoff: datetime) -> list[HumidifierTransition]:
    """Return only state-change rows in [cutoff, now].

    The SPA renders on/off bands: each transition starts a band that runs
    until the next one. Returning every sample row would bloat the payload
    by 30x with no visual information.
    """
    async with AsyncSession(engine) as session:
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
                params={"node": tent_id, "metric": METRIC, "cutoff": cutoff},
            )
        ).all()
        return [HumidifierTransition(ts=r[0], on=bool(r[1])) for r in rows]


async def _tent_sensornode_id(session: AsyncSession) -> int | None:
    from sqlmodel import select

    return (
        await session.exec(
            select(SensorNode.id).where(SensorNode.location == SensorLocation.TENT)
        )
    ).first()
