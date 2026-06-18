# Grow State

Read before writing any code that branches on stage (veg / flower_early / flower_late) or that needs the current germination/flower-flip date.

## Current grow

- **Germination date:** 2026-03-15 (authoritative: the earliest `plant.germinated_at` among current `homebox/main` plant locations, where `plant_location_history.end_at IS NULL`; inspect with `set -a; source .env; set +a; PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt`).
- **Flower start date:** 2026-05-03 (authoritative: the earliest non-null `plant.flower_started_at` among current `homebox/main` plant locations).
- **Light schedule:** 12/12, lights on 09:00-21:00 local tent time (`America/Denver`; authoritative: enabled current main `schedule` row with `kind='lights'`).

## Breeding tent

- **Germination date:** 2026-04-28 (authoritative: earliest `plant.germinated_at` among current `homebox/breeding` plant locations).
- **Flower start date:** 2026-05-24 (authoritative: earliest non-null `plant.flower_started_at` among current `homebox/breeding` plant locations).
- **Light schedule:** 18/6, lights on 06:00-00:00 local tent time (`America/Denver`; authoritative: enabled current breeding `schedule` row with `kind='lights'`).

## Deriving stage without the DB

- If `flower_start_date` is NULL (or `today` is before it) → `veg`.
- If set and `today - flower_start_date < 21` → `flower_early`.
- If ≥ 21 → `flower_late`.

See `apps/shared/src/dirt_shared/services/grow_state.py` for the canonical logic and `STAGE_TARGETS` (temp/RH/VPD bands per stage).

## Update procedure

Update **this file** whenever the grow is flipped, terminated, or a new grow is started — don't rely on the DB alone, since agents without DB access still need to know the stage.
