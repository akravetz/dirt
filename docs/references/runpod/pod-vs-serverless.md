# Pods vs Serverless for one-shot training

**TL;DR:** Use **Pods**. Serverless is queue-and-handler shaped; it fights every assumption a "run a script and exit" training job makes.

## What each surface actually is

### Pods

A Pod is a leased GPU container. You hand RunPod a Docker image and a start command, RunPod picks a host with the GPU you asked for, runs your image, billing starts when the container starts, billing ends when the Pod is `EXITED` or `TERMINATED`. Pods are persistent (they keep running until you stop or delete them) and have a filesystem you can SSH into.

Source: https://docs.runpod.io/pods/overview, https://docs.runpod.io/pods/manage-pods

### Serverless

A Serverless **endpoint** is a long-lived API surface backed by autoscaling **workers**. You author a Python `handler(event)` function in a Docker image that imports `runpod` and calls `runpod.serverless.start({"handler": handler})`. RunPod scales the worker pool (min/max count, optional always-on "active workers") and routes incoming **jobs** to workers. Clients submit jobs via `POST /run` (async, returns a job ID — poll `/status/{id}`) or `/runsync` (sync, returns the result, max ~5 min). Worker billing starts when a worker boots, ends after a configurable idle timeout (default 5 s).

Source: https://docs.runpod.io/serverless/overview, https://docs.runpod.io/serverless/sdks, https://docs.runpod.io/serverless/endpoints/job-states, https://docs.runpod.io/serverless/endpoints/send-requests

## Why Pods wins for our case

For a 30–90 min training run that produces files on disk:

| Concern | Pods | Serverless |
|---|---|---|
| Code shape | `python train.py`, exit. | Author a `handler(event)`, package as a worker, deploy as an endpoint, submit a job. |
| Lifecycle steps | `POST /pods` → poll → `DELETE /pods`. | `POST /containerregistryauth` (probably) → `POST /endpoints` → `POST /run` → poll `/status` → `DELETE /endpoints`. |
| Cold start | One image pull at Pod boot. | One image pull per worker scale-up. |
| Output channel | Files on the volume disk; SCP off. | Only the JSON your `handler` returns. Files written to disk vanish with the worker. |
| Per-second cost (RTX 4090) | ~$0.34/hr ≈ $0.000094/s on-demand. | ~$0.00031/s flex (~3x more). (Source: https://docs.runpod.io/serverless/pricing — A4000 is $0.00016/s flex; 4090-tier is higher.) |
| Max execution per "thing" | None — Pod runs until `EXITED`. | Per-job timeout, default short, max bounded by endpoint config. |

Concretely:

- Serverless **handlers return JSON, not files**. To exfil a 5–20 MB `.onnx` you'd have to base64-encode it into the response, or upload to S3 from inside the handler. Neither is free; the JSON-encoding path adds memory pressure for no reason. Pods give you a real filesystem you SCP off.
- Serverless workers can sit idle (and bill) for up to the idle-timeout window after each job. Pods bill exactly the wall time of the run.
- Serverless costs more per second (~3x) for the same GPU because you're paying the autoscaling tax.
- Serverless has **per-job timeouts** that are not designed for 30–90 min runs. Job states include `TIMED_OUT` and the docs explicitly note this fires when "the worker failed to report back before reaching the timeout threshold" — long-running training without periodic progress callbacks is an anti-pattern. (Source: https://docs.runpod.io/serverless/endpoints/job-states.)

## When Serverless would actually be right

- The "job" is a sub-minute inference (image generation, LLM completion, embedding).
- You want autoscaling — you don't know when requests will come.
- The output fits naturally in JSON (numbers, short strings, a base64 image).
- You want a stable URL you can call from a client app for months.

None of these describe wake-word retraining. Pods.

## What about RunPod **Flash**?

Flash (beta as of 2026-04) lets you `@flash.function` decorate a Python function and have it run on a remote GPU from your terminal — closer to Modal-style ephemerality. It's interesting for `python -c "do_one_thing()"` workflows but is beta, has its own pricing model and GPU type list, and doesn't materially change the pull-artifacts-back problem (you still need a path off-box for the `.onnx`). For now: stick with Pods. (Source: https://docs.runpod.io/flash/pricing exists but Flash is explicitly tagged "Beta" on the docs landing page.)

## Sources

- https://docs.runpod.io/pods/overview
- https://docs.runpod.io/pods/manage-pods
- https://docs.runpod.io/pods/pricing
- https://docs.runpod.io/serverless/overview
- https://docs.runpod.io/serverless/pricing
- https://docs.runpod.io/serverless/endpoints/job-states
- https://docs.runpod.io/serverless/sdks
