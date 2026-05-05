# Hosted Control Plane Operations

Read this before deploying, rolling back, or operating the Railway-hosted Dirt control plane.

The hosted control plane has two Railway services in project `dirt-control-plane`: `control-plane-api` for FastAPI and `web-ui` for the hosted React app. Railway `Postgres` stores cloud state, and the private `dirt-assets` bucket stores synced photos behind signed URLs. The local `dirt-gateway` service is outbound-only; it reads local state, syncs to cloud, polls PTZ-only command intent, and reports results.

## Deploy

Use only the supported script:

    scripts/deploy-control-plane

The script loads ignored `.env` first and `.env.prod` second, syncs the required Railway service variables without printing values, applies `atlas migrate apply --env cloud`, upserts the V1 gateway credential row from `DIRT_CLOUD_GATEWAY_ID`, `DIRT_CLOUD_GATEWAY_TOKEN_SHA256`, and `DIRT_CLOUD_SITE_ID`, deploys `apps/control-plane/` to `control-plane-api`, deploys `web-ui/` to `web-ui`, then waits for smoke checks at `DIRT_CLOUD_API_BASE_URL/api/health` and `DIRT_CLOUD_UI_BASE_URL/`. It requires `RAILWAY_PROJECT_ID`, `RAILWAY_ENVIRONMENT`, `RAILWAY_CONTROL_PLANE_API_SERVICE_ID`, `RAILWAY_WEB_UI_SERVICE_ID`, `RAILWAY_POSTGRES_SERVICE_ID`, `DIRT_CLOUD_API_BASE_URL`, and `DIRT_CLOUD_UI_BASE_URL` in the environment, `.env`, or `.env.prod`. Hosted browser auth also requires `DIRT_CLOUD_ADMIN_USERNAME` and `DIRT_CLOUD_ADMIN_PASSWORD_HASH`; it does not read local `AUTH_USERNAME` / `AUTH_PASSWORD`. If `DIRT_CLOUD_DATABASE_URL` is unset locally, the script reads `DATABASE_PUBLIC_URL` from the Railway Postgres service without printing it; the deployed app still uses Railway's internal `DATABASE_URL`.

Do not run app-start DDL. Cloud schema changes live in `cloud/migrations/` and are applied explicitly by Atlas before app deployment.

If the smoke check needs to be skipped during an incident, run:

    scripts/deploy-control-plane --skip-smoke

Then manually check:

    curl -fsS "$DIRT_CLOUD_API_BASE_URL/api/health" | jq .

## Gateway Service

Install or update user units:

    scripts/install-systemd

Start and inspect the gateway:

    systemctl --user start dirt-gateway
    systemctl --user status dirt-gateway
    journalctl --user -u dirt-gateway -f

Run one local dry-run sync cycle without cloud writes:

    systemctl --user stop dirt-gateway
    uv run --package dirt-gateway python -m dirt_gateway.main --once --dry-run

## Monitoring

The unauthenticated cloud health endpoint is:

    curl -fsS "$DIRT_CLOUD_API_BASE_URL/api/health" | jq .

It reports cloud API liveness, gateway heartbeat age, local gateway outbox backlog from the last heartbeat, cloud command backlog, command failures in the last 24 hours, asset upload failures in the last 24 hours, command enablement, and the configured asset retention window.

Browser session state is available at `/api/sync/status` after login. Local structured gateway events are in `var/logs/cloud_gateway/YYYY-MM-DD.jsonl` and include cycle start/finish, enqueue/delivery counts, delivery failures, and asset-failure reporting failures. Cloud audit rows are written for auth login success/failure, command creation, command claims, command results, asset upload completion/failure, asset retention, and gateway credential rotation.

## Asset Retention

Cloud assets have a 30-day V1 retention window (`DIRT_CLOUD_ASSET_RETENTION_DAYS=30`). The gateway enqueues one `asset_retention` maintenance event per day when asset sync is enabled. The cloud API deletes matching `cloud_asset` rows and, when S3 settings are present, deletes the corresponding private bucket objects.

Manual authenticated prune:

    POST /api/admin/assets/prune-expired

Gateway prune route:

    POST /api/gateway/v1/assets/prune-expired

Recent assets still require authenticated signed URL routes; unauthenticated users cannot fetch signed URLs from `/api/assets/{asset_id}/signed-url`.

## Rollback

The first rollback keeps read-only sync active and disables new hosted commands:

1. Set `DIRT_CLOUD_COMMAND_CREATION_ENABLED=false` on Railway service `control-plane-api`.
2. Set `DIRT_CLOUD_GATEWAY_COMMAND_CLAIM_ENABLED=false` if queued command claiming must also stop.
3. Restart or redeploy `control-plane-api` through Railway.
4. Confirm `curl -fsS "$DIRT_CLOUD_API_BASE_URL/api/health" | jq .commands_enabled` returns `false`.

The second rollback stops the local outbound gateway while leaving local automation untouched:

    systemctl --user stop dirt-gateway

Local `dirt-hwd`, `dirt-web`, camera, lights, humidifier, and fan loops continue without the gateway.

## Secret Rotation

Browser admin password: generate a new hash with the same SHA-256 helper used by `dirt_control.security.sha256_password_hash`, set `DIRT_CLOUD_ADMIN_PASSWORD_HASH` on `control-plane-api`, and restart/redeploy the service. Do not set a plaintext hosted password variable; the hosted API accepts only the hash.

Gateway token:

1. Generate a new high-entropy local token and store it in ignored `.env` / `.env.prod` as `DIRT_CLOUD_GATEWAY_TOKEN`.
2. Compute the SHA-256 digest.
3. While logged in to the hosted UI, call `POST /api/admin/gateway-credentials/<DIRT_CLOUD_GATEWAY_ID>/rotate` with `{"token_sha256":"<digest>"}` to update the cloud credential and write an audit row, or rerun `scripts/deploy-control-plane` to upsert the configured credential row.
4. Restart `dirt-gateway` after updating the local token.

Do not print old or new token values in terminal output.
