#!/usr/bin/env python3
"""Step 4: extract the actual effective value of a Sorting from rtdinfo over time.

Returns a time-ordered list of (TXNTIME, EQPID, RESULT) for the lot in the
window. RESULT is REGEXP_SUBSTR(rtdinfo, '<key>[^;]+') — the segment of
rtdinfo starting at the sorting key up to the next semicolon.

Pass --sorting NAME (case-insensitive); the script resolves the
case-sensitive rtdinfo key from rules/_registry.md. If RESULT comes back
fully NULL, the most likely cause is a misregistered rtdinfo key in the
registry — double-check rules/_registry.md.

Usage:
    python scripts/get_actual_value.py \\
        --lotid LOT0001 \\
        --sorting KEYLOT \\
        --start '2025-05-14 09:00:00' --end '2025-05-14 09:30:00'
"""

from __future__ import annotations

import argparse
import sys

from _common import (
    emit_error,
    escape_sql_string,
    resolve_sorting_key,
    validate_time,
    write_sql_and_run,
)


def build_sql(
    lotid: str, sorting_key: str, starttime: str, endtime: str
) -> str:
    lotid_s = escape_sql_string(lotid)
    sorting_key_s = escape_sql_string(sorting_key)
    starttime_s = escape_sql_string(starttime)
    endtime_s = escape_sql_string(endtime)
    return (
        "SELECT\n"
        "  txntime,\n"
        "  eqpid,\n"
        f"  REGEXP_SUBSTR(rtdinfo, CONCAT('{sorting_key_s}', '[^;]+')) AS result\n"
        "FROM rtd6.fabrtdlog\n"
        "WHERE 1=1\n"
        f"  AND lotid = '{lotid_s}'\n"
        "  AND rtdseq IS NOT NULL\n"
        f"  AND txntime >= '{starttime_s}'\n"
        f"  AND txntime <= '{endtime_s}'\n"
        "ORDER BY txntime\n"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--lotid", required=True)
    sort_group = p.add_mutually_exclusive_group(required=True)
    sort_group.add_argument(
        "--sorting",
        help="SORTING name; rtdinfo key auto-resolved from rules/_registry.md",
    )
    sort_group.add_argument(
        "--sorting-key",
        help="rtdinfo key override (case-sensitive); use for un-registered sortings",
    )
    p.add_argument("--start", required=True, help="'YYYY-MM-DD HH:MM:SS' (24h)")
    p.add_argument("--end", required=True, help="'YYYY-MM-DD HH:MM:SS' (24h)")
    p.add_argument("--max-rows", type=int, default=None)
    p.add_argument("--print-sql", action="store_true")
    args = p.parse_args()

    try:
        validate_time(args.start, field="--start")
        validate_time(args.end, field="--end")
        sorting_key = (
            args.sorting_key if args.sorting_key else resolve_sorting_key(args.sorting)
        )
        sql = build_sql(args.lotid, sorting_key, args.start, args.end)
    except ValueError as exc:
        return emit_error(str(exc))

    return write_sql_and_run(
        sql,
        tag="step4-actual-value",
        max_rows=args.max_rows,
        print_sql=args.print_sql,
    )


if __name__ == "__main__":
    sys.exit(main())
