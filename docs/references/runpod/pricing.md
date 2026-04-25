# Pricing

Source for everything here: https://docs.runpod.io/pods/pricing, https://docs.runpod.io/serverless/pricing, https://docs.runpod.io/storage/network-volumes.

## Billing model

- **Per-second** billing for compute and storage. No minimum charge per transaction.
- **No fees for data ingress or egress.** SCP'ing a 50 MB `.onnx` off costs nothing.
- Account must maintain credits — if balance drops below ~10 seconds of runtime cost, Pods stop. (Source: https://docs.runpod.io/pods/pricing.)
- Default account-wide spend cap: **$80/hour** across all resources. Hard cap; contact support to lift.

## Compute pricing tiers (Pods, on-demand, Secure Cloud)

The docs page does not enumerate every GPU's per-hour price (RunPod adjusts these and points users to the deploy UI for current rates). Approximate ballparks for sub-$2-per-run sizing:

| GPU | VRAM | Approx $/hr (on-demand, Secure) | 90 min cost |
|---|---|---|---|
| RTX 4090 | 24 GB | ~$0.34 | ~$0.51 |
| RTX A4000 | 16 GB | ~$0.17 | ~$0.26 |
| L4 | 24 GB | ~$0.43 | ~$0.65 |
| A40 | 48 GB | ~$0.39 | ~$0.59 |
| A100 80 GB | 80 GB | ~$1.69 | ~$2.54 |
| H100 80 GB | 80 GB | ~$2.69 | ~$4.04 |

(Numbers are illustrative — confirm in the deploy UI before depending on them. Source: tier ordering from https://docs.runpod.io/serverless/pricing's per-second table for Serverless, which mirrors Pods relative ordering. The Pods rates are typically lower than Serverless.)

For **wake-word training** (a small, fast convnet on a few hours of audio): RTX 4090 is overkill but cheap, RTX A4000 is sufficient and cheaper, L4 is fine. **Don't pay for A100/H100.**

## Storage pricing

| Type | Running | Stopped |
|---|---|---|
| Container disk | $0.10/GB-month | $0 (wiped on stop) |
| Volume disk | $0.10/GB-month | **$0.20/GB-month** |
| Network volume | $0.07/GB-month under 1 TB; $0.05/GB-month over | continuous |

The **`$0.20/GB-month while stopped`** rate on volume disk is the trap — a forgotten EXITED Pod with a 50 GB volume bills $10/month for nothing. Always `DELETE` after you've SCP'd off.

For a one-shot run with a 20 GB volume that lives ~90 min, storage cost is ~$0.005. Trivial. The compute cost dominates.

## Spot / interruptible

Setting `interruptible: true` on `POST /pods` enables spot pricing — typically 20–40% cheaper than on-demand. **5-second eviction warning.** No graceful checkpoint window.

For training without periodic checkpointing (which the wake-word trainer doesn't do), spot is a coin flip on whether your run completes; one eviction means starting over and paying twice. **Don't use spot for one-shot training jobs that don't checkpoint.**

## Savings plans

3- or 6-month prepaid commitments for steady-state usage. Discount of ~10–15% on GPU compute. Storage billed at standard rates regardless. **Irrelevant for one-shot training** — the entire point is bursty short-lived runs.

## Hard limits and safeguards

- Default account spend cap: **$80/hour** across all live resources. Contact support to raise.
- Pods stop automatically if balance falls under ~10 seconds of runtime cost.
- No documented timeout on a long-running Pod — it runs until you stop, terminate, or run out of credits.
- No documented per-API-call rate limit. Polling at 20 s is well within any reasonable bound.

## Putting it all together for one-shot wake-word training

| Line item | Estimate |
|---|---|
| RTX 4090 on-demand × 90 min | ~$0.51 |
| 50 GB container disk × 90 min | ~$0.0001 |
| 20 GB volume × 90 min | ~$0.0001 |
| Image pull (~5 min of GPU time wasted) | ~$0.03 |
| **Total** | **~$0.55** |

Comfortably under the $2/run target.

## Sources

- https://docs.runpod.io/pods/pricing
- https://docs.runpod.io/serverless/pricing
- https://docs.runpod.io/storage/network-volumes
- https://docs.runpod.io/pods/storage/types
