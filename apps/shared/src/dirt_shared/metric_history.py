from __future__ import annotations

from datetime import timedelta
from typing import Final, Literal

MetricHistoryRange = Literal["1h", "24h", "7d", "30d", "90d"]
MetricHistoryBucket = Literal["5m", "1h", "4h", "1d"]


_FIVE_MINUTE_RETENTION: Final = timedelta(hours=24)
_HOURLY_RETENTION: Final = timedelta(days=7)
_FOUR_HOUR_RETENTION: Final = timedelta(days=30)
_DAILY_RETENTION: Final = timedelta(days=90)

METRIC_ROLLUP_SPECS: Final[tuple[tuple[MetricHistoryBucket, timedelta, int], ...]] = (
    ("5m", _FIVE_MINUTE_RETENTION, 300),
    ("1h", _HOURLY_RETENTION, 3600),
    ("4h", _FOUR_HOUR_RETENTION, 14400),
    ("1d", _DAILY_RETENTION, 86400),
)


def metric_history_range_spec(
    range_key: MetricHistoryRange,
) -> tuple[MetricHistoryBucket, timedelta]:
    if range_key == "1h":
        return "5m", timedelta(hours=1)
    if range_key == "24h":
        return "5m", _FIVE_MINUTE_RETENTION
    if range_key == "7d":
        return "1h", _HOURLY_RETENTION
    if range_key == "30d":
        return "4h", _FOUR_HOUR_RETENTION
    return "1d", _DAILY_RETENTION
