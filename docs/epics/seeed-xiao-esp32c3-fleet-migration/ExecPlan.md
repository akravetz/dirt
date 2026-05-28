# Seeed XIAO ESP32-C3 Fleet Migration

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

The grow-monitoring ESP32 fleet currently runs on ESP32-C3 SuperMini clone boards. A shipment of Seeed Studio XIAO ESP32-C3 boards has arrived, and the fleet should be swapped to the XIAO boards without changing device identities, database contracts, dashboard behavior, or the host ingest API.

After this migration, each physical node can be rebuilt on the XIAO board, flashed with the existing per-device firmware identity, and observed posting the same metrics as before. The operator should be able to see the migration working through serial boot logs, mDNS/OTA reachability, `/api/ingest/sensors` posts, current `device.last_seen` rows, and normal dashboard device freshness.

The design goal is a direct cutover: use the XIAO board definition, keep the existing chip-GPIO pin contract if canary tests pass, update wiring docs to the XIAO silkscreen labels, and avoid compatibility wrappers or parallel firmware trees.


## Progress

- [x] (2026-05-27) Read `docs/commands.md`, `docs/rules/simple-clean-architecture.md`, and `.agents/PLANS.md`.
- [x] (2026-05-27) Searched the internet for Seeed Studio XIAO ESP32-C3 and ESP32-C3 SuperMini hardware facts.
- [x] (2026-05-27) Inspected current firmware projects and pin usage.
- [x] (2026-05-27) Confirmed PlatformIO knows the `seeed_xiao_esp32c3` board ID.
- [x] (2026-05-27) Confirmed the currently attached ESP32-C3 USB devices enumerate as Espressif USB JTAG/serial debug units on `/dev/ttyACM0` and `/dev/ttyACM1`.
- [x] (2026-05-27) Built the current SuperMini/DevKitM firmware profiles `plant-a`, `reservoir`, and `fan` successfully as a baseline.
- [x] (2026-05-27) Wrote this epic and ExecPlan.
- [x] (2026-05-27) Differentiated the plugged-in XIAO from the already-flashed Dirt ESP32-C3 by reading flash contents: `/dev/ttyACM0` / MAC `e8:f6:0a:16:9f:fc` contained a XIAO Arduino/factory image; `/dev/ttyACM1` / MAC `ac:a7:04:d5:31:e0` contained Dirt reservoir firmware strings.
- [x] (2026-05-27) Converted `firmware/reservoir_node` into a XIAO reservoir canary build using `board = seeed_xiao_esp32c3`, `FIRMWARE_VERSION="0.1.3-xiao-canary"`, device ID `reservoir-xiao`, hostname `dirt-reservoir-xiao`, and OTA target `dirt-reservoir-xiao.local`.
- [x] (2026-05-27) Built and USB-flashed the XIAO reservoir canary to `/dev/ttyACM0`; read back flash from `0x10000` and confirmed `reservoir-xiao`, `dirt-reservoir-xiao`, and `0.1.3-xiao-canary` are present.
- [ ] Implement XIAO board-target cutover in the remaining production firmware.
- [ ] Validate a USB-connected XIAO canary.
- [ ] Wire the XIAO reservoir canary to ADS1115/SEN0262/probe hardware and confirm I2C detection plus live reservoir readings.
- [ ] Migrate deployed nodes one at a time.
- [ ] Update wiki hardware pages after rollout.


## Surprises & Discoveries

- Observation: The XIAO and current PlatformIO DevKitM target are the same ESP32-C3 class in memory and CPU terms.
  Evidence: PlatformIO reports both `seeed_xiao_esp32c3` and `esp32-c3-devkitm-1` as ESP32C3, 160 MHz, 4 MB flash, 320 KB RAM.

- Observation: The attached XIAO board cannot be distinguished from other ESP32-C3 USB-CDC devices by VID/PID alone on this host.
  Evidence: `pio device list` showed `/dev/ttyACM0` and `/dev/ttyACM1` with USB `VID:PID=303A:1001`, both described as `USB JTAG/serial debug unit`.

- Observation: Flash contents can distinguish the XIAO canary from an already-flashed Dirt board when USB metadata is ambiguous.
  Evidence: Reading flash from `/dev/ttyACM0` / MAC `e8:f6:0a:16:9f:fc` showed an Arduino XIAO build string, while `/dev/ttyACM1` / MAC `ac:a7:04:d5:31:e0` contained `reservoir-node`, `dirt-reservoir`, and reservoir metric payload strings.

- Observation: The XIAO board was not blank from the factory, even though it was not flashed with Dirt firmware.
  Evidence: Flash offset `0x0` on `/dev/ttyACM0` contained a valid ESP image header and `esp32:esp32:XIAO_ESP32C3` strings before the canary flash.

- Observation: Non-interactive `pio device monitor` fails without a TTY, and a TTY-backed monitor attached after upload did not capture the early boot banner.
  Evidence: The first monitor attempt failed with `termios.error: (25, 'Inappropriate ioctl for device')`; the TTY-backed monitor opened `/dev/ttyACM0` and RTS toggling worked, but no boot text was captured. Read-back from flash confirmed the canary identity instead.

- Observation: PlatformIO's installed `seeed_xiao_esp32c3.json` board manifest accepts both Seeed's native `0x2886:0x0046` hardware ID and Espressif's ROM USB/JTAG `0x303a:0x1001` ID.
  Evidence: `~/.platformio/platforms/espressif32/boards/seeed_xiao_esp32c3.json` lists both IDs under `build.hwids`.

- Observation: The current firmware pin contract is small and explicit.
  Evidence: `firmware/plant_node/src/main.cpp` uses GPIO3 / ADC1_CH3 for soil moisture; `firmware/reservoir_node/src/main.cpp` uses GPIO4/GPIO5 for I2C; `firmware/fan_controller/src/main.cpp` uses GPIO4/GPIO5 for SHT45 I2C and GPIO6/GPIO7 for fan MOSFET gates.

- Observation: The installed `pio run` command does not support an inline `--project-option` override in this environment.
  Evidence: `pio run -e plant-a --project-option=...` exited with `No such option: --project-option`. Implementers should edit `platformio.ini` directly or use a temporary `--project-conf` file in `debug/` for probes.


## Decision Log

- Decision: Use `seeed_xiao_esp32c3` as the canonical board target for all active ESP32-C3 firmware projects.
  Rationale: The fleet is physically moving to Seeed XIAO boards. PlatformIO has a dedicated XIAO board manifest that sets the XIAO Arduino variant and board macro, so continuing to build as generic DevKitM would preserve a misleading source contract.
  Date/Author: 2026-05-27 / Codex

- Decision: Keep the existing chip-GPIO assignments for the first canary: GPIO3 for plant ADC, GPIO4/GPIO5 for I2C, GPIO6/GPIO7 for fan gates.
  Rationale: The XIAO exposes all of these chip GPIOs. Keeping the contract minimizes firmware churn and avoids rerouting every node around Seeed's D-label defaults before there is evidence of a board-level conflict. The migration can be mostly wiring-label and board-target work.
  Date/Author: 2026-05-27 / Codex

- Decision: Document XIAO silkscreen labels explicitly instead of introducing board-adapter macros in firmware first.
  Rationale: The firmware already uses chip GPIO numbers and that is the real electrical contract. A `BOARD_PIN_*` abstraction would only rename constants until there is a second live board family to support, which the simple clean architecture rule discourages.
  Date/Author: 2026-05-27 / Codex

- Decision: Validate one USB canary before touching deployed nodes.
  Rationale: XIAO board-level details such as boot mode, USB enumeration, onboard LED/BOOT strapping, and antenna performance are cheap to validate on the plugged-in board and expensive to debug after multiple physical swaps.
  Date/Author: 2026-05-27 / Codex

- Decision: Preserve existing device IDs, hostnames, metrics, OTA password, and ingest payloads.
  Rationale: This is a hardware board migration, not a data-model migration. The backend, gateway, dashboard, and historical queries should continue to see `plant-a-node`, `reservoir-node`, `fan-controller`, and `breeding-env-node` as the same logical devices.
  Date/Author: 2026-05-27 / Codex

- Decision: Use a temporary reservoir canary identity before wiring the XIAO into the live reservoir chain.
  Rationale: The existing reservoir node may remain online during bench testing. Using `reservoir-xiao` and `dirt-reservoir-xiao` prevents hostname/device identity collisions while still exercising the reservoir firmware, ADS1115 I2C path, WiFi, OTA, and ingest contract.
  Date/Author: 2026-05-27 / Codex

- Decision: Do not write a separate XIAO reservoir controller.
  Rationale: The existing reservoir firmware is already board-agnostic at the controller level and uses explicit chip GPIOs for I2C. The canary needs a board target and temporary identity, not a forked firmware implementation.
  Date/Author: 2026-05-27 / Codex


## Outcomes & Retrospective

Not started. Fill this in after the XIAO canary and after the fleet swap.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before implementation:

- `docs/commands.md` before running PlatformIO, tests, services, or lint.
- `docs/rules/simple-clean-architecture.md` before changing architecture, preserving compatibility, or adding abstractions.
- `.agents/PLANS.md` before updating this ExecPlan.
- `wiki/AGENTS.md` and `docs/wiki/conventions.md` before creating or substantially rewriting wiki pages.

Current firmware projects:

- `firmware/plant_node/`: plant A/B/C/D firmware. `firmware/plant_node/src/main.cpp` reads one capacitive soil moisture sensor on chip GPIO3 / ADC1_CH3 and posts `soil_moisture_raw` through the shared ingest client. Per-node PlatformIO environments set only `PLANT_ID`.
- `firmware/reservoir_node/`: reservoir pressure firmware. `firmware/reservoir_node/src/main.cpp` uses I2C on chip GPIO4/GPIO5 to read an ADS1115 and posts `reservoir_pressure_raw` plus `reservoir_in`.
- `firmware/fan_controller/`: main fan/tent environment node and `breeding-env` environment-only profile. `firmware/fan_controller/src/main.cpp` uses I2C on chip GPIO4/GPIO5 for SHT45 and, when fan control is enabled, PWM on chip GPIO6/GPIO7 for MOSFET gates to the AC Infinity fan lines.
- `firmware/common/`: shared WiFi, OTA, and ingest helpers. The board migration should not fork these helpers.

Current board target:

- All three PlatformIO projects use `board = esp32-c3-devkitm-1` under an `[esp32_c3_base]` section. This is a generic ESP32-C3 target used for the current SuperMini clone boards.

Target board:

- PlatformIO board ID: `seeed_xiao_esp32c3`.
- Installed manifest path: `~/.platformio/platforms/espressif32/boards/seeed_xiao_esp32c3.json`.
- The manifest sets `-DARDUINO_XIAO_ESP32C3`, `-DARDUINO_USB_MODE=1`, `-DARDUINO_USB_CDC_ON_BOOT=1`, 160 MHz CPU, 80 MHz flash, QIO flash mode, 4 MB flash, and the Arduino variant `XIAO_ESP32C3`.

Internet-grounded hardware facts used by this plan:

- Seeed's XIAO ESP32C3 page documents the board as using Espressif's ESP32-C3 WiFi/Bluetooth LE 5.0 chip, with 4 MB flash, 400 KB SRAM, and compact XIAO form factor.
- Seeed's pinout exposes D0 through D10 with analog-capable pins on D0 through D4, and includes I2C, UART, and SPI-capable pins through the XIAO header.
- Seeed's docs call out the BOOT button behavior: holding BOOT while connecting USB can force bootloader mode.
- PlatformIO has a first-class `seeed_xiao_esp32c3` board definition, so no custom board JSON should be necessary unless canary flashing proves a local PlatformIO bug.
- Existing SuperMini documentation and local wiki notes treat the current boards as ESP32-C3 clone/SuperMini devices with USB-C, 4 MB flash class, native USB-CDC, and exposed GPIOs including GPIO3 through GPIO7. Their board-level pin labels and physical footprint are not the same as XIAO.

Proposed XIAO wiring label map for canary validation:

- Plant moisture sensor AOUT: chip GPIO3, XIAO label D1.
- Reservoir ADS1115 SDA/SCL: chip GPIO4/GPIO5, XIAO labels D2/D3.
- SHT45 SDA/SCL: chip GPIO4/GPIO5, XIAO labels D2/D3.
- Fan D+ MOSFET gate: chip GPIO6, XIAO label D4.
- Fan B5 MOSFET gate: chip GPIO7, XIAO label D5.

If canary testing proves GPIO4/GPIO5 I2C is unreliable on XIAO, the fallback is to move I2C to Seeed's default XIAO I2C labels and then choose two non-strap, non-UART pins for fan MOSFET gates. Do not implement that fallback speculatively; record the failure evidence first.


## Plan of Work

Milestone 1: Capture the current source and hardware baseline.

Record the current PlatformIO board manifests, current firmware builds, attached USB devices, and current wiki state. This milestone should not flash hardware. It establishes the before state and proves that any later build break is caused by the board-target migration, not an existing firmware problem.

Files and commands involved:

- `firmware/plant_node/platformio.ini`
- `firmware/reservoir_node/platformio.ini`
- `firmware/fan_controller/platformio.ini`
- `firmware/plant_node/src/main.cpp`
- `firmware/reservoir_node/src/main.cpp`
- `firmware/fan_controller/src/main.cpp`
- `pio device list`
- `pio boards seeed_xiao_esp32c3`
- `pio boards esp32-c3-devkitm-1`

Milestone 2: Add a disposable XIAO canary probe in `debug/`.

Create a small PlatformIO probe project or `--project-conf` file under `debug/xiao_esp32c3_probe/`. It should compile for `seeed_xiao_esp32c3`, print chip model, MAC, flash size, board macro presence, and the planned pin map over USB CDC. If useful, include simple checks that drive GPIO6/GPIO7 low then high and scan I2C on GPIO4/GPIO5.

This is not production firmware. It answers whether the attached board flashes, boots, logs over USB CDC, and exposes the planned pins as expected. Keep it in `debug/` so it cannot become an app dependency.

Milestone 3: Change production firmware board targets directly.

Edit the `[esp32_c3_base]` section in each PlatformIO project:

- `firmware/plant_node/platformio.ini`
- `firmware/reservoir_node/platformio.ini`
- `firmware/fan_controller/platformio.ini`

Set `board = seeed_xiao_esp32c3`. Remove duplicated USB build flags if they are redundant with the XIAO board manifest and validation confirms USB CDC still works. Keep `FIRMWARE_VERSION` flags and project-specific build flags. Update comments from SuperMini to XIAO where they describe the canonical target.

Do not add `board_supermini` and `board_xiao` environments unless a real staged rollback requirement appears. If rollback is needed during the physical swap, use git to revert the small board-target diff or flash the prior build artifact.

Milestone 4: Build every production profile for XIAO.

Run all active firmware builds:

- Plant profiles: `plant-a`, `plant-b`, `plant-c`, `plant-d`.
- Reservoir profile: `reservoir`.
- Fan/environment profiles: `fan`, `breeding-env`.

The expected result is build success for every profile. The existing `ADC_ATTEN_DB_11` deprecation warning in plant firmware may remain unless this migration chooses to clean it up as a source-owned warning fix.

Milestone 5: USB flash one XIAO canary as a low-risk node.

Use the plugged-in XIAO board as the first canary. Prefer a plant profile because it exercises ADC, WiFi, ingest, mDNS, and OTA without touching the fan control circuit or reservoir analog chain. If there is no sensor attached, a no-sensor boot still validates USB, WiFi, mDNS, OTA, and ingest envelope behavior; the ADC value can be treated as meaningless until wired.

Before flashing, identify the correct USB path by `pio device list` and `udevadm info`. Flash with an explicit `--upload-port` rather than relying on `/dev/ttyACM0` or `/dev/ttyACM1`, because both attached boards may enumerate as `303A:1001`.

After flashing, watch serial logs. Confirm boot, WiFi join, mDNS hostname, OTA start, and ingest attempts. If ingest is enabled and WiFi credentials are present, confirm `device.last_seen` updates for the canary identity.

Milestone 6: Validate each electrical role before physical fleet swap.

Before replacing deployed boards, prove the XIAO can perform each role:

- Plant role: connect a capacitive soil moisture sensor to XIAO D1/GPIO3 and confirm raw ADC changes between air, touch, and water/known wet media.
- I2C role: connect SHT45 or ADS1115 to XIAO D2/GPIO4 and D3/GPIO5 and confirm sensor detection/readings.
- Fan role: with the fan disconnected or on a bench-safe harness, confirm GPIO6/GPIO7 drive the MOSFET gates as expected and boot behavior leaves the fan in the documented fail-safe state.

Record pass/fail notes in this ExecPlan.

Milestone 7: Swap deployed nodes one at a time.

For each node, move wiring to the XIAO according to the canary-proven label map, flash the matching production environment, and validate live telemetry before moving to the next node.

Suggested order:

1. Plant node with easiest physical access.
2. Remaining plant nodes.
3. Reservoir node.
4. Breeding environment node if present.
5. Fan-controller node last, because it has actuator side effects.

For each node, preserve the existing hostname and device ID so historical continuity remains intact. Check serial logs, mDNS/OTA reachability, and device freshness after each swap.

Milestone 8: Update documentation and retire misleading SuperMini language.

After the fleet is working, update the wiki and repo docs:

- `wiki/hardware/esp32-plant-nodes.md`
- `wiki/hardware/reservoir-level.md`
- `wiki/hardware/ac-infinity-fan-control.md`
- `wiki/hardware/project-box-enclosures.md`
- `wiki/index.md`
- `wiki/overview.md`
- `docs/epics/sensor-hardware/README.md`

The docs should say the fleet now uses Seeed Studio XIAO ESP32-C3 boards, include the XIAO label map, and keep old SuperMini details only where they describe historical rows or past decisions.


## Concrete Steps

Baseline commands:

    cd /home/akcom/code/dirt
    pio boards seeed_xiao_esp32c3
    pio device list

Build current production firmware after the board-target edit:

    cd /home/akcom/code/dirt/firmware/plant_node
    pio run -e plant-a
    pio run -e plant-b
    pio run -e plant-c
    pio run -e plant-d

    cd /home/akcom/code/dirt/firmware/reservoir_node
    pio run -e reservoir

    cd /home/akcom/code/dirt/firmware/fan_controller
    pio run -e fan
    pio run -e breeding-env

Expected result for each build:

    ========================= [SUCCESS] ... =========================

Canary USB device identification:

    cd /home/akcom/code/dirt
    pio device list
    udevadm info -q property -n /dev/ttyACM0 | sort
    udevadm info -q property -n /dev/ttyACM1 | sort

Canary flash example, replacing the port with the actual XIAO port:

    cd /home/akcom/code/dirt/firmware/plant_node
    pio run -e plant-a -t upload --upload-port /dev/ttyACM1

Monitor example:

    cd /home/akcom/code/dirt/firmware/plant_node
    pio device monitor -p /dev/ttyACM1 -b 115200

OTA proof after the USB canary boots and joins WiFi:

    cd /home/akcom/code/dirt/firmware/plant_node
    pio run -e plant-a-ota -t upload

Local freshness check:

    cd /home/akcom/code/dirt
    uv run --package dirt-shared python - <<'PY'
    from dirt_shared.db import session_scope
    from dirt_shared.models import Device

    with session_scope() as session:
        for device in session.query(Device).order_by(Device.device_id):
            print(device.device_id, device.last_seen, device.ip, device.firmware_version, device.uptime_ms)
    PY

Use the actual shared DB query helper if this snippet no longer matches the current shared package API.


## Validation and Acceptance

Accept the firmware-source portion when:

- `firmware/plant_node/platformio.ini`, `firmware/reservoir_node/platformio.ini`, and `firmware/fan_controller/platformio.ini` all use `board = seeed_xiao_esp32c3`.
- Every active firmware profile builds successfully.
- The production firmware still contains one clear source of truth for each chip GPIO assignment.
- There are no SuperMini-only comments describing current hardware.

Accept the USB canary when:

- The XIAO is identified as the intended upload target.
- USB flashing succeeds.
- Serial logs show firmware version, node identity, pin map, WiFi connect, mDNS/OTA startup, and ingest attempts.
- The canary accepts at least one OTA update.
- The canary updates its logical `device.last_seen` row or, if intentionally isolated from WiFi, reaches the expected serial-only proof points.

Accept the fleet rollout when:

- Every deployed ESP32 logical device is physically rebuilt on XIAO hardware.
- Each device posts fresh readings under its existing device ID.
- OTA works for each node after the swap.
- The dashboard/device freshness view shows the fleet online.
- The wiki reflects the new hardware truth and no longer presents SuperMini as the current fleet board.


## Idempotence and Recovery

Build commands are safe to repeat.

USB flashing a canary is safe to repeat. If a XIAO does not appear as a serial device, hold BOOT while plugging in USB to force bootloader mode, then retry upload. Record the exact port and serial in this ExecPlan.

OTA flashing is safe to repeat once the node has booted and the OTA password is correct. If OTA fails, use USB flashing for that physical board and preserve the same firmware identity.

Physical swaps should be one node at a time. If a swapped node fails validation, reinstall the previous SuperMini for that node or keep the XIAO connected over USB on the bench until the issue is isolated. Do not proceed to the next physical node while the current logical device is offline unless the user explicitly accepts the monitoring gap.

If GPIO4/GPIO5 I2C fails on XIAO, stop the rollout and update this plan with the failure evidence. Then choose a revised pin contract and migrate all affected firmware and wiki docs directly in one change.

If fan GPIO6/GPIO7 behavior is unsafe at boot, do not install the XIAO fan-controller board. Pick safer output pins, validate them on the bench, update the firmware constants and hardware docs directly, and only then swap the actuator node.


## Artifacts and Notes

Internet sources consulted:

- Seeed Studio XIAO ESP32C3 getting-started and pinout documentation: `https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/`
- PlatformIO board registry for `seeed_xiao_esp32c3`: `https://docs.platformio.org/en/latest/boards/espressif32/seeed_xiao_esp32c3.html`
- Espressif ESP32-C3 DevKitM-1 reference, used as a baseline for the existing generic target: `https://docs.espressif.com/projects/esp-idf/en/latest/esp32c3/hw-reference/esp32c3/user-guide-devkitm-1.html`
- SuperMini board notes: `https://homeding.github.io/boards/esp32c3/super-mini-c3.htm`

Local evidence captured on 2026-05-27:

    pio boards seeed_xiao_esp32c3
    ID                  MCU      Frequency    Flash    RAM    Name
    seeed_xiao_esp32c3  ESP32C3  160MHz       4MB      320KB  Seeed Studio XIAO ESP32C3

    pio boards esp32-c3-devkitm-1
    ID                  MCU      Frequency    Flash    RAM    Name
    esp32-c3-devkitm-1  ESP32C3  160MHz       4MB      320KB  Espressif ESP32-C3-DevKitM-1

    pio device list
    /dev/ttyACM0  USB VID:PID=303A:1001 SER=E8:F6:0A:16:9F:FC
    /dev/ttyACM1  USB VID:PID=303A:1001 SER=AC:A7:04:D5:31:E0

Current baseline builds succeeded before board-target edits:

    cd firmware/plant_node && pio run -e plant-a
    cd firmware/reservoir_node && pio run -e reservoir
    cd firmware/fan_controller && pio run -e fan

Reservoir XIAO canary evidence captured on 2026-05-27:

    /dev/ttyACM0
    MAC: e8:f6:0a:16:9f:fc
    Pre-flash flash strings included:
    esp32:esp32:XIAO_ESP32C3:UploadSpeed=921600,CDCOnBoot=default,CPUFreq=160,FlashFreq=80,FlashMode=qio,FlashSize=4M,PartitionScheme=no_ota,DebugLevel=none,EraseFlash=none

    /dev/ttyACM1
    MAC: ac:a7:04:d5:31:e0
    Flash strings included:
    reservoir-node
    dirt-reservoir
    reservoir_pressure_raw

    cd firmware/reservoir_node
    pio run -e reservoir
    pio run -e reservoir -t upload

    Upload target:
    /dev/ttyACM0, MAC e8:f6:0a:16:9f:fc

    Read-back strings from /dev/ttyACM0 after upload:
    reservoir-xiao
    0.1.3-xiao-canary
    dirt-reservoir-xiao

Open validation remaining for this canary:

- Serial boot output was not captured after upload.
- ADS1115/SEN0262/probe hardware has not yet been wired to the XIAO canary.
- WiFi join, mDNS, OTA, ingest, and `device.last_seen` are not yet proven for `reservoir-xiao`.


## Interfaces and Dependencies

Firmware board target:

- PlatformIO board ID must be `seeed_xiao_esp32c3` for all active ESP32-C3 production projects after the cutover.

Firmware identities that must remain stable:

- Plant nodes: `plant-a-node`, `plant-b-node`, `plant-c-node`, `plant-d-node` as produced by `firmware/plant_node/src/main.cpp`.
- Reservoir node: `reservoir-node`.
- Main fan/tent node: `fan-controller`.
- Breeding environment node: `breeding-env-node` if deployed.

Firmware behavior that must remain stable:

- ESP32 nodes POST to `/api/ingest/sensors`.
- Nodes use the shared WiFi, OTA, and ingest helpers under `firmware/common/`.
- OTA uses the existing fleet password environment variable `PLANT_OTA_PASSWORD`.
- The backend ingest boundary and database schema do not change for this migration.

Hardware pin contract after canary validation:

- Chip GPIO3: plant soil moisture ADC.
- Chip GPIO4/GPIO5: I2C bus for ADS1115 and SHT45 roles.
- Chip GPIO6/GPIO7: fan-controller MOSFET gate outputs.


## Revision Notes

- 2026-05-27: Initial plan created after internet research, local firmware inspection, PlatformIO board lookup, USB device enumeration, and baseline firmware builds.
