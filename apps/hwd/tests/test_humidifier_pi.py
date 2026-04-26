"""Property tests for the humidifier PI controller (Phase 4 prep).

Pure-function tests on ``compute()`` — no plant model, no I/O. Covers the
structural invariants from docs/epics/continuous-humidifier/phase4-test-plan.md.

Discipline: tests assert *behaviors*, never tuning numbers. No test pins
``Kc``, ``Ki``, threshold, or deadband to a specific value. Re-tuning must
not require touching this file.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from dirt_hwd.services.humidifier_pi import (
    PIConfig,
    PIInput,
    PIOutput,
    PIState,
    Reason,
    compute,
)

T0 = datetime(2026, 4, 25, 18, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def default_config(**overrides) -> PIConfig:
    base = dict(
        kc=10.0,
        ki=0.01,
        integrator_clamp=100.0,
        intensity_threshold=5.0,
        threshold_hysteresis=1.0,
        night_offset_kpa=-0.3,
        failsafe_stale_s=300.0,
        lights_off_prep_minutes=30.0,
    )
    base.update(overrides)
    return PIConfig(**base)


def default_input(
    *,
    now: datetime = T0,
    vpd: float | None = 1.30,
    vpd_age_s: float = 10.0,
    rh: float | None = 50.0,
    stage_vpd_band: tuple[float, float] = (0.8, 1.2),
    stage_humidity_band: tuple[float, float] = (40.0, 55.0),
    lights_on: bool = True,
    minutes_until_off: float = 300.0,
    minutes_until_on: float = 600.0,
) -> PIInput:
    vpd_ts = now - timedelta(seconds=vpd_age_s) if vpd is not None else None
    return PIInput(
        now=now,
        vpd=vpd,
        vpd_ts=vpd_ts,
        rh=rh,
        stage_vpd_band=stage_vpd_band,
        stage_humidity_band=stage_humidity_band,
        lights_on=lights_on,
        minutes_until_off=minutes_until_off,
        minutes_until_on=minutes_until_on,
    )


def step(state: PIState, inp: PIInput, cfg: PIConfig | None = None) -> PIOutput:
    return compute(cfg or default_config(), state, inp)


def run_n(state: PIState, inp_factory, cfg: PIConfig, n: int, dt_s: float = 30.0):
    """Drive the controller n ticks with inp_factory(tick_index, now). Returns final state + last output."""
    out: PIOutput | None = None
    for i in range(n):
        now = T0 + timedelta(seconds=i * dt_s)
        inp = inp_factory(i, now)
        out = compute(cfg, state, inp)
        state = out.new_state
    assert out is not None
    return state, out


# ---------------------------------------------------------------------------
# Output-range invariant
# ---------------------------------------------------------------------------


def test_output_always_in_range_under_random_inputs():
    rng = random.Random(0xC0FFEE)  # noqa: S311 — non-crypto fuzzing
    cfg = default_config()
    state = PIState()
    for _ in range(2000):
        vpd = rng.uniform(0.0, 5.0)
        rh = rng.uniform(0.0, 100.0)
        age = rng.uniform(0.0, 600.0)
        lights_on = bool(rng.getrandbits(1))
        minutes_until_off = rng.uniform(0.0, 720.0)
        minutes_until_on = rng.uniform(0.0, 720.0)
        now = T0 + timedelta(seconds=rng.uniform(0, 1e6))
        inp = default_input(
            now=now,
            vpd=vpd,
            vpd_age_s=age,
            rh=rh,
            lights_on=lights_on,
            minutes_until_off=minutes_until_off,
            minutes_until_on=minutes_until_on,
        )
        out = compute(cfg, state, inp)
        assert 0.0 <= out.u <= 100.0
        assert isinstance(out.plug_on, bool)
        state = out.new_state


# ---------------------------------------------------------------------------
# Monotonicity: ↑error → non-decreasing u (within saturation)
# ---------------------------------------------------------------------------


def test_monotonicity_in_error_at_fixed_state():
    cfg = default_config()
    state = PIState(integral=0.0, last_tick_ts=None, plug_on_for_threshold=False)
    last_u = -1.0
    # Sweep VPD low (very wet, negative error) → high (very dry, positive error).
    # Setpoint with band (0.8, 1.2), lights on = 1.2 kPa.
    # Sign convention: error = vpd - setpoint, so increasing VPD → increasing error → ↑u.
    for vpd in (0.3, 0.7, 1.0, 1.19, 1.20, 1.21, 1.5, 2.0, 3.0):
        out = step(state, default_input(vpd=vpd), cfg)
        assert out.u >= last_u, (
            f"u dropped as VPD rose (vpd={vpd}, u={out.u}, last_u={last_u})"
        )
        last_u = out.u


# ---------------------------------------------------------------------------
# Failsafe: stale sensor / missing VPD ⇒ u=0, plug off, integrator frozen
# ---------------------------------------------------------------------------


def test_stale_sensor_forces_zero_output():
    cfg = default_config()
    out = step(PIState(), default_input(vpd_age_s=cfg.failsafe_stale_s + 1.0))
    assert out.u == 0.0
    assert out.plug_on is False
    assert out.reason is Reason.FAILSAFE_STALE_SENSOR


def test_missing_vpd_forces_zero_output():
    out = step(PIState(), default_input(vpd=None))
    assert out.u == 0.0
    assert out.plug_on is False
    assert out.reason is Reason.FAILSAFE_STALE_SENSOR


def test_failsafe_does_not_grow_integrator():
    cfg = default_config()
    # First seed integrator with a positive value so we can detect drift.
    state = PIState(
        integral=20.0,
        last_tick_ts=T0 - timedelta(seconds=30),
        plug_on_for_threshold=False,
    )
    final, _ = run_n(
        state,
        lambda _i, now: default_input(now=now, vpd=None),
        cfg,
        n=20,
        dt_s=30.0,
    )
    assert final.integral == pytest.approx(20.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Lights-window guards
# ---------------------------------------------------------------------------


def test_outside_lights_window_dark_period_forces_zero():
    cfg = default_config()
    # Lights off, not yet inside the morning ramp-up window.
    inp = default_input(
        lights_on=False,
        minutes_until_off=720.0,
        minutes_until_on=cfg.lights_off_prep_minutes + 60.0,  # well outside ramp
        vpd=2.0,  # very dry; would normally drive u high
    )
    out = step(PIState(), inp)
    assert out.u == 0.0
    assert out.plug_on is False
    assert out.reason is Reason.OUTSIDE_LIGHTS_WINDOW


def test_lights_on_pre_lights_off_prep_window_forces_zero():
    cfg = default_config()
    # Lights on but inside the last `prep_minutes` before lights-off.
    inp = default_input(
        lights_on=True,
        minutes_until_off=cfg.lights_off_prep_minutes - 5.0,
        minutes_until_on=720.0,
        vpd=2.0,
    )
    out = step(PIState(), inp)
    assert out.u == 0.0
    assert out.reason is Reason.OUTSIDE_LIGHTS_WINDOW


def test_pre_lights_on_ramp_window_uses_night_setpoint():
    """Inside the ramp window (lights still off, < prep_minutes until on) the
    controller should run, but against the night-shifted setpoint."""
    cfg = default_config()
    # Lights off, just inside the ramp-up window. VPD slightly above the
    # night-shifted setpoint (= upper_band + night_offset = 1.2 - 0.3 = 0.9).
    inp = default_input(
        lights_on=False,
        minutes_until_off=720.0,
        minutes_until_on=cfg.lights_off_prep_minutes - 5.0,
        vpd=1.0,  # 0.1 kPa above night setpoint of 0.9
    )
    out = step(PIState(), inp)
    assert out.reason is Reason.PI_ACTIVE
    # Setpoint reported should match the night shift.
    assert out.setpoint_vpd == pytest.approx(0.9, abs=1e-9)


def test_lights_on_uses_day_setpoint():
    inp = default_input(lights_on=True, vpd=1.30)
    out = step(PIState(), inp)
    assert out.setpoint_vpd == pytest.approx(1.2, abs=1e-9)


# ---------------------------------------------------------------------------
# RH ceiling guard
# ---------------------------------------------------------------------------


def test_rh_above_ceiling_forces_zero_even_with_high_vpd_error():
    inp = default_input(
        vpd=2.5,  # nominally drives u to saturation
        rh=70.0,  # well above the band's upper edge of 55
        stage_humidity_band=(40.0, 55.0),
    )
    out = step(PIState(), inp)
    assert out.u == 0.0
    assert out.plug_on is False
    assert out.reason is Reason.RH_CEILING


def test_rh_at_ceiling_does_not_trigger():
    """Boundary-inclusive band semantics — RH exactly at the upper edge is
    still "in band", consistent with band_status('ok' iff lo <= v <= hi)."""
    inp = default_input(
        vpd=2.5,
        rh=55.0,  # exactly at upper edge
        stage_humidity_band=(40.0, 55.0),
    )
    out = step(PIState(), inp)
    assert out.reason is Reason.PI_ACTIVE  # ceiling did NOT fire


def test_rh_ceiling_freezes_integrator():
    cfg = default_config()
    state = PIState(
        integral=15.0,
        last_tick_ts=T0 - timedelta(seconds=30),
        plug_on_for_threshold=False,
    )
    # 30 ticks of high VPD error but RH well above ceiling — integrator must not grow.
    final, _ = run_n(
        state,
        lambda _i, now: default_input(
            now=now, vpd=2.5, rh=80.0, stage_humidity_band=(40.0, 55.0)
        ),
        cfg,
        n=30,
        dt_s=30.0,
    )
    assert final.integral == pytest.approx(15.0, abs=1e-9)


def test_missing_rh_does_not_block_pi(monkeypatch):
    # If RH sensor is unavailable, the ceiling guard is bypassed (best-effort);
    # the loop falls back to the existing VPD-only logic. Documented behavior.
    inp = default_input(rh=None, vpd=1.30)
    out = step(PIState(), inp)
    assert out.reason is Reason.PI_ACTIVE


# ---------------------------------------------------------------------------
# Normal operation
# ---------------------------------------------------------------------------


def test_zero_error_with_zero_integral_yields_zero_output():
    inp = default_input(vpd=1.20)  # exactly at upper edge → setpoint
    out = step(PIState(), inp)
    assert out.error == pytest.approx(0.0, abs=1e-9)
    assert out.u == pytest.approx(0.0, abs=1e-9)


def test_positive_error_drives_u_up():
    # vpd well above setpoint so P-term clears the sub-threshold cutoff
    inp = default_input(vpd=2.0)  # error +0.8 → p_term 8 (kc=10) → u=8 > threshold=5
    out = step(PIState(), inp)
    assert out.error > 0
    assert out.u > 0
    assert out.plug_on is True


def test_negative_error_with_zero_integral_yields_zero_u():
    inp = default_input(vpd=1.0)  # below setpoint
    out = step(PIState(), inp)
    assert out.error < 0
    assert out.u == pytest.approx(0.0, abs=1e-9)  # clamped at 0


# ---------------------------------------------------------------------------
# Plug threshold + hysteresis
# ---------------------------------------------------------------------------


def test_below_threshold_means_plug_off():
    cfg = default_config(
        intensity_threshold=20.0, threshold_hysteresis=2.0, kc=1.0, ki=0.0
    )
    # error = 1.20-1.21 = -0.01... wait we need positive small error to get small u.
    # error 0.05, kc=1.0 → u=0.05 → well below threshold of 20.
    inp = default_input(vpd=1.25)
    out = step(PIState(), inp, cfg)
    assert out.u < cfg.intensity_threshold
    assert out.plug_on is False


def test_above_threshold_means_plug_on():
    cfg = default_config(
        intensity_threshold=5.0, threshold_hysteresis=1.0, kc=10.0, ki=0.0
    )
    inp = default_input(vpd=1.50)  # error 0.30, kc=10 → u=3.0... still below 5.
    # Bump error higher.
    inp = default_input(vpd=2.20)  # error 1.00, u=10 > threshold
    out = step(PIState(), inp, cfg)
    assert out.u > cfg.intensity_threshold + cfg.threshold_hysteresis / 2
    assert out.plug_on is True


def test_threshold_hysteresis_no_chatter():
    """Once plug turns on, must require u to drop below
    (threshold - hysteresis/2) before turning off — preventing chatter
    when u oscillates around the threshold."""
    cfg = default_config(
        intensity_threshold=10.0, threshold_hysteresis=4.0, kc=10.0, ki=0.0
    )
    state = PIState()
    # Drive u above threshold + hysteresis/2 → plug on.
    out = step(state, default_input(vpd=2.40), cfg)  # error 1.20 → u=12
    assert out.plug_on is True
    state = out.new_state
    # Now drop u to inside the hysteresis band: > threshold - hysteresis/2 but < threshold.
    # threshold=10, hysteresis=4 → off-edge=8, on-edge=12. u=9 should keep plug on.
    out = step(state, default_input(vpd=2.10), cfg)  # error 0.90 → u=9
    assert 8.0 < out.u < 12.0
    assert out.plug_on is True, "plug must not chatter inside hysteresis band"
    state = out.new_state
    # Drop further below the lower hysteresis edge → plug off.
    out = step(state, default_input(vpd=1.90), cfg)  # error 0.70 → u=7 < 8
    assert out.plug_on is False


# ---------------------------------------------------------------------------
# Anti-windup
# ---------------------------------------------------------------------------


def test_integrator_clamp_under_sustained_saturation():
    cfg = default_config(kc=10.0, ki=1.0, integrator_clamp=50.0)
    # Drive 30 ticks of huge positive error — integrator should clamp at 50.
    final, _ = run_n(
        PIState(),
        lambda _i, now: default_input(now=now, vpd=5.0),  # error = 3.8
        cfg,
        n=30,
        dt_s=30.0,
    )
    assert abs(final.integral) <= cfg.integrator_clamp + 1e-9


def test_integrator_unwinds_on_error_reversal():
    cfg = default_config(kc=10.0, ki=1.0, integrator_clamp=50.0)
    # Phase 1: saturate positive.
    state, _ = run_n(
        PIState(),
        lambda _i, now: default_input(now=now, vpd=5.0),
        cfg,
        n=30,
        dt_s=30.0,
    )
    integral_after_sat = state.integral
    assert integral_after_sat > 0
    # Phase 2: reverse error (very wet) — integrator must shrink.
    state2, _ = run_n(
        state,
        lambda _i, now: default_input(now=now, vpd=0.3),  # error = -0.9
        cfg,
        n=30,
        dt_s=30.0,
    )
    assert state2.integral < integral_after_sat


def test_anti_windup_release_does_not_overshoot_to_max():
    """After saturation, when error drops to zero and integrator is positive,
    u should be the integrator's contribution — not a fresh kick to 100."""
    cfg = default_config(kc=10.0, ki=0.5, integrator_clamp=20.0)
    state, _ = run_n(
        PIState(),
        lambda _i, now: default_input(now=now, vpd=3.0),  # saturate
        cfg,
        n=30,
        dt_s=30.0,
    )
    # Now error = 0; only integrator drives u.
    out = step(state, default_input(vpd=1.20), cfg)
    assert out.u <= cfg.integrator_clamp + 1e-9


# ---------------------------------------------------------------------------
# Time-step invariance
# ---------------------------------------------------------------------------


def test_dt_invariance_30s_vs_60s_over_equal_walltime():
    """Two minutes of constant error → integrator accumulates same area
    whether we sampled it at 30 s or 60 s cadence. Pre-seed last_tick_ts
    so both runs accumulate the same number of dt windows."""
    cfg = default_config(kc=0.0, ki=1.0, integrator_clamp=1e6)  # pure-I to isolate

    def err_input(_i, now):
        return default_input(now=now, vpd=1.30)  # error = +0.10

    seed_30 = PIState(
        integral=0.0,
        last_tick_ts=T0 - timedelta(seconds=30),
        plug_on_for_threshold=False,
    )
    seed_60 = PIState(
        integral=0.0,
        last_tick_ts=T0 - timedelta(seconds=60),
        plug_on_for_threshold=False,
    )
    state_30, _ = run_n(
        seed_30, err_input, cfg, n=4, dt_s=30.0
    )  # 4 windows × 30s = 120s
    state_60, _ = run_n(
        seed_60, err_input, cfg, n=2, dt_s=60.0
    )  # 2 windows × 60s = 120s
    assert state_30.integral == pytest.approx(state_60.integral, rel=1e-6)


def test_first_tick_skips_integral_with_no_dt():
    cfg = default_config()
    # vpd far above setpoint so P-term clears the sub-threshold cutoff.
    out = step(
        PIState(), default_input(vpd=2.0), cfg
    )  # error +0.8 → p_term 8 > threshold
    # Fresh state: last_tick_ts is None → no dt → no integral update.
    assert out.new_state.integral == pytest.approx(0.0, abs=1e-9)
    # P-term still produces u based on error.
    assert out.u > 0


def test_clock_jump_backwards_does_not_grow_integrator():
    cfg = default_config(kc=0.0, ki=1.0)
    # Seed: last_tick at T0; now ticks at T0 - 60s (backwards jump).
    state = PIState(integral=10.0, last_tick_ts=T0, plug_on_for_threshold=False)
    inp = default_input(now=T0 - timedelta(seconds=60), vpd=1.30)
    out = compute(cfg, state, inp)
    # Integrator unchanged (negative dt rejected) but timestamp updated.
    assert out.new_state.integral == pytest.approx(10.0, abs=1e-9)


def test_huge_dt_does_not_blow_up_integrator():
    """A long gap (e.g. 1 hour) should be capped — controller treats it as a
    bounded tick to prevent integrator explosion after sleep/restart."""
    cfg = default_config(kc=0.0, ki=1.0, integrator_clamp=100.0)
    state = PIState(integral=0.0, last_tick_ts=T0, plug_on_for_threshold=False)
    inp = default_input(now=T0 + timedelta(hours=1), vpd=1.30)
    out = compute(cfg, state, inp)
    assert abs(out.new_state.integral) <= cfg.integrator_clamp + 1e-9


# ---------------------------------------------------------------------------
# Stage flips: setpoint changes don't reset integrator
# ---------------------------------------------------------------------------


def test_stage_flip_changes_setpoint_without_resetting_integrator():
    cfg = default_config(kc=10.0, ki=1.0)
    # Run a few ticks at veg band to accumulate integrator.
    state, _ = run_n(
        PIState(),
        lambda _i, now: default_input(now=now, vpd=1.30, stage_vpd_band=(0.8, 1.2)),
        cfg,
        n=5,
        dt_s=30.0,
    )
    integral_pre = state.integral
    assert integral_pre > 0
    # Flip to flower_late band (1.2, 1.5). Setpoint shifts to 1.5; same VPD now
    # gives negative error.
    out = step(state, default_input(vpd=1.30, stage_vpd_band=(1.2, 1.5)), cfg)
    assert out.setpoint_vpd == pytest.approx(1.5, abs=1e-9)
    # Integrator carries across the flip (it'll start unwinding from there).
    # Just assert it wasn't reset to 0.
    assert out.new_state.integral != pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Output contract — every successful tick produces the fields the shadow
# log needs.
# ---------------------------------------------------------------------------


def test_output_contract_fields_present():
    out = step(PIState(), default_input(vpd=1.30))
    # Every output must carry these for log emission, even in failsafe.
    for attr in (
        "new_state",
        "u",
        "plug_on",
        "setpoint_vpd",
        "error",
        "p_term",
        "i_term",
        "reason",
    ):
        assert hasattr(out, attr), f"PIOutput missing field {attr!r}"
    assert isinstance(out.new_state, PIState)
    assert isinstance(out.reason, Reason)


def test_failsafe_output_still_carries_full_contract():
    out = step(PIState(), default_input(vpd=None))
    # Even in failsafe, the log fields are populated (with sensible zeros).
    assert out.error == 0.0
    assert out.p_term == 0.0
    assert out.i_term == 0.0
    assert out.u == 0.0
    assert out.plug_on is False
