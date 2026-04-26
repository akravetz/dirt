# FOPDT Fit Findings — 2026-04-25

Result of step 2 in the [Phase 4 test plan](phase4-test-plan.md). Run output, verdict, and the gains we're carrying forward.

**Background reading:** if you're new to FOPDT and IMC, start with [`wiki/concepts/control-theory-primer.md`](../../../wiki/concepts/control-theory-primer.md). This doc assumes you know what τ, K, and L mean and how IMC translates them into Kp/Ki.

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

## What plant-in-loop testing surfaced

Writing the tests revealed that **conservative gains (Kc=8, Ki=0.01) cannot fully reject a fan-duty disturbance within reasonable settling time** at the slow corners of the bracket — integrator-driven re-tuning to a new fan regime can take many hours. The tests now assert directional correctness (u rises, integrator grows, peak deviation bounded) rather than full re-settling. This is informative for the eventual tuning pass: production gains will likely need higher Ki than the IMC bracket suggests, or a different control structure (e.g. feedforward on fan duty) for the fan-coupling response specifically. Captured here so the eventual tuning pass starts from "we know this is a thing" rather than "why is it slow."

## Re-running

```
cd /home/akcom/code/dirt
uv run --package dirt-shared python debug/humidifier-fopdt/fit.py
```

To extend the analysis window past 2026-04-25, edit `ANALYSIS_START_TS` in `fit.py`. To add proper lights-regime filtering, replace `lights_on_at()` with a schedule lookup against `growstate.lights_on_local` / `lights_off_local`.
