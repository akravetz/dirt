-- Modify "cloud_plant" table
ALTER TABLE "cloud_plant" ADD COLUMN "sex_key" character varying(40) NOT NULL DEFAULT 'unknown';
-- Modify "cloud_seed_lot" table
ALTER TABLE "cloud_seed_lot" ADD COLUMN "sex_type_key" character varying(40) NOT NULL DEFAULT 'unknown';
