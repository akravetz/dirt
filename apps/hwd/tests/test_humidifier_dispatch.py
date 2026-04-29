"""Tests for the u_pct → discrete-level quantizer."""

from __future__ import annotations

import pytest

from dirt_hwd.services.humidifier_dispatch import (
    DispatchConfig,
    DispatchOutput,
    DispatchState,
    quantize,
)

CFG = DispatchConfig(levels=9, level_hysteresis_pct=3.0)
# bucket_width = 100/9 ≈ 11.1111…
W = 100.0 / 9


def _q(u_pct: float, plug_on: bool, last: int | None = None) -> DispatchOutput:
    return quantize(CFG, DispatchState(last_level=last), u_pct, plug_on)


# ============================================================
# OFF passthrough
# ============================================================


def test_plug_off_yields_target_none_regardless_of_u():
    out = _q(50.0, plug_on=False, last=5)
    assert out.target_level is None
    assert out.naive_level is None
    assert out.held_by_hysteresis is False
    assert out.new_state.last_level is None


def test_plug_off_clears_last_level():
    out = _q(0.0, plug_on=False, last=7)
    assert out.new_state.last_level is None


# ============================================================
# Cold start (last=None) — naive bucket map
# ============================================================


def test_cold_start_low_u_picks_level_1():
    out = _q(0.5, plug_on=True, last=None)
    assert out.target_level == 1
    assert out.new_state.last_level == 1


def test_cold_start_max_u_picks_top_level():
    out = _q(100.0, plug_on=True, last=None)
    assert out.target_level == 9


def test_cold_start_above_100_clamps_to_top():
    out = _q(150.0, plug_on=True, last=None)
    assert out.target_level == 9


def test_cold_start_midrange_picks_middle_bucket():
    # 5 * W = 55.55…  → boundary into level 5
    out = _q(50.0, plug_on=True, last=None)
    assert out.target_level == 5  # ceil(50 / 11.11) = 5


def test_cold_start_at_exact_boundary_picks_lower_bucket():
    # ceil((W - 1e-9) / W) = 1 by floor semantics; ceil(W / W) = 1 too.
    # The bucket is (0, W] → 1, so u_pct = W lands in level 1.
    out = _q(W, plug_on=True, last=None)
    assert out.target_level == 1


def test_cold_start_just_past_boundary_picks_next_bucket():
    out = _q(W + 0.001, plug_on=True, last=None)
    assert out.target_level == 2


# ============================================================
# Hysteresis — holding at last_level
# ============================================================


def test_no_change_when_u_inside_current_bucket():
    # last=5, bucket spans (4W, 5W] = (44.44, 55.55]. u=50 stays.
    out = _q(50.0, plug_on=True, last=5)
    assert out.target_level == 5


def test_step_up_blocked_within_hysteresis_above_upper_edge():
    # last=5, upper edge = 5W = 55.55. u=57 (within 55.55 + 3 = 58.55) holds.
    out = _q(57.0, plug_on=True, last=5)
    assert out.target_level == 5
    assert out.naive_level == 6
    assert out.held_by_hysteresis is True


def test_step_up_allowed_past_upper_edge_plus_hysteresis():
    # u = 5W + 3.5 = 59.05  → past hyst boundary, step to 6.
    out = _q(5 * W + 3.5, plug_on=True, last=5)
    assert out.target_level == 6
    assert out.naive_level == 6
    assert out.held_by_hysteresis is False


def test_step_down_blocked_within_hysteresis_below_lower_edge():
    # last=5, lower edge = 4W = 44.44. u=42 (within 44.44 - 3 = 41.44) holds.
    out = _q(42.0, plug_on=True, last=5)
    assert out.target_level == 5
    assert out.naive_level == 4
    assert out.held_by_hysteresis is True


def test_step_down_allowed_past_lower_edge_minus_hysteresis():
    # u = 4W - 3.5 = 40.94  → past hyst boundary, step to 4.
    out = _q(4 * W - 3.5, plug_on=True, last=5)
    assert out.target_level == 4
    assert out.naive_level == 4
    assert out.held_by_hysteresis is False


def test_large_u_jump_skips_levels():
    # last=2, u=95 → naive=ceil(95/11.11)=9, well past upper edge + hyst.
    out = _q(95.0, plug_on=True, last=2)
    assert out.target_level == 9


def test_large_downward_u_jump_skips_levels():
    # last=8, u=2 → naive=1, well past lower edge - hyst.
    out = _q(2.0, plug_on=True, last=8)
    assert out.target_level == 1


# ============================================================
# Anti-chatter: oscillating around a single boundary
# ============================================================


def test_oscillation_in_deadzone_holds_level():
    # u oscillates inside [boundary - hyst, boundary + hyst] for level 5.
    # last=5, boundary=5W=55.55, hyst=3 → deadzone [52.55, 58.55].
    state = DispatchState(last_level=5)
    for u in (54.0, 57.0, 53.0, 58.0, 55.5, 56.0, 53.5):
        out = quantize(CFG, state, u, plug_on=True)
        assert out.target_level == 5
        state = out.new_state


def test_walks_up_through_levels_when_u_increases_monotonically():
    state = DispatchState(last_level=1)
    seen = []
    for u in [5, 12, 18, 25, 33, 42, 51, 60, 70, 82, 95]:
        out = quantize(CFG, state, float(u), plug_on=True)
        seen.append(out.target_level)
        state = out.new_state
    # Should be monotonic non-decreasing and end at 9.
    assert seen == sorted(seen)
    assert seen[-1] == 9


# ============================================================
# Edge cases
# ============================================================


def test_off_to_on_transition_preserves_naive_pick():
    # Off → ON at u=80: naive bucket = ceil(80/11.11) = 8.
    out = _q(80.0, plug_on=True, last=None)
    assert out.target_level == 8


def test_zero_levels_rejected():
    with pytest.raises(ValueError):
        quantize(DispatchConfig(levels=0), DispatchState(), 50.0, plug_on=True)


def test_bucket_width_exposed_for_logging():
    out = _q(50.0, plug_on=True, last=None)
    assert out.bucket_width == pytest.approx(100.0 / 9)


def test_diagnostic_fields_exposed_for_logging():
    out = _q(57.0, plug_on=True, last=5)
    assert out.naive_level == 6
    assert out.target_level == 5
    assert out.held_by_hysteresis is True
