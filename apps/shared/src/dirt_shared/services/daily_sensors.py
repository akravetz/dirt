"""Sensor data layer for the daily report.

Three responsibilities:

1. **Snapshot the latest reading per (location, metric)** so the orchestrator
   can run the validation checks (zero, pinned, stale).
2. **Aggregate windowed averages** for the prompt that goes to the synthesis
   sub-agent — overnight (00-06 MDT), morning (07-14 MDT), and the now
   reading.
3. **Per-plant calibrated moisture %** for the same three windows, computed
   from the live calibration row + raw readings.

All three are exposed through a :class:`SensorReader` whose constructor takes
the SQLAlchemy engine and a clock. Tests inject a test pg engine + a frozen
clock so the time-window logic can be exercised deterministically.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import SensorLocation
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import METRICS, compute_calibrated_pct

logger = logging.getLogger(__name__)

PLANT_LOCATIONS: tuple[SensorLocation, ...] = (
    SensorLocation.PLANT_A,
    SensorLocation.PLANT_B,
    SensorLocation.PLANT_C,
    SensorLocation.PLANT_D,
)
TENT_LOCATION = SensorLocation.TENT
SOIL_METRIC = "soil_moisture_raw"
MDT = ZoneInfo("America/Denver")


@dataclass(frozen=True)
class LatestReading:
    location: SensorLocation
    metric: str
    value: float
    timestamp: datetime  # always UTC-aware
    age_s: float


@dataclass(frozen=True)
class ValidationFailure:
    """Why a sensor reading failed the daily-report bail-out check."""

    location: SensorLocation
    metric: str
    value: float | None
    age_s: float | None
    reason: str  # "zero" | "raw_pinned_low" | "raw_pinned_high" | "stale" | "missing"


@dataclass(frozen=True)
class WindowAvg:
    """Average value across [start, end). `n` is the sample count; values is
    None when there were zero samples in the window."""

    avg: float | None
    n: int


@dataclass(frozen=True)
class DailySensorSnapshot:
    """The structured payload handed to the synthesis sub-agent."""

    date_mdt: date
    tent: dict[str, dict[str, WindowAvg | float | None]]
    """{metric: {"overnight": WindowAvg, "morning": WindowAvg, "now": v}}"""
    plants: dict[str, dict[str, WindowAvg | float | None]]
    """{letter: {"overnight_pct": WindowAvg, "morning_pct": WindowAvg, "now_pct": v}}"""

    def to_prompt_dict(self) -> dict[str, Any]:
        """Render to a JSON-serializable dict for the LLM prompt."""

        def render(d: dict[str, dict[str, WindowAvg | float | None]]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for k, windows in d.items():
                row: dict[str, Any] = {}
                for win, v in windows.items():
                    if isinstance(v, WindowAvg):
                        row[win] = (
                            None
                            if v.avg is None
                            else {"avg": round(v.avg, 2), "n": v.n}
                        )
                    elif isinstance(v, float):
                        row[win] = round(v, 2)
                    else:
                        row[win] = v
                out[k] = row
            return out

        return {
            "date_mdt": self.date_mdt.isoformat(),
            "tent": render(self.tent),
            "plants": render(self.plants),
        }


def mdt_window_to_utc(
    target_date: date, start_h: int, end_h: int
) -> tuple[datetime, datetime]:
    """Return [start, end) in UTC for ``[start_h:00, end_h:00)`` MDT on
    ``target_date``. ``end_h`` is exclusive."""
    start_mdt = datetime.combine(target_date, time(start_h, 0), tzinfo=MDT)
    end_mdt = datetime.combine(target_date, time(end_h, 0), tzinfo=MDT)
    return start_mdt.astimezone(UTC), end_mdt.astimezone(UTC)


class SensorReader:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_age_s: int = 300,
        sensor_min_raw: float = 30.0,
        sensor_max_raw: float = 4000.0,
    ) -> None:
        """
        Args:
            engine: AsyncEngine for the dirt sensor DB.
            clock: returns "now" — defaults to ``datetime.now(UTC)``.
                Override in tests for deterministic window math.
            max_age_s: any reading older than this is "stale" for validation.
            sensor_min_raw: plant raw moisture readings below this fail (probe
                likely out of soil / unpowered).
            sensor_max_raw: plant raw moisture readings above this fail (ADC
                pinned at the rail / disconnected sensor).
        """
        self._engine = engine
        self._clock = clock
        self._max_age_s = max_age_s
        self._min_raw = sensor_min_raw
        self._max_raw = sensor_max_raw
        # Lazy (location → sensornode.id) cache. Initial migration seeds one
        # row per enum value, so after a single lookup we never hit DB for
        # the translation again.
        self._node_ids: dict[SensorLocation, int] = {}

    async def _node_id(
        self, session: AsyncSession, location: SensorLocation
    ) -> int | None:
        if location in self._node_ids:
            return self._node_ids[location]
        result = await session.exec(
            select(SensorNode.id).where(SensorNode.location == location)
        )
        node_id = result.first()
        if node_id is not None:
            self._node_ids[location] = node_id
        return node_id

    async def latest(
        self, location: SensorLocation, metric: str
    ) -> LatestReading | None:
        async with AsyncSession(self._engine) as session:
            node_id = await self._node_id(session, location)
            if node_id is None:
                return None
            result = await session.exec(
                select(SensorReading)
                .where(SensorReading.sensornode_id == node_id)
                .where(SensorReading.metric == metric)
                .order_by(SensorReading.ts.desc())
                .limit(1)
            )
            row = result.first()
        if row is None:
            return None
        age = (self._clock() - row.ts).total_seconds()
        return LatestReading(
            location=location,
            metric=metric,
            value=row.value,
            timestamp=row.ts,
            age_s=age,
        )

    async def validate(self) -> list[ValidationFailure]:
        """Run the daily-report bail-out checks. Returns the list of all
        failures (caller decides whether to bail or just log).

        Rules:
          - Tent metric reads exactly 0.0 → impossible, sensor disconnected.
          - Plant raw < ``sensor_min_raw`` → probe out of soil.
          - Plant raw > ``sensor_max_raw`` → ADC pinned (broken sensor).
          - Any reading older than ``max_age_s`` → stale node.
          - Any expected reading missing → node never reported.
        """
        failures: list[ValidationFailure] = []

        for metric in METRICS:
            r = await self.latest(TENT_LOCATION, metric)
            if r is None:
                failures.append(
                    ValidationFailure(TENT_LOCATION, metric, None, None, "missing")
                )
                continue
            if r.value == 0.0:
                failures.append(
                    ValidationFailure(TENT_LOCATION, metric, r.value, r.age_s, "zero")
                )
            if r.age_s > self._max_age_s:
                failures.append(
                    ValidationFailure(TENT_LOCATION, metric, r.value, r.age_s, "stale")
                )

        for loc in PLANT_LOCATIONS:
            r = await self.latest(loc, SOIL_METRIC)
            if r is None:
                failures.append(
                    ValidationFailure(loc, SOIL_METRIC, None, None, "missing")
                )
                continue
            if r.value < self._min_raw:
                failures.append(
                    ValidationFailure(
                        loc, SOIL_METRIC, r.value, r.age_s, "raw_pinned_low"
                    )
                )
            if r.value > self._max_raw:
                failures.append(
                    ValidationFailure(
                        loc, SOIL_METRIC, r.value, r.age_s, "raw_pinned_high"
                    )
                )
            if r.age_s > self._max_age_s:
                failures.append(
                    ValidationFailure(loc, SOIL_METRIC, r.value, r.age_s, "stale")
                )
        return failures

    async def _avg_in_window(
        self,
        location: SensorLocation,
        metric: str,
        start: datetime,
        end: datetime,
    ) -> WindowAvg:
        async with AsyncSession(self._engine) as session:
            node_id = await self._node_id(session, location)
            if node_id is None:
                return WindowAvg(avg=None, n=0)
            result = await session.exec(
                select(SensorReading.value)
                .where(SensorReading.sensornode_id == node_id)
                .where(SensorReading.metric == metric)
                .where(SensorReading.ts >= start)
                .where(SensorReading.ts < end)
            )
            values = list(result.all())
        if not values:
            return WindowAvg(avg=None, n=0)
        return WindowAvg(avg=mean(values), n=len(values))

    async def _calibration(
        self, location: SensorLocation, metric: str
    ) -> SensorCalibration | None:
        async with AsyncSession(self._engine) as session:
            node_id = await self._node_id(session, location)
            if node_id is None:
                return None
            result = await session.exec(
                select(SensorCalibration)
                .where(SensorCalibration.sensornode_id == node_id)
                .where(SensorCalibration.metric == metric)
            )
            return result.first()

    async def _avg_pct_in_window(
        self,
        location: SensorLocation,
        start: datetime,
        end: datetime,
        cal: SensorCalibration | None,
    ) -> WindowAvg:
        """Average calibrated soil-moisture % across the window."""
        if cal is None:
            return WindowAvg(avg=None, n=0)
        async with AsyncSession(self._engine) as session:
            node_id = await self._node_id(session, location)
            if node_id is None:
                return WindowAvg(avg=None, n=0)
            result = await session.exec(
                select(SensorReading.value)
                .where(SensorReading.sensornode_id == node_id)
                .where(SensorReading.metric == SOIL_METRIC)
                .where(SensorReading.ts >= start)
                .where(SensorReading.ts < end)
            )
            raws = list(result.all())
        pcts = [
            p
            for p in (
                compute_calibrated_pct(r, cal.raw_low, cal.raw_high) for r in raws
            )
            if p is not None
        ]
        if not pcts:
            return WindowAvg(avg=None, n=0)
        return WindowAvg(avg=mean(pcts), n=len(pcts))

    async def snapshot(self, target_date: date) -> DailySensorSnapshot:
        """Build the windowed snapshot for the daily report.

        Windows (per the user spec):
          - overnight: 00:00-06:00 MDT on ``target_date``
          - morning:   07:00-14:00 MDT on ``target_date``
          - now:       latest reading
        """
        overnight = mdt_window_to_utc(target_date, 0, 6)
        morning = mdt_window_to_utc(target_date, 7, 14)

        tent: dict[str, dict[str, WindowAvg | float | None]] = {}
        for metric in METRICS:
            now_r = await self.latest(TENT_LOCATION, metric)
            tent[metric] = {
                "overnight": await self._avg_in_window(
                    TENT_LOCATION, metric, *overnight
                ),
                "morning": await self._avg_in_window(TENT_LOCATION, metric, *morning),
                "now": (None if now_r is None else now_r.value),
            }

        plants: dict[str, dict[str, WindowAvg | float | None]] = {}
        for loc in PLANT_LOCATIONS:
            cal = await self._calibration(loc, SOIL_METRIC)
            now_r = await self.latest(loc, SOIL_METRIC)
            now_pct: float | None = None
            if now_r is not None and cal is not None:
                now_pct = compute_calibrated_pct(now_r.value, cal.raw_low, cal.raw_high)
            letter = loc.value.removeprefix("plant-")
            plants[letter] = {
                "overnight_pct": await self._avg_pct_in_window(loc, *overnight, cal),
                "morning_pct": await self._avg_pct_in_window(loc, *morning, cal),
                "now_pct": now_pct,
            }

        return DailySensorSnapshot(
            date_mdt=target_date,
            tent=tent,
            plants=plants,
        )
