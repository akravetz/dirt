-- Create "cloud_wiki_page" table
CREATE TABLE "cloud_wiki_page" (
  "wiki_key" character varying(600) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "path" character varying(500) NOT NULL,
  "title" character varying(300) NOT NULL,
  "frontmatter" json NOT NULL,
  "body_markdown" text NOT NULL,
  "sha256" character varying(64) NOT NULL,
  "source_updated_at" timestamptz NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("wiki_key"),
  CONSTRAINT "cloud_wiki_page_site_id_path_key" UNIQUE ("site_id", "path")
);
-- Create index "ix_cloud_wiki_page_path" to table: "cloud_wiki_page"
CREATE INDEX "ix_cloud_wiki_page_path" ON "cloud_wiki_page" ("path");
-- Create index "ix_cloud_wiki_page_site_id" to table: "cloud_wiki_page"
CREATE INDEX "ix_cloud_wiki_page_site_id" ON "cloud_wiki_page" ("site_id");
