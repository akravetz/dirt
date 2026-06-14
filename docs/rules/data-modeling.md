# Data Modeling Rule

Read this before creating or changing SQLModel table models, SQL migrations, primary keys, foreign keys, natural keys, uniqueness constraints, table names, or persisted identifiers.

## Rule

Every table gets an integer primary key named `id`.

Use `id` as the canonical identity for Dirt-owned relationships, sync payloads, configuration references, and process boundaries unless there is a concrete reason that an external system cannot use it.

Do not add a second text `*_id` column as a parallel identity. This includes cases where the value is merely more readable, convenient for fixtures, or historically used by Dirt-owned sync/config code.

Integer foreign-key columns may still use the normal SQL convention `referenced_table_id` when they store another table's integer `id`. For example, `plant_location_history.plant_id bigint REFERENCES plant(id)` is correct because it is an integer FK, not a parallel text identifier.

Use `name` or a specific `*_name` for human-readable display text.

Use `*_key` only for a real external, hardware, vendor, protocol, file, or domain-native key whose value is owned outside the table's integer primary key. The model or migration must document who owns the key and why `id` is insufficient.

Do not add names, keys, slugs, codes, or public identifiers by default. Add them only when a current workflow needs that specific value.

## Domain Values and State

Do not model business state as a string enum or text `CHECK (... IN (...))` by default. At the database/application boundary that is still a string contract, which makes spelling drift and application/database disagreement show up late.

Prefer concrete facts:

- Use booleans for true yes/no facts.
- Use nullable foreign keys when a related row proves the fact.
- Use timestamps when the fact is "this happened at this time."
- Use generated columns for facts that are derivable from stored data.
- Use constraints to prevent impossible combinations.

Use lookup tables when the value set needs metadata, display labels, sort order, configuration, ownership outside the table, or reuse across multiple tables. Reference lookup rows by integer `id`. If application code must branch on a lookup value, add explicit semantic columns to the lookup table or remodel the state as concrete facts; do not branch on lookup `name` strings.

Treat unknown as absence where possible: nullable FK, nullable timestamp, nullable boolean, or all relevant fact booleans false. Do not store an `"unknown"` pseudo-value unless unknown is a distinct business state that needs its own metadata or workflow.

Native database enums are allowed only for values that are genuinely static, metadata-free, and not expected to be renamed or extended during normal product work. Prefer facts or lookup tables for business concepts.

## Identifier Checklist

Before adding a text key, answer:

- Is this value owned by Dirt or by an external/domain system?
- Why can't `id` be used for this relationship or boundary?
- Who creates the value?
- Who types, scans, imports, exports, or physically labels the value?
- Must it remain stable if the human display name changes?
- What breaks if the value changes?

If Dirt owns both sides and the value only makes rows easier to read, use `id` plus `name`.

Before adding a string enum/check-list column, answer:

- Can this be represented as concrete booleans, FKs, timestamps, or generated columns?
- Is "unknown" just absence/null?
- Will this value need metadata, labels, ordering, or reuse?
- Will application code branch on this value?
- What prevents application constants and database strings from drifting?

## Examples

Good:

- `device.id` as the Dirt identity; `device.firmware_key` only if firmware reports a stable hardware identifier that exists before or outside the database row.
- `plant.id` as the Dirt identity; `plant.breeding_key` only if the value is printed on plant tags, used in handwritten notes/photos, and must remain stable across exports.
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

## Legacy Cleanup Bias

When editing older tables that already have parallel Dirt-owned text ids, prefer retiring them directly if the owning code can be cut over in the same plan. Do not preserve them as compatibility shims unless there is a live external contract or staged deploy requirement.
