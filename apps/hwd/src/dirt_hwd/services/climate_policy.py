"""Pure climate policy for the main tent controller.

This module owns inspectable controller policy only. It does not allocate
actuator demand, dispatch hardware, read sensors, or persist configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dirt_shared.services.grow_state import Stage

Phase = Literal["lights_on", "lights_off"]

THERMOFORGE_SUPPORTED_LEVELS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
EXPECTED_STAGES: frozenset[Stage] = frozenset({"veg", "flower_early", "flower_late"})


@dataclass(frozen=True, slots=True)
class Band:
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError("band low must be <= high")

    def as_tuple(self) -> tuple[float, float]:
        return (self.low, self.high)


@dataclass(frozen=True, slots=True)
class PhaseClimatePolicy:
    phase: Phase
    vpd_kpa: Band
    temperature_f: Band
    rh_max_pct: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.rh_max_pct <= 100.0:
            raise ValueError("rh_max_pct must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class StageClimatePolicy:
    stage: Stage
    lights_on: PhaseClimatePolicy
    lights_off: PhaseClimatePolicy

    def __post_init__(self) -> None:
        if self.lights_on.phase != "lights_on":
            raise ValueError("lights_on policy must have phase='lights_on'")
        if self.lights_off.phase != "lights_off":
            raise ValueError("lights_off policy must have phase='lights_off'")

    def for_phase(self, phase: Phase) -> PhaseClimatePolicy:
        if phase == "lights_on":
            return self.lights_on
        return self.lights_off


@dataclass(frozen=True, slots=True)
class FanPolicy:
    floor_pct: int
    max_pct: int

    def __post_init__(self) -> None:
        if not 0 <= self.floor_pct <= self.max_pct <= 100:
            raise ValueError("fan policy must satisfy 0 <= floor <= max <= 100")


@dataclass(frozen=True, slots=True)
class HeaterPolicy:
    supported_levels: tuple[int, ...] = THERMOFORGE_SUPPORTED_LEVELS

    def __post_init__(self) -> None:
        if self.supported_levels != THERMOFORGE_SUPPORTED_LEVELS:
            raise ValueError("ThermoForge policy supports only off plus levels 1..10")


@dataclass(frozen=True, slots=True)
class SensorStaleLimits:
    temperature_s: float
    humidity_s: float
    vpd_s: float
    fan_s: float
    actuator_s: float

    def __post_init__(self) -> None:
        if (
            min(
                self.temperature_s,
                self.humidity_s,
                self.vpd_s,
                self.fan_s,
                self.actuator_s,
            )
            <= 0
        ):
            raise ValueError("stale limits must be positive")


@dataclass(frozen=True, slots=True)
class DehumidifierCyclePolicy:
    vpd_deadband_kpa: float
    rh_deadband_pct: float
    minimum_on_s: float
    minimum_off_s: float

    def __post_init__(self) -> None:
        if self.vpd_deadband_kpa < 0:
            raise ValueError("vpd_deadband_kpa must be non-negative")
        if self.rh_deadband_pct < 0:
            raise ValueError("rh_deadband_pct must be non-negative")
        if self.minimum_on_s <= 0 or self.minimum_off_s <= 0:
            raise ValueError("minimum cycle durations must be positive")


@dataclass(frozen=True, slots=True)
class ClimatePolicy:
    stage_policies: tuple[StageClimatePolicy, ...]
    hard_min_temperature_f: float
    fan: FanPolicy
    heater: HeaterPolicy
    stale: SensorStaleLimits
    dehumidifier: DehumidifierCyclePolicy

    def __post_init__(self) -> None:
        stages = {stage_policy.stage for stage_policy in self.stage_policies}
        if stages != EXPECTED_STAGES or len(self.stage_policies) != len(
            EXPECTED_STAGES
        ):
            raise ValueError("climate policy must define every grow stage exactly once")
        if self.hard_min_temperature_f <= 0:
            raise ValueError("hard_min_temperature_f must be positive")

    def for_stage(self, stage: Stage) -> StageClimatePolicy:
        for stage_policy in self.stage_policies:
            if stage_policy.stage == stage:
                return stage_policy
        raise ValueError(f"no climate policy for stage {stage!r}")

    def for_stage_phase(self, stage: Stage, phase: Phase) -> PhaseClimatePolicy:
        return self.for_stage(stage).for_phase(phase)


@dataclass(frozen=True, slots=True)
class ClimatePolicyDefaults:
    fan_floor_pct: int = 20
    fan_max_pct: int = 80
    hard_min_temperature_f: float = 70.0
    sensor_stale_s: float = 300.0
    actuator_stale_s: float = 300.0
    dehumidifier_vpd_deadband_kpa: float = 0.05
    dehumidifier_rh_deadband_pct: float = 2.0
    dehumidifier_minimum_on_s: float = 300.0
    dehumidifier_minimum_off_s: float = 300.0


def phase_from_lights(lights_on: bool) -> Phase:
    return "lights_on" if lights_on else "lights_off"


def default_climate_policy(
    values: ClimatePolicyDefaults | None = None,
) -> ClimatePolicy:
    """Return the initial explicit climate-controller policy.

    Values are deliberately first-class data here so future controller
    allocation code consumes policy instead of burying thresholds in logic.
    """
    values = values or ClimatePolicyDefaults()
    return ClimatePolicy(
        stage_policies=(
            StageClimatePolicy(
                stage="veg",
                lights_on=PhaseClimatePolicy(
                    phase="lights_on",
                    vpd_kpa=Band(0.9, 1.1),
                    temperature_f=Band(75.0, 80.0),
                    rh_max_pct=70.0,
                ),
                lights_off=PhaseClimatePolicy(
                    phase="lights_off",
                    vpd_kpa=Band(0.7, 0.9),
                    temperature_f=Band(70.0, 74.0),
                    rh_max_pct=75.0,
                ),
            ),
            StageClimatePolicy(
                stage="flower_early",
                lights_on=PhaseClimatePolicy(
                    phase="lights_on",
                    vpd_kpa=Band(1.1, 1.3),
                    temperature_f=Band(76.0, 78.0),
                    rh_max_pct=65.0,
                ),
                lights_off=PhaseClimatePolicy(
                    phase="lights_off",
                    vpd_kpa=Band(0.9, 1.1),
                    temperature_f=Band(70.0, 72.0),
                    rh_max_pct=75.0,
                ),
            ),
            StageClimatePolicy(
                stage="flower_late",
                lights_on=PhaseClimatePolicy(
                    phase="lights_on",
                    vpd_kpa=Band(1.2, 1.5),
                    temperature_f=Band(74.0, 78.0),
                    rh_max_pct=55.0,
                ),
                lights_off=PhaseClimatePolicy(
                    phase="lights_off",
                    vpd_kpa=Band(1.1, 1.3),
                    temperature_f=Band(70.0, 72.0),
                    rh_max_pct=60.0,
                ),
            ),
        ),
        hard_min_temperature_f=values.hard_min_temperature_f,
        fan=FanPolicy(floor_pct=values.fan_floor_pct, max_pct=values.fan_max_pct),
        heater=HeaterPolicy(),
        stale=SensorStaleLimits(
            temperature_s=values.sensor_stale_s,
            humidity_s=values.sensor_stale_s,
            vpd_s=values.sensor_stale_s,
            fan_s=values.sensor_stale_s,
            actuator_s=values.actuator_stale_s,
        ),
        dehumidifier=DehumidifierCyclePolicy(
            vpd_deadband_kpa=values.dehumidifier_vpd_deadband_kpa,
            rh_deadband_pct=values.dehumidifier_rh_deadband_pct,
            minimum_on_s=values.dehumidifier_minimum_on_s,
            minimum_off_s=values.dehumidifier_minimum_off_s,
        ),
    )
