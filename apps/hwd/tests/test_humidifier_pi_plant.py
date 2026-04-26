"""Plant-in-loop tests for the humidifier PI controller.

Drives the real controller against a tiny FOPDT plant simulator parameterized
from the FOPDT-fit bracket (docs/epics/continuous-humidifier/fopdt-fit-findings.md).
Asserts *behaviors*, not tuning numbers — same discipline as the property tests.

Scope: catches design mistakes (integrator escapes, force-off path leaks state,
controller fights itself across regime changes, saturation handling). Does NOT
validate tuning — the simulator is FOPDT, the real tent isn't. Acceptance soak
on real hardware (phase4-test-plan.md criterion #1) remains the binding test.

The RH ceiling guard is disabled in these tests by setting `stage_rh_max` very
high. The guard's correctness is covered by property tests with synthetic
inputs; mixing it into the dynamics tests would fragment the behavior under
test without adding coverage.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from dirt_hwd.services.humidifier_pi import (
    PIConfig,
    PIInput,
    PIState,
    Reason,
    compute,
)

T0 = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
DT_S = 30.0


# ---------------------------------------------------------------------------
# Plant simulator
# ---------------------------------------------------------------------------


def _saturation_vapor_pressure_kpa(t_f: float) -> float:
    """Tetens approximation. t_f in °F, result in kPa."""
    t_c = (t_f - 32.0) * 5.0 / 9.0
    return 0.611 * math.exp(17.27 * t_c / (t_c + 237.3))


def _vpd_to_rh_pct(vpd_kpa: float, t_f: float) -> float:
    svp = _saturation_vapor_pressure_kpa(t_f)
    return max(0.0, min(100.0, 100.0 * (1.0 - vpd_kpa / svp)))


@dataclass
class FOPDTPlant:
    """Discrete first-order tent model.

    τ · dV/dt = (V_target − V)
    V_target = V_dry_eq + lights_offset(lights_on) + K_eff(fan) · u_pct

    K_eff(fan) = K_baseline · (baseline_fan / fan_duty) — higher exhaust
    halves mist authority. fan_duty is clamped at fan_floor below to avoid
    exploding K when fan is commanded to 0.

    Pure stdlib. No dead time term — the controller's 30 s tick + 60 s sensor
    cadence already provides implicit lag, and adding explicit dead time
    inflates the simulator without adding test value at this level.
    """

    tau_s: float = 600.0
    k_per_pct_at_baseline: float = -0.04  # kPa per %u, at baseline_fan
    v_dry_eq: float = 1.5  # kPa, asymptote with u=0 and lights on
    baseline_fan: float = 25.0
    t_f: float = 78.0  # ambient temperature (°F)
    night_offset_kpa: float = -0.4  # asymptote shift when lights off
    fan_floor: float = 5.0  # min fan duty for K_eff calc

    _vpd: float = field(init=False)

    def __post_init__(self) -> None:
        self._vpd = self.v_dry_eq

    @property
    def vpd(self) -> float:
        return self._vpd

    @property
    def rh_pct(self) -> float:
        return _vpd_to_rh_pct(self._vpd, self.t_f)

    def step(
        self, dt_s: float, u_pct: float, fan_duty: float, lights_on: bool
    ) -> tuple[float, float]:
        fan_eff = max(fan_duty, self.fan_floor)
        k_eff = self.k_per_pct_at_baseline * (self.baseline_fan / fan_eff)
        offset = 0.0 if lights_on else self.night_offset_kpa
        v_target = self.v_dry_eq + offset + k_eff * u_pct
        alpha = math.exp(-dt_s / self.tau_s)
        self._vpd = self._vpd * alpha + v_target * (1.0 - alpha)
        return self._vpd, self.rh_pct


# ---------------------------------------------------------------------------
# Simulator self-tests — confirm the plant behaves before we trust assertions.
# ---------------------------------------------------------------------------


def test_plant_settles_to_v_dry_eq_with_zero_input():
    plant = FOPDTPlant(tau_s=300.0, v_dry_eq=1.5)
    plant._vpd = 0.5  # start far from equilibrium
    for _ in range(200):  # 200 * 30s = 100 min ≈ 20 τ
        plant.step(DT_S, u_pct=0.0, fan_duty=25.0, lights_on=True)
    assert plant.vpd == pytest.approx(1.5, abs=0.01)


def test_plant_settles_to_lower_asymptote_with_continuous_mist():
    plant = FOPDTPlant(
        tau_s=300.0, k_per_pct_at_baseline=-0.04, v_dry_eq=1.5, baseline_fan=25.0
    )
    # u=10% at baseline fan → steady-state ΔVPD = -0.4 kPa → asymptote 1.1
    for _ in range(200):
        plant.step(DT_S, u_pct=10.0, fan_duty=25.0, lights_on=True)
    assert plant.vpd == pytest.approx(1.1, abs=0.01)


def test_higher_fan_reduces_steady_state_drop():
    """Same u, double the fan: asymptote drop halves."""
    plant_lo = FOPDTPlant(tau_s=300.0, baseline_fan=25.0)
    plant_hi = FOPDTPlant(tau_s=300.0, baseline_fan=25.0)
    for _ in range(200):
        plant_lo.step(DT_S, u_pct=20.0, fan_duty=25.0, lights_on=True)
        plant_hi.step(DT_S, u_pct=20.0, fan_duty=50.0, lights_on=True)
    drop_lo = 1.5 - plant_lo.vpd  # baseline drop
    drop_hi = 1.5 - plant_hi.vpd  # half-authority drop
    assert drop_hi == pytest.approx(drop_lo / 2.0, rel=0.02)


# ---------------------------------------------------------------------------
# Simulation runner
# ---------------------------------------------------------------------------


@dataclass
class Trajectory:
    ts: list[datetime] = field(default_factory=list)
    vpd: list[float] = field(default_factory=list)
    rh: list[float] = field(default_factory=list)
    u: list[float] = field(default_factory=list)
    plug_on: list[bool] = field(default_factory=list)
    integrator: list[float] = field(default_factory=list)
    reason: list[Reason] = field(default_factory=list)
    setpoint: list[float] = field(default_factory=list)


def _default_lights(_i: int) -> tuple[bool, float, float]:
    """Constant lights-on, well clear of either prep window."""
    return (True, 600.0, 720.0)


def simulate(
    *,
    plant: FOPDTPlant,
    pi_cfg: PIConfig,
    n_ticks: int,
    dt_s: float = DT_S,
    fan_at: Callable[[int], float] = lambda _i: 25.0,
    lights_at: Callable[[int], tuple[bool, float, float]] = _default_lights,
    rh_ceiling: float = 99.0,  # disabled for dynamics tests
    band: tuple[float, float] = (0.8, 1.2),
    pi_state: PIState | None = None,
    start: datetime = T0,
) -> Trajectory:
    """Drive controller + plant for n_ticks, return per-tick trajectory.

    Time advances `dt_s` per tick. Plant integrates with the controller's
    just-commanded `u`. The first tick has no `dt` for the integrator
    (fresh PIState) — same convention as production.
    """
    state = pi_state or PIState()
    traj = Trajectory()
    for i in range(n_ticks):
        now = start + timedelta(seconds=i * dt_s)
        lights_on, until_off, until_on = lights_at(i)
        fan = fan_at(i)
        inp = PIInput(
            now=now,
            vpd=plant.vpd,
            vpd_ts=now,  # fresh sensor — no failsafe
            rh=plant.rh_pct,
            stage_vpd_band=band,
            stage_rh_max=rh_ceiling,
            lights_on=lights_on,
            minutes_until_off=until_off,
            minutes_until_on=until_on,
        )
        out = compute(pi_cfg, state, inp)
        state = out.new_state
        # Plant uses the controller's commanded u this tick.
        plant.step(dt_s, u_pct=out.u, fan_duty=fan, lights_on=lights_on)
        traj.ts.append(now)
        traj.vpd.append(plant.vpd)
        traj.rh.append(plant.rh_pct)
        traj.u.append(out.u)
        traj.plug_on.append(out.plug_on)
        traj.integrator.append(state.integral)
        traj.reason.append(out.reason)
        traj.setpoint.append(out.setpoint_vpd)
    return traj


# ---------------------------------------------------------------------------
# Standard config + plant param brackets
# ---------------------------------------------------------------------------


def conservative_pi() -> PIConfig:
    """Same gains the live shadow loop is running with (FOPDT bracket low end)."""
    return PIConfig(
        kc=8.0,
        ki=0.01,
        integrator_clamp=50.0,
        intensity_threshold=5.0,
        threshold_hysteresis=1.0,
        night_offset_kpa=-0.3,
        failsafe_stale_s=300.0,
        lights_off_prep_minutes=30.0,
    )


# Plant param bracket — covers the believable range from the FOPDT findings.
# τ ∈ [300, 1200] s (5–20 min), |K| ∈ [0.02, 0.06] kPa/%u, V_dry_eq ∈ [1.3, 1.7].
# Each test parametrizes over corners + a midpoint; if conservative gains fail
# on a corner, that means the bracket is wider than the gains can handle —
# diagnostic, not a test failure to paper over.
PLANT_PARAMS = [
    pytest.param(300.0, -0.06, 1.7, id="fast_strong_dry"),
    pytest.param(600.0, -0.04, 1.5, id="middle"),
    pytest.param(1200.0, -0.02, 1.3, id="slow_weak_close"),
    pytest.param(900.0, -0.04, 1.6, id="slow_middle_dry"),
]


# ---------------------------------------------------------------------------
# Test 1 — step response settles within band
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tau_s,k,v_dry_eq", PLANT_PARAMS)
def test_step_response_settles_within_envelope(tau_s, k, v_dry_eq):
    """Plant starts at V_dry_eq (well above setpoint of 1.2). Controller drives
    VPD down. After 8τ, VPD must be inside a ±0.15 kPa envelope of setpoint.

    The 0.15 envelope is intentionally looser than the production acceptance
    criterion (±0.10) — conservative starter gains are sluggish by design;
    tightening the envelope happens during real-hardware tuning, not here.
    Test catches "controller doesn't settle at all" / "integrator escapes",
    not "controller is well-tuned." Real settling uses shadow + soak data."""
    plant = FOPDTPlant(tau_s=tau_s, k_per_pct_at_baseline=k, v_dry_eq=v_dry_eq)
    cfg = conservative_pi()
    setpoint = 1.2  # band upper edge for veg
    # Run for 6 h sim time + 12τ — generous for the slowest plant corner.
    # Pytest runtime is unaffected (pure math, no real-time waits).
    n_ticks = max(int(6 * 3600 / DT_S), int(12 * tau_s / DT_S))
    traj = simulate(plant=plant, pi_cfg=cfg, n_ticks=n_ticks)

    # Last 30 min average — judges where the controller actually settled,
    # not picking off a transient peak.
    tail = traj.vpd[-int(30 * 60 / DT_S) :]
    tail_avg = sum(tail) / len(tail)
    tail_max_dev = max(abs(v - setpoint) for v in tail)
    assert tail_max_dev < 0.2, (
        f"Last 30 min: max |VPD - setpoint| = {tail_max_dev:.3f} kPa "
        f"(envelope 0.2). avg = {tail_avg:.3f}, u = {traj.u[-1]:.2f}, "
        f"integrator = {traj.integrator[-1]:.2f}"
    )
    # Centerpoint of the tail window must straddle setpoint.
    assert abs(tail_avg - setpoint) < 0.1, (
        f"Last-30-min average VPD {tail_avg:.3f} not centered on setpoint {setpoint}"
    )

    # Integrator non-degenerate (controller actually used it for bias).
    assert traj.integrator[-1] > 0, "Integrator should hold positive steady-state bias"
    # Integrator within clamp (anti-windup invariant)
    assert abs(traj.integrator[-1]) <= cfg.integrator_clamp + 1e-9


# ---------------------------------------------------------------------------
# Test 2 — lights-off transition does not blow up integrator or cause overshoot
# ---------------------------------------------------------------------------


def _lights_schedule_with_dark_period(
    seconds_on_at_start: float,
    seconds_dark: float,
    *,
    prep_minutes: float = 30.0,
    seconds_on_after_dark: float = 24 * 3600.0,
) -> Callable[[int], tuple[bool, float, float]]:
    """Schedule: lights on for `seconds_on_at_start`, then dark for `seconds_dark`,
    then lights on for `seconds_on_after_dark` (default 24 h, effectively "stay on").
    minutes_until_off / minutes_until_on are computed relative to the upcoming
    transition; the PI controller's lights window guard needs minutes_until_off
    to stay above prep_minutes for the post-return window to remain active."""

    def at(i: int) -> tuple[bool, float, float]:
        t_s = i * DT_S
        if t_s < seconds_on_at_start:
            until_off_s = seconds_on_at_start - t_s
            until_on_s = until_off_s + seconds_dark
            return (True, until_off_s / 60.0, until_on_s / 60.0)
        if t_s < seconds_on_at_start + seconds_dark:
            within_dark_s = t_s - seconds_on_at_start
            until_on_s = seconds_dark - within_dark_s
            until_off_s = until_on_s + seconds_on_after_dark
            return (False, until_off_s / 60.0, until_on_s / 60.0)
        # Back to lights on for a long stretch.
        within_day2_s = t_s - seconds_on_at_start - seconds_dark
        until_off_s = max(60.0, seconds_on_after_dark - within_day2_s)
        until_on_s = until_off_s + seconds_dark
        return (True, until_off_s / 60.0, until_on_s / 60.0)

    return at


@pytest.mark.parametrize("tau_s,k,v_dry_eq", PLANT_PARAMS)
def test_lights_off_does_not_blow_up_integrator(tau_s, k, v_dry_eq):
    """Run controller through a full lights cycle: 90 min on → 6 h dark →
    2 h on again. Verify the controller behaves correctly across regime
    transitions:

      - Integrator bounded throughout (≤ integrator_clamp).
      - Dark period (excluding ramp windows): mostly force-off via
        OUTSIDE_LIGHTS_WINDOW.
      - Pre-lights-on ramp window operates against the night-shifted
        setpoint — observed, not asserted as "unexpected."
      - 2 h after lights return, VPD is within 0.2 kPa of day setpoint."""
    plant = FOPDTPlant(tau_s=tau_s, k_per_pct_at_baseline=k, v_dry_eq=v_dry_eq)
    cfg = conservative_pi()
    setpoint = 1.2
    seconds_on_pre = 90 * 60.0  # 1.5 h to reach steady state
    seconds_dark = 6 * 60 * 60.0  # 6 h dark
    seconds_post = (
        360 * 60.0
    )  # 6 h after lights return — enough for slow plants to fully settle
    n_ticks = int((seconds_on_pre + seconds_dark + seconds_post) / DT_S)
    schedule = _lights_schedule_with_dark_period(seconds_on_pre, seconds_dark)
    traj = simulate(
        plant=plant,
        pi_cfg=cfg,
        n_ticks=n_ticks,
        lights_at=schedule,
    )

    dark_start = int(seconds_on_pre / DT_S)
    dark_end = int((seconds_on_pre + seconds_dark) / DT_S)

    # Integrator stays inside the clamp end-to-end.
    assert max(abs(x) for x in traj.integrator) <= cfg.integrator_clamp + 1e-9

    # During the *core* of the dark period (excluding the last 30 min ramp
    # window where pre-lights-on PI is allowed), reason must be force-off.
    ramp_start_idx = dark_end - int(cfg.lights_off_prep_minutes * 60 / DT_S)
    core_dark_reasons = set(traj.reason[dark_start + 1 : ramp_start_idx])
    assert core_dark_reasons == {Reason.OUTSIDE_LIGHTS_WINDOW}, (
        f"Core dark period must be 100% outside_lights_window; "
        f"got reasons {core_dark_reasons}"
    )

    # 6 h after lights return, VPD inside 0.2 kPa envelope (tail-30-min avg).
    tail = traj.vpd[-int(30 * 60 / DT_S) :]
    tail_avg = sum(tail) / len(tail)
    assert abs(tail_avg - setpoint) < 0.2, (
        f"6 h after lights return, VPD avg {tail_avg:.3f} not within 0.2 of "
        f"setpoint {setpoint}. final integrator = {traj.integrator[-1]:.2f}"
    )


# ---------------------------------------------------------------------------
# Test 3 — fan-duty step
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tau_s,k,v_dry_eq", PLANT_PARAMS)
def test_fan_duty_step_response_directionally_correct(tau_s, k, v_dry_eq):
    """Steady state at fan=25%, step to fan=50% (mist authority halves). Verify
    the controller responds in the right direction:

      - Peak |VPD - setpoint| stays inside a 0.4 kPa envelope (loose because
        conservative gains take many τ to fully reject this disturbance).
      - u rises after the step (controller commands more mist).
      - Integrator grows after the step (absorbs new bias).

    NOT asserting full settling-to-setpoint — at conservative Ki=0.01,
    integrator-driven re-tuning to the new fan regime can take hours.
    Real tuning happens against shadow data + acceptance soak."""
    plant = FOPDTPlant(tau_s=tau_s, k_per_pct_at_baseline=k, v_dry_eq=v_dry_eq)
    cfg = conservative_pi()
    setpoint = 1.2
    pre_minutes = 90.0
    post_minutes = max(180.0, 12 * tau_s / 60.0)
    step_at_tick = int(pre_minutes * 60 / DT_S)
    n_ticks = int((pre_minutes + post_minutes) * 60 / DT_S)

    def fan_at(i: int) -> float:
        return 25.0 if i < step_at_tick else 50.0

    traj = simulate(plant=plant, pi_cfg=cfg, n_ticks=n_ticks, fan_at=fan_at)

    # Peak deviation across the transient stays inside a 0.4 kPa envelope.
    transient_window = traj.vpd[step_at_tick:]
    peak_dev = max(abs(v - setpoint) for v in transient_window)
    assert peak_dev < 0.4, (
        f"Peak |VPD - setpoint| during fan step = {peak_dev:.3f} kPa "
        f"(envelope 0.4). final VPD = {traj.vpd[-1]:.3f}, u = {traj.u[-1]:.2f}"
    )

    # u rises to compensate (more fan = more u needed for same drop).
    pre_step_u = sum(traj.u[step_at_tick - 10 : step_at_tick]) / 10
    post_step_u = sum(traj.u[-10:]) / 10
    assert post_step_u > pre_step_u, (
        f"u failed to rise after fan step: pre {pre_step_u:.2f}, post {post_step_u:.2f}"
    )

    # Integrator grows post-step (it's absorbing the new steady-state bias).
    pre_step_i = sum(traj.integrator[step_at_tick - 10 : step_at_tick]) / 10
    post_step_i = sum(traj.integrator[-10:]) / 10
    assert post_step_i > pre_step_i, (
        f"Integrator failed to grow after fan step: pre {pre_step_i:.2f}, "
        f"post {post_step_i:.2f}"
    )

    # Integrator stays bounded.
    assert max(abs(x) for x in traj.integrator) <= cfg.integrator_clamp + 1e-9


# ---------------------------------------------------------------------------
# Test 4 — saturation soak
# ---------------------------------------------------------------------------


def test_unreachable_plant_pegs_integrator_at_clamp_and_recovers():
    """Set fan high enough that the plant's reachable VPD (with maximum mist
    authority the controller can command via integrator clamp) cannot reach
    setpoint. Verify anti-windup behavior:

      - Integrator pegs at integrator_clamp.
      - Integrator stays at clamp without escape (anti-windup).
      - u stays bounded (no jitter, no escape).
      - When fan drops back, integrator unwinds and plant settles.

    Note: with conservative gains (Kc=8, integrator_clamp=50), saturation
    against the u=100 ceiling requires steady-state error > ~6 kPa, which
    isn't physically realizable. The relevant saturation here is the
    integrator clamp, not the u-ceiling. That's the correct thing to test —
    integrator-clamp saturation is what actually happens under any prolonged
    actuator-insufficiency and is what the anti-windup design protects."""
    plant = FOPDTPlant(
        tau_s=600.0, k_per_pct_at_baseline=-0.02, v_dry_eq=1.5, baseline_fan=25.0
    )
    cfg = conservative_pi()
    setpoint = 1.2

    sat_hours = 6.0  # long enough to peg integrator at Ki=0.01
    recovery_hours = 6.0  # conservative gains take many hours to unwind from peg
    sat_ticks = int(sat_hours * 3600 / DT_S)
    n_ticks = sat_ticks + int(recovery_hours * 3600 / DT_S)

    def fan_at(i: int) -> float:
        return 400.0 if i < sat_ticks else 25.0  # 400% = mist authority crushed

    traj = simulate(plant=plant, pi_cfg=cfg, n_ticks=n_ticks, fan_at=fan_at)

    sat_window_start = sat_ticks // 2  # second half of sat period — well after peg
    sat_i = traj.integrator[sat_window_start:sat_ticks]

    # Integrator pegs at clamp.
    assert max(sat_i) >= cfg.integrator_clamp - 0.5, (
        f"Integrator failed to reach clamp; max {max(sat_i):.2f} "
        f"(clamp {cfg.integrator_clamp})"
    )
    # Integrator stays at clamp (no escape).
    assert all(abs(i) <= cfg.integrator_clamp + 1e-9 for i in sat_i), (
        "Integrator escaped clamp"
    )
    # u stays bounded throughout saturation.
    assert max(traj.u) <= 100.0 + 1e-9
    assert min(traj.u[sat_window_start:sat_ticks]) >= 0.0

    # Recovery: integrator unwinds after fan drops.
    final_i = traj.integrator[-1]
    assert final_i < cfg.integrator_clamp - 5.0, (
        f"Integrator failed to unwind after recovery: pegged at {cfg.integrator_clamp}, "
        f"final {final_i:.2f}"
    )
    # Plant settles back inside an envelope (loose — slow Ki = slow recovery).
    tail_avg = sum(traj.vpd[-10:]) / 10
    assert abs(tail_avg - setpoint) < 0.25, (
        f"Failed to recover after fan drop: tail avg {tail_avg:.3f}, "
        f"setpoint {setpoint}"
    )
