"""Deterministic mock generator for ``reservoir_in``, the only dashboard
metric still without hardware (see ``wiki/hardware/reservoir-level.md``).

Pure function: same ``ts`` → same value, no DB writes, no state. When the
XKC-Y25-T12V lands, the sensor will emit ``sensorreading`` rows and this
helper retires — the SPA never knows the difference because the API
envelope is shape-identical.

The fan was similarly mocked until 2026-04-23 when the combined fan-
controller node landed — its mock helpers have been retired.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

_MT = ZoneInfo("America/Denver")


def _as_utc(ts: datetime) -> datetime:
    """Promote a naive datetime to UTC-aware. Tests + historical backfill
    occasionally hand us naive datetimes; accepting both keeps the mocks
    from raising ``ValueError`` on ``astimezone()``."""
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts


# Reservoir: morning refill cycle, bounded by a physical 4 in floor / 9 in lid.
_RES_LOW = 4.0
_RES_HIGH = 9.0
_RES_DROP_PER_HOUR = 0.2
_RES_REFILL_HOUR_MT = 9  # 09:00 MDT — matches current operator pattern


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


def _sample(fn, start: datetime, end: datetime, n: int) -> list[MockPoint]:
    if n <= 1:
        return [MockPoint(end, fn(end))]
    step = (end - start) / (n - 1)
    return [MockPoint(start + step * i, fn(start + step * i)) for i in range(n)]


def get_reservoir_history(
    start: datetime, end: datetime, n: int = 96
) -> list[MockPoint]:
    """Render ``n`` sample points across ``[start, end]``. Default 96 ≈ 5-min
    buckets for a 24h range, matching ``get_sensor_history``'s output density."""
    return _sample(get_reservoir_in, start, end, n)
