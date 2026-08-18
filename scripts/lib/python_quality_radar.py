from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CATEGORIES = (
    "complexity",
    "duplication",
    "route-edge",
    "service-infrastructure",
    "boundary",
    "dto-drift",
    "thin-wrapper",
    "error-handling",
    "security",
    "async",
    "suppression",
    "test-proximity",
)

RUFF_SELECT = (
    "C901",
    "PLR0912",
    "PLR0915",
    "PLR0913",
    "S",
    "ASYNC",
    "TRY300",
)

EXCLUDED_PARTS = {
    "__pycache__",
    "tests",
    "reference",
    "validation",
    "data-gen",
    "docker",
    "generated",
}

BOUNDARY_PATH_MARKERS = (
    "api",
    "browser",
    "cloud",
    "command",
    "commands",
    "contract",
    "gateway",
    "outbox",
    "protocol",
    "protocols",
    "sync",
)

DTO_NAME_SUFFIXES = ("Request", "Response", "Payload", "Command", "Event")
ROUTE_METHODS = {"get", "post", "put", "patch", "delete"}
ENCODING = "utf-8"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str
    detector: str
    severity: int
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def sort_key(self) -> tuple[str, int, str, str, str]:
        return (self.path, self.line, self.category, self.detector, self.message)


@dataclass(frozen=True)
class ReviewPacket:
    path: str
    score: int
    finding_count: int
    categories: tuple[str, ...]


@dataclass(frozen=True)
class DtoModel:
    name: str
    path: str
    line: int
    fields: frozenset[str]
    typed_fields: frozenset[str]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    report = build_report(repo_root)
    output = render_json(report) if args.format == "json" else render_markdown(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding=ENCODING)
        print(f"Wrote {args.output}")  # noqa: T201 - operator CLI status.
    else:
        print(output)  # noqa: T201 - operator CLI stdout mode.
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report-only Python quality radar for Dirt production app code."
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Report format. Defaults to markdown.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path. The command writes no repo artifacts unless set.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def build_report(repo_root: Path) -> dict[str, Any]:
    production_files = find_production_files(repo_root)
    test_files = find_test_files(repo_root)

    findings: list[Finding] = []
    findings.extend(collect_python_metrics(repo_root, production_files))
    findings.extend(collect_ruff_findings(repo_root))
    findings.extend(collect_jscpd_findings(repo_root))
    findings.extend(collect_semgrep_findings(repo_root))
    findings.extend(collect_dto_drift_findings(repo_root, production_files))
    findings.extend(
        collect_test_proximity_findings(repo_root, production_files, test_files)
    )

    deduped = sorted(
        {finding.sort_key(): finding for finding in findings}.values(), key=_rank_key
    )
    packets = build_review_packets(deduped)
    category_counts = Counter(finding.category for finding in deduped)
    return {
        "schema_version": 1,
        "scope": "apps/*/src/**/*.py",
        "categories": list(CATEGORIES),
        "category_counts": {
            category: category_counts.get(category, 0) for category in CATEGORIES
        },
        "summary": {
            "production_file_count": len(production_files),
            "test_file_count": len(test_files),
            "finding_count": len(deduped),
            "review_packet_count": len(packets),
        },
        "review_packets": [asdict(packet) for packet in packets],
        "findings": [asdict(finding) for finding in deduped],
    }


def find_production_files(repo_root: Path) -> list[Path]:
    files = []
    for path in repo_root.glob("apps/*/src/**/*.py"):
        if not path.is_file():
            continue
        if EXCLUDED_PARTS.intersection(path.relative_to(repo_root).parts):
            continue
        files.append(path)
    return sorted(files)


def find_test_files(repo_root: Path) -> list[Path]:
    return sorted(
        path for path in repo_root.glob("apps/*/tests/**/*.py") if path.is_file()
    )


def collect_python_metrics(repo_root: Path, files: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        rel_path = relative_path(repo_root, path)
        text = path.read_text(encoding=ENCODING)
        loc = non_comment_loc(text)
        if loc >= 250:
            findings.append(
                Finding(
                    path=rel_path,
                    line=1,
                    category="complexity",
                    detector="file-loc",
                    severity=min(10, 3 + loc // 150),
                    message=f"Large production file with {loc} non-comment lines.",
                    evidence={"non_comment_loc": loc},
                )
            )

        try:
            tree = ast.parse(text, filename=rel_path)
        except SyntaxError as exc:
            findings.append(
                Finding(
                    path=rel_path,
                    line=exc.lineno or 1,
                    category="complexity",
                    detector="python-parse",
                    severity=10,
                    message="Could not parse production file for radar metrics.",
                    evidence={"error": exc.msg},
                )
            )
            continue

        findings.extend(collect_span_metrics(rel_path, tree))
        findings.extend(collect_route_metrics(rel_path, tree))
    return findings


def collect_span_metrics(path: str, tree: ast.AST) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            span = node_span(node)
            if span >= 120:
                findings.append(
                    Finding(
                        path=path,
                        line=node.lineno,
                        category="complexity",
                        detector="class-span",
                        severity=min(10, 3 + span // 80),
                        message=f"Class `{node.name}` spans {span} lines.",
                        evidence={"class": node.name, "span": span},
                    )
                )
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            span = node_span(node)
            args_count = function_arg_count(node)
            if span >= 80:
                findings.append(
                    Finding(
                        path=path,
                        line=node.lineno,
                        category="complexity",
                        detector="function-span",
                        severity=min(10, 3 + span // 40),
                        message=f"Function `{node.name}` spans {span} lines.",
                        evidence={"function": node.name, "span": span},
                    )
                )
            if args_count >= 7:
                findings.append(
                    Finding(
                        path=path,
                        line=node.lineno,
                        category="complexity",
                        detector="argument-count",
                        severity=min(10, 2 + args_count),
                        message=f"Function `{node.name}` has {args_count} arguments.",
                        evidence={"function": node.name, "argument_count": args_count},
                    )
                )
    return findings


def collect_route_metrics(path: str, tree: ast.AST) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        methods = route_methods(node)
        if not methods:
            continue
        span = node_span(node)
        branch_count = sum(
            isinstance(
                child,
                ast.If
                | ast.For
                | ast.AsyncFor
                | ast.While
                | ast.Match
                | ast.Try
                | ast.ExceptHandler
                | ast.BoolOp,
            )
            for child in ast.walk(node)
        )
        if span >= 45 or branch_count >= 6:
            findings.append(
                Finding(
                    path=path,
                    line=node.lineno,
                    category="route-edge",
                    detector="route-metrics",
                    severity=min(10, 3 + span // 35 + branch_count // 4),
                    message=(
                        f"FastAPI route `{node.name}` has {span} lines and "
                        f"{branch_count} branch nodes; review edge/business split."
                    ),
                    evidence={
                        "function": node.name,
                        "methods": sorted(methods),
                        "span": span,
                        "branch_count": branch_count,
                        "heuristic": True,
                    },
                )
            )
    return findings


def collect_ruff_findings(repo_root: Path) -> list[Finding]:
    src_paths = sorted(
        str(path.relative_to(repo_root))
        for path in repo_root.glob("apps/*/src")
        if path.is_dir()
    )
    if not src_paths:
        return []
    command = [
        "uv",
        "run",
        "ruff",
        "check",
        *src_paths,
        "--select",
        ",".join(RUFF_SELECT),
        "--ignore",
        "TRY003",
        "--output-format",
        "json",
    ]
    result = run_tool(command, repo_root)
    if result.returncode not in (0, 1):
        return tool_error("complexity", "ruff", result)
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return tool_error("complexity", "ruff-json", result)

    findings = []
    for item in payload:
        code = str(item.get("code") or "")
        if code == "TRY003":
            continue
        category = ruff_category(code)
        location = item.get("location") or {}
        filename = normalize_tool_path(repo_root, item.get("filename") or "")
        findings.append(
            Finding(
                path=filename,
                line=int(location.get("row") or 1),
                category=category,
                detector=f"ruff-{code}",
                severity=ruff_severity(code),
                message=str(item.get("message") or code),
                evidence={"code": code},
            )
        )
    return findings


def collect_jscpd_findings(repo_root: Path) -> list[Finding]:
    if not shutil.which("pnpm"):
        return [
            Finding(
                path=".",
                line=1,
                category="duplication",
                detector="jscpd-unavailable",
                severity=1,
                message=(
                    "pnpm is unavailable, so jscpd duplication detection did not run."
                ),
            )
        ]

    with tempfile.TemporaryDirectory(prefix="dirt-jscpd-") as tmp:
        command = [
            "pnpm",
            "dlx",
            "jscpd",
            "apps/*/src/**/*.py",
            "--reporters",
            "json",
            "--output",
            tmp,
            "--ignore",
            "**/tests/**",
            "--ignore",
            "**/reference/**",
            "--ignore",
            "**/data-gen/**",
            "--ignore",
            "**/validation/**",
            "--ignore",
            "**/docker/**",
        ]
        result = run_tool(command, repo_root)
        if result.returncode not in (0, 1):
            return tool_error("duplication", "jscpd", result)

        report_path = first_json_report(Path(tmp))
        if report_path is None:
            return []
        try:
            payload = json.loads(report_path.read_text(encoding=ENCODING))
        except json.JSONDecodeError:
            return tool_error("duplication", "jscpd-json", result)

    findings = []
    for duplicate in payload.get("duplicates", []):
        first = duplicate.get("firstFile") or {}
        second = duplicate.get("secondFile") or {}
        lines = int(duplicate.get("lines") or 0)
        tokens = int(duplicate.get("tokens") or 0)
        first_path = normalize_tool_path(repo_root, first.get("name") or "")
        second_path = normalize_tool_path(repo_root, second.get("name") or "")
        if not first_path or not second_path:
            continue
        severity = min(10, 3 + lines // 20 + tokens // 300)
        for current, other, file_info in (
            (first_path, second_path, first),
            (second_path, first_path, second),
        ):
            findings.append(
                Finding(
                    path=current,
                    line=int(
                        file_info.get("start")
                        or file_info.get("startLoc", {}).get("line")
                        or 1
                    ),
                    category="duplication",
                    detector="jscpd",
                    severity=severity,
                    message=(
                        f"Duplicate block of {lines} lines also appears in `{other}`."
                    ),
                    evidence={
                        "duplicate_with": other,
                        "lines": lines,
                        "tokens": tokens,
                    },
                )
            )
    return findings


def collect_semgrep_findings(repo_root: Path) -> list[Finding]:
    config_path = repo_root / "scripts" / "python-quality-radar-semgrep.yml"
    src_paths = sorted(
        str(path.relative_to(repo_root))
        for path in repo_root.glob("apps/*/src")
        if path.is_dir()
    )
    if not src_paths:
        return []
    command = [
        "uvx",
        "semgrep",
        "--config",
        str(config_path.relative_to(repo_root)),
        "--json",
        "--metrics=off",
        "--quiet",
        *src_paths,
    ]
    result = run_tool(command, repo_root)
    if result.returncode not in (0, 1):
        return tool_error("boundary", "semgrep", result)
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return tool_error("boundary", "semgrep-json", result)

    findings = []
    for item in payload.get("results", []):
        extra = item.get("extra") or {}
        metadata = extra.get("metadata") or {}
        category = metadata.get("category")
        if category not in CATEGORIES:
            category = "boundary"
        findings.append(
            Finding(
                path=normalize_tool_path(repo_root, item.get("path") or ""),
                line=int((item.get("start") or {}).get("line") or 1),
                category=category,
                detector=str(
                    metadata.get("detector") or item.get("check_id") or "semgrep"
                ),
                severity=int(metadata.get("severity_score") or 4),
                message=str(
                    extra.get("message") or item.get("check_id") or "Semgrep finding."
                ),
                evidence={"check_id": item.get("check_id")},
            )
        )
    return findings


def collect_dto_drift_findings(repo_root: Path, files: Iterable[Path]) -> list[Finding]:
    models: list[DtoModel] = []
    for path in files:
        rel_path = relative_path(repo_root, path)
        try:
            tree = ast.parse(path.read_text(encoding=ENCODING), filename=rel_path)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and is_dto_model(node):
                fields = dto_fields(node)
                if len(fields) >= 2:
                    models.append(
                        DtoModel(
                            name=node.name,
                            path=rel_path,
                            line=node.lineno,
                            fields=frozenset(fields),
                            typed_fields=frozenset(
                                f"{name}:{annotation}"
                                for name, annotation in fields.items()
                            ),
                        )
                    )

    findings = []
    for index, left in enumerate(models):
        for right in models[index + 1 :]:
            if left.path == right.path and left.name == right.name:
                continue
            similarity = dto_similarity(left, right)
            if similarity < 0.8:
                continue
            severity = (
                4
                + int(similarity == 1.0)
                + int(is_boundary_path(left.path) or is_boundary_path(right.path))
            )
            message = (
                f"DTO `{left.name}` is {similarity:.0%} field-similar to "
                f"`{right.name}` in `{right.path}`; review boundary contract drift."
            )
            findings.append(
                Finding(
                    path=left.path,
                    line=left.line,
                    category="dto-drift",
                    detector="pydantic-field-similarity",
                    severity=min(10, severity),
                    message=message,
                    evidence={
                        "model": left.name,
                        "similar_model": right.name,
                        "similar_path": right.path,
                        "similarity": round(similarity, 3),
                        "fields": sorted(left.fields),
                    },
                )
            )
    return findings


def collect_test_proximity_findings(
    repo_root: Path, production_files: Iterable[Path], test_files: Iterable[Path]
) -> list[Finding]:
    tests_by_app: dict[str, list[Path]] = defaultdict(list)
    test_text_by_app: dict[str, str] = defaultdict(str)
    for test_file in test_files:
        parts = test_file.relative_to(repo_root).parts
        if len(parts) < 2:
            continue
        app = parts[1]
        tests_by_app[app].append(test_file)
        test_text_by_app[app] += "\n" + test_file.read_text(encoding=ENCODING)

    findings = []
    for path in production_files:
        rel_path = relative_path(repo_root, path)
        if path.name == "__init__.py":
            continue
        parts = path.relative_to(repo_root).parts
        if len(parts) < 2:
            continue
        app = parts[1]
        module_stem = path.stem
        package_tail = ".".join(
            path.with_suffix("").relative_to(repo_root / "apps" / app / "src").parts
        )
        matching_name = any(
            module_stem in test_path.stem for test_path in tests_by_app.get(app, [])
        )
        mentioned = module_stem in test_text_by_app.get(
            app, ""
        ) or package_tail in test_text_by_app.get(app, "")
        if not matching_name and not mentioned:
            findings.append(
                Finding(
                    path=rel_path,
                    line=1,
                    category="test-proximity",
                    detector="nearby-test-name-or-mention",
                    severity=1,
                    message=(
                        "No obvious nearby test file or test text mention for this "
                        "production module."
                    ),
                    evidence={"module_stem": module_stem, "package": package_tail},
                )
            )
    return findings


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Python Quality Radar",
        "",
        "Report-only review queue for production Python under `apps/*/src/**/*.py`.",
        "",
        "## Summary",
        "",
        f"- Production files scanned: {summary['production_file_count']}",
        f"- Findings: {summary['finding_count']}",
        f"- Review packets: {summary['review_packet_count']}",
        "",
        "## Category Counts",
        "",
    ]
    for category in CATEGORIES:
        lines.append(f"- `{category}`: {report['category_counts'][category]}")

    findings_by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in report["findings"]:
        findings_by_path[finding["path"]].append(finding)

    lines.extend(["", "## Ranked Review Packets", ""])
    for packet in report["review_packets"][:50]:
        categories = ", ".join(f"`{category}`" for category in packet["categories"])
        lines.extend(
            [
                f"### `{packet['path']}`",
                "",
                (
                    f"Score: {packet['score']} | Findings: "
                    f"{packet['finding_count']} | Categories: {categories}"
                ),
                "",
            ]
        )
        for finding in sorted(
            findings_by_path[packet["path"]], key=_finding_dict_rank_key
        )[:12]:
            lines.append(
                f"- L{finding['line']} `{finding['category']}` "
                f"({finding['detector']}, severity {finding['severity']}): "
                f"{finding['message']}"
            )
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "- Route-edge metrics are heuristic and should be reviewed in context.",
            (
                "- Test-proximity is weak supporting evidence, not a production-code "
                "style finding."
            ),
            "- `TRY003` is intentionally excluded.",
            "",
        ]
    )
    return "\n".join(lines)


def build_review_packets(findings: Iterable[Finding]) -> list[ReviewPacket]:
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.path].append(finding)

    packets = []
    for path, path_findings in grouped.items():
        score = sum(finding.severity for finding in path_findings)
        categories = tuple(sorted({finding.category for finding in path_findings}))
        packets.append(
            ReviewPacket(
                path=path,
                score=score,
                finding_count=len(path_findings),
                categories=categories,
            )
        )
    return sorted(packets, key=lambda packet: (-packet.score, packet.path))


def non_comment_loc(text: str) -> int:
    return sum(
        1
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def node_span(node: ast.AST) -> int:
    return max(
        1,
        int(getattr(node, "end_lineno", getattr(node, "lineno", 1)))
        - int(getattr(node, "lineno", 1))
        + 1,
    )


def function_arg_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if args and args[0].arg in {"self", "cls"}:
        args = args[1:]
    return len(args)


def route_methods(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    methods = set()
    for decorator in node.decorator_list:
        call = decorator if isinstance(decorator, ast.Call) else None
        target = call.func if call else decorator
        if isinstance(target, ast.Attribute) and target.attr in ROUTE_METHODS:
            methods.add(target.attr)
    return methods


def is_dto_model(node: ast.ClassDef) -> bool:
    if not node.name.endswith(DTO_NAME_SUFFIXES):
        return False
    return any(
        base_name(base).endswith(("BaseModel", "CloudContractModel"))
        for base in node.bases
    )


def dto_fields(node: ast.ClassDef) -> dict[str, str]:
    fields = {}
    for child in node.body:
        if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            if child.target.id.startswith("_"):
                continue
            fields[child.target.id] = ast.unparse(child.annotation)
    return fields


def dto_similarity(left: DtoModel, right: DtoModel) -> float:
    left_fields = left.typed_fields or frozenset(f"{name}:*" for name in left.fields)
    right_fields = right.typed_fields or frozenset(f"{name}:*" for name in right.fields)
    if not left_fields or not right_fields:
        return 0.0
    return len(left_fields & right_fields) / len(left_fields | right_fields)


def is_boundary_path(path: str) -> bool:
    return any(
        marker in Path(path).parts or marker in Path(path).stem
        for marker in BOUNDARY_PATH_MARKERS
    )


def base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return base_name(node.value)
    return ""


def ruff_category(code: str) -> str:
    if code.startswith("S"):
        return "security"
    if code.startswith("ASYNC"):
        return "async"
    if code.startswith("TRY"):
        return "error-handling"
    return "complexity"


def ruff_severity(code: str) -> int:
    if code.startswith(("C901", "PLR0912", "PLR0915")):
        return 7
    if code.startswith("PLR0913"):
        return 5
    if code.startswith("S"):
        return 6
    if code.startswith("ASYNC"):
        return 5
    if code.startswith("TRY"):
        return 3
    return 3


def run_tool(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv assembled by this tool.
        command, cwd=cwd, text=True, capture_output=True, check=False
    )


def tool_error(
    category: str, detector: str, result: subprocess.CompletedProcess[str]
) -> list[Finding]:
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    message = detail[-1] if detail else f"{detector} exited {result.returncode}."
    return [
        Finding(
            path=".",
            line=1,
            category=category,
            detector=f"{detector}-error",
            severity=1,
            message=f"Tool did not complete cleanly: {message}",
            evidence={"returncode": result.returncode},
        )
    ]


def first_json_report(path: Path) -> Path | None:
    candidates = sorted(path.rglob("*.json"))
    for candidate in candidates:
        if "jscpd" in candidate.name or candidate.name == "report.json":
            return candidate
    return candidates[0] if candidates else None


def normalize_tool_path(repo_root: Path, value: str) -> str:
    if not value:
        return "."
    path = Path(value)
    if path.is_absolute():
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def relative_path(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _rank_key(finding: Finding) -> tuple[int, str, int, str, str]:
    return (
        -finding.severity,
        finding.path,
        finding.line,
        finding.category,
        finding.detector,
    )


def _finding_dict_rank_key(finding: dict[str, Any]) -> tuple[int, int, str, str]:
    return (
        -int(finding["severity"]),
        int(finding["line"]),
        finding["category"],
        finding["detector"],
    )
