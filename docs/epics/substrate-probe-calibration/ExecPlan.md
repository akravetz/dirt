# Local substrate probe calibration bench

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the operator can calibrate the three DFRobot SEN0604 RS485/TDS substrate probes against a dry 70/30 coco/perlite anchor and a wet field-capacity anchor from a laptop on the same LAN. The tool is local-only and intended for bench calibration before the next 4x4 drain-to-waste setup. It does not change the hosted dashboard and does not store calibration data in Postgres.

The immediate user-visible outcome is a local web UI bound to `0.0.0.0` that shows all three probes live, lets the operator identify a physical probe by pulling it from a pot and watching its moisture drop, captures 60-second dry or wet-capacity windows for any selected probe, shows the mean/min/max/standard deviation for moisture, EC, pH, and temperature, and lets the operator accept or reject the capture by judgment. Accepted captures are persisted under `var/`, grouped into immutable completed calibration sessions, and summarized into one formula per physical probe:

    normalized_moisture_pct = 100 * (raw_moisture_pct - dry_anchor_mean) / (wet_anchor_mean - dry_anchor_mean)

The calibration is relative, not absolute. It is meant to make Probe 1, Probe 2, and Probe 3 consistent with each other for future dryback comparisons. It is not meant to prove true volumetric water content. EC and pH readings are captured as context; EC is recorded as probe-native substrate EC and pH is diagnostic only in this first version.

The second user-visible outcome is higher-resolution local sampling from the RS485 substrate controller. Normal ingest to Dirt remains every 30 seconds, but when the local calibration UI enables calibration mode, the controller polls the three probes faster, keeps an in-memory ring buffer, and exposes recent decoded samples through a LAN endpoint. This gives a 60-second capture enough samples for useful noise statistics without flooding Postgres.

## Progress

- [x] (2026-07-04) Discussed the target calibration workflow with the operator: local-only web UI, laptop on LAN, all three probes shown live, ad hoc capture, 60-second capture window, human accept/reject, accepted captures only, file storage under `var/`, physical probe labels based on Modbus address, dry and wet-capacity anchors only for v1.
- [x] (2026-07-04) Confirmed current firmware cadence: `POST_INTERVAL_MS=30000`, `POLL_INTERVAL_MS=POST_INTERVAL_MS`, so a 60-second capture from `/status` alone only gets about two fresh values.
- [x] (2026-07-04) Decided to split controller measurement cadence from Dirt ingest cadence by adding calibration mode and a sample ring buffer.
- [x] (2026-07-04) Authored this ExecPlan.
- [x] (2026-07-04 05:42Z) Implemented Milestone 1: firmware high-rate calibration sampling endpoints. Validation passed for `pio run -e plant-a-substrate`, `pio run -e plant-a-substrate-ota`, and `git diff --check` on the firmware files.
- [x] (2026-07-04 06:01Z) Implemented Milestone 2: local file-backed calibration domain models and service. Added the separate `dirt_hwd.tools.substrate_calibration` CLI/app, strict local/persisted DTOs, controller adapter validation, atomic JSON store, capture preview/accept/complete APIs, calibration summaries, and focused tests.
- [ ] Implement Milestone 3: local LAN web app and UI flow.
- [ ] Implement Milestone 4: tests, docs, and operator validation.

## Surprises & Discoveries

- Observation: The RS485 substrate node currently samples at the same cadence as it ingests.
  Evidence: `firmware/rs485_substrate_node/platformio.ini` sets `POST_INTERVAL_MS=30000`, `firmware/rs485_substrate_node/src/main.cpp` defines `POLL_INTERVAL_MS = POST_INTERVAL_MS`, and `poll_sensor_if_due()` uses that interval for all slots.

- Observation: The live controller already has the three-probe logical shape needed for calibration.
  Evidence: `GET http://plant-a-substrate-node.local/status` reports three enabled slots: Plant A at Modbus `0x02`, Plant D at `0x03`, and Plant C at `0x04`, all posting `soil_moisture_pct`, `substrate_temp_c`, `substrate_ec_us_cm`, and `substrate_ph`.

- Observation: The calibration UI should not depend on Postgres for live data.
  Evidence: The controller `/status` response contains all three probes with `age_ms`, raw Modbus frame hex, decoded values, counters, and health state. Reading the controller directly makes probe identification immediate and avoids waiting for Dirt ingest.

- Observation: Milestone 1 is build-validated but not hardware-flashed yet.
  Evidence: Both PlatformIO firmware environments build successfully after the calibration endpoint changes, but `/calibration/start`, `/samples`, `/calibration/stop`, and observed 30-second Dirt ingest cadence have not been curl-validated on the physical controller.

- Observation: Static session API paths must be registered before the dynamic session id route.
  Evidence: `GET /api/sessions/latest-completed` would otherwise be interpreted as `session_id="latest-completed"`. The local calibration app registers the latest-completed route before `GET /api/sessions/{session_id}`, and `apps/hwd/tests/test_substrate_calibration.py` covers that ordering.

## Decision Log

- Decision: Build a local-only calibration utility, not a hosted dashboard feature.
  Rationale: This is a bench workflow for one operator on the grow LAN. It needs fast iteration, raw operational data, and file-backed calibration artifacts under `var/`, not a synced cloud UX or generated hosted browser contract.
  Date/Author: 2026-07-04 / Codex

- Decision: Place the local calibration web app inside the `dirt-hwd` workspace package as a separate tool entry point, not inside the production `dirt-hwd` daemon.
  Rationale: `dirt-hwd` already owns local hardware-facing FastAPI dependencies and is the right package boundary for a local hardware bench tool. Keeping the app as `python -m dirt_hwd.tools.substrate_calibration` avoids adding a new workspace service and avoids changing the long-running production daemon on port 8000.
  Date/Author: 2026-07-04 / Codex

- Decision: Store calibration sessions as JSON files under `var/substrate-calibration/`, not in Postgres.
  Rationale: The operator expects to iterate on the workflow, and this v1 calibration is strictly a bench utility. File storage keeps the blast radius low and avoids premature schema migration work. If formulas later drive automation, a later plan can promote the active calibration artifact into a source-owned model.
  Date/Author: 2026-07-04 / Codex

- Decision: Label physical probes by Modbus address: Probe 1 is `0x02`, Probe 2 is `0x03`, and Probe 3 is `0x04`.
  Rationale: The current grow labels Plant A/D/C are temporary placements. The durable bench identity for calibration should follow the physical sensor address so probes can move to new sentinel plants without losing calibration identity.
  Date/Author: 2026-07-04 / Codex

- Decision: Split firmware measurement cadence from ingest cadence.
  Rationale: Normal Dirt ingest should stay at 30 seconds. Calibration needs more granular local samples for a 60-second capture. A controller-local ring buffer and `/samples` endpoint provide that data without flooding Postgres or changing the sensor ingest API.
  Date/Author: 2026-07-04 / Codex

- Decision: Use calibration mode at a target 2-second measurement interval, with automatic timeout and safe fallback behavior.
  Rationale: At 2 seconds, a 60-second capture can collect roughly 30 samples per probe when the bus is healthy. If probe timeouts make the cycle slower, the firmware should skip overlapping cycles and expose actual sample counts rather than pretending the target cadence was met.
  Date/Author: 2026-07-04 / Codex

- Decision: Persist only accepted captures, but store each accepted capture's sample list and computed statistics.
  Rationale: The operator wants human judgment for acceptance and does not need rejected captures in the artifact. Keeping accepted sample lists makes summaries reproducible and lets later code recompute means, standard deviations, spans, and formulas if the summary logic changes.
  Date/Author: 2026-07-04 / Codex

- Decision: Treat pH as diagnostic context and EC as probe-native substrate EC for v1.
  Rationale: The dryback calibration only needs dry and wet moisture anchors. Known input EC and pH during wet-capacity captures are useful context, but the first UI should not claim a robust EC or pH correction model.
  Date/Author: 2026-07-04 / Codex

## Outcomes & Retrospective

Milestone 1 added separate firmware measurement and ingest cadences, calibration mode with bounded auto-expiry, fixed per-slot sample rings, and LAN endpoints for starting/stopping calibration mode and reading recent samples. Normal Dirt ingest remains gated by the 30-second ingest interval while calibration mode can poll probes at a 2-second default interval. Validation passed for `pio run -e plant-a-substrate`, `pio run -e plant-a-substrate-ota`, and `git diff --check -- firmware/rs485_substrate_node/src/main.cpp firmware/rs485_substrate_node/platformio.ini`.

Remaining hardware validation for Milestone 1: flash the controller through the approved firmware workflow, then curl `/health`, `/status`, `/calibration/start`, `/samples`, and `/calibration/stop`, and observe that Dirt ingest stays near the normal 30-second cadence during calibration mode.

Milestone 2 added the local calibration backend under `apps/hwd/src/dirt_hwd/tools/substrate_calibration/`. The tool now has a separate CLI entry point, local FastAPI app, controller adapter for `/status`, `/samples`, and calibration-mode commands, Pydantic DTOs for local API and persisted JSON sessions, atomic file-backed storage under `Settings.data_dir / "substrate-calibration"`, capture preview/accept/remove/complete routes, immutable completed sessions, and per-probe formula summaries with missing-anchor, low-sample, invalid-span, and inverted-anchor warnings. Validation passed for `uv run --package dirt-hwd python -m dirt_hwd.tools.substrate_calibration --help`, `uv run pytest apps/tests/invariants/test_no_concrete_clock_in_production.py::test_no_concrete_clock_in_production -q`, `uv run pytest apps/hwd/tests/test_substrate_calibration.py -q`, `uv run pytest apps/hwd/tests -q`, `uv run ruff check apps/hwd/src/dirt_hwd/tools/substrate_calibration apps/hwd/tests/test_substrate_calibration.py`, and `uv run ruff format --check apps/hwd/src/dirt_hwd/tools/substrate_calibration apps/hwd/tests/test_substrate_calibration.py`.

## Context and Orientation

Dirt's current RS485 substrate controller is the Seeed XIAO ESP32-C3 firmware in `firmware/rs485_substrate_node/src/main.cpp`. It runs on the physical device `plant-a-substrate-node` at `plant-a-substrate-node.local`, reads DFRobot SEN0604 probes over RS485/Modbus, exposes `GET /health` and `GET /status` on port 80, and posts decoded metrics into Dirt through the existing hardware ingest boundary.

The current logical slot table in firmware maps:

- Probe at Modbus `0x02` to `plant-a-substrate-node`.
- Probe at Modbus `0x03` to `plant-d-substrate-node`.
- Probe at Modbus `0x04` to `plant-c-substrate-node`.

For this calibration feature, ignore the plant names when defining physical probe identity. Use:

- Probe 1: Modbus `0x02`.
- Probe 2: Modbus `0x03`.
- Probe 3: Modbus `0x04`.

Current firmware emits four decoded values per probe:

- `soil_moisture_pct`, direct percent reported by the probe. This is the raw moisture input to the relative calibration formula, even though the metric name includes `pct`.
- `substrate_temp_c`, probe temperature in deg C.
- `substrate_ec_us_cm`, probe-native electrical conductivity in `us/cm`.
- `substrate_ph`, probe pH value.

Normal controller polling and ingest currently use the same 30-second interval. A 60-second UI capture from the current `/status` shape would only collect about two fresh values per probe. This plan adds high-rate calibration sampling to the controller while keeping normal ingest unchanged.

The local calibration app should live under `apps/hwd/src/dirt_hwd/tools/substrate_calibration/`. It should run as a foreground local process, bind to `0.0.0.0` for LAN laptop access, and serve both a small browser UI and a small local JSON API. It should not be imported by the production `dirt-hwd` daemon unless shared internal functions are genuinely useful.

Use Pydantic DTOs for the local app's HTTP request and response bodies and for persisted JSON session files where code later depends on the shape. Use `ConfigDict(extra="forbid")` for owned local API payloads. The firmware endpoints are embedded C++ JSON produced by the controller; validate those responses in the Python adapter before the rest of the calibration app uses them.

The calibration artifact root is `var/substrate-calibration/`, or `$DIRT_DATA_DIR/substrate-calibration/` if `DIRT_DATA_DIR` is set. Suggested layout:

    var/substrate-calibration/
      sessions/
        20260704-153012-bench.json
      latest-completed.json

A session starts as a draft file or in-memory draft, then becomes immutable after completion. Completed sessions should not be edited in place. To correct a bad calibration, start a new session and make it the latest completed artifact.

## Plan of Work

Milestone 1: Add controller high-rate calibration sampling.

Change `firmware/rs485_substrate_node/src/main.cpp` so normal ingest remains every 30 seconds but measurement can run faster during calibration mode. Introduce separate concepts:

- `INGEST_INTERVAL_MS`, default 30000.
- `NORMAL_MEASUREMENT_INTERVAL_MS`, default 30000.
- `CALIBRATION_MEASUREMENT_INTERVAL_MS`, default 2000.
- Calibration mode state with `active`, `started_ms`, `expires_ms`, `interval_ms`, and counters.

Keep the existing normal `/status` and `/health` behavior. Add an in-memory ring buffer per probe slot. Each sample should include at minimum:

- Controller monotonic timestamp in milliseconds.
- Slot/probe identity.
- Modbus address.
- Decoded moisture, temp, EC, and pH.
- Raw Modbus frame hex.
- Modbus status.
- Sequence number or enough timestamp data for the local app to deduplicate samples.

The ring buffer should hold at least 5 minutes of samples at the calibration cadence. At 2 seconds and three probes, this is about 150 samples per probe. Keep the structure bounded and static; do not use heap-heavy dynamic containers on the ESP32 if a fixed array is straightforward.

Add these LAN endpoints:

- `POST /calibration/start?duration_s=900&interval_ms=2000`
- `POST /calibration/stop`
- `GET /samples?window_s=120`

If Arduino `WebServer` request-body handling makes query parameters simpler and safer, keep these endpoints query-string based. They are local LAN control endpoints and should never write sensor registers. `POST /calibration/start` should validate requested duration and interval against safe bounds, for example interval `1000-30000` ms and duration `1-3600` seconds. Calibration mode should automatically expire even if the UI disappears.

`GET /samples` should return only recent decoded samples from the ring buffers, plus controller metadata. Keep JSON size bounded by `window_s` validation. A useful shape is:

    {
      "controller": {
        "device_id": "plant-a-substrate-node",
        "firmware_version": "0.1.0-rs485-substrate",
        "calibration_mode": {"active": true, "interval_ms": 2000}
      },
      "slots": [
        {
          "probe_id": 1,
          "device_id": "plant-a-substrate-node",
          "modbus_address": "0x02",
          "samples": [
            {
              "seq": 123,
              "read_ms": 456789,
              "soil_moisture_pct": 24.5,
              "substrate_temp_c": 20.2,
              "substrate_ec_us_cm": 126,
              "substrate_ph": 4.9,
              "raw_modbus_frame_hex": "02030800F500CA007E00310640"
            }
          ]
        }
      ]
    }

Do not change `POST /api/ingest/sensors`. During calibration mode, continue posting to Dirt only on the normal ingest interval. Do not post every high-rate sample.

Milestone 2: Add file-backed calibration models and service.

Add a local calibration package under `apps/hwd/src/dirt_hwd/tools/substrate_calibration/`. Keep the public entry point separate from `dirt_hwd.app:create_app`. Suggested modules:

- `__main__.py`: CLI parser and uvicorn runner.
- `app.py`: `create_app()` for the local FastAPI app.
- `controller.py`: async HTTP client for controller `/status`, `/samples`, and calibration mode endpoints.
- `schemas.py`: Pydantic DTOs for local API requests/responses and persisted session files.
- `store.py`: file-backed session persistence under `var/substrate-calibration/`.
- `calibration.py`: pure functions for stats, anchors, and formula summaries.
- `static/`: small local HTML/CSS/JS assets, or an inline Starlette static route if simpler.

The CLI should be:

    uv run --package dirt-hwd python -m dirt_hwd.tools.substrate_calibration --host 0.0.0.0 --port 8097 --controller-url http://plant-a-substrate-node.local

Default host may be `127.0.0.1` for safety, but the documented operator command must bind to `0.0.0.0`. The app should print the local URL and the LAN-bound URL if it can infer one.

Persist accepted captures in JSON files. Model these concepts:

- `CalibrationSession`: id, created time, status `draft` or `completed`, controller URL, probe map, wet reference values, accepted captures, completion summary.
- `ProbeIdentity`: probe id 1/2/3, Modbus address `0x02`/`0x03`/`0x04`, current controller slot device id.
- `Capture`: id, anchor type `dry` or `wet_capacity`, probe id, placement label or note, duration seconds, started/ended timestamps, optional wet reference override, sample list, and computed stats.
- `CaptureStats`: count, mean, min, max, standard deviation for moisture, EC, pH, and temperature where present.
- `CalibrationSummary`: per-probe dry anchor mean, wet anchor mean, span, capture counts, formula, warnings, and whether the probe has enough anchors to compute a formula.

Wet reference fields are session-level:

- `input_ec_ms_cm`
- `input_ph`

Allow optional per-capture overrides, but do not require them. The app should record probe temperature from the samples and should not ask the operator to enter solution temperature in v1.

Completion is allowed with fewer or more than three captures. Completion should generate formulas only for probes that have at least one accepted dry capture and at least one accepted wet-capacity capture. Missing anchors should produce warnings in the summary table but should not block saving the session if the operator chooses to complete it.

Keep completed sessions immutable. The simplest rule is: `complete_session()` writes a completed session file with the final summary and refuses future capture appends to that session id. If a draft needs correction before completion, accepted captures may be removed only while the session is draft. If the operator wants stricter append-only draft behavior, add that later.

Milestone 3: Build the local browser UI.

The UI should be a practical bench tool, not a polished dashboard. Use plain HTML/CSS/JavaScript served by the local FastAPI app unless a later discovery shows a strong reason to involve Vite. The page should work from a laptop browser pointed at `http://<host>:8097/`.

First screen requirements:

- Controller connection state.
- Button to enable or renew controller calibration mode.
- Three live probe cards for Probe 1, Probe 2, and Probe 3.
- Each card shows Modbus address, current slot/device id, sample age, raw moisture, EC, pH, temperature, and latest raw frame or link to details.
- Each card includes a small live moisture trace using the high-rate `/samples` data so pulling one physical probe from a pot makes its card obvious.
- Each card shows a visible noise indicator over the recent window, such as sample count, moisture standard deviation, and min/max.

Capture flow requirements:

- User selects anchor type `dry` or `wet_capacity`.
- For wet-capacity capture, session-level input EC and input pH are visible and editable before capture. Per-capture override is optional and should be tucked behind an advanced/details control.
- User clicks Start Capture on any probe card.
- The server captures 60 seconds of high-rate samples for that probe. It should poll the controller `/samples` endpoint and deduplicate by sequence/read timestamp.
- During capture, the UI shows progress, current sample count, and live stats.
- At the end, the UI presents the capture stats and asks the user to Accept or Reject.
- Accept persists the capture to the draft session. Reject discards it.

Session summary requirements:

- Show accepted dry and wet captures grouped by probe.
- Show per-probe anchor means, span, and formula if available.
- Show warnings when span is too small, sample count is low, dry mean is not below wet mean, or a probe lacks either anchor.
- Show a copyable summary table in Markdown and/or CSV.
- Provide a button to complete the session. Completion writes the completed session artifact and updates `latest-completed.json`.

The UI does not need user authentication in v1. It is local LAN only. It must not expose any endpoint that changes irrigation or writes Modbus sensor calibration registers.

Milestone 4: Tests, documentation, and operator validation.

Add focused Python tests for:

- Formula computation with multiple accepted dry/wet captures per probe.
- Completion with missing anchors produces warnings and only computes formulas for complete probes.
- Completed sessions reject further capture appends.
- Store writes under a temporary directory and does not touch real `var/` in tests.
- Controller adapter validates firmware `/samples` payloads and rejects malformed owned-protocol shapes before they reach calibration code.
- Local FastAPI API returns the expected response models for live status, capture preview, accept capture, complete session, and summary.

Add firmware validation steps:

- Build `firmware/rs485_substrate_node` USB and OTA environments.
- Confirm `/calibration/start`, `/samples`, and `/calibration/stop` work with `curl`.
- Confirm normal `/status` and `/health` still work.
- Confirm normal Dirt ingest remains about every 30 seconds during calibration mode.

Update docs:

- Add the local calibration command to `docs/commands.md` under a new RS485 substrate calibration subsection.
- Update `wiki/hardware/rs485-substrate-sensors.md` to document calibration mode endpoints, probe id mapping, and the fact that high-rate samples are local-only and not ingested.
- Update `wiki/hardware/rs485-substrate-sensor-calibration.md` with the operator workflow: dry 70/30 coco/perlite captures, wet field-capacity known-feed captures, accepted captures, formula summary, and pH/EC limitations.

## Concrete Steps

Start from the repo root and inspect the current state:

    cd /home/akcom/code/dirt
    git status --short
    sed -n '1,220p' docs/commands.md
    sed -n '1,240p' docs/rules/simple-clean-architecture.md
    sed -n '1,260p' docs/rules/boundary-contracts.md
    sed -n '1,220p' firmware/rs485_substrate_node/src/main.cpp
    curl -fsS http://plant-a-substrate-node.local/status | jq .

Implement and build firmware:

    cd /home/akcom/code/dirt/firmware/rs485_substrate_node
    pio run -e plant-a-substrate
    pio run -e plant-a-substrate-ota

After flashing by the approved firmware workflow, validate controller endpoints:

    curl -fsS http://plant-a-substrate-node.local/health
    curl -fsS http://plant-a-substrate-node.local/status | jq .
    curl -fsS -X POST 'http://plant-a-substrate-node.local/calibration/start?duration_s=900&interval_ms=2000' | jq .
    sleep 10
    curl -fsS 'http://plant-a-substrate-node.local/samples?window_s=10' | jq .
    curl -fsS -X POST 'http://plant-a-substrate-node.local/calibration/stop' | jq .

Run local app tests:

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests -q

Run the local calibration UI:

    cd /home/akcom/code/dirt
    uv run --package dirt-hwd python -m dirt_hwd.tools.substrate_calibration --host 0.0.0.0 --port 8097 --controller-url http://plant-a-substrate-node.local

Open the printed LAN URL from a laptop on the same network. For agent/browser validation on the local machine, use `agent-browser`, not raw Playwright:

    agent-browser open http://127.0.0.1:8097/

Before commit, run:

    make fix
    uv run pytest -q
    cd firmware/rs485_substrate_node && pio run -e plant-a-substrate
    cd /home/akcom/code/dirt && uv run scripts/lint.py

## Validation and Acceptance

The feature is accepted when all of these are true:

- The RS485 controller still returns healthy `/health` and `/status` responses after the firmware change.
- `POST /calibration/start?duration_s=900&interval_ms=2000` enables calibration mode without changing sensor Modbus registers.
- `GET /samples?window_s=60` returns multiple recent decoded samples per probe while calibration mode is active. A 60-second window should usually contain substantially more than two samples per probe when the bus is healthy.
- Normal Dirt ingest remains at the 30-second cadence and does not receive every high-rate calibration sample.
- The local calibration server starts with the documented `uv run --package dirt-hwd ... --host 0.0.0.0` command and can be reached from the host.
- The UI shows all three probes live with raw moisture, EC, pH, temperature, sample age, and noise stats.
- Pulling one probe from its current pot visibly changes only that probe's live moisture trace, making physical identification possible.
- A 60-second dry capture can be run for any selected probe, reviewed, accepted, and persisted.
- A 60-second wet-capacity capture can be run with session-level input EC/pH, reviewed, accepted, and persisted.
- Completion produces a summary table with dry anchor mean, wet anchor mean, span, and formula per probe where both anchors exist.
- Completed session JSON is written under `var/substrate-calibration/sessions/`, and `latest-completed.json` points to the completed artifact.
- Tests cover the formula, session immutability, store behavior under `tmp_path`, and local API response contracts.
- Documentation tells a later operator how to run the tool and explains that the output is a relative dryback calibration, not a true VWC calibration.

## Idempotence and Recovery

Firmware calibration mode is safe to start repeatedly. Starting calibration mode should renew the timeout and update the interval within allowed bounds. Stopping calibration mode should be safe even when it is not active. The ring buffer is volatile; power-cycling the controller clears it and does not affect accepted calibration artifacts.

The local calibration server is safe to restart. Draft sessions on disk should remain readable after restart. If a draft file is partially written due to process death, the store should either use atomic write-and-rename or reject the corrupt draft with a clear error. Completed sessions should be immutable. To correct a completed calibration, create a new session; do not edit the old completed file.

All tests that write files must use `tmp_path` and must not write to the real `var/` directory. The production local tool writes only under `var/substrate-calibration/` or the configured `DIRT_DATA_DIR`.

If the controller `/samples` endpoint is unavailable because firmware has not been flashed yet, the local UI may show a clear "high-rate firmware required" message. Do not silently fall back to two-sample `/status` captures without warning. A temporary fallback can exist only as an explicit diagnostic mode.

If the RS485 bus becomes unreliable during calibration mode, lower the interval through the UI or endpoint, for example from 2000 ms to 5000 ms. The UI should display actual sample counts and should let the operator reject thin/noisy captures.

If the local app port is already in use, rerun with another port, for example `--port 8098`.

## Artifacts and Notes

Current live context captured before this plan:

- Controller: `plant-a-substrate-node.local`, observed IP `192.168.1.40`.
- Firmware version: `0.1.0-rs485-substrate`.
- Current status endpoint reports three enabled slots and no Modbus failures.
- Current firmware cadence is 30 seconds because `POLL_INTERVAL_MS = POST_INTERVAL_MS` and the build flag sets `POST_INTERVAL_MS=30000`.

Expected completed session summary should be easy to copy. Example shape:

    Probe 1 / 0x02:
      dry_anchor_mean = 2.1
      wet_anchor_mean = 39.8
      span = 37.7
      formula = 100 * (raw_moisture_pct - 2.1) / 37.7

    Probe 2 / 0x03:
      dry_anchor_mean = 1.9
      wet_anchor_mean = 41.2
      span = 39.3
      formula = 100 * (raw_moisture_pct - 1.9) / 39.3

    Probe 3 / 0x04:
      dry_anchor_mean = 2.4
      wet_anchor_mean = 38.6
      span = 36.2
      formula = 100 * (raw_moisture_pct - 2.4) / 36.2

Do not treat these example numbers as real calibration values.

## Interfaces and Dependencies

Firmware interfaces to add or update:

- `GET /health`: existing endpoint, must keep working.
- `GET /status`: existing endpoint, must keep working and may include calibration mode summary.
- `POST /calibration/start?duration_s=<seconds>&interval_ms=<milliseconds>`: local state-change endpoint that enables high-rate sampling for a bounded duration.
- `POST /calibration/stop`: local state-change endpoint that disables high-rate sampling.
- `GET /samples?window_s=<seconds>`: local read endpoint returning bounded recent decoded samples from all enabled probe slots.

Local app command:

- `uv run --package dirt-hwd python -m dirt_hwd.tools.substrate_calibration --host 0.0.0.0 --port 8097 --controller-url http://plant-a-substrate-node.local`

Local app modules:

- `apps/hwd/src/dirt_hwd/tools/substrate_calibration/__main__.py`
- `apps/hwd/src/dirt_hwd/tools/substrate_calibration/app.py`
- `apps/hwd/src/dirt_hwd/tools/substrate_calibration/controller.py`
- `apps/hwd/src/dirt_hwd/tools/substrate_calibration/schemas.py`
- `apps/hwd/src/dirt_hwd/tools/substrate_calibration/store.py`
- `apps/hwd/src/dirt_hwd/tools/substrate_calibration/calibration.py`
- `apps/hwd/src/dirt_hwd/tools/substrate_calibration/static/`

Local app dependencies should come from existing `dirt-hwd` dependencies: FastAPI, uvicorn, Pydantic, and httpx. Do not add a new frontend build tool for v1.

File artifacts:

- `var/substrate-calibration/sessions/<session-id>.json`
- `var/substrate-calibration/latest-completed.json`

Documentation to update:

- `docs/commands.md`
- `wiki/hardware/rs485-substrate-sensors.md`
- `wiki/hardware/rs485-substrate-sensor-calibration.md`

## Revision Notes

- 2026-07-04: Initial ExecPlan created from operator discussion. Scope is local-only calibration UI, file-backed sessions under `var/`, physical probe labels by Modbus address, dry and wet-capacity anchors only, high-rate controller sampling in calibration mode, and no hosted dashboard work.
