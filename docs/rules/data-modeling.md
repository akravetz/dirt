# Data Modeling Rule

Read this before creating or changing SQLModel table models, SQL migrations, primary keys, foreign keys, natural keys, uniqueness constraints, table names, or persisted identifiers.

## Rule

Object tables get an integer primary key named `id`.

Use `id` as the canonical identity for Dirt-owned object relationships, sync payloads, configuration references, and process boundaries unless there is a concrete reason that an external system cannot use it.

Lookup tables use a different primary-key convention. A lookup table represents a controlled string value set with display and semantic metadata. Lookup tables use a text primary key named `key`, plus at least `display_name` and `display_order`. Referencing object tables store a `*_key` foreign key to the lookup table's `key`.

Name lookup tables close to their owning domain with `_lku_` between the object/domain and lookup concept. This preserves useful lexical ordering in database tools:

- `plant_lku_sex`
- `seed_lot_lku_sex_type`

Avoid stuttered key names. The lookup table primary key is always plain `key`, not `plant_sex_key`, `sex_key`, or another repeated name. Referencing columns should carry the context:

- `plant.sex_key REFERENCES plant_lku_sex(key)`
- `seed_lot.sex_type_key REFERENCES seed_lot_lku_sex_type(key)`

Do not add a second text `*_id` column as a parallel identity. This includes cases where the value is merely more readable, convenient for fixtures, or historically used by Dirt-owned sync/config code.

Integer foreign-key columns may still use the normal SQL convention `referenced_table_id` when they store another table's integer `id`. For example, `plant_location_history.plant_id bigint REFERENCES plant(id)` is correct because it is an integer FK, not a parallel text identifier.

Use `name` or a specific `*_name` for object table human-readable display text. Use `display_name` for lookup table display labels.

Use `*_key` on object tables only when referencing a lookup table, or for a real external, hardware, vendor, protocol, file, or domain-native key whose value is owned outside the table's integer primary key. For non-lookup external/domain keys, the model or migration must document who owns the key and why `id` is insufficient.

Do not add names, keys, slugs, codes, or public identifiers by default. Add them only when a current workflow needs that specific value.

When a field's semantics are not obvious from its name and constraints, document it at both storage and source levels:

- Add a SQL `COMMENT ON COLUMN` in the Atlas migration.
- Add a source-code comment or SQLAlchemy `Column(comment=...)` on the SQLModel field.

This is required for generic-but-domain-specific fields such as `plant.key`, where "key" means the unique human-readable plant identifier printed on tags and used in notes/photos.

## Domain Values and State

Do not model business state as a bare string enum or text `CHECK (... IN (...))` by default. At the database/application boundary that is still a string contract, which makes spelling drift and application/database disagreement show up late.

Prefer concrete facts:

- Use booleans for true yes/no facts.
- Use nullable foreign keys when a related row proves the fact.
- Use timestamps when the fact is "this happened at this time."
- Use generated columns for facts that are derivable from stored data.
- Use constraints to prevent impossible combinations.

Use lookup tables when the value set needs metadata, display labels, sort order, configuration, semantic flags, or reuse across multiple tables. Reference lookup rows by their stable `key`. If application code must branch on a lookup value, add explicit semantic columns to the lookup table, such as `is_female`, `is_regular`, or `is_terminal_state`, or remodel the state as concrete facts. Do not branch on sentinel key strings or display names.

Treat unknown as absence where possible: nullable FK, nullable timestamp, nullable boolean, or all relevant fact booleans false. Do not store an `"unknown"` pseudo-value unless unknown is a distinct business state that needs its own metadata or workflow.

Native database enums are allowed only for values that are genuinely static, metadata-free, and not expected to be renamed or extended during normal product work. Prefer facts or lookup tables for business concepts.

## Identifier Checklist

Before adding a non-lookup text key, answer:

- Is this value owned by Dirt or by an external/domain system?
- Why can't `id` be used for this relationship or boundary?
- Who creates the value?
- Who types, scans, imports, exports, or physically labels the value?
- Must it remain stable if the human display name changes?
- What breaks if the value changes?

If Dirt owns both sides and the value only makes rows easier to read, use `id` plus `name`.

Before adding a lookup table or string enum/check-list column, answer:

- Can this be represented as concrete booleans, FKs, timestamps, or generated columns?
- Is "unknown" just absence/null?
- Will this value need metadata, labels, ordering, or reuse?
- Will application code branch on this value, and what semantic lookup columns should it branch on instead of sentinel keys?
- What prevents application constants and database strings from drifting?

## Examples

Good:

- `device.id` as the Dirt identity; `device.firmware_key` only if firmware reports a stable hardware identifier that exists before or outside the database row.
- `plant.id` as the Dirt identity; `plant.key` only if the value is printed on plant tags, used in handwritten notes/photos, must remain stable across exports, and has SQL/source comments explaining that meaning.
- `plant.sex_key REFERENCES plant_lku_sex(key)` where `plant_lku_sex` has `key`, `display_name`, `display_order`, and semantic flags such as `is_female`.
- `seed_lot.sex_type_key REFERENCES seed_lot_lku_sex_type(key)` where code branches on `seed_lot_lku_sex_type.is_regular`, not the literal key `"regular"`.
- `seed_lot.is_purchased` plus generated `seed_lot.is_produced` from `produced_by_cross_event_id`, with a constraint preventing both from being true.
- `plant.is_clone` generated from `clone_source_plant_id IS NOT NULL`.
- `name` for human-readable labels such as tent name, cultivar name, or device name.

Bad:

- `site.id` plus `site.site_id` just because sync/config code wants a readable identifier.
- `plant_line.id` plus `plant_line.line_id` when strain/cultivar/generation already identify the concept for humans.
- `cross_event.id` plus `cross_event.cross_event_id` unless named crosses are a real physical or logging workflow.
- Adding `display_name`, `slug`, `code`, or `*_id` automatically to every table.
- `seed_lot.source_type text CHECK (source_type IN ('purchased', 'produced', 'unknown'))` when purchased and produced are better modeled as facts.
- `plant.propagation_type text CHECK (propagation_type IN ('seed', 'clone', 'unknown'))` when seed and clone provenance are already represented by nullable FKs.
- `plant_lku_sex.sex_key` or `plant_lku_sex.plant_sex_key`, which repeats the table context instead of using plain `key`.
- Application logic that checks `if plant.sex_key == "female"` instead of joining or projecting a semantic lookup field such as `is_female`.

## Legacy Cleanup Bias

When editing older tables that already have parallel Dirt-owned text ids, prefer retiring them directly if the owning code can be cut over in the same plan. Do not preserve them as compatibility shims unless there is a live external contract or staged deploy requirement.
