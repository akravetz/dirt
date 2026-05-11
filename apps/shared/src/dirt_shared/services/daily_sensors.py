"""Sensor data layer for the daily report.

Three responsibilities:

1. **Snapshot the latest reading per capability** so the orchestrator
   can run the validation checks (zero, pinned, stale).
2. **Aggregate windowed averages** for the prompt that goes to the synthesis
   sub-agent — overnight (00-06 MDT), morning (07-14 MDT), and the now
   reading.
3. **Per-plant soil-moisture trend context** for the same three windows,
   including raw readings and calibrated % when available. The daily synthesis
   treats calibrated absolute values as a rough reference only; relative
   movement is the more useful signal until probes are calibrated in-place.

All three are exposed through a :class:`SensorReader` whose constructor takes
the SQLAlchemy engine and a clock. Tests inject a test pg engine + a frozen
clock so the time-window logic can be exercised deterministically.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.plant import Plant
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent
from dirt_shared.sensor_contract import persisted_capability_ids_for_device_id
from dirt_shared.services.readings import (
    compute_calibrated_pct,
    get_sensor_calibration,
)
from dirt_shared.services.scope import current_grow_run

logger = logging.getLogger(__name__)

DEFAULT_REPORT_TENT_IDS = ("main", "breeding")
DEFAULT_REQUIRED_TENT_IDS = ("main",)
SOIL_METRIC = "soil_moisture_raw"
MDT = ZoneInfo("America/Denver")


@dataclass(frozen=True)
class LatestReading:
    device_id: str
    capability_id: str
    metric: str
    value: float
    timestamp: datetime  # always UTC-aware
    age_s: float


@dataclass(frozen=True)
class SensorRequirement:
    device_id: str
    capability_id: str
    metric: str
    subject: str
    pk: int


@dataclass(frozen=True)
class ValidationFailure:
    """Why a sensor reading failed the daily-report bail-out check."""

    subject: str
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
    """Legacy alias for ``tents["main"]``."""
    plants: dict[str, dict[str, WindowAvg | float | None]]
    """{letter: moisture trend context for main-tent plants}"""
    tents: dict[str, dict[str, dict[str, WindowAvg | float | None]]] = field(
        default_factory=dict
    )
    """{tent_id: {metric: {"overnight": WindowAvg, "morning": WindowAvg, "now": v}}}"""

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

        tents = self.tents or {"main": self.tent}
        return {
            "date_mdt": self.date_mdt.isoformat(),
            "tent": render(self.tent),
            "tents": {
                tent_id: render(metrics) for tent_id, metrics in sorted(tents.items())
            },
            "plants": render(self.plants),
            "soil_moisture_note": (
                "Soil-moisture absolute calibration is not trusted. Use raw and "
                "calibrated values as rough context only; emphasize relative "
                "movement between overnight, morning, and now. Flag only stale, "
                "missing, pinned, or large directional changes."
            ),
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
    def __init__(  # noqa: PLR0913 - scope knobs are part of this boundary.
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_age_s: int = 300,
        sensor_min_raw: float = 30.0,
        sensor_max_raw: float = 4000.0,
        report_tent_ids: Sequence[str] = DEFAULT_REPORT_TENT_IDS,
        required_tent_ids: Sequence[str] = DEFAULT_REQUIRED_TENT_IDS,
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
        self._report_tent_ids = tuple(dict.fromkeys(report_tent_ids))
        self._required_tent_ids = tuple(dict.fromkeys(required_tent_ids))
        self._plant_requirements: list[SensorRequirement] | None = None
        self._tent_requirements_by_tent: dict[str, list[SensorRequirement]] = {}

    async def _tent_metric_requirements(
        self,
        session: AsyncSession,
        *,
        tent_id: str,
    ) -> list[SensorRequirement]:
        if tent_id in self._tent_requirements_by_tent:
            return self._tent_requirements_by_tent[tent_id]
        rows = (
            await session.exec(
                select(
                    Device.device_id,
                    Capability.id,
                    Capability.capability_id,
                    Capability.metric_name,
                )
                .join(Device, Device.id == Capability.device_id)
                .join(Site, Site.id == Device.site_id)
                .join(Tent, Tent.id == Device.tent_id)
                .where(Site.site_id == "homebox")
                .where(Tent.tent_id == tent_id)
                .where(Device.kind == "env_sensor")
                .where(Device.enabled.is_(True))
                .where(Capability.enabled.is_(True))
                .order_by(Device.device_id, Capability.capability_id)
            )
        ).all()
        requirements = [
            SensorRequirement(
                device_id=device_id,
                capability_id=capability_id,
                metric=metric_name,
                subject=device_id,
                pk=pk,
            )
            for device_id, pk, capability_id, metric_name in rows
            if metric_name is not None
            and capability_id in persisted_capability_ids_for_device_id(device_id)
        ]
        self._tent_requirements_by_tent[tent_id] = requirements
        return requirements

    async def _plant_metric_requirements(
        self,
        session: AsyncSession,
    ) -> list[SensorRequirement]:
        if self._plant_requirements is not None:
            return self._plant_requirements
        grow = await current_grow_run(session)
        if grow is None:
            self._plant_requirements = []
            return []
        rows = (
            await session.exec(
                select(
                    Plant.code,
                    Device.device_id,
                    Capability.capability_id,
                    Capability.metric_name,
                    Capability.id,
                )
                .join(Capability, Capability.id == Plant.moisture_capability_id)
                .join(Device, Device.id == Capability.device_id)
                .where(Plant.growrun_id == grow.id)
                .where(Plant.moisture_capability_id.is_not(None))
                .where(Capability.enabled.is_(True))
                .where(Device.enabled.is_(True))
                .order_by(Plant.code)
            )
        ).all()
        self._plant_requirements = [
            SensorRequirement(
                device_id=device_id,
                capability_id=capability_id,
                metric=metric_name,
                subject=f"plant-{code}",
                pk=pk,
            )
            for code, device_id, capability_id, metric_name, pk in rows
            if metric_name == SOIL_METRIC
        ]
        return self._plant_requirements

    async def _latest_for_requirement(
        self, requirement: SensorRequirement
    ) -> LatestReading | None:
        async with AsyncSession(self._engine) as session:
            result = await session.exec(
                select(SensorReading)
                .where(SensorReading.capability_id == requirement.pk)
                .where(SensorReading.metric == requirement.metric)
                .order_by(SensorReading.ts.desc())
                .limit(1)
            )
            row = result.first()
        if row is None:
            return None
        age = (self._clock() - row.ts).total_seconds()
        return LatestReading(
            device_id=requirement.device_id,
            capability_id=requirement.capability_id,
            metric=requirement.metric,
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

        async with AsyncSession(self._engine) as session:
            tent_requirements = [
                requirement
                for tent_id in self._required_tent_ids
                for requirement in await self._tent_metric_requirements(
                    session, tent_id=tent_id
                )
            ]
            plant_requirements = await self._plant_metric_requirements(session)

        for requirement in tent_requirements:
            r = await self._latest_for_requirement(requirement)
            if r is None:
                failures.append(
                    ValidationFailure(
                        requirement.subject, requirement.metric, None, None, "missing"
                    )
                )
                continue
            if r.value == 0.0:
                failures.append(
                    ValidationFailure(
                        requirement.subject,
                        requirement.metric,
                        r.value,
                        r.age_s,
                        "zero",
                    )
                )
            if r.age_s > self._max_age_s:
                failures.append(
                    ValidationFailure(
                        requirement.subject,
                        requirement.metric,
                        r.value,
                        r.age_s,
                        "stale",
                    )
                )

        for requirement in plant_requirements:
            r = await self._latest_for_requirement(requirement)
            if r is None:
                failures.append(
                    ValidationFailure(
                        requirement.subject, requirement.metric, None, None, "missing"
                    )
                )
                continue
            if r.value < self._min_raw:
                failures.append(
                    ValidationFailure(
                        requirement.subject,
                        requirement.metric,
                        r.value,
                        r.age_s,
                        "raw_pinned_low",
                    )
                )
            if r.value > self._max_raw:
                failures.append(
                    ValidationFailure(
                        requirement.subject,
                        requirement.metric,
                        r.value,
                        r.age_s,
                        "raw_pinned_high",
                    )
                )
            if r.age_s > self._max_age_s:
                failures.append(
                    ValidationFailure(
                        requirement.subject,
                        requirement.metric,
                        r.value,
                        r.age_s,
                        "stale",
                    )
                )
        return failures

    async def _avg_in_window(
        self,
        requirement: SensorRequirement,
        start: datetime,
        end: datetime,
    ) -> WindowAvg:
        async with AsyncSession(self._engine) as session:
            result = await session.exec(
                select(SensorReading.value)
                .where(SensorReading.capability_id == requirement.pk)
                .where(SensorReading.metric == requirement.metric)
                .where(SensorReading.ts >= start)
                .where(SensorReading.ts < end)
            )
            values = list(result.all())
        if not values:
            return WindowAvg(avg=None, n=0)
        return WindowAvg(avg=mean(values), n=len(values))

    async def _calibration(
        self, requirement: SensorRequirement
    ) -> SensorCalibration | None:
        async with AsyncSession(self._engine) as session:
            return await get_sensor_calibration(
                session,
                metric=requirement.metric,
                capability_id=requirement.pk,
            )

    async def _avg_pct_in_window(
        self,
        requirement: SensorRequirement,
        start: datetime,
        end: datetime,
        cal: SensorCalibration | None,
    ) -> WindowAvg:
        """Average calibrated soil-moisture % across the window."""
        if cal is None:
            return WindowAvg(avg=None, n=0)
        async with AsyncSession(self._engine) as session:
            result = await session.exec(
                select(SensorReading.value)
                .where(SensorReading.capability_id == requirement.pk)
                .where(SensorReading.metric == requirement.metric)
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

        async with AsyncSession(self._engine) as session:
            tent_requirements_by_tent = {
                tent_id: await self._tent_metric_requirements(session, tent_id=tent_id)
                for tent_id in self._report_tent_ids
            }
            plant_requirements = await self._plant_metric_requirements(session)

        tents: dict[str, dict[str, dict[str, WindowAvg | float | None]]] = {}
        for tent_id, tent_requirements in tent_requirements_by_tent.items():
            tent: dict[str, dict[str, WindowAvg | float | None]] = {}
            for requirement in tent_requirements:
                now_r = await self._latest_for_requirement(requirement)
                tent[requirement.metric] = {
                    "overnight": await self._avg_in_window(requirement, *overnight),
                    "morning": await self._avg_in_window(requirement, *morning),
                    "now": (None if now_r is None else now_r.value),
                }
            tents[tent_id] = tent

        plants: dict[str, dict[str, WindowAvg | float | None]] = {}
        for requirement in plant_requirements:
            cal = await self._calibration(requirement)
            now_r = await self._latest_for_requirement(requirement)
            now_pct: float | None = None
            if now_r is not None and cal is not None:
                now_pct = compute_calibrated_pct(now_r.value, cal.raw_low, cal.raw_high)
            overnight_raw = await self._avg_in_window(requirement, *overnight)
            morning_raw = await self._avg_in_window(requirement, *morning)
            letter = requirement.subject.removeprefix("plant-")
            plants[letter] = {
                "overnight_raw": overnight_raw,
                "morning_raw": morning_raw,
                "now_raw": None if now_r is None else now_r.value,
                "raw_delta_morning_to_now": (
                    None
                    if now_r is None or morning_raw.avg is None
                    else now_r.value - morning_raw.avg
                ),
                "overnight_pct": await self._avg_pct_in_window(
                    requirement, *overnight, cal
                ),
                "morning_pct": await self._avg_pct_in_window(
                    requirement, *morning, cal
                ),
                "now_pct": now_pct,
                "pct_delta_morning_to_now": None,
            }
            morning_pct = plants[letter]["morning_pct"]
            if (
                isinstance(morning_pct, WindowAvg)
                and morning_pct.avg is not None
                and now_pct is not None
            ):
                plants[letter]["pct_delta_morning_to_now"] = now_pct - morning_pct.avg

        return DailySensorSnapshot(
            date_mdt=target_date,
            tent=tents.get("main", {}),
            plants=plants,
            tents=tents,
        )
