-- atlas:txmode none

-- Drop index "ux_plant_location_current_grid_position_per_tent" from table: "plant_location_history"
DROP INDEX CONCURRENTLY "ux_plant_location_current_grid_position_per_tent";
-- Modify "plant_location_history" table
ALTER TABLE "plant_location_history" DROP CONSTRAINT "ex_plant_location_no_overlap_per_tent_grid_position", DROP CONSTRAINT "ck_plant_location_grid_position_not_blank", ADD CONSTRAINT "ck_plant_location_grid_position_not_blank" CHECK ((grid_position IS NULL) OR (btrim(grid_position) <> ''::text)), ALTER COLUMN "grid_position" DROP NOT NULL, ADD CONSTRAINT "ex_plant_location_no_overlap_per_tent_grid_position" EXCLUDE USING GIST ("tent_id" WITH =, "grid_position" WITH =, (tstzrange(start_at, COALESCE(end_at, 'infinity'::timestamp with time zone), '[)'::text)) WITH &&) WHERE (grid_position IS NOT NULL);
-- Create index "ux_plant_location_current_grid_position_per_tent" to table: "plant_location_history"
CREATE UNIQUE INDEX CONCURRENTLY "ux_plant_location_current_grid_position_per_tent" ON "plant_location_history" ("tent_id", "grid_position") WHERE ((end_at IS NULL) AND (grid_position IS NOT NULL));
