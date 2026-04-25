# Auth

RunPod uses a single bearer token for all API surfaces (REST, GraphQL, `runpodctl`, the `runpod` Python package).

## What the user has to do (one-time, manual)

1. Open https://www.console.runpod.io/user/settings.
2. Expand "API Keys" → "Create API Key".
3. Pick a name (e.g. `dirt-wake-word-trainer`) and a scope. Recommended: **Restricted** with explicit pod CRUD permissions, falling back to **All** if the restricted UI doesn't expose the granular pod scopes you need. (Source: https://docs.runpod.io/get-started/api-keys — the "Restricted" scope is the post-2024-11-11 fine-grained model; legacy keys auto-mapped to "All".)
4. Copy the key immediately. **RunPod does not store it server-side** — if you close the dialog without copying, you have to make a new one. (Same source.)
5. Paste it into the project's `.env` as `RUNPOD_API_KEY=...`.

The user never has to do this again unless they rotate the key.

## How the API consumes it

```
Authorization: Bearer $RUNPOD_API_KEY
Content-Type: application/json
```

Same header shape for every endpoint under `https://rest.runpod.io/v1/`. (Source: https://docs.runpod.io/api-reference/overview — "All requests require a Runpod API key in the request headers.")

## How `runpodctl` consumes it

```sh
runpodctl config --apiKey $RUNPOD_API_KEY
```

Writes to `~/.runpod/config.toml`. There is no `--api-key` flag on individual subcommands; the key is taken from the config file. The `runpodctl doctor` command runs guided first-time setup (key + SSH key) if you'd rather. (Source: https://docs.runpod.io/runpodctl/overview.)

## How the `runpod` Python package consumes it

```python
import os
import runpod

runpod.api_key = os.environ["RUNPOD_API_KEY"]
```

Module-level mutable; not a constructor. (Source: https://docs.runpod.io/serverless/sdks.)

## Scopes — what to know

| Scope | What it grants | When to use |
|---|---|---|
| `All` | Full pod / serverless / volume / template / billing / registry CRUD. | Single-purpose key for an automation account. Easiest. |
| `Restricted` | Per-resource granularity (Read Only / Read+Write / None per Serverless endpoint). | If you want a key that can submit to one specific endpoint and nothing else. |
| `Read Only` | Read-only across the account. | Dashboards, status checks. **Will not let you create a Pod.** |

For the wake-word trainer the orchestrator must create + delete Pods, so it needs at least `All` (or a Restricted key with full pod CRUD if the UI exposes that — the docs only explicitly call out per-Serverless-endpoint granularity). (Source: https://docs.runpod.io/get-started/api-keys.)

## Expiration

No expiration. Keys live until manually disabled or deleted in the console. (Source: same; absence is explicit — the docs list "Disable" and "Delete" as the only ways a key stops working.)

## Sources

- https://docs.runpod.io/get-started/api-keys
- https://docs.runpod.io/api-reference/overview
- https://docs.runpod.io/runpodctl/overview
- https://docs.runpod.io/serverless/sdks
