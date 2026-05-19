#!/usr/bin/env python3
"""Step 3: which of the given EQPs actually had this Sorting present in rtdinfo.

Queries rtd6.fabrtdlog for DISTINCT eqpid where rtdinfo contains the
(case-sensitive) sorting key within [starttime, endtime] and eqpid is in the
list. This is the only trustworthy signal that a Sorting participated in
dispatching on an EQP.

Pass --sorting NAME (case-insensitive); the script resolves the
case-sensitive rtdinfo key from rules/_registry.md so the caller never has
to remember that e.g. INTERNALPRI lives in rtdinfo as 'InternalPri'.
For sortings not yet in the registry, use --sorting-key as an escape hatch.

Usage:
    python scripts/check_sorting_hit.py \\
        --eqpid EQP01 --eqpid EQP02 \\
        --sorting INTERNALPRI \\
        --start '2025-05-14 09:00:00' --end '2025-05-14 09:30:00'
"""

from __future__ import annotations

import argparse
import sys

from _common import (
    emit_error,
    escape_sql_string,
    format_eqpid_list,
    resolve_sorting_key,
    validate_time,
    write_sql_and_run,
)


def build_sql(
    eqpids: list[str], sorting_key: str, starttime: str, endtime: str
) -> str:
    eqpid_list = format_eqpid_list(eqpids)
    sorting_key_s = escape_sql_string(sorting_key)
    starttime_s = escape_sql_string(starttime)
    endtime_s = escape_sql_string(endtime)
    return (
        "SELECT DISTINCT eqpid\n"
        "FROM rtd6.fabrtdlog\n"
        "WHERE 1=1\n"
        f"  AND eqpid IN ({eqpid_list})\n"
        f"  AND INSTR(rtdinfo, '{sorting_key_s}') > 0\n"
        f"  AND txntime > '{starttime_s}'\n"
        f"  AND txntime <= '{endtime_s}'\n"
        "ORDER BY eqpid\n"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--eqpid",
        action="append",
        required=True,
        help="repeat for each EQP, e.g. --eqpid EQP01 --eqpid EQP02",
    )
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
        sql = build_sql(args.eqpid, sorting_key, args.start, args.end)
    except ValueError as exc:
        return emit_error(str(exc))

    return write_sql_and_run(
        sql,
        tag="step3-check-hit",
        max_rows=args.max_rows,
        print_sql=args.print_sql,
    )


if __name__ == "__main__":
    sys.exit(main())
