# Pricing and quotas

W&B has been re-pricing aggressively. Numbers below are anchored 2026-04-25; check https://wandb.ai/site/pricing for current values before any commercial decision.

## Tiers

| Tier | Price | Storage | Tracked hours | Model seats | Weave ingestion | Use case |
|---|---|---|---|---|---|---|
| **Free** | $0 | 5 GB | Unlimited | 5 | 1 GB/mo | Solo researcher, OSS, hobby. **The Dirt setup.** |
| **Pro** | $60/mo | 100 GB ($0.03/GB extra) | Unlimited | 10 | 1.5 GB/mo ($0.10/MB extra) | Early-stage team (<50 employees). |
| **Enterprise** | Custom | Custom | Unlimited | Custom | Custom | Regulated, SSO/HIPAA, dedicated support. |
| **Academic** | Free (license-gated) | 200 GB | Unlimited | 100 | 25 GB/mo | Universities; same feature set as Pro. |

(Source: https://wandb.ai/site/pricing — values current 2026-04-25.)

## What "5 GB free storage" means in practice

- One trained `.onnx` for the wake-word model is ~1–10 MB.
- One `.tflite` is similar.
- A validation report `.txt` is ~KB.
- The SDK's per-run metric history (a 90-min run logging every 100 steps) is ~10 MB on the server side.

So one full harness run consumes ~30 MB. **5 GB ≈ 150 runs of full retention.** Comfortably enough for a year of harness experimentation, *as long as* old artifact versions get pruned.

The trap: **artifact versions don't auto-prune**. If the harness logs a new `hey-claudia-model:vN` artifact every run and never cleans up old `vN-1` / `vN-2` / ..., storage grows unboundedly. See [artifacts.md](artifacts.md) for the cleanup pattern.

## Quotas worth knowing

| Quota | Free tier limit | What hits it |
|---|---|---|
| Storage | 5 GB | Artifact bytes + run history blob storage. |
| Tracked hours | Unlimited | (Was previously limited; now unlimited at every paid+free tier.) |
| Parallel runs | Unlimited | No limit on concurrent `wandb.init()`. |
| API rate limit | Unpublished | Documented as "fair use"; aggressive Public API polling (>1 req/s sustained) may earn 429. Stay >=10 s between polls. |
| Single artifact size | ~100 GB (from docs commentary; not contractual) | A single `Artifact` is uploaded as a manifest of files; per-file limit is ~10 GB. Wake-word artifacts are MB-scale, not relevant. |
| Run name length | 64 chars | `WANDB_NAME` / `name=` truncated. |
| `WANDB_RUN_ID` length | 64 chars | UUIDs fit. |

(Sources: https://wandb.ai/site/pricing, https://docs.wandb.ai/models/track/environment-variables/.)

## Things that look like quotas but aren't

- **Number of runs per project**: no limit. Create a million runs in one project; UI gets slow but nothing breaks.
- **Number of projects per user**: no limit on free tier (some Enterprise SKUs limit team projects, but not personal).
- **Number of teams**: free tier supports unlimited personal entities.

## When the harness might need Pro

| Trigger | Why |
|---|---|
| Multiple humans collaborating on the harness | Team entity (Pro+). On free tier, runs are scoped to one personal account. |
| `production`-aliased artifact reaches >5 GB cumulative | Upgrade or set up artifact-cleanup automation. |
| Need run-state webhooks (instead of polling) | Project Automations with webhook actions are Pro+. ([alerts-and-webhooks.md](alerts-and-webhooks.md)) |
| Need SSO / HIPAA / audit logs | Enterprise. Not relevant for the Dirt single-user grow. |

For the foreseeable wake-word workflow (one human, ~weekly retraining cadence, models <10 MB), **the free tier is sufficient indefinitely** as long as the artifact-cleanup script runs.

## Cost-of-being-wrong: leaked / committed `WANDB_API_KEY`

A leaked key gives the holder full access to your runs, projects, and storage. Rotation:

1. Open https://wandb.ai/authorize.
2. Click **Disable** next to the leaked key.
3. Generate a new one; update `.env` and redeploy / re-source.

W&B doesn't bill on API call volume, so the financial blast radius of a leak is bounded by storage (max 5 GB for free tier — a leaked key can't run up a bill).

(Source: https://docs.wandb.ai/quickstart for key rotation.)

## Sources

- https://wandb.ai/site/pricing
- https://docs.wandb.ai/quickstart
- https://docs.wandb.ai/models/track/environment-variables/
