"""Unit tests for the stuck-humidifier watchdog state machine.

Covers ``update_stuck_state`` as a pure function — the integration with
the Kasa plug loop and Telegram is driven from the same state transitions
these tests exercise, so asserting the state-machine behavior in isolation
is sufficient coverage for the watchdog's logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from dirt_hwd.services.humidifier import StuckState, update_stuck_state

T0 = datetime(2026, 4, 23, 5, 0, tzinfo=UTC)

# Defaults mirror the production tuning — 20 min ON with less than 0.15 kPa
# VPD drop fires the alert.
ALERT_AFTER_S = 1200.0
MIN_VPD_DROP = 0.15


def _advance(state: StuckState, *, is_on: bool, vpd: float | None, minutes: float):
    return update_stuck_state(
        state,
        is_on=is_on,
        vpd=vpd,
        now=T0 + timedelta(minutes=minutes),
        alert_after_s=ALERT_AFTER_S,
        min_vpd_drop_kpa=MIN_VPD_DROP,
    )


def test_off_initial_state_stays_off():
    state, fire = _advance(StuckState(), is_on=False, vpd=0.6, minutes=0)
    assert state == StuckState()
    assert fire is False


def test_off_to_on_starts_streak_and_captures_start_vpd():
    state, fire = _advance(StuckState(), is_on=True, vpd=1.3, minutes=0)
    assert state.start_ts == T0
    assert state.start_vpd == 1.3
    assert state.alert_sent is False
    assert fire is False


def test_on_to_off_clears_streak():
    started = StuckState(start_ts=T0, start_vpd=1.3, alert_sent=False)
    state, fire = _advance(started, is_on=False, vpd=0.8, minutes=5)
    assert state == StuckState()
    assert fire is False


def test_on_streak_with_healthy_vpd_drop_does_not_fire():
    # VPD dropped 0.35 kPa — far more than the 0.15 threshold.
    started = StuckState(start_ts=T0, start_vpd=1.30, alert_sent=False)
    state, fire = _advance(started, is_on=True, vpd=0.95, minutes=25)
    assert fire is False
    assert state.alert_sent is False


def test_on_streak_below_threshold_does_not_fire_yet():
    # Stuck-looking but only 15 min in — under the 20-min floor.
    started = StuckState(start_ts=T0, start_vpd=1.30, alert_sent=False)
    state, fire = _advance(started, is_on=True, vpd=1.30, minutes=15)
    assert fire is False
    assert state.alert_sent is False


def test_on_streak_past_threshold_with_no_drop_fires_once():
    # Over threshold, zero VPD drop → fire.
    started = StuckState(start_ts=T0, start_vpd=1.30, alert_sent=False)
    state, fire = _advance(started, is_on=True, vpd=1.30, minutes=21)
    assert fire is True
    assert state.alert_sent is True


def test_on_streak_past_threshold_with_vpd_rising_fires():
    # VPD actually climbed — the 2026-04-23 Raydrop-latch signature.
    started = StuckState(start_ts=T0, start_vpd=1.20, alert_sent=False)
    state, fire = _advance(started, is_on=True, vpd=1.85, minutes=90)
    assert fire is True
    assert state.alert_sent is True


def test_fire_happens_only_once_per_streak():
    started = StuckState(start_ts=T0, start_vpd=1.30, alert_sent=False)
    state, fire1 = _advance(started, is_on=True, vpd=1.30, minutes=21)
    assert fire1 is True
    # Same conditions next tick — must not refire.
    state, fire2 = _advance(state, is_on=True, vpd=1.30, minutes=22)
    assert fire2 is False
    # Even at 90 min in — still silenced until the next OFF transition.
    state, fire3 = _advance(state, is_on=True, vpd=1.35, minutes=90)
    assert fire3 is False


def test_streak_resets_across_off_then_on_and_can_refire():
    started = StuckState(start_ts=T0, start_vpd=1.30, alert_sent=True)
    # Turn off.
    state, _ = _advance(started, is_on=False, vpd=0.85, minutes=25)
    assert state == StuckState()
    # Turn back on — new streak starts.
    state, _ = _advance(state, is_on=True, vpd=1.25, minutes=30)
    assert state.start_ts == T0 + timedelta(minutes=30)
    assert state.alert_sent is False
    # After a fresh 21-min stuck interval, we alert again.
    state, fire = _advance(state, is_on=True, vpd=1.25, minutes=51)
    assert fire is True


def test_missing_vpd_during_streak_skips_stuck_check():
    # Failsafe handles the stale-sensor case; the stuck watchdog must not
    # pile on a second alert for the same root cause.
    started = StuckState(start_ts=T0, start_vpd=1.30, alert_sent=False)
    state, fire = _advance(started, is_on=True, vpd=None, minutes=25)
    assert fire is False
    assert state.alert_sent is False


def test_missing_start_vpd_skips_stuck_check():
    # If the transition happened without a valid VPD reading, we don't have
    # a baseline to measure drop against; stay silent.
    started = StuckState(start_ts=T0, start_vpd=None, alert_sent=False)
    state, fire = _advance(started, is_on=True, vpd=1.30, minutes=25)
    assert fire is False
    assert state.alert_sent is False


def test_vpd_drop_exactly_at_threshold_does_not_fire():
    # Drop of exactly min_vpd_drop_kpa is healthy — boundary inclusive.
    started = StuckState(start_ts=T0, start_vpd=1.30, alert_sent=False)
    _, fire = _advance(started, is_on=True, vpd=1.15, minutes=25)
    assert fire is False
