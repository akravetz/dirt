# Reservoir Node Project Box and Shared 12V Power

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this work, the reservoir node will be mounted in a splash-resistant project box and powered from the same 12V wall adapter that already powers the submerged reservoir pressure transducer loop. The operator should no longer need a separate USB power brick for the Seeed XIAO ESP32-C3 reservoir controller, and the reservoir electronics should be strain-relieved, dry, serviceable, and easier to inspect.

The observable end state is a physical box near the Autopot reservoir with one 12V input, a fused 12V distribution point, a reputable 12V-to-5V buck regulator, the existing pressure and pH signal boards, and the XIAO powered through its USB-C connector. The live `reservoir-node` should continue posting `reservoir_in`, `reservoir_pressure_raw`, `reservoir_ph_voltage`, `reservoir_ph_raw`, and `reservoir_ph` every 30 seconds with no controller reboot loops, no ingest gaps, and no pH/depth channel swap.


## Progress

- [x] (2026-05-30 MDT) Confirmed the live reservoir node publishes pressure/depth on ADS1115 A0 and pH on ADS1115 A1 with firmware `0.1.6-ph-cal`.
- [x] (2026-05-30 MDT) Confirmed the protoboard swap recovered to plausible live values after A0/A1 were corrected: `reservoir_in` around `10.6 in`, pH voltage around `1.693 V`, and `reservoir_ph` around `5.95`.
- [x] (2026-05-30 MDT) Researched reputable parts and official documentation for the buck regulator, XIAO power entry, DFRobot signal converter, pH board, USB power breakout, cable, WAGO connectors, Littelfuse fuse holder, and enclosure choices.
- [x] (2026-05-30 MDT) Wrote this project-box implementation plan.
- [ ] Order or gather the final BOM parts.
- [ ] Bench-build the fused 12V-to-5V power distribution without connecting the live sensor boards.
- [ ] Move the reservoir node electronics into the project box and wire final strain relief.
- [ ] Validate live telemetry and update hardware documentation with final photos/notes.


## Surprises & Discoveries

- Observation: The DFRobot SEN0262 is not a buck regulator.
  Evidence: DFRobot documents it as a current-to-voltage module that converts `0-25mA` to `0-3V`, is powered by `3.3-5.5V`, and recommends a 12-bit or better ADC. It is part of the pressure signal chain, not the ESP32 power supply.

- Observation: The current reservoir firmware already assumes the final signal-channel assignment.
  Evidence: `firmware/reservoir_node/src/main.cpp` reads ADS1115 channel 0 as pressure/depth and channel 1 as pH. A previous A0/A1 swap produced implausible depth and pH values before the wiring was corrected.

- Observation: Powering the XIAO directly from its `5V` pin is possible but has a board-specific caveat.
  Evidence: Seeed documents `5V` as USB VBUS power input/output and says an external source on this pin must include a diode. The less error-prone project-box design is to feed regulated 5V into a USB-A breakout and use a short USB-A-to-C cable into the XIAO's USB-C port.

- Observation: The existing reservoir wiki still mentions lower-quality generic buck choices for the first build.
  Evidence: `wiki/hardware/reservoir-level.md` lists a mini-360-class buck in the older BOM. This project-box build should replace that with a named Pololu regulator and update the wiki after assembly.


## Decision Log

- Decision: Use the existing 12V wall adapter as the single power source for both the pressure loop and reservoir controller.
  Rationale: The pressure transducer already requires a 12V loop supply. The ESP32, ADS1115, SEN0262 logic side, and pH board need 5V, so a small buck regulator can safely derive that from the same adapter. One adapter reduces clutter without changing the sensing architecture.
  Date/Author: 2026-05-30 / Codex

- Decision: Use a reputable buck regulator, specifically Pololu D24V22F5 or a directly equivalent name-brand module, instead of a no-name LM2596/mini-360 board.
  Rationale: This box carries analog pH and hydrostatic pressure signals. A better regulator reduces ripple, thermal uncertainty, and mystery failures in a humid grow-room install.
  Date/Author: 2026-05-30 / Codex

- Decision: Power the XIAO through USB-C from the regulated 5V rail.
  Rationale: USB-C preserves the board's normal power path and avoids Seeed's diode requirement for direct `5V` pin injection. A USB-A female breakout plus a short USB-A-to-C cable is mechanically simple and serviceable.
  Date/Author: 2026-05-30 / Codex

- Decision: Keep all mains voltage outside the project box.
  Rationale: The box should contain only low-voltage DC. The 120VAC-to-12V conversion remains inside the listed wall adapter, which avoids line-voltage enclosure, grounding, strain-relief, and code-compliance work.
  Date/Author: 2026-05-30 / Codex

- Decision: Do not change firmware or ingest as part of the power-box build unless validation shows a real signal problem.
  Rationale: The node already reports the desired metrics. This project is mechanical power and enclosure work, and the simplest truthful implementation is to preserve the working firmware/data path.
  Date/Author: 2026-05-30 / Codex


## Outcomes & Retrospective

Not implemented yet. Fill this section after the box is assembled and live telemetry has been observed for at least one stable 10-minute window.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before doing related work:

- `docs/commands.md` before running service, firmware, test, or deploy commands.
- `wiki/hardware/reservoir-level.md` for the current reservoir pressure-transducer architecture, calibration constants, and mounting cautions.
- `wiki/hardware/reservoir-level-bringup.md` for the current pressure-loop wiring.
- `wiki/hardware/project-box-enclosures.md` for drilling, glands, strain relief, desiccant, and enclosure layout guidance.
- `docs/rules/simple-clean-architecture.md` before expanding scope into firmware, ingest, or schema changes.

The live reservoir node is a Seeed XIAO ESP32-C3 running `firmware/reservoir_node/`. It advertises as `dirt-reservoir.local` and posts scoped ingest readings as `site_id='homebox'`, `tent_id='main'`, `zone_id='reservoir'`, `device_id='reservoir-node'`.

Current firmware behavior:

- ADS1115 address: `0x48`.
- I2C from XIAO: SDA on GPIO4, SCL on GPIO5.
- ADS1115 A0: DFRobot KIT0139 pressure transducer through DFRobot SEN0262 current-to-voltage module.
- ADS1115 A1: DFRobot Gravity SEN0169 industrial analog pH board.
- Published metrics: `reservoir_pressure_raw`, `reservoir_in`, `reservoir_ph_raw`, `reservoir_ph_voltage`, and `reservoir_ph`.

Definitions:

- A buck regulator is a DC-to-DC converter that steps 12V down to regulated 5V.
- SEN0262 is the DFRobot 4-20mA current-to-voltage converter used by the pressure sensor signal loop. It is not a power regulator.
- The pH board means the DFRobot Gravity SEN0169 analog pH board with the BNC connector and gain potentiometer. Keep it dry.
- The pH probe body may be submerged in the reservoir solution; the BNC connector and pH board must remain dry and above splash risk.
- The pressure transducer cable contains an atmospheric vent. Keep the dry end breathable and dry; do not pot or seal it into a wet airtight pocket.


## Plan of Work

Milestone 1: Finalize and purchase the BOM.

Use reputable, sourceable parts. The recommended baseline BOM is:

- 1 x Pololu D24V22F5 5V 2.5A step-down regulator, item 2858. Official page: https://www.pololu.com/product/2858.
- 1 x SparkFun PRT-10288 female 5.5 x 2.1 mm barrel jack adapter or equivalent reputable screw-terminal barrel adapter. Product reference: https://www.sparkfun.com/products/10288.
- 1 x Littelfuse 150 Series or 150520 Series inline fuse holder for 5x20mm fuses. Official series references: https://www.littelfuse.com/products/fuses-overcurrent-protection/fuse-holders-fuse-blocks-accessories/fuse-holders/in-line-fuse-holders/150 and https://www.littelfuse.com/products/fuses-overcurrent-protection/fuse-holders-fuse-blocks-accessories/fuse-holders/in-line-fuse-holders/150520.
- 2 to 3 x 5x20mm fuses, 500mA fast-blow preferred for first build; 1A acceptable if nuisance blowing occurs during WiFi startup. The existing 12V adapter is 1A, so do not exceed adapter and wire ratings.
- 1 x SparkFun BOB-12700 USB Type-A female breakout. Official page: https://www.sparkfun.com/sparkfun-usb-type-a-female-breakout.html.
- 1 x short USB-A-to-USB-C cable, such as Adafruit product 4473, 1 ft. Official page: https://www.adafruit.com/product/4473.
- 1 x WAGO 221 lever connector assortment or equivalent genuine WAGO 221 connectors for low-voltage DC distribution. Official overview: https://www.wago.com/us/installation-221-ad.
- 1 x 470uF, 10V or higher, low-ESR electrolytic capacitor from Panasonic, Nichicon, Rubycon, or United Chemi-Con for the 5V rail near the XIAO and analog boards.
- 2 to 4 x 0.1uF ceramic decoupling capacitors for local board power rails if the final layout leaves long 5V/GND runs.
- 1 x gasketed enclosure, preferably Hammond 1554C2GY or a similar Hammond/Bud polycarbonate box. Hammond 1554C2GY reference: https://www.hammfg.com/part/1554c2gy.
- PG7/PG9 IP-rated cable glands sized to the actual cable jackets.
- Internal screw-down cable-tie mounts, small zip ties, heat-shrink, ferrules if using screw terminals, M2.5/M3 standoffs, and desiccant packets.

Do not buy a no-name LM2596/XL4015/mini-360 board for the final install unless the Pololu-class part is unavailable and the substitute is explicitly validated for low ripple and thermal behavior at 12V input.

Milestone 2: Bench-build and test the power path.

Build only the power distribution first, with the reservoir electronics disconnected. The bench topology is:

- 12V wall adapter center-positive barrel output into the barrel adapter.
- Barrel adapter positive through the inline fuse.
- Fused 12V positive to a WAGO or terminal distribution point.
- Barrel adapter negative to the 12V return distribution point.
- 12V positive/return to the Pololu buck `VIN` and `GND`.
- Buck 5V output to the USB-A breakout `VCC` and `GND`.
- Buck 5V output to a 5V distribution point for ADS1115 VDD, SEN0262 Gravity VCC, and pH board VCC.
- 470uF capacitor across 5V and GND near the XIAO/sensor-board distribution point, observing polarity.

Before connecting the XIAO, measure with a multimeter:

- Barrel polarity is center-positive.
- Fused distribution is about 12V DC.
- Buck output is 5.00V to 5.15V DC with no load.
- USB-A breakout VBUS is 5V relative to USB-A GND.
- There is continuity between all low-voltage grounds that must be common.
- There is no continuity from 12V positive to 5V positive or from either positive rail to the enclosure hardware.

Milestone 3: Move sensor wiring into the project box.

Mount the Pololu buck, USB-A breakout, ADS1115, SEN0262, pH board, and XIAO on perma-proto or standoffs. Keep analog leads short and separated from the 12V input leads where practical.

Final low-voltage wiring:

- Pressure loop 12V path remains the existing loop: 12V positive to SEN0262 loop positive, SEN0262 loop negative to KIT0139 probe brown, KIT0139 probe blue to 12V negative.
- SEN0262 Gravity VCC to regulated 5V, GND to common 5V/12V return, signal to ADS1115 A0.
- pH board `+` to regulated 5V, `-` to common ground, analog output to ADS1115 A1.
- ADS1115 VDD to regulated 5V, GND to common ground, SDA to XIAO GPIO4, SCL to XIAO GPIO5, ADDR to GND for address `0x48`.
- USB-A breakout VCC/GND to regulated 5V/GND, short USB-A-to-C cable to XIAO USB-C.
- Do not also run a second separate 5V feed to the XIAO `5V` pin unless the USB-C path is removed and Seeed's diode guidance is followed.

Mechanical layout:

- Put cable entries on the lower side of the mounted box when possible, with drip loops before each gland.
- Use one gland for 12V input if it enters as a cable, one gland for the pressure probe cable, and one gland for the pH probe cable if routing requires it.
- Strain-relieve each cable twice: gland at the wall plus an internal zip tie or clamp before a terminal, solder joint, or board connector.
- Keep the BNC connector, pH board, ADS1115, SEN0262, XIAO, buck, and USB breakout dry.
- Keep the pressure transducer cable vent breathable and dry. Add desiccant but do not pot the cable end.
- Label A0 as pressure and A1 as pH inside the box.

Milestone 4: Power up and validate live behavior.

Power the completed box from the 12V adapter. The XIAO should boot from USB-C, join WiFi, and post within about 30 seconds. The pressure/depth and pH metrics should remain plausible and should not match the previous swapped-channel failure mode.

If the node does not appear, validate in this order:

- 12V at the input distribution.
- 5V at the buck output and USB-A breakout.
- XIAO power LED/boot state.
- WiFi reachability of `dirt-reservoir.local`.
- `systemctl --user status dirt-hwd dirt-gateway`.
- Recent `dirt-hwd` ingest logs and `sensor_quality` logs.
- ADS1115 channel wiring: A0 pressure, A1 pH.

Milestone 5: Update documentation after the hardware is stable.

After the final box has run stably, update:

- `wiki/hardware/reservoir-level.md` with the final power topology, actual buck model, fuse rating, enclosure model, and any changed cable routing.
- `wiki/hardware/project-box-enclosures.md` if the build teaches a reusable gland, vent, strain-relief, or layout lesson.
- This ExecPlan's `Progress`, `Surprises & Discoveries`, `Outcomes & Retrospective`, and `Artifacts and Notes` sections with validation evidence.


## Concrete Steps

Run commands from the repository root:

    cd /home/akcom/code/dirt

Before hardware assembly, confirm the current firmware still builds:

    cd firmware
    pio run -e reservoir

Expected result: PlatformIO builds the reservoir firmware successfully.

After power-up, check that the local services are running:

    systemctl --user status dirt-hwd dirt-gateway --no-pager

Check recent hwd logs for accepted ingest from `reservoir-node`:

    journalctl --user -u dirt-hwd -n 120 --no-pager

Check sensor-quality state:

    tail -n 80 var/logs/sensor_quality/$(date +%F).jsonl
    sed -n '1,200p' var/logs/sensor_quality/state.json

If a direct database check is needed, load `.env` without printing it and query the latest reservoir rows:

    set -a; source .env; set +a
    uv run --package dirt-shared python - <<'PY'
    import os
    from datetime import UTC, datetime
    from sqlalchemy import create_engine, text

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        rows = conn.execute(text("""
            select sr.ts, sr.metric, round(sr.value::numeric, 4) as value
            from sensorreading sr
            join capability c on c.capability_id = sr.capability_id
            where c.device_id = 'reservoir-node'
              and sr.metric in (
                'reservoir_in',
                'reservoir_pressure_raw',
                'reservoir_ph_voltage',
                'reservoir_ph_raw',
                'reservoir_ph'
              )
            order by sr.ts desc
            limit 20
        """)).all()
    now = datetime.now(UTC)
    print("now_utc", now.isoformat())
    for row in rows:
        print(row.ts, row.metric, row.value)
    PY

Expected result: timestamps are current, metrics include both pressure/depth and pH, depth is plausible for the actual reservoir fill, and pH is plausible for the solution being measured.


## Validation and Acceptance

Hardware acceptance:

- 12V input is fused before it branches inside the box.
- The buck output measures 5.00V to 5.15V before connecting the XIAO.
- The XIAO is powered through USB-C from the regulated 5V rail.
- The project box contains only low-voltage DC, not 120VAC.
- All cables entering the box have drip loops and strain relief.
- The pH board, BNC connector, buck, XIAO, ADS1115, and SEN0262 stay dry.
- The pressure sensor vent remains dry and breathable.

Telemetry acceptance:

- `reservoir-node` is seen by `dirt-hwd` within 60 seconds of power-up.
- For a 10-minute window, readings arrive at roughly the 30-second firmware cadence.
- Latest metrics include `reservoir_in`, `reservoir_pressure_raw`, `reservoir_ph_voltage`, `reservoir_ph_raw`, and `reservoir_ph`.
- `sensor_quality` remains `ok` for `reservoir-node`.
- pH voltage is in the expected analog range for the current solution, and depth is in the expected range for the actual fill level.
- There is no recurrence of the known swapped-channel signature: absurdly high `reservoir_in` combined with pH near the top of the 0-14 scale.

Documentation acceptance:

- `wiki/hardware/reservoir-level.md` no longer recommends the old generic buck for the final project-box build.
- The wiki records the final fuse rating, regulator model, enclosure model, and wiring topology.
- This ExecPlan records the actual validation evidence and any deviations from the planned BOM.


## Idempotence and Recovery

Safe to repeat:

- Firmware build with `pio run -e reservoir`.
- Service status/log checks.
- Database latest-reading queries.
- Multimeter checks with power applied and sensor boards connected, as long as probes do not short adjacent terminals.

Risky or non-idempotent:

- Cutting, stripping, crimping, soldering, and drilling enclosure holes. Measure cable diameter, gland size, and board placement before drilling.
- Changing pressure or pH wiring. Label ADS1115 A0/A1 and verify before power-up.
- Changing the pH gain potentiometer. Do not adjust it during project-box assembly unless a fresh pH calibration is intentionally being performed.
- Applying power after rewiring. First power-up should use the fuse installed and should happen with the box open for measurement and inspection.

Recovery paths:

- If the buck output is not 5V, disconnect all downstream electronics and troubleshoot the buck/input wiring first.
- If the XIAO does not boot from USB-C, temporarily power it from the old known-good USB source. If telemetry returns, the issue is in the new 5V/USB-A breakout path.
- If pressure/depth becomes implausible but pH is plausible, inspect ADS1115 A0 and SEN0262 wiring.
- If pH becomes implausible but pressure/depth is plausible, inspect ADS1115 A1 and pH board power/signal wiring.
- If both pressure and pH are wrong, inspect 5V rail noise/grounding, ADS1115 power, I2C wiring, and shared ground.
- If ingest is absent but serial/LEDs show the node is alive, check WiFi, `dirt-reservoir.local`, `dirt-hwd`, and the ingest token/secrets only through local files without printing secret values.


## Artifacts and Notes

Official references checked while drafting:

- Pololu D24V22F5 5V 2.5A regulator: https://www.pololu.com/product/2858.
- DFRobot SEN0262 current-to-voltage converter wiki: https://wiki.dfrobot.com/sen0262/.
- DFRobot Gravity SEN0169 industrial pH meter kit product page: https://www.dfrobot.com/product-1110.html.
- Seeed XIAO ESP32-C3 getting started and power-pin guidance: https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/.
- SparkFun USB Type-A female breakout BOB-12700: https://www.sparkfun.com/sparkfun-usb-type-a-female-breakout.html.
- Adafruit 1 ft USB-A to USB-C cable product 4473: https://www.adafruit.com/product/4473.
- WAGO 221 connector overview: https://www.wago.com/us/installation-221-ad.
- Littelfuse inline fuse holder families: https://www.littelfuse.com/products/fuses-overcurrent-protection/fuse-holders-fuse-blocks-accessories/fuse-holders/in-line-fuse-holders.
- Hammond 1554C2GY enclosure: https://www.hammfg.com/part/1554c2gy.

Known live-good post-swap values from 2026-05-30 MDT, before this project-box plan:

- Firmware: `0.1.6-ph-cal`.
- Node: `reservoir-node`, IP previously observed as `192.168.1.10`.
- Depth: about `10.6 in`.
- pH voltage: about `1.693 V`.
- pH: about `5.95`.
- Sensor quality state: `ok`.


## Interfaces and Dependencies

Hardware interfaces:

- Existing 12V wall adapter, center-positive, currently powering the pressure sensor loop.
- Fused 12V distribution inside the project box.
- Pololu D24V22F5 or equivalent 12V-to-5V buck regulator.
- USB-A female breakout providing 5V/GND to a short USB-A-to-C cable.
- Seeed XIAO ESP32-C3 powered through USB-C.
- ADS1115 at I2C address `0x48`.
- ADS1115 A0 connected to SEN0262 pressure signal.
- ADS1115 A1 connected to pH board analog output.
- Common low-voltage ground among buck, XIAO, ADS1115, SEN0262 Gravity side, and pH board.

Software interfaces:

- Firmware directory: `firmware/reservoir_node/`.
- Firmware PlatformIO envs: `reservoir` for USB build/upload and `reservoir-ota` for OTA upload.
- Ingest endpoint consumed by firmware: `/api/ingest/sensors`.
- Device identity: `homebox/main/reservoir/reservoir-node`.
- Metrics expected in `sensorreading`: `reservoir_pressure_raw`, `reservoir_in`, `reservoir_ph_raw`, `reservoir_ph_voltage`, and `reservoir_ph`.
- Local services for validation: `dirt-hwd` and `dirt-gateway`.
- Sensor-quality logs: `var/logs/sensor_quality/`.

External dependencies:

- Official manufacturer docs and parts pages listed in `Artifacts and Notes`.
- Existing pH and pressure probes and current firmware calibration constants.
- Existing 12V adapter capacity. If the adapter is replaced, confirm output voltage, current rating, polarity, safety listing, and connector size before using it.


## Revision Notes

- 2026-05-30 / Codex: Initial ExecPlan drafted from the live reservoir bring-up, pH integration, and shared-12V power/BOM discussion.
