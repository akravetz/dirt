---
title: Grow Runs
type: index
created: 2026-05-30
updated: 2026-06-14
---

# Grow Runs

Grow folders are historical/documentation organization. Current database plant
identity is the integer `plant.id`; the durable human-facing label is
`plant.key`. Existing folder names remain stable so old daily links keep
working, but they are no longer database identity or plant scope.

| Grow folder | Current database scope | Site | Tent | Purpose | Plant keys |
|---|---|---|---|---|---|
| [Main grow 2026-03-15](main-2026-03-15/README.md) | current `plant_location_history` rows for tent `main` | `homebox` | `main` | Flower / phenotype candidate run | `SBBS-R1-001` through `SBBS-R1-004` |
| [Track A pollen run](breeding-track-a-2026-04-28/README.md) | current/historical plant rows for tent `breeding` | `homebox` | `breeding` | R2 pollen collection | `SBBS-R1-006` retained; `SBBS-R1-005`, `SBBS-R1-007`, `SBBS-R1-008`, `SBBS-R1-009` culled/not retained |

## Structure

- `grows/<historical-grow>/README.md` — historical grow-level status, current scope, and plant list.
- `grows/<historical-grow>/plants/*.md` — plant-level historical pages; identify plants in page text by `plant.id` and `plant.key`.
- Daily observations remain canonical in [`daily/`](../daily/); grow and plant pages summarize and link back to them.
