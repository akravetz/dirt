# AC Infinity ThermoForge Night Heat

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

The main tent gets too cold overnight. A ThermoForge heater is connected to an AC Infinity Controller 69 Pro that is reachable locally over Bluetooth Low Energy. After this change, Dirt will run ThermoForge heaters as DB-known scheduled heater actuators:

- when a ThermoForge heater's enabled `schedule.kind='heater'` window is active, Dirt turns that ThermoForge on and sets heat level `4`;
- when that heater schedule is inactive, Dirt turns that ThermoForge off.

This first release is intentionally not a temperature feedback controller. It follows explicit heater schedules in the database and uses local BLE control so night heat does not depend on AC Infinity cloud availability or an internet connection.

Dirt already has a breeding Kasa heat pad scheduled from the database. This plan standardizes that vocabulary so Kasa heat pads and AC Infinity ThermoForge devices are both modeled as heaters:

- `schedule.kind='heater'`;
- `capability.capability_id='power'` with `metric_name='heater_on'`;
- `capability.capability_id='heat_level'` with `metric_name='heater_heat_level'` for devices that expose discrete heat levels;
- observability stream `heater`.

The safety and reliability goals are explicit:

- Production control connects to the MAC address stored on each DB-known AC Infinity BLE device only. There is no scan/discovery fallback in the service.
- If the controller cannot be reached, that is an actionable failure. Dirt sends a Telegram notification, keeps the service alive, and retries with exponential backoff capped at 5 minutes.
- If the controller comes back after being unplugged, rebooted, or disconnected from a phone, Dirt reconnects and reconciles the heater back to the schedule-derived target.


## Progress

- [x] (2026-05-16) Read `.agents/PLANS.md`, `docs/commands.md`, `docs/observability.md`, and `docs/rules/simple-clean-architecture.md`.
- [x] (2026-05-16) Inspected hardware service patterns in `apps/hwd/src/dirt_hwd/app.py`, `apps/hwd/src/dirt_hwd/services/humidifier.py`, `apps/hwd/src/dirt_hwd/services/fan_controller.py`, and `apps/hwd/src/dirt_hwd/services/metric_freshness.py`.
- [x] (2026-05-16) Confirmed existing Telegram alert helper in `apps/shared/src/dirt_shared/services/telegram.py`.
- [x] (2026-05-16) Reverse-engineered the AC Infinity BLE command packet shape from Android Bluetooth HCI logs and live Controller 69 Pro writes.
- [x] (2026-05-16) Live-tested local BLE writes: off, on, and set heat level `4` worked against Controller 69 Pro `80:B5:4E:4D:27:CA`.
- [x] (2026-05-16) Wrote this implementation plan.
- [x] (2026-05-16) Revised the plan to make ThermoForge placement and schedules DB-driven and to standardize existing Kasa heat pad vocabulary under `heater`.
- [ ] Promote the reverse-engineered ThermoForge protocol into tested app code.
- [ ] Add an exact-MAC BLE client and night-heat actuator service.
- [ ] Add configuration, observability, Telegram alerts, and retry/backoff behavior.
- [ ] Wire the service into `dirt-hwd`.
- [ ] Validate with unit tests, invariants, and a controlled live test.


## Surprises & Discoveries

- Observation: The AC Infinity mobile app writes compact command bodies wrapped in an AC Infinity packet with two CRC-16/CCITT-FALSE checksums.
  Evidence: Android HCI capture `debug/bugreport2.zip` contained writes to ATT handle `0x0030`; captured packets reproduce exactly with `crccheck` CRC-16/CCITT-FALSE.

- Observation: Controller 69 Pro write and notify characteristics are stable in the captured session.
  Evidence: BLE service UUID `70d51000-2c7f-4e75-ae8a-d758951ce4e0`, write characteristic `70d51001-2c7f-4e75-ae8a-d758951ce4e0`, notify characteristic `70d51002-2c7f-4e75-ae8a-d758951ce4e0`.

- Observation: The command bodies needed for the first actuator release are known.
  Evidence: App capture showed `0003100101ff00` for off, `0003100102ff00` for on, and `00031201XXff00` for heat level `XX`.

- Observation: Status notifications expose enough state to reconcile without blind writes.
  Evidence: In 54-byte status frames, observed heat level is `(byte48 & 0x3c) >> 2`; observed running state is true when `byte17 == 0x02` and `byte16 & 0x02` is set.

- Observation: Live BLE writes through `debug/ac-infinity-research/thermoforge_write.py` controlled the physical heater.
  Evidence: Off write ramped observed status from level `4` to level `0` and running false. On plus level `4` write ramped observed status back to level `4` and running true.

- Surprise: A phone connection can make the controller temporarily unavailable to Dirt.
  Evidence: During manual testing, the phone app connection affected BLE availability. Production should treat this as a real offline state, alert once, and retry instead of scanning for a different device.

- Observation: The current data model already supports general heater devices and schedules.
  Evidence: `Device` has scoped site/tent/zone ownership plus `provider_uid_kind` and `provider_uid`; `Capability` is per-device and can reuse public IDs like `power`; `Schedule` points to a specific device/capability and carries `kind`, local start/end times, timezone, and enabled state.

- Observation: The existing Kasa breeding heat pad already uses this model but with heat-pad-specific vocabulary.
  Evidence: `migrations/20260515030000_seed_breeding_heat_pad.sql` seeds `schedule.kind='heat_pad'`, `capability_id='heat_pad_power'`, metric `heat_pad_on`, and observability stream `heat_pad`.


## Decision Log

- Decision: Implement ThermoForge as a scheduled heater actuator, not a humidity or temperature feedback loop.
  Rationale: The current goal is to keep grow spaces warm overnight. Explicit DB schedules make this general across the main tent, breeding tent, Dirt Two, and future boxes without adding one-off service config per tent.
  Date/Author: 2026-05-16 / User, recorded by Codex

- Decision: Use local BLE writes instead of AC Infinity cloud automation for production control.
  Rationale: Cloud automation would be simpler to call but depends on internet connectivity. The heater is needed specifically when the local tent environment gets too cold, so local control is the right first reliability boundary.
  Date/Author: 2026-05-16 / User/Codex

- Decision: Production connects only to the DB device `provider_uid` MAC for each ThermoForge schedule; it does not scan for a fallback device.
  Rationale: If the configured Controller 69 Pro cannot be reached, something needs attention. Scanning can hide misconfiguration, phone contention, or the wrong controller being nearby.
  Date/Author: 2026-05-16 / User/Codex

- Decision: BLE availability failures stay inside the ThermoForge service loop and trigger Telegram transition alerts plus exponential backoff capped at 300 seconds.
  Rationale: The rest of `dirt-hwd` should keep running, and the heater service should recover automatically when the controller is available again.
  Date/Author: 2026-05-16 / User/Codex

- Decision: Do not turn the heater off unconditionally during service shutdown.
  Rationale: A systemd restart during the dark period should not create an avoidable cold interval. On startup and reconnect, the service reconciles to the current light-derived target. Safety-off behavior belongs to explicit policy states such as lights on, disabled service, or missing/untrusted schedule context.
  Date/Author: 2026-05-16 / Codex

- Decision: Keep debug scan helpers under `debug/` only.
  Rationale: Scanning and packet probing are useful research tools, but they are not part of the production control contract.
  Date/Author: 2026-05-16 / Codex

- Decision: Standardize scheduled heat vocabulary as `heater`.
  Rationale: The Kasa heat pad and ThermoForge serve the same operational role. `heater` is vendor-neutral and avoids carrying a heat-pad-specific name into ThermoForge and Dirt Two work.
  Date/Author: 2026-05-16 / User/Codex

- Decision: Use generic capability IDs `power` and `heat_level`, with metrics `heater_on` and `heater_heat_level`.
  Rationale: `power` is a clear capability but an ambiguous metric name because it can mean watts. `heater_on` is an unambiguous boolean reading; `heater_heat_level` is explicit for discrete level devices.
  Date/Author: 2026-05-16 / User/Codex

- Decision: Keep ThermoForge heat level `4` in service config for the first release.
  Rationale: The immediate need uses one configured level across ThermoForge devices. Adding per-schedule target JSON is possible later, but it is unnecessary until different boxes need different levels.
  Date/Author: 2026-05-16 / User/Codex


## Outcomes & Retrospective

Not yet implemented. At completion, record whether the BLE protocol module remained small, whether the exact-MAC connection path was reliable on the deployment host, how Telegram alert noise behaved during controller contention, and whether actuator metrics were sufficient for dashboard/device freshness visibility.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before implementation:

- `docs/commands.md` before running tests, lint, service commands, or dependency commands.
- `docs/observability.md` before adding or changing `log_event()` streams.
- `docs/rules/simple-clean-architecture.md` before adding abstractions or compatibility paths.
- `docs/database.md` and `docs/references/atlas/INDEX.md` before editing SQLModel models, adding enum values, or creating Atlas migrations.
- `docs/rules/boundary-contracts.md` before changing APIs, gateway payloads, command payloads, outbox JSON, or generated contracts.

Important existing code:

- `apps/hwd/src/dirt_hwd/app.py` wires long-running hardware services into `dirt-hwd`.
- `apps/hwd/src/dirt_hwd/services/humidifier.py` shows the current pattern for an actuator loop that records readings, logs structured events, sends Telegram alerts, catches expected provider failures, and keeps running.
- `apps/hwd/src/dirt_hwd/services/fan_controller.py` shows the current pattern for deriving a target from grow state and dispatching only when the target differs from observed state.
- `apps/hwd/src/dirt_hwd/services/metric_freshness.py` shows transition-style Telegram alerting backed by state under `var/logs/`.
- `apps/shared/src/dirt_shared/config.py` owns environment-backed settings and purpose-specific config slices.
- `apps/shared/src/dirt_shared/services/telegram.py` provides `TelegramClient.send_message(...)`.
- `apps/shared/src/dirt_shared/models/device.py` defines scoped hardware identity. `Device.provider_uid_kind='mac'` plus `Device.provider_uid='<MAC>'` is already the stable identity pattern.
- `apps/shared/src/dirt_shared/models/schedule.py` defines DB schedules that can point at a specific device and capability.
- `apps/hwd/src/dirt_hwd/services/kasa_schedule.py` already reconciles DB-known Kasa schedules. It currently loads `lights` and `heat_pad`; this plan changes heater schedules to `heater`.
- `apps/shared/src/dirt_shared/observability.py` owns known log streams and retention.

Reverse-engineered ThermoForge facts:

- Controller 69 Pro name observed during testing: `83T65`.
- Controller 69 Pro MAC observed during testing: `80:B5:4E:4D:27:CA`.
- BLE service UUID: `70d51000-2c7f-4e75-ae8a-d758951ce4e0`.
- BLE write characteristic UUID: `70d51001-2c7f-4e75-ae8a-d758951ce4e0`.
- BLE notify characteristic UUID: `70d51002-2c7f-4e75-ae8a-d758951ce4e0`.
- Command body for off: `0003100101ff00`.
- Command body for on: `0003100102ff00`.
- Command body for level `N`: `00031201NNff00`.
- Packet wrapper: `a5 00`, two-byte big-endian body length minus two, two-byte big-endian sequence, CRC-16/CCITT-FALSE over the prefix through sequence, command body, CRC-16/CCITT-FALSE over the command body.
- Captured app packet examples:
  - off: `a50000050015055d0003100101ff00790f`
  - on: `a5000005001eb4360003100102ff00205f`
  - level `7`: `a5000005003251d80003120107ff008f2c`
  - level `1`: `a500000500455fa80003120101ff003d8c`
  - level `4`: `a5000005008e378f0003120104ff00d67c`
- Status notifications observed during live tests are 54 bytes.
- Status heat level decode: `(frame[48] & 0x3c) >> 2`.
- Status running decode used for this release: `frame[17] == 0x02 and bool(frame[16] & 0x02)`.

Research artifacts:

- `debug/ac-infinity-research/ble_probe.py` is a BLE exploration helper.
- `debug/ac-infinity-research/thermoforge_write.py` is a dry-run/live-write helper used to prove the command format.
- `debug/bugreport2.zip` is the full Android Bluetooth HCI bug report used to extract app writes.
- `debug/ac-infinity-research/android-bugreports/bugreport2-20260516-2247/` contains extracted bug report artifacts.
- `debug/ac-infinity-research/captures/` contains live BLE status captures.


## Plan of Work

Milestone 1: Add dependencies and isolate the protocol.

Add the runtime dependencies to `dirt-hwd`:

    uv add --package dirt-hwd bleak crccheck

Create a small protocol module, for example `apps/hwd/src/dirt_hwd/services/thermoforge_protocol.py`. Keep it pure and independent from `bleak`, settings, Telegram, and database code.

The module should define:

- constants for the service, write characteristic, and notify characteristic UUIDs;
- `ThermoForgeCommand` helpers or simple functions for `off`, `on`, and `level`;
- `build_packet(body: bytes, sequence: int) -> bytes`;
- `decode_status(frame: bytes) -> ThermoForgeStatus | None`;
- `ThermoForgeStatus(running: bool, level: int, raw: bytes | None = None)`.

Protocol tests must reproduce captured packets exactly for fixed sequence numbers and decode captured status frames for off, on, and level `4`. These tests are the guardrail that prevents future packet changes from drifting away from the proven app behavior.

Milestone 2: Add an exact-MAC BLE client.

Create a BLE client module, for example `apps/hwd/src/dirt_hwd/services/thermoforge_ble.py`.

The production client should:

- instantiate `BleakClient(config.mac)` directly;
- never import or call `BleakScanner`;
- subscribe to the notify characteristic;
- write command packets to the write characteristic;
- wait for a recent status notification after connect and after writes;
- expose methods such as `connect()`, `disconnect()`, `read_status()`, `set_power(on: bool)`, `set_level(level: int)`, and `reconcile(target: ThermoForgeTarget)`;
- raise typed local exceptions such as `ThermoForgeUnavailable` and `ThermoForgeProtocolError`.

Use dependency injection or a small backend interface so service tests can run without Bluetooth hardware. Do not put retry policy or Telegram behavior in this low-level client; the service owns operational policy.

Milestone 3: Standardize heater schedule vocabulary.

Create an Atlas migration that moves the existing Kasa breeding heat pad from heat-pad-specific vocabulary to the generic heater vocabulary.

The migration should update the existing rows rather than creating parallel rows:

- `schedule.kind`: `heat_pad` to `heater`;
- `schedule.schedule_id`: optionally `breeding-heat-pad-night` to `breeding-heater-night`;
- `capability.capability_id`: `heat_pad_power` to `power`;
- `capability.metric_name`: `heat_pad_on` to `heater_on`;
- `capability.name`: `Heat Pad Power` to `Heater Power`;
- observability documentation and app code: `heat_pad` stream to `heater`.

Keep the Kasa device ID hardware-specific, for example `kasa-heat-pad-breeding`, unless there is a separate product reason to rename it. Device IDs identify physical inventory; schedule/capability/metric names identify the operational role.

After this migration, `ScheduledKasaActuatorService` should load `schedule.kind='heater'` for Kasa heater plugs instead of `heat_pad`. Existing Kasa lights behavior should remain unchanged.

Milestone 4: Add ThermoForge configuration.

Add a `ThermoForgeConfig` slice in `apps/shared/src/dirt_shared/config.py`.

Initial environment-backed fields:

- `THERMOFORGE_ENABLED`, default false.
- `THERMOFORGE_NIGHT_LEVEL`, default `4`.
- `THERMOFORGE_POLL_INTERVAL`, default `30`.
- `THERMOFORGE_CONNECT_TIMEOUT_S`, default `15`.
- `THERMOFORGE_BACKOFF_BASE_S`, default `5`.
- `THERMOFORGE_BACKOFF_MAX_S`, default `300`.

Validate that `THERMOFORGE_NIGHT_LEVEL` is in the supported range observed for the controller. For this release, accept levels `0` through `10` unless implementation discovery proves the device constrains the set differently.

Do not include `THERMOFORGE_MAC`, `THERMOFORGE_SITE_ID`, `THERMOFORGE_TENT_ID`, or `THERMOFORGE_DEVICE_ID` as production ownership settings. Production ownership comes from `device` and `schedule` rows.

Milestone 5: Seed the first ThermoForge as a DB-known heater.

Create an Atlas migration for the first ThermoForge heater. The seed should use deterministic public IDs and upsert existing rows where possible.

Suggested initial rows:

- `device.device_id='ac-infinity-thermoforge-main'`;
- `device.name='AC Infinity ThermoForge main'`;
- `device.kind='actuator'`;
- `device.controller='ac_infinity_ble'`;
- `device.provider_uid_kind='mac'`;
- `device.provider_uid='80:B5:4E:4D:27:CA'`;
- `device.tent_id` and `device.zone_id` scoped to the current physical location;
- `capability.capability_id='power'`, `kind='actuator'`, `metric_name='heater_on'`, `unit='bool'`, `source='ac_infinity'`;
- `capability.capability_id='heat_level'`, `kind='actuator'`, `metric_name='heater_heat_level'`, `unit='level'`, `source='ac_infinity'`;
- `schedule.kind='heater'`, pointed at the ThermoForge device and its `power` capability.

Use whatever heater schedule matches the desired current deployment. If the main tent heater should mirror the dark period, seed the explicit same local window as the main tent dark period rather than deriving it at runtime from the light schedule. Future boxes, including Dirt Two, should be added by inserting another DB-known heater device plus another `heater` schedule.

Milestone 6: Implement the scheduled ThermoForge service.

Create `apps/hwd/src/dirt_hwd/services/thermoforge.py` with `ScheduledThermoForgeService`.

Each tick should:

- load enabled `schedule.kind='heater'` rows joined to enabled `Device` rows with `controller='ac_infinity_ble'`, `provider_uid_kind='mac'`, and non-null `provider_uid`;
- use `Schedule.starts_local`, `Schedule.ends_local`, and `Schedule.timezone` to derive whether the heater should be on;
- if the schedule is active, target `running=True` and `level=config.night_level`;
- if the schedule is inactive, target `running=False`;
- read live ThermoForge status over BLE;
- skip writes when live status already matches the target;
- when turning night heat on, send on first, then set level if needed;
- when turning heat off, send off;
- verify the post-write status from notifications before recording success.

Do not unconditionally send off on process shutdown. On restart, the service should reconnect and reconcile to the current schedule-derived target.

Milestone 7: Add Telegram alerting and retry/backoff.

The service should catch expected BLE failures inside its loop and keep running. It should send Telegram notifications only on transitions:

- online to offline: controller unavailable, connect failed, write failed, or protocol status timeout;
- offline to online: controller reachable again and status read succeeded;
- reconcile failure to reconcile success, if write failures are tracked separately from connection failures.

Use the same Telegram configuration fields already used elsewhere: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

Persist alert state under `var/logs/heater/state.json` keyed by `device_id` or MAC so service restarts do not spam repeated offline messages. Use exponential backoff beginning at `THERMOFORGE_BACKOFF_BASE_S` and capped at `THERMOFORGE_BACKOFF_MAX_S`, which defaults to 300 seconds.

Expected BLE failures should not escape to `supervise` as fatal task crashes. Unexpected programming errors may still surface normally.

Milestone 8: Add observability and actuator readings.

Register a `heater` stream in `apps/shared/src/dirt_shared/observability.py` with 30-day retention and document it in `docs/observability.md`. Replace the current `heat_pad` stream usage for the Kasa breeding heater with `heater`.

Log structured events:

- `status_read` with `running`, `level`, and `target`.
- `state_change` with `previous_running`, `previous_level`, `new_running`, `new_level`, `reason`, `site_id`, `tent_id`, and `device_id`.
- `command_sent` with `command`, `level` when relevant, and sequence.
- `offline` with compact exception details and retry delay.
- `recovered` with status and outage duration when available.

Record actuator readings through `ReadingsService` if the existing readings model can represent this without distorting source ownership:

- `heater_on`, unit `bool`;
- `heater_heat_level`, unit `level`;
- source should be AC Infinity or ThermoForge, not Govee or Kasa.

If this requires a new `SensorSource` enum value, read `docs/database.md` and `docs/references/atlas/INDEX.md`, add the SQLModel enum change, create an Atlas migration, and update tests. Do not fake AC Infinity readings as another provider just to avoid a migration.

Milestone 9: Wire into `dirt-hwd`.

In `apps/hwd/src/dirt_hwd/app.py`, instantiate and supervise `ScheduledThermoForgeService` only when `settings.thermoforge().enabled` is true.

Keep the service independent from humidifier and Kasa scheduling code. Shared behavior such as backoff may be copied as a tiny helper or extracted only if there is an existing local helper that fits cleanly. Do not create a generic BLE actuator framework for one device.

Milestone 10: Live rollout.

Before enabling production:

- confirm the ThermoForge DB device has `provider_uid='80:B5:4E:4D:27:CA'`;
- confirm the ThermoForge DB device has an enabled `heater` schedule;
- confirm the phone app is disconnected from the Controller 69 Pro;
- run a short manual client smoke test if useful from `debug/ac-infinity-research/thermoforge_write.py`;
- enable `THERMOFORGE_ENABLED=true`;
- restart `dirt-hwd`;
- observe `var/logs/heater/` and Telegram behavior.

Controlled live validation should cover:

- inactive heater schedule commands the heater off;
- active heater schedule commands the heater on at level `4`;
- already-correct state does not repeat writes every poll;
- blocking BLE access with the phone produces one Telegram offline alert and retries with capped backoff;
- releasing the phone connection produces one recovery alert and the heater reconciles to the current target.


## Concrete Steps

1. Add dependencies:

    uv add --package dirt-hwd bleak crccheck

2. Add `apps/hwd/src/dirt_hwd/services/thermoforge_protocol.py` and focused tests in `apps/hwd/tests/test_thermoforge_protocol.py` using captured packet examples.

3. Add `apps/hwd/src/dirt_hwd/services/thermoforge_ble.py` with exact-MAC `BleakClient` usage and fakeable tests. Confirm production code does not use `BleakScanner`.

4. Add the heater vocabulary migration:

    atlas migrate diff standardize_heater_schedules --env local

   Then manually confirm it updates the existing Kasa breeding heat pad from `heat_pad` / `heat_pad_power` / `heat_pad_on` to `heater` / `power` / `heater_on` without duplicating rows.

5. Add `ThermoForgeConfig` to `apps/shared/src/dirt_shared/config.py` with tests for defaults, enabled validation, and level range validation.

6. Add the first ThermoForge DB seed migration with an AC Infinity BLE device, `power` and `heat_level` capabilities, and an enabled `heater` schedule.

7. Add `apps/hwd/src/dirt_hwd/services/thermoforge.py` and tests in `apps/hwd/tests/test_thermoforge.py` covering schedule-derived target decisions, idempotent reconciliation, write ordering, failures, Telegram transitions, per-device backoff, and backoff cap.

8. Add `heater` observability stream/docs and update the Kasa scheduler to emit `heater` instead of `heat_pad`.

9. Add actuator readings and any required `SensorSource`/migration work. If a migration is required, read the database and Atlas docs first, then run the repo's Atlas migration workflow.

10. Wire `ScheduledThermoForgeService` into `apps/hwd/src/dirt_hwd/app.py`.

11. Run focused validation:

    uv run pytest apps/hwd/tests/test_thermoforge_protocol.py apps/hwd/tests/test_thermoforge.py -q

12. Run broader validation:

    uv run pytest apps/hwd/tests apps/shared/tests apps/tests/invariants -q
    uv run ruff check apps/hwd/src/dirt_hwd/services/thermoforge_protocol.py apps/hwd/src/dirt_hwd/services/thermoforge_ble.py apps/hwd/src/dirt_hwd/services/thermoforge.py apps/hwd/src/dirt_hwd/app.py apps/shared/src/dirt_shared/config.py apps/shared/src/dirt_shared/observability.py

13. Run live smoke tests with the phone app disconnected and record the commands, observed status, and any Telegram alerts in `Outcomes & Retrospective`.


## Validation and Acceptance

Automated acceptance:

- Protocol tests reproduce the captured app packets for off, on, level `1`, level `4`, and level `7`.
- Protocol tests decode captured off and level `4` status frames correctly.
- Migration tests or DB verification prove the existing Kasa breeding heater uses `schedule.kind='heater'`, capability `power`, and metric `heater_on`.
- Loader tests prove the ThermoForge service loads all enabled AC Infinity BLE `heater` schedules, not a single env-configured tent.
- Service tests prove active heater schedule maps to on level `4`.
- Service tests prove inactive heater schedule maps to off.
- Service tests prove no write occurs when live status already matches target.
- Service tests prove on reconciliation writes power on before setting level.
- Service tests prove connection failures send one offline Telegram alert, retry with exponential backoff, and cap retry delay at 300 seconds.
- Service tests prove recovery sends one Telegram recovery alert.
- Tests prove production BLE client construction uses the DB device MAC directly and has no scanner fallback.
- Existing hardware service tests and invariant tests still pass.

Live acceptance:

- With `THERMOFORGE_ENABLED=true`, `dirt-hwd` starts and keeps running.
- During inactive heater schedule windows, the ThermoForge is commanded off.
- During active heater schedule windows, the ThermoForge is commanded on at heat level `4`.
- Disconnecting or occupying the controller BLE connection produces a Telegram alert and retry loop instead of a service crash.
- Restoring BLE availability produces a Telegram recovery alert and schedule-correct heater state.
- `var/logs/heater/` contains enough structured data to diagnose command decisions without parsing raw BLE packets.


## Idempotence and Recovery

The service is idempotent by construction: every tick computes the desired target from current heater schedules, reads live ThermoForge status, and writes only when observed state differs.

If `dirt-hwd` restarts, the service reconnects and reconciles to the current target. It does not assume the heater state persisted correctly across the restart.

If the Controller 69 Pro is unavailable, the service records offline state, sends one Telegram alert, and retries with capped exponential backoff. When the controller is reachable again, it reads status, sends one recovery alert, resets backoff, and reconciles to target.

If a heater schedule is missing, disabled, malformed, or no longer points at an enabled AC Infinity BLE device, the service skips that target and logs the reason. It must not invent a schedule from the device's tent.

If a migration is added for new reading source values or catalog rows, make it repeatable through normal Atlas migration application. Seed rows should use deterministic IDs and upsert-style SQL where appropriate.

Rollback is straightforward:

- set `THERMOFORGE_ENABLED=false`;
- restart `dirt-hwd`;
- leave protocol tests and debug artifacts in place unless the feature is abandoned;
- manually control the ThermoForge through the AC Infinity app until the service is re-enabled.


## Artifacts and Notes

Do not import files from `debug/` into production code. They are research artifacts only.

Known useful artifacts:

- `debug/ac-infinity-research/thermoforge_write.py`
- `debug/ac-infinity-research/ble_probe.py`
- `debug/bugreport2.zip`
- `debug/ac-infinity-research/android-bugreports/bugreport2-20260516-2247/`
- `debug/ac-infinity-research/captures/`

When updating this plan during implementation, add exact filenames for any status fixtures copied into tests. If raw BLE frames are used as fixtures, keep them small and inline in tests unless a dedicated fixture file is clearer.


## Interfaces and Dependencies

New app dependencies:

- `bleak` for BLE connections.
- `crccheck` for CRC-16/CCITT-FALSE packet checksums.

New or changed configuration:

- `THERMOFORGE_ENABLED`
- `THERMOFORGE_NIGHT_LEVEL`
- `THERMOFORGE_POLL_INTERVAL`
- `THERMOFORGE_CONNECT_TIMEOUT_S`
- `THERMOFORGE_BACKOFF_BASE_S`
- `THERMOFORGE_BACKOFF_MAX_S`

New app modules:

- `apps/hwd/src/dirt_hwd/services/thermoforge_protocol.py`
- `apps/hwd/src/dirt_hwd/services/thermoforge_ble.py`
- `apps/hwd/src/dirt_hwd/services/thermoforge.py`

Likely changed existing files:

- `apps/hwd/src/dirt_hwd/app.py`
- `apps/hwd/pyproject.toml`
- `uv.lock`
- `apps/shared/src/dirt_shared/config.py`
- `apps/shared/src/dirt_shared/observability.py`
- `docs/observability.md`
- possibly `apps/shared/src/dirt_shared/models/enums.py`
- possibly `migrations/*.sql` and `migrations/atlas.sum`

Runtime external interfaces:

- BLE connection to Controller 69 Pro MAC values stored in DB `device.provider_uid`.
- Telegram Bot API through existing `TelegramClient`.
- Local database through DB-known `Device`, `Capability`, `Schedule`, and `ReadingsService`.


## Revision Notes

- 2026-05-16: Initial plan written from BLE reverse-engineering results and user-confirmed actuator policy.
- 2026-05-16: Revised plan to use DB-known `heater` schedules, generic `power` / `heat_level` capabilities, `heater_on` / `heater_heat_level` metrics, and service-configured ThermoForge level `4`.
