---
title: Grow Runs
type: index
created: 2026-05-30
updated: 2026-06-14
---

# Grow Runs

Grow pages are scoped to the database `growrun` model. The stable wiki folder
name is the database `grow_run_id`; individual plant pages live under that grow
because plant identifiers are unique per grow run, not globally.

| Grow run | Database key | Site | Tent | Purpose | Plants |
|---|---|---|---|---|---|
| [Main grow 2026-03-15](main-2026-03-15/README.md) | `growrun.grow_run_id = main-2026-03-15` (`growrun.id = 1`) | `homebox` | `main` | Flower / phenotype candidate run | A-D |
| [Track A pollen run](breeding-track-a-2026-04-28/README.md) | `growrun.grow_run_id = breeding-track-a-2026-04-28` (`growrun.id = 2`) | `homebox` | `breeding` | R2 pollen collection | R2 retained; R1/R3/R4/R5 culled/not retained |

## Structure

- `grows/<grow_run_id>/README.md` — grow-level status, database mapping, and plant list.
- `grows/<grow_run_id>/plants/plant-<plant_id>.md` — plant-level view for the plant row whose `plant.plant_id` matches that file name.
- Daily observations remain canonical in [`daily/`](../daily/); grow and plant pages summarize and link back to them.
