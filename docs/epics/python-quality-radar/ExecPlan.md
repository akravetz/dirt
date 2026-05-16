# Python Quality Radar

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this work, Dirt maintainers can run a single report-only command that surfaces likely Python quality and architecture debt introduced by high-speed AI-assisted development. The command will not claim that every finding is a bug. It will create a high-recall review queue for likely bloat, duplication, over-complex functions, weak boundary contracts, broad exception handling, dependency drift, and under-tested hot spots.

This matters because vibe coding often shifts effort from writing code to verifying code. Sonar's 2026 State of Code report says 96% of developers do not fully trust AI-generated code, yet only 48% always verify AI-assisted code before committing. GitClear's 2025 AI code quality report describes rising copy/paste and falling refactoring in 211 million changed lines. A 2025 arXiv paper, "Is Vibe Coding Safe?", reports that coding agents can produce functionally correct but insecure implementations on real-world vulnerability tasks. Dirt already has unusually strong architectural constraints, but the Python codebase still needs a broad radar that finds suspicious areas before reviewers decide which ones deserve cleanup or new invariants.

The observable result is a generated report in `var/reports/python-quality-radar/` plus a JSON artifact that can be diffed across runs. A reviewer can open the Markdown report, pick a high-ranked file such as a large control loop or gateway boundary module, inspect the concrete signals, and decide whether to refactor source code, add tests, add a new guardrail, or mark a detector as too noisy.


## Progress

- [x] (2026-05-16T00:00Z) Researched common vibe-coding failure modes and mapped them to existing Dirt Python constraints.
- [x] (2026-05-16T00:00Z) Ran exploratory local scans for Python file size, function span, Ruff complexity rules, raw payloads, broad exception handling, duplicate AST bodies, weak test-name signals, and dependency hygiene noise.
- [x] (2026-05-16T00:00Z) Created this planning epic and ExecPlan.
- [ ] Milestone 1: Add a report-only radar script with deterministic JSON and Markdown output.
- [ ] Milestone 2: Add focused detector tests and baseline the current Python codebase.
- [ ] Milestone 3: Review the first report and create a prioritized cleanup backlog.
- [ ] Milestone 4: Run targeted cleanup passes over the highest-value findings.
- [ ] Milestone 5: Promote repeated true-positive detector classes into guardrails.


## Surprises & Discoveries

- Observation: Dirt already has invariant tests for several AI-code failure modes.
  Evidence: `apps/tests/invariants/` includes checks for import boundaries, auth boundaries, raw SQL outside the data layer, direct env reads outside config, module-level singletons, concrete clocks in production, patching production code, and schema ownership.

- Observation: Broad lint selection is too noisy to become a gate directly.
  Evidence: `uv run ruff check apps --select C901,PLR0912,PLR0915,PLR0913,PLR2004,TRY003,B904,S110,S112,S603,S607,F401,ARG --statistics` produced 541 findings, including 385 magic-value comparisons. That is useful radar input, not a useful CI failure mode.

- Observation: Complexity signals already point to a small set of review targets.
  Evidence: `uv run ruff check apps --select C901,PLR0912,PLR0915,PLR0913 --output-format=concise` flagged complex functions including `HumidifierLoopService.run`, `decide_fan_trim`, `collect_agent_trace`, `_backlinks_for`, `build_sensor_tools`, and wake-word training helpers.

- Observation: Exact AST-body duplication is low, but the quick scan still found concrete candidates.
  Evidence: Duplicate-ish bodies included `open_capture_policy` in `apps/shared/src/dirt_shared/services/camera_publisher.py` and `_open_capture_policy` in `apps/control-plane/src/dirt_control/api/gateway.py`, plus repeated `_load_state` helpers in hwd watchdog/freshness services.

- Observation: Root-level dependency hygiene is too noisy in this workspace shape.
  Evidence: `uv run deptry apps --json-output /tmp/dirt-deptry.json` reported 1052 issues, mostly because workspace packages and dev dependencies are resolved differently from a single-package project. Dependency detection must run per package or use a custom workspace-aware collector.

- Observation: The current test suite has broad coverage volume.
  Evidence: `uv run pytest --collect-only -q` collected 664 tests.


## Decision Log

- Decision: Build a report-only tool first, not a new invariant.
  Rationale: The requested detector should favor recall over precision. CI failures should come only after humans review the first reports and identify repeatable true-positive classes.
  Date/Author: 2026-05-16 / Codex

- Decision: Store generated reports under `var/reports/python-quality-radar/` and keep them gitignored.
  Rationale: Reports are runtime artifacts and may contain large finding inventories. The durable repo changes should be the script, tests, reviewed backlog docs, and eventual invariants.
  Date/Author: 2026-05-16 / Codex

- Decision: Scope the first implementation to Python production code under `apps/*/src`.
  Rationale: The user asked to focus on Python. Tests, wake-word data-generation scripts, firmware, frontend, and wiki content have different quality signals and would dilute the first report.
  Date/Author: 2026-05-16 / Codex

- Decision: Prefer simple AST and existing-tool collectors over adding a large quality platform.
  Rationale: The repo already uses Ruff, pytest, import-linter, deptry, and custom invariant tests. A small collector that composes those signals is easier to inspect and tune than introducing a heavyweight service.
  Date/Author: 2026-05-16 / Codex

- Decision: Treat boundary-contract drift as a first-class signal, not just a type-style concern.
  Rationale: Dirt's `docs/rules/boundary-contracts.md` exists because raw gateway dictionaries already caused a real hosted dashboard bug. Raw `dict[str, Any]` near HTTP, outbox, command, or persisted JSON boundaries should rank higher than the same type in an internal formatter.
  Date/Author: 2026-05-16 / Codex


## Outcomes & Retrospective

No implementation has started. This plan creates the path for a report-first quality audit and later guardrails.


## Context and Orientation

Dirt is a Python 3.13 uv workspace with services under `apps/`. Production Python packages live under paths such as `apps/shared/src/dirt_shared/`, `apps/hwd/src/dirt_hwd/`, `apps/web/src/dirt_web/`, `apps/gateway/src/dirt_gateway/`, `apps/control-plane/src/dirt_control/`, `apps/voice/src/dirt_voice/`, `apps/mcp/src/dirt_mcp/`, `apps/camera-agent/src/dirt_camera_agent/`, and `apps/wake-word/src/dirt_wake_word/`.

The existing human-owned invariant tests under `apps/tests/invariants/` already enforce several architecture rules. They must not be edited while implementing this plan. New guardrails should begin as agent-owned tests outside that directory unless the user explicitly promotes them.

The local architecture rules that matter most for this effort are:

- `docs/rules/simple-clean-architecture.md`: prefer the simplest truthful model, delete misleading old structure, avoid thin wrappers and unnecessary compatibility layers.
- `docs/rules/boundary-contracts.md`: use Pydantic DTOs for process, network, persistence, outbox, command, and generated-client boundaries; avoid raw `dict[str, Any]` for owned protocols.
- `docs/commands.md`: use `uv run ...` for Python commands.

The radar is a review tool. A finding means "review this location." It does not mean "refactor this blindly." Some large functions are legitimate control loops; some broad exceptions are appropriate daemon resilience; some duplicate shapes should stay separate because they describe different domain concepts. The report should make that tradeoff explicit.

Important terms:

- `Detector`: a collector that emits one class of finding, such as "function longer than 80 lines" or "broad exception in production code."
- `Finding`: one detector result with a file path, line number when available, severity score, category, and explanation.
- `Review packet`: the grouped findings for one file or small module cluster.
- `Promotion`: converting a detector that repeatedly finds real issues into a test, invariant, lint rule, or AGENTS.md/documentation constraint.


## Plan of Work

Milestone 1 adds a small report-only command. Create `scripts/python-quality-radar` as the operator entrypoint and `apps/shared/src/dirt_shared/tools/python_quality_radar.py` or `scripts/lib/python_quality_radar.py` as the implementation module. Prefer `scripts/lib/` if the code is purely repository tooling and should not be imported by app services. The command scans `apps/*/src/**/*.py`, excluding generated, reference, validation, data-generation, and docker helper paths that are already excluded or special-cased by Ruff.

The first detector set should include:

- Size and complexity: non-comment LOC per file, function span, class span, argument count, and Ruff `C901`, `PLR0912`, `PLR0915`, `PLR0913` output.
- Duplication: exact AST-body duplicate detection for functions over a small span threshold, plus line-window duplicate detection for repeated blocks of five or more meaningful lines.
- Boundary payload risk: `dict[str, Any]`, bare `Any`, `json.loads`, `json.dumps`, `model_dump`, `model_validate`, FastAPI route return annotations, command payload/result fields, and outbox/cloud/gateway modules. Findings in gateway/control-plane/outbox/command files should score higher.
- Error handling: broad `except Exception`, bare `except`, `pass` in exception handlers, and `contextlib.suppress`.
- Suppressions: `# noqa`, `type: ignore`, `pragma: no cover`, and related comments.
- Dependency/runtime bloat: imports of heavyweight packages at module import time, subprocess/network/filesystem operations, and per-package dependency hygiene where practical.
- Test proximity: production files with no obvious matching test module or no test text mentioning the module stem; this is weak evidence and should score low unless combined with complexity or boundary findings.

Milestone 2 adds focused tests for the radar itself. Use small fixture files under an agent-owned test directory such as `apps/shared/tests/test_python_quality_radar.py` if the implementation is in `dirt_shared`, or add a pytest file under a new tooling test location if the repository already has a pattern for scripts tests. The tests should prove that each detector emits deterministic findings with stable categories and that the Markdown/JSON output order is stable.

Milestone 3 runs the first baseline report and writes a human-readable review backlog. Add a checked-in summary document such as `docs/progress/python-quality-radar-baseline.md` or `docs/epics/python-quality-radar/baseline-review.md`. Do not check in the raw generated report unless it is short enough to be useful. The baseline review should list the top review packets, the likely false-positive classes, and candidate invariants.

Milestone 4 performs targeted cleanup on the highest-value true positives. Use the source-level cleanup bias from `AGENTS.md`: trace producer to storage/API to consumer/tests, identify the canonical owner, and delete dead paths instead of adding adapters. Avoid broad refactors in hardware-control services unless tests pin current behavior tightly enough.

Milestone 5 promotes repeated true positives into guardrails. Candidate guardrails include:

- Agent-owned test that all owned boundary DTOs use Pydantic instead of raw dictionaries in gateway/control-plane protocol paths.
- Agent-owned test that broad exception handlers in production loops either re-raise, return an explicit typed failure, or log structured context with `log_event()`.
- Report-only or warning test for functions/classes over agreed thresholds, with allowlists requiring rationale.
- Clone detector threshold for repeated blocks outside tests.
- Workspace-aware dependency hygiene check for each package's `pyproject.toml`.


## Concrete Steps

From the repository root:

    cd /home/akcom/code/dirt

Create the tooling entrypoint and implementation:

    scripts/python-quality-radar --help
    scripts/python-quality-radar --format markdown --output var/reports/python-quality-radar/latest.md
    scripts/python-quality-radar --format json --output var/reports/python-quality-radar/latest.json

Expected behavior after Milestone 1:

    Wrote var/reports/python-quality-radar/latest.md
    Wrote var/reports/python-quality-radar/latest.json

Run focused tests after Milestone 2:

    uv run pytest apps/shared/tests/test_python_quality_radar.py -q

Expected result:

    ... passed

Run existing broad safety checks after implementation milestones:

    uv run ruff check
    uv run pytest apps/tests/invariants/ -q
    uv run pytest apps/shared/tests/test_python_quality_radar.py -q

Before committing implementation work:

    scripts/agent-fix
    git diff --check


## Validation and Acceptance

The implementation is accepted when these conditions are true:

- `scripts/python-quality-radar --format markdown --output var/reports/python-quality-radar/latest.md` exits 0 and writes a readable report.
- `scripts/python-quality-radar --format json --output var/reports/python-quality-radar/latest.json` exits 0 and writes deterministic JSON with file, line, category, severity, detector, and explanation fields.
- The report includes at least these categories: `complexity`, `duplication`, `boundary`, `error-handling`, `suppression`, `dependency`, and `test-proximity`.
- Focused tests cover detector behavior and output ordering.
- The first baseline review document identifies top review packets and separates true-positive cleanup candidates from noisy detector classes.
- Existing human-owned invariants still pass.
- No generated report artifacts under `var/` are committed.

Human review acceptance for the epic is stronger than command success. Reviewers should be able to use the report to choose concrete cleanup work without re-running the exploratory analysis manually.


## Idempotence and Recovery

The radar command must be safe to run repeatedly. It only reads repository files and writes report artifacts under `var/reports/python-quality-radar/`. Re-running the command with the same working tree should produce stable ordering and stable scores.

If a detector is too noisy, do not delete it immediately. Lower its severity, mark it report-only, or add a narrow suppression reason to the baseline review. Only promote detectors after at least one report review confirms repeated true positives.

If implementation changes accidentally touch human-owned invariants under `apps/tests/invariants/`, revert only those edits and move the new check into an agent-owned test. Do not alter the protected invariant files as part of this plan.

If dependency hygiene output remains noisy, keep it as an optional collector until a workspace-aware package mapping exists. Do not gate CI on raw `deptry apps` output.


## Artifacts and Notes

Exploratory commands already run during planning:

    uv run ruff check apps --select C901,PLR0912,PLR0915,PLR0913 --output-format=concise

This found 9 complexity findings, including complex functions in hwd control services, shared agent tracing/wiki helpers, voice tool construction, and wake-word training code.

    uv run ruff check apps --select C901,PLR0912,PLR0915,PLR0913,PLR2004,TRY003,B904,S110,S112,S603,S607,F401,ARG --statistics

This found 541 issues. The largest bucket was 385 `PLR2004` magic-value comparisons, which confirms that broad lint expansion should feed a report rather than become a direct gate.

    uv run pytest --collect-only -q

This collected 664 tests.

    uv run deptry apps --json-output /tmp/dirt-deptry.json

This produced 1052 dependency issues, mostly workspace-shape noise. Use per-package or custom dependency checks instead of this raw command for acceptance.

External references that motivated detector categories:

- Sonar State of Code Developer Survey 2026: `https://www.sonarsource.com/resources/developer-survey-report/`
- GitClear AI Code Quality Research v2025.2.5: `https://gitclear-public.s3.us-west-2.amazonaws.com/GitClear-AI-Copilot-Code-Quality-2025.pdf`
- LeadDev, "You can't verify all the AI-generated code": `https://leaddev.com/ai/you-cant-verify-all-the-ai-generated-code`
- Zhao et al., "Is Vibe Coding Safe? Benchmarking Vulnerability of Agent-Generated Code in Real-World Tasks": `https://arxiv.org/abs/2512.03262`


## Interfaces and Dependencies

The final implementation should provide:

- `scripts/python-quality-radar`: executable repo-root command.
- A Python implementation module, preferably under `scripts/lib/` unless there is a concrete reason for app services to import it.
- JSON report schema with fields for `path`, `line`, `category`, `detector`, `severity`, `message`, and optional `evidence`.
- Markdown report grouped by ranked review packet.
- Focused pytest coverage for detector behavior and deterministic output.
- A baseline review document under `docs/epics/python-quality-radar/` or `docs/progress/`.

The implementation may use the Python standard library AST support, Ruff via subprocess, and existing dev dependencies already available through `uv run`. Avoid adding new dependencies until the standard-library/existing-tool approach proves insufficient.


## Revision Notes

- 2026-05-16: Initial ExecPlan created from the Python vibe-coding quality audit discussion and exploratory local scans.
