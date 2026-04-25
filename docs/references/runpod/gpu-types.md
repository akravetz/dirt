# GPU types

When `POST /v1/pods` takes a `gpuTypeIds` array, the strings are the **display names** as RunPod surfaces them. Pass an array — multi-entry arrays are tried in priority order (with `gpuTypePriority`).

Source: https://docs.runpod.io/references/gpu-types and the OpenAPI schema at https://docs.runpod.io/api-reference/openapi.json.

## Strings the REST API accepts

This is the subset we care about for sub-$2/run training. Full list at https://docs.runpod.io/references/gpu-types.

| API ID string | VRAM | Tier | Notes |
|---|---|---|---|
| `"NVIDIA GeForce RTX 4090"` | 24 GB | ADA_24 | Recommended default. Cheapest 24GB option, plenty for wake-word training. |
| `"NVIDIA L4"` | 24 GB | AMPERE_24 | Slightly more expensive than 4090 on Pods. Good fallback. |
| `"NVIDIA RTX A4000"` | 16 GB | AMPERE_16 | Cheapest tier worth using. Adequate for small models. |
| `"NVIDIA RTX A5000"` | 24 GB | ADA_24 | In the same pool as 4090/L4. |
| `"NVIDIA A40"` | 48 GB | AMPERE_48 | Use only if you need >24GB VRAM. |
| `"NVIDIA RTX A6000"` | 48 GB | AMPERE_48 | Same. |
| `"NVIDIA A100 80GB PCIe"` | 80 GB | — | Only if you really need it. ~5x the 4090 price. |
| `"NVIDIA H100 80GB HBM3"` | 80 GB | — | Same. |

**T4 is not in RunPod's current offerings.** If you see training data suggesting `"NVIDIA Tesla T4"`, that's a different cloud (AWS/GCP). Use the 4090 or A4000 instead.

## How to discover the current canonical strings

The doc page is the source of truth, but you can also enumerate live availability via:

```sh
runpodctl gpu list
```

(Source: https://docs.runpod.io/runpodctl/overview — `gpu` command group, "List available GPUs".) This gives you the exact strings the platform currently accepts, which is more reliable than the docs if they ever drift.

## Multi-entry arrays for capacity fallback

```json
{
  "gpuTypeIds": ["NVIDIA GeForce RTX 4090", "NVIDIA L4", "NVIDIA RTX A4000"],
  "gpuTypePriority": "availability"
}
```

`"availability"` lets RunPod pick whichever has spare capacity (cheapest first per their internal ordering). `"custom"` enforces strict order. **Use `"availability"`** unless you have a specific cost-vs-time preference.

## Cloud type interaction

- `cloudType: "SECURE"` — RunPod-operated DCs. More reliable, slightly more expensive, public IP available.
- `cloudType: "COMMUNITY"` — host-provided machines. Cheaper, more variable, public IP requires `supportPublicIp: true` (and may not always be granted).

For training where you need SCP-off-the-Pod, **`SECURE` is the safe default.** Drop to `COMMUNITY` only if you've decided to use Cloud Sync or network volumes for artifact retrieval (see [artifacts.md](artifacts.md)).

## Sources

- https://docs.runpod.io/references/gpu-types
- https://docs.runpod.io/api-reference/openapi.json
- https://docs.runpod.io/runpodctl/overview
