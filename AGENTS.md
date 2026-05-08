# AGENTS.md

**Dirt** — home grow monitoring + agent-maintained wiki. Python ≥3.13 (uv workspace services under `apps/`), Vite/React frontend (`web-ui/`), PostgreSQL 17, ESP32 firmware (`firmware/`).

> **IMPORTANT — read this first.** Before writing any code or running any
> command, scan the documentation map below and load the deep-dive doc(s)
> that match what you're about to do. The triggers tell you *when* each
> doc is load-bearing. Don't proceed on this index alone.

## Repository layout

- `apps/{hwd,web,shared,mcp,voice,wake-word,control-plane,gateway}/` — Python services (uv workspace; each has its own `pyproject.toml` + tests). `dirt-hwd` runs on :8000 (production keep-alive — no routine rewrites), `dirt-web` on :8001 (UI + MCP), `dirt-gateway` syncs outbound to the hosted control plane.
- `apps/tests/invariants/` — **HUMAN-OWNED** architectural rules. Never modify; fix code to satisfy the test instead.
- `apps/wake-word/` — wake-word retraining infra; data artifacts gitignored under `var/wake-word/`. Read [`apps/wake-word/AGENTS.md`](apps/wake-word/AGENTS.md) before touching.
- `firmware/{fan_controller,reservoir_node,…}/` — ESP32 firmware (PlatformIO).
- `web-ui/` — Vite + React + TS + TanStack Router/Query + Tailwind v4 + Biome. Dev server :5173.
- `wiki/` — agent-maintained grow knowledge base. Start at [`wiki/AGENTS.md`](wiki/AGENTS.md) for any wiki work.
- `var/` — runtime data (snapshots, logs, sessions, photos, db-backups, wake-word artifacts). Gitignored. Override root via `DIRT_DATA_DIR`.
- `contracts/` — OpenAPI spec + generated Pydantic + TS schema.
- `debug/` — agent sandbox. Write throwaway scripts here; never imported by app code.
- `docs/` — progressive-disclosure index (next section).
- `systemd/` — user-level systemd units; `scripts/install-systemd` symlinks them.

## Documentation map

Read the linked doc *before* doing the activity in the trigger column.

### Operations

| Doc | Read before |
|---|---|
| [`docs/commands.md`](docs/commands.md) | running anything (dev/test/lint/firmware/web-ui/PTZ/voice/daily-report/web-api auth/hosted deploys) |
| [`docs/database.md`](docs/database.md) | writing SQL, editing `apps/shared/src/dirt_shared/models/`, running `atlas migrate` |
| [`docs/observability.md`](docs/observability.md) | calling `log_event()`, debugging across `var/logs/`, adding a new log stream, writing tests that touch shared filesystem |
| [`docs/hosted-control-plane.md`](docs/hosted-control-plane.md) | deploying or rolling back Railway hosted control plane, operating `dirt-gateway`, checking cloud health, rotating hosted secrets, pruning cloud assets |
| [`docs/grow-state.md`](docs/grow-state.md) | writing code that branches on stage (veg / flower_early / flower_late) or needs current germination/flower-flip date |

### Framework anchors (override training-data drift)

`docs/references/<pack>/INDEX.md` for any of these — full trigger + drift-warning text in [`docs/references/INDEX.md`](docs/references/INDEX.md).

| Pack | Read before |
|---|---|
| `pipecat/` | importing `pipecat.*`, building Pipeline/PipelineTask, Pipecat services, transports, VAD |
| `tanstack-router-v1/` | `web-ui/src/routes/`, `createFileRoute`/`createRouter`, route loaders, search params |
| `tailwind-v4/` | utility classes in `web-ui/src/`, `web-ui/src/styles.css`, vite tailwind config |
| `govee-api/` | `openapi.api.govee.com/router/api/v1/...`, humidifier loop edits |
| `atlas/` | Atlas HCL schema, `atlas.hcl`, `atlas migrate diff/apply/lint`, files under `migrations/` |
| `msw-v2/` | `web-ui/src/mocks/**`, `msw` imports, http handlers, `setupWorker`/`setupServer` |
| `wandb/` | `wandb` imports in `apps/wake-word/`, `wandb.*` calls, `WANDB_*` env vars, sweep configs |
| `runpod/` | `rest.runpod.io/v1/...`, `runpod` PyPI package, `runpodctl`, GPU training orchestration |
| `claude-agent-sdk/` | `claude_agent_sdk` imports, `query()`/`ClaudeSDKClient`, sub-agents under `apps/voice/src/dirt_voice/tools/` |
| `deepgram-tts-aura-2/` | Deepgram TTS REST/WebSocket calls, voice id, TTS auth |
| `modern-idiomatic-typescript/` | any `.ts`/`.tsx` authoring, `tsconfig.json`, lint/format tooling choices |

### Architecture & process

- [`docs/README.md`](docs/README.md) — full doc index (front door for the docs/ tree)
- [`docs/adrs/`](docs/adrs/) — settled decisions; read before proposing alternatives
- [`docs/epics/`](docs/epics/) — in-flight epic context
- [`docs/progress/`](docs/progress/) — feature progress between PRs
- [`docs/rules/`](docs/rules/) — codebase rules and conventions. Read [`docs/rules/boundary-contracts.md`](docs/rules/boundary-contracts.md) before changing FastAPI request/response models, gateway/control-plane payloads, outbox JSON, command payloads/results, generated API contracts, or any other process/network/persistence boundary.

## How agents work here

- **ExecPlans**: When writing complex features or significant refactors, use an ExecPlan (as described in `.agents/PLANS.md`) from design to implementation.
- **Boundary contracts**: Pydantic DTOs are the schema mechanism for process, network, persistence, outbox, command, and generated-client boundaries. Do not hand-roll raw `dict[str, Any]` payloads for owned protocols; read [`docs/rules/boundary-contracts.md`](docs/rules/boundary-contracts.md) first.
- **Source-level cleanup bias**: When a change reveals stale naming, unit mismatch, duplicated truth, legacy branches, or test-harness friction, prefer fixing the source contract over adding adapters or compatibility glue. First trace producer → storage/API → consumer → tests; identify the canonical owner; search live legacy usage/data with `rg`/`find`; delete dead paths instead of preserving them. If agent-owned tests encode the old contract, update them. Never edit human-owned invariants; treat failures as architecture feedback. Examples: split mixed wake-word data buckets instead of documenting around misleading names; normalize sensor units at the producing service/shared model boundary instead of converting in every consumer.
- **Scratch dir**: write throwaway scripts to `debug/`. Don't clutter `apps/` or `scripts/`.
- **Hosted deploys**: use only `scripts/deploy-control-plane` for Railway deployments. It applies the dedicated cloud Atlas migrations before deploying `control-plane-api` and `web-ui`; do not run app-start DDL or ad hoc `railway up` for these services.
- **Commits**: run `scripts/agent-fix` before `git add` + `git commit`. Pre-commit hooks are write-mode; if a hook modifies files, re-add and re-commit. Never `--no-verify`. Don't auto-amend.
- **Tests**: `apps/tests/invariants/` is HUMAN-OWNED — fix your code to pass invariants, never modify them. Per-app tests under `apps/<app>/tests/` are agent-owned. Tests that write to disk must use `tmp_path` and the autouse `isolate_observability_logs` fixture (see [`docs/observability.md`](docs/observability.md)).
- **Risky actions**: confirm before destructive ops (force push, hard reset, rm of unfamiliar files), shared-state mutations, or anything visible to others (chat sends, PR comments). Auto mode does not override this.

## Help

- `/help` for Codex help.

## Repo + project board

- Repo: https://github.com/akravetz/dirt
- Project board: https://github.com/users/akravetz/projects/1/views/1
