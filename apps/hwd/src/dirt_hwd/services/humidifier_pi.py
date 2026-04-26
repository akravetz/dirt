"""PI controller for continuous humidifier intensity (Phase 4 prep).

Pure-function module — no I/O, no actuator coupling. ``compute()`` takes
(config, state, input) and returns (new_state, output). Designed for shadow-
mode logging today and authoritative use once Phase 2/3 lands a continuous-
intensity actuator.

See:
  - docs/epics/continuous-humidifier/phase4-test-plan.md
  - docs/epics/continuous-humidifier/fopdt-fit-findings.md (gain bracket)
  - wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

# Hard cap on per-tick dt (s) used for integral updates. A long gap (sleep,
# service restart, NTP step forward) shouldn't let the integrator jump by
# hours of accumulated error in a single tick. Picked larger than a normal
# 30 s tick but small enough to behave like a bounded sample.
MAX_INTEGRAL_DT_S = 120.0


class Reason(str, Enum):
    """Why ``u`` is what it is this tick. Logged verbatim."""

    PI_ACTIVE = "pi_active"
    FAILSAFE_STALE_SENSOR = "failsafe_stale_sensor"
    OUTSIDE_LIGHTS_WINDOW = "outside_lights_window"
    RH_CEILING = "rh_ceiling"


@dataclass(frozen=True)
class PIConfig:
    """Tuning + envelope. All fields stage-independent except via inputs."""

    kc: float
    ki: float
    integrator_clamp: float  # max |I| in %u (anti-windup)
    intensity_threshold: float  # below this → plug off (sub-threshold cutoff)
    threshold_hysteresis: float  # %u; threshold ± hysteresis/2 forms the band
    night_offset_kpa: float  # negative; setpoint shift during lights-off
    failsafe_stale_s: float  # max VPD age before failsafe-OFF
    lights_off_prep_minutes: float  # margin around lights-off / lights-on


@dataclass(frozen=True)
class PIState:
    """Mutable-across-ticks controller state."""

    integral: float = 0.0
    last_tick_ts: datetime | None = None
    plug_on_for_threshold: bool = False  # tracks hysteresis band side


@dataclass(frozen=True)
class PIInput:
    """One tick's view of the world. Caller assembles from sensors + grow state."""

    now: datetime
    vpd: float | None
    vpd_ts: datetime | None
    rh: float | None  # relative humidity %; None → ceiling check skipped
    stage_vpd_band: tuple[float, float]  # (lo, hi) kPa
    stage_rh_max: float  # upper edge of stage RH band
    lights_on: bool
    minutes_until_off: float  # always positive
    minutes_until_on: float  # always positive


@dataclass(frozen=True)
class PIOutput:
    """Result of one tick. ``new_state`` carries forward; the rest is for logging."""

    new_state: PIState
    u: float  # commanded intensity %, ∈ [0, 100]
    plug_on: bool  # whether plug should be ON given threshold + hysteresis
    setpoint_vpd: float  # active setpoint after night offset
    error: float  # setpoint - vpd; 0 in failsafe paths
    p_term: float
    i_term: float
    reason: Reason


def _allowed_window(inp: PIInput, prep_minutes: float) -> bool:
    """Mirror of the existing bang-bang ``allowed`` gate.

    Allowed only:
      - lights_on AND minutes_until_off >= prep_minutes (full-day phase), OR
      - lights_off AND minutes_until_on <= prep_minutes (pre-lights-on ramp).

    Force-off everywhere else (last 30 min of day; most of dark period)."""
    if inp.lights_on:
        return inp.minutes_until_off >= prep_minutes
    return inp.minutes_until_on <= prep_minutes


def _setpoint(inp: PIInput, night_offset_kpa: float) -> float:
    upper = inp.stage_vpd_band[1]
    return upper if inp.lights_on else upper + night_offset_kpa


def _failsafe_output(
    state: PIState, now: datetime, setpoint: float, reason: Reason
) -> PIOutput:
    """Common shape for force-off paths — preserves integrator (frozen)
    and stamps last_tick_ts so dt accounting stays consistent on the next
    return to PI_ACTIVE."""
    return PIOutput(
        new_state=replace(state, last_tick_ts=now, plug_on_for_threshold=False),
        u=0.0,
        plug_on=False,
        setpoint_vpd=setpoint,
        error=0.0,
        p_term=0.0,
        i_term=state.integral,
        reason=reason,
    )


def compute(cfg: PIConfig, state: PIState, inp: PIInput) -> PIOutput:
    """Advance the PI controller one tick. Pure function.

    Order of guards (most-protective first):
      1. Failsafe — stale or missing VPD → u=0.
      2. Lights window — outside allowed window → u=0.
      3. RH ceiling — RH at/above stage cap → u=0 (envelope guard).
      4. Normal — PI on (setpoint - VPD).

    Sub-threshold cutoff + hysteresis converts the continuous ``u`` into the
    binary ``plug_on`` for the Kasa hard-off authority.
    """
    setpoint = _setpoint(inp, cfg.night_offset_kpa)

    # ---- Failsafe: stale or missing VPD --------------------------------------
    age_s: float | None = None
    if inp.vpd is not None and inp.vpd_ts is not None:
        age_s = (inp.now - inp.vpd_ts).total_seconds()
    if inp.vpd is None or age_s is None or age_s > cfg.failsafe_stale_s:
        return _failsafe_output(state, inp.now, setpoint, Reason.FAILSAFE_STALE_SENSOR)

    # ---- Lights window -------------------------------------------------------
    if not _allowed_window(inp, cfg.lights_off_prep_minutes):
        return _failsafe_output(state, inp.now, setpoint, Reason.OUTSIDE_LIGHTS_WINDOW)

    # ---- RH ceiling ---------------------------------------------------------
    # Best-effort: if RH sensor is unavailable, fall through to PI.
    if inp.rh is not None and inp.rh >= inp.stage_rh_max:
        return _failsafe_output(state, inp.now, setpoint, Reason.RH_CEILING)

    # ---- PI active -----------------------------------------------------------
    # Sign convention: positive error = "too dry" (VPD above setpoint), drives
    # u up to add mist. Matches the bang-bang's "kick on when VPD > upper edge."
    error = inp.vpd - setpoint

    # dt for integral update; skip on first tick or if the clock jumped backward.
    if state.last_tick_ts is None:
        dt_s = 0.0
    else:
        raw_dt = (inp.now - state.last_tick_ts).total_seconds()
        dt_s = max(0.0, min(raw_dt, MAX_INTEGRAL_DT_S))

    new_integral = state.integral + cfg.ki * error * dt_s
    # Anti-windup: clamp the integrator. Keeps it bounded under sustained
    # saturation; allows symmetric unwinding when error reverses.
    if new_integral > cfg.integrator_clamp:
        new_integral = cfg.integrator_clamp
    elif new_integral < -cfg.integrator_clamp:
        new_integral = -cfg.integrator_clamp

    p_term = cfg.kc * error
    i_term = new_integral
    u_raw = p_term + i_term
    u = max(0.0, min(100.0, u_raw))

    # Sub-threshold cutoff with hysteresis. The plug_on state hysteresizes the
    # transitions; once on, it stays on until u drops below threshold - half-band.
    half_band = cfg.threshold_hysteresis / 2.0
    if state.plug_on_for_threshold:
        plug_on = u >= cfg.intensity_threshold - half_band
    else:
        plug_on = u >= cfg.intensity_threshold + half_band
    if not plug_on:
        # When the plug is off we don't actually drive any mist — report u=0
        # so downstream consumers see a coherent "no output" signal. The PI
        # math is still tracked above for diagnosability via i_term.
        u = 0.0

    return PIOutput(
        new_state=PIState(
            integral=new_integral,
            last_tick_ts=inp.now,
            plug_on_for_threshold=plug_on,
        ),
        u=u,
        plug_on=plug_on,
        setpoint_vpd=setpoint,
        error=error,
        p_term=p_term,
        i_term=i_term,
        reason=Reason.PI_ACTIVE,
    )
