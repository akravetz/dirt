-- atlas:txmode none

-- Create index "ix_cloud_plant_location_current_tent" to table: "cloud_plant_location"
CREATE INDEX CONCURRENTLY "ix_cloud_plant_location_current_tent" ON "cloud_plant_location" ("site_id", "source_tent_id", "grid_position", "source_plant_id");
