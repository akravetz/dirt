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

## Identifier Checklist

Before adding a text key, answer:

- Is this value owned by Dirt or by an external/domain system?
- Why can't `id` be used for this relationship or boundary?
- Who creates the value?
- Who types, scans, imports, exports, or physically labels the value?
- Must it remain stable if the human display name changes?
- What breaks if the value changes?

If Dirt owns both sides and the value only makes rows easier to read, use `id` plus `name`.

## Examples

Good:

- `device.id` as the Dirt identity; `device.firmware_key` only if firmware reports a stable hardware identifier that exists before or outside the database row.
- `plant.id` as the Dirt identity; `plant.breeding_key` only if the value is printed on plant tags, used in handwritten notes/photos, and must remain stable across exports.
- `seed_lot.id` as the Dirt identity; `seed_lot.vendor_lot_key` only if the vendor packet has a lot code worth preserving.
- `name` for human-readable labels such as tent name, cultivar name, or device name.

Bad:

- `site.id` plus `site.site_id` just because sync/config code wants a readable identifier.
- `plant_line.id` plus `plant_line.line_id` when strain/cultivar/generation already identify the concept for humans.
- `cross_event.id` plus `cross_event.cross_event_id` unless named crosses are a real physical or logging workflow.
- Adding `display_name`, `slug`, `code`, or `*_id` automatically to every table.

## Legacy Cleanup Bias

When editing older tables that already have parallel Dirt-owned text ids, prefer retiring them directly if the owning code can be cut over in the same plan. Do not preserve them as compatibility shims unless there is a live external contract or staged deploy requirement.
