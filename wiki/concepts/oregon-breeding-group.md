---
title: Oregon Breeding Group (OBG) — Wayne, Serious Black, and the BS01 breeding-stock pack
type: concept
sources: []
related: [wiki/overview.md, wiki/concepts/plant-training-methods.md, wiki/concepts/anthocyanin.md]
created: 2026-04-24
updated: 2026-04-24
---

# Oregon Breeding Group (OBG) — Wayne, Serious Black, and the BS01 breeding-stock pack

The seeds for the current grow (Serious Black feminized) come from **Oregon Breeding Group**, founded and run by **Wayne**. This page exists because (a) the seller relationship turns out to be much more substantive than a routine seed purchase, and (b) the next grow is being planned as a small breeding program built around a second pack — `BS01` — that Wayne included with the original order.

> **Key fact for next-grow planning:** the current pack of feminized Serious Black is one of two packs we received. The second is `BS01` ("Breeding Stock 01"), regular (non-feminized) seeds that Wayne included specifically so the buyer could grow males, harvest pollen, and pollinate selected female phenotypes from the feminized pack. We did not understand what BS01 was at the time of receipt; clarified via email exchange with Wayne on 2026-04-24.

## The breeder — Wayne / Oregon Breeding Group

Source: direct email correspondence with Wayne on 2026-04-24 (kept in personal mail; not in `raw/` yet — should be archived there if we want it durable).

What we know:

- Wayne founded Oregon Breeding Group and is the breeder behind **Serious Black** (the strain currently in tent).
- He has been growing cannabis since the 1970s.
- He's personally connected to the original breeders of **White Widow** and **Gorilla Glue #4** — two lineages that anchor a lot of modern hybrid genetics.
- He shared his breeding philosophy in detail in the email thread (specifics not yet captured here — *TODO: extract notes from the email and add a "Wayne's breeding theory" section*).

This is rare and valuable: most retail seed sellers have no operator-level breeding context to offer. Wayne does, and explicitly engages with hobbyists who want to do phenotypic selection rather than just grow flower.

## What we have on hand

Two packs received on the original order. Both have been germinated/inventoried distinctly.

| Pack | Type | Seed count | Status | Use |
|---|---|---:|---|---|
| **Serious Black (feminized)** | Feminized — all seeds will produce female plants | 10 (originally) | 4 currently growing as plants A/B/C/D; 6 unplanted in storage | Current grow + next grow's main pop |
| **BS01 — Breeding Stock 01** | Regular — ~50/50 male/female | unknown count, in storage | Unplanted | Next grow: harvest pollen from males, use to pollinate selected feminized phenotypes |

Additionally: more feminized seeds have been ordered (2026-04-24, in transit). Exact strain TBD — confirm against shipping notification when it arrives.

## Plan: next grow as a phenotypic selection + breeding run

This is a deliberate departure from the current grow's "4 plants, optimize yield" approach. Goal: characterize the genotype space we have, identify the phenotypes worth preserving, and produce our own F1 seed for future grows.

**Phase A — Population grow:**
- Grow out all 10 feminized seeds (or however many are in the new pack — confirm count).
- Grow out a subset of BS01 (start with ~6–8 to guarantee at least 2–3 males survive; see *Sex-test note* below).
- Same environment, same media, same nutrients as current grow — control for environment so phenotype variation traces to genotype.

**Phase B — Phenotypic selection:**
- Score each feminized plant on a structured rubric:
  - Vigor (height, internode density, branching)
  - Anthocyanin expression (purple) — see [`concepts/anthocyanin.md`](anthocyanin.md)
  - Stress tolerance (any deficiencies, training response)
  - Aroma profile during late veg / early flower
  - Trichome production at week 4 of flower
  - Yield (final dry weight per plant)
  - Anything else we identify as worth tracking — *add to plant-page templates before grow starts*
- Score each BS01 male on early vigor, structure, aroma (pre-flower trichomes have weak signal in males but stalk diameter, branching, and pollen-sac density are useful proxies).

**Phase C — Pollen collection + breeding:**
- Isolate selected BS01 male(s) (separate space + air handling — pollen contamination of the main flower room would ruin the rest of the grow's bag yield).
- Collect pollen on parchment paper or silicone mat. Dry, then store in airtight desiccated container with silica beads, frozen if not using immediately.
- Selectively pollinate one or two branches on the top-scoring feminized phenotypes — leave the rest of those plants untouched for normal flower harvest.
- Harvest seed at maturity (~6 weeks after pollination). Cure, label by parent pair, archive.

**Phase D — F1 evaluation grow (a future grow, not the next one):**
- Germinate F1 seeds, grow ~10 of each cross, score same rubric, identify keepers.
- Iterate: backcross to parent for stabilization, sib-cross for diversity, etc. — depends on what Wayne recommends in follow-up email exchange.

**Sex-test note:** for the BS01 regular pack, there's a real win in PCR-based sex testing at seedling stage (~$25/sample, results in days) — kills the ~50% of seedlings that turn out female before they consume tent space. See *Genomics + ML opportunities* below for vendor options.

## Operational risks specific to a breeding run

These are NOT in the standard grow-page recommendations and need to be planned for:

- **Pollen contamination** is catastrophic and silent. One stray grain from a male in the main flower room will seed the buds across every plant — dropping potency, making the harvest unsmokable, and ruining the phenotype-selection signal. **Hard requirement: physical and air-handling separation between male isolation room and main flower tent.** Negative pressure on the male room ideally; minimum is a closed door + opposite-side ventilation.
- **Male timing.** Males show sex 1–2 weeks earlier than females in flower, but in regular seed packs you can sometimes spot pre-flowers in late veg with a loupe. Identify and isolate males the moment sex is confirmed; do not let them shed pollen in the main tent even briefly.
- **Hermaphrodite watch.** Stress-induced hermies on feminized plants can self-pollinate even without our intentional male — track every plant for late-flower pistil-on-banana intersex. Has implications for phenotype evaluation rubric (deduct heavily for hermie tendency — that genetic doesn't get carried forward).
- **Storage of harvested seed.** Cool, dark, dry. ~5 °C in a sealed jar with silica beads is the standard. Label each cross with parent IDs (e.g. `SB-A x BS01-3`).

## Genomics + ML opportunities

> Full bioinformatics pipeline (alignment, variant calling, SnpEff annotation, kinship/PCA, MAS workflow) is documented separately at [`concepts/cannabis-genomics.md`](cannabis-genomics.md). This section is the procurement + ROI summary; that page is the operational manual.

Researched 2026-04-24. The market for cannabis genomics has consolidated since 2020 — most boutique services either died (Steep Hill, Anandia's old SSR offering) or pivoted to corporate-only sales (NRGene, Phylos's seed business). The hobbyist-accessible options reduce to three vendors and four cost tiers:

### Recommended stack at this scale

| Tier | Action | Cost | When to do it |
|---|---|---:|---|
| **Pure ROI** | PCR sex test on every BS01 seedling — [Farmer Freeman EZ-XY](https://farmerfreeman.com/) | **$8–10/sample**, 1–2 day turnaround, 99.5% claimed accuracy | Day 14–21 of veg, before males consume canopy + nutrients |
| **High-value, finite** | Whole-genome sequencing on the 2–3 keeper mothers + 1–2 selected breeding males — [Medicinal Genomics StrainSEEK WGS](https://medicinalgenomics.com/cannabis-sequencing/) | **$547/sample**, ~10× depth, raw FASTQ + cannabinoid/terpene gene report, published to Kannapedia | Once phenotype rubric has identified keepers (end of flower for moms, late veg for males) |
| **Skip** | CannaSNP90 chip ($249) | — | Less data than WGS for half the price; FASTQ is extensible (re-query against new GWAS papers as they publish), SNP chip results aren't |
| **Skip until N≥100** | Genomic prediction (GBLUP, BLUP, BayesB) | $0 + your time | At N=10–30 the kinship matrix is too sparse; you'd be fitting noise. Crop-genetics consensus needs 200–500 phenotyped+genotyped plants before GS beats simple phenotypic selection |

Total realistic 2026 spend: **~$80 for sex tests on a BS01 batch + ~$1500–2200 for WGS on 3–4 keepers ≈ $1600–2300 over the breeding cycle.** Per-grow this is small.

### What you can actually do with the WGS data

The published QTL/GWAS literature is now dense enough for marker-assisted selection at this scale, not just at corporate scale:

- **Cannabinoid chemotype (Type I/II/III)** is essentially a single-locus call from any WGS. Trivial.
- **High-PVE single SNPs from [Ronne et al. 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12104491/)** (174 accessions, ~282k SNPs, 33 significant markers) — standout examples: SNP_1 chr9 explains 96% of CBGA variance; SNP_12 chr7 explains 89% of CBC variance. The chr7 ~60 Mb haplotype covers THCAS/CBDAS together. Genotype these markers in your keepers and you have a *defensible* prediction for the F1's cannabinoid profile *before* you run an evaluation grow.
- **Terpene profile** is messier — three genomic regions correlate with the four terpenes that drive sativa/indica perception ([Watts et al. 2021, Nature Plants](https://www.nature.com/articles/s41477-021-01003-y)) — but still informs cross design.
- **Pedigree confirmation + relatedness.** With WGS on parents + cheap targeted PCR on F1 seedlings (~$5–10/marker), you can confirm a cross is what you think it is and avoid accidental selfing. Tools: `plink --pca`, `vcftools --relatedness2`, `ADMIXTURE` for population structure with N as low as ~10. (Full how-to in [`cannabis-genomics.md`](cannabis-genomics.md#population-structure--relatedness).)
- **Reference assemblies for variant calling** — CBDRx and Jamaican Lion. Pipeline: `bwa-mem2` → `bcftools` → SnpEff. (Full how-to in [`cannabis-genomics.md`](cannabis-genomics.md#variant-calling).)

### Why ML on grow observations + genotype isn't the right move yet

Honest assessment: at N=10–30 plants over a few years, **the binding constraint on selection accuracy is your phenotype matrix, not your genotype data.** Our sensor history per plant + daily photos + cannabinoid assays at harvest already give us a richer phenotype representation than most hobbyist breeding programs ever build. Adding WGS on the keepers makes it a *defensible* dataset (genotype + phenotype, properly paired). But fitting GBLUP / Bayesian-prior models requires training sets of 200–500 paired plants before they'd outperform "look at the rubric, pick the best." We're an order of magnitude under that.

The actually-useful ML application at this scale is *small and specific*: image-based phenotyping. Trichome maturity scoring from macro photos (already a published research direction with off-the-shelf YOLOv8 weights), color-band extraction for anthocyanin scoring across plants, leaf-symptom classification — these benefit from the daily photo dataset we're already producing and don't need genotype data at all.

**Bottom-line plan** (revised after research): sex-test BS01 seedlings, WGS our 3–4 keeper-tier plants, genotype-confirm any F1 cross we keep going forward, and treat the phenotype matrix as the primary asset. Defer genomic-prediction modeling indefinitely.

## Open follow-ups

- [ ] Archive the email thread with Wayne into `raw/references/` so it's durable beyond the personal inbox.
- [ ] Extract Wayne's breeding theory from the email and add a "Wayne's breeding theory" section above.
- [ ] Confirm BS01 seed count + confirm strain name on the new feminized pack when it arrives.
- [ ] Decide on the male isolation space + air handling before the next grow starts.
- [ ] Build a phenotype-scoring rubric template into a plant-page format that supports cross-plant comparison.
- [ ] Append the genomics research findings (research agent in flight).
