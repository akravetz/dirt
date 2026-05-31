#!/usr/bin/env python3
"""Analyze climate-controller JSONL for cascade RH-control metrics.

The default report is read-only: it reads climate_controller JSONL logs, compares
logged actuator targets with a pure replay through the currently checked-out
controller, and prints both metric sets in one table.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "apps/hwd/src"))
sys.path.insert(0, str(REPO / "apps/shared/src"))

from dirt_hwd.services.climate_controller import (  # noqa: E402
    ClimateInput,
    ClimateState,
    decide_climate,
)
from dirt_hwd.services.climate_policy import default_climate_policy  # noqa: E402

DEFAULT_LOG_DIR = REPO / "var/logs/climate_controller"
DEFAULT_WINDOWS = ("1d", "4d")
MAX_INTERVAL = timedelta(minutes=5)
REPLAY_STATE_RESET_GAP = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class Tick:
    ts: datetime
    stage: str
    lights_on: bool
    minutes_until_off: float | None
    minutes_until_on: float | None
    temperature_f: float | None
    temperature_age_s: float | None
    humidity_pct: float | None
    humidity_age_s: float | None
    rh_max_pct: float | None
    vpd_kpa: float | None
    vpd_age_s: float | None
    vpd_high_kpa: float | None
    current_fan_pct: int | None
    target_fan_pct: int | None
    current_humidifier_pct: float | None
    target_humidifier_pct: float | None
    current_dehumidifier_on: bool | None
    target_dehumidifier_on: bool | None
    current_heater_level: int | None
    target_heater_level: int | None
    reasons: tuple[str, ...]
    constraints: tuple[str, ...]
    conflicts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WindowMetrics:
    label: str
    source: str
    start: datetime
    end: datetime
    ticks: int
    large_fan_steps: int
    large_fan_reversals: int
    rh_in_band_pct: float | None
    median_abs_rh_error: float | None
    high_rh_exceedance_min: float
    high_vpd_exceedance_min: float
    dehumidifier_cycles: int
    humidifier_dehumidifier_conflict_avoidance_events: int
    hard_safety_overrides: int


@dataclass(frozen=True, slots=True)
class Window:
    label: str
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class FanStep:
    ts: datetime
    delta: int
    phase: str
    reason_bucket: str


def main() -> int:
    args = _parse_args()
    ticks = sorted(_read_ticks(args.logs_dir), key=lambda tick: tick.ts)
    if not ticks:
        _emit(f"No climate_controller tick events found under {args.logs_dir}")
        return 1

    windows = _windows(args, ticks)
    replay_ticks = _replay_ticks(ticks)
    metrics = []
    for label, start, end in windows:
        window = Window(label=label, start=start, end=end)
        metrics.append(
            _metrics_for_window(window, "logged_baseline", ticks, args)
        )
        metrics.append(
            _metrics_for_window(
                window,
                "new_controller_replay",
                replay_ticks,
                args,
            )
        )
    table = _format_table(metrics)
    breakdown = _format_breakdowns(windows, ticks, replay_ticks, args)
    _emit(table)
    _emit("")
    _emit(breakdown)
    _print_notes(args.logs_dir)
    if args.output is not None:
        args.output.write_text(
            f"{table}\n\n{breakdown}\n\n{_notes(args.logs_dir)}\n",
            encoding="utf-8",
        )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory containing climate_controller/*.jsonl logs.",
    )
    parser.add_argument(
        "--window",
        action="append",
        default=None,
        help="Relative window such as 1d, 4d, 12h, or 90m. Repeatable.",
    )
    parser.add_argument("--start", help="Inclusive ISO timestamp for an exact window.")
    parser.add_argument("--end", help="Exclusive ISO timestamp for an exact window.")
    parser.add_argument(
        "--anchor",
        choices=("latest", "now"),
        default="latest",
        help="End time for relative windows. Default uses the latest tick.",
    )
    parser.add_argument(
        "--large-step-pct",
        type=int,
        default=30,
        help="Fan duty change threshold for large steps and reversals.",
    )
    parser.add_argument(
        "--reversal-window-min",
        type=float,
        default=10.0,
        help="Minutes in which opposite large fan steps count as a reversal.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the report. No files are written by default.",
    )
    return parser.parse_args()


def _read_ticks(logs_dir: Path) -> Iterable[Tick]:
    for path in sorted(logs_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    _warn(
                        f"warning: skipping invalid JSON at {path}:{line_no}: {exc}",
                    )
                    continue
                tick = _tick_from_row(row)
                if tick is not None:
                    yield tick


def _tick_from_row(row: dict[str, Any]) -> Tick | None:
    if row.get("event") != "tick":
        return None
    ts = _parse_time(row.get("ts"))
    if ts is None:
        return None
    return Tick(
        ts=ts,
        stage=str(row.get("stage") or "flower_late"),
        lights_on=bool(row.get("lights_on")),
        minutes_until_off=_float(row.get("minutes_until_off")),
        minutes_until_on=_float(row.get("minutes_until_on")),
        temperature_f=_float(row.get("temperature_f")),
        temperature_age_s=_float(row.get("temperature_age_s")),
        humidity_pct=_float(row.get("humidity_pct")),
        humidity_age_s=_float(row.get("humidity_age_s")),
        rh_max_pct=_float(row.get("rh_max_pct")),
        vpd_kpa=_float(row.get("vpd_kpa")),
        vpd_age_s=_float(row.get("vpd_age_s")),
        vpd_high_kpa=_float(row.get("vpd_high_kpa")),
        current_fan_pct=_int(row.get("current_fan_pct")),
        target_fan_pct=_int(row.get("target_fan_pct")),
        current_humidifier_pct=_float(row.get("current_humidifier_pct")),
        target_humidifier_pct=_float(row.get("target_humidifier_pct")),
        current_dehumidifier_on=_bool(row.get("current_dehumidifier_on")),
        target_dehumidifier_on=_bool(row.get("target_dehumidifier_on")),
        current_heater_level=_int(row.get("current_heater_level")),
        target_heater_level=_int(row.get("target_heater_level")),
        reasons=tuple(str(reason) for reason in row.get("reasons") or ()),
        constraints=tuple(str(reason) for reason in row.get("constraints") or ()),
        conflicts=tuple(str(reason) for reason in row.get("conflicts") or ()),
    )


def _replay_ticks(ticks: list[Tick]) -> list[Tick]:
    policy = default_climate_policy()
    state = ClimateState()
    replayed: list[Tick] = []
    previous_ts: datetime | None = None
    fan_pct = policy.fan.floor_pct
    humidifier_pct = 0.0
    dehumidifier_on = False
    heater_level = 0

    for tick in ticks:
        if not _can_replay(tick):
            continue
        if (
            previous_ts is None
            or tick.ts - previous_ts > REPLAY_STATE_RESET_GAP
            or tick.ts < previous_ts
        ):
            state = ClimateState()
            fan_pct = tick.current_fan_pct or policy.fan.floor_pct
            humidifier_pct = tick.current_humidifier_pct or 0.0
            dehumidifier_on = tick.current_dehumidifier_on or False
            heater_level = tick.current_heater_level or 0

        inp = ClimateInput(
            now=tick.ts,
            stage=tick.stage,  # type: ignore[arg-type]
            lights_on=tick.lights_on,
            minutes_until_off=tick.minutes_until_off,
            minutes_until_on=tick.minutes_until_on,
            temperature_f=tick.temperature_f,
            temperature_age_s=tick.temperature_age_s,
            rh_pct=tick.humidity_pct,
            rh_age_s=tick.humidity_age_s,
            vpd_kpa=tick.vpd_kpa,
            vpd_age_s=tick.vpd_age_s,
            current_fan_pct=fan_pct,
            current_humidifier_pct=humidifier_pct,
            current_dehumidifier_on=dehumidifier_on,
            current_heater_level=heater_level,
        )
        decision = decide_climate(policy, state, inp)
        state = decision.state
        fan_pct = decision.fan_duty_pct
        humidifier_pct = decision.humidifier_pct
        dehumidifier_on = decision.dehumidifier_on
        heater_level = decision.heater_level
        previous_ts = tick.ts
        replayed.append(
            Tick(
                ts=tick.ts,
                stage=tick.stage,
                lights_on=tick.lights_on,
                minutes_until_off=tick.minutes_until_off,
                minutes_until_on=tick.minutes_until_on,
                temperature_f=tick.temperature_f,
                temperature_age_s=tick.temperature_age_s,
                humidity_pct=tick.humidity_pct,
                humidity_age_s=tick.humidity_age_s,
                rh_max_pct=tick.rh_max_pct,
                vpd_kpa=tick.vpd_kpa,
                vpd_age_s=tick.vpd_age_s,
                vpd_high_kpa=tick.vpd_high_kpa,
                current_fan_pct=inp.current_fan_pct,
                target_fan_pct=decision.fan_duty_pct,
                current_humidifier_pct=inp.current_humidifier_pct,
                target_humidifier_pct=decision.humidifier_pct,
                current_dehumidifier_on=inp.current_dehumidifier_on,
                target_dehumidifier_on=decision.dehumidifier_on,
                current_heater_level=inp.current_heater_level,
                target_heater_level=decision.heater_level,
                reasons=decision.reasons,
                constraints=decision.constraints,
                conflicts=decision.conflicts,
            )
        )
    return replayed


def _can_replay(tick: Tick) -> bool:
    return (
        tick.stage in {"veg", "flower_early", "flower_late"}
        and tick.temperature_f is not None
        and tick.temperature_age_s is not None
        and tick.humidity_pct is not None
        and tick.humidity_age_s is not None
        and tick.vpd_kpa is not None
        and tick.vpd_age_s is not None
    )


def _windows(
    args: argparse.Namespace,
    ticks: list[Tick],
) -> list[tuple[str, datetime, datetime]]:
    if args.start or args.end:
        if not (args.start and args.end):
            raise SystemExit("--start and --end must be supplied together")
        start = _require_time(args.start, "--start")
        end = _require_time(args.end, "--end")
        return [(f"{start.isoformat()}..{end.isoformat()}", start, end)]

    end = ticks[-1].ts if args.anchor == "latest" else datetime.now(UTC)
    windows = args.window or list(DEFAULT_WINDOWS)
    return [(window, end - _parse_duration(window), end) for window in windows]


def _metrics_for_window(
    window: Window,
    source: str,
    ticks: list[Tick],
    args: argparse.Namespace,
) -> WindowMetrics:
    window_ticks = [tick for tick in ticks if window.start <= tick.ts < window.end]
    intervals = _interval_minutes(window_ticks)
    rh_samples = [
        tick
        for tick in window_ticks
        if tick.humidity_pct is not None and tick.rh_max_pct is not None
    ]
    rh_errors = [
        abs(tick.humidity_pct - tick.rh_max_pct)
        for tick in rh_samples
        if tick.humidity_pct is not None and tick.rh_max_pct is not None
    ]
    fan_steps = _fan_steps(window_ticks, args.large_step_pct)
    return WindowMetrics(
        label=window.label,
        source=source,
        start=window.start,
        end=window.end,
        ticks=len(window_ticks),
        large_fan_steps=len(fan_steps),
        large_fan_reversals=len(
            _large_fan_reversals(
                fan_steps,
                timedelta(minutes=args.reversal_window_min),
            )
        ),
        rh_in_band_pct=_pct(
            sum(1 for tick in rh_samples if tick.humidity_pct <= tick.rh_max_pct),
            len(rh_samples),
        ),
        median_abs_rh_error=statistics.median(rh_errors) if rh_errors else None,
        high_rh_exceedance_min=sum(
            minutes
            for tick, minutes in intervals
            if tick.humidity_pct is not None
            and tick.rh_max_pct is not None
            and tick.humidity_pct > tick.rh_max_pct
        ),
        high_vpd_exceedance_min=sum(
            minutes
            for tick, minutes in intervals
            if tick.vpd_kpa is not None
            and tick.vpd_high_kpa is not None
            and tick.vpd_kpa > tick.vpd_high_kpa
        ),
        dehumidifier_cycles=_dehumidifier_cycles(window_ticks),
        humidifier_dehumidifier_conflict_avoidance_events=sum(
            1 for tick in window_ticks if _conflict_avoidance_observed(tick)
        ),
        hard_safety_overrides=sum(
            1 for tick in window_ticks if _hard_safety_observed(tick)
        ),
    )


def _interval_minutes(ticks: list[Tick]) -> list[tuple[Tick, float]]:
    if not ticks:
        return []
    intervals: list[tuple[Tick, float]] = []
    for index, tick in enumerate(ticks):
        if index + 1 < len(ticks):
            delta = ticks[index + 1].ts - tick.ts
        else:
            delta = timedelta(seconds=30)
        delta = max(timedelta(seconds=0), min(delta, MAX_INTERVAL))
        intervals.append((tick, delta.total_seconds() / 60.0))
    return intervals


def _fan_steps(ticks: list[Tick], threshold_pct: int) -> list[FanStep]:
    steps: list[FanStep] = []
    previous: int | None = None
    for tick in ticks:
        if tick.target_fan_pct is None:
            continue
        if previous is not None:
            delta = tick.target_fan_pct - previous
            if abs(delta) >= threshold_pct:
                steps.append(
                    FanStep(
                        ts=tick.ts,
                        delta=delta,
                        phase="lights_on" if tick.lights_on else "lights_off",
                        reason_bucket=_reason_bucket(tick),
                    )
                )
        previous = tick.target_fan_pct
    return steps


def _large_fan_reversals(
    steps: list[FanStep],
    window: timedelta,
) -> list[FanStep]:
    reversals: list[FanStep] = []
    for index, step in enumerate(steps):
        direction = 1 if step.delta > 0 else -1
        for next_step in steps[index + 1 :]:
            if next_step.ts - step.ts > window:
                break
            if next_step.delta * direction < 0:
                reversals.append(next_step)
                break
    return reversals


def _reason_bucket(tick: Tick) -> str:
    observed = (*tick.constraints, *tick.reasons, *tick.conflicts)
    if any("hard_rh" in reason for reason in observed):
        return "hard_rh"
    if any("hard_low_temperature" in reason for reason in observed):
        return "hard_low_temp"
    if any(
        reason in {"hard_temperature_guard", "heater_safety_off"}
        for reason in observed
    ):
        return "hard_heat"
    if "lights_off_feedforward" in observed:
        return "lights_off_ff"
    if "fan_elevated_for_cooling" in observed:
        return "cooling"
    if "fan_elevated_for_drying" in observed:
        return "rh_drying"
    if "fan_drying_decay" in observed:
        return "fan_decay"
    if "fan_min_dwell" in observed:
        return "fan_dwell"
    if "fan_floor" in observed:
        return "fan_floor"
    if any("sensor_failsafe" in reason for reason in observed):
        return "failsafe"
    return "other"


def _dehumidifier_cycles(ticks: list[Tick]) -> int:
    cycles = 0
    previous: bool | None = None
    for tick in ticks:
        if tick.target_dehumidifier_on is None:
            continue
        if tick.target_dehumidifier_on and previous is False:
            cycles += 1
        previous = tick.target_dehumidifier_on
    return cycles


def _conflict_avoidance_observed(tick: Tick) -> bool:
    if "humidifier_forced_off_dehumidifier_on" in tick.reasons:
        return True
    if tick.target_dehumidifier_on and tick.target_humidifier_pct == 0:
        return any("humidifier" in reason for reason in tick.reasons)
    return any(
        "dehumidifier" in conflict and "humidifier" in conflict
        for conflict in tick.conflicts
    )


def _hard_safety_observed(tick: Tick) -> bool:
    safety_terms = (
        "hard_rh",
        "hard_temperature",
        "hard_low_temperature",
        "heater_safety_off",
    )
    observed = (*tick.constraints, *tick.reasons)
    return any(any(term in reason for term in safety_terms) for reason in observed)


def _format_table(metrics: list[WindowMetrics]) -> str:
    headers = (
        "window",
        "source",
        "start",
        "end",
        "ticks",
        "large_fan_steps",
        "large_fan_reversals",
        "rh_in_band_pct",
        "median_abs_rh_error",
        "high_rh_min",
        "high_vpd_min",
        "dehumidifier_cycles",
        "conflict_avoidance",
        "hard_safety_overrides",
    )
    rows = [
        (
            metric.label,
            metric.source,
            _fmt_time(metric.start),
            _fmt_time(metric.end),
            str(metric.ticks),
            str(metric.large_fan_steps),
            str(metric.large_fan_reversals),
            _fmt_optional(metric.rh_in_band_pct),
            _fmt_optional(metric.median_abs_rh_error),
            f"{metric.high_rh_exceedance_min:.1f}",
            f"{metric.high_vpd_exceedance_min:.1f}",
            str(metric.dehumidifier_cycles),
            str(metric.humidifier_dehumidifier_conflict_avoidance_events),
            str(metric.hard_safety_overrides),
        )
        for metric in metrics
    ]
    widths = [
        max(len(str(row[index])) for row in (headers, *rows))
        for index in range(len(headers))
    ]
    lines = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    lines.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


def _format_breakdowns(
    windows: list[tuple[str, datetime, datetime]],
    baseline_ticks: list[Tick],
    replay_ticks: list[Tick],
    args: argparse.Namespace,
) -> str:
    sources = (
        ("logged_baseline", baseline_ticks),
        ("new_controller_replay", replay_ticks),
    )
    lines = ["Large fan step breakdown (top buckets):"]
    for label, start, end in windows:
        window = Window(label=label, start=start, end=end)
        for source, ticks in sources:
            window_ticks = _ticks_in_window(ticks, window)
            steps = _fan_steps(window_ticks, args.large_step_pct)
            step_counts = Counter(
                (
                    "up" if step.delta > 0 else "down",
                    step.phase,
                    step.reason_bucket,
                )
                for step in steps
            )
            lines.append(
                f"- {label} {source}: {_format_counter(step_counts, limit=8)}"
            )

    lines.append("")
    lines.append("Large fan reversal breakdown (opposite step bucket):")
    for label, start, end in windows:
        window = Window(label=label, start=start, end=end)
        for source, ticks in sources:
            window_ticks = _ticks_in_window(ticks, window)
            steps = _fan_steps(window_ticks, args.large_step_pct)
            reversals = _large_fan_reversals(
                steps,
                timedelta(minutes=args.reversal_window_min),
            )
            reversal_counts = Counter(
                (step.phase, step.reason_bucket) for step in reversals
            )
            lines.append(
                f"- {label} {source}: {_format_counter(reversal_counts, limit=8)}"
            )
    return "\n".join(lines)


def _ticks_in_window(ticks: list[Tick], window: Window) -> list[Tick]:
    return [tick for tick in ticks if window.start <= tick.ts < window.end]


def _format_counter(counter: Counter[tuple[str, ...]], *, limit: int) -> str:
    if not counter:
        return "none"
    return ", ".join(
        f"{'/'.join(key)}={count}" for key, count in counter.most_common(limit)
    )


def _print_notes(logs_dir: Path) -> None:
    _emit("")
    _emit(_notes(logs_dir))


def _notes(logs_dir: Path) -> str:
    return "\n".join(
        (
            "Assumptions and limitations:",
            (
                f"- Read-only input: {logs_dir}; no hardware, services, or "
                "databases are touched."
            ),
            (
                "- logged_baseline uses actuator targets already present in the "
                "JSONL ticks."
            ),
            (
                "- new_controller_replay feeds the logged sensor/lights sequence "
                "through the checked-out pure controller and assumes each replayed "
                "actuator target is successfully applied by the next tick."
            ),
            (
                "- Replay is not a counterfactual climate simulation: RH, VPD, "
                "and temperature remain the historical measured values, so "
                "environmental effects from different fan/dehumidifier choices "
                "are not estimated."
            ),
            (
                "- Replay controller state is reset after gaps longer than "
                f"{REPLAY_STATE_RESET_GAP}."
            ),
        )
    )


def _emit(message: str) -> None:
    sys.stdout.write(f"{message}\n")


def _warn(message: str) -> None:
    sys.stderr.write(f"{message}\n")


def _parse_duration(value: str) -> timedelta:
    suffix = value[-1].lower()
    try:
        amount = float(value[:-1])
    except ValueError as exc:
        raise SystemExit(f"invalid duration {value!r}") from exc
    if suffix == "d":
        return timedelta(days=amount)
    if suffix == "h":
        return timedelta(hours=amount)
    if suffix == "m":
        return timedelta(minutes=amount)
    raise SystemExit(f"invalid duration suffix for {value!r}; use d, h, or m")


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _require_time(value: str, label: str) -> datetime:
    parsed = _parse_time(value)
    if parsed is None:
        raise SystemExit(f"{label} must be an ISO timestamp")
    return parsed


def _float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value)
    return None


def _bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator * 100.0


def _fmt_optional(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _fmt_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="minutes").replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
