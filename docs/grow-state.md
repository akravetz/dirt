# Grow State

Read before writing any code that branches on stage (veg / flower_early / flower_late) or that needs the current germination/flower-flip date.

## Current grow

- **Germination date:** 2026-03-15 (authoritative: `growstate.germination_date` in the Postgres `dirt` database; inspect with `set -a; source .env; set +a; PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt`).
- **Flower start date:** not yet set (still in vegetative stage). Once flower is flipped, `growstate.flower_start_date` becomes the authoritative source.

## Deriving stage without the DB

- If `flower_start_date` is NULL (or `today` is before it) → `veg`.
- If set and `today - flower_start_date < 21` → `flower_early`.
- If ≥ 21 → `flower_late`.

See `apps/shared/src/dirt_shared/services/grow_state.py` for the canonical logic and `STAGE_TARGETS` (temp/RH/VPD bands per stage).

## Update procedure

Update **this file** whenever the grow is flipped, terminated, or a new grow is started — don't rely on the DB alone, since agents without DB access still need to know the stage.
