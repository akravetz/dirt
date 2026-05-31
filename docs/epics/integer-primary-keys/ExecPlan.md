# Replace synthetic string primary keys with integer row identity

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, Dirt's local and hosted databases use relational row identity consistently: most persisted tables have `id bigint generated always as identity primary key`, while real business identity is enforced with named `UNIQUE` constraints over structured columns. Operators and future agents no longer need to reason about colon-joined synthetic strings such as `metric_key`, `rollup_key`, `capability_key`, or `plant_key` as if they were domain objects.

This matters because the current hosted control-plane schema mixes two concepts: row identity and sync/business identity. A metric stream really is identified by structured fields such as `site_id`, `tent_id`, `device_id`, `capability_id`, and `metric`; a rollup is that stream plus `bucket` and `bucket_start_at`. Those fields should remain visible and constrained, but the storage primary key should be a stable database-owned integer. The observable outcome is simpler models, simpler upsert helpers, fewer string-building functions, clearer indexes, and generated browser/API payloads that expose domain fields rather than storage implementation keys.

## Progress

- [x] (2026-05-31) Drafted the migration plan after review of the metric presentation PR exposed new string primary keys.
- [ ] Inventory all local and cloud string primary keys and classify them as entity/fact tables, reference/code tables, external IDs, or cursor/idempotency keys.
- [ ] Convert hosted control-plane projection tables from string synthetic primary keys to integer identity primary keys plus unique business constraints.
- [ ] Remove synthetic key construction from gateway/control-plane sync code.
- [ ] Convert any remaining local tables that use string primary keys without a strong external-ID reason.
- [ ] Regenerate hosted contracts and simplify frontend/API code that no longer needs storage key concepts.

## Surprises & Discoveries

- Observation: The metric presentation PR originally added `metric` as the primary key on `metric_presentation` and `cloud_metric_presentation`.
  Evidence: The first version of `apps/shared/src/dirt_shared/models/metric_presentation.py` used `Column(Text, primary_key=True)`, and `apps/control-plane/src/dirt_control/models/cloud.py` used `Field(primary_key=True, max_length=120)` for `CloudMetricPresentation.metric`.
- Observation: The hosted control-plane already has the target business uniqueness constraints beside the string synthetic primary keys for most projection tables.
  Evidence: `CloudTent` has `tent_key` as primary key and `UniqueConstraint("site_id", "tent_id")`; `CloudCapability` has `capability_key` as primary key and `UniqueConstraint("site_id", "tent_id", "device_id", "capability_id")`; `CloudMetricRollup` has `rollup_key` as primary key and a unique constraint over `site_id`, `tent_id`, `device_id`, `capability_id`, `metric`, `bucket`, and `bucket_start_at`.

## Decision Log

- Decision: New tables added by the metric presentation PR should be fixed in that PR to use integer identity primary keys.
  Rationale: The PR should not extend the synthetic string primary key pattern. This is low-risk because the presentation tables have no foreign keys or API exposure of their row identity.
  Date/Author: 2026-05-31 / Codex
- Decision: Existing hosted projection tables should be migrated in a dedicated follow-up PR, not folded into metric presentation.
  Rationale: Re-keying existing cloud tables affects gateway idempotent upserts, existing production rows, tests, and generated contracts. It is an architectural storage migration with different risk from metric presentation.
  Date/Author: 2026-05-31 / Codex
- Decision: Keep structured natural/business identities as `UNIQUE` constraints, not as application-built string columns.
  Rationale: A metric name alone is not unique, but the real uniqueness belongs in database constraints over actual columns. This preserves data integrity while removing lossy colon-joined storage keys.
  Date/Author: 2026-05-31 / Codex

## Outcomes & Retrospective

Not started. Update this section after each milestone with the concrete schema state, code simplifications, migration evidence, and any tables intentionally left with non-integer primary keys.

## Context and Orientation

Dirt has a local PostgreSQL database managed by Atlas migrations in `migrations/` and a hosted control-plane schema managed by Atlas migrations in `cloud/migrations/`. SQLModel classes for local shared tables live under `apps/shared/src/dirt_shared/models/`. Hosted control-plane SQLModel classes live in `apps/control-plane/src/dirt_control/models/cloud.py`.

The problematic pattern is a string column whose value is mechanically built from other columns and used as the primary key. Examples in `apps/control-plane/src/dirt_control/models/cloud.py` include:

- `CloudTent.tent_key`, currently duplicating `site_id`, `tent_id`.
- `CloudZone.zone_key`, currently duplicating `site_id`, `tent_id`, `zone_id`.
- `CloudDevice.device_key`, currently duplicating `site_id`, `tent_id`, `device_id`.
- `CloudCapability.capability_key`, currently duplicating `site_id`, `tent_id`, `device_id`, `capability_id`.
- `CloudSchedule.schedule_key`, currently duplicating `site_id`, `tent_id`, `schedule_id`.
- `CloudPlant.plant_key`, currently duplicating `site_id`, `tent_id`, `grow_run_id`, `plant_id`.
- `CloudWikiPage.wiki_key`, currently duplicating `site_id`, `path`.
- `CloudLatestMetric.metric_key`, currently duplicating `site_id`, `tent_id`, `device_id`, `capability_id`, `metric`.
- `CloudMetricRollup.rollup_key`, currently duplicating `site_id`, `tent_id`, `device_id`, `capability_id`, `metric`, `bucket`, `bucket_start_at`.

These are not API concepts. Gateway request DTOs in `apps/shared/src/dirt_shared/cloud_contract.py` already carry structured fields. The control-plane gateway API in `apps/control-plane/src/dirt_control/api/gateway.py` builds synthetic keys through helpers such as `_metric_key()` and `_rollup_key()` before calling `_upsert()`. The correct final design is for `_upsert()` or table-specific upsert functions to target unique constraints over structured fields, not a generated string primary key.

Some string primary keys may remain when the string is genuinely external identity or an operational token. Examples to review carefully instead of converting mechanically:

- `CloudSite.site_id`: may be an externally meaningful site slug. Prefer integer `id` plus unique `site_id` if foreign-key relationships grow, but do not break existing gateway auth scope casually.
- `CloudAsset.asset_id`: may be a content digest or object identity used by asset flows.
- `CloudCommand.command_id`, `CloudAuditEvent.event_id`, and `GatewayCredential.credential_id`: may be externally visible IDs or security-related identifiers.
- `CloudOutboxCursor.cursor_key`: a small operational cursor table where a string key may be acceptable.

## Plan of Work

Milestone 1: Inventory and classify primary keys.

Create a checked-in inventory under this ExecPlan or `docs/progress/` listing every SQLModel table whose primary key is not an integer identity column. For each table, record the file path, current primary key column, current unique constraints, whether the key is synthetic, whether the key is exposed over an API, and the target action. Use `rg -n "primary_key=True|Identity\\(" apps/shared/src/dirt_shared/models apps/control-plane/src/dirt_control/models`.

Acceptance for this milestone: there is an explicit table-by-table decision before any broad migration is written.

Milestone 2: Convert hosted projection catalog tables.

Target `CloudTent`, `CloudZone`, `CloudDevice`, `CloudCapability`, `CloudSchedule`, `CloudPlant`, and `CloudWikiPage` in `apps/control-plane/src/dirt_control/models/cloud.py`.

For each table:

- Add `id: int | None` with `Column(BigInteger, Identity(always=True), primary_key=True)`.
- Change the existing `*_key` column from primary key to ordinary nullable or non-null string temporarily, then remove it in the same milestone if no code/API still uses it.
- Preserve or add a named unique constraint over the structured business key.
- Replace `_tent_key()`, `_zone_key()`, `_device_key()`, `_capability_key()`, `_schedule_key()`, `_plant_key()`, and `_wiki_key()` usage in `apps/control-plane/src/dirt_control/api/gateway.py` with table-specific upserts by unique columns.
- Keep gateway DTOs unchanged unless a DTO currently exposes a storage key. They should carry structured fields only.

Migration shape for each table:

    ALTER TABLE "cloud_tent" ADD COLUMN "id" bigint GENERATED ALWAYS AS IDENTITY;
    ALTER TABLE "cloud_tent" DROP CONSTRAINT "cloud_tent_pkey";
    ALTER TABLE "cloud_tent" ADD CONSTRAINT "cloud_tent_pkey" PRIMARY KEY ("id");
    ALTER TABLE "cloud_tent" DROP COLUMN "tent_key";

Before dropping a `*_key` column, verify no foreign key references it and no application code reads it. If a table has no named unique constraint for its business identity, add one before removing the synthetic key.

Milestone 3: Convert hosted metric fact tables.

Target `CloudLatestMetric` and `CloudMetricRollup`.

For `CloudLatestMetric`, preserve uniqueness on:

    site_id, tent_id, device_id, capability_id, metric

For `CloudMetricRollup`, preserve uniqueness on:

    site_id, tent_id, device_id, capability_id, metric, bucket, bucket_start_at

Change the control-plane gateway route `metrics_latest()` and `metrics_rollups()` in `apps/control-plane/src/dirt_control/api/gateway.py` so they upsert by those unique constraints instead of `_metric_key()` and `_rollup_key()`. Remove the helper functions after all call sites are gone.

This milestone is the highest risk because it affects idempotency. It must include tests that post the same latest/rollup payload twice and prove there is still one row with updated values, not duplicates.

Milestone 4: Review externally visible string IDs.

Review `CloudSite`, `CloudAsset`, `CloudCommand`, `CloudAuditEvent`, and `GatewayCredential`. For each, decide whether to convert now, leave with a documented reason, or split storage identity from public ID.

Preferred pattern for externally visible IDs:

    id bigint generated always as identity primary key,
    command_id varchar(...) not null unique

Do not remove public IDs from API payloads when they are part of an external contract. The goal is to remove public/string IDs as storage primary keys, not to make public APIs unusable.

Milestone 5: Convert remaining local tables with synthetic string primary keys.

Inspect `apps/shared/src/dirt_shared/models/` after hosted conversion. Most local domain tables already use integer identity primary keys. Likely exceptions include operational cursor tables such as `CloudOutboxCursor.cursor_key`. Convert only tables where the string key is a synthetic duplicate of other columns. Leave genuine key-value cursor tables alone if the string key is the actual lookup key and there are no relationships.

Milestone 6: Simplify code and contracts.

After storage migrations:

- Delete key-builder helpers in `apps/control-plane/src/dirt_control/api/gateway.py`.
- Remove `*_key` attributes from SQLModel classes.
- Regenerate hosted browser contracts with `scripts/gen-hosted-contract` if any browser-visible schema changed.
- Run stale-code searches for `tent_key`, `zone_key`, `device_key`, `capability_key`, `schedule_key`, `plant_key`, `wiki_key`, `metric_key`, and `rollup_key`.
- Simplify tests so they assert structured identity behavior and idempotency instead of colon-joined key strings.

## Concrete Steps

Start with documentation and inventory:

    cd /home/akcom/code/dirt
    rg -n "primary_key=True|Identity\\(" apps/shared/src/dirt_shared/models apps/control-plane/src/dirt_control/models
    rg -n "def _.*_key|_key\\(" apps/control-plane/src apps/gateway/src apps/shared/src apps/control-plane/tests apps/gateway/tests

For each migration milestone:

    cd /home/akcom/code/dirt
    atlas migrate diff <name> --env cloud
    atlas migrate hash --env cloud
    set -a; source .env; set +a; atlas migrate apply --env cloud --dry-run

For local-schema changes:

    cd /home/akcom/code/dirt
    atlas migrate diff <name> --env local
    atlas migrate hash --env local
    set -a; source .env; set +a; atlas migrate apply --env local --dry-run

Run focused tests after each milestone:

    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    uv run pytest apps/gateway/tests/test_sync.py -q
    uv run pytest apps/tests/invariants/ -q

Run full validation before opening the PR:

    make fix
    uv run pytest -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build
    git diff --check

## Validation and Acceptance

The migration is accepted when all of these are true:

- No hosted projection table uses a mechanically composed `*_key` column as its primary key.
- Tables that need business identity have named `UNIQUE` constraints over structured columns.
- Gateway latest and rollup sync remains idempotent when the same payload is sent repeatedly.
- Browser/API payloads do not expose storage-only integer IDs unless there is a deliberate product reason.
- Searches for synthetic storage keys return no active code paths except documented external IDs or cursor/idempotency tables:

    rg -n "tent_key|zone_key|device_key|capability_key|schedule_key|plant_key|wiki_key|metric_key|rollup_key" apps/control-plane apps/gateway apps/shared web-ui

- Atlas dry-runs pass for local and cloud migrations.
- Full Python and web validation passes.

## Idempotence and Recovery

Adding identity columns and unique constraints is safe to dry-run repeatedly. Applying migrations to production cloud state is not reversible without a backup. Before the production apply, take a cloud database backup through the hosted provider or a compressed dump if credentials and network access allow it. Do not deploy app code that expects removed `*_key` columns until the migration that removes them has applied.

For each table, use this sequence to reduce risk:

1. Add integer `id` identity column.
2. Backfill automatically through PostgreSQL identity behavior and verify no null IDs.
3. Ensure a unique constraint exists for the structured business key.
4. Update application upserts to use structured columns.
5. Remove the synthetic key column.

If deployment sequencing requires it, split steps 1-3 and steps 4-5 into separate PRs. Do not keep compatibility wrappers longer than one migration cycle.

## Artifacts and Notes

Useful initial search:

    rg -n "primary_key=True|Identity\\(" apps/shared/src/dirt_shared/models apps/control-plane/src/dirt_control/models

Initial high-priority hosted synthetic keys found in `apps/control-plane/src/dirt_control/models/cloud.py`:

    tent_key, zone_key, device_key, capability_key, schedule_key,
    plant_key, wiki_key, metric_key, rollup_key

Metric presentation tables were corrected in the metric presentation PR so that new schema does not add more string primary keys:

    metric_presentation.id bigint generated always as identity primary key
    metric_presentation.metric unique
    cloud_metric_presentation.id bigint generated always as identity primary key
    cloud_metric_presentation.metric unique

## Interfaces and Dependencies

The final schema must expose these storage conventions:

- SQLModel table classes use `id: int | None = Field(default=None, sa_column=Column(BigInteger, Identity(always=True), primary_key=True))` for row identity unless explicitly documented otherwise.
- Business identity is represented by named `UniqueConstraint(...)` entries on structured columns.
- Gateway request DTOs in `apps/shared/src/dirt_shared/cloud_contract.py` continue to use structured fields such as `site_id`, `tent_id`, `device_id`, `capability_id`, `metric`, `bucket`, and `bucket_start_at`.
- Control-plane gateway routes in `apps/control-plane/src/dirt_control/api/gateway.py` upsert by structured unique constraints, not colon-joined string keys.

## Revision Notes

- 2026-05-31: Initial plan written after metric presentation PR review identified synthetic string primary keys as a broader schema problem.
