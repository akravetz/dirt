from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status


def require_consistent_metric_unit(
    units: Iterable[str | None],
    *,
    metric: str,
) -> str | None:
    distinct_units = set(units)
    if len(distinct_units) > 1:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"metric rollups have inconsistent units for {metric}",
        )
    return next(iter(distinct_units), None)
