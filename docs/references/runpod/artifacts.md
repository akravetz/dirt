# Getting artifacts off a finished Pod

The Pod is `EXITED`. Your `.onnx` / `.tflite` / `validation-report.txt` are in `/workspace/out/` (volume disk, persists until Pod is `DELETE`d). You need them on your local machine.

Four options. Recommendation first, then the others.

## Recommended: SCP via Direct TCP port 22

This is the only option that:
- Has no third-party dependency.
- Works script-friendly without any extra service install on the Pod (assuming the image runs sshd — see [docker-image.md](docker-image.md)).
- Is fast.

### Setup (once)

1. Generate a key locally if you don't have one: `ssh-keygen -t ed25519 -C "runpod" -f ~/.ssh/runpod_ed25519`.
2. Upload the **public** key (`runpod_ed25519.pub`) at https://www.console.runpod.io/user/settings → SSH Public Keys.

### Per-Pod request shape

On `POST /v1/pods`, set:

```json
{
  "ports": ["22/tcp"],
  "supportPublicIp": true,
  "cloudType": "SECURE",
  ...
}
```

After the Pod transitions to `RUNNING`, the GET response includes:

```json
{
  "publicIp": "100.65.0.119",
  "portMappings": { "22": 10341 }
}
```

(`publicIp` may be empty for the first few seconds — re-poll.)

### Pull artifacts

```sh
scp -i ~/.ssh/runpod_ed25519 \
    -o StrictHostKeyChecking=accept-new \
    -P 10341 \
    "root@100.65.0.119:/workspace/out/*" \
    var/wake-word/models/2026-04-25/
```

In Python:

```python
subprocess.run(
    [
        "scp",
        "-i", str(Path.home() / ".ssh/runpod_ed25519"),
        "-o", "StrictHostKeyChecking=accept-new",
        "-P", str(port_mappings["22"]),
        "-r",
        f"root@{public_ip}:/workspace/out/.",
        str(local_dest),
    ],
    check=True,
)
```

Source for the syntax: https://docs.runpod.io/pods/configuration/use-ssh ("Full SSH via Public IP" — `ssh root@[POD_IP_ADDRESS] -p [SSH_PORT] -i [PATH_TO_SSH_KEY]`, "Supports SCP and SFTP for file transfers").

## NOT recommended: SSH proxy at `ssh.runpod.io`

There's a second SSH path (`ssh <pod_id>@ssh.runpod.io -i ...`) that proxies through RunPod's infrastructure and works without a public IP. **It does not support SCP or SFTP.** Source: https://docs.runpod.io/pods/configuration/use-ssh — "does not support commands like SCP (Secure Copy Protocol) or SFTP". Useful for an interactive `ssh` debug session; useless for orchestration.

## Alternative: `runpodctl send` / `runpodctl receive`

Peer-to-peer file transfer using a one-time pairing code. Works machine-to-machine including local-to-Pod and Pod-to-local.

Source: https://docs.runpod.io/runpodctl/reference/runpodctl-send.

```sh
# On the Pod (via the pre-installed runpodctl):
runpodctl send /workspace/out/wake-word.onnx
# prints: Code is: 1234-bunny-tomato

# Locally:
runpodctl receive 1234-bunny-tomato
```

Why we don't use this for orchestration:

- **The send command is interactive** — it prints a code that the receiver has to enter. Scripting this means parsing stdout from a remote `ssh exec` to capture the code, then handing it to a local subprocess. Awkward.
- It's one-file (or one-folder) at a time per code.
- Failures are silent / hard to retry deterministically.

It's a great escape hatch for ad-hoc transfers from a Pod you SSH'd into manually. Don't build the orchestrator on it.

## Alternative: Cloud Sync (S3 / GCS / Azure / B2 / Dropbox)

The console has a "Cloud Sync" button that can push `/workspace` to one of those providers. Source: https://docs.runpod.io/pods/configuration/export-data — "Cloud Sync uploads and downloads data between your Pod and external cloud storage providers."

Why we don't use this:

- Adds a third-party dependency (an S3 bucket we'd have to provision and pay for).
- The console UX is human-only; programmatic Cloud Sync isn't documented in the REST API surface.
- For one-shot training where the artifact is going straight to the local repo, the round-trip via S3 is pure overhead.

If your artifact is large enough that SCP becomes the bottleneck (multi-GB), or if you want artifacts to land in a managed bucket for sharing, this is reasonable.

## Alternative: Network volume

Attach an existing network volume on `POST /pods` (`networkVolumeId: "..."`), have your training script write to `/workspace`, and the data persists after Pod delete. Then attach the same volume to a new (cheap CPU) Pod to retrieve, or use the [S3-compatible API](https://docs.runpod.io/storage/network-volumes) to pull from the volume directly.

Source: https://docs.runpod.io/storage/network-volumes.

Why we don't use this for one-shot:

- Network volumes are billed continuously ($0.07/GB-month under 1 TB) regardless of whether anything is attached.
- They must attach at Pod create-time and **cannot be detached** without deleting the Pod — so the simple "delete pod, keep data" path doesn't exist.
- Secure Cloud only — restricts machine availability.
- More moving parts (one extra resource to provision, track, and clean up).

Use network volumes if you want a persistent dataset shared across many runs (training corpus, base model weights). Don't use them for one-shot artifact retrieval.

## Sources

- https://docs.runpod.io/pods/configuration/use-ssh
- https://docs.runpod.io/pods/configuration/expose-ports
- https://docs.runpod.io/runpodctl/reference/runpodctl-send
- https://docs.runpod.io/pods/configuration/export-data
- https://docs.runpod.io/storage/network-volumes
- https://docs.runpod.io/pods/storage/types
