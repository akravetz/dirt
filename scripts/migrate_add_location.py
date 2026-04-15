"""Add `location` column to sensorreading and create sensornode table.

Idempotent: detects existing schema and skips already-applied changes.

Run from repo root:  uv run python scripts/migrate_add_location.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "dirt.db"


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def main() -> None:
    if not DB.exists():
        sys.exit(f"{DB} not found")

    conn = sqlite3.connect(DB)
    conn.isolation_level = None  # explicit transaction control

    try:
        conn.execute("BEGIN")

        # 1) sensorreading.location column
        cols = column_names(conn, "sensorreading")
        if "location" in cols:
            print("sensorreading.location already exists — skipping ADD COLUMN")
        else:
            print("adding sensorreading.location (default 'tent' backfills existing rows)")
            conn.execute(
                "ALTER TABLE sensorreading "
                "ADD COLUMN location TEXT NOT NULL DEFAULT 'tent'"
            )
            n = conn.execute(
                "SELECT COUNT(*) FROM sensorreading WHERE location = 'tent'"
            ).fetchone()[0]
            print(f"  backfilled {n} rows with location='tent'")

        # Index on location for query performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_sensorreading_location "
            "ON sensorreading (location)"
        )

        # 2) sensornode table
        if table_exists(conn, "sensornode"):
            print("sensornode table already exists — skipping CREATE TABLE")
        else:
            print("creating sensornode table")
            conn.execute(
                """
                CREATE TABLE sensornode (
                    location TEXT PRIMARY KEY,
                    ip TEXT,
                    firmware_version TEXT,
                    uptime_ms INTEGER,
                    last_seen DATETIME
                )
                """
            )
            conn.execute(
                "CREATE INDEX ix_sensornode_last_seen ON sensornode (last_seen)"
            )

        conn.execute("COMMIT")
        print("migration committed")

    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
