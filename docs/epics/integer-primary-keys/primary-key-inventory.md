# Non-integer SQLModel primary key inventory

Date: 2026-06-10

Scope: SQLModel tables under `apps/shared/src/dirt_shared/models/` and
`apps/control-plane/src/dirt_control/models/` whose primary key is not a single
`BigInteger` identity column.

Verification commands used:

```bash
rg -n "primary_key=True|Identity\(" apps/shared/src/dirt_shared/models apps/control-plane/src/dirt_control/models
rg -n "def _.*_key|_key\(" apps/control-plane/src apps/gateway/src apps/shared/src apps/control-plane/tests apps/gateway/tests
uv run python - <<'PY'
import importlib
from pathlib import Path
from sqlmodel import SQLModel

for module_path in Path("apps/shared/src/dirt_shared/models").glob("*.py"):
    if module_path.name != "__init__.py":
        importlib.import_module(f"dirt_shared.models.{module_path.stem}")
importlib.import_module("dirt_control.models.cloud")

for table in sorted(SQLModel.metadata.tables.values(), key=lambda t: t.name):
    pk_cols = list(table.primary_key.columns)
    if not pk_cols:
        continue
    is_int_identity_pk = (
        len(pk_cols) == 1
        and str(pk_cols[0].type).lower().startswith("bigint")
        and getattr(pk_cols[0], "identity", None) is not None
        and getattr(pk_cols[0].identity, "always", None)
    )
    if not is_int_identity_pk:
        uniques = [
            (constraint.name, [column.name for column in constraint.columns])
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        ]
        print(table.name, pk_cols, uniques)
PY
```

All other SQLModel primary keys in the scoped paths are already single
`BigInteger Identity(always=True)` columns.

No reference/code tables with non-integer primary keys were found in the scoped
model directories.

## Hosted synthetic projection and fact keys

These keys are mechanically composed from structured business columns. They are
storage implementation details, not gateway DTO fields or browser response
fields. Later milestones should replace them with integer row identity and
upsert by structured unique constraints.

| File path | Table / model | Current primary key column(s) | Current unique constraints | Synthetic? | API exposed? | Target action |
|---|---|---|---|---|---|---|
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_tent` / `CloudTent` | `tent_key` (`str`) | Unnamed unique on `site_id`, `tent_id` | Yes: `_tent_key(site_id, tent_id)` duplicates the unique columns. | No. Gateway catalog DTOs and browser tent responses expose `site_id` / `tent_id`, not `tent_key`. | Milestone 2: add integer identity `id`, preserve/add a named unique constraint on `site_id`, `tent_id`, remove `tent_key`, and upsert by the structured columns. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_zone` / `CloudZone` | `zone_key` (`str`) | Unnamed unique on `site_id`, `tent_id`, `zone_id` | Yes: `_zone_key(site_id, tent_id, zone_id)` duplicates the unique columns. | No. Gateway catalog DTOs expose structured zone identity only. | Milestone 2: add integer identity `id`, preserve/add a named unique constraint on `site_id`, `tent_id`, `zone_id`, remove `zone_key`, and upsert by the structured columns. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_device` / `CloudDevice` | `device_key` (`str`) | Unnamed unique on `site_id`, `tent_id`, `device_id` | Yes: `_device_key(site_id, tent_id, device_id)` duplicates the unique columns. | Not as an API field. Browser code currently uses `device_key` internally for grouping/audit subject IDs. | Milestone 2: add integer identity `id`, preserve/add a named unique constraint on `site_id`, `tent_id`, `device_id`, remove `device_key`, and replace internal grouping/audit subject usage with structured tuple/string built at the use site or another deliberate subject ID. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_capability` / `CloudCapability` | `capability_key` (`str`) | Unnamed unique on `site_id`, `tent_id`, `device_id`, `capability_id` | Yes: `_capability_key(site_id, tent_id, device_id, capability_id)` duplicates the unique columns. | No. Gateway catalog DTOs expose structured capability identity only. | Milestone 2: add integer identity `id`, preserve/add a named unique constraint on `site_id`, `tent_id`, `device_id`, `capability_id`, remove `capability_key`, and upsert by the structured columns. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_schedule` / `CloudSchedule` | `schedule_key` (`str`) | Unnamed unique on `site_id`, `tent_id`, `schedule_id` | Yes: `_schedule_key(site_id, tent_id, schedule_id)` duplicates the unique columns. | No. Gateway catalog DTOs and capture-policy/browser responses expose structured schedule fields only. | Milestone 2: add integer identity `id`, preserve/add a named unique constraint on `site_id`, `tent_id`, `schedule_id`, remove `schedule_key`, and upsert by the structured columns. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_plant` / `CloudPlant` | `plant_key` (`str`) | Unnamed unique on `site_id`, `tent_id`, `grow_run_id`, `plant_id` | Yes: `_plant_key(site_id, tent_id, grow_run_id, plant_id)` duplicates the unique columns. | Not as an API field. Browser plant responses expose structured plant identity; browser ordering currently references `plant_key` as an internal tie-breaker. | Milestone 2: add integer identity `id`, preserve/add a named unique constraint on `site_id`, `tent_id`, `grow_run_id`, `plant_id`, remove `plant_key`, and replace internal ordering tie-breaker with structured columns or integer `id`. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_wiki_page` / `CloudWikiPage` | `wiki_key` (`str`) | Unnamed unique on `site_id`, `path` | Yes: `_wiki_key(site_id, path)` duplicates the unique columns. | No. Gateway wiki DTOs and browser wiki responses expose `site_id` / `path`, not `wiki_key`. | Milestone 2: add integer identity `id`, preserve/add a named unique constraint on `site_id`, `path`, remove `wiki_key`, and upsert by the structured columns. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_latest_metric` / `CloudLatestMetric` | `metric_key` (`str`) | Unnamed unique on `site_id`, `tent_id`, `device_id`, `capability_id`, `metric` | Yes: `_metric_key(site_id, tent_id, device_id, capability_id, metric)` duplicates the unique columns. | No. Gateway latest-metric DTOs and browser current-metric responses expose structured stream fields only. | Milestone 3: add integer identity `id`, preserve/add a named unique constraint on `site_id`, `tent_id`, `device_id`, `capability_id`, `metric`, remove `metric_key`, and prove repeated latest sync remains idempotent. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_metric_rollup` / `CloudMetricRollup` | `rollup_key` (`str`) | Unnamed unique on `site_id`, `tent_id`, `device_id`, `capability_id`, `metric`, `bucket`, `bucket_start_at` | Yes: `_rollup_key(rollup)` duplicates stream identity plus bucket start. | No. Gateway rollup DTOs and browser history responses expose structured stream and bucket fields only. | Milestone 3: add integer identity `id`, preserve/add a named unique constraint on `site_id`, `tent_id`, `device_id`, `capability_id`, `metric`, `bucket`, `bucket_start_at`, remove `rollup_key`, and prove repeated rollup sync remains idempotent. |

## Hosted external, public, and security identifiers

These string primary keys are not mechanically composed storage keys. They are
currently public protocol identifiers, externally meaningful slugs, or
security/admin identifiers. They should be reviewed separately from synthetic
projection keys.

| File path | Table / model | Current primary key column(s) | Current unique constraints | Synthetic? | API exposed? | Target action |
|---|---|---|---|---|---|---|
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_site` / `CloudSite` | `site_id` (`str`) | None beyond primary key | No. This is the gateway site slug and default scope identifier. | Yes. Gateway heartbeat/catalog/auth scope and browser health/site responses expose `site_id`. | Milestone 4 complete: converted to integer identity `id` primary key plus named unique `site_id`; public `site_id` remains in gateway/browser contracts and route behavior. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_asset` / `CloudAsset` | `asset_id` (`str`) | Unnamed unique on `site_id`, `tent_id`, `object_key` | No. It is supplied by the gateway or derived from `sha256` / `object_key`, and is used as asset object identity. | Yes. Gateway asset sign/complete/failure payloads, browser latest-asset responses, and `/api/assets/{asset_id}/signed-url` expose it. | Milestone 4 complete: converted to integer identity `id` primary key plus named unique `asset_id`; existing `site_id`, `tent_id`, `object_key` uniqueness is preserved with its existing database name. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_command` / `CloudCommand` | `command_id` (`str`) | Unnamed unique on `requested_by`, `idempotency_key` | No. It is a generated command UUID and command protocol handle. | Yes. Browser command APIs and gateway claim/result APIs use `command_id` in payloads and paths. | Milestone 4 complete: converted to integer identity `id` primary key plus named unique `command_id`; public command paths/payloads still use `command_id`, and idempotency uniqueness remains on `requested_by`, `idempotency_key`. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `cloud_audit_event` / `CloudAuditEvent` | `event_id` (`str`) | None beyond primary key | No. It is a generated UUID for audit rows, not a duplicate of other columns. | Not currently exposed as an API field; audit rows are queried for health/audit side effects. | Milestone 4 complete: converted to integer identity `id` primary key plus named unique `event_id`; audit event UUIDs remain available for future external audit APIs. |
| `apps/control-plane/src/dirt_control/models/cloud.py` | `gateway_credential` / `GatewayCredential` | `credential_id` (`str`) | None beyond primary key | No. It is a seeded/admin credential identifier tied to gateway auth and rotation. | Yes. Admin rotation path/response and gateway auth principal use `credential_id`. | Milestone 4 complete: converted to integer identity `id` primary key plus named unique `credential_id`; gateway auth token lookup still uses `token_sha256`, while admin/bootstrap follow-up lookups query by public credential ID. |

## Local cursor and idempotency-like keys

This local key is operational state, not a domain entity or projection fact. It
should not be grouped with hosted synthetic keys.

| File path | Table / model | Current primary key column(s) | Current unique constraints | Synthetic? | API exposed? | Target action |
|---|---|---|---|---|---|---|
| `apps/shared/src/dirt_shared/models/cloud_gateway.py` | `cloud_sync_cursor` / `CloudSyncCursor` | `cursor_key` (`Text`) | None beyond primary key | No. The string is the actual lookup key for a small per-stream cursor map. | No. Used by the local gateway sync service; not part of hosted browser/gateway DTOs. | Milestone 5 complete: leave as-is unless later relationships or multi-column cursor identity appear. This is an acceptable key-value cursor table and should not be converted just because it is a string. |
