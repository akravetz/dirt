"""Cross-actuator allocation for tent humidity control.

The humidifier PI loop computes how much mist would help VPD. This module
decides whether that request should reach the H7142 now, given the exhaust
fan's current duty and the RH safety envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HumidifierAllocationConfig:
    fan_floor_pct: int
    fan_max_pct: int
    fan_high_vpd_margin_kpa: float
    fan_sensor_stale_s: int
    rh_reenable_buffer_pct: float


@dataclass(frozen=True)
class HumidifierAllocationInput:
    now: datetime
    requested_u_pct: float
    requested_plug_on: bool
    vpd: float | None
    rh: float | None
    fan_pct: float | None
    fan_age_s: float | None
    vpd_band: tuple[float, float]
    rh_band: tuple[float, float]


@dataclass(frozen=True)
class HumidifierAllocationOutput:
    u_pct: float
    plug_on: bool
    reason: str
    fan_pct: float | None
    fan_age_s: float | None


def allocate_humidifier_output(
    cfg: HumidifierAllocationConfig,
    inp: HumidifierAllocationInput,
) -> HumidifierAllocationOutput:
    """Allocate PI mist demand after cross-actuator constraints.

    The fan is treated as the first relief path whenever it is already above
    its ventilation floor and either:
      - it is saturated at the configured maximum,
      - RH is still inside the near-ceiling re-enable buffer, or
      - VPD is only marginally high, where reducing exhaust is cheaper than
        adding mist against elevated exhaust.

    Missing/stale fan duty is fail-open for mist control; the existing PI
    stale-sensor and RH-ceiling guards still protect the humidifier path.
    """
    if not inp.requested_plug_on or inp.requested_u_pct <= 0:
        return HumidifierAllocationOutput(
            u_pct=0.0,
            plug_on=False,
            reason="pi_off",
            fan_pct=inp.fan_pct,
            fan_age_s=inp.fan_age_s,
        )

    if (
        inp.fan_pct is None
        or inp.fan_age_s is None
        or inp.fan_age_s > cfg.fan_sensor_stale_s
    ):
        return HumidifierAllocationOutput(
            u_pct=inp.requested_u_pct,
            plug_on=True,
            reason="fan_unknown_passthrough",
            fan_pct=inp.fan_pct,
            fan_age_s=inp.fan_age_s,
        )

    fan_elevated = inp.fan_pct > cfg.fan_floor_pct
    if not fan_elevated:
        return HumidifierAllocationOutput(
            u_pct=inp.requested_u_pct,
            plug_on=True,
            reason="pi_request",
            fan_pct=inp.fan_pct,
            fan_age_s=inp.fan_age_s,
        )

    _vpd_lo, vpd_hi = inp.vpd_band
    _rh_lo, rh_hi = inp.rh_band
    near_rh_ceiling = (
        inp.rh is not None and inp.rh >= rh_hi - cfg.rh_reenable_buffer_pct
    )
    fan_saturated = inp.fan_pct >= cfg.fan_max_pct
    marginal_high_vpd = (
        inp.vpd is not None and inp.vpd <= vpd_hi + cfg.fan_high_vpd_margin_kpa
    )

    if fan_saturated or near_rh_ceiling or marginal_high_vpd:
        return HumidifierAllocationOutput(
            u_pct=0.0,
            plug_on=False,
            reason="fan_relief_first",
            fan_pct=inp.fan_pct,
            fan_age_s=inp.fan_age_s,
        )

    return HumidifierAllocationOutput(
        u_pct=inp.requested_u_pct,
        plug_on=True,
        reason="pi_request",
        fan_pct=inp.fan_pct,
        fan_age_s=inp.fan_age_s,
    )
