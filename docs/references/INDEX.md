# Framework / API Reference Packs

Version-pinned anchors that override training-data drift toward obsolete patterns. Each pack contains a top-level `INDEX.md` plus topic files. **Read the pack's `INDEX.md` before writing code that touches the listed APIs** — most of these have shipped breaking changes that training data still reflects.

## Trigger map

| Pack | Read before |
|---|---|
| [pipecat/](pipecat/INDEX.md) | importing `pipecat.*`, building Pipeline/PipelineTask/PipelineRunner, instantiating a Pipecat service (`AnthropicLLMService`, `DeepgramSTTService`, `ElevenLabsTTSService`, …), configuring a transport (`LocalAudioTransport`, `DailyTransport`), wiring a VAD/`SileroVADAnalyzer` |
| [tanstack-router-v1/](tanstack-router-v1/INDEX.md) | writing or modifying routes in `web-ui/src/routes/`, using `createFileRoute` / `createRootRoute` / `createRouter`, route loaders (`loader`, `beforeLoad`, `loaderDeps`, `staleTime`), URL search params (`validateSearch`, `useSearch`, `<Link search>`, search middlewares) |
| [tailwind-v4/](tailwind-v4/INDEX.md) | writing or refactoring Tailwind utility classes in `web-ui/src/`, editing `web-ui/src/styles.css` (`@import "tailwindcss"` + `@theme`), wiring `vite.config.ts` for the `@tailwindcss/vite` plugin, custom utilities with `@utility`, dark-mode overrides with `@custom-variant` |
| [govee-api/](govee-api/INDEX.md) | calling `https://openapi.api.govee.com/router/api/v1/...`, sending a body shaped like `{requestId, payload: {sku, device, capability: {...}}}`, setting the `Govee-API-Key` header, editing the humidifier control loop in `apps/hwd/src/dirt_hwd/services/humidifier.py` |
| [atlas/](atlas/INDEX.md) | writing or modifying Atlas HCL schema files, editing `atlas.hcl`, running `atlas migrate diff`/`apply`/`lint`, configuring the SQLAlchemy external schema loader, authoring migration files under `migrations/` |
| [msw-v2/](msw-v2/INDEX.md) | writing or modifying any code under `web-ui/src/mocks/**`, importing from `msw` / `msw/browser` / `msw/node`, defining a request handler (`http.get/post/put/patch/delete`), `setupWorker` or `setupServer`, running `msw init <public-dir>` |
| [wandb/](wandb/INDEX.md) | importing `wandb` (in `apps/wake-word/src/dirt_wake_word/` or `apps/wake-word/docker/entrypoint.py`), calling `wandb.init`/`log`/`finish`/`log_artifact`/`Table`/`alert`, polling `wandb.Api().run(id).state`, setting a `WANDB_*` env var, designing a sweep config |
| [runpod/](runpod/INDEX.md) | calling `https://rest.runpod.io/v1/...` or `https://api.runpod.io/graphql`, importing the `runpod` PyPI package, shelling out to `runpodctl`, orchestrating a one-shot GPU training job on RunPod |
| [claude-agent-sdk/](claude-agent-sdk/INDEX.md) | importing from `claude_agent_sdk`, calling `query()` or `ClaudeSDKClient`, configuring `ClaudeAgentOptions` (cwd, allowed_tools, disallowed_tools, permission_mode, system_prompt, hooks, can_use_tool), building a local Claude-Code-style research sub-agent (e.g. `apps/voice/src/dirt_voice/tools/wiki.py`) |
| [deepgram-tts-aura-2/](deepgram-tts-aura-2/INDEX.md) | calling Deepgram text-to-speech (REST `POST /v1/speak` or WebSocket `wss://api.deepgram.com/v1/speak`), picking a voice/model id, setting up the voice agent's TTS output, handling Deepgram auth |
| [modern-idiomatic-typescript/](modern-idiomatic-typescript/INDEX.md) | writing or refactoring any `.ts`/`.tsx` file, choosing lint/format tooling, editing `tsconfig.json` |

## Why these packs exist

Per-pack drift warnings (the "training data will suggest X, use Y" details) live in each pack's `INDEX.md`. Selected highlights:

- **Pipecat v1.0** shipped 2026-04-14 with major breaking changes from v0.x. Training data still suggests `OpenAILLMContext`, `llm.create_context_aggregator(...)`, `TransportParams(vad_analyzer=...)`, `allow_interruptions=True` — all gone or relocated in v1.0.
- **TanStack Router v1**: training data reaches for `react-router-dom`, v0 `new Router()` / `new RootRoute()` syntax, `useSearchParams`, or `useEffect`-based data fetching. All wrong.
- **Tailwind v4** (v4.2.x) is a ground-up rewrite. Training data suggests v3 patterns (`tailwind.config.js` with `content:` / `theme.extend`, the three `@tailwind base/components/utilities` directives, `postcss-cli` + `autoprefixer`, PurgeCSS, JS plugin API, `resolveConfig()`) — all obsolete.
- **Govee Public API v2**: training data mixes the legacy v1 surface (`developer-api.govee.com/v1/devices/control` with `cmd: {name, value}` payload) and gets the auth header name wrong (suggests `X-Govee-API-Key` or `Authorization: Bearer …`; actual header is exactly `Govee-API-Key`). Also covers H71xx capability list, dual rate-limit ceilings (10K/account/day + ~10 changes/min/device), cloud-only constraint.
- **Atlas v1.2** vs Alembic / hand-written SQL / pre-v1 Atlas flag names (`--dev` → `--dev-url`, `atlas migrate validate` → `atlas migrate hash`).
- **MSW v2** (Oct 2023) was a ground-up rewrite of v1. Training data suggests v1 patterns (`rest.get(...)`, `(req, res, ctx) => res(ctx.json(...))`, `req.url.searchParams`, `ctx.status(...)`, `import { setupWorker } from "msw"` without `/browser`).
- **Wandb >=0.21.x**: training data suggests `wandb.plots.*` (removed 0.17.0), `wandb.beta.workflows.log_model` (removed 0.24.0), `WANDB_DISABLE_SERVICE=true` (errors in 0.20+), `run.project_name()` (deprecated 0.19.10), `Table.add_row(...)` (use `add_data`).
- **RunPod**: REST API v1 (launched 2025-03-10) is canonical. Training data reaches for `runpod.create_pod()` (still GraphQL underneath), the older `api.runpod.io/graphql` endpoint, Serverless-for-batch-training, the `ssh.runpod.io` proxy (which doesn't pass SCP), stop-instead-of-delete cleanup (which leaks $0.20/GB-month indefinitely).
- **Claude Agent SDK** was renamed from `claude-code-sdk` at v0.1.0. Training data suggests `ClaudeCodeOptions`, `api_key=...` parameters, `allowed_tools` as an availability filter — all wrong for current versions.
- **Modern TS**: anchor to `satisfies`, discriminated unions, branded types, Biome. Override training-data defaults (`enum`, `namespace`, `any`, ESLint+Prettier scaffolds).

For the full set of warnings + worked examples, open the pack's `INDEX.md` and the linked topic files.
