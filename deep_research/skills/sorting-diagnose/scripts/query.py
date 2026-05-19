"""SQL query wrapper for the sorting-diagnose skill.

Connects to MySQL using credentials inlined below. Prints query results as
JSON to stdout so the calling scripts can parse them.

Usage (runs directly on the host — no docker wrapper):
    python scripts/query.py --sql-file tmp/q.sql
    python scripts/query.py --sql "SELECT 1"
    python scripts/query.py --sql-file tmp/q.sql --max-rows 5000

Env overrides (optional, useful when swapping environments without re-editing
this file):
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    DB_MAX_ROWS  -- operational row-cap tuning

Exit codes:
    0 -- success; stdout: {"ok": true, "rowCount": N, "truncated": bool, "rows": [...]}
    1 -- failure; stdout: {"ok": false, "error": "...", "errorType": "..."}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor


# --- Connection parameters (inlined; bundled with the skill) -----------------
#
# Default to the local MySQL instance. Override per-environment via env vars
# (DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME) without touching this
# file.

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "123456")
DB_NAME = os.environ.get("DB_NAME", "test")

DEFAULT_MAX_ROWS = 10_000


def connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
    )


def run_sql(sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> tuple[list[dict], bool]:
    """Execute SQL, return (rows, truncated).

    The caller (a script in this directory) has already produced a fully
    materialized SQL string — no placeholder substitution happens here.
    Returns truncated=True if the row cap was hit; some rows may be missing.
    """
    conn = connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            if cursor.description is None:
                return [], False
            rows: list[dict] = []
            truncated = False
            while True:
                batch = cursor.fetchmany(1000)
                if not batch:
                    break
                for row in batch:
                    if len(rows) >= max_rows:
                        truncated = True
                        break
                    # Upper-case keys so downstream rule docs that reference
                    # EQPID / LOTID / TXNTIME / RESULT keep working regardless
                    # of the source SQL's column case.
                    rows.append({k.upper(): v for k, v in row.items()})
                if truncated:
                    break
            return rows, truncated
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run SQL against MySQL and print rows as JSON."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--sql", help="SQL string to execute")
    src.add_argument("--sql-file", help="Path to a file containing the SQL")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=int(os.environ.get("DB_MAX_ROWS", DEFAULT_MAX_ROWS)),
        help=f"Cap returned rows (default {DEFAULT_MAX_ROWS}); excess is truncated",
    )
    args = parser.parse_args()

    sql = args.sql if args.sql else Path(args.sql_file).read_text(encoding="utf-8")

    try:
        rows, truncated = run_sql(sql, max_rows=args.max_rows)
    except Exception as exc:
        json.dump(
            {"ok": False, "error": str(exc), "errorType": type(exc).__name__},
            sys.stdout,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
        return 1

    json.dump(
        {
            "ok": True,
            "rowCount": len(rows),
            "truncated": truncated,
            "rows": rows,
        },
        sys.stdout,
        default=str,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
