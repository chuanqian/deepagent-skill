#!/usr/bin/env python3
"""INTERNALPRI rule: fetch (eventtime, internalpriority) events for a lot in a window.

Source: rpt6.lot_history. The caller (the rule logic in
rules/internalpri.md §4) filters out the three sentinel values
{None, 0, -9999} to get effective events.

eventtime is a DATETIME column; MySQL accepts ISO-8601 strings directly
in range comparisons, so we compare the raw string literals without any
explicit date-parsing function.

Usage:
    python scripts/internalpri_history.py \\
        --lotid LOT0001 \\
        --start '2025-05-14 09:00:00' --end '2025-05-14 09:30:00'
"""

from __future__ import annotations

import argparse
import sys

from _common import (
    emit_error,
    escape_sql_string,
    validate_time,
    write_sql_and_run,
)


def build_sql(lotid: str, starttime: str, endtime: str) -> str:
    lotid_s = escape_sql_string(lotid)
    starttime_s = escape_sql_string(starttime)
    endtime_s = escape_sql_string(endtime)
    return (
        "SELECT\n"
        "  eventtime,\n"
        "  internalpriority\n"
        "FROM rpt6.lot_history\n"
        "WHERE 1=1\n"
        f"  AND lotname = '{lotid_s}'\n"
        f"  AND eventtime >= '{starttime_s}'\n"
        f"  AND eventtime <= '{endtime_s}'\n"
        "ORDER BY eventtime\n"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--lotid", required=True)
    p.add_argument("--start", required=True, help="'YYYY-MM-DD HH:MM:SS' (24h)")
    p.add_argument("--end", required=True, help="'YYYY-MM-DD HH:MM:SS' (24h)")
    p.add_argument("--max-rows", type=int, default=None)
    p.add_argument("--print-sql", action="store_true")
    args = p.parse_args()

    try:
        validate_time(args.start, field="--start")
        validate_time(args.end, field="--end")
        sql = build_sql(args.lotid, args.start, args.end)
    except ValueError as exc:
        return emit_error(str(exc))

    return write_sql_and_run(
        sql,
        tag="internalpri-history",
        max_rows=args.max_rows,
        print_sql=args.print_sql,
    )


if __name__ == "__main__":
    sys.exit(main())
