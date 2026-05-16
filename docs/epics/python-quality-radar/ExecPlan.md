# Python Quality Radar

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this work, Dirt maintainers can run a single report-only command that surfaces likely Python application-code quality and architecture debt introduced by high-speed AI-assisted development. The command will not claim that every finding is a bug. It will create a high-recall review queue for likely bloat, duplication, over-complex functions, weak boundary contracts, broad exception handling, dependency drift, and under-tested hot spots in production code.

This matters because vibe coding often shifts effort from writing code to verifying code. Sonar's 2026 State of Code report says 96% of developers do not fully trust AI-generated code, yet only 48% always verify AI-assisted code before committing. GitClear's 2025 AI code quality report describes rising copy/paste and falling refactoring in 211 million changed lines. A 2025 arXiv paper, "Is Vibe Coding Safe?", reports that coding agents can produce functionally correct but insecure implementations on real-world vulnerability tasks. Dirt already has unusually strong architectural constraints, but the Python codebase still needs a broad radar that finds suspicious areas before reviewers decide which ones deserve cleanup or new invariants.

The observable result is a generated report in `var/reports/python-quality-radar/` plus a JSON artifact that can be diffed across runs. A reviewer can open the Markdown report, pick a high-ranked file such as a large control loop or gateway boundary module, inspect the concrete signals, and decide whether to refactor source code, add tests, add a new guardrail, or mark a detector as too noisy.


## Progress

- [x] (2026-05-16T00:00Z) Researched common vibe-coding failure modes and mapped them to existing Dirt Python constraints.
- [x] (2026-05-16T00:00Z) Ran exploratory local scans for production Python file size, function span, Ruff complexity rules, raw payloads, broad exception handling, duplication probes, weak test-name signals, and dependency hygiene noise.
- [x] (2026-05-16T00:00Z) Created this planning epic and ExecPlan.
- [x] (2026-05-16T13:51:24-06:00) Milestone 1: Add a report-only radar script with deterministic JSON and Markdown output.
- [x] (2026-05-16T13:56:52-06:00) Milestone 2: Add focused detector tests and baseline the current Python codebase.
- [x] (2026-05-16T14:00:50-06:00) Milestone 3: Review the first report and create a prioritized cleanup backlog.
- [ ] Milestone 4: Run targeted cleanup passes over the highest-value findings.
- [ ] Milestone 5: Promote repeated true-positive detector classes into guardrails.


## Surprises & Discoveries

- Observation: Dirt already has invariant tests for several AI-code failure modes.
  Evidence: `apps/tests/invariants/` includes checks for import boundaries, auth boundaries, raw SQL outside the data layer, direct env reads outside config, module-level singletons, concrete clocks in production, patching production code, and schema ownership.

- Observation: Broad lint selection across all Python files is misleading because tests intentionally tolerate rougher style, and `TRY003` is not a useful signal for this audit.
  Evidence: The all-`apps` scan produced 541 findings, including 385 magic-value comparisons, but most magic-value findings were in tests. The original production-only scan also included 77 `TRY003` long-exception-message findings, which are style noise for Dirt. A corrected production-only scan with `uv run ruff check apps/*/src --select C901,PLR0912,PLR0915,PLR0913,PLR2004,TRY300,B904,S,ASYNC,F401,ARG --statistics` produced 56 findings. The radar should score `apps/*/src` findings, exclude `TRY003`, and treat tests only as coverage/proximity evidence.

- Observation: Complexity signals already point to a small set of review targets.
  Evidence: `uv run ruff check apps --select C901,PLR0912,PLR0915,PLR0913 --output-format=concise` flagged complex functions including `HumidifierLoopService.run`, `decide_fan_trim`, `collect_agent_trace`, `_backlinks_for`, `build_sensor_tools`, and wake-word training helpers.

- Observation: A hand-rolled AST clone prototype found a few candidates, but it should not become the implementation path.
  Evidence: Duplicate-ish bodies included `open_capture_policy` in `apps/shared/src/dirt_shared/services/camera_publisher.py` and `_open_capture_policy` in `apps/control-plane/src/dirt_control/api/gateway.py`, plus repeated `_load_state` helpers in hwd watchdog/freshness services. The final duplication detector should use `jscpd` instead of maintaining custom clone logic.

- Observation: Root-level dependency hygiene is too noisy in this workspace shape.
  Evidence: `uv run deptry apps --json-output /tmp/dirt-deptry.json` reported 1052 issues, mostly because workspace packages and dev dependencies are resolved differently from a single-package project. Dependency detection must run per package or use a custom workspace-aware collector.

- Observation: The current test suite has broad coverage volume.
  Evidence: `uv run pytest --collect-only -q` collected 664 tests.

- Observation: Test-code quality is not the primary target for this epic.
  Evidence: Dirt already accepts that tests may be more repetitive or literal than production code when that makes behavior clear. The useful test signal for this epic is whether production hot spots have meaningful tests nearby, not whether test files have magic constants or duplicated fixtures.

- Observation: The first report-only run produced no current findings for duplication, DTO drift, Ruff security, or Ruff async categories at the configured thresholds, but those categories are still present in the JSON schema and Markdown category counts.
  Evidence: `scripts/python-quality-radar --format json --output var/reports/python-quality-radar/latest.json` reported `duplication: 0`, `dto-drift: 0`, `security: 0`, and `async: 0` with no tool-error findings.

- Observation: Rendered JSON is deterministic through `sort_keys=True`, while Markdown category counts intentionally follow the canonical radar category order.
  Evidence: `apps/shared/tests/test_python_quality_radar.py` now asserts canonical in-memory category ordering, alphabetized rendered JSON object keys, ranked finding order, and Markdown category ordering.


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

- Decision: Do not score test-code style as product debt.
  Rationale: Functional tests are allowed to be more literal, repetitive, and fixture-heavy than app code. The radar may inspect tests to estimate coverage proximity, but findings such as magic comparisons, duplicate setup, long test functions, or rough fixture style should not rank production cleanup work.
  Date/Author: 2026-05-16 / User + Codex

- Decision: Exclude Ruff `TRY003` from the radar.
  Rationale: `TRY003` flags long exception messages outside exception classes. In this repo that is not a meaningful proxy for vibe-coded bloat, poor architecture, duplication, or correctness risk. The exception-handling signals worth reviewing are broad catches, swallowed failures, missing structured context, and overly wide `try` blocks around boundary or hardware operations.
  Date/Author: 2026-05-16 / User + Codex

- Decision: Use `jscpd` for duplication detection.
  Rationale: Clone detection is a solved tool problem. `jscpd` gives configurable token/block thresholds and machine-readable reports across Python files, which is better than maintaining a bespoke line-window or AST-body clone detector.
  Date/Author: 2026-05-16 / User + Codex

- Decision: Keep FastAPI route scanning simple and explicitly mark it as tricky.
  Rationale: Route functions are a useful place to catch business logic leaking into HTTP edge code, but deep semantic route analysis would be brittle. The first implementation should identify `@router.get` / `@router.post` style handlers and report simple metrics: span, branch count, direct model/db/infrastructure imports, and obvious service bypasses.
  Date/Author: 2026-05-16 / User + Codex

- Decision: Skip lexical shared-module app-specific vocabulary scanning.
  Rationale: Existing import-boundary invariants already catch hard shared-to-app dependency violations. Lexical scans for words such as gateway, web, hwd, or voice inside `dirt_shared` would be noisy and would duplicate weaker versions of the protected invariants.
  Date/Author: 2026-05-16 / User + Codex

- Decision: Use Ruff `S` rules for the security radar surface.
  Rationale: Ruff's Bandit-derived `S` rules are enough for the first report. Custom security regexes should not be added until the Ruff output shows a concrete gap.
  Date/Author: 2026-05-16 / User + Codex

- Decision: Use Ruff `ASYNC` rules for async blocking-risk detection.
  Rationale: The repo already uses Ruff async rules. A custom AST scanner for blocking calls inside `async def` would duplicate existing tooling and add maintenance cost.
  Date/Author: 2026-05-16 / User + Codex

- Decision: Use Ruff `TRY300` only for wide-try/success-path review signals.
  Rationale: `TRY300` is a lightweight pointer to try-block structure. Custom try-block AST analysis is unnecessary for the first report.
  Date/Author: 2026-05-16 / User + Codex

- Decision: Use Semgrep for repo-specific AST-like pattern detectors.
  Rationale: Route-edge leakage, boundary raw payloads, service infrastructure imports, and simple thin-wrapper shapes are pattern-matching problems. Semgrep already provides Python-aware structural matching and JSON output, so the radar should use Semgrep rules instead of reinventing an AST parser for those detectors. Keep custom Python code for aggregation, scoring, DTO field-set comparison, and test proximity.
  Date/Author: 2026-05-16 / User + Codex

- Decision: Prefer existing analyzers and a thin Dirt-specific orchestrator over adding a quality platform to this epic.
  Rationale: The repo already uses Ruff, pytest, import-linter, deptry, and custom invariant tests; this plan adds `jscpd` and Semgrep rather than building a general static-analysis engine. A small collector that composes tool outputs is easier to inspect and tune than introducing a heavyweight service. SonarQube is a separate future project, not part of this ExecPlan.
  Date/Author: 2026-05-16 / Codex

- Decision: Treat boundary-contract drift as a first-class signal, not just a type-style concern.
  Rationale: Dirt's `docs/rules/boundary-contracts.md` exists because raw gateway dictionaries already caused a real hosted dashboard bug. Raw `dict[str, Any]` near HTTP, outbox, command, or persisted JSON boundaries should rank higher than the same type in an internal formatter.
  Date/Author: 2026-05-16 / Codex


## Outcomes & Retrospective

Milestone 1 is implemented as a report-only operator command. The command writes only the requested output path, keeps `jscpd` intermediate files in a temporary directory, and emits deterministic JSON plus a Markdown review queue for production Python files under `apps/*/src/**/*.py`.

Validation completed on 2026-05-16:

    scripts/python-quality-radar --format markdown --output var/reports/python-quality-radar/latest.md
    scripts/python-quality-radar --format json --output var/reports/python-quality-radar/latest.json
    uvx semgrep --validate --config scripts/python-quality-radar-semgrep.yml
    uv run ruff check scripts/lib/python_quality_radar.py scripts/python-quality-radar

All commands exited 0. The generated reports remain under ignored `var/reports/python-quality-radar/` and should not be committed.

Milestone 2 added focused unit tests for local detector behavior and deterministic report ordering without invoking real Ruff, jscpd, or Semgrep execution. The tests use small `tmp_path` fixture apps and monkeypatch external collector boundaries for report-level ordering coverage.

Validation completed on 2026-05-16:

    uv run pytest apps/shared/tests/test_python_quality_radar.py -q
    uv run ruff check apps/shared/tests/test_python_quality_radar.py

Both commands exited 0. The requested simplify pass was completed over the test diff using the sequential fallback because no subagent spawning tool is available in this runtime.

Milestone 3 reviewed the first baseline report and captured the human-readable backlog in `docs/epics/python-quality-radar/baseline-review.md`. The validated baseline scanned 140 production files, used 82 test files for proximity evidence, produced 457 findings, and grouped them into 97 review packets. The review identified the highest-priority cleanup packets as control-plane gateway/browser route modules, gateway command/sync/cloud boundary code, the hwd humidifier loop, and the shared readings service. It also separated likely true-positive classes from noisy detector classes and listed candidate guardrails for Milestone 5.

Validation completed on 2026-05-16:

    scripts/python-quality-radar --format markdown --output var/reports/python-quality-radar/latest.md
    scripts/python-quality-radar --format json --output var/reports/python-quality-radar/latest.json
    sed -n '1,240p' docs/epics/python-quality-radar/baseline-review.md

All commands exited 0. The manual simplify pass over the new baseline review adjusted the validated test-file count and tightened the true-positive cleanup section. Generated reports remain under ignored `var/reports/python-quality-radar/` and should not be committed.


## Context and Orientation

Dirt is a Python 3.13 uv workspace with services under `apps/`. Production Python packages live under paths such as `apps/shared/src/dirt_shared/`, `apps/hwd/src/dirt_hwd/`, `apps/web/src/dirt_web/`, `apps/gateway/src/dirt_gateway/`, `apps/control-plane/src/dirt_control/`, `apps/voice/src/dirt_voice/`, `apps/mcp/src/dirt_mcp/`, `apps/camera-agent/src/dirt_camera_agent/`, and `apps/wake-word/src/dirt_wake_word/`.

The existing human-owned invariant tests under `apps/tests/invariants/` already enforce several architecture rules. They must not be edited while implementing this plan. New guardrails should begin as agent-owned tests outside that directory unless the user explicitly promotes them.

The local architecture rules that matter most for this effort are:

- `docs/rules/simple-clean-architecture.md`: prefer the simplest truthful model, delete misleading old structure, avoid thin wrappers and unnecessary compatibility layers.
- `docs/rules/boundary-contracts.md`: use Pydantic DTOs for process, network, persistence, outbox, command, and generated-client boundaries; avoid raw `dict[str, Any]` for owned protocols.
- `docs/commands.md`: use `uv run ...` for Python commands.

The radar is a review tool. A finding means "review this production location." It does not mean "refactor this blindly." Some large functions are legitimate control loops; some broad exceptions are appropriate daemon resilience; some duplicate shapes should stay separate because they describe different domain concepts. The report should make that tradeoff explicit.

Tests are not part of the production smell scan. The radar may read tests only to answer questions such as "does this complex production module have nearby tests?" or "is this boundary contract exercised by any test?" It should not report test-file magic constants, duplicate fixtures, or long test functions as cleanup candidates.

Important terms:

- `Detector`: a collector that emits one class of finding, such as "function longer than 80 lines" or "broad exception in production code."
- `Finding`: one detector result with a file path, line number when available, severity score, category, and explanation.
- `Review packet`: the grouped findings for one file or small module cluster.
- `Promotion`: converting a detector that repeatedly finds real issues into a test, invariant, lint rule, or AGENTS.md/documentation constraint.


## Plan of Work

Milestone 1 adds a small report-only command. Create `scripts/python-quality-radar` as the operator entrypoint and `apps/shared/src/dirt_shared/tools/python_quality_radar.py` or `scripts/lib/python_quality_radar.py` as the implementation module. Prefer `scripts/lib/` if the code is purely repository tooling and should not be imported by app services. The command scans production files under `apps/*/src/**/*.py`, excluding generated, reference, validation, data-generation, and docker helper paths that are already excluded or special-cased by Ruff. Test files are read only by the low-severity test-proximity detector.

The first detector set should include:

- Size and complexity: non-comment LOC per file, function span, class span, argument count, and Ruff `C901`, `PLR0912`, `PLR0915`, `PLR0913` output.
- Duplication: run `jscpd` against production Python files under `apps/*/src/**/*.py`, with tests and generated/reference helper paths excluded. Parse the `jscpd` JSON output into ranked review packets. Do not implement custom clone detection in v1.
- Route edge logic: use Semgrep rules to scan FastAPI route handlers with decorators such as `@router.get`, `@router.post`, `@router.put`, and `@router.delete`. Report direct DB/model imports or calls, direct infrastructure calls, raw response dictionaries, and obvious service-layer bypasses. Keep route span and branch count in the Python collector because those are metrics, not Semgrep patterns. Mark this detector as tricky and heuristic.
- Service infrastructure imports: use Semgrep rules to report service modules that import infrastructure-heavy packages or process-boundary tools such as `subprocess`, direct env access, cloud SDKs, `httpx`, hardware/client libraries, or framework modules. Score as a review signal, not an automatic smell.
- Boundary payload risk: use Semgrep rules for raw `dict[str, Any]` payloads, bare `Any` boundary parameters, `json.loads`, `json.dumps`, `model_dump`, `model_validate`, FastAPI route return annotations, command payload/result fields, and outbox/cloud/gateway modules. Findings in gateway/control-plane/outbox/command files should score higher.
- Duplicate DTO / boundary model drift: compare Pydantic `BaseModel` classes ending in names like `Request`, `Response`, `Payload`, `Command`, or `Event` by field-name and type sets, especially across `dirt_shared`, `dirt_gateway`, `dirt_control`, and `dirt_web`.
- Thin wrappers and stale forwarding: use Semgrep rules for simple forwarding shapes such as `return other(...)`, `return await other(...)`, and `return self._client.method(...)`, plus lexical markers such as `legacy`, `compat`, `adapter`, `alias`, `deprecated`, `temporary`, or `TODO remove`. Keep this contextual because real adapters and protocols can be valid.
- Error handling: broad `except Exception`, bare `except`, `pass` in exception handlers, `contextlib.suppress`, and low-priority Ruff `TRY300` findings. Do not collect `TRY003` or implement custom try-block AST analysis.
- Security: consume Ruff `S` findings only. Do not add custom security regexes in v1.
- Async blocking risk: consume Ruff `ASYNC` findings only. Do not add custom async AST scanning in v1.
- Suppressions: `# noqa`, `type: ignore`, `pragma: no cover`, and related comments.
- Test proximity: production files with no obvious matching test module or no test text mentioning the module stem; this is weak evidence and should score low unless combined with complexity or boundary findings. Do not emit style findings for the test files themselves.

Milestone 2 adds focused tests for the radar itself. Use small fixture files under an agent-owned test directory such as `apps/shared/tests/test_python_quality_radar.py` if the implementation is in `dirt_shared`, or add a pytest file under a new tooling test location if the repository already has a pattern for scripts tests. The tests should prove that each detector emits deterministic findings with stable categories and that the Markdown/JSON output order is stable.

Milestone 3 runs the first baseline report and writes a human-readable review backlog. Add a checked-in summary document such as `docs/progress/python-quality-radar-baseline.md` or `docs/epics/python-quality-radar/baseline-review.md`. Do not check in the raw generated report unless it is short enough to be useful. The baseline review should list the top review packets, the likely false-positive classes, and candidate invariants.

Milestone 4 performs targeted cleanup on the highest-value true positives. Use the source-level cleanup bias from `AGENTS.md`: trace producer to storage/API to consumer/tests, identify the canonical owner, and delete dead paths instead of adding adapters. Avoid broad refactors in hardware-control services unless tests pin current behavior tightly enough.

Milestone 5 promotes repeated true positives into guardrails. Candidate guardrails include:

- Agent-owned test that all owned boundary DTOs use Pydantic instead of raw dictionaries in gateway/control-plane protocol paths.
- Agent-owned test that broad exception handlers in production loops either re-raise, return an explicit typed failure, or log structured context with `log_event()`.
- Report-only or warning test for functions/classes over agreed thresholds, with allowlists requiring rationale.
- `jscpd` threshold for repeated production-code blocks, with an explicit ignore list for generated or vendored/reference files.
- Report-only review of route handlers that grow past the agreed edge-code threshold.
- Report-only review of thin wrappers and stale forwarding code before any guardrail promotion.


## Concrete Steps

From the repository root:

    cd /home/akcom/code/dirt

Create the tooling entrypoint and implementation:

    scripts/python-quality-radar --help
    scripts/python-quality-radar --format markdown --output var/reports/python-quality-radar/latest.md
    scripts/python-quality-radar --format json --output var/reports/python-quality-radar/latest.json

Run the duplication detector directly while developing the radar:

    pnpm dlx jscpd "apps/*/src/**/*.py" --reporters json,markdown --output var/reports/python-quality-radar/jscpd --ignore "**/tests/**" --ignore "**/reference/**" --ignore "**/data-gen/**" --ignore "**/validation/**" --ignore "**/docker/**"

Run the Semgrep pattern suite directly while developing the radar:

    uvx semgrep --config scripts/python-quality-radar-semgrep.yml --json apps/*/src

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
- The report includes at least these production-code categories: `complexity`, `duplication`, `route-edge`, `service-infrastructure`, `boundary`, `dto-drift`, `thin-wrapper`, `error-handling`, `security`, `async`, and `suppression`, plus the supporting `test-proximity` category.
- Focused tests cover detector behavior and output ordering.
- The first baseline review document identifies top review packets and separates true-positive cleanup candidates from noisy detector classes.
- Existing human-owned invariants still pass.
- No generated report artifacts under `var/` are committed.

Human review acceptance for the epic is stronger than command success. Reviewers should be able to use the report to choose concrete cleanup work without re-running the exploratory analysis manually.


## Idempotence and Recovery

The radar command must be safe to run repeatedly. It only reads repository files and writes report artifacts under `var/reports/python-quality-radar/`. Re-running the command with the same working tree should produce stable ordering and stable scores.

If a detector is too noisy, do not delete it immediately. Lower its severity, mark it report-only, or add a narrow suppression reason to the baseline review. Only promote detectors after at least one report review confirms repeated true positives.

If implementation changes accidentally touch human-owned invariants under `apps/tests/invariants/`, revert only those edits and move the new check into an agent-owned test. Do not alter the protected invariant files as part of this plan.

If dependency hygiene output remains noisy, keep it out of the first report until a workspace-aware package mapping exists. Do not gate CI on raw `deptry apps` output.


## Artifacts and Notes

Exploratory commands already run during planning:

    uv run ruff check apps --select C901,PLR0912,PLR0915,PLR0913 --output-format=concise

This found 9 complexity findings, including complex functions in hwd control services, shared agent tracing/wiki helpers, voice tool construction, and wake-word training code.

    uv run ruff check apps/*/src --select C901,PLR0912,PLR0915,PLR0913,PLR2004,TRY300,B904,S,ASYNC,F401,ARG --statistics

This corrected production-only scan found 56 issues: 28 `PLR2004`, 13 `ARG001`, 6 `C901`, 4 `ARG002`, 3 `TRY300`, and 2 `PLR0912`. Adding Ruff `S` and `ASYNC` to the source-only selection did not add findings in the current tree, but those rule families remain part of the radar.

    uv run pytest --collect-only -q

This collected 664 tests.

    uv run deptry apps --json-output /tmp/dirt-deptry.json

This produced 1052 dependency issues, mostly workspace-shape noise. Keep dependency hygiene out of v1 unless a workspace-aware package mapping is added.

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
- `jscpd` integration for primary duplication detection, invoked through `pnpm dlx jscpd` unless the implementation later adds a pinned repo-local dev dependency.
- Semgrep rule file such as `scripts/python-quality-radar-semgrep.yml` for route-edge leakage, boundary raw payloads, service infrastructure imports, and thin-wrapper candidates.
- Simple route span and branch-count metrics in the Python collector, marked heuristic in the report output.
- Pydantic DTO field-set similarity scanner.
- Ruff integration for `S`, `ASYNC`, and `TRY300` signals, with `TRY003` excluded.
- Focused pytest coverage for detector behavior and deterministic output.
- A baseline review document under `docs/epics/python-quality-radar/` or `docs/progress/`.

The implementation should prefer existing analyzers over custom parsing: Ruff for lint/security/async/try signals, `jscpd` for duplication, Semgrep for repo-specific structural patterns, and custom Python only for aggregation, scoring, DTO field-set comparison, route metrics, and test proximity. Do not include SonarQube in this ExecPlan; evaluate it separately if a dashboard/platform project is desired later.


## Revision Notes

- 2026-05-16: Initial ExecPlan created from the Python vibe-coding quality audit discussion and exploratory local scans.
- 2026-05-16: Revised scope to make production app code the scored surface and tests supporting coverage evidence only.
- 2026-05-16: Removed `TRY003` from scope after review showed it only flagged long exception messages, which are not useful product-debt signals here.
- 2026-05-16: Revised duplication detection to prefer `jscpd` over a custom clone detector.
- 2026-05-16: Revised detector set after review: keep simple route scanning, service infrastructure imports, duplicate DTO detection, thin wrappers, Ruff `S`, Ruff `ASYNC`, and Ruff `TRY300`; skip lexical shared-module vocabulary scanning and custom security/async/try AST detectors.
- 2026-05-16: Revised AST-like repo-specific detectors to use Semgrep rules instead of custom AST parsing, and left SonarQube for a separate future project.
