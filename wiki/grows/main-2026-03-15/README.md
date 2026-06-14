---
title: Main Grow 2026-03-15
type: grow
sources: []
related: [wiki/overview.md, wiki/breeding/README.md, wiki/daily/2026-06-10.md, wiki/environment/nutrients.md]
created: 2026-05-30
updated: 2026-06-12
---

# Main Grow 2026-03-15

## Database Identity

| Field | Value |
|---|---|
| `growrun.id` | `1` |
| `growrun.grow_run_id` | `main-2026-03-15` |
| `site.site_id` | `homebox` |
| `tent.tent_id` | `main` |
| `name` | Main grow 2026-03-15 |
| `purpose` | flower |
| `strain` | Sirius Black x BS01 |
| `germination_date` | 2026-03-15 |
| `flower_start_date` | 2026-05-03 |
| `plant_count` | 4 |

## Plants

- [Plant A](plants/plant-a.md) — database `plant.id = 1`, `plant.plant_id = a`
- [Plant B](plants/plant-b.md) — database `plant.id = 2`, `plant.plant_id = b`
- [Plant C](plants/plant-c.md) — database `plant.id = 3`, `plant.plant_id = c`
- [Plant D](plants/plant-d.md) — database `plant.id = 4`, `plant.plant_id = d`

## Current Role

This is the original four-plant SBxBS01 flower run. Plants A and D are the
primary purple keeper candidates; B and C remain secondary references. See the
current operational summary in [overview.md](../../overview.md).

As of 2026-06-12, the run is Day 90 / Flower Day 40. The main canopy remains
dense, purple, and flower-heavy; Plant A is still a watched Autopot
reconnection, Plant B returned to the high/pinned rough-moisture zone after
yesterday's drier move, Plant C remains high/flat, Plant D remains a low/probe
hand-check, and environment work is focused on dark-cycle clearing without
pushing the current lights-on window drier. The Autopot reservoir was reset on
2026-06-10 from EC well over 2.0 to pH 5.8 / EC ~0.3 plain tap water for about
24 hours. On 2026-06-12, rebuilt feed measured 1300 uS/cm / 1.3 mS/cm on the
Apera EC60, then was diluted to EC 1.0 as a conservative recovery-strength feed
after the burn/high-EC concern.

Moisture telemetry changed on 2026-06-10/11. Plant A now uses
`plant-a-substrate-node` RS485 direct-percent substrate moisture as its
canonical current moisture source. Plants B-D have no current trusted moisture
probe after the old capacitive nodes were disabled/retired, so use direct hand
checks, tray behavior, media condition, and plant posture for root-zone
decisions until replacement probes exist.
