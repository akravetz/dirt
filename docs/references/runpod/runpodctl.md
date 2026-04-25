# `runpodctl`

The official RunPod CLI. Useful for **interactive debugging** and a couple of orchestration affordances; not the right tool for the polling loop in our trainer (REST is cleaner there).

Source: https://docs.runpod.io/runpodctl/overview, https://docs.runpod.io/runpodctl/reference/runpodctl-pod, https://docs.runpod.io/runpodctl/reference/runpodctl-send.

## Install

```sh
bash <(wget -qO- cli.runpod.io)
# or:
curl -sSL cli.runpod.io | bash
```

Installs to `/usr/local/bin/runpodctl` (root) or `~/.local/bin/runpodctl` (non-root). Also available via Homebrew on macOS, conda/mamba/pixi.

## Auth

```sh
runpodctl config --apiKey $RUNPOD_API_KEY
# or, guided first-time setup (key + SSH key upload):
runpodctl doctor
```

Stored in `~/.runpod/config.toml`. Same key as the REST API.

## Command groups

| Group | Aliases | Use |
|---|---|---|
| `pod` | — | Pod CRUD. |
| `serverless` | `sls` | Serverless endpoints. |
| `template` | `tpl` | Templates. |
| `network-volume` | `nv` | Network volumes. |
| `gpu` | — | List GPU types currently offered. |
| `user` | `me` | Account info, balance check. |
| `hub` | — | Browse/deploy from RunPod Hub (community templates). |
| (other) | — | Registry, datacenter, billing, SSH key sync. |

## Pod creation via CLI (alternative to REST)

```sh
runpodctl pod create \
  --name wakeword-train \
  --image ghcr.io/akravetz/dirt-wake-word-trainer:latest \
  --gpu-id "NVIDIA GeForce RTX 4090" \
  --gpu-count 1 \
  --container-disk-in-gb 50 \
  --volume-in-gb 20 \
  --ports "22/tcp" \
  --env '{"WAKE_WORD":"hey-claudia"}'
```

Flag list (from https://docs.runpod.io/runpodctl/reference/runpodctl-pod):

- `--image` — Docker image
- `--gpu-id` — GPU display name string (run `runpodctl gpu list` to see options)
- `--gpu-count` — default 1
- `--compute-type cpu` — for CPU pods
- `--env '{"K":"V"}'` — JSON-encoded env var map
- `--ports "8888/http,22/tcp"` — comma-separated `port/protocol`
- `--volume-in-gb` — persistent volume size
- `--network-volume-id` — attach existing network volume
- `--template-id` — use a template instead of explicit fields

Returns a pod ID. Use `runpodctl pod get <id>` for status, `runpodctl pod delete <id>` to clean up.

## Why we still use REST for orchestration

`runpodctl pod create` works fine, but:

1. The flag surface doesn't expose every REST field (e.g. `containerRegistryAuthId`, `dockerStartCmd` have to go through `--env` hacks or template indirection).
2. Output is human-formatted text; parsing it from a Python orchestrator is fragile.
3. We already have an HTTP client; introducing a CLI-shell dependency on the orchestrator path is a regression.

REST gives us deterministic JSON in/out and full field coverage. Use the CLI for:

- Initial smoke testing (deploy a pod by hand, confirm it boots, SSH in, validate the image).
- `runpodctl gpu list` — discover currently-offered GPU type strings.
- `runpodctl me` — confirm the API key works and see the credit balance.
- Cleanup when the orchestrator crashes mid-flight (`runpodctl pod list` then `runpodctl pod delete`).

## `runpodctl send` / `receive` — peer-to-peer file transfer

Different from the rest of the CLI: a one-time pairing-code-based file transfer using a relay service. Works for local↔Pod and Pod↔Pod.

```sh
# On the Pod:
runpodctl send /workspace/out/wake-word.onnx
# prints: "Code is: 1234-bunny-tomato"

# Locally:
runpodctl receive 1234-bunny-tomato
```

Useful as a fallback when SCP is blocked or the SSH key path is broken. Awkward to script (the sender prints the code on stdout; the receiver needs that string). For orchestrated artifact retrieval, prefer SCP — see [artifacts.md](artifacts.md).

## Sources

- https://docs.runpod.io/runpodctl/overview
- https://docs.runpod.io/runpodctl/reference/runpodctl-pod
- https://docs.runpod.io/runpodctl/reference/runpodctl-send
