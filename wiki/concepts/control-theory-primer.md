---
title: "Control Theory Primer — PID, FOPDT, and How Our Humidifier Loop Works"
type: concept
sources: []
related: [wiki/hardware/humidifier-control.md, wiki/decisions/2026-04-27-h7142-deployed.md, wiki/decisions/2026-04-19-lights-off-aware-humidifier.md, wiki/concepts/multi-actuator-environment-control.md, wiki/concepts/vpd.md]
created: 2026-04-25
updated: 2026-04-27
---

# Control Theory Primer

A conceptual + practical walkthrough of feedback control as it shows up in this project. Written for someone who has tuned a racing-drone PID by trial-and-error and now wants the math + intuition behind it. Each section has a runnable companion script under [`debug/control-theory-demos/`](../../debug/control-theory-demos/) — the wiki text gives you the model, the script lets you play.

The home-grow humidifier is a useful teaching plant: slow, single-direction, with a real engineering history (we replaced bang-bang with PI on the live system as of 2026-04-27 with the [Govee H7142 cutover](../decisions/2026-04-27-h7142-deployed.md); the original [Raydrop MCU-mod plan](../decisions/2026-04-23-raydrop-mcu-mist-control.md) and [test plan](../../docs/epics/continuous-humidifier/phase4-test-plan.md) document the trade-offs in action).

## 1. The fundamental problem

You have a thing (the **plant**) whose behavior you want to push toward some desired value (the **setpoint**). You have a knob (the **actuator**, output **u**) that influences the plant. You have a sensor reading the plant's actual state (**y**, the measurement).

The challenge: you don't fully know the plant's dynamics, the actuator isn't instant, the sensor is noisy, and disturbances (lights flipping on, fan duty changing) keep nudging the plant away from where you want it.

The **controller** is the algorithm that turns (setpoint, measurement) into a sensible u every tick. The space of controllers is enormous; this doc walks the small ladder we actually use:

```
bang-bang   →   P-only   →   PI   →   PI + envelope guards   →   PI + feedforward   →   multi-actuator
(today)         (toy)        (next)    (Phase 4 prep)             (Phase 4 mature)         (dehumidifier era)
```

## 2. Bang-bang and why we hate it

The simplest controller: u is binary.

```python
def bang_bang(setpoint, deadband, measurement, currently_on):
    if currently_on:
        return measurement > setpoint - deadband   # stay on until clearly back in band
    return measurement > setpoint                  # turn on only when above edge
```

That `deadband` is **hysteresis** — without it, sensor noise around the setpoint would chatter the relay every sample. With it, the actuator commits to a "phase" until clearly outside the deadband on the other side.

Bang-bang is what production runs today (`apps/hwd/src/dirt_hwd/services/humidifier.py`). Run [`01_bang_bang.py`](../../debug/control-theory-demos/01_bang_bang.py) to see it cycle a simulated tent VPD around setpoint 1.2 kPa with deadband 0.4. You'll get ~12 transitions per hour and a clearly visible sawtooth pattern. **The pattern is unavoidable** — a binary actuator can only sit at one of two extremes; the plant will always overshoot when it kicks on and undershoot when it kicks off.

You can stretch out the cycles by widening the deadband (which is what we did, going 0.1 → 0.3 → 0.4 kPa over 2026-04-23) but you can't smooth them. To smooth, you need a *continuous* actuator and a different controller.

## 3. Proportional control (P) and the offset bug

With a continuous u, the simplest "smart" controller is linear feedback:

```python
def p_controller(setpoint, kc, measurement):
    err = measurement - setpoint   # positive = too dry
    return max(0.0, min(100.0, kc * err))
```

`Kc` (the proportional gain, often called Kp) sets how aggressively you correct. High Kc means a tiny error produces a big u; low Kc means the controller is sleepy.

**Problem:** P-only has *steady-state error*. Run [`02_p_only_offset.py`](../../debug/control-theory-demos/02_p_only_offset.py):

```
  Kc      V_ss   offset    u_ss
   1     1.488   +0.288    0.29
   8     1.427   +0.227    1.82
  50     1.300   +0.100    5.00
 100     1.260   +0.060    6.00
```

VPD never reaches setpoint — it settles ABOVE setpoint forever. Higher Kc shrinks the offset but never kills it. Eventually high Kc starts oscillating (we'll get there).

**Why** — at err=0 the controller commands u=0. But the plant only stays at setpoint if u = some positive value (to counteract V_dry_eq drift). So there *has to be* nonzero err in steady state, just enough that Kc·err equals the u needed to hold the plant.

Algebraically: at steady state V_ss = V_dry_eq + K·u_ss = V_dry_eq + K·Kc·(V_ss − setpoint), which solves to V_ss = (V_dry_eq − K·Kc·setpoint)/(1 − K·Kc). With K=−0.04 and Kc=8: V_ss = 1.427, offset 0.227. Permanent.

This is the most common surprise people hit when they first reach for a PID library. P alone is fundamentally broken for any plant where the natural equilibrium isn't already at setpoint. **And every real plant has that property.**

## 4. PI: integrating to kill the offset

Add an integrator that accumulates error over time:

```python
integrator += ki * err * dt
u = kc * err + integrator
```

The fix is structural: at steady state the integrator stops changing only when err = 0. So the controller HAS to drive err to 0. The constant u that holds the plant at setpoint comes from `integrator` (the accumulated history of past error), not from `kc * err` (which is 0 at err=0).

Run [`03_pi_eliminates_offset.py`](../../debug/control-theory-demos/03_pi_eliminates_offset.py) — VPD actually reaches 1.200 kPa, and the integrator settles at 7.49 (which is exactly the u needed at steady state to hold the plant against V_dry_eq drift).

`Ki` is the **integral gain** — how fast the integrator accumulates per unit of error per second. Conservative Ki = slow but stable. Aggressive Ki = fast but risks oscillation. Our production loop runs Ki=0.01, which means the integrator builds up about 0.01 × 0.1 × 30 = 0.03 per tick at err=0.1 kPa. Reaching u=7.5 takes around 250 ticks ≈ 2 hours — sluggish, but stable as a rock against an unknown plant.

### Why "PI" as opposed to "PID" — the D term and noise

The full PID adds a *derivative* term:

```python
d = kd * (err - last_err) / dt
u = kc * err + integrator + d
```

D anticipates: it commands extra u when err is *growing*, not just when err is large. On a clean signal D is genius — predicts the future, suppresses overshoot.

On a noisy signal D is a disaster. Every ±ε of sensor noise gets multiplied by Kd/dt. Run [`06_derivative_noise.py`](../../debug/control-theory-demos/06_derivative_noise.py) — u jumps wildly tick-to-tick because each sample's noise is differentiated.

Drone PIDs use D heavily because the IMU runs at ~1 kHz with very low noise. Our SHT45 reports VPD once per minute with a noise floor around ±0.02 kPa from the heater cycle. Differentiating that gives garbage. There are tricks (low-pass filter on D, derivative-on-measurement-not-error) but for a slow plant we just skip D entirely and use feedforward (section 9 below) for anticipation. **PI, not PID.** This is also captured in the [decision doc](../decisions/2026-04-23-raydrop-mcu-mist-control.md): "PID with derivative term — out of scope. The SHT45 heater-cycle noise floor makes D unhelpful."

## 5. Anti-windup — the most important practical detail

There's one more issue with PI you cannot ship without. If the actuator is *saturated* (u capped at 100, or physically blocked — water tank empty, plug unplugged), the integrator keeps accumulating error indefinitely. When the situation reverses, the integrator has built up a giant "memory" that takes ages to unwind, and the plant overshoots wildly before the controller stops driving in the wrong direction. This is **integrator windup**.

[`04_windup.py`](../../debug/control-theory-demos/04_windup.py) demonstrates: 4 hours of "tank empty," then actuator works again. Integrator grows to ~144. Plant crashes to **VPD = −1.57 kPa** (unphysical, but you get the picture — the simulated tent is a swamp).

The fix is simple: **clamp the integrator at a sensible bound**.

```python
integrator += ki * err * dt
integrator = max(-clamp, min(clamp, integrator))   # the whole anti-windup
u = kc * err + integrator
```

[`05_anti_windup.py`](../../debug/control-theory-demos/05_anti_windup.py) is the same scenario with a clamp at 50: integrator pegs there, recovery dips to **VPD = 0.38 kPa** instead of −1.57. That's the value of two extra lines of code.

How big should the clamp be? Just larger than the steady-state I you'd ever see in normal operation. Our production loop uses 50 — well above the ~7.5 needed at typical steady state, with headroom for transient bias. Too small a clamp throws away authority you need to reject real disturbances; too large defeats the purpose. A useful default: 5–10× the steady-state I you predict from the plant model.

There are fancier anti-windup schemes (back-calculation, conditional integration) but for our scale, clamping is plenty. Most production PID controllers in the wild use exactly this.

## 6. The plant — first-order systems, τ, K, L

To pick gains intelligently you need a *model* of the plant. The minimum-viable model for most physical processes is **first-order plus dead time** (FOPDT):

```
τ · dV/dt = (V_target − V)              ← the dynamics: V chases V_target with time constant τ
V_target  = V_dry_eq + K · u(t − L)     ← the steering: u with delay L moves V_target by K
```

Three parameters describe the entire plant:

| Parameter | What it means | Tent example |
|---|---|---|
| **τ** (tau, time constant, seconds) | How long it takes V to get ~63% of the way from where it is to where it's heading. After 3τ you're 95% there; after 5τ you're 99%. | Tent VPD: ~5–15 min depending on fan and conditions |
| **K** (process gain, kPa/%u) | Steady-state ΔV per unit Δu. How much "punch" the actuator has. | −0.04 kPa per %u of mist (negative — mist drops VPD) |
| **L** (dead time, seconds) | Lag between commanding u and seeing any response in V. Sensor delay + transport delay + mixing time. | ~60 s (SHT45 sample cadence dominates) |

Run [`00_plant.py`](../../debug/control-theory-demos/00_plant.py) to watch a first-order plant settle from V=0.5 to V_dry_eq=1.5 with no input — you'll see ~63% recovery at 1τ, ~95% at 3τ, ~99% at 5τ. This is the fundamental shape. Almost every physical process — temperature in a room, voltage in an RC circuit, water level in a tank — looks like this near steady state.

Real plants are higher-order (multiple staggered time constants) and nonlinear, but FOPDT captures *enough* of the dynamics for tuning purposes. If FOPDT-derived gains end up wildly off, your real plant probably needs a fancier model — but that's rare for slow processes like ours.

Drones are FOPDT-able too, but with τ measured in milliseconds and almost no dead time. The reason their PID tuning *feels* completely different from ours isn't the controller math — it's that "fast plant + clean sensor + unpredictable disturbances" is a different regime from "slow plant + noisy sensor + scheduled disturbances." Same equations, different tuning.

## 7. System identification — fitting (τ, K, L) from data

Where do τ, K, L come from? In principle: a step test. Take the plant at rest, jump u from 0 to some constant U, log y(t), fit the exponential. Standard textbook chapter, ~15 lines of scipy.

In practice for this project: we don't have step-test data because the bang-bang controller doesn't produce steps — it produces brief on-pulses too short to see the asymptote, and rare long off-segments contaminated by lights cycles. So we fit globally over the whole timeseries with a discrete first-order ARX model:

```
y[n+1] = α · y[n] + β · u[n] + γ
```

Then recover (τ, K, V_dry_eq) from (α, β, γ):

```
τ        = -dt / ln(α)
K        = β / (1 - α)
V_dry_eq = γ / (1 - α)
```

See [`debug/humidifier-fopdt/fit.py`](../../debug/humidifier-fopdt/fit.py) for the actual code, and [`fopdt-fit-findings.md`](../../docs/epics/continuous-humidifier/fopdt-fit-findings.md) for what came out: a *bracket* (τ ∈ [300, 1200] s, K ∈ [-0.06, -0.02] kPa/%u, V_dry_eq ∈ [1.3, 1.7] kPa), not a point estimate, because bang-bang segments are too short for clean asymptote fits.

The key takeaway about identification: it's not magic. You're fitting an exponential to noisy data; the quality of the fit depends entirely on the input excitation. Bang-bang on/off pulses contain enough information to bracket the parameters but not pin them. A graduated step test (hold u=25%, then 50%, then 75% for 20 min each) would give a tight fit, which is exactly what Phase 2/3 acceptance plans to do once continuous control hardware lands.

## 8. IMC tuning — picking gains from the model

Once you have (τ, K, L), you can derive PI gains directly. The most common modern method is **Internal Model Control** (IMC), which has one tuning knob — λ (lambda), the *desired closed-loop time constant*:

```
Kc = (1/|K|) · τ / (λ + L)
Ki = Kc / τ
```

λ is "how fast do you want the closed loop to be." Conservative λ ≈ 2–3τ → controller behaves *slower* than the plant's natural time constant (sluggish but very stable). Aggressive λ ≈ τ/2 → controller pushes faster than the plant naturally moves (snappy but at risk of oscillation).

Engineering trade-off: aggressive gains track better but are sensitive to model error. If your real plant has τ = 800 s and you tuned for τ = 400 s, an aggressive λ that worked great in simulation will oscillate in production. Conservative gains forgive model error.

### Worked example — computing our shadow gains by hand

Take the middle of our FOPDT bracket: τ = 600 s, K = −0.04 kPa/%u, L = 60 s. Pick λ = 2τ = 1200 s (conservative).

```
Kc = (1/|K|) · τ / (λ + L)
   = (1/0.04) · 600 / (1200 + 60)
   = 25 · 600 / 1260
   = 11.9   %u per kPa of error

Ki = Kc / τ
   = 11.9 / 600
   = 0.020  %u per kPa·s
```

Pick the slow-corner end (τ = 1200, λ = 3τ = 3600 s) for extra safety:

```
Kc = (1/0.04) · 1200 / (3600 + 60) = 25 · 0.328 = 8.2
Ki = 8.2 / 1200 = 0.0068
```

Production runs Kc=8, Ki=0.01 — sitting at the conservative edge of the slow-corner IMC, with Ki rounded up slightly. We expect to tighten gains during real-hardware tuning once we have shadow data + a graduated step test.

The point of going through this by hand is to see that **the gains aren't magic — they're a direct consequence of the plant model and the λ knob.** Pick a different λ, get different gains. There's no "right" λ; you're trading tracking speed for robustness to model error.

## 9. Feedforward — using known disturbances proactively

Feedback is *reactive* — it only sees the disturbance after it has hit the plant. Feedforward is *proactive* — it knows about a disturbance ahead of time and pre-compensates.

The dominant disturbance in our tent is the **lights schedule**. Lights on at 05:00, off at 23:00 (in veg). When lights flip off, the tent cools by several degrees over the next hour, which drops VPD substantially because cool air holds less water vapor. The feedback loop sees the VPD drop *after* it happens and reacts late.

Two ways to use feedforward in our controller:

**1. Setpoint scheduling.** When lights are off, shift the VPD setpoint downward (the "night offset"). This is a static lookup, not a model — at lights-off we know the equilibrium VPD will be lower, so we lower our target to match. See [`2026-04-19-lights-off-aware-humidifier.md`](../decisions/2026-04-19-lights-off-aware-humidifier.md). Implementation: 3 lines of code in `compute()` — `setpoint = upper_band + (0 if lights_on else night_offset_kpa)`.

**2. Operating-mode dispatch.** During the prep window before lights-off (currently 5 min, was 30 until 2026-04-27), force the actuator off — we know mist now will linger after lights turn off and contribute to a damping-off RH spike. The ramp window before lights-on (same 5 min, symmetric) allows the controller to resume against the day setpoint. This is a discrete state machine layered on top of the continuous PI loop.

Why feedforward beats derivative for our case: the lights schedule is a **known periodic disturbance**. Differentiating VPD to anticipate the disturbance would be using noisy sensor data to detect something we already know exactly when it happens. Feedforward is mathematically optimal here; D is at best a noisy substitute.

The general principle: **if you can model a disturbance, feedforward it. If you can only measure it, feed it back.** Drones can't predict gusts (no model), so they use D heavily. We can predict lights flips (perfect model from `growstate.lights_on_local`), so we use feedforward and skip D.

## 10. Stability — why too-aggressive gains oscillate

Closed-loop stability comes down to: *will the system settle, or will it ring?*

Intuition: the controller's correction has to "catch up" to the plant before the plant has moved too far. If the controller is too aggressive (high Kc, high Ki) for the plant's lag (τ + L), corrections arrive in the wrong direction and the loop *hunts*.

Concretely: high Kc means a small error provokes a big u, which overshoots the setpoint, which provokes a big u in the *opposite* direction, which overshoots back, etc. If the loop gain × phase lag exceeds 1.0, oscillation grows; below 1.0, oscillations decay.

Drone PIDs ring up to vehicle resonances; HVAC PIs ring up to ~10 minute cycles. The math is identical; only the timescale differs.

There are two classical methods to find the stability boundary:

- **Ziegler-Nichols ultimate gain** — empirical. Crank Kc up until the closed loop *just* sustains oscillation, measure the period (`Pu`), set gains as a fraction of those values (Z-N PI: Kc = 0.45·Ku, Ki = Kc / (0.83·Pu)). Effective but uses your real plant as a test rig — risky if your plant can damage itself or others when oscillating.
- **IMC (Internal Model Control)** — model-based. Section 8. Pick λ from a model and hope the model is right. Safer, but only as good as the model.

In our case the FOPDT model is approximate, and instead of cranking gains until the real tent oscillates, we run **shadow mode** (compute u, log it, don't act) for days, then refine. This is essentially "ultimate-gain-style identification but read out from a parallel-computed signal instead of a swinging plant." It also gives us continuous-input data we never got from the bang-bang regime — every shadow tick is essentially a graduated step test snippet.

### A more theoretical view (optional)

If you want the formal version: the closed-loop transfer function for a PI controller on an FOPDT plant is a polynomial in the Laplace variable `s`, and stability comes down to whether the roots of the denominator (the closed-loop poles) lie in the left half of the complex plane. As you crank Kc, the poles move toward the right half — when they cross the imaginary axis, you get sustained oscillation (Z-N's Ku); when they cross into the right half, oscillation grows unboundedly. Bode plots and root-locus diagrams visualize this geometrically.

You don't need this for tuning our humidifier — IMC + shadow mode + acceptance soak get us where we need to be. But the underlying machinery is the same one used to design F-16 flight control and missile guidance, and it's worth knowing it exists.

## 11. Drone PID vs grow-tent PI — same math, different regime

| | Racing drone | Grow tent humidifier |
|---|---|---|
| **τ (plant time constant)** | ~50 ms (vehicle inertia) | ~10 min |
| **L (dead time)** | <5 ms | ~60 s |
| **Sample rate** | 1–8 kHz | 1/min (sensor cadence) |
| **Sensor noise** | very low (calibrated IMU) | moderate (SHT45 heater drift) |
| **Disturbances** | unpredictable (gusts, prop wash) | mostly scheduled (lights) |
| **Actuator** | continuous (motor PWM, ~1% steps) | binary today, continuous after Phase 2 |
| **Symmetric authority?** | yes (motors push both directions) | no (humidifier only adds moisture) |
| **Dominant term in tuned controller** | **D** (anticipates fast disturbances) | **I** (kills slow steady-state offset) |
| **Why no D?** | — | sensor noise / dt blow-up |
| **Why feedforward?** | rare (disturbances unpredictable) | common (lights schedule is known) |
| **Tuning approach** | Z-N + flight test | IMC + shadow mode + soak |
| **Failure mode of bad tuning** | crash | swamp |

Same equations, completely different shape. Internalizing this difference is the main payoff of learning control theory after only ever having tuned drones — it lets you reason about why each parameter matters in *any* domain instead of memorizing recipes per system.

The classic mistake is reaching for a familiar pattern from the wrong domain. "PID worked great on my quad, why doesn't it work on my sous-vide?" → because the sous-vide is a slow plant with no D term in its right-sized solution. Match the controller to the regime, not the other way around.

## 12. Cascade control — a bridge to multi-actuator

Before jumping to MIMO and multi-actuator dispatch, there's a stepping-stone worth knowing: **cascade control**. You stack two PI loops, where the outer loop's output is the inner loop's setpoint.

Example from HVAC (not our system, but illustrative): outer loop targets room temperature, output is "desired chilled-water flow rate." Inner loop targets that flow rate by adjusting a valve position. The inner loop is fast (valve responds in seconds); the outer loop is slow (room responds in minutes).

Why cascade beats a single loop for these cases: the inner loop *isolates the outer loop from inner-loop disturbances*. If the chilled-water supply pressure drops, the inner loop reacts immediately to maintain flow rate; the outer loop never has to know about it.

For our project: the future "fan + humidifier + dehumidifier" architecture in [`multi-actuator-environment-control.md`](multi-actuator-environment-control.md) is *not* cascade. It's "cascaded SISO with class-based dispatch" — meaning we have multiple independent SISO loops (one per actuator) and a discrete state machine that decides which loop is in charge for each tent state. That's a different and arguably simpler design than full cascade, and it works because our actuators are largely orthogonal in their effect (humidifier mostly moves RH; fan mostly moves T).

The key thing to know: cascade is the standard pattern when one actuator's effect propagates through multiple stages with different timescales. Multi-actuator dispatch is the standard pattern when multiple actuators each affect mostly-orthogonal outputs. Picking the right pattern comes from looking at the actuator-output coupling structure, which you can write out as a sparse matrix and read off directly.

## 13. Tour of our actual controller

`apps/hwd/src/dirt_hwd/services/humidifier_pi.py` is ~200 lines. Walking it top to bottom with the concepts above:

- **`PIConfig`** — Kc, Ki, integrator clamp, sub-threshold cutoff, hysteresis, night offset, failsafe stale window, lights prep window. Every dial we'd want to tune lives here.
- **`PIInput`** — one tick's view of the world. VPD, RH, lights state, stage targets. Pure data; no I/O, no surprises.
- **`compute(cfg, state, inp)`** — the actual controller. Pure function. Order of operations:
  1. **Failsafe stale sensor**: if the latest VPD is too old, force u=0 and freeze the integrator. (Section 5 — anti-windup applies to *any* situation where the loop can't act, not just actuator saturation.)
  2. **Outside lights window**: same — force u=0, freeze integrator. The plant is in a regime we don't want to control in. (Section 9 — feedforward via discrete state.)
  3. **RH ceiling guard**: if RH ≥ stage_rh_max, force u=0. This is an **envelope guard**, not a control law — it stops the loop from violating the 2D feasibility region (T, RH) when scalar VPD might say "fine." See [multi-actuator-environment-control.md](multi-actuator-environment-control.md) Principle 1 for why this matters.
  4. **PI math**: compute err = vpd − setpoint, integrate (with dt clamped to MAX_INTEGRAL_DT_S to handle clock jumps and long gaps), apply anti-windup clamp, sum P+I, saturate to [0, 100].
  5. **Sub-threshold cutoff with hysteresis**: if u < threshold, force the plug off. The Raydrop's ultrasonic doesn't run usefully below ~5% intensity, so commanding 1% intensity is worse than off. Hysteresis around the threshold prevents the plug from chattering when u oscillates near the cutoff.

- **`PIState`** — what carries forward across ticks: integrator value, last tick timestamp (for dt), and the threshold's hysteresis state.

The whole file is testable in isolation because the controller is a pure function (state in, command out, no side effects). Property tests in `apps/hwd/tests/test_humidifier_pi.py` — 28 of them, none pin specific gain values, all assert *behaviors* (monotonicity, saturation, anti-windup, etc.). Plant-in-loop tests in `test_humidifier_pi_plant.py` — 16 tests that simulate the FOPDT plant and assert the controller drives it sensibly.

The discipline of "test behaviors not numbers" is worth its own paragraph: `assert kc == 8` is a test that breaks every time you re-tune. `assert u increases when err increases` is a test that holds across all reasonable tunings. The first is a regression test for tuning; the second is a regression test for *correctness*. Both have a place, but in a controller that's still being tuned, only the second one is sustainable.

## 14. Going deeper

If you want the textbook treatment:

- **Karl Åström & Tore Hägglund, *Advanced PID Control*** — the bible for industrial PID. Practical, not theoretical-heavy. Chapters on anti-windup, IMC, and tuning are directly relevant.
- **APMonitor's online PID course** ([apmonitor.com/pdc](https://apmonitor.com/pdc/index.php/Main/HomePage)) — free, well-paced, all in Python. Covers everything in this primer plus state-space, MPC, and identification.
- **Brian Douglas's Control Systems Lectures** on YouTube — fantastic visual intuition for stability, root locus, frequency-domain thinking. Start with "What is a PID Controller?" and "Understanding Bode Plots."
- **Ziegler-Nichols original 1942 paper** ("Optimum Settings for Automatic Controllers") — surprisingly readable; tells you where the rules came from.
- **Sigurd Skogestad, "Simple analytic rules for model reduction and PID controller tuning"** (Journal of Process Control, 2003) — the modern reference for IMC-style tuning, including what to do when your plant doesn't fit FOPDT cleanly.

For the multi-actuator and MIMO control direction (the next frontier in this project once the dehumidifier arrives), see [multi-actuator-environment-control.md](multi-actuator-environment-control.md) — the design philosophy is "cascaded SISO with class-based dispatch," explicitly *not* MPC or LQR. The reasoning there is the practical extension of everything in this primer to multiple control loops sharing a state.

For an applied frequency-domain treatment with no math background assumed, see Brian Douglas's **"Bode Plots by Hand"** YouTube series. It's the cleanest path from "I tune PIDs by trial and error" to "I can read a frequency response and predict stability." Worth a few hours.
