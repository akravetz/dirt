"""Deterministic mock generators for sensors we don't have hardware for yet.

Two metrics, both flagged in ``data_model.md`` §2c/2d as mocks:

- ``fan_pct`` — AC Infinity inline fan duty cycle. Placeholder sine wave
  in the 45-52 % band, keyed off minute-of-day so the sparkline animates
  on the dashboard without being indistinguishable noise.

- ``reservoir_in`` — water level in the Autopot reservoir. Sawtooth that
  drops ~0.2 in / hour, with a 9 in refill-like spike at 09:00 MDT.

Both functions are pure: same ``ts`` → same value, no DB writes, no state.
When real hardware lands (see ``wiki/hardware/{ac-infinity-fan-control,
reservoir-level}.md``), the sensors will emit ``sensorreading`` rows and
these helpers retire — the SPA never knows the difference because the API
envelope is shape-identical.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

_MT = ZoneInfo("America/Denver")


def _as_utc(ts: datetime) -> datetime:
    """Promote a naive datetime to UTC-aware. Tests + historical backfill
    occasionally hand us naive datetimes; accepting both keeps the mocks
    from raising ``ValueError`` on ``astimezone()``."""
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts

# Fan: slow sine between 45 and 52 %.
_FAN_LOW = 45.0
_FAN_HIGH = 52.0
# Period ~= 3 hours so the sparkline shows a visible undulation on
# both the 1h and 24h ranges.
_FAN_PERIOD_MIN = 180.0

# Reservoir: morning refill cycle, bounded by a physical 4 in floor / 9 in lid.
_RES_LOW = 4.0
_RES_HIGH = 9.0
_RES_DROP_PER_HOUR = 0.2
_RES_REFILL_HOUR_MT = 9  # 09:00 MDT — matches current operator pattern


def get_fan_pct(ts: datetime) -> float:
    """Mocked inline-fan duty cycle at ``ts``, in percent. Pure function."""
    ts = _as_utc(ts)
    minute_of_day = ts.hour * 60 + ts.minute + ts.second / 60.0
    phase = 2 * math.pi * (minute_of_day / _FAN_PERIOD_MIN)
    amplitude = (_FAN_HIGH - _FAN_LOW) / 2
    midpoint = (_FAN_HIGH + _FAN_LOW) / 2
    return midpoint + amplitude * math.sin(phase)


def get_reservoir_in(ts: datetime) -> float:
    """Mocked reservoir level at ``ts``, in inches. Pure function.

    Model: refill to ``_RES_HIGH`` at ``_RES_REFILL_HOUR_MT`` (local time).
    Linear drop at ``_RES_DROP_PER_HOUR`` until the next refill. Clamped
    to [``_RES_LOW``, ``_RES_HIGH``] so we never show a negative reservoir.
    """
    local = _as_utc(ts).astimezone(_MT)
    refill_today = local.replace(
        hour=_RES_REFILL_HOUR_MT, minute=0, second=0, microsecond=0
    )
    if local < refill_today:
        # Last refill was yesterday.
        last_refill = refill_today - timedelta(days=1)
    else:
        last_refill = refill_today
    hours_since_refill = (local - last_refill).total_seconds() / 3600.0
    level = _RES_HIGH - hours_since_refill * _RES_DROP_PER_HOUR
    return max(_RES_LOW, min(_RES_HIGH, level))


@dataclass(frozen=True)
class MockPoint:
    ts: datetime
    value: float


def _sample(
    fn, start: datetime, end: datetime, n: int
) -> list[MockPoint]:
    if n <= 1:
        return [MockPoint(end, fn(end))]
    step = (end - start) / (n - 1)
    return [MockPoint(start + step * i, fn(start + step * i)) for i in range(n)]


def get_fan_history(start: datetime, end: datetime, n: int = 96) -> list[MockPoint]:
    """Render ``n`` sample points across ``[start, end]``. Default 96 ≈ 5-min
    buckets for a 24h range, matching ``get_sensor_history``'s output density."""
    return _sample(get_fan_pct, start, end, n)


def get_reservoir_history(
    start: datetime, end: datetime, n: int = 96
) -> list[MockPoint]:
    return _sample(get_reservoir_in, start, end, n)
