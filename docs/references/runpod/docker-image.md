# Docker image for the trainer

Constraints RunPod actually imposes are minimal — the platform pulls and runs your image like any other container host. The constraints worth knowing:

## Hard requirements

- **`linux/amd64` architecture.** RunPod's hosts are x86_64. Don't ship `linux/arm64`. (Source: https://docs.runpod.io/tutorials/introduction/containers/create-dockerfiles — "Runpod's infrastructure uses `linux/amd64` architecture".)
- **CUDA in the image** if you're training on GPU. The host provides the NVIDIA driver via the runtime; your image needs the matching CUDA runtime libs. The cleanest path: base off `nvidia/cuda:<ver>-cudnn-runtime-ubuntu22.04` or `runpod/pytorch:<ver>` (which RunPod maintains).
- **The container must keep running while you want it to keep running.** If your `CMD` exits, the Pod transitions to `EXITED` and billing-for-compute stops (storage continues). For one-shot training that's exactly what you want — `dockerStartCmd: ["python", "train.py"]`, exit 0 on success, the Pod hits `EXITED`, you SCP off, you `DELETE`.

## Soft requirements (set if you want SCP-off-the-pod to work)

If you go with **Direct TCP** SSH (the only path that supports SCP), the image must run an SSH daemon. Two options:

### Option A: base on a RunPod image that already starts sshd

`runpod/pytorch:<ver>`, `runpod/base:<ver>`, and the official Ubuntu/PyTorch templates start sshd as part of their default startup and read `~/.ssh/authorized_keys` from a key you upload to your account. **This is the lowest-friction path.** If you base on one of these, port 22 is already wired up.

### Option B: roll your own from a clean CUDA base

Add to your Dockerfile:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends openssh-server \
 && mkdir -p /run/sshd /root/.ssh \
 && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config

# Entrypoint that injects the public key from a RunPod env var, starts sshd, then runs the trainer.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

`entrypoint.sh`:

```sh
#!/usr/bin/env bash
set -euo pipefail

# RunPod injects the user's first SSH public key into PUBLIC_KEY when supportPublicIp + 22/tcp is set
# (this is also documented as available in /etc/runpod/authorized_keys on official templates).
if [ -n "${PUBLIC_KEY:-}" ]; then
  echo "$PUBLIC_KEY" >> /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
fi

# Start sshd in the background.
/usr/sbin/sshd

# Run the actual training job. When this returns, the container exits and the Pod -> EXITED.
exec "$@"
```

Then on `POST /pods` set `dockerStartCmd: ["python", "/app/train.py"]` — entrypoint launches sshd, then execs the cmd. (The `PUBLIC_KEY` env var is the convention the official RunPod templates use; alternatively, pass your public key in via `env: {"PUBLIC_KEY": "ssh-ed25519 ..."}` on `POST /pods`.)

Source on the SSH setup pattern: https://docs.runpod.io/pods/configuration/use-ssh ("For instances using custom Docker templates rather than official images, administrators must ensure TCP port 22 is exposed and include specific startup commands to install and configure the SSH daemon with proper authorization.")

## What the image should write

- Outputs go to **`/workspace/out/`** (the volume mount, which survives Pod stop and is visible over SSH).
- Write a sentinel file (`/workspace/out/SUCCESS` or `/workspace/out/FAILURE` with a stack trace) so the orchestrator can distinguish success from a no-op exit.
- Don't write outputs to `/tmp` or anywhere on the container disk — those are wiped on stop.

## Image size

No documented hard limit on image size, but pull time directly maps to GPU billing time (you start paying when the container starts, which is after the pull). A 2 GB image on a 100 Mbps host pull is ~3 min of training-tier GPU time at $0.34/hr → ~$0.02 wasted. A 20 GB image is ~30 min wasted, ~$0.17. For a $2/run budget, keep the image lean — slim Python base, only the packages your training script actually imports, no model weights baked in (download them at runtime to `/workspace`).

## Recommended base images

| Base | When |
|---|---|
| `runpod/pytorch:<ver>` (e.g. `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`) | Default. Has sshd, has CUDA, has PyTorch. ~7–10 GB. |
| `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04` + your own Python install | If you want a smaller image and don't need the full PyTorch bundle. ~3 GB before deps. Need Option B for sshd. |
| `python:3.11-slim` | **Don't.** No CUDA, no NVIDIA libs. Will fail on `import torch` against a GPU. |

## Sources

- https://docs.runpod.io/tutorials/introduction/containers/create-dockerfiles
- https://docs.runpod.io/pods/configuration/use-ssh
- https://docs.runpod.io/pods/configuration/expose-ports
- https://docs.runpod.io/pods/templates/create-custom-template
