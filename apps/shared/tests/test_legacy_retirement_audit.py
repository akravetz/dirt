"""Audit guards for the legacy SensorLocation/sensornode retirement plan."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from dirt_shared.models.enums import SensorLocation
from dirt_shared.sensor_contract import (
    DEVICE_METRICS,
    device_id_for_legacy_location,
    emitted_metrics_for_device_id,
    persisted_capability_ids_for_device_id,
    persisted_metrics_for_device_id,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOTS = tuple(
    sorted(path for path in (REPO_ROOT / "apps").glob("*/src") if path.is_dir())
)

CENTRALIZED_WRITERS: dict[str, frozenset[tuple[str, str]]] = {
    "SensorReading": frozenset(
        {
            (
                "apps/shared/src/dirt_shared/services/readings.py",
                "ReadingsService.ingest_reading",
            ),
        }
    ),
    "SensorCalibration": frozenset(
        {
            (
                "apps/shared/src/dirt_shared/services/readings.py",
                "_update_calibration",
            ),
        }
    ),
    "SensorNode": frozenset(
        {
            (
                "apps/shared/src/dirt_shared/services/readings.py",
                "ReadingsService.ingest_reading",
            ),
            (
                "apps/shared/src/dirt_shared/services/readings.py",
                "ReadingsService.touch_node",
            ),
        }
    ),
}
SCOPED_WRITERS = frozenset({"SensorReading", "SensorCalibration"})

LEGACY_REFERENCE_TOKENS = (
    "SensorLocation",
    "SensorNode",
    "sensornode_id",
    "legacy_location",
    "missing_emitted",
)

EXPECTED_LEGACY_REFERENCE_FILES = frozenset(
    {
        "apps/hwd/src/dirt_hwd/api/ingest.py",
        "apps/hwd/src/dirt_hwd/services/humidifier.py",
        "apps/shared/src/dirt_shared/models/__init__.py",
        "apps/shared/src/dirt_shared/models/enums.py",
        "apps/shared/src/dirt_shared/models/sensor_node.py",
        "apps/shared/src/dirt_shared/models/sensor_reading.py",
        "apps/shared/src/dirt_shared/sensor_contract.py",
        "apps/shared/src/dirt_shared/services/readings.py",
    }
)


@dataclass(frozen=True)
class ConstructorCall:
    model: str
    path: str
    line: int
    qualname: str
    keyword_names: frozenset[str]

    @property
    def location(self) -> tuple[str, str]:
        return (self.path, self.qualname)

    def format(self) -> str:
        return f"{self.path}:{self.line} in {self.qualname or '<module>'}"


class _ConstructorVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self._path = path.relative_to(REPO_ROOT).as_posix()
        self._stack: list[str] = []
        self.calls: list[ConstructorCall] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in CENTRALIZED_WRITERS:
            self.calls.append(
                ConstructorCall(
                    model=name,
                    path=self._path,
                    line=node.lineno,
                    qualname=".".join(self._stack),
                    keyword_names=frozenset(
                        keyword.arg for keyword in node.keywords if keyword.arg
                    ),
                )
            )
        self.generic_visit(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _source_files() -> list[Path]:
    return sorted(path for root in SOURCE_ROOTS for path in root.rglob("*.py"))


def _constructor_calls() -> list[ConstructorCall]:
    calls: list[ConstructorCall] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        visitor = _ConstructorVisitor(path)
        visitor.visit(tree)
        calls.extend(visitor.calls)
    return calls


def test_legacy_reference_inventory_is_explicit() -> None:
    discovered = frozenset(
        path.relative_to(REPO_ROOT).as_posix()
        for path in _source_files()
        if any(token in path.read_text() for token in LEGACY_REFERENCE_TOKENS)
    )

    unexpected = sorted(discovered - EXPECTED_LEGACY_REFERENCE_FILES)
    missing = sorted(EXPECTED_LEGACY_REFERENCE_FILES - discovered)
    assert discovered == EXPECTED_LEGACY_REFERENCE_FILES, (
        "Legacy reference inventory changed.\n"
        f"Unexpected files: {unexpected}\n"
        f"Missing files: {missing}"
    )


def test_legacy_table_writers_stay_centralized() -> None:
    """New live writers must not bypass the compatibility choke points."""
    unexpected = [
        call
        for call in _constructor_calls()
        if call.location not in CENTRALIZED_WRITERS[call.model]
    ]

    assert unexpected == [], "Unexpected legacy/scoped table writers:\n" + "\n".join(
        f"- {call.model}: {call.format()}" for call in unexpected
    )


def test_current_reading_and_calibration_writers_carry_capability_scope() -> None:
    missing_scope = [
        call
        for call in _constructor_calls()
        if call.model in SCOPED_WRITERS and "capability_id" not in call.keyword_names
    ]

    assert missing_scope == [], (
        "Writers must pass capability_id, even when the compatibility path "
        "resolves to None:\n"
        + "\n".join(f"- {call.model}: {call.format()}" for call in missing_scope)
    )


def test_legacy_sensor_contract_helpers_are_derived_from_device_contracts() -> None:
    expected_locations = {contract[0] for contract in DEVICE_METRICS.values()}
    expected_devices_by_location = {
        contract[0]: device_id for device_id, contract in DEVICE_METRICS.items()
    }

    assert expected_locations == set(SensorLocation)
    assert {
        location: device_id_for_legacy_location(location) for location in SensorLocation
    } == expected_devices_by_location
    for device_id, contract in DEVICE_METRICS.items():
        assert emitted_metrics_for_device_id(device_id) == {
            metric[0] for metric in contract[1].values() if metric[1]
        }
        assert persisted_metrics_for_device_id(device_id) == {
            metric[0] for metric in contract[1].values() if metric[2]
        }
        assert persisted_capability_ids_for_device_id(device_id) == {
            capability_id for capability_id, metric in contract[1].items() if metric[2]
        }


def test_device_contract_metrics_are_keyed_by_capability_identity() -> None:
    offenders = {
        device_id: sorted(
            capability_id
            for capability_id, metric in contract[1].items()
            if capability_id != metric[0]
        )
        for device_id, contract in DEVICE_METRICS.items()
    }
    offenders = {device_id: keys for device_id, keys in offenders.items() if keys}

    assert not offenders, (
        "Canonical DEVICE_METRICS must be keyed by capability_id and carry the "
        f"matching metric identity for current sensor capabilities: {offenders}"
    )
