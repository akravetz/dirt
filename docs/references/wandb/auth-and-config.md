# Auth and config

W&B uses a single bearer token (the API key) for the SDK, the public API, and the CLI. There is no per-project key.

## What the user does once

1. Open https://wandb.ai/authorize (or `User Settings → API Keys` from any W&B page).
2. Copy the key. (Source: https://docs.wandb.ai/quickstart — "Find your API key at https://wandb.ai/authorize.")
3. Paste into the project's `.env` as `WANDB_API_KEY=...`. The `.env.example` already has the slot.

The user never has to do this again unless they rotate.

## How the SDK consumes it (headless / Docker / RunPod)

The single rule: **set `WANDB_API_KEY` before the first `import wandb` call (or at least before `wandb.init()`)**. The SDK auto-detects it; no `wandb.login()` call is needed.

```python
import os
os.environ["WANDB_API_KEY"] = "..."   # already set by the systemd unit / Docker env in our case
import wandb
run = wandb.init(project="dirt-wake-word")
```

In a Dockerfile / `entrypoint.py`:

```dockerfile
# Do NOT bake the key into the image. Inject at runtime.
ENV WANDB_PROJECT=dirt-wake-word \
    WANDB_DIR=/workspace/wandb \
    WANDB_SILENT=true
```

Then on `POST /pods`:

```json
{
  "env": {
    "WANDB_API_KEY": "<from local .env at orchestration time>",
    "WANDB_RUN_GROUP": "auto-research-2026-04-25"
  }
}
```

(Source for the env-var auth path: https://docs.wandb.ai/models/track/environment-variables/ — "WANDB_API_KEY: Sets the authentication key associated with your account.")

**Never** call `wandb.login()` interactively in a non-tty context — it blocks on stdin. If you must call it for some reason, pass the key explicitly: `wandb.login(key=os.environ["WANDB_API_KEY"])`.

## How the public API consumes it

Same env var, no separate auth step:

```python
api = wandb.Api()              # picks up WANDB_API_KEY from env
run = api.run("entity/dirt-wake-word/abc123")
print(run.state)
```

You can also pass `api_key=` explicitly to `wandb.Api(api_key=...)` (Source: https://docs.wandb.ai/models/ref/python/public-api/api/).

The Public API reads the API key from `~/.netrc` if env is unset — set by `wandb login` on a developer workstation. For headless orchestration, env is the canonical channel.

## Env-var precedence over `wandb.init()` kwargs

This is a frequent footgun. **Env vars override `wandb.init()` kwargs**, not the other way around.

| Env var | Overrides `wandb.init(...)` arg | Notes |
|---|---|---|
| `WANDB_API_KEY` | (no equivalent) | Required for cloud mode. |
| `WANDB_PROJECT` | `project=` | "Can be set via wandb init, but the environment variable overrides that value" — docs explicit. |
| `WANDB_ENTITY` | `entity=` | Username or team name. |
| `WANDB_NAME` | `name=` | Display name. |
| `WANDB_NOTES` | `notes=` | Markdown allowed. |
| `WANDB_TAGS` | `tags=` | Comma-separated. |
| `WANDB_RUN_ID` | `id=` | Globally unique within the project, max 64 chars; needed for resume. |
| `WANDB_RUN_GROUP` | `group=` | Use to bundle the auto-research harness's N runs under one group. |
| `WANDB_DIR` | `dir=` | Where the SDK stages local logs before upload. |
| `WANDB_MODE` | `mode=` | `online` (default) / `offline` / `disabled` / `shared`. |
| `WANDB_RESUME` | `resume=` | `never` (default) / `auto` / `must` / `allow`. |
| `WANDB_SILENT` | (Settings.quiet) | Silences SDK stdout. Set in containers. |
| `WANDB_BASE_URL` | (Settings) | Override for self-hosted (`http://YOUR_IP:YOUR_PORT`). |

(Source for the full list: https://docs.wandb.ai/models/track/environment-variables/.)

For the auto-research harness, the recommended split:

- **Set in the trainer Dockerfile** (baked, image-layer): `WANDB_PROJECT`, `WANDB_DIR`, `WANDB_SILENT` — these are the same for every run.
- **Set per-pod via RunPod `env` block** (per-invocation): `WANDB_API_KEY`, `WANDB_RUN_GROUP`, optionally `WANDB_NAME` — these vary per orchestrator invocation.
- **Set in `wandb.init()` kwargs**: `job_type=`, `config=`, `tags=` — these are dynamic from the trainer's perspective and don't make sense as env.

## Free vs. Pro vs. Enterprise — what changes for auth

The auth mechanism is identical across tiers. Pro/Enterprise add team-scoped auth (the entity is a team slug instead of a personal username) and Service Accounts (separate keys for automation that don't tie to a human account) — see [pricing-and-quotas.md](pricing-and-quotas.md). For the solo-researcher Dirt setup the personal account is fine.

## Sources

- https://docs.wandb.ai/quickstart
- https://docs.wandb.ai/models/track/environment-variables/
- https://docs.wandb.ai/models/ref/python/public-api/api/
- https://wandb.ai/authorize
