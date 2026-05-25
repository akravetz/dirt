# Device Hostname, Shelly mDNS Resolution, and Irrigation Pulse Schedule

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, Dirt can store a device's local DNS or mDNS hostname directly on the `device` row and use that hostname as the preferred reachability hint for the Shelly Plus Plug US that will control the breeding-tent drip-assist pump. It will also have the database foundation for repeatable irrigation pulses: an enabled irrigation schedule attached to the Shelly pump capability, one or more local-time pulse items with explicit seconds durations, and a durable run ledger so the hardware service can avoid duplicate watering after restarts. This matters because DHCP IP addresses can move, while the Shelly advertises a stable `.local` hostname on the LAN, and because watering is an edge-triggered action where duplicate dispatch is riskier than a missed pulse. A human can observe the result by querying the database for `shelly-breeding-drip-pump`, seeing `hostname='ShellyPlugUSG4-ACEBE6F59BDC.local'`, seeing an irrigation schedule with pulse items, and by running focused tests that prove the Shelly client prefers hostname, falls back to IP, verifies the returned Shelly identity before control, and records pulse attempts idempotently.

The hostname is not authority. Stable device identity still comes from provider identity fields such as `provider_uid_kind='mac'` and `provider_uid='ACEBE6F59BDC'`. The hostname and IP are reachability hints only.

The schedule is not an instruction to leave a pump on for a window. Irrigation uses short pulses. The device command must be a Shelly `Switch.Set` call with `toggle_after` seconds, and the database must store seconds explicitly as `duration_s`.

## Progress

- [x] (2026-05-24 05:18Z) Read repository command, database, Atlas, boundary-contract, and simple-clean-architecture guidance.
- [x] (2026-05-24 05:18Z) Confirmed live Shelly mDNS hostname `ShellyPlugUSG4-ACEBE6F59BDC.local`, IP `192.168.1.44`, model `S4PL-00116US`, and MAC `ACEBE6F59BDC`.
- [ ] Add nullable `device.hostname` to the SQLModel and Atlas migration.
- [ ] Seed the Shelly breeding drip pump device row with hostname, IP hint, MAC provider UID, and an actuator capability.
- [ ] Add irrigation pulse storage: schedule seed, item rows, SQLModel table models, and a run ledger for idempotent dispatch.
- [ ] Add focused Shelly client/resolution tests and implementation.
- [ ] Validate with focused tests, invariants as appropriate, and `scripts/agent-fix`.
- [ ] Commit and push.

## Surprises & Discoveries

- Observation: The working tree already contains unrelated plant-identity edits, including a migration and `migrations/atlas.sum` changes.
  Evidence: `git status --short --branch` showed modified plant files and `migrations/20260524044500_plant_identity_cleanup.sql` before this plan began. This plan must preserve that work.

- Observation: Existing Kasa device resolution already treats stored IPs as hints rather than authority.
  Evidence: `apps/hwd/src/dirt_hwd/services/kasa_inventory.py` tries the stored host first, then discovery, and accepts a device only after its observed MAC matches the DB `provider_uid`.

- Observation: Dirt already has a scoped `schedule` table for local actuator schedules, but no `schedule_item` table.
  Evidence: `apps/shared/src/dirt_shared/models/schedule.py` defines only `Schedule`; `\dt *schedule*` in the live database returns only `public.schedule`.

## Decision Log

- Decision: Add nullable `device.hostname` instead of overloading `metadata` for hostnames.
  Rationale: Hostname is a general reachability hint like `device.ip`, not a Shelly-specific fact. A first-class nullable column keeps queries and future resolvers direct without introducing a broader endpoint table before the domain needs it.
  Date/Author: 2026-05-24 / Codex

- Decision: Keep identity and reachability separate.
  Rationale: MAC and Shelly ID identify the physical device; IP and hostname locate it. Pump control must verify the Shelly identity returned by RPC before issuing power commands.
  Date/Author: 2026-05-24 / Codex

- Decision: Use the stored mDNS hostname as the preferred Shelly endpoint and IP as fallback.
  Rationale: The Shelly advertises a stable `.local` hostname over mDNS, while the IP can change under DHCP. The stored IP remains useful as a fast or fallback hint.
  Date/Author: 2026-05-24 / Codex

- Decision: Reuse the existing `schedule` table for the top-level irrigation schedule and add irrigation-specific item and run tables.
  Rationale: `schedule` already owns scoped local schedules with `site_id`, `tent_id`, `device_id`, `capability_id`, `schedule_id`, `kind`, `timezone`, and `enabled`. A parallel `water_schedule` table would duplicate that source of truth. Irrigation differs from lights and heaters because it has multiple edge-triggered pulses, so `irrigation_schedule_item` should store per-pulse local start times and durations, while `irrigation_run` records attempted dispatches for idempotency and audit.
  Date/Author: 2026-05-25 / Codex

- Decision: Store pulse duration as integer seconds in `duration_s`.
  Rationale: The Shelly safety command accepts seconds through `toggle_after`. A unit-bearing column prevents ambiguity and avoids hidden conversions for safety-critical pump control.
  Date/Author: 2026-05-25 / Codex

## Outcomes & Retrospective

Pending implementation.

## Context and Orientation

Dirt's stable hardware inventory lives in `apps/shared/src/dirt_shared/models/device.py`. The `Device` SQLModel maps to the PostgreSQL `device` table and currently includes `ip`, `provider_uid_kind`, and `provider_uid`. The database uses `device.device_id` as the human-readable local natural key scoped by site, while provider identity fields store controller-specific identity such as a Kasa MAC address.

Local schedules live in `apps/shared/src/dirt_shared/models/schedule.py`. The `Schedule` SQLModel maps to the PostgreSQL `schedule` table and already has scoped ownership fields plus optional device and capability links. Lights and heaters use rows with `kind='lights'` or `kind='heater'`; irrigation should use `kind='irrigation'` rather than a separate top-level water schedule table.

There is no existing `schedule_item` table. Lights and heaters express one on/off window directly on `schedule.starts_local` and `schedule.ends_local`. Irrigation needs a different shape because a water event is a pulse, not a continuous desired state. The durable data model should be `schedule` for the target and enable switch, `irrigation_schedule_item` for recurring local-time pulse definitions, and `irrigation_run` for every due pulse that the service decides to skip, dispatch, or fail.

Kasa resolution in `apps/hwd/src/dirt_hwd/services/kasa_inventory.py` is the closest existing pattern. It tries a stored host, discovers devices if needed, and verifies the observed MAC against the database before returning a controllable plug.

The new Shelly plug is a Shelly Plus Plug US / PlugUSG4 that currently advertises `_shelly._tcp` over mDNS as `ShellyPlugUSG4-ACEBE6F59BDC.local` and responds to Gen2/Gen4 RPC endpoints under `/rpc`. The safety-critical command for the future pump is `Switch.Set` with `toggle_after` seconds so the plug turns itself off.

This plan includes the database foundation for an autonomous irrigation schedule and enough service behavior to dispatch due pulses safely. It does not need to add a UI for editing schedules in this milestone; seed data and focused tests are sufficient for first bring-up.

## Plan of Work

1. Update `Device` in `apps/shared/src/dirt_shared/models/device.py` with `hostname: str | None`, backed by nullable `Text`.
2. Add SQLModel table models for irrigation pulse storage, likely in `apps/shared/src/dirt_shared/models/irrigation.py`, and export them from `apps/shared/src/dirt_shared/models/__init__.py`.
3. Define `IrrigationScheduleItem` with `schedule_id` as a foreign key to `schedule.id`, `starts_local time not null`, `duration_s integer not null`, `enabled boolean not null default true`, nullable `label text`, and timestamps. Add a check constraint that `duration_s > 0`.
4. Define `IrrigationRun` with foreign keys to `schedule.id`, `irrigation_schedule_item.id`, `device.id`, and `capability.id`; `intended_start_at timestamptz not null`; nullable `started_at` and `finished_at`; `duration_s integer not null`; `status text not null`; nullable `error text`; and timestamps. Add a unique constraint on `schedule_item_id, intended_start_at` so retry logic cannot create duplicate run records for the same pulse.
5. Add an Atlas migration under `migrations/` that adds `device.hostname`, creates the irrigation tables, seeds or updates the `shelly-breeding-drip-pump` device under `homebox/breeding`, adds the Shelly pump capability, creates a `schedule` row with `kind='irrigation'`, and seeds conservative disabled or short supervised pulse items for calibration. If the first real pulse timing is unknown, seed the schedule disabled and leave item rows disabled.
6. Add `apps/hwd/src/dirt_hwd/services/shelly.py` with an internal `ShellyPlugTarget`, DB loader, and `ShellyPlugClient` that uses `hostname` before `ip`, verifies `Shelly.GetDeviceInfo`, and sends timed `Switch.Set` pulses.
7. Add an irrigation scheduler service, either in `apps/hwd/src/dirt_hwd/services/shelly_irrigation.py` or next to the Shelly client if the file remains small. The service should load enabled `kind='irrigation'` schedules and enabled pulse items, compute the current due pulse in the schedule timezone, create or reuse the `irrigation_run` row for idempotency, and dispatch exactly one `toggle_after=duration_s` Shelly pulse when due.
8. Add focused tests in `apps/hwd/tests/test_shelly.py` or a separate `apps/hwd/tests/test_shelly_irrigation.py` that cover endpoint ordering, identity mismatch rejection, timed pulse payload shape, DB target loading, due-pulse detection, duplicate-run suppression, disabled schedule/item filtering, and failure status recording.
9. Extend existing scoped identity smoke tests to assert the seeded Shelly row has the expected hostname and provider UID, and add shared-model tests that assert the seeded irrigation schedule and pulse storage point at the Shelly pump capability.

## Concrete Steps

Run from the repository root:

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests/test_shelly.py apps/hwd/tests/test_shelly_irrigation.py apps/shared/tests/test_scoped_identity_models.py -q
    uv run pytest apps/tests/invariants/ -q
    scripts/agent-fix
    git status --short
    git add docs/epics/device-hostname-shelly-mdns/ExecPlan.md apps/shared/src/dirt_shared/models/device.py apps/shared/src/dirt_shared/models/irrigation.py apps/shared/src/dirt_shared/models/__init__.py apps/shared/tests/test_scoped_identity_models.py apps/hwd/src/dirt_hwd/services/shelly.py apps/hwd/src/dirt_hwd/services/shelly_irrigation.py apps/hwd/tests/test_shelly.py apps/hwd/tests/test_shelly_irrigation.py migrations migrations/atlas.sum
    git commit -m "Add Shelly irrigation scheduling foundation"
    git push

Expected focused test result:

    ... passed

## Validation and Acceptance

Acceptance requires:

- `Device.hostname` exists in the SQLModel and migration.
- `IrrigationScheduleItem` and `IrrigationRun` exist as SQLModel table models and are backed by Atlas-managed tables.
- The seeded `shelly-breeding-drip-pump` row has `hostname='ShellyPlugUSG4-ACEBE6F59BDC.local'`, `ip='192.168.1.44'`, `controller='shelly'`, `provider_uid_kind='mac'`, and `provider_uid='ACEBE6F59BDC'`.
- The seeded Shelly capability is the target of a `schedule` row with `kind='irrigation'`; pulse definitions live in `irrigation_schedule_item` with explicit `duration_s`.
- `irrigation_run` has a uniqueness rule that prevents duplicate run rows for the same schedule item and intended start time.
- Shelly tests prove the client tries the hostname before IP and refuses to control a plug whose RPC identity does not match the DB target.
- Timed pulse tests prove the RPC payload includes `toggle_after`, not a sleep-and-off sequence.
- Irrigation scheduler tests prove a due pulse creates one run record and one Shelly command, while a repeated scheduler tick for the same intended start time does not dispatch again.
- Focused pytest commands and `scripts/agent-fix` complete.

## Idempotence and Recovery

The migration should use `ALTER TABLE ... ADD COLUMN` once, `CREATE TABLE` for the new irrigation tables, and idempotent `INSERT ... ON CONFLICT` seed statements for the Shelly row, capability, schedule row, and any calibration pulse items. Re-running tests is safe. If Atlas checksum drift occurs because of the existing uncommitted migration work, regenerate the migration hash with `atlas migrate hash` or the repo-approved Atlas workflow, preserving the unrelated migration file.

The irrigation scheduler must write or find the `irrigation_run` row before dispatching a pulse. If the service crashes after creating a run row but before sending the Shelly command, the conservative recovery is to mark the row failed or skipped and require a later retry/manual decision rather than blindly replaying an old water pulse. Missed irrigation is safer than duplicate watering.

If the Shelly device changes IP, update only `device.ip`; if the mDNS hostname changes because the physical device is replaced, update `hostname` and provider identity together after verifying the replacement.

## Artifacts and Notes

Live bring-up before this plan:

    avahi-browse -rt _shelly._tcp
    hostname = [ShellyPlugUSG4-ACEBE6F59BDC.local]
    address = [192.168.1.44]
    txt = ["ver=1.7.99-plugusg4prod1" "app=PlugUSG4" "gen=4"]

    curl http://192.168.1.44/rpc/Shelly.GetDeviceInfo
    id=shellyplugusg4-acebe6f59bdc mac=ACEBE6F59BDC model=S4PL-00116US app=PlugUSG4 gen=4

    Switch.Set with toggle_after=3 turned on, then status changed to output=false source=timer.

## Interfaces and Dependencies

Database:

- `device.hostname text NULL`
- Seeded device row `device_id='shelly-breeding-drip-pump'`
- Seeded capability row for future pump power state
- `schedule.kind='irrigation'` row targeting the Shelly pump capability
- `irrigation_schedule_item` table:
  - `id bigint primary key`
  - `schedule_id bigint not null references schedule(id)`
  - `starts_local time not null`
  - `duration_s integer not null check (duration_s > 0)`
  - `enabled boolean not null default true`
  - `label text null`
  - `created_at timestamptz not null default now()`
  - `updated_at timestamptz not null default now()`
- `irrigation_run` table:
  - `id bigint primary key`
  - `schedule_id bigint not null references schedule(id)`
  - `schedule_item_id bigint not null references irrigation_schedule_item(id)`
  - `device_id bigint not null references device(id)`
  - `capability_id bigint not null references capability(id)`
  - `intended_start_at timestamptz not null`
  - `started_at timestamptz null`
  - `finished_at timestamptz null`
  - `duration_s integer not null check (duration_s > 0)`
  - `status text not null`
  - `error text null`
  - `created_at timestamptz not null default now()`
  - `updated_at timestamptz not null default now()`
  - unique constraint on `schedule_item_id, intended_start_at`

Python:

- `dirt_shared.models.device.Device.hostname`
- `dirt_shared.models.irrigation.IrrigationScheduleItem`
- `dirt_shared.models.irrigation.IrrigationRun`
- `dirt_hwd.services.shelly.ShellyPlugClient`
- `dirt_hwd.services.shelly.load_shelly_plug_target`
- `dirt_hwd.services.shelly_irrigation.ShellyIrrigationScheduleService`

External:

- Shelly local HTTP RPC under `http://<hostname-or-ip>/rpc`
- mDNS `.local` hostname resolution provided by the host OS/Avahi; no new Python dependency is required.

## Revision Notes

- 2026-05-24 / Codex: Initial plan created.
- 2026-05-25 / Codex: Expanded scope to include irrigation pulse schedule storage and idempotent run ledger, reusing the existing `schedule` table instead of introducing a parallel `water_schedule` table.
