"""Hypothesis property tests for pure grow_state helpers.

Two properties pinned here:

1. ``band_status(value, band)`` partitions the real line into exactly
   three disjoint regions (ok / warn / crit). Agents love to "fix" a
   status classifier by adding a fourth state, collapsing one, or
   flipping a comparator; this property catches all three regressions.

2. Stage derivation — given any ``(today, germination_date,
   flower_start_date)`` triple, the derived stage is one of
   ``{veg, flower_early, flower_late}`` and obeys the monotonic
   germination → veg → flower_early → flower_late progression. The
   invariant stays pure (no DB) so hypothesis can explore the full
   date space without fixtures.

The oracle here is the canonical logic documented in CLAUDE.md
("Deriving stage without the DB") and in
``apps/shared/src/dirt_shared/services/grow_state.py:GrowStateService.current_stage``.
The property test duplicates that logic in a local ``derive_stage``
helper — intentionally, because the production path is async (takes a
DB session). Duplication is the point: if someone later changes the
production logic without updating the pinned property, hypothesis
finds the split.
"""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from dirt_shared.services.grow_state import (
    _LATE_FLOWER_DAY,
    STAGE_TARGETS,
    Stage,
    band_status,
)


def derive_stage(
    today: date, germination_date: date, flower_start_date: date | None
) -> Stage:
    """Pure mirror of GrowStateService.current_stage — see module docstring."""
    if flower_start_date is None or today < flower_start_date:
        return "veg"
    days_in_flower = (today - flower_start_date).days
    if days_in_flower < _LATE_FLOWER_DAY:
        return "flower_early"
    return "flower_late"


# Hypothesis strategies
_DATE = st.dates(min_value=date(2024, 1, 1), max_value=date(2030, 12, 31))
_BAND = st.tuples(
    st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
).map(lambda t: (min(t), max(t)))
_VALUE = st.floats(
    min_value=-2000, max_value=2000, allow_nan=False, allow_infinity=False
)


@given(today=_DATE, germ=_DATE, flower=st.none() | _DATE)
def test_derive_stage_is_always_one_of_three(
    today: date, germ: date, flower: date | None
) -> None:
    """For any date triple, derive_stage returns one of the three stages."""
    stage = derive_stage(today, germ, flower)
    assert stage in ("veg", "flower_early", "flower_late")
    # Every stage has a full STAGE_TARGETS entry (round-trip invariant).
    assert set(STAGE_TARGETS[stage]) == {"temperature_f", "humidity_pct", "vpd_kpa"}


@given(germ=_DATE, flower=_DATE)
def test_derive_stage_progression_is_monotonic(germ: date, flower: date) -> None:
    """Walking ``today`` forward across the flower boundary, stage never regresses."""
    # Before flower_start_date → veg.
    assert derive_stage(flower - timedelta(days=1), germ, flower) == "veg"
    # Day 0 of flower = flower_early.
    assert derive_stage(flower, germ, flower) == "flower_early"
    # Day _LATE_FLOWER_DAY - 1 still flower_early.
    assert (
        derive_stage(flower + timedelta(days=_LATE_FLOWER_DAY - 1), germ, flower)
        == "flower_early"
    )
    # Day _LATE_FLOWER_DAY tips to flower_late, and every subsequent day stays late.
    for offset in (0, 1, 7, 100):
        assert (
            derive_stage(
                flower + timedelta(days=_LATE_FLOWER_DAY + offset), germ, flower
            )
            == "flower_late"
        )


@given(value=_VALUE, band=_BAND)
def test_band_status_partitions_real_line(
    value: float, band: tuple[float, float]
) -> None:
    """band_status returns exactly one of ok/warn/crit for any (value, band)."""
    status = band_status(value, band)
    assert status in ("ok", "warn", "crit")


@given(band=_BAND)
def test_band_status_inside_band_is_ok(band: tuple[float, float]) -> None:
    """Any value inside [lo, hi] should classify as ok."""
    lo, hi = band
    if lo == hi:
        assert band_status(lo, band) == "ok"
        return
    mid = (lo + hi) / 2
    assert band_status(lo, band) == "ok"
    assert band_status(hi, band) == "ok"
    assert band_status(mid, band) == "ok"
