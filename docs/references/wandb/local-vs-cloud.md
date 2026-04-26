# Local (self-hosted) vs. cloud W&B

W&B has three deployment models:

| Model | Where | Who manages | Who you are |
|---|---|---|---|
| **Multi-tenant cloud** | `https://wandb.ai` | W&B | Default. The Dirt setup. |
| **Dedicated cloud** | W&B-hosted, single-tenant VPC | W&B (infra) + you (config) | Enterprise, regulated, want VPC isolation but not ops. |
| **Self-managed (W&B Server)** | Your infra (k8s / AWS / GCP / Azure / on-prem) | You (everything) | On-prem mandate, air-gapped, regulatory ownership. |

(Source: https://docs.wandb.ai/models/hosting/.)

## When self-hosting makes sense

Per the docs, W&B explicitly recommends self-managed only when:

1. **Existing infra is on-prem.** You already run a Kubernetes cluster, you have ops on-call, the marginal cost of one more service is small.
2. **Regulatory needs that Dedicated Cloud can't satisfy.** HIPAA, FedRAMP-High, classified-network constraints, etc.

Outside those cases, self-hosting trades `$0/mo (free tier) or $60/mo (Pro)` for full responsibility for:

- Database (Postgres + Redis + object store)
- Backups, restore drills, schema upgrades
- TLS certificate rotation
- W&B Server release upgrades (monthly, sometimes painful)
- Authentication integration (LDAP / SSO)
- Storage capacity planning

## When cloud is the right answer (almost everyone)

The docs note: cloud "is recommended for users with no strict regulatory needs." For a solo researcher running a personal grow-monitoring + wake-word retraining pipeline:

- **Setup cost**: zero. Sign up at https://wandb.ai/, paste API key, done.
- **Ongoing ops**: zero. W&B handles the database, the upgrades, the certs.
- **Cost**: zero (free tier sufficient for the harness's footprint — see [pricing-and-quotas.md](pricing-and-quotas.md)).
- **Time to first value**: 10 minutes from "I read this doc" to "first run logged".

For Dirt: **always cloud.**

## What `WANDB_BASE_URL` does

If you ever do self-host, the SDK's only knob is the env var:

```bash
export WANDB_BASE_URL=https://wandb.internal.example.com
```

Everything else (`init`, `log`, `Api`) works unchanged. The CLI auth becomes:

```sh
wandb login --host=https://wandb.internal.example.com
```

(Source: https://docs.wandb.ai/models/track/environment-variables/.)

For Dirt, leave this unset (defaults to `https://api.wandb.ai`).

## Dedicated Cloud as the middle ground

Not free, not self-hosted: W&B runs a single-tenant instance for you in a VPC of your choice. You get:

- Cloud SaaS UX (W&B handles upgrades, backups, TLS).
- Your data lives in your AWS / GCP / Azure account (not multi-tenanted with other W&B customers).
- BYO encryption keys.

Pricing is custom (Enterprise contract). Not relevant for Dirt.

## Decision matrix for Dirt

| Question | Answer for Dirt |
|---|---|
| Are we in a regulated industry? | No. |
| Do we have on-prem infra mandate? | No. |
| Do we have ops staff? | No (one person). |
| Is our data sensitive? | Sensor readings + wake-word audio clips of the user's voice. Mildly sensitive but not regulated. |
| Decision: | **Multi-tenant cloud, free tier.** |

## Sources

- https://docs.wandb.ai/models/hosting/
- https://docs.wandb.ai/models/track/environment-variables/
- https://wandb.ai/site/pricing
