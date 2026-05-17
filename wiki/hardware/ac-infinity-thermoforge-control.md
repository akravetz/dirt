---
title: "Hardware — AC Infinity ThermoForge T3 Control Investigation"
type: hardware
sources: []
related: [wiki/hardware/ac-infinity-fan-control.md, wiki/concepts/multi-actuator-environment-control.md, wiki/environment/temperature.md]
created: 2026-05-16
updated: 2026-05-16
---

# AC Infinity ThermoForge T3 Control Investigation

**Status (2026-05-16):** investigation parked for follow-up. The ThermoForge T3 is working well as a night heater and has made VPD/temperature more stable. Goal is to determine whether Dirt can control it directly, preferably through the low-voltage UIS cable path rather than cloud-only control. No hardware probing has been done yet.

## Goal

Add programmatic heat control for the main tent while preserving the ThermoForge's built-in safety protections. Preferred end state: a local ESP32-class controller exposes a Dirt HTTP control surface, analogous to the current fan controller, and drives the heater through the ThermoForge's external low-voltage control interface.

## What the docs say

- AC Infinity markets the T3 as a 530 W environmental plant heater with **10 heat and cool air intake levels** and smart VPD/temperature controls.
- The ThermoForge manual shows a **UIS male-to-male extension cord** in the product contents.
- The manual's UIS setup says a compatible UIS controller can be connected to the heater by cable. When connected, the UIS controller overrides the ThermoForge's onboard controls, display, and probe.
- AC Infinity's ecosystem docs describe UIS as a proprietary control ecosystem. The physical connector may resemble USB-C, but this is not standard USB host/device communication.

Relevant public docs:

- ThermoForge product page: <https://acinfinity.com/indoor-grow/thermoforge-t3-environmental-plant-heater-530w-smart-vpd-temperature-controls-10-heat-and-cool-air-intake-levels-includes-extendable-tubing/>
- ThermoForge programming guide: <https://acinfinity.com/pages/thermoforge-programming-guide.html>
- ThermoForge manual PDF: <https://acinfinity.com/content/SFT2311X1_231120_THERMOFORGE%20Manual.pdf>
- UIS compatibility: <https://acinfinity.com/pages/ac-infinity-ecosystem/ecosystem-compatibility.html>

## Control options

### Option A — AC Infinity controller as bridge

Use a Controller 69 Pro/Pro+/AI+ as the supported bridge:

```
Dirt -> AC Infinity cloud/BLE integration -> UIS controller -> UIS cable -> ThermoForge T3
```

This is the fastest path to software control, but it depends on AC Infinity's controller/app ecosystem and community-reverse-engineered APIs rather than a documented local API.

### Option B — Direct UIS emulation

Reverse-engineer the controller-to-ThermoForge UIS signaling, then replace the UIS controller with an ESP32-based low-voltage controller:

```
Dirt -> ESP32 HTTP endpoint -> low-voltage UIS emulation -> ThermoForge T3
```

This is the preferred direction if the signaling is simple enough. It matches the successful fan-control pattern, where the stock remote's protocol turned out to be 4,969 Hz open-drain PWM plus a keep-alive line. See [AC Infinity Fan Control + Tent Environmental Sensor](ac-infinity-fan-control.md).

### Option C — Smart plug / relay

Use a rated smart plug or relay only as a safety cutoff or crude fallback, not as the primary control loop. The ThermoForge is a 530 W heater; cycling mains power loses the heater's intended UIS-level modulation and increases safety/design risk compared with using the low-voltage control interface.

## Reverse-engineering plan

Use the same staged method that worked for the Cloudline fan, with stricter heater fail-safe requirements.

1. **Get a valid signal source.** Use a Controller 69 Pro/Pro+/AI+ and the ThermoForge's UIS cable so there is real traffic to observe.
2. **Build a passive inline tap.** Put a USB-C/UIS breakout between the controller and ThermoForge. Do not connect a laptop USB port to UIS as if it were normal USB.
3. **Multimeter pre-flight.** Measure every pin to GND with the heater and controller powered. Assume signal lines may track an internal rail above 5 V until proven otherwise.
4. **Level-safe logic capture.** Use dividers, buffers, or an opto/logic-level front end before connecting the logic analyzer. Capture OFF, heat levels 1-10, controller boot/connect, probe changes, and unplug/replug behavior.
5. **Classify the protocol.** Look for PWM duty changes, fixed keep-alive pulses, bidirectional serial, device-ID pulls, or controller polling.
6. **Replay only after pin behavior is known.** Start with a sacrificial low-voltage emulator that can command OFF and one low heat level before attempting ramps.
7. **Integrate after a soak test.** Only then add a Dirt-side client/control loop.

## Safety requirements

The heater must fail differently from the fan.

- Fan controller fail-safe: driver loss lets the fan float to high speed, which is acceptable.
- Heater controller fail-safe: driver loss, ESP32 reset, WiFi loss, host crash, or stale commands must bias heat to **OFF**.

Minimum design constraints for any direct controller:

- Boot with heat disabled.
- Require explicit recent host commands to enable heat.
- Add a local max-runtime guard independent of Dirt.
- Add an independent tent temperature ceiling.
- Keep the ThermoForge's own overheat/tilt/internal protections intact by controlling only the low-voltage external interface.
- Never bypass or modify mains wiring.

## Open questions for tomorrow

- Which UIS controller is available or needs ordering: Controller 69 Pro, 69 Pro+, or Controller AI+?
- Does the ThermoForge's UIS traffic look like the fan's simple PWM/keep-alive pattern, or like a richer serial protocol?
- What voltage rails are present on the ThermoForge UIS cable?
- Does the heater default to OFF, last state, or onboard mode when UIS control disappears?
- Does level 0/Off require actively pulling a line, or is floating safe?
- Can the existing fan reverse-engineering kit be reused directly, or do we need different USB-C/UIS breakouts for the ThermoForge cable geometry?

## Resume checklist

1. Confirm the exact cable/connector orientation and photograph both ThermoForge and controller UIS ports.
2. Connect ThermoForge to a UIS controller and verify app/controller-level heat-level changes work.
3. Insert the passive inline tap and map GND/VBUS/signals with a multimeter.
4. Capture a level sweep in PulseView/sigrok.
5. Compare captured pins/frequencies/duty cycles against the fan notes.
6. Decide whether direct ESP32 emulation is worth pursuing before writing firmware.
