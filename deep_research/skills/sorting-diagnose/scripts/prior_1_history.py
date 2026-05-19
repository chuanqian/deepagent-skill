#!/usr/bin/env python3
"""PRIOR_1 rule: fetch the latest (eventtime, priority, internalpriority) for a lot in a window.

Source: rpt6.lot_history. The caller (the rule logic in rules/prior_1.md §4)
combines these fields:
  - if priority == 1: PRIOR_1 = -1 * concat(priority, zero-padded 2-digit internalpriority)
    (e.g. priority=1, internalpriority=2  -> "1" + "02" -> 102 -> -102)
  - else:             PRIOR_1 = -9999

We pull only the single newest row inside the window. Any earlier rows are not
needed: PRIOR_1 is a snapshot value driven by the most recent lot_history event.
Picking the latest row in SQL (rather than ORDER BY in Python) keeps the wire
result small and avoids surprises if --max-rows truncates a long history.

eventtime is a DATETIME column; MySQL accepts ISO-8601 strings directly in
range comparisons, so we compare the raw string literals without any explicit
date-parsing function.

Usage:
    python scripts/prior_1_history.py \\
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
    # Pick the newest row server-side with ORDER BY + LIMIT, so a chatty
    # lot_history won't blow past --max-rows and silently drop the row we
    # actually care about.
    return (
        "SELECT\n"
        "  eventtime,\n"
        "  priority,\n"
        "  internalpriority\n"
        "FROM rpt6.lot_history\n"
        "WHERE 1=1\n"
        f"  AND lotname = '{lotid_s}'\n"
        f"  AND eventtime >= '{starttime_s}'\n"
        f"  AND eventtime <= '{endtime_s}'\n"
        "ORDER BY eventtime DESC\n"
        "LIMIT 1\n"
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
        tag="prior1-history",
        max_rows=args.max_rows,
        print_sql=args.print_sql,
    )


if __name__ == "__main__":
    sys.exit(main())
