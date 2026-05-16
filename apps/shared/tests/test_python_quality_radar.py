from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

import python_quality_radar as radar  # noqa: E402

SERVICE_PATH = "apps/demo/src/dirt_demo/service.py"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_python_metric_detectors_find_complex_routes_and_argument_sprawl(
    tmp_path: Path,
) -> None:
    route_body = "\n".join(
        [
            "    if alpha:",
            "        value += 1",
            "    if beta:",
            "        value += 1",
            "    if gamma:",
            "        value += 1",
            "    if delta:",
            "        value += 1",
            "    if epsilon:",
            "        value += 1",
            "    if zeta:",
            "        value += 1",
            *("    value += 1" for _ in range(72)),
            "    return {'value': value}",
        ]
    )
    source = (
        "router = object()\n\n"
        "@router.get('/items')\n"
        "def list_items(alpha, beta, gamma, delta, epsilon, zeta, eta):\n"
        "    value = 0\n"
        f"{route_body}\n"
    )
    path = _write(tmp_path / "apps/demo/src/dirt_demo/api.py", source)

    findings = radar.collect_python_metrics(tmp_path, [path])

    by_detector = {finding.detector: finding for finding in findings}
    assert by_detector["argument-count"].evidence == {
        "function": "list_items",
        "argument_count": 7,
    }
    assert by_detector["function-span"].evidence == {
        "function": "list_items",
        "span": 87,
    }
    route_finding = by_detector["route-metrics"]
    assert route_finding.category == "route-edge"
    assert route_finding.evidence["methods"] == ["get"]
    assert route_finding.evidence["branch_count"] == 6


def test_dto_drift_and_test_proximity_detectors_use_small_fixture_repo(
    tmp_path: Path,
) -> None:
    left = _write(
        tmp_path / "apps/gateway/src/dirt_gateway/api.py",
        """
from pydantic import BaseModel


class CreateThingRequest(BaseModel):
    id: str
    name: str
    enabled: bool


def untested_boundary_helper() -> None:
    pass
""".lstrip(),
    )
    right = _write(
        tmp_path / "apps/control-plane/src/dirt_control/gateway.py",
        """
from pydantic import BaseModel


class UpsertThingPayload(BaseModel):
    id: str
    name: str
    enabled: bool
""".lstrip(),
    )
    test_file = _write(
        tmp_path / "apps/gateway/tests/test_other.py",
        "def test_placeholder() -> None:\n    assert True\n",
    )

    drift = radar.collect_dto_drift_findings(tmp_path, [left, right])
    proximity = radar.collect_test_proximity_findings(tmp_path, [left], [test_file])

    assert [(finding.category, finding.detector) for finding in drift] == [
        ("dto-drift", "pydantic-field-similarity")
    ]
    assert drift[0].evidence == {
        "model": "CreateThingRequest",
        "similar_model": "UpsertThingPayload",
        "similar_path": "apps/control-plane/src/dirt_control/gateway.py",
        "similarity": 1.0,
        "fields": ["enabled", "id", "name"],
    }
    assert [(finding.category, finding.detector) for finding in proximity] == [
        ("test-proximity", "nearby-test-name-or-mention")
    ]


def test_report_json_and_markdown_keep_stable_category_and_finding_order(
    tmp_path: Path, monkeypatch
) -> None:
    production_file = _write(
        tmp_path / SERVICE_PATH,
        "def covered_service() -> None:\n    pass\n",
    )

    def fake_ruff_findings(_repo_root: Path) -> list[radar.Finding]:
        return [
            radar.Finding(
                path=SERVICE_PATH,
                line=4,
                category="security",
                detector="ruff-S101",
                severity=6,
                message="Security check.",
            ),
            radar.Finding(
                path=SERVICE_PATH,
                line=5,
                category="async",
                detector="ruff-ASYNC100",
                severity=5,
                message="Async check.",
            ),
        ]

    def fake_jscpd_findings(_repo_root: Path) -> list[radar.Finding]:
        return [
            radar.Finding(
                path=SERVICE_PATH,
                line=3,
                category="duplication",
                detector="jscpd",
                severity=9,
                message="Duplicate block.",
            )
        ]

    def fake_semgrep_findings(_repo_root: Path) -> list[radar.Finding]:
        return [
            radar.Finding(
                path=SERVICE_PATH,
                line=1,
                category=category,
                detector=f"semgrep-{category}",
                severity=severity,
                message=f"{category} check.",
            )
            for category, severity in [
                ("route-edge", 5),
                ("service-infrastructure", 4),
                ("boundary", 6),
                ("thin-wrapper", 3),
                ("error-handling", 4),
                ("suppression", 2),
            ]
        ]

    def fake_dto_drift_findings(
        _repo_root: Path, files: list[Path]
    ) -> list[radar.Finding]:
        assert files == [production_file]
        return [
            radar.Finding(
                path=SERVICE_PATH,
                line=2,
                category="dto-drift",
                detector="pydantic-field-similarity",
                severity=7,
                message="DTO drift.",
            )
        ]

    monkeypatch.setattr(radar, "collect_ruff_findings", fake_ruff_findings)
    monkeypatch.setattr(radar, "collect_jscpd_findings", fake_jscpd_findings)
    monkeypatch.setattr(radar, "collect_semgrep_findings", fake_semgrep_findings)
    monkeypatch.setattr(radar, "collect_dto_drift_findings", fake_dto_drift_findings)

    report = radar.build_report(tmp_path)
    json_payload = json.loads(radar.render_json(report))
    markdown = radar.render_markdown(report)

    assert list(report["category_counts"]) == list(radar.CATEGORIES)
    assert json_payload["categories"] == list(radar.CATEGORIES)
    assert list(json_payload["category_counts"]) == sorted(radar.CATEGORIES)
    assert all(
        json_payload["category_counts"][category] == 1
        for category in radar.CATEGORIES
        if category != "complexity"
    )
    assert json_payload["category_counts"]["complexity"] == 0
    assert [
        (finding["category"], finding["severity"])
        for finding in json_payload["findings"][:4]
    ] == [
        ("duplication", 9),
        ("dto-drift", 7),
        ("boundary", 6),
        ("security", 6),
    ]
    assert radar.render_json(report) == radar.render_json(report)
    assert markdown.index("- `complexity`: 0") < markdown.index("- `duplication`: 1")
    assert markdown.index("- `suppression`: 1") < markdown.index(
        "- `test-proximity`: 1"
    )
    assert "Score: 52 | Findings: 11" in markdown
