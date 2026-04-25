# Private container registry

If your training image is in a private registry (private Docker Hub repo, GitHub Container Registry / GHCR, ECR, GCR), you must register credentials with RunPod once and reference them by ID on every `POST /pods`.

If your image is in a **public** Docker Hub repo (e.g. `runpod/pytorch:...`), skip this entirely — `imageName` alone is enough.

## Endpoint

`POST https://rest.runpod.io/v1/containerregistryauth`

Body:

```json
{
  "name": "ghcr-akravetz",
  "username": "akravetz",
  "password": "<personal-access-token>"
}
```

Returns `201` with `{"id": "<registry-auth-id>", ...}`. Save that ID.

Source: https://docs.runpod.io/api-reference/container-registry-auths/POST/containerregistryauth.

Then on `POST /pods`:

```json
{
  "imageName": "ghcr.io/akravetz/dirt-wake-word-trainer:latest",
  "containerRegistryAuthId": "<registry-auth-id>",
  ...
}
```

## Endpoint family

| Method | Path | Use |
|---|---|---|
| `POST` | `/v1/containerregistryauth` | Create. |
| `GET` | `/v1/containerregistryauth` | List. |
| `GET` | `/v1/containerregistryauth/{id}` | Read one. |
| `DELETE` | `/v1/containerregistryauth/{id}` | Delete. |

(There is no `PATCH` — to rotate a token, create a new auth, point future Pods at it, then delete the old.)

## Per-registry notes

### GitHub Container Registry (ghcr.io)

- **Username**: your GitHub username **in all lowercase**. (Source: https://www.answeroverflow.com/m/1331739796263014400 — community thread, but the lowercase requirement is documented behavior of GHCR's auth, not a RunPod quirk.)
- **Password**: a Personal Access Token (Classic) with `read:packages`. The fine-grained tokens are unreliable for `docker pull` from third-party services. Use **Tokens (classic)**.
- The image must be **published as Public visibility** OR the token's user must have access to the private package.
- **Whitespace bites** — community reports of pulls failing because the token was pasted with a trailing newline. Strip it.

### Docker Hub private repos

- **Username**: your Docker Hub username.
- **Password**: a personal access token from Docker Hub (Account Settings → Security → Access Tokens), with at least Read scope. Don't use your account password.

### ECR / GCR / ACR

Supported but the auth model is uglier (ECR uses time-limited tokens from `aws ecr get-login-password`; GCR uses service-account JSON). For our use case, GHCR is the path of least resistance — we already have a GitHub account.

## Once-only setup vs each-run

The `containerRegistryAuthId` is durable. Create it once, store the ID alongside the API key (e.g. in `.env` as `RUNPOD_GHCR_AUTH_ID`), reuse it on every `POST /pods`. Rotate when the underlying GitHub PAT rotates.

## Sources

- https://docs.runpod.io/api-reference/container-registry-auths/POST/containerregistryauth
- https://docs.runpod.io/api-reference/openapi.json
- https://docs.runpod.io/api-reference/pods/POST/pods (for `containerRegistryAuthId` field on pod create)
