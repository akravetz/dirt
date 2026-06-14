# Data Model Cleanup and Breeding Records

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt can track a real breeding program while also cleaning up the broader data-model habit of adding parallel text identifiers to Dirt-owned tables. Every table uses integer `id` as its canonical identity across local relationships, sync payloads, configuration references, and hosted projections. Breeding records add only the extra keys that are real domain artifacts, such as a plant `breeding_key` printed on tags and used in notes/photos.

Each plant has a required strain and cultivar through its plant line, optional seed-lot or clone provenance, durable lifecycle timestamps, current and historical tent position, daily notes, and breeding events such as pollen collection or sex observation. The hosted UI can answer "which plants are currently in this tent and where are they?" directly from plant location history instead of inferring that from `growrun`.

This matters because breeding records must survive tent moves, culling, flowering runs, future clone/mother workflows, and parent selection. `growrun` currently owns plant identity, strain, germination date, and flower date in ways that are no longer truthful. The target architecture makes the individual plant the durable record, makes `plant_location_history` the occupancy model for tents and grid positions, and removes grow-run-centered compatibility shims rather than preserving stale A-D assumptions.

The work is complete when a developer can query current plants in a tent with `plant_location_history.end_at IS NULL`, see plant tag keys such as `SBBS-R1-001` without confusing those keys for database identity, record free-text notes and breeding events per plant, record internal crosses and resulting seed lots, move plants between tents without changing identity, and run the hosted dashboard against generated API contracts that no longer expose `grow_run_id` as plant identity scope.


## Progress

- [x] (2026-06-14T00:00Z) Drafted the data-model-first ExecPlan from the user's breeding-program requirements and the repo's current `growrun`/`plant` model.
- [x] (2026-06-14T00:00Z) Revised the plan into a broader data-model cleanup plan: integer `id` is canonical Dirt identity, parallel text `*_id` columns are not allowed for human convenience, and plant tag values use `breeding_key`.
- [ ] Implement local SQLModel tables, constraints, generated columns, and Atlas migration.
- [ ] Cut over services, gateway/cloud sync, hosted browser API, and generated frontend contracts.
- [ ] Retire `growrun` from source-owned code and database schema.
- [ ] Validate locally and record implementation evidence.


## Surprises & Discoveries

- Observation: The current source-of-truth plant model is still grow-run scoped.
  Evidence: `apps/shared/src/dirt_shared/models/plant.py` enforces `UniqueConstraint("growrun_id", "plant_id")`; `apps/shared/src/dirt_shared/models/grow_run.py` stores `germination_date`, `flower_start_date`, `strain`, `plant_count`, and `is_current`.

- Observation: Hosted cloud plant projection repeats the grow-run scope.
  Evidence: `apps/control-plane/src/dirt_control/models/cloud.py` defines `CloudPlant` with unique key `(site_id, tent_id, grow_run_id, plant_id)` and `CloudPlantMetricStream` includes `grow_run_id`.

- Observation: Several existing Dirt tables use integer `id` plus text `*_id` as a parallel identity.
  Evidence: `site.site_id`, `tent.tent_id`, `device.device_id`, and `growrun.grow_run_id` follow this pattern. This plan must not copy that pattern into new breeding tables unless the text key is owned by a real external, hardware, vendor, protocol, file, or domain workflow.

- Observation: Plant-breeding standards and tools separate germplasm identity, seed or accession provenance, crosses/pedigree, individual plants, and observations.
  Evidence: BrAPI, Breedbase, MCPD, and MIAPPE all model these as separate concepts rather than overloading one "plant" row. Relevant references: `https://brapi.org/`, `https://plant-breeding-api.readthedocs.io/`, `https://solgenomics.github.io/sgn/`, `https://www.genesys-pgr.org/descriptorlists/0cd31350-234b-4ebf-80bc-fc65f14f7541`, and `https://www.miappe.org/`.


## Decision Log

- Decision: Retire `growrun` as a plant identity, strain, and lifecycle owner.
  Rationale: Plant identity must survive tent moves and future flowering tents. A grow run is an operational cohort concept, but Dirt's current `growrun` table has become the canonical owner of plant facts that belong to individual plants or plant lines.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Use integer `id` as Dirt's canonical identity, including Dirt-owned sync and configuration boundaries.
  Rationale: Parallel text `*_id` columns make the data model harder to reason about when Dirt owns both sides. Readability alone is not a reason to create a second identity.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Replace the old A-D scoped plant text identity with `plant.breeding_key`, not `plant.plant_id`.
  Rationale: Values such as `SBBS-R1-001` are real breeding tags that people will write on labels, notes, and photos, but they are not the database identity. The database identity remains `plant.id`.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Represent purchased seed lines and internally bred lines with the same `plant_line` table.
  Rationale: Both purchased and internally bred material still has strain and cultivar identity. Purchased lines can leave `project_code` and `generation_label` null or partially known without requiring a separate model.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Require both `strain` and `cultivar` on `plant_line`.
  Rationale: The user wants those fields to be explicit for purchased seeds and internal lines. Unknown parents do not excuse missing strain/cultivar labels in Dirt's working record.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Include clone provenance now, but keep it simple.
  Rationale: Cannabis breeding commonly uses clones, mothers, and reversed plants. The schema should not assume every plant germinated from seed, but v1 does not need a separate mother/clone subsystem.
  Date/Author: 2026-06-14 / Codex

- Decision: Store core lifecycle state directly on `plant`, not only as events.
  Rationale: `germinated_at`, `veg_started_at`, `flower_started_at`, `culled_at`, `culled_reason`, `harvested_at`, and `selected_for_breeding_at` are first-class plant state queried by UI and services. Requiring every caller to find the latest event of each type would create avoidable complexity.
  Date/Author: 2026-06-14 / Codex

- Decision: Use `plant_event` for irregular breeding actions and observations.
  Rationale: Event rows are a good fit for facts such as pollen collected, sex observed, reversed, clone taken, and transplant notes. They avoid widening `plant` for every future breeding action.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Use `plant_location_history` with `position` as free text and current occupancy derived from `end_at IS NULL`.
  Rationale: The grid system is not finalized, but the UI needs current tent occupancy now. A text `position` supports values like `A1` or `D5`; partial unique indexes and exclusion constraints keep current and overlapping locations coherent.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Model seed production canonically as `seed_lot` rows, not only as plant events.
  Rationale: A produced seed lot is durable source material for future plants. A `seeds_produced` event can still be recorded as a note-like event, but the seed lot is the queryable artifact used by propagation.
  Date/Author: 2026-06-14 / Codex

- Decision: Do not model breeding business state as string enum/check-list columns.
  Rationale: At the database/application boundary those values are still string contracts. Concrete facts, generated columns, lookup tables, and constraints make drift harder and keep the model closer to the domain.
  Date/Author: 2026-06-14 / User + Codex


## Outcomes & Retrospective

No implementation has been performed yet. Fill this section after each milestone with the actual migration file names, commands run, API contract changes, and validation evidence.


## Context and Orientation

Dirt uses SQLModel table classes under `apps/shared/src/dirt_shared/models/` for local PostgreSQL state, Atlas migrations under `migrations/`, and a hosted control-plane projection under `apps/control-plane/src/dirt_control/models/cloud.py`. Browser-facing hosted API response types are generated from FastAPI OpenAPI into `web-ui/src/api-client/generated/hosted-schema.ts`; do not hand-write hosted response interfaces in `web-ui/src/api-client/cloud.ts`.

The current relevant source files are:

- `apps/shared/src/dirt_shared/models/grow_run.py`: current grow-cycle table that must be retired from plant identity and lifecycle ownership.
- `apps/shared/src/dirt_shared/models/plant.py`: current plant table, still scoped by `growrun_id`.
- `apps/shared/src/dirt_shared/models/enums.py`: current Postgres enum definitions for grow stage, plant status, and sticker color.
- `apps/shared/src/dirt_shared/services/grow_state.py`: currently derives stage and environmental target context from `growrun.germination_date` and `growrun.flower_start_date`.
- `apps/shared/src/dirt_shared/cloud_contract.py`: gateway-to-control-plane catalog DTOs that currently include `grow_run_id` on plant payloads.
- `apps/gateway/src/dirt_gateway/local.py` and `apps/gateway/src/dirt_gateway/sync.py`: local-to-cloud projection and outbox code.
- `apps/control-plane/src/dirt_control/models/cloud.py`: hosted mirror tables that currently scope plants by `grow_run_id`.
- `apps/control-plane/src/dirt_control/api/browser.py`: hosted browser API responses consumed by the React dashboard.
- `web-ui/src/routes/tents.$tentId.plants.$plantId.tsx` and related UI files: browser plant listing/detail surfaces.

Use these repository rules while implementing:

- Read `docs/database.md` before editing SQLModel classes or Atlas migrations.
- Read `docs/rules/data-modeling.md` before adding or preserving persisted identifiers.
- Read `docs/rules/simple-clean-architecture.md` before making compatibility decisions.
- Read `docs/rules/boundary-contracts.md` before changing gateway, control-plane, outbox, or generated browser payloads.
- Read `docs/references/atlas/INDEX.md` before running Atlas commands or editing migration files.
- Read `docs/references/tanstack-router-v1/INDEX.md`, `docs/references/tailwind-v4/INDEX.md`, and `docs/references/modern-idiomatic-typescript/INDEX.md` before editing relevant web-ui route or TypeScript files.


## Proposed Data Model

The SQL below is the target shape. Implementation should migrate existing tables with `ALTER TABLE` where practical, but these `CREATE TABLE` statements define the final model and constraints.

Use `timestamptz` for timestamps. Application code must write UTC-aware datetimes; PostgreSQL stores the moment in time and renders it in the session timezone.

Some target FKs form a real cycle: plants can come from seed lots, produced seed lots can come from crosses, and crosses reference parent plants. The migration may create tables first and add those FKs with `ALTER TABLE` after all referenced tables exist. The final constraints must still match the target model below.

### `plant_line`

`plant_line` represents the genetic/market identity of a line of plants. It covers purchased seed lines and internal breeding lines. Purchased lines usually have `project_code IS NULL` and may have `generation_label IS NULL`; internal lines can use values such as `SBBS` and `R1`.

```sql
CREATE TABLE plant_line (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_code text NULL,
    generation_label text NULL,
    strain text NOT NULL,
    cultivar text NOT NULL,
    description text NULL,
    source_name text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_plant_line_identity UNIQUE NULLS NOT DISTINCT (
        project_code,
        generation_label,
        strain,
        cultivar
    ),
    CONSTRAINT ck_plant_line_project_code_not_blank CHECK (
        project_code IS NULL OR btrim(project_code) <> ''
    ),
    CONSTRAINT ck_plant_line_generation_label_not_blank CHECK (
        generation_label IS NULL OR btrim(generation_label) <> ''
    ),
    CONSTRAINT ck_plant_line_strain_not_blank CHECK (btrim(strain) <> ''),
    CONSTRAINT ck_plant_line_cultivar_not_blank CHECK (btrim(cultivar) <> ''),
    CONSTRAINT ck_plant_line_description_not_blank CHECK (
        description IS NULL OR btrim(description) <> ''
    ),
    CONSTRAINT ck_plant_line_source_name_not_blank CHECK (
        source_name IS NULL OR btrim(source_name) <> ''
    )
);
```

Constraints to implement:

- Primary key on `id`.
- Unique identity across `project_code`, `generation_label`, `strain`, and `cultivar` with `NULLS NOT DISTINCT` so duplicate external lines cannot be inserted by leaving nullable fields null.
- Required non-empty `strain` and `cultivar`.
- Nullable text fields must be either null or non-blank.

### `cross_event`

`cross_event` records an intentional breeding cross between two known Dirt plants. It is only for crosses where the parent plants are in Dirt. Purchased seed-line parent labels stay on `plant_line` notes/description until the actual parents exist as plants.

```sql
CREATE TABLE cross_event (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resulting_line_id bigint NOT NULL,
    seed_parent_plant_id bigint NOT NULL,
    pollen_parent_plant_id bigint NOT NULL,
    pollinated_at timestamptz NOT NULL,
    pollen_parent_is_reversed boolean NULL,
    notes text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_cross_event_resulting_line
        FOREIGN KEY (resulting_line_id) REFERENCES plant_line(id) ON DELETE RESTRICT,
    CONSTRAINT fk_cross_event_seed_parent
        FOREIGN KEY (seed_parent_plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT fk_cross_event_pollen_parent
        FOREIGN KEY (pollen_parent_plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT ck_cross_event_distinct_parents CHECK (
        seed_parent_plant_id <> pollen_parent_plant_id
    ),
    CONSTRAINT ck_cross_event_notes_not_blank CHECK (
        notes IS NULL OR btrim(notes) <> ''
    )
);
```

Constraints to implement:

- Primary key on `id`.
- Required FK to the resulting `plant_line`.
- Required FKs to seed parent and pollen parent `plant` rows.
- Parents must be two different plant rows.
- `pollen_parent_is_reversed` is a nullable fact: `true` means reversed female pollen, `false` means regular male pollen, and `NULL` means not recorded.

### `seed_lot`

`seed_lot` represents acquired or produced seed material. It is the canonical source record for seed-grown plants.

```sql
CREATE TABLE seed_lot (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    line_id bigint NOT NULL,
    is_purchased boolean NOT NULL DEFAULT false,
    vendor_name text NULL,
    acquired_at timestamptz NULL,
    produced_by_cross_event_id bigint NULL,
    is_produced boolean GENERATED ALWAYS AS (produced_by_cross_event_id IS NOT NULL) STORED,
    seed_count integer NULL,
    notes text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_seed_lot_line
        FOREIGN KEY (line_id) REFERENCES plant_line(id) ON DELETE RESTRICT,
    CONSTRAINT fk_seed_lot_cross_event
        FOREIGN KEY (produced_by_cross_event_id) REFERENCES cross_event(id) ON DELETE RESTRICT,
    CONSTRAINT ck_seed_lot_not_purchased_and_produced CHECK (
        NOT (is_purchased AND produced_by_cross_event_id IS NOT NULL)
    ),
    CONSTRAINT ck_seed_lot_vendor_for_purchased CHECK (
        NOT is_purchased OR (vendor_name IS NOT NULL AND btrim(vendor_name) <> '')
    ),
    CONSTRAINT ck_seed_lot_vendor_only_when_purchased CHECK (
        is_purchased OR vendor_name IS NULL
    ),
    CONSTRAINT ck_seed_lot_seed_count_positive CHECK (
        seed_count IS NULL OR seed_count >= 0
    ),
    CONSTRAINT ck_seed_lot_notes_not_blank CHECK (
        notes IS NULL OR btrim(notes) <> ''
    )
);
```

Constraints to implement:

- Primary key on `id`.
- Required FK to `plant_line`.
- `is_purchased` is a stored fact.
- `is_produced` is generated from `produced_by_cross_event_id IS NOT NULL`.
- A seed lot cannot be both purchased and produced.
- Purchased seed lots must have a non-blank vendor and no internal cross.
- Produced seed lots reference a `cross_event`.
- Unknown source is represented as `is_purchased = false` and `produced_by_cross_event_id IS NULL`.
- `seed_count` cannot be negative.

### `plant`

`plant` is the durable individual plant record. A clone gets its own integer `id` and its own `breeding_key` even when genetically identical to its source plant.

```sql
CREATE TABLE plant (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    breeding_key text NOT NULL,
    line_id bigint NOT NULL,
    source_seed_lot_id bigint NULL,
    clone_source_plant_id bigint NULL,
    is_seed_grown boolean GENERATED ALWAYS AS (source_seed_lot_id IS NOT NULL) STORED,
    is_clone boolean GENERATED ALWAYS AS (clone_source_plant_id IS NOT NULL) STORED,
    name text NOT NULL,
    germinated_at timestamptz NULL,
    rooted_at timestamptz NULL,
    veg_started_at timestamptz NULL,
    flower_started_at timestamptz NULL,
    culled_at timestamptz NULL,
    culled_reason text NULL,
    harvested_at timestamptz NULL,
    selected_for_breeding_at timestamptz NULL,
    selected_for_breeding_reason text NULL,
    moisture_target_low double precision NOT NULL DEFAULT 55,
    moisture_target_high double precision NOT NULL DEFAULT 70,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_plant_breeding_key UNIQUE (breeding_key),
    CONSTRAINT fk_plant_line
        FOREIGN KEY (line_id) REFERENCES plant_line(id) ON DELETE RESTRICT,
    CONSTRAINT fk_plant_source_seed_lot
        FOREIGN KEY (source_seed_lot_id) REFERENCES seed_lot(id) ON DELETE RESTRICT,
    CONSTRAINT fk_plant_clone_source
        FOREIGN KEY (clone_source_plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT ck_plant_breeding_key_not_blank CHECK (btrim(breeding_key) <> ''),
    CONSTRAINT ck_plant_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_plant_seed_or_clone_not_both CHECK (
        source_seed_lot_id IS NULL OR clone_source_plant_id IS NULL
    ),
    CONSTRAINT ck_plant_not_self_clone CHECK (
        clone_source_plant_id IS NULL OR clone_source_plant_id <> id
    ),
    CONSTRAINT ck_plant_seed_not_rooted_as_clone CHECK (
        source_seed_lot_id IS NULL OR rooted_at IS NULL
    ),
    CONSTRAINT ck_plant_clone_not_germinated CHECK (
        clone_source_plant_id IS NULL OR germinated_at IS NULL
    ),
    CONSTRAINT ck_plant_culled_reason_required CHECK (
        (culled_at IS NULL AND culled_reason IS NULL)
        OR (culled_at IS NOT NULL AND culled_reason IS NOT NULL AND btrim(culled_reason) <> '')
    ),
    CONSTRAINT ck_plant_culled_or_harvested_not_both CHECK (
        culled_at IS NULL OR harvested_at IS NULL
    ),
    CONSTRAINT ck_plant_selection_reason_not_blank CHECK (
        selected_for_breeding_reason IS NULL OR btrim(selected_for_breeding_reason) <> ''
    ),
    CONSTRAINT ck_plant_moisture_low_bounds CHECK (
        moisture_target_low >= 0 AND moisture_target_low < moisture_target_high
    ),
    CONSTRAINT ck_plant_moisture_high_bounds CHECK (
        moisture_target_high <= 100
    )
);
```

Constraints to implement:

- Primary key on `id`.
- Globally unique `breeding_key`, no grow-run scope. This is the physical/domain plant tag, not the database identity.
- Required FK to `plant_line`.
- Optional FK to `seed_lot` for seed-grown plants.
- Optional self-FK to clone source plant for clones.
- `is_seed_grown` and `is_clone` are generated from provenance FKs.
- Unknown propagation is represented as both provenance FKs null.
- A plant cannot be both seed-grown and clone-propagated.
- Culling requires a non-blank reason.
- A plant cannot be both culled and harvested.
- `selected_for_breeding_at` means approved parent used or planned for breeding, not merely "keep for now".
- Keep moisture target bounds because existing plant telemetry and watering surfaces depend on them.

### `plant_location_history`

`plant_location_history` tracks current and past tent occupancy. `position` is free text for v1 and can hold grid coordinates such as `A1`, `B1`, or `D5`.

```sql
CREATE TABLE plant_location_history (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plant_id bigint NOT NULL,
    site_id bigint NOT NULL,
    tent_id bigint NOT NULL,
    zone_id bigint NULL,
    position text NOT NULL,
    start_at timestamptz NOT NULL,
    end_at timestamptz NULL,
    is_current boolean GENERATED ALWAYS AS (end_at IS NULL) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_plant_location_plant
        FOREIGN KEY (plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT fk_plant_location_site
        FOREIGN KEY (site_id) REFERENCES site(id) ON DELETE RESTRICT,
    CONSTRAINT fk_plant_location_tent
        FOREIGN KEY (tent_id) REFERENCES tent(id) ON DELETE RESTRICT,
    CONSTRAINT fk_plant_location_zone
        FOREIGN KEY (zone_id) REFERENCES zone(id) ON DELETE RESTRICT,
    CONSTRAINT ck_plant_location_position_not_blank CHECK (btrim(position) <> ''),
    CONSTRAINT ck_plant_location_time_order CHECK (
        end_at IS NULL OR end_at > start_at
    )
);

CREATE UNIQUE INDEX ux_plant_location_current_per_plant
    ON plant_location_history (plant_id)
    WHERE end_at IS NULL;

CREATE UNIQUE INDEX ux_plant_location_current_position_per_tent
    ON plant_location_history (tent_id, position)
    WHERE end_at IS NULL;

CREATE INDEX ix_plant_location_current_tent
    ON plant_location_history (tent_id, position, plant_id)
    WHERE end_at IS NULL;

CREATE INDEX ix_plant_location_plant_start
    ON plant_location_history (plant_id, start_at DESC);

ALTER TABLE plant_location_history
    ADD CONSTRAINT ex_plant_location_no_overlap_per_plant
    EXCLUDE USING gist (
        plant_id WITH =,
        tstzrange(start_at, COALESCE(end_at, 'infinity'::timestamptz), '[)') WITH &&
    );

ALTER TABLE plant_location_history
    ADD CONSTRAINT ex_plant_location_no_overlap_per_tent_position
    EXCLUDE USING gist (
        tent_id WITH =,
        position WITH =,
        tstzrange(start_at, COALESCE(end_at, 'infinity'::timestamptz), '[)') WITH &&
    );
```

Constraints to implement:

- Primary key on `id`.
- Required FK to `plant`, `site`, and `tent`; optional FK to `zone`.
- `position` must be non-blank text.
- `end_at` must be after `start_at` when present.
- Generated `is_current` field equals `end_at IS NULL`; application code should treat `end_at` as the source of truth.
- A plant can have only one current location.
- A tent position can have only one current plant.
- Exclusion constraints prevent overlapping historical locations for the same plant and overlapping historical occupancy for the same tent position. The migration must enable `btree_gist` if it is not already enabled.

### `plant_note`

`plant_note` stores free-text daily notes and observations. This is intentionally separate from structured trait scoring; add structured observations later only when the workflow requires it.

```sql
CREATE TABLE plant_note (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plant_id bigint NOT NULL,
    observed_at timestamptz NOT NULL,
    body text NOT NULL,
    created_by text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_plant_note_plant
        FOREIGN KEY (plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT ck_plant_note_body_not_blank CHECK (btrim(body) <> ''),
    CONSTRAINT ck_plant_note_created_by_not_blank CHECK (
        created_by IS NULL OR btrim(created_by) <> ''
    )
);

CREATE INDEX ix_plant_note_plant_observed_at
    ON plant_note (plant_id, observed_at DESC);
```

Constraints to implement:

- Primary key on `id`.
- Required FK to `plant`.
- Required non-blank `body`.
- Indexed by plant and observation time for plant detail timelines.

### `plant_event`

`plant_event` stores irregular breeding actions or observations. Lifecycle fields on `plant` remain canonical for cull, harvest, veg start, and flower start.

```sql
CREATE TABLE plant_event (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plant_id bigint NOT NULL,
    is_pollen_collection boolean NOT NULL DEFAULT false,
    is_seed_production boolean NOT NULL DEFAULT false,
    is_clone_taken boolean NOT NULL DEFAULT false,
    is_sex_observation boolean NOT NULL DEFAULT false,
    is_reversal boolean NOT NULL DEFAULT false,
    is_transplant boolean NOT NULL DEFAULT false,
    is_selection_for_breeding boolean NOT NULL DEFAULT false,
    occurred_at timestamptz NOT NULL,
    reason text NULL,
    notes text NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_plant_event_plant
        FOREIGN KEY (plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT ck_plant_event_one_kind CHECK (
        (CASE WHEN is_pollen_collection THEN 1 ELSE 0 END) +
        (CASE WHEN is_seed_production THEN 1 ELSE 0 END) +
        (CASE WHEN is_clone_taken THEN 1 ELSE 0 END) +
        (CASE WHEN is_sex_observation THEN 1 ELSE 0 END) +
        (CASE WHEN is_reversal THEN 1 ELSE 0 END) +
        (CASE WHEN is_transplant THEN 1 ELSE 0 END) +
        (CASE WHEN is_selection_for_breeding THEN 1 ELSE 0 END) = 1
    ),
    CONSTRAINT ck_plant_event_reason_not_blank CHECK (
        reason IS NULL OR btrim(reason) <> ''
    ),
    CONSTRAINT ck_plant_event_notes_not_blank CHECK (
        notes IS NULL OR btrim(notes) <> ''
    ),
    CONSTRAINT ck_plant_event_metadata_object CHECK (
        jsonb_typeof(metadata) = 'object'
    )
);

CREATE INDEX ix_plant_event_plant_occurred_at
    ON plant_event (plant_id, occurred_at DESC);
```

Constraints to implement:

- Primary key on `id`.
- Required FK to `plant`.
- Event kind is represented by explicit boolean facts with an exactly-one constraint, not a string type column.
- Add partial indexes for individual event-kind booleans only when query volume requires them.
- `metadata` is reserved for opaque event details; if application logic begins depending on a structured metadata shape, define a Pydantic DTO at that boundary before writing/reading it.
- Indexed by plant timeline.


## GrowRun Retirement

`growrun` should be removed from source-owned plant identity and lifecycle flows in the same implementation series. Do not keep a long-term compatibility wrapper that rehydrates grow-run semantics from the new tables.

Target changes:

- Remove `Plant.growrun_id`, replace `UniqueConstraint("growrun_id", "plant_id")` with canonical integer `plant.id`, and rename the old text plant tag to `plant.breeding_key`.
- Move current `growrun.strain` to `plant_line.strain` and `plant_line.cultivar`.
- Move current `growrun.germination_date` and `growrun.flower_start_date` to plant-level `germinated_at` and `flower_started_at` timestamps for each existing plant.
- Replace `growrun.is_current` tent membership with `plant_location_history.end_at IS NULL`.
- Replace `growrun.plant_count` with count queries over current plant locations.
- Replace `GrowStateService` with a plant/tent context service that derives plant stage from plant lifecycle timestamps and derives tent context from current plants.
- Remove `growrun_id` from local cloud catalog DTOs, gateway outbox payloads, hosted `CloudPlant`, hosted `CloudPlantMetricStream`, browser responses, and generated frontend types. Dirt-owned sync should carry integer row identity and `breeding_key` only as a displayed/tagged domain key.
- Remove `Snapshot.growrun_id` or stop writing it, then drop it once no query or projection depends on it. Snapshots should remain scoped by site/tent/view and can gain direct plant association later if plant-specific snapshot identity becomes necessary.
- Drop the `growrun` table only after source code, tests, cloud schema, and generated contracts no longer reference it.

The direct cutover is intentional. If a deploy-order bridge is required between gateway and hosted control-plane, keep it inside one milestone and remove it before the plan is complete.


## Plan of Work

Milestone 1 validates current data and finalizes breeding-key mapping. Inspect all existing `growrun`, `plant`, `plant_metric_stream`, `snapshot`, `cloud_plant`, and `cloud_plant_metric_stream` rows. Create a migration mapping for every existing plant. The expected main-tent tag mapping is old text `a -> SBBS-R1-001`, `b -> SBBS-R1-002`, `c -> SBBS-R1-003`, and `d -> SBBS-R1-004`, preserving integer row ids and moisture metric stream ownership. If existing breeding-tent rows such as `r1` through `r5` exist, add explicit `breeding_key` mappings for those rows before applying the migration; do not derive new keys implicitly.

Milestone 2 implements local SQLModel target tables. Add `PlantLine`, `SeedLot`, `CrossEvent`, `PlantLocationHistory`, `PlantNote`, and `PlantEvent` models under `apps/shared/src/dirt_shared/models/`. Modify `Plant` to match the target schema: canonical integer `id`, required `breeding_key`, plant-line/provenance FKs, lifecycle timestamps, breeding selection fields, and no `growrun_id`. Update `apps/shared/src/dirt_shared/models/__init__.py`.

Milestone 3 creates and reviews the Atlas migration. The migration must create new tables, backfill one `plant_line` and `seed_lot` for current purchased `Sirius Black x BS01` material, rename the old text plant identifiers to `breeding_key` values using the explicit mapping, create current `plant_location_history` rows for each active plant, move grow-run dates to plant lifecycle timestamps, preserve `plant_metric_stream` relationships, remove `plant.growrun_id`, remove obsolete grow-run constraints, and eventually drop `growrun`. Use a compressed custom-format backup before local apply as described in `docs/database.md`.

Milestone 4 updates local services. Replace `GrowStateService` callers with a plant/tent context service. Update plant listing/detail/moisture services to query current plants through `plant_location_history`; order by grid `position` and then `breeding_key`. Use integer `plant.id` for internal lookups and sync identity. Update daily reports, camera publisher, sensor summaries, and any voice tools that still use grow-run plant scope.

Milestone 5 updates gateway and hosted cloud projection. Extend `dirt_shared.cloud_contract` with DTOs for plant lines, seed lots, plant locations, plant notes if needed by the browser, and plant rows without `grow_run_id`. Update gateway local projection and outbox validation before changing control-plane routes. Update `CloudPlant` uniqueness to the Dirt-owned integer source plant identity, carry `breeding_key` as a displayed/tagged domain key, add cloud mirror tables for line/location data needed by the browser, and remove `grow_run_id` from hosted plant metric stream identity.

Milestone 6 updates browser API and frontend. Regenerate the hosted OpenAPI client with `scripts/gen-hosted-contract` after FastAPI response models change. Update the tent plant list to query current location rows and show `position`. Update plant detail to show line identity, lifecycle timestamps, current location, notes, and events. Keep the first UI pass workmanlike and data-dense; do not build a marketing or landing page.

Milestone 7 removes dead code and validates. Delete source-owned grow-run code, route fields, tests, and docs that only preserve the old model. Do not edit human-owned invariants. Run focused backend tests, control-plane tests, gateway tests, web-ui typecheck/lint/tests, invariants, and `make fix`. Record exact evidence in this ExecPlan.


## Concrete Steps

Read required docs:

    cd /home/akcom/code/dirt
    sed -n '1,240p' docs/database.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,260p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/references/atlas/INDEX.md

Inspect current schema and references:

    rg -n "growrun|grow_run_id|GrowRun|germination_date|flower_start_date|plant_count|is_current" apps web-ui contracts migrations docs -g '*'
    rg -n "class Plant|CloudPlant|CatalogPlant|PlantMetricStream|plant_location|plant_note|plant_event" apps web-ui contracts -g '*'

Inspect live local data before writing the migration:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "\d growrun"
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "\d plant"
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT t.tent_id, g.grow_run_id, g.strain, g.germination_date, g.flower_start_date, p.plant_id, p.name FROM plant p JOIN growrun g ON g.id = p.growrun_id JOIN tent t ON t.id = p.tent_id ORDER BY t.tent_id, p.plant_id;"

Create the local models and migration:

    atlas migrate diff breeding_data_model --env local
    atlas migrate hash --env local
    atlas migrate apply --env local --dry-run

Back up before applying locally:

    set -a; source .env; set +a
    mkdir -p var/db-backups
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump \
      -h 127.0.0.1 -U dirt -d dirt \
      -Fc --compress=zstd:level=6 \
      -f var/db-backups/dirt-$(date +%F-%H%M%S)-pre-breeding-data-model.dump

Apply locally only after reviewing the SQL:

    atlas migrate apply --env local

Regenerate hosted contracts after API changes:

    scripts/gen-hosted-contract

Run focused validation as implementation progresses:

    uv run pytest apps/shared/tests -q
    uv run pytest apps/gateway/tests -q
    uv run pytest apps/control-plane/tests -q
    uv run pytest apps/tests/invariants/ -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test

Before committing implementation work:

    make fix


## Validation and Acceptance

Database acceptance:

- `plant.id` is the canonical Dirt identity for relationships, sync, and configuration references.
- `plant.breeding_key` is globally unique and no longer scoped by `growrun_id`; it is the physical/domain plant tag, not the database identity.
- Business state is not represented by string enum/check-list columns such as `source_type`, `propagation_type`, `event_type`, or `pollen_source_type`.
- `plant_line` has required non-blank `strain` and `cultivar`.
- Current purchased material is represented by `plant_line` plus `seed_lot`, even if parent plants are unknown.
- Current plants have explicit breeding keys, lifecycle timestamps migrated from old grow-run dates where appropriate, and current `plant_location_history` rows.
- The query for current tent plants uses `plant_location_history.end_at IS NULL`.
- A plant cannot have two current locations.
- A tent position cannot have two current plants.
- Culling cannot be recorded without a non-blank `culled_reason`.
- `growrun` is absent from the final schema, or the only remaining references are explicitly documented external historical artifacts scheduled for deletion in the same plan.

Run acceptance SQL after local apply:

```sql
SELECT p.id, p.breeding_key, pl.strain, pl.cultivar, p.germinated_at, p.flower_started_at
FROM plant p
JOIN plant_line pl ON pl.id = p.line_id
ORDER BY p.breeding_key;

SELECT t.tent_id, l.position, p.id, p.breeding_key, l.start_at
FROM plant_location_history l
JOIN plant p ON p.id = l.plant_id
JOIN tent t ON t.id = l.tent_id
WHERE l.end_at IS NULL
ORDER BY t.tent_id, l.position, p.breeding_key;

SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name IN ('growrun_id', 'grow_run_id')
ORDER BY table_name, column_name;

SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name IN ('source_type', 'propagation_type', 'event_type', 'pollen_source_type')
ORDER BY table_name, column_name;
```

Expected result: current plants list with integer ids and breeding keys; current tent positions list without duplicates; no source-owned current tables expose `growrun_id`, `grow_run_id`, `source_type`, `propagation_type`, `event_type`, or `pollen_source_type`.

API and UI acceptance:

- Hosted browser API returns current tent plants from location history with integer `id`, `breeding_key`, line identity, current `position`, lifecycle timestamps, and no `grow_run_id`.
- Plant detail can show notes and events for one globally identified plant.
- Moving a plant to another tent closes the old location row and opens a new row without changing `plant.id` or `plant.breeding_key`.
- The frontend uses generated hosted types and contains no hand-written hosted plant response interfaces.

Test acceptance:

- Focused shared model/service tests pass.
- Gateway sync tests pass with typed DTO validation for the new plant catalog shape.
- Control-plane API tests pass with generated browser response models.
- `uv run pytest apps/tests/invariants/ -q` passes without editing human-owned invariant tests.
- `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, and `pnpm --dir web-ui test` pass.
- `make fix` passes before commit.


## Idempotence and Recovery

Model and service edits are normal source changes and can be rerun safely. Atlas migration generation is not idempotent if repeated with different model state; inspect generated SQL, keep one migration file for this plan, and run `atlas migrate hash --env local` after manual edits.

Before applying DDL to the local live database, create the compressed custom-format backup shown above. Restore into a fresh database with `pg_restore` if rollback inspection is needed; do not casually restore over the live database. Hosted deployment must use `scripts/deploy-control-plane`; do not run ad hoc Railway DDL or app-start DDL.

If migration review finds unexpected existing plant rows, stop and update the explicit plant-id mapping in the migration rather than applying a derived rename. If a deploy-order issue requires temporary cloud compatibility, record it in `Decision Log`, keep it narrow, and remove it before marking this plan complete.


## Artifacts and Notes

Internet research sources used for the data-model split:

- BrAPI: `https://brapi.org/` and `https://plant-breeding-api.readthedocs.io/`
- Breedbase: `https://solgenomics.github.io/sgn/`
- FAO/Bioversity MCPD: `https://www.genesys-pgr.org/descriptorlists/0cd31350-234b-4ebf-80bc-fc65f14f7541`
- MIAPPE: `https://www.miappe.org/`
- Iowa State plant breeding notation: `https://iastate.pressbooks.pub/cropimprovement/chapter/pedigree-naming-systems-and-symbols/`

Current user decisions captured in this draft:

- Every table should use integer `id` as the canonical Dirt identity.
- Do not add text `*_id` columns merely for human convenience or Dirt-owned sync/config readability.
- Use `name`/`*_name` for human display text and `*_key` only for a real external, hardware, vendor, protocol, file, or domain-native key.
- Avoid string enum/check-list columns for business state; prefer concrete facts, generated columns, lookup tables, and constraints.
- Plant tag values such as `SBBS-R1-001` should be modeled as `plant.breeding_key`, not `plant.plant_id`.
- Do not maintain backwards compatibility shims for old plant identity.
- Plants may move between tents.
- Purchased seed lines use the same `plant_line` table, with nullable `project_code` and nullable `generation_label`.
- Both `strain` and `cultivar` are required on `plant_line`.
- Clones should get their own integer `plant.id` rows and their own `breeding_key` values.
- `selected_for_breeding` means approved parent used or planned for breeding.
- `plant_location_history.position` is free text for v1.
- Culling requires both `culled_at` and `culled_reason`.


## Interfaces and Dependencies

Final local database interfaces:

- `plant_line`
- `seed_lot`
- `cross_event`
- `plant`
- `plant_location_history`
- `plant_note`
- `plant_event`
- Existing `plant_metric_stream`, updated only as needed to reference the global `plant` row without grow-run scope.

Final source modules:

- `apps/shared/src/dirt_shared/models/plant.py` owns `Plant`, `PlantMetricStream`, `PlantLine`, `SeedLot`, `CrossEvent`, `PlantLocationHistory`, `PlantNote`, and `PlantEvent`, unless implementation splits the new models into small files and re-exports them from `models/__init__.py`.
- `apps/shared/src/dirt_shared/services/grow_state.py` is removed or replaced by a plant/tent context service with no dependency on `growrun`.
- `apps/shared/src/dirt_shared/cloud_contract.py` exposes typed gateway DTOs with no `grow_run_id` in plant identity.
- `apps/control-plane/src/dirt_control/models/cloud.py` mirrors the new hosted plant identity and location projection.
- `web-ui/src/api-client/generated/hosted-schema.ts` is regenerated from FastAPI OpenAPI.

External dependencies:

- PostgreSQL 17.
- Atlas migrations.
- `btree_gist` PostgreSQL extension for location overlap exclusion constraints.
- Existing uv workspace and pnpm web-ui toolchain.


## Revision Notes

- 2026-06-14 / Codex: Initial draft with target SQL schemas, constraints, grow-run retirement path, migration strategy, and validation plan.
- 2026-06-14 / Codex: Added the data-modeling rule preference and revised the plan to remove duplicative text identifiers from `plant_line`, `cross_event`, and `seed_lot`; `plant.breeding_key` now represents the physical/domain plant tag while integer `plant.id` remains canonical identity.
