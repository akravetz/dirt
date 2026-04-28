"""Quantize PI continuous output u_pct ∈ [0, 100] into a discrete
H7142 Manual-mode mist level (1..N) with hysteresis at level boundaries.

Pure-function module — no I/O. Composes downstream of ``humidifier_pi``:
the PI controller already applied the threshold cutoff and emits
``plug_on=False`` when the device should be off; this module only decides
which level to send when ``plug_on=True``.

Hysteresis prevents limit-cycle chatter at level boundaries: once the
device is at level N, ``u_pct`` has to walk past ``boundary ± hyst`` before
we step. ``last_level`` is the trailing dispatched level (None == OFF).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class DispatchConfig:
    """Quantizer tuning. ``levels=9`` matches the deployed H7142.

    ``level_hysteresis_pct`` is one-sided: from level N, we step up at
    ``upper_edge(N) + hyst`` and step down at ``lower_edge(N) - hyst``.
    Picking it ≥ 0 and < bucket_width / 2 keeps boundaries well-defined.
    """

    levels: int = 9
    level_hysteresis_pct: float = 3.0


@dataclass(frozen=True)
class DispatchState:
    last_level: int | None = None  # None ⇒ device dispatched OFF


@dataclass(frozen=True)
class DispatchOutput:
    new_state: DispatchState
    target_level: int | None  # None ⇒ OFF
    bucket_width: float  # exposed for logging


def _bucket_width(levels: int) -> float:
    if levels <= 0:
        raise ValueError(f"levels must be positive, got {levels}")
    return 100.0 / levels


def _naive_level(u_pct: float, levels: int) -> int:
    """Bucket map: (0, w] → 1, (w, 2w] → 2, …, (>(levels-1)*w) → levels."""
    width = _bucket_width(levels)
    # ``u_pct`` here has already passed the PI threshold cutoff, so it is
    # > 0 by construction. Treat exact 0 as level 1 anyway to be defensive.
    if u_pct <= 0:
        return 1
    raw = math.ceil(u_pct / width)
    return max(1, min(levels, raw))


def quantize(
    cfg: DispatchConfig,
    state: DispatchState,
    u_pct: float,
    plug_on: bool,
) -> DispatchOutput:
    """Advance the dispatcher one tick.

    Returns the level to command (or ``None`` for OFF). ``last_level`` in
    the new state matches the level we just decided to dispatch — call
    sites that fail to actually deliver a control message must NOT use
    that returned state, since it would lie about the device.
    """
    width = _bucket_width(cfg.levels)

    if not plug_on:
        return DispatchOutput(
            new_state=DispatchState(last_level=None),
            target_level=None,
            bucket_width=width,
        )

    naive = _naive_level(u_pct, cfg.levels)

    # No hysteresis on first transition out of OFF — we have no anchor
    # level yet, so just pick the bucket u_pct lands in.
    if state.last_level is None:
        return DispatchOutput(
            new_state=replace(state, last_level=naive),
            target_level=naive,
            bucket_width=width,
        )

    # Hysteresis at the current level's boundaries:
    #   - step up to N+1 only when u_pct > N*width + hyst
    #   - step down to N-1 only when u_pct < (N-1)*width - hyst
    # Within the dead-zone, hold ``last_level`` regardless of where the
    # naive bucket math points. This eliminates 4↔5 chatter when u_pct
    # sits right at a boundary.
    last = state.last_level
    upper_edge = last * width
    lower_edge = (last - 1) * width
    hyst = cfg.level_hysteresis_pct

    step_up_blocked = naive > last and u_pct <= upper_edge + hyst
    step_down_blocked = naive < last and u_pct >= lower_edge - hyst
    target = last if (step_up_blocked or step_down_blocked) else naive

    return DispatchOutput(
        new_state=replace(state, last_level=target),
        target_level=target,
        bucket_width=width,
    )
