---
title: Cannabis genomics — reference assemblies, variant calling, MAS, and population structure
type: concept
sources: []
related: [wiki/concepts/oregon-breeding-group.md]
created: 2026-04-24
updated: 2026-04-24
---

# Cannabis genomics — reference assemblies, variant calling, MAS, and population structure

Reference page for the bioinformatics tooling and concepts behind the breeding program scoped in [`oregon-breeding-group.md`](oregon-breeding-group.md). Read in order; later sections build on earlier ones.

The headline use case: take whole-genome sequencing data from our keeper plants (~$547/sample from MGC StrainSEEK), turn the raw reads into a queryable database of biological hypotheses about each plant, and use that to make defensible breeding decisions (parent-pair selection, pedigree confirmation, chemotype prediction).

## The pipeline at a glance

```
your_plant.fastq          ← raw reads (~100M short 150 bp fragments) from MGC
       │
       │  bwa-mem2 align against reference assembly
       ▼
your_plant.bam            ← reads positioned on reference coordinates
       │
       │  bcftools mpileup | bcftools call
       ▼
your_plant.vcf            ← list of every position where you differ from ref
       │
       │  SnpEff annotate
       ▼
your_plant.annotated.vcf  ← variants tagged with gene + predicted impact
       │
       │  plink / vcftools / R
       ▼
analyses                  ← PCA, kinship, MAS queries
```

Each box is open-source, runs locally on a workstation, and is well-documented. No proprietary tooling, no cloud dependencies. The expensive part is the wet-lab sequencing; the analysis is free.

## Reference assemblies

A **reference assembly** is one canonical complete genome sequence for the species, used as a coordinate system everyone agrees on. When MGC sequences your plant, you don't get back a clean linear genome — you get back ~100M short reads (~150 bp each) scattered randomly across the genome, like a book that's been shredded. The reference is the index you align fragments against to figure out where each one goes.

Two high-quality cannabis references are public:

- **CBDRx** — assembled from a CBD-dominant (Type III) chemotype. NCBI BioProject `PRJEB29284`. The most-cited reference; most published cannabis GWAS hits anchor to its coordinates.
- **Jamaican Lion** — assembled from a THC-dominant (Type I) chemotype. Useful comparison reference if your plant is closer to Type I.

Either works for our use case — both are well-curated, both are the coordinate systems the literature anchors to. Pick whichever the upstream tutorial or paper you're following uses, and stay consistent across all plants in the same analysis (mixing references in one VCF is a coordinate-system error you can't easily recover from).

A typical cannabis plant differs from CBDRx at roughly **3–5 million sites** (a SNP density of ~0.5%). Most are silent / intergenic; a small fraction land in functional regions and matter.

## Variant calling

The standard pipeline:

```bash
# 1. Index the reference (one-time)
bwa-mem2 index cbdrx.fa
samtools faidx cbdrx.fa

# 2. Align reads to reference, produce sorted BAM
bwa-mem2 mem -t 16 cbdrx.fa your_plant_R1.fq.gz your_plant_R2.fq.gz \
  | samtools sort -@ 8 -o your_plant.bam
samtools index your_plant.bam

# 3. Call variants
bcftools mpileup -f cbdrx.fa your_plant.bam \
  | bcftools call -mv -Oz -o your_plant.vcf.gz
bcftools index your_plant.vcf.gz
```

Output is **VCF (Variant Call Format)** — a tab-separated table where each row is one position where your plant differs from the reference. A row looks like:

```
chr7    25302447    .    G    A    .    PASS    DP=42;...    GT:DP    0/1:42
```

Translation: at chromosome 7, position 25,302,447, the reference has `G` but your plant has `A`. Sequencing depth at that site was 42 reads. Genotype is `0/1` (heterozygous — you got the reference allele from one parent and the alternate from the other).

Useful filtering: `bcftools view -e 'QUAL<20 || DP<10'` drops low-confidence calls before downstream analysis.

## SnpEff — turning positions into biology

A raw VCF is information-free without context. `chr7:25,302,447 G→A` doesn't mean anything to a human. **SnpEff** is the annotator that joins each variant against the reference's gene model and adds biological meaning:

```bash
snpeff -v cannabis_sativa your_plant.vcf.gz > your_plant.annotated.vcf
```

The same row now reads:

```
chr7  25302447  .  G  A  ...  ANN=A|missense_variant|MODERATE|THCAS|GENE_THCAS|...|c.860G>A|p.Arg287Lys
```

Translation: "this G→A change is a missense mutation in the THCA-synthase gene, predicted MODERATE impact, changes amino acid 287 from Arginine to Lysine."

The annotated VCF is now queryable. Useful queries for breeding decisions:

- **"Show all HIGH-impact variants in cannabinoid synthase genes"** — finds broken alleles that explain chemotype. A heterozygous STOP_GAINED in CBDA-synthase is the canonical Type II (mixed THC+CBD) signature.
- **"Does this male carry the chr9 SNP_1 variant Ronne et al. associate with high CBGA?"** — cross-references a known QTL.
- **"Are any of my keepers homozygous for the loss-of-function CBDA allele?"** — those will produce pure-THC F1s if the other parent is also CBDA-null.

Without SnpEff: VCF is a 3M-row CSV of differences. With SnpEff: VCF is a queryable database of biological hypotheses about your plant.

The cannabis annotation database is bundled with SnpEff (or buildable from the public GFF files that ship with CBDRx / Jamaican Lion).

## Marker-assisted selection (MAS)

Pre-genotyping breeding decisions are made by phenotype: grow the plant out, harvest, assay, score. With MAS we can shortcut some of those decisions using **published QTLs** — single SNPs or haplotypes the literature has shown to explain a large fraction of variance in a trait.

The most useful current paper for our purposes: [Ronne et al. 2025, Plant Genome](https://pmc.ncbi.nlm.nih.gov/articles/PMC12104491/) — GWAS on 174 drug-type accessions, ~282k SNPs, **33 significant markers** for 11 cannabinoid traits. Standout high-PVE single SNPs:

| Locus | Trait | % variance explained | Notes |
|---|---|---:|---|
| chr9 SNP_1 | CBGA | **96%** | Single-locus call |
| chr7 SNP_12 | CBC | **89%** | Single-locus call |
| chr7 ~60 Mb haplotype | THCA / CBDA ratio | (block) | Covers THCAS + CBDAS together |

Workflow: WGS the keepers → annotate with SnpEff → query the annotated VCF for genotype at these specific loci → predict F1 chemotype before flower harvest.

For terpenes the picture is messier: [Watts et al. 2021, Nature Plants](https://www.nature.com/articles/s41477-021-01003-y) found three genomic regions correlate with the four terpenes that drive sativa/indica perception, but no single dominant SNP. Still informs cross design at the haplotype level.

## Population structure & relatedness

Once you have VCFs for multiple plants — call it `combined.vcf.gz` — you can analyze the **genetic relationships among them**. Three flavors:

### Kinship matrix

A pairwise number between 0 (unrelated) and 1 (clonally identical) for every pair of plants. Useful coefficients:

- Full siblings ≈ 0.5
- Half siblings ≈ 0.25
- Parent-offspring = 0.5
- Unrelated ≈ 0
- Clones / selfed F1s ≈ 1.0

Compute with `vcftools --vcf combined.vcf --relatedness2`. For our breeding program:

- **Inbreeding-risk gauge.** Crossing two BS01 brothers (kinship 0.5+) carries inbreeding-depression risk. The number tells you when you've drifted too tight.
- **Pedigree validation.** Each F1 seedling should have ~0.5 kinship with each putative parent. A seedling that comes back at 0.05 was accidentally selfed or pollen-contaminated — quarantine it from the keeper pool.

### Principal component analysis (PCA)

Squash the millions-of-SNPs matrix down to 2–3 axes you can plot. Plants that group together on the PCA plot are genetically similar; plants in different corners are diverse.

```bash
plink --vcf combined.vcf.gz --pca 5 --out combined_pca
# Then plot combined_pca.eigenvec in R / Python
```

For our breeding program:

- **Heterosis prediction.** Hybrid vigor (the F1 outperforming both parents) tends to show up when parents are far apart on the PCA. If you have 3 candidate males × 3 candidate females, pick the pair with maximum PCA distance.
- **Off-type detection.** A "BS01" seedling that lands in a totally different cluster than the other BS01 sibs was mislabeled or the pack was contaminated. Drop it before it confuses your phenotype matrix.

### ADMIXTURE — ancestry decomposition

Assumes there are K ancestral source populations (you pick K, e.g. 3) and estimates "this plant is 60% population A, 30% population B, 10% population C."

```bash
admixture combined.bed 3   # K=3
```

ADMIXTURE shines when you have **hundreds of plants from multiple known landraces**. With our pack of N=10–30 home-grow descendants from one breeder, kinship + PCA cover the practical needs and ADMIXTURE adds little. Revisit once we're crossing across multiple breeder lines or thousands of generations deep.

## What we'd actually do for the breeding program

Concrete sequence for the next-grow + first F1 cycle:

1. **PCR sex-test** every BS01 seedling (~$10/sample) at day 14–21. Cull males that aren't candidates.
2. **WGS** the 2–3 keeper-tier feminized phenotypes + 1–2 selected breeding males ($547 each, MGC StrainSEEK). Total: 3–5 samples × $547 ≈ $1500–2500.
3. **Variant call + SnpEff annotate** each FASTQ locally.
4. **MAS query** each keeper for chemotype-predictive SNPs (chr7 + chr9 from Ronne 2025). Predicts F1 cannabinoid profile *before* the F1s are even germinated.
5. **PCA + kinship** across all 3–5 sequenced plants. Pick the male × female pair with maximum PCA distance for the first cross (heterosis-likely).
6. **Pollinate, harvest seed, label by parent pair** (`SB-A × BS01-3`, etc.).
7. **F1 evaluation grow** (a future grow): germinate ~10 seeds per cross, score the standard rubric. For each kept F1, run a cheap targeted PCR (~$5–10/marker) at the chr7/chr9 chemotype loci to confirm the cross is what we think it is and the F1 inherited the predicted chemotype variants.

Total realistic 2026 spend: **~$80 sex tests + ~$1500–2500 WGS + ~$50–100 confirmation PCRs ≈ $1700–2700 per breeding cycle.**

## What ML can and can't do for us at this scale

**Can't.** Genomic prediction (GBLUP, BayesB, rrBLUP) needs training sets of 200–500 phenotyped+genotyped plants before it outperforms phenotypic selection. At N=10–30 we'd be fitting noise. R packages (`rrBLUP`, `BGLR`, `sommer`) work fine on cannabis VCFs, but they're not where the value lives at this scale.

**Can.** Image-based phenotyping from our daily photo dataset — trichome maturity scoring (off-the-shelf YOLOv8 weights work), color-band extraction for anthocyanin scoring, leaf-symptom classification. These benefit from data we're already producing and don't need genotype data at all. Standalone work item, not blocked on the breeding program.

## References

- [Medicinal Genomics — StrainSEEK Whole Genome](https://medicinalgenomics.com/cannabis-sequencing/) — the sequencing service we'd use ($547/sample, ~10× depth, raw FASTQ + report)
- [Ronne et al. 2025 — Cannabinoid QTL GWAS, Plant Genome](https://pmc.ncbi.nlm.nih.gov/articles/PMC12104491/) — the published QTL set we'd query against
- [Watts et al. 2021 — Terpene synthase GWAS, Nature Plants](https://www.nature.com/articles/s41477-021-01003-y) — terpene QTL paper
- [CBDRx reference — NCBI BioProject PRJEB29284](https://www.ncbi.nlm.nih.gov/bioproject/PRJEB29284)
- [bcftools manual / variant calling howto](https://samtools.github.io/bcftools/howtos/variant-calling.html)
- [SnpEff documentation](http://pcingola.github.io/SnpEff/)
- [PLINK documentation](https://www.cog-genomics.org/plink/2.0/)
