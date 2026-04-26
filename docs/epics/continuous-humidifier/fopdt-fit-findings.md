# FOPDT Fit Findings — 2026-04-25 (initial) + 2026-04-26 (refit on shadow data)

Result of step 2 in the [Phase 4 test plan](phase4-test-plan.md). Run output, verdict, and the gains we're carrying forward.

**Background reading:** if you're new to FOPDT and IMC, start with [`wiki/concepts/control-theory-primer.md`](../../../wiki/concepts/control-theory-primer.md). This doc assumes you know what τ, K, and L mean and how IMC translates them into Kp/Ki.

**Quick orientation:**
- The **2026-04-25 fit** is the original analysis on bang-bang `humidifier/*.jsonl` logs. Verdict: data brackets gains (Kc ∈ [8, 12], Ki ∈ [0.01, 0.02] at λ = 2τ–3τ) but the τ estimate (81 s global / 12 min per-segment) was noise-floor-dominated.
- The **2026-04-26 refit** is on `humidifier_shadow/*.jsonl` data — higher cadence, per-tick lights state, full lights cycle. Verdict: **trustworthy lights-on regime fit** (τ = 133 s, K = −0.72 kPa). IMC bracket against the new fit is 5–12× more aggressive than what we shipped at shadow start. See "Refit on shadow data (2026-04-26)" near the bottom.

**The 2026-04-26 numbers supersede the 2026-04-25 ones for any practical tuning question.** The 2026-04-25 history is preserved here so the original "why did we ship Kc=8?" decision is still legible.

## What was run

[`debug/humidifier-fopdt/fit.py`](../../../debug/humidifier-fopdt/fit.py) — throwaway analysis script.

- Input 1: humidifier `state_change` events from `var/logs/humidifier/*.jsonl` since 2026-04-24 00:00 UTC (post-SHT45 cutover, post-deadband-stabilization at 0.4 kPa).
- Input 2: `vpd_kpa` rows from Postgres (`source='esp32'`, ~1/min cadence) for the same window.
- Two fits in the same script:
  1. **Per-segment** — `scipy.optimize.curve_fit` of `y(t) = V_eq + (V0 − V_eq)·exp(−t/τ)` on each ON or OFF segment between consecutive `state_change` events.
  2. **Global ARX** — pools every consecutive sample pair into one discrete first-order model `y[n+1] = a·y[n] + b·u[n] + c` by least squares, recovers `τ`, `K`, asymptotes from `(a, b, c)`. Statistically efficient when individual cycles are short.
- Reports IMC-derived starting Kc/Ki for `λ ∈ {τ/2, τ, 2τ, 3τ}`.

Re-run with `uv run --package dirt-shared python debug/humidifier-fopdt/fit.py` (loads `.env` automatically for the Postgres connection).

## Run output (2026-04-25 ~15:00 UTC)

```
838 state_change events since 2026-04-24T00:00:00+00:00, 2643 vpd_kpa samples
Built 839 segments  (419 ON, 420 OFF)
```

| | Per-segment ON (37 fits) | Per-segment OFF (48 fits) | Global ARX (2,642 pairs) |
|---|---|---|---|
| τ | median 67 s, IQR [59, 122] | median 746 s, IQR [291, 819] | 19 s |
| V_eq (asymptote) | 0.66 kPa | **4.54 kPa — unphysical** | off=1.15, on=0.91 |
| RMS residual | ~0.02 kPa | ~0.04 kPa | 0.22 kPa |

**Model-free sanity check:** short ON segments (<2 min) drop VPD by **+0.585 kPa median, IQR [+0.543, +0.637]**. Falls out of the raw deltas — strong actuator authority confirmed, matches the wiki's "1 minute of mist drops VPD ~0.45 kPa" observation.

## Verdict

**The data brackets plausible gains; it does not produce a confident point estimate.** Three reasons, in priority order:

1. **Bang-bang segments are too short.** 382 of 419 ON segments and 372 of 420 OFF segments had < 4 samples (60 s sample cadence vs ~3 min segment lengths). Per-segment fits with 4 data points and 2 free parameters are essentially overfit; many ran to the optimizer's bounds (V_eq pinned at 0 or 5 kPa).
2. **Asymptote estimates are unreliable from short windows.** The 4.54 kPa OFF asymptote is unphysical — short OFF segments only see the early part of the recovery, so extrapolation runs to the bound.
3. **Per-segment and global fits disagree by ~40× on τ** (746 s vs 19 s). Neither is precise. The global fit's asymptotes look physically plausible (1.15 / 0.91 kPa) but its 19 s τ is suspiciously short, suggesting the fit is dominated by sample-to-sample noise rather than the underlying exponential dynamics. The per-segment OFF τ has the right order of magnitude (minutes-scale) but garbage asymptotes.

**Known limitation in this analysis pass:** the `lights_on / lights_off` regime separator relied on `state_change.lights_on`, but `state_change` events almost never fire during lights-off (the loop force-stops the plug then), so the regime filter is effectively a no-op. The `lights_on` and `all` global-fit rows are identical; `lights_off` reports "insufficient data." Real regime separation needs a true lights-schedule lookup. Out of scope for this pass — would mostly affect the asymptote, not the time constant.

## What we can confidently say

- **Strong actuator authority.** ~0.5 kPa VPD drop per 3 min of mist at the current Raydrop dial setting. Model-free.
- **Natural drying asymptote (mist off, lights on, current fan duty).** ~1.15 kPa from the global fit.
- **Tent memory is minutes-scale.** Per-segment OFF median τ around 12 min; visual inspection of long OFF segments supports "minutes to tens of minutes." 19 s from the global fit is almost certainly noise-dominated.

## What we can't confidently say

- **Exact τ.** Best estimate is somewhere in the 5–15 min range. Span across fits is wider than that.
- **Process gain at u=100% (continuous).** Today's bang-bang gain is at "current Raydrop dial." After Phase 2 replaces or overrides the dial, the gain at u=100% will shift. No way to extract this from bang-bang data.
- **Dead time L.** 60 s VPD sample cadence is below interesting resolution; assumed `L ≈ 60 s` for IMC.

## What we're carrying forward to Phase 4

**Conservative starting gains** — explicitly bracketed, not pinned:

```
Kc starting bracket:  8 – 12 %u/kPa     (per-segment IMC at λ = 2τ–3τ)
Ki starting bracket:  0.01 – 0.02 %u/(kPa·s)
```

We **do not** ship "best guess" Kp/Ki and call it tuned. We ship at the low end of the bracket — intentionally sluggish — so the loop won't oscillate against the unknown real plant. Then:

1. **Shadow mode** runs alongside the live bang-bang. Days of `(VPD, u_shadow)` data → re-fit globally → tighten gains. Phase-4-prep step 5.
2. **Graduated step test** as Phase 2/3 acceptance — first hour of authoritative operation, hold u=25%, u=50%, u=75% for 20 min each in lights-on steady state. 60 min of clean continuous-input data → re-fit FOPDT properly. *This* is the data the bang-bang regime can't produce.
3. **Re-tune** based on graduated-step + shadow-mode data before declaring acceptance criteria met.

## Implications for the test plan

- Property tests (step 3) **do not** assert specific Kp/Ki values — that discipline is reaffirmed.
- Plant-in-loop tests (step 6) **landed 2026-04-25** and use this bracket directly: `τ ∈ [300, 1200] s`, `|K| ∈ [0.02, 0.06]` kPa/%u, `V_dry_eq ∈ [1.3, 1.7]`. Each design test parametrizes over 4 corner/midpoint plant configs. A future re-fit on shadow data will tighten the test envelope automatically by narrowing `PLANT_PARAMS` in the test file.
- Acceptance criterion #1 (VPD within ±0.1 kPa of upper edge across 18 h) is unchanged — that's the empirical end-state, not a tuning target.

## What shadow-mode operation surfaced (2026-04-25 evening)

Once the band fix landed and shadow data started accumulating cleanly, the analyzer (`debug/humidifier-shadow/analyze.py`) revealed a separate practical finding: **the conservative starter gains produce `u` below the 5% sub-threshold cutoff on every observed `pi_active` tick.** Across 99 pi_active ticks, the median commanded `u` was 0.0% and the maximum was below threshold — `plug_on_shadow` was False on 100% of ticks, regardless of regime.

Mechanically: at `Kc=8, Ki=0.01`, conservative IMC tuning, the controller's response to a typical mid-band error of ~0.2 kPa is `P = 1.6` plus a slowly-accumulating I term. With `intensity_threshold=5.0`, the controller would need either ~3× larger error or ~30 minutes of integrator buildup to clear the cutoff. Under realistic tent dynamics with bang-bang absorbing the big errors before shadow can integrate, that buildup never happens.

**Implication for production tuning:** the IMC formula's "conservative" end (λ = 2τ–3τ) is conservative to the point of inertness when combined with a sub-threshold cutoff sized for ultrasonic minimum-running-power. Real production gains will likely need:
- Smaller λ (closer to τ, maybe smaller) → larger Kc and Ki, OR
- Lower `intensity_threshold` (1–2% instead of 5%) so the integrator has somewhere to land, OR
- Both.

This isn't a controller bug — the controller is doing exactly what conservative tuning + sub-threshold cutoff means. It IS a tuning surprise: the bracket we derived from FOPDT-fit-IMC math doesn't include "controller never actuates" as a degenerate case, but in this regime it is one. Worth knowing before the graduated step test, so we don't ship the conservative end as-is and conclude "it doesn't work" — it works as designed; the design is just inert.

## What plant-in-loop testing surfaced

Writing the tests revealed that **conservative gains (Kc=8, Ki=0.01) cannot fully reject a fan-duty disturbance within reasonable settling time** at the slow corners of the bracket — integrator-driven re-tuning to a new fan regime can take many hours. The tests now assert directional correctness (u rises, integrator grows, peak deviation bounded) rather than full re-settling. This is informative for the eventual tuning pass: production gains will likely need higher Ki than the IMC bracket suggests, or a different control structure (e.g. feedforward on fan duty) for the fan-coupling response specifically. Captured here so the eventual tuning pass starts from "we know this is a thing" rather than "why is it slow."

## Refit on shadow data (2026-04-26)

After the band fix and analyzer landed, the shadow stream collected a full lights cycle (1832 ticks, 15.3 h, 1112 lights-on / 716 lights-off samples). Re-running the FOPDT fit on shadow data via `debug/humidifier-shadow/analyze.py --section fopdt` produces dramatically better numbers:

| regime | n | τ | K (binary input) | V_off | V_on | rms |
|---|---|---|---|---|---|---|
| **lights_on** | 1112 | **133 s** (~2.2 min) | **−0.72 kPa** | 1.56 | 0.84 | 0.108 |
| lights_off | 716 | 1073 s | 0.000 (no input variability) | 0.95 | 0.95 | 0.016 |
| all combined | 1830 | 185 s | −0.41 | 1.19 | 0.78 | 0.093 |

**The lights_on row is the first trustworthy plant fit we have.** Physically credible: ~2-min closed-loop response, mist-on-vs-off ΔVPD of 0.72 kPa, asymptotes straddling the (0.8, 1.2) veg band. Fan duty was 20% throughout, Raydrop dial at 50–60% as deployed. The lights_off row has K = 0 because the controller force-stops the plug all night (no actuator signal) — expected, not a fit failure.

### Why this refit beats the 2026-04-25 attempt

Three structural reasons:

1. **Higher sample density.** Shadow logs are 30 s cadence (vs sensorreading's 60 s). 1832 samples vs 2643 — roughly equivalent volume but with lights regime explicit per tick, no contamination from lights transitions.
2. **Per-tick lights state.** The 2026-04-25 script's `lights_on_at()` used nearest-`state_change` lookup, which silently always returned `lights_on=True` because state-changes don't fire during lights-off (the loop force-stops). Shadow logs have `lights_on` directly in each record. Per-regime split is now meaningful instead of a no-op filter.
3. **A full dark period.** 716 lights-off ticks. Even though they produce K = 0 (forced off), they remove the lights-off contamination that dragged the 2026-04-25 global fit toward the noise floor.

### IMC bracket against the lights-on fit

Same formulae as 2026-04-25, with τ = 133 s, K_per_pct ≈ −0.0072 kPa/%u (binary K divided by 100 — see caveat below), L = 60 s:

| λ choice | Kc (%u/kPa) | Ki (%u/(kPa·s)) |
|---|---|---|
| aggressive (λ = τ/2) | 145 | 1.10 |
| moderate (λ = τ) | 95 | 0.72 |
| robust (λ = 2τ) | 56 | 0.43 |
| conservative (λ = 3τ) | 40 | 0.30 |

**5–12× higher than the shadow's current Kc=8, Ki=0.01.** This matches the conservative-gain inertness finding — current shipped gains land outside the IMC bracket on the still-conservative side, which is why every pi_active tick produces u below the 5% threshold.

### Important caveat — binary input vs continuous u

The shadow refit's K is "ΔVPD between mist plug ON and mist plug OFF" — at the Raydrop's *current dial setting*. With the dial at ~50–60% as physically configured, ON delivers a fixed mist rate that's roughly half of what u=100% continuous control would produce. So the binary K ≈ −0.72 kPa probably corresponds to a continuous K_per_pct in the −0.005 to −0.01 kPa/%u range, not exactly −0.0072.

The graduated step test at Phase 2/3 acceptance is the only way to pin K_per_pct precisely. Don't ship the IMC numbers above as-is — they're a much better starting bracket than 2026-04-25's, but they still need validation against clean continuous-input data.

### What this changes for the test plan

- **Plant-in-loop tests' parameter bracket** can be tightened from `τ ∈ [300, 1200]` (the 2026-04-25 wide bracket) to `τ ∈ [100, 200]` for lights-on regime. Worth doing during the next test-suite update; reduces parametrize count from 4 corners to 2.
- **Conservative starter gains for the next shadow restart** could be Kc=20, Ki=0.05 (still 4-5× below the IMC moderate bracket, well within engineering safety, but actually clears threshold with err ≈ 0.25 kPa). Don't change yet — keep current data-collection regime stable until the graduated step test, then re-tune from there.

### Findings that survive across both fits

- The −0.3 kPa night offset is overcorrecting (analyzer's PI math health section).
- The conservative starter gains are inert (sub-threshold cutoff fires every tick).
- Bang-bang gives ~−0.5 kPa per 3 min of mist (model-free, both runs).

## Re-running

Original (bang-bang data) fit:

```
uv run --package dirt-shared python debug/humidifier-fopdt/fit.py
```

Newer (shadow data) fit, lives in the analyzer:

```
uv run --package dirt-shared python debug/humidifier-shadow/analyze.py --section fopdt
```

The second one supersedes the first for any tuning question. The first is useful only for understanding the bang-bang baseline (and the noise-floor-dominated τ estimate that taught us why we needed shadow data in the first place).
