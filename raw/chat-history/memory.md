Purpose & context
Alex is conducting a personal indoor cannabis grow in Denver, Colorado, with the primary goal of hunting for a dark purple phenotype with exceptional bag appeal, terpene complexity, and potency. The strain is Sirius Black (Reversed) x BS01 (feminized). The grow doubles as a learning and documentation project, with Alex maintaining structured markdown files (a grow bible and a progress log) updated across sessions. Alex has 1–2 grows of prior experience, values low maintenance and simplicity over maximum optimization, and wants the ability to leave the grow unattended for extended periods.
Alex is a software engineer and self-described tinkerer with hands-on hardware experience (drone building, PCB soldering) but limited formal electronics theory background. Prefers explanations pitched at a technically intelligent audience with precise detail, not dumbed down.
Current state
The grow is past Day 20, with four plants (A, B, C, D) in 15L Autopot XL pots using coco/perlite (60/40) medium, running an 18/6 light schedule. The hand-watering phase is ongoing — Autopot float valves remain closed until roots reach the pot base. An AirBase disc at the bottom of each pot prevents visual root confirmation, so float valve activation will be determined by behavioral signals (increased water uptake frequency, accelerating node development, upward-reaching foliage), estimated roughly one to two weeks out.
Phenotype priority ranking:

Plants A and D — Primary candidates; showing early anthocyanin (purple) expression at stems, petioles, and cotyledons, with D showing the strongest signal. This genetic expression appearing before environmental triggers (cool temps, UV stress) is a strong positive indicator for purple bud development.
Plant C — Most vigorous and developmentally advanced (3 nodes, wide fan leaves, tight internodal spacing), but no purple expression.
Plant B — Dense, compact, healthy; no purple expression.

Current recommendation: Run all four into flower weeks 5–6 before making clone/cull decisions. Evaluate across purple depth in calyxes specifically, aroma complexity, bud structure, plant health, and stretch behavior. Clone top candidates no later than flower weeks 3–4.
Environmental targets to maintain: 74–80°F, 65–75% RH. RH has been running at the ceiling of acceptable range; temperature has been running slightly below ideal.
On the horizon

Float valve activation: Watch for behavioral signals of root establishment; likely 1–2 weeks out
Topping: At nodes 4–5 (estimated ~2–3 weeks from Day 18)
LST: Can begin now
SCROG net installation: Around weeks 6–8 of veg
12/12 flip: When SCROG net is ~70% full
Lollipopping + defoliation: Early flower
Clone selection: Flower weeks 3–4 from top phenotype candidates
Final phenotype evaluation: Flower weeks 5–6 (purple calyx depth, aroma, bud structure, stretch, health)
Monitoring system: Alex is building a Python-based automated photo capture and environmental logging system using a home media box (not Raspberry Pi)

Key learnings & principles

Anthocyanin expression before environmental triggers is a strong genetic signal for purple phenotype potential; prioritize A and D accordingly
Denver tap water runs pH 8.5–8.8 (Lead Reduction Program); pH Down required at every reservoir fill — Canna A+B's buffering does not eliminate this need. Target pH 5.8 after nutrients are added
Denver's dry climate requires active humidity management in early veg; Denver's naturally cool nights become an advantage later for amplifying anthocyanin expression during late flower
Chloramines in Denver water do not off-gas; cannot be treated by letting water sit
Canna Coco A+B already accounts for coco's calcium and magnesium demands; supplemental CalMag should be skipped unless deficiency signs appear
Runoff in Autopot trays during hand-watering phase should be removed promptly (turkey baster, sponge, or tipping); standing water risks anaerobic conditions before roots reach that zone
Watering volume during hand-watering phase: ~150–200ml targeted at stem base; expand radius gradually as roots colonize the pot
Etiolated/stretched stems can be buried at transplant — cannabis roots from buried stem tissue, resulting in stronger root systems
Early culling based on a single trait signal is risky: don't conflate one phenotype indicator with overall quality before multiple signals can be evaluated
Simplicity over optimization: Alex explicitly pushed back on over-engineered approaches; the grow plan was deliberately simplified (single top → LST → SCROG; Canna A+B as sole nutrient; no VPD tracking, no AirDomes, no multi-product nutrient stacks)
Aroma evaluation at flower weeks 5–6 should precede final clone commitment

Approach & patterns

Uses a propose-critique-refine framework for significant decisions (e.g., clone/cull timing, humidifier selection, cloning strategy)
Maintains structured markdown project files: grow-project-bible.md and progress.md at /mnt/project/, updated regularly via Claude across sessions
Progress log uses ##/### heading hierarchy, pipe-delimited per-plant tables, checkbox milestone tracking, and emoji indicators (✅/⚠️) for quick scanning
File edits use str_replace anchored on the stable footer delimiter (---\n\n*Log updated as grow progresses.*) rather than appending to end-of-file, preserving document structure
Per-plant tracking uses consistent labels (A, B, C, D) across all log entries
Checks in regularly with photos and environmental readings for plant health assessments
Documents grow decisions with rationale, not just conclusions

Tools & resources

Grow setup: VIVOSUN S448 4×4 tent; Medic Grow Fold-650 light; Autopot 4-Pot XL with 25-gallon FlexiTank reservoir; AC Infinity CLOUDLINE LITE exhaust with carbon filter; VIVOSUN AeroWave E6 Gen2 circulation fan; seedling dome (no longer active)
Medium & nutrients: Coco/perlite 60/40; Canna Coco A+B (sole nutrient line); General Hydroponics pH Down
Monitoring: TempPro sensor (inside tent); Inkbird IBS-TH3 sensor; dirt:get_latest_snapshot_tool for tent snapshots (returns cached image; 20–30 min delay needed between calls for meaningful updates)
Monitoring system (in progress): Python scripts on home media box for photo capture and environmental logging; TEMPerHUM USB HID sensor (temper-py library); Logitech C920-series webcam (UVC-compatible, manual white balance via v4l2-ctl for consistent color under grow lighting)
pH management: VIVOSUN pH meter (short-term); Bluelab pH pen noted as quality upgrade; Apera PC60 as best all-in-one option
EC monitoring: HM Digital TDS-3 (~$15)
Arduino: Arduino Nano clone with breadboard and DHT22 sensor; moisture sensor with extended cable (Dupont jumper wire extensions)
Project files: /mnt/project/grow-project-bible.md, /mnt/project/progress.md