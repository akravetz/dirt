#!/usr/bin/env python3
"""One-shot SQLite → Postgres data migration for the pg cutover (ADR-006).

Runs against a pg target that has already had the initial Atlas migration
applied (growstate/sensornode/plant/sensorcalibration/sensorreading/snapshot
tables exist + seed rows are in place). Fails fast if that prep isn't done.

Source:  var/dirt.db (the sqlite we're retiring)
Target:  the pg `dirt` database (or a rehearsal DB via --target override)

Ordering (all inside one pg transaction, rolled back on any error):
  1. Assertions: source non-empty; target has schema + seed + no user data yet.
  2. growstate: UPDATE the seeded is_current=true row with sqlite values.
  3. sensornode: UPDATE each seeded row by location with sqlite metadata.
  4. sensorcalibration: INSERT, FK'd to sensornode.id by location.
  5. sensorreading: COPY FROM STDIN in batches — the hot 200k+ rows.
  6. snapshot: bulk INSERT (4k rows; small enough for VALUES).
  7. Verify row counts vs source; COMMIT on match, else raise + ROLLBACK.

Usage:
    uv run python scripts/sqlite_to_postgres.py \\
        --source var/dirt.db \\
        --target postgresql://dirt:PASS@127.0.0.1:5432/dirt \\
        [--dry-run]

The target URL here is a plain postgresql:// (no +asyncpg) because this
script uses asyncpg directly — no SQLAlchemy indirection for the bulk path.
"""
from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import asyncpg

BATCH = 5000  # sensorreading COPY batch size

# sqlite's free-form `location` values must match the sensor_location enum on
# pg. This is also the set of rows the initial Atlas migration seeded.
VALID_LOCATIONS = {"tent", "plant-a", "plant-b", "plant-c", "plant-d", "reservoir"}
VALID_SOURCES = {"arduino", "esp32", "kasa", "mock"}


def _parse_sqlite_ts(s: str) -> datetime:
    """SQLite stores timestamps as naive TEXT (writer intent: UTC). Coerce
    to UTC-aware datetime for the timestamptz target column."""
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


async def _assert_target_is_prepared(conn: asyncpg.Connection) -> None:
    """Target must have schema applied + seed rows present + no user data yet."""
    for table in ("growstate", "sensornode", "plant", "sensorcalibration", "sensorreading", "snapshot"):
        r = await conn.fetchval(
            f"SELECT COUNT(*) FROM information_schema.tables "
            f"WHERE table_schema = 'public' AND table_name = $1",
            table,
        )
        if r == 0:
            raise RuntimeError(
                f"target pg is missing `{table}` table — apply the initial "
                "Atlas migration first: `atlas migrate apply --env local --url <target>`"
            )

    growstate_n = await conn.fetchval("SELECT COUNT(*) FROM growstate WHERE is_current = true")
    if growstate_n != 1:
        raise RuntimeError(
            f"target pg must have exactly one is_current=true growstate row (seed); got {growstate_n}"
        )
    sensornode_n = await conn.fetchval("SELECT COUNT(*) FROM sensornode")
    if sensornode_n != len(VALID_LOCATIONS):
        raise RuntimeError(
            f"target pg must have {len(VALID_LOCATIONS)} seeded sensornode rows; got {sensornode_n}"
        )
    plant_n = await conn.fetchval("SELECT COUNT(*) FROM plant")
    if plant_n != 4:
        raise RuntimeError(
            f"target pg must have 4 seeded plant rows; got {plant_n}"
        )

    # No user data yet (we're about to load it).
    for table, label in (
        ("sensorreading", "readings"),
        ("sensorcalibration", "calibration"),
        ("snapshot", "snapshots"),
    ):
        n = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
        if n > 0:
            raise RuntimeError(
                f"target pg already has {n} rows in {table} — aborting to "
                "prevent double-load. Drop + recreate the target DB if this is a rehearsal."
            )


def _src_counts(src: sqlite3.Connection) -> dict[str, int]:
    return {
        "sensorreading": src.execute("SELECT COUNT(*) FROM sensorreading").fetchone()[0],
        "sensornode": src.execute("SELECT COUNT(*) FROM sensornode").fetchone()[0],
        "sensorcalibration": src.execute("SELECT COUNT(*) FROM sensorcalibration").fetchone()[0],
        "snapshot": src.execute("SELECT COUNT(*) FROM snapshot").fetchone()[0],
        "growstate": src.execute("SELECT COUNT(*) FROM growstate").fetchone()[0],
    }


async def _load_node_ids(conn: asyncpg.Connection) -> dict[str, int]:
    """Map sensor_location string → sensornode.id."""
    rows = await conn.fetch("SELECT id, location FROM sensornode")
    return {r["location"]: r["id"] for r in rows}


async def _migrate_growstate(src: sqlite3.Connection, conn: asyncpg.Connection) -> None:
    row = src.execute(
        "SELECT germination_date, flower_start_date, lights_on_local, lights_off_local FROM growstate"
    ).fetchone()
    if row is None:
        print("[growstate] no source row; leaving seed values in place", file=sys.stderr)
        return
    germ, flower, lon, loff = row
    flower_date = None
    if flower:  # sqlite stores NULL dates as empty string in some versions
        flower_date = datetime.fromisoformat(flower).date() if "-" in str(flower) else None
    await conn.execute(
        """
        UPDATE growstate SET
            germination_date = $1,
            flower_start_date = $2,
            lights_on_local = $3,
            lights_off_local = $4
        WHERE is_current = true
        """,
        datetime.fromisoformat(germ).date() if germ else None,
        flower_date,
        datetime.strptime(lon, "%H:%M:%S").time() if lon else None,
        datetime.strptime(loff, "%H:%M:%S").time() if loff else None,
    )
    print(f"[growstate] updated current row: germ={germ} flower={flower} lights={lon}/{loff}")


async def _migrate_sensornode(src: sqlite3.Connection, conn: asyncpg.Connection) -> None:
    rows = src.execute(
        "SELECT location, ip, firmware_version, uptime_ms, last_seen FROM sensornode"
    ).fetchall()
    n = 0
    for loc, ip, fw, uptime, last_seen in rows:
        if loc not in VALID_LOCATIONS:
            print(f"[sensornode] WARN: unknown location {loc!r}, skipping", file=sys.stderr)
            continue
        ts = _parse_sqlite_ts(last_seen) if last_seen else None
        await conn.execute(
            """
            UPDATE sensornode SET
                ip = $1::inet,
                firmware_version = $2,
                uptime_ms = $3,
                last_seen = $4
            WHERE location = $5::sensor_location
            """,
            ip, fw, uptime, ts, loc,
        )
        n += 1
    print(f"[sensornode] updated {n} rows")


async def _migrate_sensorcalibration(
    src: sqlite3.Connection, conn: asyncpg.Connection, node_ids: dict[str, int]
) -> None:
    rows = src.execute(
        "SELECT location, metric, raw_low, raw_high FROM sensorcalibration"
    ).fetchall()
    records = []
    for loc, metric, raw_low, raw_high in rows:
        node_id = node_ids.get(loc)
        if node_id is None:
            print(f"[sensorcalibration] WARN: no sensornode_id for {loc!r}, skipping", file=sys.stderr)
            continue
        records.append((node_id, metric, raw_low, raw_high))
    if records:
        await conn.copy_records_to_table(
            "sensorcalibration",
            records=records,
            columns=["sensornode_id", "metric", "raw_low", "raw_high"],
        )
    print(f"[sensorcalibration] inserted {len(records)} rows")


async def _migrate_sensorreading(
    src: sqlite3.Connection, conn: asyncpg.Connection, node_ids: dict[str, int]
) -> int:
    # Stream in batches; COPY per batch. Preserves the timestamp column order
    # and the (ts, sensornode_id, metric, value, source) target column set.
    total = 0
    warned_locs = set()
    warned_sources = set()
    cur = src.execute(
        "SELECT timestamp, location, metric, value, source FROM sensorreading ORDER BY id"
    )
    batch: list[tuple] = []

    def _flush_sync_capture() -> list[tuple]:
        # swap + return the current batch, then reset
        nonlocal batch
        out = batch
        batch = []
        return out

    while True:
        rows = cur.fetchmany(BATCH)
        if not rows:
            break
        for ts_str, loc, metric, value, source in rows:
            if loc not in VALID_LOCATIONS:
                if loc not in warned_locs:
                    print(f"[sensorreading] WARN: unknown location {loc!r}, skipping all", file=sys.stderr)
                    warned_locs.add(loc)
                continue
            if source not in VALID_SOURCES:
                if source not in warned_sources:
                    print(f"[sensorreading] WARN: unknown source {source!r}, skipping all", file=sys.stderr)
                    warned_sources.add(source)
                continue
            node_id = node_ids.get(loc)
            if node_id is None:
                continue  # shouldn't happen post-assertion but be defensive
            batch.append((
                _parse_sqlite_ts(ts_str),
                node_id,
                metric,
                float(value),
                source,
            ))
            if len(batch) >= BATCH:
                await conn.copy_records_to_table(
                    "sensorreading",
                    records=_flush_sync_capture(),
                    columns=["ts", "sensornode_id", "metric", "value", "source"],
                )
                total += BATCH
                if total % 50000 == 0:
                    print(f"[sensorreading] migrated {total:,}...", file=sys.stderr)
    if batch:
        await conn.copy_records_to_table(
            "sensorreading",
            records=batch,
            columns=["ts", "sensornode_id", "metric", "value", "source"],
        )
        total += len(batch)
    print(f"[sensorreading] inserted {total:,} rows")
    return total


async def _migrate_snapshot(src: sqlite3.Connection, conn: asyncpg.Connection) -> int:
    rows = src.execute("SELECT timestamp, file_path FROM snapshot ORDER BY id").fetchall()
    records = [(_parse_sqlite_ts(ts), path) for ts, path in rows]
    if records:
        await conn.copy_records_to_table(
            "snapshot",
            records=records,
            columns=["ts", "file_path"],
        )
    print(f"[snapshot] inserted {len(records)} rows")
    return len(records)


async def _verify(
    src_counts: dict[str, int], conn: asyncpg.Connection, migrated_readings: int, migrated_snapshots: int,
) -> None:
    dst_readings = await conn.fetchval("SELECT COUNT(*) FROM sensorreading")
    dst_cal = await conn.fetchval("SELECT COUNT(*) FROM sensorcalibration")
    dst_snap = await conn.fetchval("SELECT COUNT(*) FROM snapshot")
    print(
        f"[verify] src readings={src_counts['sensorreading']:,}, "
        f"dst={dst_readings:,}, migrated={migrated_readings:,}"
    )
    print(f"[verify] src cal={src_counts['sensorcalibration']}, dst={dst_cal}")
    print(f"[verify] src snap={src_counts['snapshot']}, dst={dst_snap}, migrated={migrated_snapshots}")

    # Readings count can differ from src if we skipped unknown locations /
    # sources, but migrated count must match dst count.
    if dst_readings != migrated_readings:
        raise RuntimeError(
            f"sensorreading count mismatch: dst={dst_readings} vs migrated={migrated_readings}"
        )
    if dst_cal != src_counts["sensorcalibration"]:
        raise RuntimeError(
            f"sensorcalibration count mismatch: src={src_counts['sensorcalibration']} vs dst={dst_cal}"
        )
    if dst_snap != migrated_snapshots:
        raise RuntimeError(
            f"snapshot count mismatch: dst={dst_snap} vs migrated={migrated_snapshots}"
        )


async def main_async(args: argparse.Namespace) -> int:
    src_path = Path(args.source).resolve()
    if not src_path.exists():
        print(f"source sqlite not found: {src_path}", file=sys.stderr)
        return 2
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)

    counts = _src_counts(src)
    print(f"[source] {src_path}: {counts}")
    if counts["sensorreading"] == 0:
        print("source sqlite has zero readings — nothing to migrate", file=sys.stderr)
        return 2

    # asyncpg wants a plain postgresql:// URL (not +asyncpg).
    target_url = args.target.replace("+asyncpg", "")
    conn: asyncpg.Connection = await asyncpg.connect(target_url)

    try:
        async with conn.transaction():
            await _assert_target_is_prepared(conn)
            node_ids = await _load_node_ids(conn)

            if args.dry_run:
                print("[dry-run] target is prepared; stopping before writes.")
                return 0

            await _migrate_growstate(src, conn)
            await _migrate_sensornode(src, conn)
            # Reload node_ids in case sensornode ids shifted (they shouldn't,
            # but the seeded rows are the same rows we just updated).
            node_ids = await _load_node_ids(conn)
            await _migrate_sensorcalibration(src, conn, node_ids)
            migrated_readings = await _migrate_sensorreading(src, conn, node_ids)
            migrated_snapshots = await _migrate_snapshot(src, conn)

            await _verify(counts, conn, migrated_readings, migrated_snapshots)
            print("[ok] migration complete — committing transaction.")
    finally:
        await conn.close()
        src.close()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Migrate dirt SQLite data to Postgres.")
    p.add_argument("--source", required=True, help="path to source sqlite db (e.g. var/dirt.db)")
    p.add_argument("--target", required=True, help="target pg URL (postgresql://user:pass@host:port/db)")
    p.add_argument("--dry-run", action="store_true", help="connect + verify target prep; do not write")
    args = p.parse_args()
    try:
        return asyncio.run(main_async(args))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
