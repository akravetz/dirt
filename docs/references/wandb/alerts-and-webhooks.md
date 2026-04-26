# Alerts and webhooks

Two different mechanisms with different scopes:

- **`run.alert(...)`** — fires from inside a training script. Scoped to the user's account. Free tier.
- **Project-level Automations** — UI-configured triggers on run-state transitions or metric thresholds. Pro/Enterprise tier, multi-tenant cloud only.

For the wake-word harness, `run.alert()` is the right surface (free, programmatic, no UI dance).

## `run.alert(title, text, level, wait_duration)`

```python
run.alert(
    title="Trainer crashed",
    text="OOM after step 12,400 of 50,000.\n\n```\n<traceback>\n```",
    level="ERROR",          # "INFO" | "WARN" | "ERROR" — accepts string or wandb.AlertLevel enum
    wait_duration=300,      # seconds; suppress duplicate alerts within this window
)
```

(Source: https://docs.wandb.ai/models/runs/alert/.)

### Parameters

| Param | What it does |
|---|---|
| `title` | Headline of the alert (also the email subject / Slack message header). |
| `text` | Body. Markdown allowed. Slack mentions: `<@USER_ID>` to ping a person. |
| `level` | `"INFO"` / `"WARN"` / `"ERROR"`. Affects styling and (in some Slack configs) channel routing. |
| `wait_duration` | Seconds to suppress duplicate alerts with the same `title`. Default is short (~minute). Set to e.g. 3600 to dedupe within an hour. |

### Where alerts go

- **Email**: to the W&B account email. Always available once enabled in User Settings.
- **Slack**: if the user has connected Slack in `User Settings → Notifications`. Direct message to them via the W&B Slackbot.

The user must opt in: open `https://wandb.ai/settings → Alerts` and enable email + Slack at least once. The SDK call is a no-op if neither channel is enabled. (Source: https://docs.wandb.ai/models/runs/alert/.)

### When to fire alerts in the harness

| Event | Level | Why |
|---|---|---|
| Trainer raised an unhandled exception | `ERROR` | The orchestrator already sees the failed state, but the human sees the alert immediately. |
| Trainer finished but `val/f1 < 0.80` (regression) | `WARN` | Run completed; quality gate failed. |
| New artifact promoted to `production` | `INFO` | "We just shipped a new model" record. |
| Validation report contains a per-threshold row with `recall < 0.5` | `WARN` | One more sanity check beyond F1. |

### Throttling

Don't fire alerts inside the training loop without `wait_duration` — a hung loss-explosion check could fire 1000s of alerts. Pair every alert with a sane `wait_duration` (60–3600 s) and a guard to fire at most once per run:

```python
_alerted_oom = False

def on_oom():
    global _alerted_oom
    if _alerted_oom:
        return
    run.alert(title="OOM", text="...", level="ERROR", wait_duration=3600)
    _alerted_oom = True
```

## Project-level Automations (Pro+ only)

Configured in the UI at `Project Settings → Automations`. Triggers and actions:

| Trigger | Notes |
|---|---|
| Run completes (any state) | Fires on `finished` / `failed` / `crashed` / `killed`. |
| Run metric crosses absolute threshold | E.g. `val/f1 < 0.85`. |
| Run metric z-score deviates from historical mean | E.g. "loss this run is 3σ above the project's last 50 runs". |
| New artifact version created | E.g. "a new `hey-claudia-model` was logged". |
| Artifact alias changed | E.g. "the `production` alias was reassigned". |

Actions:

- **Slack notification** to a team channel.
- **Webhook POST** to an arbitrary URL with a JSON payload describing the event.

(Source: https://docs.wandb.ai/models/automations/.)

### Why the harness probably doesn't use Automations

- **Multi-tenant cloud only** — works on `wandb.ai`, not on a self-hosted Server. (Source: same docs page.)
- **Pro/Enterprise tier** — not in the free tier.
- **UI-configured, not committed-to-git** — fragile compared to the equivalent `run.alert()` calls inside the trainer code.
- **Webhook receiver overhead** — needs a public URL the harness orchestrator listens on. Polling `Api().run().state` is simpler.

If the harness eventually goes multi-user / multi-team, the Automation → webhook → orchestrator-side receiver is a worthwhile upgrade. Until then, in-run `alert()` + external state polling covers the same ground.

## Sources

- https://docs.wandb.ai/models/runs/alert/
- https://docs.wandb.ai/models/automations/
