// Atlas config — Dirt. See docs/references/atlas/INDEX.md.
//
// SQLModel classes in apps/shared/src/dirt_shared/models/ are the single
// source of truth. scripts/atlas-load-sqlmodel.py renders them as DDL
// that Atlas uses as the "desired state" for migration diffs.
//
// Usage:
//   set -a; source .env; set +a                     # load DIRT_PG_* into shell env
//   atlas migrate diff <name>    --env local        # write a new migrations/*.sql
//   atlas migrate apply          --env local        # apply to local pg
//   atlas migrate lint           --env local --latest 1
//
// Dev-db is Docker-ephemeral (docker://postgres/17/dev) — Atlas spins a
// short-lived postgres:17 container per diff. Cannot accidentally hit
// prod even if misconfigured.

data "external_schema" "sqlmodel" {
  program = [
    "uv", "run", "--package", "dirt-shared",
    "python", "scripts/atlas-load-sqlmodel.py",
    "postgresql",
  ]
}

variable "pg_password" {
  type    = string
  default = getenv("DIRT_PG_PASSWORD")
}

variable "migration_dir" {
  type    = string
  default = "file://migrations"
}

// Local — the single live `dirt` database on 127.0.0.1:5432.
env "local" {
  src = data.external_schema.sqlmodel.url
  dev = "docker://postgres/17/dev?search_path=public"
  url = "postgres://dirt:${var.pg_password}@127.0.0.1:5432/dirt?sslmode=disable&search_path=public"

  migration {
    dir = var.migration_dir
  }

  diff {
    concurrent_index {
      create = true
      drop   = true
    }
  }
}

// CI — diff + lint only. No prod url; CI workflow passes --url for apply.
env "ci" {
  src = data.external_schema.sqlmodel.url
  dev = "docker://postgres/17/dev?search_path=public"

  migration {
    dir = var.migration_dir
  }
}
