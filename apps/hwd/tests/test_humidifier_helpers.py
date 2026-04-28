"""Tests for the pure-function helpers in `humidifier.py`:

- ``update_lack_water`` (rising-edge tracker)
- ``update_ineffective_state`` (commanded-level watchdog)
- ``_plan_dispatch`` (current/target → API call diff)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from dirt_hwd.services.humidifier import (
    IneffectiveState,
    LackWaterState,
    _plan_dispatch,
    update_ineffective_state,
    update_lack_water,
)

T0 = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)


# ============================================================
# update_lack_water
# ============================================================


def test_lack_water_no_event_no_state_change():
    s, edge = update_lack_water(LackWaterState(), lack_water=False, now=T0)
    assert edge is None
    assert s == LackWaterState()


def test_lack_water_rising_edge_records_started_at():
    s, edge = update_lack_water(LackWaterState(), lack_water=True, now=T0)
    assert edge == "rising"
    assert s.active is True
    assert s.started_at == T0


def test_lack_water_held_active_no_re_edge():
    started = LackWaterState(active=True, started_at=T0)
    s, edge = update_lack_water(
        started, lack_water=True, now=T0 + timedelta(seconds=30)
    )
    assert edge is None
    assert s == started


def test_lack_water_falling_edge_clears_state():
    started = LackWaterState(active=True, started_at=T0)
    s, edge = update_lack_water(
        started, lack_water=False, now=T0 + timedelta(minutes=2)
    )
    assert edge == "falling"
    assert s.active is False
    assert s.started_at is None


# ============================================================
# update_ineffective_state
# ============================================================


def _advance(state, *, level, vpd, minutes):
    return update_ineffective_state(
        state,
        commanded_level=level,
        vpd=vpd,
        now=T0 + timedelta(minutes=minutes),
        alert_after_s=20 * 60,
        min_vpd_drop_kpa=0.15,
    )


def test_ineffective_no_streak_when_off():
    state, fire = _advance(IneffectiveState(), level=None, vpd=1.30, minutes=0)
    assert state == IneffectiveState()
    assert fire is False


def test_ineffective_off_to_commanded_starts_streak():
    state, fire = _advance(IneffectiveState(), level=3, vpd=1.30, minutes=0)
    assert state.start_ts == T0
    assert state.start_vpd == 1.30
    assert fire is False


def test_ineffective_commanded_to_off_clears_streak():
    started = IneffectiveState(start_ts=T0, start_vpd=1.30)
    state, fire = _advance(started, level=None, vpd=1.20, minutes=5)
    assert state == IneffectiveState()
    assert fire is False


def test_ineffective_held_with_no_drop_after_threshold_fires_once():
    started = IneffectiveState(start_ts=T0, start_vpd=1.30)
    state, fire = _advance(started, level=5, vpd=1.30, minutes=21)
    assert fire is True
    assert state.alert_sent is True


def test_ineffective_held_with_sufficient_drop_does_not_fire():
    started = IneffectiveState(start_ts=T0, start_vpd=1.30)
    state, fire = _advance(started, level=5, vpd=1.10, minutes=25)
    assert fire is False
    assert state.alert_sent is False


def test_ineffective_held_below_threshold_time_does_not_fire():
    started = IneffectiveState(start_ts=T0, start_vpd=1.30)
    _state, fire = _advance(started, level=5, vpd=1.30, minutes=10)
    assert fire is False


def test_ineffective_dedupes_alert():
    """alert_sent=True suppresses repeat alerts within the same streak."""
    sent = IneffectiveState(start_ts=T0, start_vpd=1.30, alert_sent=True)
    state, fire = _advance(sent, level=5, vpd=1.30, minutes=30)
    assert fire is False
    assert state.alert_sent is True


def test_ineffective_level_change_does_not_reset_streak():
    """A level change (3→5) keeps the streak — the failure mode is
    'we keep asking for mist but VPD doesn't drop', regardless of level."""
    started = IneffectiveState(start_ts=T0, start_vpd=1.30)
    state, fire = _advance(started, level=5, vpd=1.30, minutes=21)
    assert fire is True
    # Streak start_ts unchanged
    assert state.start_ts == T0


def test_ineffective_skips_check_when_vpd_missing():
    started = IneffectiveState(start_ts=T0, start_vpd=1.30)
    _state, fire = _advance(started, level=5, vpd=None, minutes=25)
    assert fire is False


# ============================================================
# _plan_dispatch
# ============================================================


def test_plan_off_to_off_is_noop():
    diff = _plan_dispatch(current_power=False, current_level=None, target_level=None)
    assert diff.no_op is True
    assert diff.set_power_on is None
    assert diff.set_level is None


def test_plan_on_to_off_powers_off_only():
    diff = _plan_dispatch(current_power=True, current_level=5, target_level=None)
    assert diff.no_op is False
    assert diff.set_power_on is False
    assert diff.set_level is None


def test_plan_off_to_level_collapses_to_two_calls_with_interleave():
    diff = _plan_dispatch(current_power=False, current_level=1, target_level=5)
    assert diff.no_op is False
    assert diff.set_power_on is True
    assert diff.set_level == 5
    assert diff.interleave is True


def test_plan_off_to_same_level_only_powers_on():
    """The H7142 preserves workMode across power cycles — if the device's
    last commanded level already matches the target, only set_power is
    needed."""
    diff = _plan_dispatch(current_power=False, current_level=7, target_level=7)
    assert diff.set_power_on is True
    assert diff.set_level is None
    assert diff.interleave is False


def test_plan_on_at_n_to_on_at_m_only_changes_level():
    diff = _plan_dispatch(current_power=True, current_level=3, target_level=8)
    assert diff.set_power_on is None
    assert diff.set_level == 8
    assert diff.interleave is False


def test_plan_on_at_n_to_on_at_n_is_noop():
    """Steady state — most ticks land here. No API call sent."""
    diff = _plan_dispatch(current_power=True, current_level=4, target_level=4)
    assert diff.no_op is True


def test_plan_unknown_power_treated_as_off():
    """Device omitted powerSwitch from the response — fail safe to OFF."""
    diff = _plan_dispatch(current_power=None, current_level=None, target_level=None)
    assert diff.no_op is True


def test_plan_unknown_power_to_level_powers_on_and_sets_level():
    diff = _plan_dispatch(current_power=None, current_level=None, target_level=4)
    assert diff.set_power_on is True
    assert diff.set_level == 4
    assert diff.interleave is True
